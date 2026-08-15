"""Celery-Beat 定时任务（自动化运维）。

1. 活动状态自动流转：
   - 到达报名截止时间 -> CLOSED
   - 到达活动结束时间 -> FINISHED
   - 草稿进入报名期 -> OPEN
2. 报表文件清理：删除超过保留天数的 CSV 报表，防止磁盘占满。
3. 历史任务记录清理：删除长期结束的任务记录。
"""
import logging
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import delete, select

from app.core.config import settings
from app.db.session import SessionLocal
from app.models import TaskRecord
from app.models.enums import TaskStatus
from app.services.activity_service import auto_transition_by_time
from app.tasks.celery_app import celery_app

logger = logging.getLogger("celery.task")

# 报表文件命名前缀（与 app/tasks/report.py 一致）
REPORT_PREFIX = "report_activity_"


@celery_app.task(name="tasks.auto_transition_activities")
def auto_transition_activities() -> dict:
    """活动状态自动流转：OPEN->CLOSED/FINISHED，DRAFT->OPEN。"""
    db = SessionLocal()
    try:
        stats = auto_transition_by_time(db)
        if any(stats.values()):
            logger.info("活动状态自动流转: %s", stats)
        return stats
    finally:
        db.close()


@celery_app.task(name="tasks.cleanup_expired_reports")
def cleanup_expired_reports() -> dict:
    """清理超过保留天数的报表文件 + 对应的历史任务记录。"""
    db = SessionLocal()
    removed_files = 0
    removed_records = 0
    try:
        report_dir = Path(settings.REPORT_DIR)
        retention = timedelta(days=settings.REPORT_RETENTION_DAYS)
        cutoff = datetime.now() - retention

        # 1) 按文件 mtime 删除过期报表
        if report_dir.exists():
            for f in report_dir.glob(f"{REPORT_PREFIX}*.csv"):
                mtime = datetime.fromtimestamp(f.stat().st_mtime)
                if mtime < cutoff:
                    f.unlink(missing_ok=True)
                    removed_files += 1

        # 2) 清理已结束且超过保留期的任务记录（连带找不到文件的情况）
        stmt = delete(TaskRecord).where(
            TaskRecord.status.in_(
                [
                    TaskStatus.SUCCESS.value,
                    TaskStatus.PARTIAL_FAIL.value,
                    TaskStatus.FAILED.value,
                ]
            ),
            TaskRecord.finished_at.isnot(None),
            TaskRecord.finished_at < cutoff,
        )
        result = db.execute(stmt)
        removed_records = result.rowcount or 0
        db.commit()

        if removed_files or removed_records:
            logger.info("清理完成: 删除报表文件 %s 个, 任务记录 %s 条", removed_files, removed_records)
        return {"removed_files": removed_files, "removed_records": removed_records}
    finally:
        db.close()
