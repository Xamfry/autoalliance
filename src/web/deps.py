from collections.abc import Generator
from fastapi import Cookie, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from src.app.db import SessionLocal
from src.web.auth import read_session_token
from src.web.models import WebUser


def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    db: Session = Depends(get_db),
    session: str | None = Cookie(default=None),
) -> WebUser:
    user_id = read_session_token(session)

    if not user_id:
        raise HTTPException(status_code=303, headers={"Location": "/login"})

    user = db.get(WebUser, user_id)

    if not user or not user.is_active:
        raise HTTPException(status_code=303, headers={"Location": "/login"})

    return user


def require_admin(
    user: WebUser = Depends(get_current_user),
) -> WebUser:
    if user.role != "admin":
        raise HTTPException(status_code=403)

    return user