from itsdangerous import URLSafeSerializer, BadSignature
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.app.config import settings
from src.web.models import WebUser


pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

serializer = URLSafeSerializer(
    settings.web_secret_key,
    salt="auth-session",
)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def create_session_token(user_id: int) -> str:
    return serializer.dumps({"user_id": user_id})


def read_session_token(token: str | None) -> int | None:
    if not token:
        return None

    try:
        data = serializer.loads(token)
        return int(data["user_id"])
    except (BadSignature, KeyError, ValueError, TypeError):
        return None


def authenticate_user(db: Session, username: str, password: str) -> WebUser | None:
    user = db.scalar(select(WebUser).where(WebUser.username == username))

    if not user:
        return None

    if not user.is_active:
        return None

    if not verify_password(password, user.password_hash):
        return None

    return user