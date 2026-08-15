"""异步任务记录表：报表导出 / AI 分析 共用，持久化进度与状态。"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import TaskStatus


class TaskRecord(Base):
    __tablename__ = "task_records"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # Celery task_id，用于前端轮询进度 / 下载结果
    celery_task_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    task_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)  # REPORT / AI_ANALYSIS

    activity_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("activities.id"), nullable=True, index=True
    )
    created_by: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=True
    )

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=TaskStatus.PENDING.value, index=True
    )
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # 0-100

    total_count: Mapped[int] = mapped_column(Integer, default=0)
    success_count: Mapped[int] = mapped_column(Integer, default=0)
    fail_count: Mapped[int] = mapped_column(Integer, default=0)

    # 报表落盘相对路径（如 reports/xxxx.csv），下载接口据此拼绝对路径
    file_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
