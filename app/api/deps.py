"""通用依赖：认证、权限、限流。"""
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.redis import get_redis
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models import User
from app.models.enums import UserRole
from app.utils.rate_limit import RateLimitExceeded, check_rate_limit

bearer_scheme = HTTPBearer(auto_error=False)

_CREDENTIALS_EXC = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="无效或过期的登录凭证",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """从 Bearer Token 解析并加载当前登录用户。"""
    if credentials is None or not credentials.credentials:
        raise _CREDENTIALS_EXC
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = int(payload.get("sub"))
    except (JWTError, ValueError, TypeError):
        raise _CREDENTIALS_EXC

    user = db.get(User, user_id)
    if user is None:
        raise _CREDENTIALS_EXC
    if not user.is_active:
        # 已禁用账号：即便是有效 token 也不予放行
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已被禁用，请联系管理员")
    return user


def get_current_admin(current_user: User = Depends(get_current_user)) -> User:
    """仅管理员可访问。"""
    if current_user.role != UserRole.ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限"
        )
    return current_user


def rate_limit(request: Request):
    """对 (IP + 路由) 做限流，超限返回 429。

    需要 Redis 可用；Redis 不可用时降级放行，不阻塞主流程。
    """
    try:
        client = get_redis()
        ip = request.client.host if request.client else "unknown"
        check_rate_limit(client, ip, request.url.path)
    except RateLimitExceeded as e:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(e))
    except Exception:
        # Redis 异常不阻断业务，仅降级
        pass
