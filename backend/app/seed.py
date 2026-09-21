"""首次啟動：建立管理員與這台主機上既有服務的預設監測。"""
import logging
import secrets

from sqlalchemy import func, select

from .config import settings
from .db import session_scope
from .models import Monitor, User
from .security import hash_password

log = logging.getLogger("seed")

DEFAULT_MONITORS = [
    # 轉發服務：網域 vs 後端
    dict(name="careloger.com", type="proxy_pair", target="https://careloger.com",
         backend_url="http://127.0.0.1:3100/health", tags="轉發服務"),
    dict(name="inspect.careloger.com", type="proxy_pair", target="https://inspect.careloger.com",
         backend_url="http://127.0.0.1:8081", tags="轉發服務"),
    dict(name="inspect-main.careloger.com", type="proxy_pair", target="https://inspect-main.careloger.com",
         backend_url="http://127.0.0.1:8082", tags="轉發服務"),
    # SSL 憑證（每 6 小時檢查一次）
    *[dict(name=f"SSL {d}", type="ssl_cert", target=d, interval_sec=21600, retries=1,
           resend_interval_min=1440, tags="SSL")
      for d in ["careloger.com", "inspect.careloger.com", "inspect-main.careloger.com", "agetsu13.com"]],
    # 基礎設施
    dict(name="MSSQL 1433", type="tcp", target="127.0.0.1:1433", tags="資料庫"),
    dict(name="SSH 22", type="tcp", target="127.0.0.1:22", tags="主機"),
    *[dict(name=f"容器 {c}", type="docker", target=c, tags="Docker")
      for c in ["nginx_proxy", "mssql_2022_rtm_gdr1", "inspect_summary", "inspect_summary_main",
                "certbot_manager"]],
]


def seed() -> None:
    with session_scope() as s:
        if not s.scalar(select(func.count(User.id))):
            pw = settings.admin_init_password or secrets.token_urlsafe(12)
            s.add(User(username="admin", password_hash=hash_password(pw)))
            if settings.admin_init_password:
                log.info("已建立初始管理員 admin（密碼取自 ADMIN_INIT_PASSWORD）")
            else:
                log.warning("已建立初始管理員 admin，初始密碼：%s（請登入後立即修改）", pw)
        if settings.seed_defaults and not s.scalar(select(func.count(Monitor.id))):
            for d in DEFAULT_MONITORS:
                s.add(Monitor(**d))
            log.info("已建立 %d 個預設監測", len(DEFAULT_MONITORS))
