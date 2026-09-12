"""Low-level HTTPS transport that tunnels through a SOCKS4/SOCKS5/HTTP-CONNECT
proxy to a fixed target IP+hostname, bypassing the SOCKS4/requests remote-DNS
mismatch that made `requests`' socks4:// scheme hang against these proxies.
"""
from __future__ import annotations

import http.client
import json
import socket
import ssl
import threading
import time
from dataclasses import dataclass
from pathlib import Path

import socks

TARGET_HOST = "monitoramento.sema.mt.gov.br"
TARGET_IP = "201.49.166.36"
TARGET_PORT = 443

_SOCKS_TYPES = {"socks4": socks.SOCKS4, "socks5": socks.SOCKS5}


@dataclass
class Proxy:
    ip: str
    port: int
    protocol: str  # "socks4" | "socks5" | "http" | "https"
    org: str = ""

    @property
    def key(self) -> str:
        return f"{self.ip}:{self.port}"


class ProxyRequestError(Exception):
    pass


def _connect_raw_socket(proxy: Proxy, timeout: float) -> socket.socket:
    if proxy.protocol in _SOCKS_TYPES:
        s = socks.socksocket()
        s.set_proxy(_SOCKS_TYPES[proxy.protocol], proxy.ip, proxy.port)
        s.settimeout(timeout)
        s.connect((TARGET_IP, TARGET_PORT))
        return s
    if proxy.protocol in ("http", "https"):
        s = socket.create_connection((proxy.ip, proxy.port), timeout=timeout)
        s.settimeout(timeout)
        connect_req = f"CONNECT {TARGET_IP}:{TARGET_PORT} HTTP/1.1\r\nHost: {TARGET_IP}:{TARGET_PORT}\r\n\r\n"
        s.sendall(connect_req.encode("ascii"))
        response = b""
        while b"\r\n\r\n" not in response:
            chunk = s.recv(4096)
            if not chunk:
                break
            response += chunk
        status_line = response.split(b"\r\n", 1)[0]
        if b"200" not in status_line:
            s.close()
            raise ProxyRequestError(f"CONNECT tunnel refused: {status_line!r}")
        return s
    raise ProxyRequestError(f"unsupported proxy protocol {proxy.protocol!r}")


def request(proxy: Proxy, method: str, path: str, *, headers: dict | None = None,
            body: bytes | None = None, timeout: float = 25.0) -> tuple[int, dict, bytes]:
    """Send one HTTPS request to TARGET_HOST through `proxy`. Returns (status, headers, body)."""
    raw = _connect_raw_socket(proxy, timeout)
    ctx = ssl.create_default_context()
    tls = ctx.wrap_socket(raw, server_hostname=TARGET_HOST)
    tls.settimeout(timeout)
    conn = http.client.HTTPConnection(TARGET_HOST)
    conn.sock = tls
    try:
        conn.request(method, path, body=body, headers=headers or {})
        resp = conn.getresponse()
        data = resp.read()
        return resp.status, dict(resp.getheaders()), data
    finally:
        conn.close()


class ProxyPoolExhausted(Exception):
    pass


class ProxyPool:
    """Thread-safe round-robin proxy pool with failure-based eviction."""

    def __init__(self, proxies: list[Proxy], max_consecutive_failures: int = 4):
        self._proxies = list(proxies)
        self._idx = 0
        self._lock = threading.Lock()
        self._fail_counts: dict[str, int] = {p.key: 0 for p in proxies}
        self._max_failures = max_consecutive_failures

    @classmethod
    def load(cls, path: Path) -> "ProxyPool":
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return cls([Proxy(ip=d["ip"], port=d["port"], protocol=d["protocol"], org=d.get("org", "")) for d in data])

    def get(self) -> Proxy | None:
        with self._lock:
            if not self._proxies:
                return None
            proxy = self._proxies[self._idx % len(self._proxies)]
            self._idx += 1
            return proxy

    def mark_success(self, proxy: Proxy) -> None:
        with self._lock:
            self._fail_counts[proxy.key] = 0

    def mark_failure(self, proxy: Proxy) -> None:
        with self._lock:
            self._fail_counts[proxy.key] = self._fail_counts.get(proxy.key, 0) + 1
            if self._fail_counts[proxy.key] >= self._max_failures:
                self._proxies = [p for p in self._proxies if p.key != proxy.key]

    def size(self) -> int:
        with self._lock:
            return len(self._proxies)


def request_with_pool(pool: ProxyPool, method: str, path: str, *, headers: dict | None = None,
                       body: bytes | None = None, timeout: float = 30.0,
                       max_attempts: int = 6) -> tuple[int, dict, bytes, Proxy]:
    """Try the request across up to max_attempts proxies drawn from the pool,
    with exponential backoff between attempts and 429/5xx retried on a fresh proxy."""
    last_exc: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        proxy = pool.get()
        if proxy is None:
            raise ProxyPoolExhausted("no working proxies left in pool")
        try:
            status, resp_headers, data = request(proxy, method, path, headers=headers, body=body, timeout=timeout)
        except Exception as exc:
            last_exc = exc
            pool.mark_failure(proxy)
            time.sleep(min(30.0, 1.5 * attempt))
            continue
        if status == 429 or status >= 500:
            pool.mark_failure(proxy)
            retry_after = resp_headers.get("Retry-After") or resp_headers.get("retry-after")
            try:
                sleep_s = float(retry_after) if retry_after else 1.5 * attempt
            except ValueError:
                sleep_s = 1.5 * attempt
            time.sleep(min(30.0, sleep_s))
            continue
        pool.mark_success(proxy)
        return status, resp_headers, data, proxy
    if last_exc:
        raise last_exc
    raise ProxyPoolExhausted(f"exhausted {max_attempts} attempts without a usable response")


def probe(proxy: Proxy, timeout: float = 15.0) -> tuple[bool, str]:
    """Real end-to-end check: does a full HTTPS POST through this proxy succeed?"""
    body = (b'{"Filtros":{"NUMERO":"PREFLIGHT-PROBE"},"ItensPorPagina":1,"Pagina":1,'
            b'"IsOrdenarCrescente":true,"ColunaOrdenar":"","Colunas":[]}')
    headers = {
        "Content-Type": "application/json", "Content-Length": str(len(body)),
        "Accept": "application/json, */*", "Connection": "close",
        "User-Agent": "Mozilla/5.0 SIMCAR-public-archiver/2.0",
    }
    t0 = time.time()
    try:
        status, _, data = request(proxy, "POST", "/simcar/tecnico.api/api/Publico/ListarRequerimento",
                                   headers=headers, body=body, timeout=timeout)
        elapsed = time.time() - t0
        if status == 200:
            return True, f"ok in {elapsed:.1f}s"
        return False, f"http_status={status} in {elapsed:.1f}s"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc} ({time.time() - t0:.1f}s)"
