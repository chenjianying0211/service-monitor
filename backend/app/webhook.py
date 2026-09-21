"""LINE webhook：使用者加好友 / 機器人入群 / 傳「綁定」時，自動建立待啟用的聯絡人。"""
import asyncio
import base64
import hashlib
import hmac
import json
import logging

from fastapi import APIRouter, Header, HTTPException, Request
from sqlalchemy import select

from .db import session_scope
from .models import Contact, LineChannel
from .notifiers import NotifyError, line_reply, line_request
from .security import decrypt

log = logging.getLogger("webhook")
router = APIRouter(tags=["webhook"])
BIND_WORDS = {"綁定", "绑定", "bind", "/bind"}


def _channel_creds(cid: int) -> tuple[str, str] | None:
    with session_scope() as s:
        ch = s.get(LineChannel, cid)
        if not ch or not ch.enabled:
            return None
        return decrypt(ch.access_token_enc), decrypt(ch.secret_enc)


def _exists(cid: int, address: str) -> bool:
    with session_scope() as s:
        return s.scalars(select(Contact.id).where(Contact.line_channel_id == cid,
                                                  Contact.address == address)).first() is not None


def _upsert_pending(cid: int, ctype: str, address: str, name: str) -> tuple[Contact, bool]:
    with session_scope() as s:
        c = s.scalars(select(Contact).where(Contact.line_channel_id == cid,
                                            Contact.address == address)).first()
        if c:
            return c, False
        c = Contact(name=name[:128], type=ctype, address=address, line_channel_id=cid,
                    status="pending", note="由 LINE 綁定自動建立")
        s.add(c)
        s.flush()
        return c, True


async def _display_name(token: str, source: dict) -> str:
    try:
        if source.get("type") == "group":
            info = await line_request(token, "GET", f"/group/{source['groupId']}/summary")
            return f"群組：{info.get('groupName', '')}"
        if source.get("type") == "user":
            info = await line_request(token, "GET", f"/profile/{source['userId']}")
            return info.get("displayName", "LINE 使用者")
    except NotifyError:
        pass
    return "LINE 群組" if source.get("type") == "group" else "LINE 使用者"


@router.post("/webhook/line/{cid}")
async def line_webhook(cid: int, request: Request, x_line_signature: str = Header(default="")):
    body = await request.body()
    creds = await asyncio.to_thread(_channel_creds, cid)
    if not creds:
        raise HTTPException(404, "channel not found")
    token, secret = creds
    digest = hmac.new(secret.encode(), body, hashlib.sha256).digest()
    if not hmac.compare_digest(base64.b64encode(digest).decode(), x_line_signature):
        raise HTTPException(401, "invalid signature")

    for ev in json.loads(body or b"{}").get("events", []):
        etype, src = ev.get("type"), ev.get("source", {})
        is_bind = etype in ("follow", "join") or (
            etype == "message" and ev.get("message", {}).get("type") == "text"
            and ev["message"].get("text", "").strip().lower() in BIND_WORDS)
        # 任何訊息都登記為待啟用（例如加好友時 webhook 尚未開啟、錯過 follow 事件）；仍需管理員啟用
        if not is_bind and etype != "message":
            continue
        if src.get("type") == "group":
            ctype, address = "line_group", src.get("groupId")
        elif src.get("type") == "user":
            ctype, address = "line_user", src.get("userId")
        else:
            continue  # 多人聊天室 (room) 不支援
        if not is_bind and await asyncio.to_thread(_exists, cid, address):
            continue  # 已登記過的一般訊息不處理（避免群組每則訊息都查 LINE API）
        name = await _display_name(token, src)
        contact, created = await asyncio.to_thread(_upsert_pending, cid, ctype, address, name)
        log.info("LINE 綁定 channel=%s %s %s created=%s", cid, ctype, address, created)
        if ev.get("replyToken") and (is_bind or created):  # 一般訊息只在首次登記時回覆
            if contact.status == "active":
                msg = "✅ 此帳號已啟用監控通知。"
            else:
                msg = ("📝 已收到綁定申請，請通知管理員到監控平台「通知設定 → 聯絡人」啟用。\n"
                       f"名稱：{contact.name}")
            try:
                await line_reply(token, ev["replyToken"], msg)
            except NotifyError as e:
                log.warning("reply 失敗: %s", e)
    return {"ok": True}
