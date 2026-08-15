"""密码加密（bcrypt）与 JWT 签发 / 校验。"""
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    """密码哈希，只存哈希不存明文。"""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_access_token(user_id: int, role: str) -> tuple[str, int]:
    """签发 JWT，返回 (token, 过期秒数)。"""
    expire_seconds = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "role": role,
        "iat": now,
        "exp": now + timedelta(seconds=expire_seconds),
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)
    return token, expire_seconds


def decode_access_token(token: str) -> dict:
    """校验并解析 JWT，非法或过期抛 JWTError。"""
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
