"""輕量 schema 升級：create_all 只會建新表，既有表新增欄位在這裡補。"""
import logging

from sqlalchemy import inspect, text

from .db import engine

log = logging.getLogger("migrate")


def upgrade() -> None:
    insp = inspect(engine)
    cols = {c["name"] for c in insp.get_columns("monitors")}
    with engine.begin() as conn:
        if "host_id" not in cols:
            conn.execute(text(
                "ALTER TABLE monitors ADD host_id INT NULL "
                "CONSTRAINT fk_monitors_host_id FOREIGN KEY REFERENCES hosts(id) ON DELETE SET NULL"))
            conn.execute(text("CREATE INDEX ix_monitors_host_id ON monitors(host_id)"))
            log.info("已新增 monitors.host_id")
