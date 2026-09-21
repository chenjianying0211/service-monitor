"""執行一次監測、更新狀態機（UP / PENDING / DOWN）並觸發通知。"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import or_, select

from .checkers import CheckOutcome, run_check
from .config import settings
from .db import session_scope
from .models import CheckResult, Incident, MaintenanceWindow, Monitor, utcnow
from .notifiers import dispatch

log = logging.getLogger("engine")
TZ = ZoneInfo(settings.tz)

TYPE_LABEL = {
    "http": "HTTP", "keyword": "關鍵字", "tcp": "TCP 連接埠", "ssl_cert": "SSL 憑證",
    "docker": "Docker 容器", "proxy_pair": "轉發服務", "push": "獨立服務",
}


def local_str(dt: datetime) -> str:
    return dt.replace(tzinfo=timezone.utc).astimezone(TZ).strftime("%Y-%m-%d %H:%M:%S")


def fmt_duration(td: timedelta) -> str:
    secs = int(td.total_seconds())
    d, rem = divmod(secs, 86400)
    h, rem = divmod(rem, 3600)
    mnt, s = divmod(rem, 60)
    parts = [f"{d} 天" if d else "", f"{h} 小時" if h else "", f"{mnt} 分" if mnt else ""]
    return "".join(parts) or f"{s} 秒"


def _in_maintenance(s, monitor_id: int, now: datetime) -> bool:
    q = select(MaintenanceWindow.id).where(
        MaintenanceWindow.start_at <= now, MaintenanceWindow.end_at >= now,
        or_(MaintenanceWindow.monitor_id.is_(None), MaintenanceWindow.monitor_id == monitor_id),
    )
    return s.execute(q).first() is not None


def _apply(monitor_id: int, r: CheckOutcome):
    """寫入結果並推進狀態機，回傳 (event, subject, text) 或 None。"""
    now = utcnow()
    with session_scope() as s:
        m = s.get(Monitor, monitor_id)
        if m is None or not m.enabled:
            return None
        s.add(CheckResult(monitor_id=m.id, ts=now, ok=r.ok, latency_ms=r.latency_ms,
                          status_code=r.status_code, message=r.message))
        m.last_check_at, m.last_latency_ms, m.last_message = now, r.latency_ms, r.message
        head = f"{m.name}（{TYPE_LABEL.get(m.type, m.type)}）"
        target = "外部回報" if m.type == "push" else m.target  # push 的 target 是密鑰，不可外流
        event = None

        if r.ok:
            m.fail_count = 0
            if m.status == "DOWN":
                inc = s.scalars(select(Incident).where(Incident.monitor_id == m.id,
                                                       Incident.resolved_at.is_(None))
                                .order_by(Incident.id.desc())).first()
                dur = ""
                if inc:
                    inc.resolved_at = now
                    dur = f"\n中斷時長：{fmt_duration(now - inc.started_at)}"
                event = ("up", f"✅ 已恢復：{m.name}",
                         f"✅【服務恢復】{head}\n目標：{target}{dur}\n狀態：{r.message}\n時間：{local_str(now)}")
            m.status = "UP"
        else:
            m.fail_count += 1
            if m.status != "DOWN" and m.fail_count >= max(1, m.retries):
                m.status = "DOWN"
                s.add(Incident(monitor_id=m.id, started_at=now, cause=r.message))
                m.last_notified_at = now
                event = ("down", f"🔴 服務中斷：{m.name}",
                         f"🔴【服務中斷】{head}\n目標：{target}\n原因：{r.message}\n"
                         f"連續失敗：{m.fail_count} 次\n時間：{local_str(now)}")
            elif m.status == "DOWN":
                if m.resend_interval_min > 0 and (
                        m.last_notified_at is None
                        or now - m.last_notified_at >= timedelta(minutes=m.resend_interval_min)):
                    m.last_notified_at = now
                    inc = s.scalars(select(Incident).where(Incident.monitor_id == m.id,
                                                           Incident.resolved_at.is_(None))).first()
                    since = f"\n已中斷：{fmt_duration(now - inc.started_at)}" if inc else ""
                    event = ("reminder", f"🔁 仍然中斷：{m.name}",
                             f"🔁【仍然中斷】{head}\n目標：{target}\n原因：{r.message}{since}\n"
                             f"時間：{local_str(now)}")
            else:
                m.status = "PENDING"

        if event and _in_maintenance(s, m.id, now):
            log.info("monitor=%s 維護時段內，略過通知 %s", m.id, event[0])
            return None
        return event


async def apply_and_notify(monitor_id: int, result: CheckOutcome) -> None:
    """寫入一筆結果、推進狀態機，需要時發通知（排程檢查與外部回報共用）。"""
    event = await asyncio.to_thread(_apply, monitor_id, result)
    if event:
        await dispatch(monitor_id, *event)


async def execute(monitor_id: int) -> None:
    try:
        with session_scope() as s:
            m = s.get(Monitor, monitor_id)
            if m is None or not m.enabled:
                return
            s.expunge(m)
        result = await run_check(m)
        if result is None:  # push 類型按時回報中，這輪不用記錄
            return
        await apply_and_notify(monitor_id, result)
    except Exception:
        log.exception("monitor=%s 執行失敗", monitor_id)
