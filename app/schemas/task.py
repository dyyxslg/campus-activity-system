"""异步任务相关请求 / 响应模型。"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TaskCreate(BaseModel):
    activity_id: int


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    celery_task_id: str
    task_type: str
    activity_id: int | None = None
    status: str
    progress: int
    total_count: int = 0
    success_count: int = 0
    fail_count: int = 0
    error_message: str | None = None
    created_at: datetime
    finished_at: datetime | None = None
    # 文件下载地址（动态注入）
    download_url: str | None = None


class TaskProgressOut(BaseModel):
    task_id: str
    status: str
    progress: int
    total_count: int
    success_count: int
    fail_count: int
    error_message: str | None = None
    download_url: str | None = None


class AiAnalysisOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    activity_id: int
    report: str
    model: str
    created_at: datetime
    # 结构化统计摘要（仅返回部分字段，stats_json 太占体积可另行获取）
    stats_json: dict | None = None
