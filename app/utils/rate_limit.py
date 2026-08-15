"""基于 Redis 的固定窗口接口限流。

策略：对 (IP + 路由) 每窗口（秒）计数，超过阈值直接拒绝（429）。
实现原子性：INCR + 首请求设 EXPIRE，避免竞态。
"""
import time

from redis import Redis

from app.core.config import settings


class RateLimitExceeded(Exception):
    pass


def check_rate_limit(
    client: Redis, ip: str, path: str, limit: int | None = None, window_seconds: int = 1
) -> None:
    """校验当前请求是否超限，超限抛 RateLimitExceeded。"""
    limit = limit or settings.RATE_LIMIT_PER_SECOND
    key = f"rl:{ip}:{path}:{int(time.time()) // window_seconds}"

    count = client.incr(key)
    if count == 1:
        client.expire(key, window_seconds + 1)

    if count > limit:
        raise RateLimitExceeded(f"请求过于频繁，请稍后再试（{limit}/{window_seconds}s）")
