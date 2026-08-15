"""Redis 客户端。

用途（全系统无凑数）：
1. 分布式锁：并发报名防超报
2. 缓存活动报名人数：降低 MySQL COUNT 压力
3. 异步任务进度缓存
4. 接口限流：防脚本刷接口
"""
import time
import uuid

import redis

from app.core.config import settings

# decode_responses=True 使所有 value 自动转 str，方便业务使用
redis_client = redis.Redis.from_url(
    settings.REDIS_URL,
    decode_responses=True,
    socket_connect_timeout=5,
    socket_timeout=5,
)


def get_redis() -> redis.Redis:
    return redis_client


class RedisLock:
    """基于 Redis SET NX EX 的分布式锁（支持自旋重试）。

    使用模式：
        with RedisLock(redis, "activity:100", ttl=10, wait_timeout=15):
            # 临界区：名额判断 + 写入

    高并发争抢时，拿不到锁的请求会自旋重试，直到 wait_timeout 超时再抛错；
    而不是一次性失败，保证「同一活动」的报名操作最终被串行化。
    """

    def __init__(
        self,
        client: redis.Redis,
        key: str,
        ttl: int = 10,
        wait_timeout: float = 15.0,
        retry_interval: float = 0.02,
    ):
        self.client = client
        self.key = f"lock:{key}"
        self.ttl = ttl
        self.wait_timeout = wait_timeout
        self.retry_interval = retry_interval
        # 唯一随机值，用于安全释放：只删除自己加的锁
        self.token = f"{uuid.uuid4()}"

    def __enter__(self) -> "RedisLock":
        deadline = time.monotonic() + self.wait_timeout
        while True:
            if self.client.set(self.key, self.token, nx=True, ex=self.ttl):
                return self
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"获取分布式锁超时: {self.key}（{self.wait_timeout}s 内未能获得锁）"
                )
            time.sleep(self.retry_interval)

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Lua 脚本保证「校验值 + 删除」原子，避免误删他人锁
        lua = """
        if redis.call('get', KEYS[1]) == ARGV[1] then
            return redis.call('del', KEYS[1])
        else
            return 0
        end
        """
        self.client.eval(lua, 1, self.key, self.token)
        return False
