"""报名业务路由：报名 / 取消 / 我的报名 / 管理员查看明细。"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin, get_current_user, rate_limit
from app.core.redis import get_redis
from app.db.session import get_db
from app.models import Activity, Registration, User
from app.models.enums import ActivityStatus, RegistrationStatus
from app.schemas.registration import (
    MyRegistration,
    RegistrationAdminListItem,
    RegistrationOverviewItem,
    RegistrationPageResult,
    RegistrationStatusInfo,
    SignupResult,
)
from app.services.activity_service import ensure_owner, signed_count_for
from app.services.registration_service import cancel, get_cached_count, signup

router = APIRouter(prefix="/registrations", tags=["报名业务"])


@router.get(
    "",
    response_model=RegistrationPageResult,
    summary="管理员查看全部报名记录（跨活动，分页/筛选）",
)
def all_registrations(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    activity_id: int | None = Query(None, description="按活动筛选"),
    status_filter: str | None = Query(None, alias="status", description="SIGNED / CANCELED"),
    keyword: str | None = Query(None, description="用户名/昵称搜索"),
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    stmt = (
        select(Registration, Activity, User)
        .join(Activity, Activity.id == Registration.activity_id)
        .join(User, User.id == Registration.user_id)
    )
    if activity_id:
        stmt = stmt.where(Registration.activity_id == activity_id)
    if status_filter:
        stmt = stmt.where(Registration.status == status_filter)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(or_(User.username.like(like), User.nickname.like(like)))

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.execute(
        stmt.order_by(Registration.signed_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return RegistrationPageResult(
        total=total,
        page=page,
        page_size=page_size,
        items=[
            RegistrationOverviewItem(
                id=reg.id,
                activity_id=reg.activity_id,
                activity_title=activity.title,
                user_id=reg.user_id,
                username=user.username,
                nickname=user.nickname,
                status=reg.status,
                signed_at=reg.signed_at,
                canceled_at=reg.canceled_at,
            )
            for reg, activity, user in rows
        ],
    )


@router.post(
    "/{activity_id}",
    response_model=SignupResult,
    summary="报名活动（Redis 分布式锁防超报）",
    dependencies=[Depends(rate_limit)],
)
def signup_activity(
    activity_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    count, reg_status = signup(db, get_redis(), activity_id, current_user.id)
    return SignupResult(
        activity_id=activity_id,
        user_id=current_user.id,
        status=reg_status,
        signed_count=count,
        message="报名成功",
    )


@router.delete(
    "/{activity_id}",
    response_model=SignupResult,
    summary="取消我的报名",
    dependencies=[Depends(rate_limit)],
)
def cancel_registration(
    activity_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    count = cancel(db, get_redis(), activity_id, current_user.id)
    return SignupResult(
        activity_id=activity_id,
        user_id=current_user.id,
        status=RegistrationStatus.CANCELED.value,
        signed_count=count,
        message="已取消报名",
    )


@router.get("/my", response_model=list[MyRegistration], summary="我的报名列表")
def my_registrations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = db.execute(
        select(Registration, Activity)
        .join(Activity, Activity.id == Registration.activity_id)
        .where(Registration.user_id == current_user.id)
        .order_by(Registration.updated_at.desc())
    ).all()
    return [
        MyRegistration(
            activity_id=reg.activity_id,
            activity_title=activity.title,
            activity_status=activity.status,
            event_start_at=activity.event_start_at,
            registration_status=reg.status,
            signed_at=reg.signed_at,
        )
        for reg, activity in rows
    ]


@router.get("/{activity_id}/status", response_model=RegistrationStatusInfo, summary="我在某活动的报名状态")
def my_status(
    activity_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    reg = db.scalar(
        select(Registration).where(
            Registration.activity_id == activity_id,
            Registration.user_id == current_user.id,
        )
    )
    if reg is None:
        return RegistrationStatusInfo(activity_id=activity_id, status=None, signed_at=None)
    return RegistrationStatusInfo(
        activity_id=activity_id,
        status=RegistrationStatus(reg.status),
        signed_at=reg.signed_at,
    )


@router.get("/activity/{activity_id}", response_model=list[RegistrationAdminListItem], summary="管理员查看某活动报名明细")
def activity_registrations(
    activity_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    activity = db.get(Activity, activity_id)
    if activity is None:
        raise HTTPException(status_code=404, detail="活动不存在")
    ensure_owner(activity, admin.id)

    rows = db.execute(
        select(Registration, User)
        .join(User, User.id == Registration.user_id)
        .where(Registration.activity_id == activity_id)
        .order_by(Registration.signed_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return [
        RegistrationAdminListItem(
            id=reg.id,
            user_id=reg.user_id,
            username=user.username,
            nickname=user.nickname,
            status=reg.status,
            signed_at=reg.signed_at,
            canceled_at=reg.canceled_at,
        )
        for reg, user in rows
    ]
