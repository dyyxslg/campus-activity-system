"""异步任务服务：任务记录管理 + 进度持久化（DB 权威 + Redis 实时）。

Redis 承担「任务执行进度」缓存：worker 每个批次回写 Redis + DB，
进度接口优先读 Redis，避免高频轮询打满 MySQL。
"""
import json
from datetime import datetime
from pathlib import Path

from redis import Redis
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import TaskRecord
from app.models.enums import TaskStatus

PROGRESS_KEY = "task:progress:{}"
PROGRESS_TTL = 86400 * 7  # 任务进度缓存 7 天


def create_task_record(
    db: Session,
    celery_task_id: str,
    task_type: str,
    activity_id: int | None,
    created_by: int,
) -> TaskRecord:
    record = TaskRecord(
        celery_task_id=celery_task_id,
        task_type=task_type,
        activity_id=activity_id,
        created_by=created_by,
        status=TaskStatus.PENDING.value,
        progress=0,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def update_progress(
    client: Redis,
    db: Session,
    record_id: int,
    *,
    status: str,
    progress: int,
    total: int = 0,
    success: int = 0,
    fail: int = 0,
    error_message: str | None = None,
    file_path: str | None = None,
) -> TaskRecord:
    """worker 内调用：更新 DB（权威）并回写 Redis（实时）。"""
    record = db.get(TaskRecord, record_id)
    if record is None:
        return record

    record.status = status
    record.progress = min(max(progress, 0), 100)
    record.total_count = total
    record.success_count = success
    record.fail_count = fail
    if error_message is not None:
        record.error_message = error_message
    if file_path is not None:
        record.file_path = file_path
    if status in (TaskStatus.SUCCESS.value, TaskStatus.PARTIAL_FAIL.value, TaskStatus.FAILED.value):
        record.finished_at = datetime.now()
    db.commit()

    _write_redis_progress(
        client,
        record_id,
        record.status,
        record.progress,
        record.total_count,
        record.success_count,
        record.fail_count,
        record.error_message,
    )
    return record


def get_progress(client: Redis, db: Session, record_id: int) -> TaskRecord | None:
    """进度查询：优先 Redis 快照，缺失回源 DB。"""
    cached = client.get(PROGRESS_KEY.format(record_id))
    if cached is not None:
        data = json.loads(cached)
        record = db.get(TaskRecord, record_id)
        if record is not None:
            # 用缓存值覆盖 DB 字段（Redis 是最新的实时进度）
            record.status = data["status"]
            record.progress = data["progress"]
            record.total_count = data.get("total", record.total_count)
            record.success_count = data.get("success", record.success_count)
            record.fail_count = data.get("fail", record.fail_count)
            record.error_message = data.get("error", record.error_message)
        return record
    return db.get(TaskRecord, record_id)


def _write_redis_progress(
    client: Redis,
    record_id: int,
    status: str,
    progress: int,
    total: int,
    success: int,
    fail: int,
    error: str | None,
) -> None:
    payload = json.dumps(
        {
            "status": status,
            "progress": progress,
            "total": total,
            "success": success,
            "fail": fail,
            "error": error,
        }
    )
    client.set(PROGRESS_KEY.format(record_id), payload, ex=PROGRESS_TTL)


def find_report_file_path(record: TaskRecord) -> str | None:
    """把 record.file_path 相对路径拼成绝对路径。"""
    if not record.file_path:
        return None
    return str(Path(settings.REPORT_DIR) / record.file_path)
