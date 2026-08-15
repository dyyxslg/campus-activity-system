"""FastAPI 应用入口。

开发顺序（文档第九节）：
  步骤1 骨架 -> 步骤2 模型 -> 步骤3 鉴权/限流 -> 步骤4 活动CRUD
  -> 步骤5 报名+分布式锁 -> 步骤6 异步报表 -> 步骤7 定时任务 -> 步骤8 AI 分析
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import auth, activities, registrations, tasks, users
from app.core.config import settings

logger = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时尝试建表；基础设施未就绪时仅告警，不阻断服务启动
    try:
        from app.db.session import create_tables

        create_tables()
        logger.info("数据库表结构检查/创建完成")
    except Exception as e:  # noqa: BLE001
        logger.warning("建表失败（基础设施可能未就绪），稍后可重试: %s", e)
    yield


app = FastAPI(
    title="校园社团活动报名 & 数据分析后端系统",
    description="活动报名 / 异步报表导出 / Celery-Beat 定时运维 / AI 数据分析",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# 跨域：Vue 前端（5173 等）可直接调用本服务；生产按需收紧 allow_origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

API_PREFIX = settings.API_PREFIX
app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(activities.router, prefix=API_PREFIX)
app.include_router(registrations.router, prefix=API_PREFIX)
app.include_router(tasks.router, prefix=API_PREFIX)
app.include_router(users.router, prefix=API_PREFIX)


@app.get("/health", tags=["系统"], summary="健康检查")
def health() -> dict:
    return {"status": "ok", "app_env": settings.APP_ENV}
