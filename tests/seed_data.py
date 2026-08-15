"""批量造数据脚本：为大数据量报表导出 / AI 分析 / 定时清理等场景灌入真实感数据。

特性：
- 一次生成多个处于不同状态的活动（DRAFT / OPEN / CLOSED / FINISHED）；
- OPEN 大活动灌入数千条报名记录，报名时间按「晚间高峰」分布，含一部分已取消记录，
  便于观察报表导出的分批进度、AI 统计的按小时/按天分布与取消率；
- 使用 SQLAlchemy Core executemany 批量插入，1 万行量级秒级完成；
- 每次运行用唯一前缀（时间戳）生成新用户/新活动，可反复运行互不冲突；
- --clean 可先清理历史上所有种子数据（按前缀匹配），保持数据库整洁。

用法：
    python tests/seed_data.py                            # 默认：大活动 5000 报名
    python tests/seed_data.py --signups 20000            # 大数据量压力测试报表导出
    python tests/seed_data.py --signups 200 --quick      # 小批量快速验证
    python tests/seed_data.py --clean                    # 清空所有种子数据
"""
import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path
from random import Random

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import delete, func, insert, select  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.models import Activity, AiAnalysisResult, Registration, TaskRecord, User  # noqa: E402
from app.models.enums import (  # noqa: E402
    ActivityStatus,
    RegistrationStatus,
    UserRole,
)

# 确定性的随机种子：同参数重跑，报名时间分布完全一致（便于复现）
RNG_SEED = 20260813
# 晚间 18-23 点权重更高，模拟真实社团报名的活跃时段
HOUR_WEIGHTS = [1, 1, 1, 1, 1, 1, 2, 3, 3, 2, 2, 2, 2, 2, 3, 3, 3, 4, 5, 6, 5, 4, 3, 2]
TITLE_PREFIX = "【种子】"
USERNAME_PREFIX = "seed_"

# 每批插入行数，避免单条 INSERT 过大
BATCH = 2000


def _pick_signup_time(rng: Random, window_start: datetime, window_days: int) -> datetime:
    """在报名窗口内生成带晚间高峰的报名时间（锚定 window_start 相对偏移）。"""
    day = rng.randrange(window_days)
    hour = rng.choices(range(24), weights=HOUR_WEIGHTS)[0]
    minute = rng.randrange(60)
    second = rng.randrange(60)
    return window_start + timedelta(days=day, hours=hour, minutes=minute, seconds=second)


def _delete_all_seed_data() -> None:
    """清理所有种子数据，按外键依赖从子到父顺序：
    ai_analysis_results -> task_records -> registrations -> activities -> users。

    注意 MySQL 限制：不能 DELETE 同表时在子查询里引用该表（错误 1093），
    因此先在 Python 侧取回 id 列表，再以字面量 IN 删除。
    """
    db = SessionLocal()
    try:
        seed_activity_ids = list(
            db.scalars(select(Activity.id).where(Activity.title.like(f"{TITLE_PREFIX}%")))
        )
        seed_user_ids = list(
            db.scalars(select(User.id).where(User.username.like(f"{USERNAME_PREFIX}%")))
        )
        seed_task_record_ids = list(
            db.scalars(select(TaskRecord.id).where(TaskRecord.activity_id.in_(seed_activity_ids)))
        )

        # 子表先删
        db.execute(
            delete(AiAnalysisResult).where(AiAnalysisResult.activity_id.in_(seed_activity_ids))
        )
        db.execute(delete(AiAnalysisResult).where(AiAnalysisResult.task_record_id.in_(seed_task_record_ids)))
        db.execute(delete(TaskRecord).where(TaskRecord.activity_id.in_(seed_activity_ids)))
        db.execute(delete(TaskRecord).where(TaskRecord.created_by.in_(seed_user_ids)))
        db.execute(delete(Registration).where(Registration.activity_id.in_(seed_activity_ids)))
        db.execute(delete(Registration).where(Registration.user_id.in_(seed_user_ids)))
        # 父表后删
        db.execute(delete(Activity).where(Activity.id.in_(seed_activity_ids)))
        db.execute(delete(User).where(User.id.in_(seed_user_ids)))
        db.commit()
        print("已清理全部种子数据")
    finally:
        db.close()


def _ensure_admin(db) -> int:
    """确保存在至少一个管理员用于 activity.creator_id。"""
    admin = db.scalar(select(User).where(User.role == UserRole.ADMIN.value).limit(1))
    if admin is not None:
        return admin.id
    u = User(username="seed_admin", password_hash="x", nickname="种子管理员", role=UserRole.ADMIN.value)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u.id


def _insert_students(db, count: int, prefix: str) -> dict[int, int]:
    """批量插入学生用户（executemany 快插），返回 {用户名序号: user_id}。"""
    if count <= 0:
        return {}
    rows = [
        {
            "username": f"{USERNAME_PREFIX}{prefix}_{i}",
            "password_hash": "x",  # 纯造数，不校验登录
            "nickname": f"同学{i}",
            "role": UserRole.STUDENT.value,
        }
        for i in range(count)
    ]
    for start in range(0, len(rows), BATCH):
        db.execute(insert(User), rows[start : start + BATCH])
    db.commit()

    # 统一回查主键：executemany 不返回每行自增 id
    id_map: dict[int, int] = {}
    for uid, username in db.execute(
        select(User.id, User.username)
        .where(User.username.like(f"{USERNAME_PREFIX}{prefix}_%"))
        .order_by(User.id)
    ):
        idx = int(username.split("_")[-1])  # seed_{prefix}_{idx}
        id_map[idx] = uid
    return id_map


def _create_activity(db, *, title: str, capacity: int, status: str,
                     signup_start: datetime, signup_end: datetime,
                     event_start: datetime, event_end: datetime, creator_id: int) -> Activity:
    act = Activity(
        title=f"{TITLE_PREFIX}{title}",
        description="种子脚本生成的演示数据",
        max_participants=capacity,
        signup_start_at=signup_start,
        signup_end_at=signup_end,
        event_start_at=event_start,
        event_end_at=event_end,
        status=status,
        creator_id=creator_id,
    )
    db.add(act)
    db.commit()
    db.refresh(act)
    return act


def _seed_registrations(db, rng: Random, activity: Activity, signed: int, cancel_ratio: float,
                        student_id_map: dict[int, int], next_index: int) -> int:
    """为活动灌入 signed 条报名 + 按比例取消的记录，返回已消耗的用户序号。"""
    total = signed + int(signed * cancel_ratio)
    if total == 0:
        return next_index

    window_days = (activity.signup_end_at - activity.signup_start_at).days
    window_start = activity.signup_start_at
    rows = []
    for k in range(total):
        idx = next_index + k
        uid = student_id_map[idx]
        signed_at = _pick_signup_time(rng, window_start, window_days)
        if k < signed:
            rows.append(
                {
                    "activity_id": activity.id,
                    "user_id": uid,
                    "status": RegistrationStatus.SIGNED.value,
                    "signed_at": signed_at,
                    "canceled_at": None,
                }
            )
        else:
            canceled_at = signed_at + timedelta(minutes=rng.randint(10, 300))
            rows.append(
                {
                    "activity_id": activity.id,
                    "user_id": uid,
                    "status": RegistrationStatus.CANCELED.value,
                    "signed_at": signed_at,
                    "canceled_at": canceled_at,
                }
            )
        if len(rows) >= BATCH:
            db.execute(insert(Registration), rows)
            rows.clear()
    if rows:
        db.execute(insert(Registration), rows)
    db.commit()
    return next_index + total


def main() -> None:
    parser = argparse.ArgumentParser(description="批量造数据脚本")
    parser.add_argument("--signups", type=int, default=5000, help="OPEN 大活动报名人数（默认 5000）")
    parser.add_argument("--capacity", type=int, default=8000, help="OPEN 大活动名额（默认 8000）")
    parser.add_argument("--cancel-ratio", type=float, default=0.12, help="已取消记录占比（默认 0.12）")
    parser.add_argument("--finished-signups", type=int, default=800, help="FINISHED 活动报名人数")
    parser.add_argument("--closed-signups", type=int, default=300, help="CLOSED 活动报名人数")
    parser.add_argument("--quick", action="store_true", help="小批量快速验证")
    parser.add_argument("--clean", action="store_true", help="仅清理全部种子数据后退出")
    args = parser.parse_args()

    if args.quick:
        args.signups = 200
        args.capacity = 400
        args.finished_signups = 30
        args.closed_signups = 10

    if args.clean:
        _delete_all_seed_data()
        return

    assert args.signups <= args.capacity, "报名人数不能超过活动名额"

    now = datetime.now()
    # 每次运行独立前缀，避免与前次种子数据撞唯一约束
    prefix = now.strftime("%H%M%S")
    rng = Random(RNG_SEED)

    # 计算需要的用户总数
    need_open = args.signups + int(args.signups * args.cancel_ratio)
    need_finished = args.finished_signups + int(args.finished_signups * args.cancel_ratio)
    need_closed = args.closed_signups + int(args.closed_signups * args.cancel_ratio)
    total_users = need_open + need_finished + need_closed

    print(f"=== 批量造数据 ===")
    print(f"数据库: {engine.url.render_as_string(hide_password=True)}")
    print(f"计划: OPEN 报名 {args.signups}(+取消) | FINISHED {args.finished_signups} | CLOSED {args.closed_signups} | 共需用户 {total_users}")

    db = SessionLocal()
    try:
        creator_id = _ensure_admin(db)
        student_id_map = _insert_students(db, total_users, prefix)
        if len(student_id_map) < total_users:
            # 同秒前缀冲突兜底（基本不会发生）
            raise RuntimeError("用户主键回查数量不足")

        # 各类状态活动
        open_act = _create_activity(
            db, title="秋季纳新·百团大战", capacity=args.capacity, status=ActivityStatus.OPEN.value,
            signup_start=now - timedelta(days=7), signup_end=now + timedelta(days=2),
            event_start=now + timedelta(days=3), event_end=now + timedelta(days=4), creator_id=creator_id,
        )
        closed_act = _create_activity(
            db, title="编程马拉松讲座", capacity=300, status=ActivityStatus.CLOSED.value,
            signup_start=now - timedelta(days=10), signup_end=now - timedelta(days=1),
            event_start=now + timedelta(days=5), event_end=now + timedelta(days=6), creator_id=creator_id,
        )
        finished_act = _create_activity(
            db, title="春季社团招新·已结束", capacity=1000, status=ActivityStatus.FINISHED.value,
            signup_start=now - timedelta(days=30), signup_end=now - timedelta(days=20),
            event_start=now - timedelta(days=15), event_end=now - timedelta(days=10), creator_id=creator_id,
        )
        draft_act = _create_activity(
            db, title="冬季跨年晚会（草稿）", capacity=2000, status=ActivityStatus.DRAFT.value,
            signup_start=now + timedelta(days=7), signup_end=now + timedelta(days=14),
            event_start=now + timedelta(days=15), event_end=now + timedelta(days=16), creator_id=creator_id,
        )

        idx = 0
        seed_activity_ids = []
        idx = _seed_registrations(db, rng, open_act, args.signups, args.cancel_ratio, student_id_map, idx)
        seed_activity_ids.append(open_act.id)
        idx = _seed_registrations(db, rng, finished_act, args.finished_signups, args.cancel_ratio, student_id_map, idx)
        seed_activity_ids.append(finished_act.id)
        idx = _seed_registrations(db, rng, closed_act, args.closed_signups, args.cancel_ratio, student_id_map, idx)
        seed_activity_ids.append(closed_act.id)

        # 校验：只统计本次新建的活动/用户
        added_regs = db.scalar(
            select(func.count())
            .select_from(Registration)
            .where(Registration.activity_id.in_(seed_activity_ids))
        ) or 0
        added_users = db.scalar(
            select(func.count())
            .select_from(User)
            .where(User.username.like(f"{USERNAME_PREFIX}{prefix}_%"))
        ) or 0
    finally:
        db.close()

    expected = total_users
    assert added_regs == idx == total_users, f"报名记录数异常: {added_regs} != {total_users}"
    assert added_users == total_users, f"用户数异常: {added_users} != {total_users}"
    print(f"完成: 新增活动 {len(seed_activity_ids)} 个, 报名记录 {added_regs} 条, 用户 {added_users} 名")
    print(f"  OPEN 活动报名时间已按晚间高峰分布，可直接提交报表导出 / AI 分析体验全链路")


if __name__ == "__main__":
    main()
