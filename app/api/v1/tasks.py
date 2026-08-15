"""异步任务路由：报表导出任务的提交 / 进度 / 下载。AI 分析任务（步骤8）同挂此路由。"""
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin
from app.core.config import settings
from app.core.redis import get_redis
from app.db.session import get_db
from app.models import Activity, AiAnalysisResult, TaskRecord, User
from app.models.enums import TaskStatus, TaskType
from app.schemas.task import AiAnalysisOut, TaskOut, TaskProgressOut
from app.services.activity_service import ensure_owner
from app.services.task_service import (
    create_task_record,
    find_report_file_path,
    get_progress,
)
from app.tasks.ai_analysis import analyze_activity_ai
from app.tasks.report import export_registration_report

router = APIRouter(prefix="/tasks", tags=["异步任务"])


@router.post(
    "/reports/{activity_id}",
    response_model=TaskOut,
    status_code=202,
    summary="提交活动报名报表导出任务（异步，立即返回 task_id）",
)
def submit_report(
    activity_id: int,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    activity = db.get(Activity, activity_id)
    if activity is None:
        raise HTTPException(status_code=404, detail="活动不存在")
    ensure_owner(activity, admin.id)

    # 先落库拿 record.id，再提交 Celery 任务，最后回填 celery_task_id
    record = create_task_record(db, celery_task_id="", task_type=TaskType.REPORT.value,
                                activity_id=activity_id, created_by=admin.id)
    async_result = export_registration_report.delay(record.id, activity_id)
    record.celery_task_id = async_result.id
    db.commit()

    out = TaskOut.model_validate(record)
    out.download_url = f"{settings.API_PREFIX}/tasks/reports/{record.id}/download"
    return out


@router.get(
    "/reports/{record_id}/progress",
    response_model=TaskProgressOut,
    summary="查询异步任务进度（报表/AI 通用；优先读 Redis 实时进度）",
)
def report_progress(
    record_id: int,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    record = get_progress(get_redis(), db, record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    # 报表与 AI 分析任务共用进度查询（下载仅报表有意义）
    if record.task_type not in (TaskType.REPORT.value, TaskType.AI_ANALYSIS.value):
        raise HTTPException(status_code=400, detail="任务类型不匹配")

    out = TaskProgressOut(
        task_id=record.celery_task_id,
        status=record.status,
        progress=record.progress,
        total_count=record.total_count,
        success_count=record.success_count,
        fail_count=record.fail_count,
        error_message=record.error_message,
    )
    if (
        record.task_type == TaskType.REPORT.value
        and record.status in (TaskStatus.SUCCESS.value, TaskStatus.PARTIAL_FAIL.value)
    ):
        out.download_url = f"{settings.API_PREFIX}/tasks/reports/{record.id}/download"
    return out


@router.get("/reports/{record_id}/download", summary="下载生成的报表 CSV")
def download_report(
    record_id: int,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    record = db.get(TaskRecord, record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    if record.status not in (TaskStatus.SUCCESS.value, TaskStatus.PARTIAL_FAIL.value):
        raise HTTPException(status_code=400, detail="任务尚未完成，无法下载")

    file_path = find_report_file_path(record)
    if not file_path or not Path(file_path).exists():
        raise HTTPException(status_code=404, detail="报表文件不存在或已清理")

    return FileResponse(
        file_path,
        media_type="text/csv; charset=utf-8",
        filename=Path(file_path).name,
    )


@router.post(
    "/ai/{activity_id}",
    response_model=TaskOut,
    status_code=202,
    summary="提交活动 AI 数据分析任务（异步；AI_ENABLE=false 时拒绝）",
)
def submit_ai_analysis(
    activity_id: int,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    if not settings.AI_ENABLE:
        raise HTTPException(
            status_code=400,
            detail="AI 分析功能未开启（AI_ENABLE=false），可前往 .env 开启",
        )
    activity = db.get(Activity, activity_id)
    if activity is None:
        raise HTTPException(status_code=404, detail="活动不存在")
    ensure_owner(activity, admin.id)

    record = create_task_record(db, celery_task_id="", task_type=TaskType.AI_ANALYSIS.value,
                                activity_id=activity_id, created_by=admin.id)
    async_result = analyze_activity_ai.delay(record.id, activity_id)
    record.celery_task_id = async_result.id
    db.commit()

    out = TaskOut.model_validate(record)
    out.download_url = None
    return out


@router.get("/ai/{activity_id}/result", response_model=AiAnalysisOut, summary="查询活动最新 AI 分析结果")
def ai_analysis_result(
    activity_id: int,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    activity = db.get(Activity, activity_id)
    if activity is None:
        raise HTTPException(status_code=404, detail="活动不存在")
    ensure_owner(activity, admin.id)

    result = db.scalar(
        select(AiAnalysisResult)
        .where(AiAnalysisResult.activity_id == activity_id)
        .order_by(AiAnalysisResult.id.desc())
        .limit(1)
    )
    if result is None:
        raise HTTPException(status_code=404, detail="该活动尚无 AI 分析结果")
    return result


@router.get("/reports", response_model=list[TaskOut], summary="我的报表任务列表")
def list_reports(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    stmt = (
        select(TaskRecord)
        .where(
            TaskRecord.task_type == TaskType.REPORT.value,
            TaskRecord.created_by == admin.id,
        )
        .order_by(TaskRecord.id.desc())
    )
    records = db.scalars(
        stmt.offset((page - 1) * page_size).limit(page_size)
    ).all()
    result = []
    for record in records:
        out = TaskOut.model_validate(record)
        if record.status in (TaskStatus.SUCCESS.value, TaskStatus.PARTIAL_FAIL.value):
            out.download_url = f"{settings.API_PREFIX}/tasks/reports/{record.id}/download"
        result.append(out)
    return result
