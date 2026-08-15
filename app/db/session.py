"""数据库引擎与会话管理。"""
from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

engine = create_engine(
    settings.sqlalchemy_url,
    pool_pre_ping=True,   # 取连接前先 ping，规避 MySQL 断连
    pool_recycle=3600,
    pool_size=10,
    max_overflow=20,
    echo=False,
    # 关键：READ COMMITTED。配合 Redis 分布式锁，锁内 COUNT 永远读到最新已提交数据，
    # 避免 REPEATABLE READ 快照导致名额判断读到旧计数而超报。
    isolation_level="READ_COMMITTED",
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db() -> Generator[Session, None, None]:
    """FastAPI 依赖：每个请求一个会话，结束后关闭。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables() -> None:
    """建表（开发用）；生产建议由迁移工具管理。"""
    from app.db.base import Base
    from app.models import user, activity, registration, task_record, ai_analysis  # noqa: F401

    Base.metadata.create_all(bind=engine)
    ensure_column_exists(
        engine,
        table="users",
        column="is_active",
        ddl="ALTER TABLE users ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT 1",
    )


def ensure_column_exists(engine, table: str, column: str, ddl: str) -> None:
    """幂等给已存在的表补列（MySQL 8 不支持 ADD COLUMN IF NOT EXISTS）。

    create_all 只建不存在的表，模型新增列后需手动补列。
    这里通过 information_schema 判断列是否已存在，缺列才执行 ALTER。
    """
    with engine.connect() as conn:
        exists = conn.execute(
            text(
                "SELECT COUNT(*) FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :t AND COLUMN_NAME = :c"
            ),
            {"t": table, "c": column},
        ).scalar()
        if not exists:
            conn.execute(text(ddl))
            conn.commit()
