"""创建管理员账号（运维脚本，命令行执行）。

用法：
    python scripts/create_admin.py --username admin --password admin123456 --nickname 管理员
"""
import argparse
import sys
from pathlib import Path

# 把项目根目录加入 sys.path，保证 `python scripts/xxx.py` 也能导入 app 包
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import User
from app.models.enums import UserRole


def main() -> None:
    parser = argparse.ArgumentParser(description="创建管理员账号")
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--nickname", default="管理员")
    args = parser.parse_args()

    with SessionLocal() as db:
        if db.scalar(select(User).where(User.username == args.username)):
            print(f"用户 {args.username} 已存在，跳过")
            return
        user = User(
            username=args.username,
            password_hash=hash_password(args.password),
            nickname=args.nickname,
            role=UserRole.ADMIN.value,
        )
        db.add(user)
        db.commit()
        print(f"管理员创建成功: {args.username} ({args.nickname})")


if __name__ == "__main__":
    main()
