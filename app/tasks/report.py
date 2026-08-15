"""异步报名报表导出任务。

解决痛点：HTTP 接口内同步生成 CSV 在大数据量下会触发网关超时。
方案：Celery worker 后台分页拉取报名数据，流式写 CSV，实时上报进度。

容错：单条脏数据不拖垮整个任务 —— 记录到 fail_count，其余正常导出，
最终状态为 PARTIAL_FAIL（部分失败）而不是整体 FAILED。
"""
import csv
import os
import uuid
from datetime import datetime
from pathlib import Path

from sqlalchemy import func, select

from app.core.config import settings
from app.core.redis import get_redis
from app.db.session import SessionLocal
from app.models import Activity, Registration, User
from app.models.enums import TaskStatus
from app.services.task_service import update_progress
from app.tasks.celery_app import celery_app

BATCH_SIZE = 2000  # 每批处理行数，控制内存与进度粒度

CSV_HEADER = ["报名ID", "活动ID", "用户名", "昵称", "报名状态", "报名时间", "取消时间"]


@celery_app.task(name="tasks.export_registration_report", bind=True)
def export_registration_report(self, task_record_id: int, activity_id: int) -> str:
    """批量导出某活动的报名记录为 CSV，返回最终状态字符串。"""
    db = SessionLocal()
    client = get_redis()
    report_dir = Path(settings.REPORT_DIR)
    report_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = report_dir / f".{uuid.uuid4().hex}.csv.tmp"
    final_name = ""
    final_path = None

    try:
        activity = db.get(Activity, activity_id)
        if activity is None:
            update_progress(
                client, db, task_record_id,
                status=TaskStatus.FAILED.value, progress=100,
                error_message="活动不存在",
            )
            return TaskStatus.FAILED.value

        total = db.scalar(
            select(func.count())
            .select_from(Registration)
            .where(Registration.activity_id == activity_id)
        ) or 0

        if total == 0:
            update_progress(
                client, db, task_record_id,
                status=TaskStatus.SUCCESS.value, progress=100, total=0, success=0, fail=0,
            )
            return TaskStatus.SUCCESS.value

        update_progress(
            client, db, task_record_id,
            status=TaskStatus.RUNNING.value, progress=0, total=total,
        )

        final_name = f"report_activity_{activity_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        final_path = report_dir / final_name

        success = 0
        fail = 0
        last_id = 0
        processed = 0

        with open(tmp_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(CSV_HEADER)

            while True:
                # 按主键游标分页（id > last_id），避免 OFFSET 深翻页性能问题
                rows = db.execute(
                    select(Registration, User)
                    .join(User, User.id == Registration.user_id)
                    .where(
                        Registration.activity_id == activity_id,
                        Registration.id > last_id,
                    )
                    .order_by(Registration.id)
                    .limit(BATCH_SIZE)
                ).all()

                if not rows:
                    break

                for reg, user in rows:
                    try:
                        writer.writerow(
                            [
                                reg.id,
                                reg.activity_id,
                                user.username,
                                user.nickname,
                                reg.status,
                                reg.signed_at.strftime("%Y-%m-%d %H:%M:%S") if reg.signed_at else "",
                                reg.canceled_at.strftime("%Y-%m-%d %H:%M:%S") if reg.canceled_at else "",
                            ]
                        )
                        success += 1
                    except Exception:  # noqa: BLE001 单条脏数据不拖垮任务
                        fail += 1

                processed += len(rows)
                last_id = rows[-1][0].id
                progress = int(processed / total * 100) if total else 100
                update_progress(
                    client, db, task_record_id,
                    status=TaskStatus.RUNNING.value, progress=progress,
                    total=total, success=success, fail=fail,
                )

        # 原子改名：全部写入完成才对外可见
        os.replace(tmp_path, final_path)

        status = TaskStatus.SUCCESS.value if fail == 0 else TaskStatus.PARTIAL_FAIL.value
        update_progress(
            client, db, task_record_id,
            status=status, progress=100,
            total=total, success=success, fail=fail,
            file_path=final_name,
        )
        return status

    except Exception as e:  # noqa: BLE001
        try:
            update_progress(
                client, db, task_record_id,
                status=TaskStatus.FAILED.value, progress=100,
                error_message=str(e)[:1000],
            )
        finally:
            pass
        return TaskStatus.FAILED.value

    finally:
        db.close()
        # 出错时清理半成品临时文件
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
