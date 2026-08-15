"""AI 数据分析的统计采集：基于系统真实报名行为数据生成结构化指标。

不依赖大模型，纯 SQL 聚合；AI 仅消费这里产出的 JSON。
"""
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Activity, Registration
from app.models.enums import RegistrationStatus


def collect_activity_stats(db: Session, activity: Activity) -> dict:
    """采集某活动的报名统计指标，供大模型做业务分析。"""
    base = select(Registration).where(Registration.activity_id == activity.id)

    total_signups = db.scalar(
        select(func.count())
        .select_from(Registration)
        .where(
            Registration.activity_id == activity.id,
            Registration.status == RegistrationStatus.SIGNED.value,
        )
    ) or 0

    total_cancels = db.scalar(
        select(func.count())
        .select_from(Registration)
        .where(
            Registration.activity_id == activity.id,
            Registration.canceled_at.isnot(None),
        )
    ) or 0

    # 报名时间分布：按小时
    hour_dist = dict(
        db.execute(
            select(func.hour(Registration.signed_at), func.count())
            .where(
                Registration.activity_id == activity.id,
                Registration.signed_at.isnot(None),
            )
            .group_by(func.hour(Registration.signed_at))
            .order_by(func.hour(Registration.signed_at))
        ).all()
    )
    # 报名时间分布：按天
    day_dist = dict(
        db.execute(
            select(func.date(Registration.signed_at), func.count())
            .where(
                Registration.activity_id == activity.id,
                Registration.signed_at.isnot(None),
            )
            .group_by(func.date(Registration.signed_at))
            .order_by(func.date(Registration.signed_at))
        ).all()
    )

    peak_hours = sorted(
        (h for h, cnt in hour_dist.items() if cnt == max(hour_dist.values(), default=0) and cnt > 0)
    )
    peak_day = max(day_dist, key=day_dist.get, default=None)

    return {
        "activity_id": activity.id,
        "activity_title": activity.title,
        "capacity": activity.max_participants,
        "status": activity.status,
        "signup_window": {
            "start": activity.signup_start_at.isoformat() if activity.signup_start_at else None,
            "end": activity.signup_end_at.isoformat() if activity.signup_end_at else None,
        },
        "total_signups": total_signups,
        "current_signed": total_signups,
        "total_cancels": total_cancels,
        "cancel_rate": round(total_cancels / total_signups, 4) if total_signups else 0,
        "occupancy_rate": round(total_signups / activity.max_participants, 4)
        if activity.max_participants
        else 0,
        "signup_by_hour": {str(h): c for h, c in sorted(hour_dist.items())},
        "signup_by_day": {str(d): c for d, c in sorted(day_dist.items(), key=lambda x: str(x[0]))},
        "peak_signup_hours": [str(h) for h in peak_hours],
        "peak_signup_day": str(peak_day) if peak_day else None,
        "collected_at": datetime.now().isoformat(),
    }
