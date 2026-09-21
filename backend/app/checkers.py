"""各類型監測的實作。每個 checker 回傳 CheckOutcome，不拋例外。"""
import asyncio
import socket
import ssl
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx


@dataclass
class CheckOutcome:
    ok: bool
    message: str
    latency_ms: int | None = None
    status_code: int | None = None


def _status_ok(code: int, expected: str) -> bool:
    for part in (expected or "200-399").split(","):
        part = part.strip()
        if "-" in part:
            lo, hi = part.split("-", 1)
            if int(lo) <= code <= int(hi):
                return True
        elif part and int(part) == code:
            return True
    return False


def _short_err(e: Exception) -> str:
    name = type(e).__name__
    text = str(e) or name
    mapping = {
        "ConnectError": "連線失敗",
        "ConnectTimeout": "連線逾時",
        "ReadTimeout": "讀取逾時",
        "TimeoutError": "逾時",
        "ConnectionRefusedError": "連線被拒絕",
    }
    return f"{mapping.get(name, name)}: {text}"[:500]


async def check_http(m, keyword_mode: bool = False, url: str | None = None) -> CheckOutcome:
    url = url or m.target
    start = time.perf_counter()
    try:
        async with httpx.AsyncClient(
            verify=not m.ignore_tls, follow_redirects=m.follow_redirects, timeout=m.timeout_sec,
            headers={"User-Agent": "ServiceMonitor/1.0"},
        ) as c:
            r = await c.request(m.method or "GET", url)
        ms = int((time.perf_counter() - start) * 1000)
        if not _status_ok(r.status_code, m.expected_status):
            return CheckOutcome(False, f"HTTP {r.status_code}（預期 {m.expected_status}）", ms, r.status_code)
        if keyword_mode and m.keyword and m.keyword not in r.text:
            return CheckOutcome(False, f"找不到關鍵字「{m.keyword}」", ms, r.status_code)
        return CheckOutcome(True, f"HTTP {r.status_code}", ms, r.status_code)
    except Exception as e:
        return CheckOutcome(False, _short_err(e), int((time.perf_counter() - start) * 1000))


def _split_host_port(target: str, default_port: int) -> tuple[str, int]:
    if "://" in target:
        u = urlparse(target)
        return u.hostname or "", u.port or default_port
    if ":" in target:
        h, p = target.rsplit(":", 1)
        return h, int(p)
    return target, default_port


async def check_tcp(m) -> CheckOutcome:
    host, port = _split_host_port(m.target, 80)
    start = time.perf_counter()
    try:
        _, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=m.timeout_sec)
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        ms = int((time.perf_counter() - start) * 1000)
        return CheckOutcome(True, f"{host}:{port} 可連線", ms)
    except Exception as e:
        return CheckOutcome(False, _short_err(e), int((time.perf_counter() - start) * 1000))


def _cert_expiry(host: str, port: int, timeout: int) -> datetime:
    ctx = ssl.create_default_context()
    with socket.create_connection((host, port), timeout=timeout) as sock:
        with ctx.wrap_socket(sock, server_hostname=host) as ss:
            cert = ss.getpeercert()
    return datetime.fromtimestamp(ssl.cert_time_to_seconds(cert["notAfter"]), tz=timezone.utc)


async def check_ssl(m) -> CheckOutcome:
    host, port = _split_host_port(m.target, 443)
    start = time.perf_counter()
    try:
        exp = await asyncio.to_thread(_cert_expiry, host, port, m.timeout_sec)
        ms = int((time.perf_counter() - start) * 1000)
        days = (exp - datetime.now(timezone.utc)).days
        msg = f"憑證剩 {days} 天到期（{exp:%Y-%m-%d}）"
        if days <= m.ssl_warn_days:
            return CheckOutcome(False, msg + f"，低於警戒 {m.ssl_warn_days} 天", ms)
        return CheckOutcome(True, msg, ms)
    except ssl.SSLCertVerificationError as e:
        return CheckOutcome(False, f"憑證驗證失敗: {e.verify_message}")
    except Exception as e:
        return CheckOutcome(False, _short_err(e))


_docker_client = None


def _docker_state(name: str) -> tuple[bool, str]:
    global _docker_client
    import docker
    if _docker_client is None:
        _docker_client = docker.from_env()
    try:
        c = _docker_client.containers.get(name)
    except docker.errors.NotFound:
        return False, f"找不到容器 {name}"
    state = c.attrs.get("State", {})
    status = state.get("Status")
    health = (state.get("Health") or {}).get("Status")
    if status != "running":
        return False, f"容器狀態 {status}（exit {state.get('ExitCode')}）"
    if health and health != "healthy":
        return False, f"容器運行中但健康檢查為 {health}"
    return True, f"running{f' / {health}' if health else ''}"


async def check_docker(m) -> CheckOutcome:
    start = time.perf_counter()
    try:
        ok, msg = await asyncio.to_thread(_docker_state, m.target)
        return CheckOutcome(ok, msg, int((time.perf_counter() - start) * 1000))
    except Exception as e:
        return CheckOutcome(False, f"無法連到 Docker: {_short_err(e)}")


async def check_proxy_pair(m) -> CheckOutcome:
    """同時打網域與後端，判斷是後端掛了還是 nginx 轉發壞了。"""
    front, back = await asyncio.gather(check_http(m, url=m.target), check_http(m, url=m.backend_url))
    if front.ok and back.ok:
        return CheckOutcome(True, f"網域 {front.message}／後端 {back.message}", front.latency_ms, front.status_code)
    if not back.ok and not front.ok:
        return CheckOutcome(False, f"後端服務中斷（{back.message}），網域同時無法存取", front.latency_ms, front.status_code)
    if not back.ok:
        return CheckOutcome(False, f"後端異常（{back.message}），但網域仍回應 {front.message}", front.latency_ms, front.status_code)
    return CheckOutcome(False, f"轉發異常：後端正常，但網域失敗（{front.message}）— 請檢查 nginx / DNS / SSL",
                        front.latency_ms, front.status_code)


async def run_check(m) -> CheckOutcome:
    t = m.type
    if t == "http":
        return await check_http(m)
    if t == "keyword":
        return await check_http(m, keyword_mode=True)
    if t == "tcp":
        return await check_tcp(m)
    if t == "ssl_cert":
        return await check_ssl(m)
    if t == "docker":
        return await check_docker(m)
    if t == "proxy_pair":
        return await check_proxy_pair(m)
    return CheckOutcome(False, f"未知監測類型 {t}")
