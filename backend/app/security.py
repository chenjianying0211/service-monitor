from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from cryptography.fernet import Fernet
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import settings

_fernet = Fernet(settings.fernet_key.encode())
_bearer = HTTPBearer(auto_error=False)


def encrypt(value: str | None) -> str | None:
    return _fernet.encrypt(value.encode()).decode() if value else None


def decrypt(value: str | None) -> str | None:
    return _fernet.decrypt(value.encode()).decode() if value else None


def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def verify_password(pw: str, hashed: str) -> bool:
    return bcrypt.checkpw(pw.encode(), hashed.encode())


def create_token(username: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(hours=12)
    return jwt.encode({"sub": username, "exp": exp}, settings.jwt_secret, algorithm="HS256")


def require_user(cred: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> str:
    if not cred:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "未登入")
    try:
        payload = jwt.decode(cred.credentials, settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "登入已過期，請重新登入")
    return payload["sub"]
