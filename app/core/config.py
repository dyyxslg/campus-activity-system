"""全局配置：从 .env 读取，所有模块共享。"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ---------- 服务基础配置 ----------
    APP_ENV: str = "dev"
    API_PREFIX: str = "/api/v1"
    SECRET_KEY: str = "change-me-in-production-please-xxxx"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    # ---------- MySQL ----------
    MYSQL_HOST: str = "127.0.0.1"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "activity_user"
    MYSQL_PASSWORD: str = "activity_pass"
    MYSQL_DATABASE: str = "campus_activity"
    DATABASE_URL: str = ""

    # ---------- Redis ----------
    REDIS_URL: str = "redis://127.0.0.1:6379/0"

    # ---------- RabbitMQ ----------
    RABBITMQ_URL: str = "amqp://127.0.0.1:5672//"

    # ---------- AI（可一键关闭） ----------
    AI_ENABLE: bool = False
    DEEPSEEK_API_KEY: str = "your_key_here"
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_MODEL: str = "deepseek-chat"

    # ---------- 报表导出 ----------
    REPORT_DIR: str = "./reports"
    REPORT_RETENTION_DAYS: int = 7
    # 历史异步任务记录保留天数（到期由定时任务清理）
    TASK_RECORD_RETENTION_DAYS: int = 30

    # ---------- 接口限流 ----------
    RATE_LIMIT_PER_SECOND: int = 10

    # ---------- 跨域（前端开发地址，逗号分隔） ----------
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def sqlalchemy_url(self) -> str:
        """优先使用 DATABASE_URL，否则按组件拼装。"""
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return (
            f"mysql+pymysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}"
            f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}?charset=utf8mb4"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
