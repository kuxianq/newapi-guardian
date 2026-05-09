"""NewAPI 运行版本与健康信息检测。

只做只读探测；版本字段取不到时返回 unknown，不猜测。
"""
from __future__ import annotations

from typing import Any

from core.http_client import call_api

NEWAPI_GITHUB_URL = "https://github.com/Calcium-Ion/new-api"
NEWAPI_DOCS_URL = "https://docs.newapi.pro"

VERSION_ENDPOINTS = (
    "/api/status",
    "/api/about",
    "/api/system",
    "/api/option",
)

VERSION_KEYS = (
    "version",
    "Version",
    "build_version",
    "commit",
    "git_commit",
    "buildTime",
    "build_time",
)


def _redact_payload(value: Any, depth: int = 0) -> Any:
    if depth > 3:
        return "..."
    if isinstance(value, dict):
        safe = {}
        for key, item in value.items():
            key_lower = str(key).lower()
            if any(word in key_lower for word in ("token", "key", "secret", "password", "authorization")):
                safe[key] = "[REDACTED]"
            else:
                safe[key] = _redact_payload(item, depth + 1)
        return safe
    if isinstance(value, list):
        return [_redact_payload(item, depth + 1) for item in value[:10]]
    text = str(value)
    return text[:300] if len(text) > 300 else value


def _find_version(payload: Any) -> str | None:
    if isinstance(payload, dict):
        for key in VERSION_KEYS:
            if payload.get(key):
                return str(payload[key])
        for item in payload.values():
            found = _find_version(item)
            if found:
                return found
    elif isinstance(payload, list):
        for item in payload:
            found = _find_version(item)
            if found:
                return found
    return None


def detect_newapi_version() -> dict[str, Any]:
    attempts = []
    for endpoint in VERSION_ENDPOINTS:
        result = call_api("GET", endpoint)
        safe_result = {
            "endpoint": endpoint,
            "success": bool(result.get("success")),
            "status_code": result.get("status_code"),
            "error": result.get("error"),
        }
        if result.get("success"):
            payload = _redact_payload(result.get("data"))
            version = _find_version(payload)
            safe_result["sample"] = payload
            attempts.append(safe_result)
            if version:
                return {
                    "success": True,
                    "version": version,
                    "source": f"api:{endpoint}",
                    "github": NEWAPI_GITHUB_URL,
                    "docs": NEWAPI_DOCS_URL,
                    "attempts": attempts,
                }
        else:
            attempts.append(safe_result)

    return {
        "success": False,
        "version": "unknown",
        "source": "unknown",
        "github": NEWAPI_GITHUB_URL,
        "docs": NEWAPI_DOCS_URL,
        "message": "当前 NewAPI 实例未暴露可识别版本字段，或相关只读端点不可用。",
        "attempts": attempts,
    }
