"""活动表：全生命周期状态管理。"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import ActivityStatus


class Activity(Base):
    __tablename__ = "activities"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, default="")

    max_participants: Mapped[int] = mapped_column(nullable=False)  # 最大报名人数
    signup_start_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    signup_end_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    event_start_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)   # 活动开始
    event_end_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)     # 活动结束

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ActivityStatus.DRAFT.value, index=True
    )
    creator_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False, index=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
