"""活动业务服务：CRUD + 状态机流转。

供 HTTP 路由与 Celery 定时任务复用（步骤7 会调用 auto_transition_by_time）。
"""
from datetime import datetime

from fastapi import HTTPException, status as http_status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Activity, Registration
from app.models.enums import ACTIVITY_TRANSITIONS, ActivityStatus, RegistrationStatus

PUBLIC_STATUSES = (
    ActivityStatus.OPEN.value,
    ActivityStatus.CLOSED.value,
    ActivityStatus.FINISHED.value,
)


def ensure_owner(activity: Activity, user_id: int) -> None:
    if activity.creator_id != user_id:
        raise HTTPException(status_code=403, detail="只能操作自己创建的活动")


def validate_time_order(activity: Activity) -> None:
    """校验活动时间顺序（创建/编辑后调用，编辑需合并后的最终值）。"""
    if activity.signup_start_at >= activity.signup_end_at:
        raise HTTPException(status_code=400, detail="报名开始时间必须早于报名截止时间")
    if activity.signup_end_at > activity.event_start_at:
        raise HTTPException(status_code=400, detail="报名截止时间应早于活动开始时间")
    if activity.event_start_at >= activity.event_end_at:
        raise HTTPException(status_code=400, detail="活动开始时间必须早于活动结束时间")


def signed_count_for(db: Session, activity_id: int) -> int:
    return db.scalar(
        select(func.count())
        .select_from(Registration)
        .where(
            Registration.activity_id == activity_id,
            Registration.status == RegistrationStatus.SIGNED.value,
        )
    ) or 0


def batch_signed_counts(db: Session, activity_ids: list[int]) -> dict[int, int]:
    """一次查询多条活动的报名人数，避免 N+1。"""
    if not activity_ids:
        return {}
    rows = db.execute(
        select(Registration.activity_id, func.count())
        .where(
            Registration.activity_id.in_(activity_ids),
            Registration.status == RegistrationStatus.SIGNED.value,
        )
        .group_by(Registration.activity_id)
    ).all()
    return {aid: cnt for aid, cnt in rows}


def change_status(db: Session, activity: Activity, target: str, user_id: int) -> Activity:
    """活动状态迁移，带合法性校验（服务层/路由共用）。"""
    ensure_owner(activity, user_id)
    try:
        current = ActivityStatus(activity.status)
        target_enum = ActivityStatus(target)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"非法状态: {target}")

    allowed = ACTIVITY_TRANSITIONS.get(current, set())
    if target_enum not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"非法状态迁移: {current.value} -> {target_enum.value}",
        )

    now = datetime.now()
    if target_enum is ActivityStatus.OPEN and now >= activity.signup_end_at:
        raise HTTPException(status_code=400, detail="报名截止时间已过，无法开放报名")

    activity.status = target_enum.value
    db.commit()
    db.refresh(activity)
    return activity


def auto_transition_by_time(db: Session, now: datetime | None = None) -> dict[str, int]:
    """定时任务用：根据时间自动流转所有活动状态。

    返回变更统计 {"opened": n, "closed": n, "finished": n}
    """
    now = now or datetime.now()
    stats = {"opened": 0, "closed": 0, "finished": 0}

    activities = db.scalars(
        select(Activity).where(Activity.status == ActivityStatus.DRAFT.value)
    ).all()
    for a in activities:
        # 草稿且已进入报名期 -> 自动开放（管理员已安排上架）
        if now >= a.signup_start_at:
            a.status = ActivityStatus.OPEN.value
            stats["opened"] += 1

    activities = db.scalars(
        select(Activity).where(Activity.status == ActivityStatus.OPEN.value)
    ).all()
    for a in activities:
        if now >= a.event_end_at:
            a.status = ActivityStatus.FINISHED.value
            stats["finished"] += 1
        elif now >= a.signup_end_at:
            a.status = ActivityStatus.CLOSED.value
            stats["closed"] += 1

    db.commit()
    return stats
