"""Verify that every analytical input is stored inside the project folder."""
from __future__ import annotations

import json
from pathlib import Path

import _00_paths as paths


ROOT = paths.ROOT.resolve()


def inside_project(value: str | Path) -> bool:
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = ROOT / candidate
    try:
        candidate.resolve().relative_to(ROOT)
        return True
    except ValueError:
        return False


def main() -> None:
    failures: list[str] = []
    config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    for name, value in config.get("inputs", {}).items():
        path = ROOT / value
        if not inside_project(path):
            failures.append(f"config input outside project: {name} -> {value}")
        elif not path.exists():
            failures.append(f"missing config input: {name} -> {value}")

    for metadata_path in (ROOT / "data/pre").glob("*/layers_meta.json"):
        for row in json.loads(metadata_path.read_text(encoding="utf-8")):
            value = row.get("path")
            if value and not inside_project(value):
                failures.append(f"layer outside project: {metadata_path.relative_to(ROOT)} -> {value}")
            elif value and not Path(value).exists():
                failures.append(f"missing layer: {metadata_path.relative_to(ROOT)} -> {value}")

    links = [p for p in (ROOT / "data").rglob("*") if p.is_symlink()]
    for link in links:
        if not inside_project(link.resolve()):
            failures.append(f"external symbolic link: {link.relative_to(ROOT)} -> {link.resolve()}")

    data_files = [p for p in (ROOT / "data").rglob("*") if p.is_file()]
    total_bytes = sum(p.stat().st_size for p in data_files)
    report = {
        "project_root": ".",
        "data_file_count": len(data_files),
        "data_size_bytes": total_bytes,
        "configured_inputs": len(config.get("inputs", {})),
        "external_input_failures": len(failures),
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
    }
    out = ROOT / "qa" / "self_contained_project_audit.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
