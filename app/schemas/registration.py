"""报名相关请求 / 响应模型。"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import RegistrationStatus


class RegistrationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    activity_id: int
    user_id: int
    status: str
    signed_at: datetime
    canceled_at: datetime | None = None


class RegistrationStatusInfo(BaseModel):
    """给学生的个人报名状态。"""
    activity_id: int
    status: RegistrationStatus | None = None  # None = 从未报名
    signed_at: datetime | None = None


class SignupResult(BaseModel):
    activity_id: int
    user_id: int
    status: str
    signed_count: int  # 报名成功后的最新已报名人数
    message: str = ""


class MyRegistration(BaseModel):
    """我的报名记录（含活动信息，供列表展示）。"""
    activity_id: int
    activity_title: str
    activity_status: str
    event_start_at: datetime
    registration_status: str
    signed_at: datetime


class RegistrationAdminListItem(BaseModel):
    """管理员查看某活动的报名明细。"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    username: str
    nickname: str
    status: str
    signed_at: datetime
    canceled_at: datetime | None = None


class RegistrationOverviewItem(BaseModel):
    """跨活动报名记录（供管理端「全部报名」页）。"""
    id: int
    activity_id: int
    activity_title: str
    user_id: int
    username: str
    nickname: str
    status: str
    signed_at: datetime
    canceled_at: datetime | None = None


class RegistrationPageResult(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[RegistrationOverviewItem]
