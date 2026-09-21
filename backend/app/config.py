from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    db_url: str = "mssql+pymssql://monitor_app:changeme@127.0.0.1:1433/ServiceMonitor"
    fernet_key: str
    jwt_secret: str
    admin_init_password: str | None = None  # 只在 users 表為空時使用；未設定則隨機產生
    public_base_url: str = "http://127.0.0.1:8090"
    tz: str = "Asia/Taipei"
    retention_days: int = 90
    host: str = "127.0.0.1"
    port: int = 8090
    seed_defaults: bool = True


settings = Settings()
