from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlencode

import proxy_transport as pt

API_PATH = "/simcar/tecnico.api/api"
VALID_STATUSES = {"CAR_VALIDADO", "CAR_VALIDADO_EM_REGULARIZACAO", "AGUARDANDO_ENVIO_PRA", "AGUARDANDO_ANALISE_PRA"}
BASE_HEADERS = {
    "Accept": "application/json, application/pdf, */*",
    "User-Agent": "Mozilla/5.0 SIMCAR-public-archiver/2.0",
    "Origin": "https://monitoramento.sema.mt.gov.br",
    "Referer": "https://monitoramento.sema.mt.gov.br/simcar/tecnico.app/publico/car",
    "Connection": "close",
}
MANIFEST_FIELDS = [
    "simcar_id", "federal_id", "official_status", "request_id", "result",
    "url", "http_status", "size_bytes", "sha256", "file", "proxy", "note", "timestamp",
]


@dataclass(frozen=True)
class CarRecord:
    simcar_id: str
    federal_id: str
    status: str
    request_id: str


def clean(value: str | None) -> str:
    return (value or "").strip().strip("[]")


def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("_") or "unknown"


def header(headers: dict, name: str, default: str = "") -> str:
    lname = name.lower()
    for k, v in headers.items():
        if k.lower() == lname:
            return v
    return default


def read_cars(path: Path, limit: int) -> list[CarRecord]:
    rows, seen = [], set()
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            status = clean(row.get("SITUACAO"))
            if status not in VALID_STATUSES:
                continue
            simcar_id = clean(row.get("NUMEROESTA"))
            federal_id = clean(row.get("CODIGO_CAR"))
            request_id = clean(row.get("REQUERIMEN")).removesuffix(".0")
            key = simcar_id or federal_id
            if not key or key in seen:
                continue
            seen.add(key)
            rows.append(CarRecord(simcar_id, federal_id, status, request_id))
            if limit and len(rows) >= limit:
                break
    return rows


def load_manifest(path: Path) -> dict[str, dict]:
    rows: dict[str, dict] = {}
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            key = row.get("simcar_id") or row.get("federal_id")
            if key:
                rows[key] = row
    return rows


def write_manifest(path: Path, rows: dict[str, dict]) -> None:
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=MANIFEST_FIELDS)
        writer.writeheader()
        for key in sorted(rows):
            writer.writerow({field: rows[key].get(field, "") for field in MANIFEST_FIELDS})
    tmp.replace(path)


def write_failed_list(path: Path, rows: dict[str, dict]) -> None:
    failed = {k: v for k, v in rows.items() if v.get("result") not in ("downloaded", "already_exists")}
    write_manifest(path, failed)


def find_record(pool: pt.ProxyPool, car: CarRecord, timeout: int, max_attempts: int) -> tuple[dict | None, str, int | None]:
    for field, value in (("NUMERO", car.simcar_id), ("NUMERO_CAR_FERERAL", car.federal_id)):
        if not value:
            continue
        payload = json.dumps({"Filtros": {field: value}, "ItensPorPagina": 10, "Pagina": 1,
                               "IsOrdenarCrescente": True, "ColunaOrdenar": "", "Colunas": []}).encode()
        path = f"{API_PATH}/Publico/ListarRequerimento"
        headers = {**BASE_HEADERS, "Content-Type": "application/json", "Content-Length": str(len(payload))}
        status, resp_headers, data, _ = pt.request_with_pool(pool, "POST", path, headers=headers, body=payload,
                                                               timeout=timeout, max_attempts=max_attempts)
        if status != 200:
            continue
        result = json.loads(data.decode("utf-8-sig"))
        items = result.get("Itens", []) if isinstance(result, dict) else result
        if items:
            exact = [x for x in items if clean(x.get("NumeroCompleto")) == car.simcar_id]
            return (exact or items)[0], path, status
    return None, "", None


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def save_pdf(folder: Path, target: Path, raw: bytes, metadata: dict) -> str:
    folder.mkdir(parents=True, exist_ok=True)
    target.write_bytes(raw)
    digest = sha256_bytes(raw)
    target.with_suffix(target.suffix + ".sha256").write_text(digest + "\n", encoding="ascii")
    (folder / "official_metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return digest


def process_car(pool: pt.ProxyPool, car: CarRecord, out_dir: Path, timeout: int, max_attempts: int) -> dict:
    folder = out_dir / safe_name(car.simcar_id or car.federal_id)
    target = folder / "registration_summary.pdf"
    row = {
        "simcar_id": car.simcar_id, "federal_id": car.federal_id, "official_status": car.status,
        "request_id": car.request_id, "result": "", "url": "", "http_status": "", "size_bytes": "",
        "sha256": "", "file": "", "proxy": "", "note": "", "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    if target.exists() and target.read_bytes()[:4] == b"%PDF":
        row["result"] = "already_exists"
        row["file"] = str(target)
        sha_side = target.with_suffix(target.suffix + ".sha256")
        row["sha256"] = sha_side.read_text().strip() if sha_side.exists() else sha256_bytes(target.read_bytes())
        row["size_bytes"] = str(target.stat().st_size)
        return row
    try:
        if car.request_id:
            path = f"{API_PATH}/Publico/BuscarPdfRecibo/{car.request_id}"
            headers = {**BASE_HEADERS}
            status, resp_headers, data, proxy = pt.request_with_pool(pool, "GET", path, headers=headers,
                                                                       timeout=timeout, max_attempts=max_attempts)
            row["url"], row["http_status"], row["proxy"] = path, status, proxy.key
            content_type = header(resp_headers, "Content-Type")
            if status != 200 or (not data.startswith(b"%PDF") and "pdf" not in content_type.lower()):
                row["result"] = "invalid_response"
                row["note"] = f"status={status} content_type={content_type} bytes={len(data)}"
                return row
            digest = save_pdf(folder, target, data, {"Id": car.request_id, "NumeroCompleto": car.simcar_id, "source": "REQUERIMEN"})
        else:
            record, search_path, search_status = find_record(pool, car, timeout, max_attempts)
            if not record:
                row["result"] = "not_found"
                row["url"] = search_path
                row["http_status"] = search_status or ""
                return row
            record_id = str(record["Id"])
            path = f"{API_PATH}/Publico/DownloadDemonstrativoCar/{record_id}"
            body = urlencode({"Authorization": "", "FormParams": ""}).encode("ascii")
            headers = {**BASE_HEADERS, "Content-Type": "application/x-www-form-urlencoded", "Content-Length": str(len(body))}
            status, resp_headers, data, proxy = pt.request_with_pool(pool, "POST", path, headers=headers, body=body,
                                                                       timeout=timeout, max_attempts=max_attempts)
            row["url"], row["http_status"], row["proxy"] = path, status, proxy.key
            content_type = header(resp_headers, "Content-Type")
            if status != 200 or (not data.startswith(b"%PDF") and "pdf" not in content_type.lower()):
                row["result"] = "invalid_response"
                row["note"] = f"status={status} content_type={content_type} bytes={len(data)}"
                return row
            digest = save_pdf(folder, target, data, record)
        row["result"] = "downloaded"
        row["file"] = str(target)
        row["size_bytes"] = str(target.stat().st_size)
        row["sha256"] = digest
        return row
    except pt.ProxyPoolExhausted as exc:
        row["result"] = "connection_error"
        row["note"] = str(exc)[:300]
        return row
    except Exception as exc:
        row["result"] = "error"
        row["note"] = f"{type(exc).__name__}: {exc}"[:300]
        return row


def preflight(pool: pt.ProxyPool, timeout: int) -> tuple[bool, str]:
    if pool.size() == 0:
        return False, "proxy pool is empty"
    payload = json.dumps({"Filtros": {"NUMERO": "PREFLIGHT"}, "ItensPorPagina": 1, "Pagina": 1,
                           "IsOrdenarCrescente": True, "ColunaOrdenar": "", "Colunas": []}).encode()
    headers = {**BASE_HEADERS, "Content-Type": "application/json", "Content-Length": str(len(payload))}
    try:
        status, _, _, proxy = pt.request_with_pool(pool, "POST", f"{API_PATH}/Publico/ListarRequerimento",
                                                     headers=headers, body=payload, timeout=timeout, max_attempts=3)
        return True, f"reachable via {proxy.key} (status={status})"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Archive all public validated SIMCAR PDFs via a rotating Brazilian-ISP proxy pool.")
    parser.add_argument("--input", type=Path, default=Path("data/pre/car_proxy/car_atp_joined_20260818.csv"))
    parser.add_argument("--output", type=Path, default=Path("data/raw/simcar_documents/validated_car_pdfs"))
    parser.add_argument("--proxy-pool", type=Path, default=Path("data/raw/simcar_documents/working_proxies.json"))
    parser.add_argument("--limit", type=int, default=0, help="0 means all eligible records")
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--max-attempts", type=int, default=6)
    parser.add_argument("--checkpoint-every", type=int, default=100)
    parser.add_argument("--skip-preflight", action="store_true")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    pool = pt.ProxyPool.load(args.proxy_pool)
    print(f"proxy_pool_size={pool.size()} ({args.proxy_pool})", flush=True)

    cars = read_cars(args.input, args.limit)
    print(f"eligible={len(cars)}", flush=True)

    if not args.skip_preflight:
        ok, note = preflight(pool, args.timeout)
        print(f"preflight: {'ok' if ok else 'FAILED'} - {note}", flush=True)
        if not ok:
            print("portal_unavailable_via_proxy_pool: aborting before batch (no records processed)", flush=True)
            sys.exit(75)

    manifest_path = args.output / "download_manifest.csv"
    failed_path = args.output / "failed_records.csv"
    rows = load_manifest(manifest_path)

    to_submit: list[CarRecord] = []
    for car in cars:
        key = car.simcar_id or car.federal_id
        folder = args.output / safe_name(key)
        target = folder / "registration_summary.pdf"
        if target.exists() and target.read_bytes()[:4] == b"%PDF":
            sha_side = target.with_suffix(target.suffix + ".sha256")
            rows[key] = {
                "simcar_id": car.simcar_id, "federal_id": car.federal_id, "official_status": car.status,
                "request_id": car.request_id, "result": "already_exists", "url": "", "http_status": "",
                "size_bytes": str(target.stat().st_size),
                "sha256": sha_side.read_text().strip() if sha_side.exists() else sha256_bytes(target.read_bytes()),
                "file": str(target), "proxy": "", "note": "", "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            }
        else:
            to_submit.append(car)

    print(f"already_valid_on_disk={len(cars) - len(to_submit)} to_download={len(to_submit)}", flush=True)

    completed = 0
    lock = threading.Lock()
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = {executor.submit(process_car, pool, car, args.output, args.timeout, args.max_attempts): car for car in to_submit}
        for future in as_completed(futures):
            car = futures[future]
            key = car.simcar_id or car.federal_id
            try:
                result_row = future.result()
            except Exception as exc:
                result_row = {"simcar_id": car.simcar_id, "federal_id": car.federal_id, "official_status": car.status,
                              "request_id": car.request_id, "result": "error", "url": "", "http_status": "",
                              "size_bytes": "", "sha256": "", "file": "", "proxy": "", "note": str(exc)[:300],
                              "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S")}
            with lock:
                rows[key] = result_row
                completed += 1
                if completed % args.checkpoint_every == 0:
                    write_manifest(manifest_path, rows)
                    print(f"progress {completed}/{len(to_submit)} live_proxies={pool.size()}", flush=True)
                if pool.size() == 0:
                    print("all proxies exhausted mid-batch; stopping further submissions", flush=True)

    write_manifest(manifest_path, rows)
    write_failed_list(failed_path, rows)

    counts: dict[str, int] = {}
    for row in rows.values():
        counts[row.get("result", "")] = counts.get(row.get("result", ""), 0) + 1

    print("=== SUMMARY ===")
    print(f"eligible={len(cars)}")
    for status in ("downloaded", "already_exists", "not_found", "invalid_response", "connection_error", "error"):
        print(f"{status}={counts.get(status, 0)}")
    print(f"live_proxies_remaining={pool.size()}")
    print(f"manifest={manifest_path}")
    print(f"failed_records={failed_path}")

    hard_failures = counts.get("connection_error", 0) + counts.get("error", 0) + counts.get("invalid_response", 0)
    sys.exit(2 if hard_failures else 0)


if __name__ == "__main__":
    main()
