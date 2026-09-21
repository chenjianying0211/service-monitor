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
        if "last_push_at" not in cols:
            conn.execute(text("ALTER TABLE monitors ADD last_push_at DATETIME NULL"))
            log.info("已新增 monitors.last_push_at")
        # 修正舊資料：Email 聯絡人不應綁 LINE 官方帳號（否則刪 LINE 帳號時會被連帶刪除）
        n = conn.execute(text(
            "UPDATE contacts SET line_channel_id = NULL WHERE type = 'email' AND line_channel_id IS NOT NULL")).rowcount
        if n:
            log.info("已修正 %d 筆 Email 聯絡人的 line_channel_id", n)
