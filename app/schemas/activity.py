"""活动相关请求 / 响应模型。"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import ActivityStatus


class ActivityCreate(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    description: str = ""
    max_participants: int = Field(gt=0, le=100000)
    signup_start_at: datetime
    signup_end_at: datetime
    event_start_at: datetime
    event_end_at: datetime

    @model_validator(mode="after")
    def check_time_order(self) -> "ActivityCreate":
        if self.signup_start_at >= self.signup_end_at:
            raise ValueError("报名开始时间必须早于报名截止时间")
        if self.signup_end_at > self.event_start_at:
            raise ValueError("报名截止时间应早于活动开始时间")
        if self.event_start_at >= self.event_end_at:
            raise ValueError("活动开始时间必须早于活动结束时间")
        return self


class ActivityUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None
    max_participants: int | None = Field(default=None, gt=0, le=100000)
    signup_start_at: datetime | None = None
    signup_end_at: datetime | None = None
    event_start_at: datetime | None = None
    event_end_at: datetime | None = None


class ActivityStatusChange(BaseModel):
    target_status: ActivityStatus


class ActivityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str
    max_participants: int
    signup_start_at: datetime
    signup_end_at: datetime
    event_start_at: datetime
    event_end_at: datetime
    status: str
    creator_id: int
    created_at: datetime
    updated_at: datetime
    # 动态注入：当前报名人数
    signed_count: int = 0


class ActivityListItem(BaseModel):
    """列表项：不含大字段 description，降低传输成本。"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    max_participants: int
    signup_start_at: datetime
    signup_end_at: datetime
    event_start_at: datetime
    event_end_at: datetime
    status: str
    signed_count: int = 0


class PageResult(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[ActivityListItem]
