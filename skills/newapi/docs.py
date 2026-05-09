"""NewAPI 文档 Skill。

提供轻量官方入口和常用排查参考。真实运行状态仍以当前实例数据库/API 为准。
"""
from __future__ import annotations

NEWAPI_GITHUB_URL = "https://github.com/Calcium-Ion/new-api"
NEWAPI_DOCS_URL = "https://docs.newapi.pro"

DOC_TOPICS = {
    "channels": {
        "title": "渠道 / Channel",
        "notes": [
            "渠道状态、模型列表、优先级、权重和自动禁用会影响路由。",
            "排查单模型失败时，优先看该模型可用渠道、近期失败日志和渠道状态。",
        ],
    },
    "logs": {
        "title": "日志 / Logs",
        "notes": [
            "日志可用于定位 channel_id、model_name、错误内容、耗时和消费情况。",
            "部分 relay 失败可能不在普通使用日志里完整展示，需要结合服务日志或数据库字段判断。",
        ],
    },
    "quota": {
        "title": "额度 / Quota",
        "notes": [
            "余额不足、预扣费失败、quota/balance/insufficient 一类错误通常指向账号或钱包额度问题。",
            "模型上下文越大，预扣费额度需求越高，可能触发 fallback。",
        ],
    },
    "models": {
        "title": "模型 / Models",
        "notes": [
            "模型路由取决于渠道支持的 models 字段、分组、优先级和渠道状态。",
            "模型不支持、参数不兼容、上游 400 通常需要检查渠道模型映射和请求转换。",
        ],
    },
    "api": {
        "title": "管理 API / API",
        "notes": [
            "只读查询优先使用 GET；启用、禁用、更新渠道属于修改动作，需要确认。",
            "不确定接口行为时先查看官方文档和当前实例响应，不要猜测字段。",
        ],
    },
}


def get_newapi_docs(topic: str | None = None) -> dict:
    topic_key = (topic or "").strip().lower()
    if topic_key and topic_key in DOC_TOPICS:
        topics = {topic_key: DOC_TOPICS[topic_key]}
    else:
        topics = DOC_TOPICS
    return {
        "success": True,
        "github": NEWAPI_GITHUB_URL,
        "docs": NEWAPI_DOCS_URL,
        "topic": topic_key or "all",
        "topics": topics,
    }
