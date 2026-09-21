from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import User
from ..security import create_token, hash_password, require_user, verify_password
from .common import iso

router = APIRouter(prefix="/api", tags=["auth"])


class LoginIn(BaseModel):
    username: str
    password: str


class UserIn(BaseModel):
    username: str = Field(min_length=2, max_length=64)
    password: str = Field(min_length=6)


class PasswordIn(BaseModel):
    old_password: str
    new_password: str = Field(min_length=6)


@router.post("/auth/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    u = db.scalars(select(User).where(User.username == body.username)).first()
    if not u or not verify_password(body.password, u.password_hash):
        raise HTTPException(401, "帳號或密碼錯誤")
    return {"token": create_token(u.username), "username": u.username}


@router.get("/auth/me")
def me(user: str = Depends(require_user)):
    return {"username": user}


@router.post("/auth/password")
def change_password(body: PasswordIn, user: str = Depends(require_user), db: Session = Depends(get_db)):
    u = db.scalars(select(User).where(User.username == user)).first()
    if not u or not verify_password(body.old_password, u.password_hash):
        raise HTTPException(400, "舊密碼錯誤")
    u.password_hash = hash_password(body.new_password)
    db.commit()
    return {"ok": True}


@router.get("/users")
def list_users(_: str = Depends(require_user), db: Session = Depends(get_db)):
    return [{"id": u.id, "username": u.username, "created_at": iso(u.created_at)}
            for u in db.scalars(select(User).order_by(User.id))]


@router.post("/users")
def create_user(body: UserIn, _: str = Depends(require_user), db: Session = Depends(get_db)):
    if db.scalars(select(User).where(User.username == body.username)).first():
        raise HTTPException(400, "帳號已存在")
    db.add(User(username=body.username, password_hash=hash_password(body.password)))
    db.commit()
    return {"ok": True}


@router.delete("/users/{uid}")
def delete_user(uid: int, user: str = Depends(require_user), db: Session = Depends(get_db)):
    u = db.get(User, uid)
    if not u:
        raise HTTPException(404, "找不到帳號")
    if u.username == user:
        raise HTTPException(400, "不能刪除自己")
    if db.scalar(select(func.count(User.id))) <= 1:
        raise HTTPException(400, "至少要保留一個管理員")
    db.delete(u)
    db.commit()
    return {"ok": True}
