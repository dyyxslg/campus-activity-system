"""用户相关请求 / 响应模型。"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import UserRole


class UserRegister(BaseModel):
    username: str = Field(min_length=3, max_length=50, description="用户名")
    password: str = Field(min_length=6, max_length=64, description="密码")
    nickname: str = Field(default="", max_length=50)


class UserLogin(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    nickname: str
    role: str
    is_active: bool = True
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut


# ---------- 管理员账号管理 ----------

class UserCreate(BaseModel):
    """管理员创建账号，可指定角色。"""
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=6, max_length=64)
    nickname: str = Field(default="", max_length=50)
    role: UserRole = UserRole.STUDENT


class UserUpdateActive(BaseModel):
    """启用 / 禁用账号。"""
    is_active: bool


class UserResetPassword(BaseModel):
    """重置密码（管理员代改）。"""
    new_password: str = Field(min_length=6, max_length=64)


class UserPageResult(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[UserOut]
