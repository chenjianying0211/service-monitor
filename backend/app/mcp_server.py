"""MCP 通道：讓 AI 透過 Model Context Protocol 查詢與管理主機 / 監測項目。

掛在 /mcp/（Streamable HTTP），以 API 金鑰驗證：Authorization: Bearer smk_...
工具直接呼叫既有 API 的函式，驗證、排程、通知群組邏輯與網頁完全一致。
"""
import asyncio
from typing import Any, Literal
from urllib.parse import urlparse

from fastapi import HTTPException
from pydantic import ValidationError
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations
from sqlalchemy import select

from .api import hosts as hosts_api
from .api import monitors as mon_api
from .api import notify as notify_api
from .api.apikeys import verify_api_key
from .api.common import iso, row_dict, uptime_map
from .checkers import run_check
from .config import settings
from .db import SessionLocal
from .engine import execute
from .models import Host, Incident, Monitor, MonitorNotifyGroup, NotifyGroup

MonitorType = Literal["http", "keyword", "tcp", "ssl_cert", "docker", "proxy_pair"]

mcp = MCPServer(
    name="service-monitor",
    title="服務監控平台",
    instructions=(
        "管理服務監控平台的主機與監測項目。監測類型："
        "http（網址狀態碼）、keyword（網頁需含關鍵字）、tcp（host:port 可連線）、"
        "ssl_cert（憑證到期天數）、docker（僅限平台所在主機 testlinux 的容器）、"
        "proxy_pair（nginx 轉發：target=對外網址、backend_url=後端網址）。"
        "新增前請先用 list_hosts / list_notify_groups 取得正確名稱；"
        "不確定目標是否正確時可先用 test_target 試打。"
    ),
)

READ = ToolAnnotations(readOnlyHint=True)
WRITE = ToolAnnotations(readOnlyHint=False, destructiveHint=False)
DESTRUCTIVE = ToolAnnotations(readOnlyHint=False, destructiveHint=True)


def _db(fn, *args, **kwargs):
    """在 thread 中開 session 執行同步 DB 函式，HTTPException 轉成可讀錯誤。"""
    def run():
        db = SessionLocal()
        try:
            return fn(db, *args, **kwargs)
        except HTTPException as e:
            raise ToolError(str(e.detail)) from None
        except ValidationError as e:
            raise ToolError(_fmt_validation(e)) from None
        finally:
            db.close()
    return asyncio.to_thread(run)


def _fmt_validation(e: ValidationError) -> str:
    return "參數錯誤：" + "；".join(f"{'.'.join(map(str, x['loc']))}: {x['msg']}" for x in e.errors())


def _resolve_host(db, host: str | int | None) -> int | None:
    if host in (None, ""):
        return None
    q = select(Host).where(Host.id == int(host)) if str(host).isdigit() else select(Host).where(Host.name == str(host))
    h = db.scalars(q).first()
    if not h:
        names = ", ".join(db.scalars(select(Host.name)))
        raise ToolError(f"找不到主機「{host}」。現有主機：{names or '（無）'}")
    return h.id


def _resolve_groups(db, names: list[str] | None) -> list[mon_api.GroupLink] | None:
    if names is None:
        return None
    all_groups = {g.name: g.id for g in db.scalars(select(NotifyGroup))}
    links = []
    for n in names:
        if n not in all_groups:
            raise ToolError(f"找不到通知群組「{n}」。現有群組：{', '.join(all_groups) or '（無）'}")
        links.append(mon_api.GroupLink(group_id=all_groups[n]))
    return links


def _monitor_brief(m: Monitor, host_names: dict[int, str]) -> dict[str, Any]:
    return {
        "id": m.id, "name": m.name, "type": m.type, "target": m.target, "backend_url": m.backend_url,
        "host": host_names.get(m.host_id) if m.host_id else None,
        "status": m.status if m.enabled else "PAUSED", "enabled": m.enabled,
        "last_message": m.last_message, "last_latency_ms": m.last_latency_ms,
        "last_check_at": iso(m.last_check_at), "interval_sec": m.interval_sec, "tags": m.tags,
    }


def _monitor_body(db, current: dict[str, Any], changes: dict[str, Any]) -> mon_api.MonitorIn:
    data = {**current, **{k: v for k, v in changes.items() if v is not None}}
    if "host" in changes:
        data["host_id"] = _resolve_host(db, changes["host"])
    data.pop("host", None)
    groups = _resolve_groups(db, changes.get("notify_groups"))
    data.pop("notify_groups", None)
    if groups is not None:
        data["groups"] = groups
    return mon_api.MonitorIn(**data)


# ---------------- 查詢 ----------------
@mcp.tool(annotations=READ)
async def dashboard_summary() -> dict:
    """整體狀態摘要：各狀態數量、各主機狀態、目前中斷中的項目。"""
    def q(db):
        hosts = {h.id: h.name for h in db.scalars(select(Host))}
        mons = db.scalars(select(Monitor)).all()
        counts: dict[str, int] = {}
        by_host: dict[str, dict[str, int]] = {}
        for m in mons:
            st = m.status if m.enabled else "PAUSED"
            counts[st] = counts.get(st, 0) + 1
            hn = hosts.get(m.host_id, "未指定主機")
            by_host.setdefault(hn, {})[st] = by_host.setdefault(hn, {}).get(st, 0) + 1
        down = [_monitor_brief(m, hosts) for m in mons if m.enabled and m.status in ("DOWN", "PENDING")]
        return {"total": len(mons), "counts": counts, "by_host": by_host, "problems": down}
    return await _db(q)


@mcp.tool(annotations=READ)
async def list_hosts() -> list[dict]:
    """列出所有主機（名稱、IP、OS、區域、資源群組、VM 規格、監測數量）。"""
    return await _db(hosts_api.list_hosts)


@mcp.tool(annotations=READ)
async def list_monitors(host: str | None = None, status: str | None = None) -> list[dict]:
    """列出監測項目。可用 host（主機名稱）與 status（UP/DOWN/PENDING/PAUSED/UNKNOWN）過濾。"""
    def q(db):
        hosts = {h.id: h.name for h in db.scalars(select(Host))}
        hid = _resolve_host(db, host) if host else None
        out = []
        for m in db.scalars(select(Monitor).order_by(Monitor.name)):
            if host and m.host_id != hid:
                continue
            b = _monitor_brief(m, hosts)
            if status and b["status"] != status.upper():
                continue
            out.append(b)
        return out
    return await _db(q)


@mcp.tool(annotations=READ)
async def get_monitor(monitor_id: int) -> dict:
    """取得單一監測項目的完整設定、可用率（24h/7d/30d）、通知群組與最近 10 筆中斷事件。"""
    def q(db):
        m = db.get(Monitor, monitor_id)
        if not m:
            raise ToolError(f"找不到監測項目 id={monitor_id}")
        d = row_dict(m)
        groups = {g.id: g.name for g in db.scalars(select(NotifyGroup))}
        d["notify_groups"] = [groups.get(g.group_id) for g in db.scalars(
            select(MonitorNotifyGroup).where(MonitorNotifyGroup.monitor_id == m.id))]
        d["host"] = db.get(Host, m.host_id).name if m.host_id else None
        d["uptime"] = {"24h": uptime_map(db, 24).get(m.id), "7d": uptime_map(db, 168, 300).get(m.id),
                       "30d": uptime_map(db, 720, 600).get(m.id)}
        d["recent_incidents"] = [row_dict(i) for i in db.scalars(
            select(Incident).where(Incident.monitor_id == m.id).order_by(Incident.started_at.desc()).limit(10))]
        return d
    return await _db(q)


@mcp.tool(annotations=READ)
async def list_notify_groups() -> list[dict]:
    """列出通知群組（名稱與收件人數），新增監測時 notify_groups 參數請用這裡的名稱。"""
    def q(db):
        return [{"id": g["id"], "name": g["name"], "description": g["description"],
                 "contacts": len(g["contact_ids"]), "monitors": len(g["monitor_ids"])}
                for g in notify_api.list_groups(db)]
    return await _db(q)


@mcp.tool(annotations=READ)
async def list_open_incidents() -> list[dict]:
    """列出目前進行中（尚未恢復）的中斷事件。"""
    return await _db(lambda db: mon_api.list_incidents(only_open=True, limit=200, db=db))


@mcp.tool(annotations=READ)
async def test_target(type: MonitorType, target: str, backend_url: str | None = None,
                      keyword: str | None = None, expected_status: str = "200-399",
                      timeout_sec: int = 10) -> dict:
    """不存檔，直接試打一次目標，確認設定是否正確（ok / message / latency_ms）。"""
    try:
        body = mon_api.MonitorIn(name="test", type=type, target=target, backend_url=backend_url,
                                 keyword=keyword, expected_status=expected_status, timeout_sec=timeout_sec)
        mon_api._validate(body)
    except ValidationError as e:
        raise ToolError(_fmt_validation(e)) from None
    except HTTPException as e:
        raise ToolError(str(e.detail)) from None
    r = await run_check(Monitor(**body.model_dump(exclude={"groups"})))
    return {"ok": r.ok, "message": r.message, "latency_ms": r.latency_ms, "status_code": r.status_code}


# ---------------- 新增 / 修改 ----------------
@mcp.tool(annotations=WRITE)
async def create_host(name: str, ip: str | None = None, os: str | None = None, region: str | None = None,
                      resource_group: str | None = None, vm_size: str | None = None,
                      description: str | None = None) -> dict:
    """新增主機。os 建議填 Linux 或 Windows。"""
    return await _db(lambda db: hosts_api.create_host(hosts_api.HostIn(
        name=name, ip=ip, os=os, region=region, resource_group=resource_group,
        vm_size=vm_size, description=description), db))


@mcp.tool(annotations=WRITE)
async def create_monitor(
    name: str, type: MonitorType, target: str, host: str | None = None,
    backend_url: str | None = None, keyword: str | None = None, expected_status: str = "200-399",
    interval_sec: int = 60, timeout_sec: int = 10, retries: int = 3, resend_interval_min: int = 60,
    ssl_warn_days: int = 14, tags: str | None = None, notify_groups: list[str] | None = None,
    description: str | None = None, enabled: bool = True,
) -> dict:
    """新增監測項目並立即開始檢查。

    target 格式：http/keyword/proxy_pair 為完整網址；tcp 為 host:port；ssl_cert 為網域；docker 為容器名稱。
    host 為主機名稱（list_hosts）；notify_groups 為通知群組名稱清單（list_notify_groups）。
    retries = 連續失敗幾次才告警；resend_interval_min = 持續中斷時每幾分鐘重複提醒（0 不提醒）。
    """
    def q(db):
        body = _monitor_body(db, {}, dict(
            name=name, type=type, target=target, host=host, backend_url=backend_url, keyword=keyword,
            expected_status=expected_status, interval_sec=interval_sec, timeout_sec=timeout_sec,
            retries=retries, resend_interval_min=resend_interval_min, ssl_warn_days=ssl_warn_days,
            tags=tags, notify_groups=notify_groups or [], description=description, enabled=enabled))
        return mon_api.create_monitor(body, db)
    return await _db(q)


@mcp.tool(annotations=WRITE)
async def update_monitor(
    monitor_id: int, name: str | None = None, target: str | None = None, host: str | None = None,
    backend_url: str | None = None, keyword: str | None = None, expected_status: str | None = None,
    interval_sec: int | None = None, timeout_sec: int | None = None, retries: int | None = None,
    resend_interval_min: int | None = None, ssl_warn_days: int | None = None, tags: str | None = None,
    notify_groups: list[str] | None = None, description: str | None = None,
) -> dict:
    """修改監測項目；只需給要改的欄位。notify_groups 給值時會整批取代原本的通知群組。"""
    def q(db):
        m = db.get(Monitor, monitor_id)
        if not m:
            raise ToolError(f"找不到監測項目 id={monitor_id}")
        current = {k: getattr(m, k) for k in mon_api.MonitorIn.model_fields if k != "groups"}
        current["groups"] = [mon_api.GroupLink(group_id=g["group_id"], events=g["events"])
                             for g in mon_api._groups_of(db, monitor_id)]
        changes = dict(name=name, target=target, backend_url=backend_url, keyword=keyword,
                       expected_status=expected_status, interval_sec=interval_sec, timeout_sec=timeout_sec,
                       retries=retries, resend_interval_min=resend_interval_min, ssl_warn_days=ssl_warn_days,
                       tags=tags, description=description, notify_groups=notify_groups)
        if host is not None:
            changes["host"] = host
        return mon_api.update_monitor(monitor_id, _monitor_body(db, current, changes), db)
    return await _db(q)


@mcp.tool(annotations=WRITE)
async def set_monitor_enabled(monitor_id: int, enabled: bool) -> dict:
    """暫停（enabled=false）或恢復（enabled=true）監測。"""
    def q(db):
        m = db.get(Monitor, monitor_id)
        if not m:
            raise ToolError(f"找不到監測項目 id={monitor_id}")
        if m.enabled == enabled:
            return {"enabled": enabled, "changed": False}
        return {**mon_api.toggle_monitor(monitor_id, db), "changed": True}
    return await _db(q)


@mcp.tool(annotations=WRITE)
async def check_monitor_now(monitor_id: int) -> dict:
    """立即執行一次檢查並回傳最新狀態。"""
    await execute(monitor_id)
    return await get_monitor(monitor_id)


@mcp.tool(annotations=DESTRUCTIVE)
async def delete_monitor(monitor_id: int) -> dict:
    """刪除監測項目與其所有歷史紀錄（無法復原）。"""
    return await _db(lambda db: mon_api.delete_monitor(monitor_id, db))


# ---------------- ASGI：驗證 + 掛載 ----------------
def _allowed_hosts() -> list[str]:
    hosts = ["127.0.0.1:*", "localhost:*", "127.0.0.1", "localhost"]
    public = urlparse(settings.public_base_url).netloc
    if public:
        hosts.append(public)
    return hosts


_inner_app = mcp.streamable_http_app(
    streamable_http_path="/",
    stateless_http=True,
    json_response=True,
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=True, allowed_hosts=_allowed_hosts(), allowed_origins=[]),
)


async def mcp_asgi(scope, receive, send):
    """檢查 API 金鑰（Authorization: Bearer 或 X-API-Key）後交給 MCP app。"""
    if scope["type"] == "http":
        headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
        auth = headers.get("authorization", "")
        key = auth[7:].strip() if auth.lower().startswith("bearer ") else headers.get("x-api-key", "")
        if not await asyncio.to_thread(verify_api_key, key):
            await send({"type": "http.response.start", "status": 401,
                        "headers": [(b"content-type", b"application/json"),
                                    (b"www-authenticate", b'Bearer realm="service-monitor"')]})
            await send({"type": "http.response.body",
                        "body": '{"error":"invalid or missing API key"}'.encode()})
            return
    await _inner_app(scope, receive, send)
