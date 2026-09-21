from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..models import (
    Contact, LineChannel, MaintenanceWindow, Monitor, MonitorNotifyGroup, NotificationLog,
    NotifyGroup, NotifyGroupMember, SmtpProfile,
)
from ..notifiers import NotifyError, line_request, send_email, send_to_contact
from ..security import decrypt, encrypt, require_user
from .common import row_dict

router = APIRouter(prefix="/api", tags=["notify"], dependencies=[Depends(require_user)])


def _get(db: Session, model, oid: int, label: str):
    obj = db.get(model, oid)
    if not obj:
        raise HTTPException(404, f"找不到{label}")
    return obj


# ================= LINE 官方帳號 =================
class LineChannelIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    access_token: str | None = None  # 編輯時留空 = 不變
    channel_secret: str | None = None
    enabled: bool = True


def _webhook_url(cid: int) -> str:
    return f"{settings.public_base_url.rstrip('/')}/webhook/line/{cid}"


@router.get("/line-channels")
def list_line_channels(db: Session = Depends(get_db)):
    counts = dict(db.execute(select(Contact.line_channel_id, func.count(Contact.id))
                             .where(Contact.line_channel_id.is_not(None))
                             .group_by(Contact.line_channel_id)).all())
    out = []
    for c in db.scalars(select(LineChannel).order_by(LineChannel.id)):
        d = row_dict(c, exclude=("access_token_enc", "secret_enc"))
        d["webhook_url"] = _webhook_url(c.id)
        d["contact_count"] = counts.get(c.id, 0)
        out.append(d)
    return out


async def _bot_info(token: str) -> dict:
    try:
        return await line_request(token, "GET", "/info")
    except NotifyError as e:
        raise HTTPException(400, f"Channel Access Token 無效：{e}")


@router.post("/line-channels")
async def create_line_channel(body: LineChannelIn, db: Session = Depends(get_db)):
    if not body.access_token or not body.channel_secret:
        raise HTTPException(400, "請填寫 Channel Access Token 與 Channel Secret")
    info = await _bot_info(body.access_token)
    c = LineChannel(name=body.name, bot_basic_id=info.get("basicId"), enabled=body.enabled,
                    access_token_enc=encrypt(body.access_token), secret_enc=encrypt(body.channel_secret))
    db.add(c)
    db.commit()
    return {"id": c.id, "webhook_url": _webhook_url(c.id), "bot": info}


@router.put("/line-channels/{cid}")
async def update_line_channel(cid: int, body: LineChannelIn, db: Session = Depends(get_db)):
    c = _get(db, LineChannel, cid, "LINE 官方帳號")
    c.name, c.enabled = body.name, body.enabled
    if body.access_token:
        info = await _bot_info(body.access_token)
        c.access_token_enc = encrypt(body.access_token)
        c.bot_basic_id = info.get("basicId")
    if body.channel_secret:
        c.secret_enc = encrypt(body.channel_secret)
    db.commit()
    return {"ok": True}


@router.delete("/line-channels/{cid}")
def delete_line_channel(cid: int, db: Session = Depends(get_db)):
    db.delete(_get(db, LineChannel, cid, "LINE 官方帳號"))
    db.commit()
    return {"ok": True}


@router.get("/line-channels/{cid}/quota")
async def line_quota(cid: int, db: Session = Depends(get_db)):
    c = _get(db, LineChannel, cid, "LINE 官方帳號")
    token = decrypt(c.access_token_enc)
    try:
        quota = await line_request(token, "GET", "/message/quota")
        used = await line_request(token, "GET", "/message/quota/consumption")
        info = await line_request(token, "GET", "/info")
    except NotifyError as e:
        raise HTTPException(400, str(e))
    return {"type": quota.get("type"), "limit": quota.get("value"),
            "used": used.get("totalUsage"), "bot": info}


# ================= SMTP =================
class SmtpIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    host: str
    port: int = 587
    security: Literal["none", "starttls", "ssl"] = "starttls"
    username: str | None = None
    password: str | None = None  # 編輯時留空 = 不變
    from_addr: str
    is_default: bool = False


@router.get("/smtp")
def list_smtp(db: Session = Depends(get_db)):
    out = []
    for p in db.scalars(select(SmtpProfile).order_by(SmtpProfile.id)):
        d = row_dict(p, exclude=("password_enc",))
        d["has_password"] = bool(p.password_enc)
        out.append(d)
    return out


def _unset_default(db: Session, keep_id: int | None):
    for p in db.scalars(select(SmtpProfile).where(SmtpProfile.is_default == True)):  # noqa: E712
        if p.id != keep_id:
            p.is_default = False


@router.post("/smtp")
def create_smtp(body: SmtpIn, db: Session = Depends(get_db)):
    p = SmtpProfile(**body.model_dump(exclude={"password"}), password_enc=encrypt(body.password))
    if not db.scalar(select(func.count(SmtpProfile.id))):
        p.is_default = True
    db.add(p)
    db.flush()
    if p.is_default:
        _unset_default(db, p.id)
    db.commit()
    return {"id": p.id}


@router.put("/smtp/{pid}")
def update_smtp(pid: int, body: SmtpIn, db: Session = Depends(get_db)):
    p = _get(db, SmtpProfile, pid, "SMTP 設定")
    for k, v in body.model_dump(exclude={"password"}).items():
        setattr(p, k, v)
    if body.password:
        p.password_enc = encrypt(body.password)
    if p.is_default:
        _unset_default(db, p.id)
    db.commit()
    return {"ok": True}


@router.delete("/smtp/{pid}")
def delete_smtp(pid: int, db: Session = Depends(get_db)):
    db.delete(_get(db, SmtpProfile, pid, "SMTP 設定"))
    db.commit()
    return {"ok": True}


class SmtpTestIn(BaseModel):
    to: str = Field(pattern=r"^[^@\s]+@[^@\s]+$")


@router.post("/smtp/{pid}/test")
async def test_smtp(pid: int, body: SmtpTestIn, db: Session = Depends(get_db)):
    p = _get(db, SmtpProfile, pid, "SMTP 設定")
    try:
        await send_email(p, body.to, "【監控平台】SMTP 測試信", "這是一封測試信，收到代表 SMTP 設定正確。")
    except NotifyError as e:
        raise HTTPException(400, str(e))
    return {"ok": True}


# ================= 聯絡人 =================
class ContactIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    type: Literal["line_user", "line_group", "email"]
    address: str = Field(min_length=1, max_length=256)
    line_channel_id: int | None = None
    smtp_profile_id: int | None = None
    status: Literal["pending", "active", "disabled"] = "active"
    note: str | None = None
    group_ids: list[int] = []


def _contact_groups(db: Session) -> dict[int, list[int]]:
    out: dict[int, list[int]] = {}
    for gm in db.scalars(select(NotifyGroupMember)):
        out.setdefault(gm.contact_id, []).append(gm.group_id)
    return out


@router.get("/contacts")
def list_contacts(db: Session = Depends(get_db)):
    groups = _contact_groups(db)
    out = []
    for c in db.scalars(select(Contact).order_by(Contact.status.desc(), Contact.id)):
        d = row_dict(c)
        d["group_ids"] = groups.get(c.id, [])
        out.append(d)
    return out


def _check_contact(body: ContactIn):
    # 依類型清掉不相干的欄位：Email 聯絡人若掛著 line_channel_id，刪除該 LINE 官方帳號時會被連帶刪除
    if body.type == "email":
        body.line_channel_id = None
        if "@" not in body.address:
            raise HTTPException(400, "Email 格式錯誤")
    else:
        body.smtp_profile_id = None
        if not body.line_channel_id:
            raise HTTPException(400, "LINE 聯絡人需指定官方帳號")


def _save_contact_groups(db: Session, cid: int, group_ids: list[int]):
    db.execute(delete(NotifyGroupMember).where(NotifyGroupMember.contact_id == cid))
    for gid in set(group_ids):
        db.add(NotifyGroupMember(group_id=gid, contact_id=cid))


@router.post("/contacts")
def create_contact(body: ContactIn, db: Session = Depends(get_db)):
    _check_contact(body)
    c = Contact(**body.model_dump(exclude={"group_ids"}))
    db.add(c)
    db.flush()
    _save_contact_groups(db, c.id, body.group_ids)
    db.commit()
    return {"id": c.id}


@router.put("/contacts/{cid}")
def update_contact(cid: int, body: ContactIn, db: Session = Depends(get_db)):
    _check_contact(body)
    c = _get(db, Contact, cid, "聯絡人")
    for k, v in body.model_dump(exclude={"group_ids"}).items():
        setattr(c, k, v)
    _save_contact_groups(db, cid, body.group_ids)
    db.commit()
    return {"ok": True}


@router.delete("/contacts/{cid}")
def delete_contact(cid: int, db: Session = Depends(get_db)):
    db.delete(_get(db, Contact, cid, "聯絡人"))
    db.commit()
    return {"ok": True}


@router.post("/contacts/{cid}/test")
async def test_contact(cid: int):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        await send_to_contact(cid, "【監控平台】測試通知",
                              f"🔔 監控平台測試通知\n收到這則訊息代表通知設定正確。\n時間：{now}", "test")
    except NotifyError as e:
        raise HTTPException(400, str(e))
    return {"ok": True}


# ================= 通知群組 =================
class GroupIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: str | None = None
    contact_ids: list[int] = []
    monitor_ids: list[int] = []


@router.get("/groups")
def list_groups(db: Session = Depends(get_db)):
    members: dict[int, list[int]] = {}
    for gm in db.scalars(select(NotifyGroupMember)):
        members.setdefault(gm.group_id, []).append(gm.contact_id)
    mons: dict[int, list[int]] = {}
    for mg in db.scalars(select(MonitorNotifyGroup)):
        mons.setdefault(mg.group_id, []).append(mg.monitor_id)
    return [{**row_dict(g), "contact_ids": members.get(g.id, []), "monitor_ids": mons.get(g.id, [])}
            for g in db.scalars(select(NotifyGroup).order_by(NotifyGroup.id))]


def _save_group_links(db: Session, gid: int, body: GroupIn):
    db.execute(delete(NotifyGroupMember).where(NotifyGroupMember.group_id == gid))
    for cid in set(body.contact_ids):
        db.add(NotifyGroupMember(group_id=gid, contact_id=cid))
    existing = {mg.monitor_id: mg for mg in
                db.scalars(select(MonitorNotifyGroup).where(MonitorNotifyGroup.group_id == gid))}
    wanted = set(body.monitor_ids)
    for mid, mg in existing.items():
        if mid not in wanted:
            db.delete(mg)
    for mid in wanted - existing.keys():  # 新加入的監測預設收全部事件
        db.add(MonitorNotifyGroup(monitor_id=mid, group_id=gid, events="down,up,reminder"))


@router.post("/groups")
def create_group(body: GroupIn, db: Session = Depends(get_db)):
    g = NotifyGroup(name=body.name, description=body.description)
    db.add(g)
    db.flush()
    _save_group_links(db, g.id, body)
    db.commit()
    return {"id": g.id}


@router.put("/groups/{gid}")
def update_group(gid: int, body: GroupIn, db: Session = Depends(get_db)):
    g = _get(db, NotifyGroup, gid, "通知群組")
    g.name, g.description = body.name, body.description
    _save_group_links(db, gid, body)
    db.commit()
    return {"ok": True}


@router.delete("/groups/{gid}")
def delete_group(gid: int, db: Session = Depends(get_db)):
    db.delete(_get(db, NotifyGroup, gid, "通知群組"))
    db.commit()
    return {"ok": True}


# ================= 通知紀錄 =================
@router.get("/notification-logs")
def notification_logs(limit: int = 300, db: Session = Depends(get_db)):
    names = dict(db.execute(select(Monitor.id, Monitor.name)).all())
    rows = db.scalars(select(NotificationLog).order_by(NotificationLog.id.desc()).limit(min(limit, 2000)))
    return [{**row_dict(r), "monitor_name": names.get(r.monitor_id)} for r in rows]


# ================= 維護時段 =================
class MaintenanceIn(BaseModel):
    monitor_id: int | None = None
    start_at: datetime
    end_at: datetime
    note: str | None = None


def _to_naive_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


@router.get("/maintenance")
def list_maintenance(db: Session = Depends(get_db)):
    names = dict(db.execute(select(Monitor.id, Monitor.name)).all())
    return [{**row_dict(w), "monitor_name": names.get(w.monitor_id) if w.monitor_id else "全部監測"}
            for w in db.scalars(select(MaintenanceWindow).order_by(MaintenanceWindow.start_at.desc()))]


@router.post("/maintenance")
def create_maintenance(body: MaintenanceIn, db: Session = Depends(get_db)):
    start, end = _to_naive_utc(body.start_at), _to_naive_utc(body.end_at)
    if end <= start:
        raise HTTPException(400, "結束時間需晚於開始時間")
    w = MaintenanceWindow(monitor_id=body.monitor_id, start_at=start, end_at=end, note=body.note)
    db.add(w)
    db.commit()
    return {"id": w.id}


@router.delete("/maintenance/{wid}")
def delete_maintenance(wid: int, db: Session = Depends(get_db)):
    db.delete(_get(db, MaintenanceWindow, wid, "維護時段"))
    db.commit()
    return {"ok": True}

