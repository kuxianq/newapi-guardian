"""Usage summary helpers for NewAPI Guardian.

Deterministic usage statistics keep the Agent from guessing SQL for common
questions like "how many tokens have we used in total?".
"""
from __future__ import annotations

from typing import Any

from core.database import query

VALID_SCOPES = {"today", "yesterday", "all", "last_hours"}
VALID_GROUPS = {"none", "model", "user", "token"}


def _scope_where(scope: str, hours: int | None = None) -> tuple[str, tuple[Any, ...], str]:
    scope = scope or "today"
    if scope not in VALID_SCOPES:
        scope = "today"

    if scope == "today":
        return "type = 2 AND created_at > UNIX_TIMESTAMP(CURDATE())", (), "today"
    if scope == "yesterday":
        return (
            "type = 2 AND created_at >= UNIX_TIMESTAMP(CURDATE() - INTERVAL 1 DAY) "
            "AND created_at < UNIX_TIMESTAMP(CURDATE())",
            (),
            "yesterday",
        )
    if scope == "last_hours":
        safe_hours = max(1, min(int(hours or 24), 24 * 365))
        return (
            "type = 2 AND created_at > UNIX_TIMESTAMP(NOW() - INTERVAL %s HOUR)",
            (safe_hours,),
            f"last_{safe_hours}_hours",
        )
    return "type = 2", (), "all"


def _safe_limit(limit: int | None) -> int:
    try:
        return max(1, min(int(limit or 10), 50))
    except Exception:
        return 10


def get_usage_summary(
    *,
    scope: str = "today",
    hours: int | None = None,
    group_by: str = "none",
    limit: int = 10,
) -> dict[str, Any]:
    """Return token/quota usage summary.

    scope:
        today | yesterday | all | last_hours
    group_by:
        none | model | user | token
    """
    where, args, normalized_scope = _scope_where(scope, hours)
    group_by = group_by if group_by in VALID_GROUPS else "none"
    limit = _safe_limit(limit)

    total_rows = query(
        "SELECT COUNT(*) AS total_calls, "
        "COALESCE(SUM(prompt_tokens),0) AS total_prompt_tokens, "
        "COALESCE(SUM(completion_tokens),0) AS total_completion_tokens, "
        "COALESCE(SUM(prompt_tokens + completion_tokens),0) AS total_tokens, "
        "COALESCE(SUM(quota),0) AS total_quota, "
        "COALESCE(AVG(use_time),0) AS avg_time "
        f"FROM logs WHERE {where}",
        args,
    )
    totals = total_rows[0] if total_rows else {}

    groups: list[dict[str, Any]] = []
    group_label = None
    if group_by != "none":
        column_map = {
            "model": "model_name",
            "user": "username",
            "token": "token_name",
        }
        column = column_map[group_by]
        group_label = column
        groups = query(
            f"SELECT COALESCE({column}, '未知') AS name, "
            "COUNT(*) AS calls, "
            "COALESCE(SUM(prompt_tokens),0) AS prompt_tokens, "
            "COALESCE(SUM(completion_tokens),0) AS completion_tokens, "
            "COALESCE(SUM(prompt_tokens + completion_tokens),0) AS total_tokens, "
            "COALESCE(SUM(quota),0) AS quota, "
            "COALESCE(AVG(use_time),0) AS avg_time "
            f"FROM logs WHERE {where} "
            f"GROUP BY {column} "
            "ORDER BY total_tokens DESC LIMIT %s",
            args + (limit,),
        )

    return {
        "success": True,
        "scope": normalized_scope,
        "group_by": group_by,
        "group_label": group_label,
        "limit": limit,
        "totals": totals,
        "groups": groups,
    }
