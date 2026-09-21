from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Host, Monitor
from ..security import require_user
from .common import row_dict

router = APIRouter(prefix="/api", tags=["hosts"], dependencies=[Depends(require_user)])


class HostIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    ip: str | None = None
    os: str | None = None
    region: str | None = None
    resource_group: str | None = None
    vm_size: str | None = None
    description: str | None = None
    sort_order: int = 0
    monitor_ids: list[int] | None = None  # None = 不變更歸屬


def _assign(db: Session, host_id: int, monitor_ids: list[int] | None):
    if monitor_ids is None:
        return
    db.execute(update(Monitor).where(Monitor.host_id == host_id).values(host_id=None))
    if monitor_ids:
        db.execute(update(Monitor).where(Monitor.id.in_(monitor_ids)).values(host_id=host_id))


@router.get("/hosts")
def list_hosts(db: Session = Depends(get_db)):
    mons = db.execute(select(Monitor.id, Monitor.host_id, Monitor.status, Monitor.enabled)).all()
    out = []
    for h in db.scalars(select(Host).order_by(Host.sort_order, Host.name)):
        mine = [m for m in mons if m.host_id == h.id]
        counts = {"UP": 0, "DOWN": 0, "PENDING": 0, "PAUSED": 0, "UNKNOWN": 0}
        for m in mine:
            counts[m.status if m.enabled else "PAUSED"] += 1
        out.append({**row_dict(h), "monitor_ids": [m.id for m in mine], "counts": counts})
    return out


def _unique(db: Session, name: str, exclude_id: int | None = None):
    h = db.scalars(select(Host).where(Host.name == name)).first()
    if h and h.id != exclude_id:
        raise HTTPException(400, "主機名稱已存在")


@router.post("/hosts")
def create_host(body: HostIn, db: Session = Depends(get_db)):
    _unique(db, body.name)
    h = Host(**body.model_dump(exclude={"monitor_ids"}))
    db.add(h)
    db.flush()
    _assign(db, h.id, body.monitor_ids)
    db.commit()
    return {"id": h.id}


@router.put("/hosts/{hid}")
def update_host(hid: int, body: HostIn, db: Session = Depends(get_db)):
    h = db.get(Host, hid)
    if not h:
        raise HTTPException(404, "找不到主機")
    _unique(db, body.name, hid)
    for k, v in body.model_dump(exclude={"monitor_ids"}).items():
        setattr(h, k, v)
    _assign(db, hid, body.monitor_ids)
    db.commit()
    return {"ok": True}


@router.delete("/hosts/{hid}")
def delete_host(hid: int, db: Session = Depends(get_db)):
    h = db.get(Host, hid)
    if not h:
        raise HTTPException(404, "找不到主機")
    db.execute(update(Monitor).where(Monitor.host_id == hid).values(host_id=None))
    db.delete(h)
    db.commit()
    return {"ok": True}
