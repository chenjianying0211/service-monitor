"""外部回報端點：其他主機自行監控，定時打這個網址回報狀態，由本平台統一發通知。

GET/POST /api/push/{token}?status=up|down&msg=說明&ping=毫秒
免登入，密鑰即憑證（可在網頁重新產生）。
"""
import asyncio
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from ..checkers import CheckOutcome
from ..db import session_scope
from ..engine import apply_and_notify
from ..models import Monitor, utcnow

router = APIRouter(tags=["push"])


def _touch(token: str) -> tuple[int, bool] | None:
    with session_scope() as s:
        m = s.scalars(select(Monitor).where(Monitor.type == "push", Monitor.target == token)).first()
        if not m:
            return None
        if m.enabled:
            m.last_push_at = utcnow()
        return m.id, m.enabled


@router.api_route("/api/push/{token}", methods=["GET", "POST"])
async def push(
    token: str,
    status: Literal["up", "down"] = Query("up", description="up = 正常，down = 異常"),
    msg: str | None = Query(None, max_length=500, description="狀態說明，會出現在通知內容"),
    ping: int | None = Query(None, ge=0, description="回應時間（毫秒），用於圖表"),
):
    found = await asyncio.to_thread(_touch, token)
    if not found:
        raise HTTPException(404, "回報網址無效")
    monitor_id, enabled = found
    if not enabled:
        return {"ok": True, "paused": True}
    ok = status == "up"
    await apply_and_notify(monitor_id, CheckOutcome(ok, msg or ("回報正常" if ok else "回報異常"), ping))
    return {"ok": True}
