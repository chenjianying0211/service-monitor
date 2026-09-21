from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from ..checkers import run_check
from ..db import get_db
from ..engine import execute
from ..models import CheckResult, Host, Incident, Monitor, MonitorNotifyGroup, utcnow
from ..scheduler import sync_job
from ..security import require_user
from .common import iso, row_dict, uptime_map

router = APIRouter(prefix="/api", tags=["monitors"], dependencies=[Depends(require_user)])

MonitorType = Literal["http", "keyword", "tcp", "ssl_cert", "docker", "proxy_pair"]


class GroupLink(BaseModel):
    group_id: int
    events: list[Literal["down", "up", "reminder"]] = ["down", "up", "reminder"]


class MonitorIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    type: MonitorType
    target: str = Field(min_length=1, max_length=512)
    backend_url: str | None = None
    method: str = "GET"
    expected_status: str = "200-399"
    keyword: str | None = None
    timeout_sec: int = Field(10, ge=1, le=120)
    interval_sec: int = Field(60, ge=20, le=86400)
    retries: int = Field(3, ge=1, le=20)
    resend_interval_min: int = Field(60, ge=0, le=10080)
    ssl_warn_days: int = Field(14, ge=0, le=365)
    follow_redirects: bool = True
    ignore_tls: bool = False
    enabled: bool = True
    tags: str | None = None
    description: str | None = None
    host_id: int | None = None
    groups: list[GroupLink] = []


def _validate(body: MonitorIn):
    if body.type == "proxy_pair" and not body.backend_url:
        raise HTTPException(400, "轉發服務需要填寫後端網址")
    if body.type == "keyword" and not body.keyword:
        raise HTTPException(400, "關鍵字監測需要填寫關鍵字")


def _groups_of(db: Session, mid: int) -> list[dict]:
    return [{"group_id": g.group_id, "events": g.events.split(",") if g.events else []}
            for g in db.scalars(select(MonitorNotifyGroup).where(MonitorNotifyGroup.monitor_id == mid))]


def _save_groups(db: Session, mid: int, groups: list[GroupLink]):
    db.execute(delete(MonitorNotifyGroup).where(MonitorNotifyGroup.monitor_id == mid))
    for g in {g.group_id: g for g in groups}.values():
        db.add(MonitorNotifyGroup(monitor_id=mid, group_id=g.group_id, events=",".join(g.events)))


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db)):
    monitors = db.scalars(select(Monitor).order_by(Monitor.name)).all()
    beats = db.execute(text(
        "SELECT monitor_id, ts, ok, latency_ms, message FROM ("
        " SELECT monitor_id, ts, ok, latency_ms, message,"
        "  ROW_NUMBER() OVER (PARTITION BY monitor_id ORDER BY ts DESC) rn"
        " FROM check_results WHERE ts >= DATEADD(day, -3, SYSUTCDATETIME())) t"
        " WHERE rn <= 60 ORDER BY monitor_id, ts"
    )).all()
    by_mon: dict[int, list] = {}
    for b in beats:
        by_mon.setdefault(b.monitor_id, []).append(
            {"ts": iso(b.ts), "ok": bool(b.ok), "latency_ms": b.latency_ms, "message": b.message})
    up24, up7, up30 = uptime_map(db, 24, 30), uptime_map(db, 24 * 7, 300), uptime_map(db, 24 * 30, 600)
    open_incidents = db.scalars(select(Incident).where(Incident.resolved_at.is_(None))).all()
    recent = db.execute(
        select(Incident, Monitor.name).join(Monitor, Monitor.id == Incident.monitor_id)
        .order_by(Incident.started_at.desc()).limit(10)).all()

    items = []
    counts = {"UP": 0, "DOWN": 0, "PENDING": 0, "PAUSED": 0, "UNKNOWN": 0}
    for m in monitors:
        st = m.status if m.enabled else "PAUSED"
        counts[st] = counts.get(st, 0) + 1
        items.append({
            "id": m.id, "name": m.name, "type": m.type, "target": m.target, "tags": m.tags,
            "host_id": m.host_id,
            "status": st, "last_check_at": iso(m.last_check_at), "last_latency_ms": m.last_latency_ms,
            "last_message": m.last_message, "heartbeats": by_mon.get(m.id, []),
            "uptime_24h": up24.get(m.id), "uptime_7d": up7.get(m.id), "uptime_30d": up30.get(m.id),
        })
    return {
        "counts": counts, "total": len(monitors), "open_incidents": len(open_incidents),
        "monitors": items,
        "hosts": [row_dict(h) for h in db.scalars(select(Host).order_by(Host.sort_order, Host.name))],
        "recent_incidents": [{
            "id": i.id, "monitor_id": i.monitor_id, "monitor_name": name, "cause": i.cause,
            "started_at": iso(i.started_at), "resolved_at": iso(i.resolved_at)} for i, name in recent],
    }


@router.get("/monitors")
def list_monitors(db: Session = Depends(get_db)):
    links: dict[int, list] = {}
    for g in db.scalars(select(MonitorNotifyGroup)):
        links.setdefault(g.monitor_id, []).append(
            {"group_id": g.group_id, "events": g.events.split(",") if g.events else []})
    out = []
    for m in db.scalars(select(Monitor).order_by(Monitor.name)):
        d = row_dict(m)
        d["groups"] = links.get(m.id, [])
        out.append(d)
    return out


@router.get("/monitors/{mid}")
def get_monitor(mid: int, db: Session = Depends(get_db)):
    m = db.get(Monitor, mid)
    if not m:
        raise HTTPException(404, "找不到監測項目")
    d = row_dict(m)
    d["groups"] = _groups_of(db, mid)
    d["uptime_24h"] = uptime_map(db, 24, 30).get(mid)
    d["uptime_7d"] = uptime_map(db, 24 * 7, 300).get(mid)
    d["uptime_30d"] = uptime_map(db, 24 * 30, 600).get(mid)
    return d


@router.get("/monitors/{mid}/results")
def monitor_results(mid: int, hours: int = 24, db: Session = Depends(get_db)):
    hours = max(1, min(hours, 24 * 90))
    rows = db.execute(text(
        "SELECT ts, ok, latency_ms, status_code, message FROM check_results "
        "WHERE monitor_id=:m AND ts >= DATEADD(hour, :h, SYSUTCDATETIME()) ORDER BY ts"
    ), {"m": mid, "h": -hours}).all()
    # 資料量太大時降採樣，避免前端圖表卡頓
    step = max(1, len(rows) // 1500)
    pts = rows[::step]
    if rows and pts[-1] is not rows[-1]:
        pts.append(rows[-1])
    return [{"ts": iso(r.ts), "ok": bool(r.ok), "latency_ms": r.latency_ms,
             "status_code": r.status_code, "message": r.message} for r in pts]


@router.get("/monitors/{mid}/incidents")
def monitor_incidents(mid: int, db: Session = Depends(get_db)):
    rows = db.scalars(select(Incident).where(Incident.monitor_id == mid)
                      .order_by(Incident.started_at.desc()).limit(100))
    return [row_dict(i) for i in rows]


@router.post("/monitors")
def create_monitor(body: MonitorIn, db: Session = Depends(get_db)):
    _validate(body)
    m = Monitor(**body.model_dump(exclude={"groups"}))
    db.add(m)
    db.flush()
    _save_groups(db, m.id, body.groups)
    db.commit()
    sync_job(m.id, m.interval_sec, m.enabled, run_now=True)
    return {"id": m.id}


@router.put("/monitors/{mid}")
def update_monitor(mid: int, body: MonitorIn, db: Session = Depends(get_db)):
    _validate(body)
    m = db.get(Monitor, mid)
    if not m:
        raise HTTPException(404, "找不到監測項目")
    for k, v in body.model_dump(exclude={"groups"}).items():
        setattr(m, k, v)
    _save_groups(db, mid, body.groups)
    db.commit()
    sync_job(mid, m.interval_sec, m.enabled, run_now=True)
    return {"ok": True}


@router.post("/monitors/{mid}/toggle")
def toggle_monitor(mid: int, db: Session = Depends(get_db)):
    m = db.get(Monitor, mid)
    if not m:
        raise HTTPException(404, "找不到監測項目")
    m.enabled = not m.enabled
    if m.enabled:
        m.status, m.fail_count = "UNKNOWN", 0
    db.commit()
    sync_job(mid, m.interval_sec, m.enabled, run_now=True)
    return {"enabled": m.enabled}


@router.post("/monitors/{mid}/check")
async def check_now(mid: int):
    await execute(mid)
    return {"ok": True}


@router.post("/monitors/test")
async def test_monitor(body: MonitorIn):
    """不存檔，直接測一次（表單上的「測試」按鈕）。"""
    _validate(body)
    m = Monitor(**body.model_dump(exclude={"groups"}))
    r = await run_check(m)
    return {"ok": r.ok, "message": r.message, "latency_ms": r.latency_ms, "status_code": r.status_code}


@router.delete("/monitors/{mid}")
def delete_monitor(mid: int, db: Session = Depends(get_db)):
    m = db.get(Monitor, mid)
    if not m:
        raise HTTPException(404, "找不到監測項目")
    sync_job(mid, None, False)
    # 大量歷史資料先分批刪，避免一次鎖太久
    while db.execute(text("DELETE TOP (5000) FROM check_results WHERE monitor_id=:m"), {"m": mid}).rowcount:
        db.commit()
    db.delete(m)
    db.commit()
    return {"ok": True}


@router.get("/incidents")
def list_incidents(only_open: bool = False, limit: int = 200, db: Session = Depends(get_db)):
    q = select(Incident, Monitor.name).join(Monitor, Monitor.id == Incident.monitor_id)
    if only_open:
        q = q.where(Incident.resolved_at.is_(None))
    rows = db.execute(q.order_by(Incident.started_at.desc()).limit(min(limit, 1000))).all()
    out = []
    now = utcnow()
    for i, name in rows:
        d = row_dict(i)
        d["monitor_name"] = name
        d["duration_sec"] = int(((i.resolved_at or now) - i.started_at).total_seconds())
        out.append(d)
    return out


@router.post("/incidents/{iid}/ack")
def ack_incident(iid: int, user: str = Depends(require_user), db: Session = Depends(get_db)):
    i = db.get(Incident, iid)
    if not i:
        raise HTTPException(404, "找不到事件")
    i.acked_by, i.acked_at = user, utcnow()
    db.commit()
    return {"ok": True}


@router.get("/stats")
def stats(db: Session = Depends(get_db)):
    return {"check_results": db.scalar(select(func.count(CheckResult.id)))}

