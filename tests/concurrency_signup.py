"""并发报名测试脚本：验证 Redis 分布式锁防止超报。

单人即可复现两类场景：
  1) 默认（加锁）：M 个用户同时抢 N 个名额，最终报名人数严格 == N，零超报。
  2) --no-lock：跳过分布式锁，对比演示「查询-判断-插入」竞态导致的超报。

用法：
    python tests/concurrency_signup.py --capacity 30 --users 50            # 加锁（默认）
    python tests/concurrency_signup.py --capacity 30 --users 50 --no-lock  # 不加锁对照

说明：直接调用服务层（绕过 HTTP 与限流），只为隔离验证分布式锁本身。
"""
import argparse
import sys
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import HTTPException  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.redis import get_redis  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.models import Activity, User  # noqa: E402
from app.models.enums import ActivityStatus  # noqa: E402
from app.services.registration_service import signup  # noqa: E402

LOCK_TTL = 30  # 测试线程多，锁 TTL 给足，避免测试期锁过期


def _prepare(capacity: int, user_count: int) -> tuple[int, list[int]]:
    db = SessionLocal()
    now = datetime.now()
    activity = Activity(
        title="并发抢报测试活动",
        description="专用于并发测试",
        max_participants=capacity,
        signup_start_at=now - timedelta(days=1),
        signup_end_at=now + timedelta(days=1),
        event_start_at=now + timedelta(days=2),
        event_end_at=now + timedelta(days=3),
        status=ActivityStatus.OPEN.value,
        creator_id=1,
    )
    db.add(activity)
    db.commit()
    db.refresh(activity)
    # 关键：尽早取出 id，后续 user 循环的 commit 会把 session 内对象全部标记过期
    activity_id = activity.id

    user_ids = []
    for i in range(user_count):
        u = User(username=f"conc_user_{activity_id}_{i}", password_hash="x", nickname=f"U{i}")
        db.add(u)
        db.commit()
        db.refresh(u)
        user_ids.append(u.id)
    db.close()
    return activity_id, user_ids


def run_concurrency(capacity: int, user_count: int, no_lock: bool, race_delay_ms: int = 0) -> dict:
    activity_id, user_ids = _prepare(capacity, user_count)
    client = get_redis()

    success = 0
    full = 0
    lock_fail = 0
    other_err = 0
    barrier = threading.Barrier(user_count)
    results_lock = threading.Lock()

    def worker(uid: int):
        nonlocal success, full, lock_fail, other_err
        barrier.wait()  # 齐步起跑，制造最大并发
        db = SessionLocal()
        try:
            try:
                _, _ = signup(db, client, activity_id, uid, use_lock=not no_lock, race_delay_ms=race_delay_ms)
                with results_lock:
                    success += 1
            except HTTPException as e:
                if "已满" in e.detail:
                    with results_lock:
                        full += 1
                else:
                    with results_lock:
                        other_err += 1
        except TimeoutError:
            with results_lock:
                lock_fail += 1
        except Exception:
            with results_lock:
                other_err += 1
        finally:
            db.close()

    threads = [threading.Thread(target=worker, args=(uid,)) for uid in user_ids]
    t0 = time.time()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    elapsed = time.time() - t0

    # 最终库内实际报名人数（不经过缓存，直接查库）
    from sqlalchemy import func, select
    from app.models import Registration
    from app.models.enums import RegistrationStatus

    db = SessionLocal()
    final_count = db.scalar(
        select(func.count())
        .select_from(Registration)
        .where(
            Registration.activity_id == activity_id,
            Registration.status == RegistrationStatus.SIGNED.value,
        )
    )
    db.close()

    return {
        "activity_id": activity_id,
        "capacity": capacity,
        "users": user_count,
        "success": success,
        "full": full,
        "lock_fail": lock_fail,
        "other_err": other_err,
        "final_count": final_count,
        "elapsed": round(elapsed, 2),
        "no_lock": no_lock,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="并发报名测试")
    parser.add_argument("--capacity", type=int, default=30, help="活动名额")
    parser.add_argument("--users", type=int, default=50, help="并发报名人数")
    parser.add_argument("--no-lock", action="store_true", help="跳过分布式锁，演示超报")
    parser.add_argument("--race-delay-ms", type=int, default=80,
                        help="放大「查数-写入」间隙（仅不加锁演示有效，稳定复现竞态）")
    args = parser.parse_args()

    assert args.users > args.capacity, "并发人数应大于活动名额，否则无法体现竞争"

    print(f"=== 并发报名测试: 名额 {args.capacity}, 并发 {args.users}, 锁={'关闭' if args.no_lock else '开启'} ===")
    print(f"数据库: {engine.url.render_as_string(hide_password=True)}")

    race_delay = args.race_delay_ms if args.no_lock else 0
    result = run_concurrency(args.capacity, args.users, args.no_lock, race_delay)

    print(f"耗时: {result['elapsed']}s")
    print(f"报名成功: {result['success']}")
    print(f"名额已满被拒: {result['full']}")
    print(f"获取锁超时: {result['lock_fail']}")
    print(f"其他错误: {result['other_err']}")
    print(f"最终库内报名人数: {result['final_count']} / 容量 {result['capacity']}")

    if result["no_lock"]:
        over = result["final_count"] > result["capacity"]
        print(f"结果判定: {'超报复现成功（不加锁时报名人数超过上限）' if over else '本次未复现超报（可加大并发量或重试）'}")
        sys.exit(0 if over else 1)
    else:
        ok = result["final_count"] == result["capacity"]
        print(f"结果判定: {'PASS — 报名人数严格等于名额，未超报' if ok else 'FAIL — 出现超报'}")
        sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
