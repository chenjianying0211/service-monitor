import hashlib
import secrets

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db, session_scope
from ..models import ApiKey, utcnow
from ..security import require_user
from .common import row_dict

router = APIRouter(prefix="/api", tags=["api-keys"], dependencies=[Depends(require_user)])
KEY_PREFIX = "smk_"


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def verify_api_key(key: str) -> str | None:
    """驗證金鑰，成功回傳金鑰名稱並更新最後使用時間。"""
    if not key or not key.startswith(KEY_PREFIX):
        return None
    with session_scope() as s:
        k = s.scalars(select(ApiKey).where(ApiKey.key_hash == hash_key(key))).first()
        if not k:
            return None
        k.last_used_at = utcnow()
        return k.name


class ApiKeyIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)


@router.get("/api-keys")
def list_keys(db: Session = Depends(get_db)):
    return [row_dict(k, exclude=("key_hash",)) for k in db.scalars(select(ApiKey).order_by(ApiKey.id))]


@router.post("/api-keys")
def create_key(body: ApiKeyIn, user: str = Depends(require_user), db: Session = Depends(get_db)):
    key = KEY_PREFIX + secrets.token_urlsafe(32)
    db.add(ApiKey(name=body.name, key_hash=hash_key(key), prefix=key[:10], created_by=user))
    db.commit()
    return {"key": key, "mcp_url": f"{settings.public_base_url.rstrip('/')}/mcp/"}


@router.delete("/api-keys/{kid}")
def delete_key(kid: int, db: Session = Depends(get_db)):
    k = db.get(ApiKey, kid)
    if not k:
        raise HTTPException(404, "找不到金鑰")
    db.delete(k)
    db.commit()
    return {"ok": True}
