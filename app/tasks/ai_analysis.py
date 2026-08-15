"""AI 异步数据分析任务（可一键关闭）。

设计约束：
- settings.AI_ENABLE=false 时，提交接口直接拒绝，任务体内也做二次校验。
- 读取系统真实报名统计数据（app.services.ai_stats），调用 Deepseek 大模型做业务分析。
- 同样作为 Celery 异步任务，大模型响应慢不会阻塞 HTTP 接口。
- 大模型不可用时降级为「规则化摘要」，保证任务仍能落库，不成为硬依赖。
"""
import json
import logging

import httpx

from app.core.config import settings
from app.core.redis import get_redis
from app.db.session import SessionLocal
from app.models import Activity, AiAnalysisResult
from app.models.enums import TaskStatus
from app.services.ai_stats import collect_activity_stats
from app.services.task_service import update_progress
from app.tasks.celery_app import celery_app

logger = logging.getLogger("celery.task")

SYSTEM_PROMPT = (
    "你是一位校园社团运营数据分析师。请基于给定的活动报名统计数据，"
    "面向社团管理员输出 200-400 字的运营复盘与优化建议。要求："
    "1) 直接指出关键问题（如曝光不足、报名集中、参与群体特征等）；"
    "2) 给出 3-5 条可落地的改进建议；3) 语言简洁专业，不客套。"
)


def _call_deepseek(stats_json: dict, api_key: str, base_url: str, model: str) -> str:
    """调用 Deepseek 对话补全接口（OpenAI 兼容）。单独成函数便于测试替换。"""
    url = f"{base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(stats_json, ensure_ascii=False)},
        ],
        "temperature": 0.6,
        "max_tokens": 1000,
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    with httpx.Client(timeout=60) as client:
        resp = client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()


def _fallback_summary(stats: dict) -> str:
    """大模型不可用时降级：基于统计拼出规则化摘要，保证任务仍能完成。"""
    peak = "、".join(stats["peak_signup_hours"]) or "无明显高峰"
    return (
        f"【规则化摘要】活动《{stats['activity_title']}》共报名 {stats['total_signups']} 人，"
        f"取消 {stats['total_cancels']} 人（取消率 {stats['cancel_rate']:.1%}），"
        f"容量利用率 {stats['occupancy_rate']:.1%}。"
        f"报名高峰时段：{peak} 点。"
        f"（AI 分析不可用，已降级为统计摘要）"
    )


@celery_app.task(name="tasks.analyze_activity_ai", bind=True)
def analyze_activity_ai(self, task_record_id: int, activity_id: int) -> str:
    """异步 AI 数据分析：统计 -> 大模型 -> 结果落库。"""
    db = SessionLocal()
    client = get_redis()

    try:
        # 二次校验开关（提交接口已拦截，这里兜底）
        if not settings.AI_ENABLE:
            update_progress(
                client, db, task_record_id,
                status=TaskStatus.CANCELED.value, progress=100,
                error_message="AI 功能未启用（AI_ENABLE=false）",
            )
            return TaskStatus.CANCELED.value

        activity = db.get(Activity, activity_id)
        if activity is None:
            update_progress(
                client, db, task_record_id,
                status=TaskStatus.FAILED.value, progress=100, error_message="活动不存在",
            )
            return TaskStatus.FAILED.value

        update_progress(
            client, db, task_record_id,
            status=TaskStatus.RUNNING.value, progress=20,
        )

        stats = collect_activity_stats(db, activity)
        update_progress(client, db, task_record_id, status=TaskStatus.RUNNING.value, progress=50)

        try:
            report_text = _call_deepseek(
                stats,
                settings.DEEPSEEK_API_KEY,
                settings.DEEPSEEK_BASE_URL,
                settings.DEEPSEEK_MODEL,
            )
            used_model = settings.DEEPSEEK_MODEL
        except Exception as e:  # noqa: BLE001 大模型失败不阻塞系统
            logger.warning("Deepseek 调用失败，降级为规则摘要: %s", e)
            report_text = _fallback_summary(stats)
            used_model = "fallback"

        result = AiAnalysisResult(
            activity_id=activity_id,
            task_record_id=task_record_id,
            stats_json=stats,
            report=report_text,
            model=used_model,
            status="SUCCESS",
        )
        db.add(result)
        db.commit()

        update_progress(
            client, db, task_record_id,
            status=TaskStatus.SUCCESS.value, progress=100,
            error_message=("Deepseek 不可用，已降级" if used_model == "fallback" else None),
        )
        return TaskStatus.SUCCESS.value

    except Exception as e:  # noqa: BLE001
        try:
            update_progress(
                client, db, task_record_id,
                status=TaskStatus.FAILED.value, progress=100, error_message=str(e)[:1000],
            )
        finally:
            pass
        return TaskStatus.FAILED.value

    finally:
        db.close()
