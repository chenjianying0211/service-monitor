from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, Unicode, UnicodeText,
)
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def utcnow() -> datetime:
    # 一律以 naive UTC 存進 DATETIME2
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(Unicode(64), unique=True)
    password_hash: Mapped[str] = mapped_column(Unicode(128))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class ApiKey(Base):
    """給 MCP / 外部程式用的 API 金鑰；只存 SHA-256 雜湊。"""
    __tablename__ = "api_keys"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Unicode(128))
    key_hash: Mapped[str] = mapped_column(Unicode(64), unique=True)
    prefix: Mapped[str] = mapped_column(Unicode(16))
    created_by: Mapped[str | None] = mapped_column(Unicode(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Host(Base):
    __tablename__ = "hosts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Unicode(128), unique=True)
    ip: Mapped[str | None] = mapped_column(Unicode(64), nullable=True)
    os: Mapped[str | None] = mapped_column(Unicode(32), nullable=True)  # Linux / Windows
    region: Mapped[str | None] = mapped_column(Unicode(64), nullable=True)
    resource_group: Mapped[str | None] = mapped_column(Unicode(128), nullable=True)
    vm_size: Mapped[str | None] = mapped_column(Unicode(64), nullable=True)
    description: Mapped[str | None] = mapped_column(Unicode(256), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Monitor(Base):
    __tablename__ = "monitors"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Unicode(128))
    # http | keyword | tcp | ssl_cert | docker | proxy_pair | push
    type: Mapped[str] = mapped_column(Unicode(16))
    target: Mapped[str] = mapped_column(Unicode(512))  # URL / host:port / 容器名 / 網域 / push token
    backend_url: Mapped[str | None] = mapped_column(Unicode(512), nullable=True)  # proxy_pair 後端
    method: Mapped[str] = mapped_column(Unicode(8), default="GET")
    expected_status: Mapped[str] = mapped_column(Unicode(32), default="200-399")
    keyword: Mapped[str | None] = mapped_column(Unicode(256), nullable=True)
    timeout_sec: Mapped[int] = mapped_column(Integer, default=10)
    interval_sec: Mapped[int] = mapped_column(Integer, default=60)
    retries: Mapped[int] = mapped_column(Integer, default=3)
    resend_interval_min: Mapped[int] = mapped_column(Integer, default=60)
    ssl_warn_days: Mapped[int] = mapped_column(Integer, default=14)
    follow_redirects: Mapped[bool] = mapped_column(Boolean, default=True)
    ignore_tls: Mapped[bool] = mapped_column(Boolean, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    tags: Mapped[str | None] = mapped_column(Unicode(256), nullable=True)
    description: Mapped[str | None] = mapped_column(Unicode(512), nullable=True)
    host_id: Mapped[int | None] = mapped_column(
        ForeignKey("hosts.id", ondelete="SET NULL"), nullable=True, index=True)
    # UP | DOWN | PENDING | UNKNOWN
    status: Mapped[str] = mapped_column(Unicode(16), default="UNKNOWN")
    fail_count: Mapped[int] = mapped_column(Integer, default=0)
    last_check_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_message: Mapped[str | None] = mapped_column(Unicode(1024), nullable=True)
    last_notified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_push_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # push 類型最後回報時間
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class CheckResult(Base):
    __tablename__ = "check_results"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    monitor_id: Mapped[int] = mapped_column(ForeignKey("monitors.id", ondelete="CASCADE"))
    ts: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    ok: Mapped[bool] = mapped_column(Boolean)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    message: Mapped[str | None] = mapped_column(Unicode(1024), nullable=True)

    __table_args__ = (Index("ix_check_results_monitor_ts", "monitor_id", "ts"),)


class Incident(Base):
    __tablename__ = "incidents"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    monitor_id: Mapped[int] = mapped_column(ForeignKey("monitors.id", ondelete="CASCADE"), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    cause: Mapped[str | None] = mapped_column(Unicode(1024), nullable=True)
    acked_by: Mapped[str | None] = mapped_column(Unicode(64), nullable=True)
    acked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class LineChannel(Base):
    __tablename__ = "line_channels"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Unicode(128))
    bot_basic_id: Mapped[str | None] = mapped_column(Unicode(64), nullable=True)
    access_token_enc: Mapped[str] = mapped_column(UnicodeText)
    secret_enc: Mapped[str] = mapped_column(UnicodeText)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class SmtpProfile(Base):
    __tablename__ = "smtp_profiles"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Unicode(128))
    host: Mapped[str] = mapped_column(Unicode(256))
    port: Mapped[int] = mapped_column(Integer, default=587)
    security: Mapped[str] = mapped_column(Unicode(16), default="starttls")  # none|starttls|ssl
    username: Mapped[str | None] = mapped_column(Unicode(256), nullable=True)
    password_enc: Mapped[str | None] = mapped_column(UnicodeText, nullable=True)
    from_addr: Mapped[str] = mapped_column(Unicode(256))
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)


class Contact(Base):
    __tablename__ = "contacts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Unicode(128))
    type: Mapped[str] = mapped_column(Unicode(16))  # line_user | line_group | email
    address: Mapped[str] = mapped_column(Unicode(256))  # userId / groupId / email
    line_channel_id: Mapped[int | None] = mapped_column(
        ForeignKey("line_channels.id", ondelete="CASCADE"), nullable=True)
    smtp_profile_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(Unicode(16), default="active")  # pending|active|disabled
    note: Mapped[str | None] = mapped_column(Unicode(256), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class NotifyGroup(Base):
    __tablename__ = "notify_groups"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Unicode(128))
    description: Mapped[str | None] = mapped_column(Unicode(256), nullable=True)


class NotifyGroupMember(Base):
    __tablename__ = "notify_group_members"
    group_id: Mapped[int] = mapped_column(ForeignKey("notify_groups.id", ondelete="CASCADE"), primary_key=True)
    contact_id: Mapped[int] = mapped_column(ForeignKey("contacts.id", ondelete="CASCADE"), primary_key=True)


class MonitorNotifyGroup(Base):
    __tablename__ = "monitor_notify_groups"
    monitor_id: Mapped[int] = mapped_column(ForeignKey("monitors.id", ondelete="CASCADE"), primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("notify_groups.id", ondelete="CASCADE"), primary_key=True)
    # 逗號分隔：down,up,reminder
    events: Mapped[str] = mapped_column(Unicode(64), default="down,up,reminder")


class NotificationLog(Base):
    __tablename__ = "notification_logs"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    channel: Mapped[str] = mapped_column(Unicode(16))  # line | email
    target: Mapped[str] = mapped_column(Unicode(256))
    contact_name: Mapped[str | None] = mapped_column(Unicode(128), nullable=True)
    monitor_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    event: Mapped[str] = mapped_column(Unicode(16))  # down|up|reminder|test
    success: Mapped[bool] = mapped_column(Boolean)
    error: Mapped[str | None] = mapped_column(Unicode(1024), nullable=True)
    content: Mapped[str | None] = mapped_column(UnicodeText, nullable=True)


class MaintenanceWindow(Base):
    __tablename__ = "maintenance_windows"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    monitor_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # NULL = 全部
    start_at: Mapped[datetime] = mapped_column(DateTime)
    end_at: Mapped[datetime] = mapped_column(DateTime)
    note: Mapped[str | None] = mapped_column(Unicode(256), nullable=True)
