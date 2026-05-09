"""NewAPI 错误归因规则。"""
from __future__ import annotations

ERROR_RULES = [
    ("prepay_failed", ("预扣费", "prepay"), "预扣费额度失败"),
    ("balance_insufficient", ("insufficient", "余额", "quota", "balance", "credit", "billing", "depleted", "not enough"), "余额或额度不足"),
    ("rate_limited", ("429", "rate limit", "too many requests"), "请求频率受限"),
    ("timeout", ("timeout", "timed out", "deadline"), "请求超时"),
    ("empty_response", ("empty", "no response", "blank"), "上游空响应"),
    ("upstream_400", ("400", "invalid request", "bad request"), "上游 400 / 请求参数问题"),
    ("upstream_403", ("403", "forbidden", "unauthorized"), "上游 403 / 鉴权或额度问题"),
    ("server_error", ("500", "502", "503", "504", "524"), "上游服务错误"),
    ("model_unsupported", ("model", "not support", "unsupported", "not found"), "模型不支持或路由异常"),
]


def classify_error(content: str | None) -> dict[str, str]:
    text = (content or "").lower()
    for error_type, needles, label in ERROR_RULES:
        if any(needle.lower() in text for needle in needles):
            return {"type": error_type, "label": label}
    return {"type": "unknown", "label": "未知错误"}
