import logging
import random
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import delete, select

from .config import settings
from .db import session_scope
from .engine import execute
from .models import CheckResult, Monitor, NotificationLog, utcnow

log = logging.getLogger("scheduler")
scheduler = AsyncIOScheduler()


def _job_id(monitor_id: int) -> str:
    return f"monitor-{monitor_id}"


def sync_job(monitor_id: int, interval_sec: int | None, enabled: bool, run_now: bool = False) -> None:
    """新增 / 更新 / 移除單一監測的排程。"""
    jid = _job_id(monitor_id)
    if scheduler.get_job(jid):
        scheduler.remove_job(jid)
    if not enabled or not interval_sec:
        return
    delay = 1 if run_now else random.uniform(1, min(interval_sec, 15))
    scheduler.add_job(
        execute, "interval", seconds=max(20, interval_sec), args=[monitor_id], id=jid,
        max_instances=1, coalesce=True, misfire_grace_time=30,
        next_run_time=datetime.now() + timedelta(seconds=delay),
    )


def cleanup() -> None:
    cutoff = utcnow() - timedelta(days=settings.retention_days)
    with session_scope() as s:
        n1 = s.execute(delete(CheckResult).where(CheckResult.ts < cutoff)).rowcount
        n2 = s.execute(delete(NotificationLog).where(NotificationLog.ts < cutoff)).rowcount
    log.info("清除 %s 天前資料：check_results=%s notification_logs=%s", settings.retention_days, n1, n2)


def start() -> None:
    with session_scope() as s:
        rows = s.execute(select(Monitor.id, Monitor.interval_sec).where(Monitor.enabled == True)).all()  # noqa: E712
    for mid, interval in rows:
        sync_job(mid, interval, True)
    scheduler.add_job(cleanup, "cron", hour=3, minute=17, id="cleanup")
    scheduler.start()
    log.info("排程啟動，共 %d 個監測", len(rows))
