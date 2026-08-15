"""报名核心业务：并发防超报（Redis 分布式锁）+ 报名人数缓存。

关键设计：
- 分布式锁：对「同一活动」的报名操作加锁，串行化 名额判断 + 写入，杜绝超报。
- 人数缓存：锁内写库后直接回写缓存，读接口优先走缓存，降低 MySQL COUNT 压力。
- 唯一约束兜底：表级 UNIQUE(activity_id, user_id)，即便锁意外失效也不会有重复行。
"""
import time
from datetime import datetime

from fastapi import HTTPException
from redis import Redis
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.redis import RedisLock
from app.models import Activity, Registration
from app.models.enums import ActivityStatus, RegistrationStatus

# 报名人数缓存 key 与 TTL
COUNT_KEY = "activity:signup_count:{}"
COUNT_TTL = 86400  # 写路径持续回写，TTL 仅作兜底过期


def _count_key(activity_id: int) -> str:
    return COUNT_KEY.format(activity_id)


def get_cached_count(client: Redis, db: Session, activity_id: int) -> int:
    """读报名人数：优先 Redis 缓存，缺失回源 MySQL 并回填。"""
    cached = client.get(_count_key(activity_id))
    if cached is not None:
        return int(cached)
    count = _db_signed_count(db, activity_id)
    client.set(_count_key(activity_id), count, ex=300)
    return count


def _db_signed_count(db: Session, activity_id: int) -> int:
    return db.scalar(
        select(func.count())
        .select_from(Registration)
        .where(
            Registration.activity_id == activity_id,
            Registration.status == RegistrationStatus.SIGNED.value,
        )
    ) or 0


def _validate_signup_activity(activity: Activity) -> None:
    now = datetime.now()
    if activity.status != ActivityStatus.OPEN.value:
        raise HTTPException(status_code=400, detail=f"活动当前状态 {activity.status}，不可报名")
    if now < activity.signup_start_at:
        raise HTTPException(status_code=400, detail="报名尚未开始")
    if now > activity.signup_end_at:
        raise HTTPException(status_code=400, detail="报名已截止")


def signup(
    db: Session,
    client: Redis,
    activity_id: int,
    user_id: int,
    use_lock: bool = True,
    race_delay_ms: int = 0,
) -> tuple[int, int]:
    """报名。

    返回 (最新报名人数, 报名记录状态)。
    并发入口（HTTP/测试脚本）必须 use_lock=True，保证名额严格受控。
    use_lock=False 仅用于并发脚本演示「不加锁会超报」的对照实验；
    race_delay_ms 仅用于放大竞态窗口，让对照实验稳定复现，生产默认 0。
    """
    activity = db.get(Activity, activity_id)
    if activity is None:
        raise HTTPException(status_code=404, detail="活动不存在")

    if use_lock:
        with RedisLock(client, _count_key(activity_id), ttl=10):
            return _signup_in_lock(db, client, activity, user_id, race_delay_ms)
    return _signup_in_lock(db, client, activity, user_id, race_delay_ms)


def _signup_in_lock(
    db: Session, client: Redis, activity: Activity, user_id: int, race_delay_ms: int = 0
) -> tuple[int, int]:
    """锁内的临界区：状态校验 -> 查重 -> 判名额 -> 写入 -> 回写缓存。"""
    _validate_signup_activity(activity)

    # 查重：同一用户不可重复报名（CANCELED 可重新报名，复用原行）
    reg = db.scalar(
        select(Registration).where(
            Registration.activity_id == activity.id,
            Registration.user_id == user_id,
        )
    )
    if reg is not None and reg.status == RegistrationStatus.SIGNED.value:
        raise HTTPException(status_code=400, detail="你已报名该活动，请勿重复报名")

    # 判名额：以库内真实 SIGNED 数为准（锁保证无并发写冲突）
    current = _db_signed_count(db, activity.id)
    if current >= activity.max_participants:
        raise HTTPException(status_code=400, detail="报名人数已满")

    # 放大「查数 -> 写入」间隙，仅对照实验复现竞态使用，生产保持 0
    if race_delay_ms > 0:
        time.sleep(race_delay_ms / 1000)

    now = datetime.now()
    if reg is None:
        reg = Registration(
            activity_id=activity.id,
            user_id=user_id,
            status=RegistrationStatus.SIGNED.value,
            signed_at=now,
        )
        db.add(reg)
    else:
        reg.status = RegistrationStatus.SIGNED.value
        reg.signed_at = now
        reg.canceled_at = None

    db.commit()

    new_count = current + 1
    client.set(_count_key(activity.id), new_count, ex=COUNT_TTL)
    return new_count, reg.status


def cancel(
    db: Session,
    client: Redis,
    activity_id: int,
    user_id: int,
) -> int:
    """取消报名，返回取消后的报名人数。"""
    activity = db.get(Activity, activity_id)
    if activity is None:
        raise HTTPException(status_code=404, detail="活动不存在")

    with RedisLock(client, _count_key(activity_id), ttl=10):
        reg = db.scalar(
            select(Registration).where(
                Registration.activity_id == activity_id,
                Registration.user_id == user_id,
            )
        )
        if reg is None or reg.status != RegistrationStatus.SIGNED.value:
            raise HTTPException(status_code=400, detail="你尚未报名该活动")

        reg.status = RegistrationStatus.CANCELED.value
        reg.canceled_at = datetime.now()
        db.commit()

        new_count = max(_db_signed_count(db, activity_id), 0)
        client.set(_count_key(activity_id), new_count, ex=COUNT_TTL)
        return new_count
