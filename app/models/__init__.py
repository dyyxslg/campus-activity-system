"""ORM 模型统一导出。"""
from app.models.activity import Activity
from app.models.ai_analysis import AiAnalysisResult
from app.models.registration import Registration
from app.models.task_record import TaskRecord
from app.models.user import User

__all__ = ["Activity", "AiAnalysisResult", "Registration", "TaskRecord", "User"]
