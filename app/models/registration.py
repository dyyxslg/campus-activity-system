"""报名记录表。

设计要点：
- 同一用户同一活动最多一条记录（唯一约束），通过 status 字段在 SIGNED/CANCELED 之间切换。
- 取消后重新报名 = 把 status 改回 SIGNED 并刷新 signed_at，保证「不能重复报名」且能保留取消痕迹。
- 当前报名人数 = COUNT(status='SIGNED')，供分布式锁 + Redis 缓存使用。
"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import RegistrationStatus


class Registration(Base):
    __tablename__ = "registrations"
    __table_args__ = (
        UniqueConstraint("activity_id", "user_id", name="uq_registration_activity_user"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    activity_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("activities.id"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=RegistrationStatus.SIGNED.value
    )

    # 最新一次报名时间 / 最近一次取消时间
    signed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
