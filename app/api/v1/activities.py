"""活动管理路由：管理员 CRUD + 状态流转，学生浏览公开活动。"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin, get_current_user
from app.db.session import get_db
from app.models import Activity, User
from app.models.enums import ActivityStatus
from app.schemas.activity import (
    ActivityCreate,
    ActivityListItem,
    ActivityOut,
    ActivityStatusChange,
    ActivityUpdate,
    PageResult,
)
from app.services.activity_service import (
    PUBLIC_STATUSES,
    batch_signed_counts,
    change_status,
    ensure_owner,
    signed_count_for,
    validate_time_order,
)

router = APIRouter(prefix="/activities", tags=["活动管理"])


def _load_owned(db: Session, activity_id: int, user: User) -> Activity:
    activity = db.get(Activity, activity_id)
    if activity is None:
        raise HTTPException(status_code=404, detail="活动不存在")
    ensure_owner(activity, user.id)
    return activity


@router.post(
    "",
    response_model=ActivityOut,
    status_code=status.HTTP_201_CREATED,
    summary="创建活动（管理员，默认草稿）",
)
def create_activity(
    body: ActivityCreate,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    activity = Activity(
        **body.model_dump(),
        status=ActivityStatus.DRAFT.value,
        creator_id=admin.id,
    )
    db.add(activity)
    db.commit()
    db.refresh(activity)
    result = ActivityOut.model_validate(activity)
    result.signed_count = 0
    return result


@router.get("", response_model=PageResult, summary="活动列表（分页/筛选）")
def list_activities(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    status_filter: str | None = Query(None, alias="status", description="DRAFT/OPEN/CLOSED/FINISHED"),
    keyword: str | None = Query(None, description="标题模糊搜索"),
    mine_only: bool = Query(False, description="只看自己创建的（需管理员）"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stmt = select(Activity)
    # 普通学生看不到草稿
    if status_filter == ActivityStatus.DRAFT.value:
        if current_user.role != "admin":
            raise HTTPException(status_code=403, detail="无权查看草稿")
    elif status_filter:
        stmt = stmt.where(Activity.status == status_filter)
    elif current_user.role != "admin":
        stmt = stmt.where(Activity.status.in_(PUBLIC_STATUSES))

    if mine_only:
        if current_user.role != "admin":
            raise HTTPException(status_code=403, detail="仅管理员可查看自己创建的活动")
        stmt = stmt.where(Activity.creator_id == current_user.id)

    if keyword:
        stmt = stmt.where(Activity.title.like(f"%{keyword}%"))

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(Activity.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()

    counts = batch_signed_counts(db, [a.id for a in rows])
    items = []
    for a in rows:
        item = ActivityListItem.model_validate(a)
        item.signed_count = counts.get(a.id, 0)
        items.append(item)
    return PageResult(total=total, page=page, page_size=page_size, items=items)


@router.get("/{activity_id}", response_model=ActivityOut, summary="活动详情")
def get_activity(
    activity_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    activity = db.get(Activity, activity_id)
    if activity is None:
        raise HTTPException(status_code=404, detail="活动不存在")
    # 草稿仅创建者可看
    if activity.status == ActivityStatus.DRAFT.value and activity.creator_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权查看该活动")
    result = ActivityOut.model_validate(activity)
    result.signed_count = signed_count_for(db, activity.id)
    return result


@router.put("/{activity_id}", response_model=ActivityOut, summary="编辑活动（仅创建者）")
def update_activity(
    activity_id: int,
    body: ActivityUpdate,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    activity = _load_owned(db, activity_id, admin)
    if activity.status == ActivityStatus.FINISHED.value:
        raise HTTPException(status_code=400, detail="活动已结束，不可编辑")

    data = body.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(activity, key, value)
    # 部分更新后，按合并结果校验时间顺序，避免写出 截止>开始 的脏数据
    validate_time_order(activity)
    db.commit()
    db.refresh(activity)
    result = ActivityOut.model_validate(activity)
    result.signed_count = signed_count_for(db, activity.id)
    return result


@router.post("/{activity_id}/status", response_model=ActivityOut, summary="活动状态流转（上架/关闭/结束）")
def transition_activity(
    activity_id: int,
    body: ActivityStatusChange,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    activity = _load_owned(db, activity_id, admin)
    activity = change_status(db, activity, body.target_status.value, admin.id)
    result = ActivityOut.model_validate(activity)
    result.signed_count = signed_count_for(db, activity.id)
    return result


@router.delete("/{activity_id}", status_code=status.HTTP_204_NO_CONTENT, summary="删除活动（仅草稿）")
def delete_activity(
    activity_id: int,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    activity = _load_owned(db, activity_id, admin)
    if activity.status != ActivityStatus.DRAFT.value:
        raise HTTPException(status_code=400, detail="仅草稿状态的活动可删除")
    db.delete(activity)
    db.commit()
