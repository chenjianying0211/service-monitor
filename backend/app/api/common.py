import time
from datetime import datetime

from sqlalchemy import inspect as sa_inspect, text


def iso(dt: datetime | None) -> str | None:
    """naive UTC → ISO 字串（帶 Z），前端自行轉當地時間。"""
    return dt.isoformat(timespec="seconds") + "Z" if dt else None


def row_dict(obj, exclude: tuple[str, ...] = ()) -> dict:
    out = {}
    for col in sa_inspect(obj).mapper.column_attrs:
        k = col.key
        if k in exclude:
            continue
        v = getattr(obj, k)
        out[k] = iso(v) if isinstance(v, datetime) else v
    return out


_uptime_cache: dict[int, tuple[float, dict[int, float]]] = {}


def uptime_map(db, hours: int, ttl: int = 60) -> dict[int, float]:
    """每個 monitor 在過去 N 小時的可用率（%）。結果快取 ttl 秒。"""
    hit = _uptime_cache.get(hours)
    if hit and time.time() - hit[0] < ttl:
        return hit[1]
    rows = db.execute(text(
        "SELECT monitor_id, SUM(CASE WHEN ok=1 THEN 1 ELSE 0 END) AS up, COUNT(*) AS total "
        "FROM check_results WHERE ts >= DATEADD(hour, :h, SYSUTCDATETIME()) GROUP BY monitor_id"
    ), {"h": -hours}).all()
    data = {r.monitor_id: round(r.up * 100.0 / r.total, 2) for r in rows if r.total}
    _uptime_cache[hours] = (time.time(), data)
    return data


def invalidate_uptime() -> None:
    _uptime_cache.clear()
