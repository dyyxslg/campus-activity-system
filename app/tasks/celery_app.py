"""Celery 应用：broker=RabbitMQ，result backend=Redis。

用途：
- 异步生成报名 CSV 报表，规避 HTTP 长请求超时
- 异步执行 AI 数据分析，避免大模型响应慢阻塞 web 接口
- Celery-Beat 定时任务：活动状态流转 / 报表文件清理

启动（本地虚拟环境 / Windows）：
    celery -A app.tasks.celery_app.celery_app worker --loglevel=info --pool=threads
    celery -A app.tasks.celery_app.celery_app beat --loglevel=info

Linux 容器内使用默认 prefork pool（见 docker-compose.yml）。
"""
from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "campus_activity",
    broker=settings.RABBITMQ_URL,
    backend=settings.REDIS_URL,
    include=["app.tasks.report", "app.tasks.scheduled", "app.tasks.ai_analysis"],
)

celery_app.conf.update(
    # 消息序列化
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    # 时区：与业务库内 naive 时间保持一致（Asia/Shanghai）
    timezone="Asia/Shanghai",
    enable_utc=False,
    # 任务执行
    task_track_started=True,
    task_acks_late=False,
    worker_max_tasks_per_child=200,
    task_ignore_result=True,  # 结果以 TaskRecord 表 + Redis 进度为准，不存 Celery result
    # 兼容启动时 broker 尚未就绪的情况
    broker_connection_retry_on_startup=True,
    # ---------- Celery-Beat 定时调度 ----------
    beat_schedule={
        # 每分钟检查活动状态是否该自动流转（报名截止/活动结束/进入报名期）
        "auto-transition-activities": {
            "task": "tasks.auto_transition_activities",
            "schedule": crontab(minute="*"),
        },
        # 每日 03:17 清理过期报表文件与历史任务记录（错开整点，避免镜像站点拥塞）
        "cleanup-expired-reports": {
            "task": "tasks.cleanup_expired_reports",
            "schedule": crontab(minute=17, hour=3),
        },
    },
)
