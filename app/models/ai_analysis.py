"""AI 数据分析结果表。

AI 模块可一键关闭（AI_ENABLE=false），本表只是数据载体，不承载任何业务依赖。
"""
from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AiAnalysisResult(Base):
    __tablename__ = "ai_analysis_results"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    activity_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("activities.id"), nullable=False, index=True
    )
    # 关联的异步任务记录
    task_record_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("task_records.id"), nullable=True
    )

    # 送入大模型的结构化业务统计（JSON）
    stats_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # 大模型输出的运营优化建议
    report: Mapped[str | None] = mapped_column(Text, nullable=True)
    model: Mapped[str] = mapped_column(String(64), default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="SUCCESS")

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
