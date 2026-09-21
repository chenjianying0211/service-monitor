"""LINE Messaging API 與 Email 發送，以及依監測項目分派通知。"""
import asyncio
import logging
from email.message import EmailMessage

import aiosmtplib
import httpx
from sqlalchemy import select

from .db import session_scope
from .models import (
    Contact, LineChannel, MonitorNotifyGroup, NotificationLog, NotifyGroupMember, SmtpProfile,
)
from .security import decrypt

log = logging.getLogger("notifier")
LINE_API = "https://api.line.me/v2/bot"


class NotifyError(Exception):
    pass


# ---------- LINE ----------
async def line_request(token: str, method: str, path: str, json: dict | None = None) -> dict:
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.request(method, f"{LINE_API}{path}", json=json,
                            headers={"Authorization": f"Bearer {token}"})
    if r.status_code >= 400:
        try:
            detail = r.json().get("message", r.text)
        except Exception:
            detail = r.text
        raise NotifyError(f"LINE API {r.status_code}: {detail}")
    return r.json() if r.content else {}


async def line_push(token: str, to: str, text: str) -> None:
    await line_request(token, "POST", "/message/push",
                       {"to": to, "messages": [{"type": "text", "text": text[:4900]}]})


async def line_reply(token: str, reply_token: str, text: str) -> None:
    await line_request(token, "POST", "/message/reply",
                       {"replyToken": reply_token, "messages": [{"type": "text", "text": text}]})


# ---------- Email ----------
async def send_email(profile: SmtpProfile, to: str, subject: str, body: str) -> None:
    msg = EmailMessage()
    msg["From"] = profile.from_addr
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    try:
        await aiosmtplib.send(
            msg, hostname=profile.host, port=profile.port,
            username=profile.username or None, password=decrypt(profile.password_enc) or None,
            use_tls=profile.security == "ssl", start_tls=profile.security == "starttls",
            timeout=20,
        )
    except Exception as e:
        raise NotifyError(f"SMTP 發送失敗: {e}") from e


# ---------- 對單一聯絡人發送 ----------
def _load_contact_ctx(contact_id: int) -> dict:
    """回傳 {contact, token, smtp, error}；有 error 時仍帶回 contact 以便寫紀錄。"""
    with session_scope() as s:
        c = s.get(Contact, contact_id)
        ctx = {"contact": c, "token": None, "smtp": None, "error": None}
        if not c:
            ctx["error"] = "聯絡人不存在"
        elif c.type in ("line_user", "line_group"):
            ch = s.get(LineChannel, c.line_channel_id) if c.line_channel_id else None
            if not ch or not ch.enabled:
                ctx["error"] = "LINE 官方帳號不存在或已停用"
            else:
                ctx["token"] = decrypt(ch.access_token_enc)
        else:
            p = s.get(SmtpProfile, c.smtp_profile_id) if c.smtp_profile_id else None
            if p is None:
                p = s.scalars(select(SmtpProfile).order_by(SmtpProfile.is_default.desc(),
                                                           SmtpProfile.id)).first()
            if p is None:
                ctx["error"] = "尚未設定 SMTP"
            ctx["smtp"] = p
        return ctx


async def send_to_contact(contact_id: int, subject: str, text: str, event: str,
                          monitor_id: int | None = None) -> None:
    """發送並寫入 notification_logs；失敗時拋出 NotifyError。"""
    ctx = await asyncio.to_thread(_load_contact_ctx, contact_id)
    contact = ctx["contact"]
    try:
        if ctx["error"]:
            raise NotifyError(ctx["error"])
        if ctx["token"]:
            await line_push(ctx["token"], contact.address, text)
        else:
            await send_email(ctx["smtp"], contact.address, subject, text)
        await asyncio.to_thread(_write_log, contact, event, monitor_id, True, None, text)
    except Exception as e:
        err = str(e)[:1000]
        log.warning("notify contact=%s failed: %s", contact_id, err)
        await asyncio.to_thread(_write_log, contact, event, monitor_id, False, err, text)
        raise NotifyError(err) from e


def _write_log(contact, event, monitor_id, success, error, content):
    with session_scope() as s:
        s.add(NotificationLog(
            channel="email" if contact is not None and contact.type == "email" else "line",
            target=contact.address if contact else "?",
            contact_name=contact.name if contact else None,
            monitor_id=monitor_id, event=event, success=success, error=error, content=content,
        ))


# ---------- 依監測項目分派 ----------
def _recipients(monitor_id: int, event: str) -> list[int]:
    with session_scope() as s:
        rows = s.execute(
            select(MonitorNotifyGroup.events, Contact.id)
            .join(NotifyGroupMember, NotifyGroupMember.group_id == MonitorNotifyGroup.group_id)
            .join(Contact, Contact.id == NotifyGroupMember.contact_id)
            .where(MonitorNotifyGroup.monitor_id == monitor_id, Contact.status == "active")
        ).all()
    ids: list[int] = []
    for events, cid in rows:
        if event in (events or "").split(",") and cid not in ids:
            ids.append(cid)
    return ids


async def dispatch(monitor_id: int, event: str, subject: str, text: str) -> None:
    ids = await asyncio.to_thread(_recipients, monitor_id, event)
    if not ids:
        log.info("monitor=%s event=%s 沒有設定收件人", monitor_id, event)
        return
    results = await asyncio.gather(
        *(send_to_contact(cid, subject, text, event, monitor_id) for cid in ids),
        return_exceptions=True,
    )
    fails = sum(isinstance(r, Exception) for r in results)
    log.info("monitor=%s event=%s 發送 %d 筆，失敗 %d", monitor_id, event, len(ids), fails)
