"""业务枚举：活动状态 / 报名状态 / 异步任务状态 / 用户角色。"""
from enum import Enum


class ActivityStatus(str, Enum):
    """活动生命周期状态机。"""
    DRAFT = "DRAFT"        # 草稿
    OPEN = "OPEN"          # 报名开放中
    CLOSED = "CLOSED"      # 报名截止
    FINISHED = "FINISHED"  # 活动结束


# 合法的状态迁移表（模块级常量，避免 (str, Enum) 把 dict 误捕获为枚举成员）
ACTIVITY_TRANSITIONS: dict[ActivityStatus, set[ActivityStatus]] = {
    ActivityStatus.DRAFT: {ActivityStatus.OPEN},                 # 草稿 -> 上架
    ActivityStatus.OPEN: {ActivityStatus.CLOSED, ActivityStatus.FINISHED},  # 开放中 -> 关闭/结束
    ActivityStatus.CLOSED: {ActivityStatus.OPEN, ActivityStatus.FINISHED},  # 已关闭 -> 重新开放/结束
    ActivityStatus.FINISHED: set(),                              # 终态，不可再流转
}


class RegistrationStatus(str, Enum):
    SIGNED = "SIGNED"      # 已报名
    CANCELED = "CANCELED"  # 已取消


class TaskStatus(str, Enum):
    """异步导出任务状态机。"""
    PENDING = "PENDING"            # 排队中
    RUNNING = "RUNNING"            # 运行中
    SUCCESS = "SUCCESS"            # 成功
    PARTIAL_FAIL = "PARTIAL_FAIL"  # 部分失败（个别脏数据不影响整体）
    FAILED = "FAILED"              # 失败
    CANCELED = "CANCELED"          # 已取消


class TaskType(str, Enum):
    REPORT = "REPORT"        # 报名报表导出
    AI_ANALYSIS = "AI_ANALYSIS"  # AI 数据分析


class UserRole(str, Enum):
    STUDENT = "student"  # 普通学生
    ADMIN = "admin"      # 管理员（可创建/管理活动）
