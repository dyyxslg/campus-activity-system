"""管理员账号管理路由：用户列表 / 创建 / 重置密码 / 禁用启用 / 删除。

删除策略（软删除替代硬删，保护业务数据）：
- 用户存在报名记录、创建的活动或异步任务记录时，禁止硬删，提示改用禁用；
- 空账号可硬删；当前登录管理员不可操作自己，防止误锁。
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin
from app.core.security import hash_password
from app.db.session import get_db
from app.models import Activity, Registration, TaskRecord, User
from app.schemas.user import (
    UserCreate,
    UserOut,
    UserPageResult,
    UserResetPassword,
    UserUpdateActive,
)

router = APIRouter(prefix="/admin/users", tags=["账号管理"])


def _get_user_or_404(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    return user


def _forbid_self(user_id: int, admin: User) -> None:
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="不能对当前登录管理员账号执行此操作")


@router.get("", response_model=UserPageResult, summary="用户列表（分页/搜索/角色筛选）")
def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: str | None = Query(None, description="用户名/昵称模糊搜索"),
    role: str | None = Query(None, description="student / admin"),
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    stmt = select(User)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(or_(User.username.like(like), User.nickname.like(like)))
    if role:
        stmt = stmt.where(User.role == role)

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(User.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return UserPageResult(total=total, page=page, page_size=page_size, items=[UserOut.model_validate(u) for u in rows])


@router.post(
    "",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    summary="创建账号（可指定学生/管理员）",
)
def create_user(
    body: UserCreate,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    if db.scalar(select(User).where(User.username == body.username)):
        raise HTTPException(status_code=400, detail="用户名已被占用")
    user = User(
        username=body.username,
        password_hash=hash_password(body.password),
        nickname=body.nickname or body.username,
        role=body.role.value,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.put("/{user_id}/password", response_model=UserOut, summary="重置密码")
def reset_password(
    user_id: int,
    body: UserResetPassword,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    _forbid_self(user_id, admin)
    user = _get_user_or_404(db, user_id)
    user.password_hash = hash_password(body.new_password)
    db.commit()
    db.refresh(user)
    return user


@router.put("/{user_id}/active", response_model=UserOut, summary="启用 / 禁用账号")
def set_active(
    user_id: int,
    body: UserUpdateActive,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    _forbid_self(user_id, admin)
    user = _get_user_or_404(db, user_id)
    user.is_active = body.is_active
    db.commit()
    db.refresh(user)
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT, summary="删除账号（仅无业务数据时允许）")
def delete_user(
    user_id: int,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    _forbid_self(user_id, admin)
    user = _get_user_or_404(db, user_id)

    reg_cnt = db.scalar(
        select(func.count()).select_from(Registration).where(Registration.user_id == user_id)
    ) or 0
    act_cnt = db.scalar(
        select(func.count()).select_from(Activity).where(Activity.creator_id == user_id)
    ) or 0
    task_cnt = db.scalar(
        select(func.count()).select_from(TaskRecord).where(TaskRecord.created_by == user_id)
    ) or 0
    if reg_cnt or act_cnt or task_cnt:
        raise HTTPException(
            status_code=400,
            detail="该用户存在报名/活动/任务记录，不可删除；如需封禁请使用「禁用」",
        )

    db.delete(user)
    db.commit()
