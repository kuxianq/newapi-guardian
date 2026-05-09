"""NewAPI 故障诊断核心。

只做只读数据聚合与归因，不包含 Telegram UI，不执行任何管理动作。
"""
from __future__ import annotations

from typing import Any

from core.database import query
from core.error_classifier import ERROR_RULES, classify_error
from core.log_diagnostics import collect_runtime_failures

FAILURE_KEYWORDS = (
    "insufficient",
    "余额",
    "quota",
    "balance",
    "credit",
    "billing",
    "depleted",
    "not enough",
    "预扣费",
    "error",
    "failed",
    "timeout",
    "empty",
    "invalid request",
    "rate limit",
    "429",
    "400",
    "403",
    "500",
    "502",
    "503",
    "504",
    "524",
)


def _clamp_minutes(minutes: int, default: int = 60) -> int:
    try:
        value = int(minutes)
    except Exception:
        value = default
    return max(1, min(value, 7 * 24 * 60))


def _is_failure_clause(alias: str = "l") -> str:
    parts = [f"{alias}.type != 2"]
    for keyword in FAILURE_KEYWORDS:
        parts.append(f"LOWER({alias}.content) LIKE LOWER('%%{keyword}%%')")
    return "(" + " OR ".join(parts) + ")"



def _row_error_text(row: dict[str, Any]) -> str | None:
    return row.get("content") or row.get("sample_error")


def _summarize_error_types(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    bucket: dict[str, dict[str, Any]] = {}
    for row in rows:
        classified = classify_error(_row_error_text(row))
        item = bucket.setdefault(classified["type"], {**classified, "count": 0})
        item["count"] += int(row.get("fail_count") or 1)
    return sorted(bucket.values(), key=lambda item: item["count"], reverse=True)


def diagnose_failure_scope(
    model: str | None = None,
    channel_id: int | None = None,
    minutes: int = 60,
    include_recent: bool = True,
) -> dict[str, Any]:
    """按模型 / 渠道 / 时间窗口诊断失败范围。"""
    minutes = _clamp_minutes(minutes)
    where = ["l.created_at > UNIX_TIMESTAMP(NOW() - INTERVAL %s MINUTE)"]
    params: list[Any] = [minutes]

    if model:
        where.append("l.model_name = %s")
        params.append(model)
    if channel_id is not None:
        where.append("l.channel_id = %s")
        params.append(int(channel_id))

    where_sql = " AND ".join(where)
    failure_clause = _is_failure_clause("l")

    summary_rows = query(
        f"""
        SELECT
          COUNT(*) AS total_count,
          SUM(CASE WHEN {failure_clause} THEN 1 ELSE 0 END) AS fail_count,
          SUM(CASE WHEN NOT {failure_clause} THEN 1 ELSE 0 END) AS success_count,
          AVG(l.use_time) AS avg_time,
          MAX(CASE WHEN {failure_clause} THEN l.created_at ELSE NULL END) AS last_fail_time
        FROM logs l
        WHERE {where_sql}
        """,
        params,
    )
    summary = summary_rows[0] if summary_rows else {}
    total = int(summary.get("total_count") or 0)
    failed = int(summary.get("fail_count") or 0)
    success = int(summary.get("success_count") or 0)
    summary = {
        "total": total,
        "success": success,
        "failed": failed,
        "fail_rate": round(failed / total, 4) if total else 0,
        "avg_time": summary.get("avg_time"),
        "last_fail_time": summary.get("last_fail_time"),
    }

    channel_rows = query(
        f"""
        SELECT
          l.channel_id,
          COALESCE(c.name, l.channel_name, CONCAT('ID:', l.channel_id)) AS channel_name,
          c.status,
          c.models,
          COUNT(*) AS fail_count,
          GROUP_CONCAT(DISTINCT l.model_name ORDER BY l.model_name SEPARATOR ', ') AS models_seen,
          MAX(l.created_at) AS last_fail_time,
          LEFT(MAX(l.content), 300) AS sample_error
        FROM logs l
        LEFT JOIN channels c ON c.id = l.channel_id
        WHERE {where_sql} AND {failure_clause}
        GROUP BY l.channel_id, channel_name, c.status, c.models
        ORDER BY fail_count DESC, last_fail_time DESC
        LIMIT 20
        """,
        params,
    )

    model_rows = query(
        f"""
        SELECT
          l.model_name,
          COUNT(*) AS fail_count,
          GROUP_CONCAT(DISTINCT l.channel_id ORDER BY l.channel_id SEPARATOR ', ') AS channel_ids,
          MAX(l.created_at) AS last_fail_time,
          LEFT(MAX(l.content), 300) AS sample_error
        FROM logs l
        WHERE {where_sql} AND {failure_clause}
        GROUP BY l.model_name
        ORDER BY fail_count DESC, last_fail_time DESC
        LIMIT 20
        """,
        params,
    )

    balance_rows = query(
        f"""
        SELECT
          l.channel_id,
          COALESCE(c.name, l.channel_name, CONCAT('ID:', l.channel_id)) AS channel_name,
          c.status,
          COUNT(*) AS fail_count,
          GROUP_CONCAT(DISTINCT l.model_name ORDER BY l.model_name SEPARATOR ', ') AS models_seen,
          MAX(l.created_at) AS last_fail_time,
          LEFT(MAX(l.content), 300) AS sample_error
        FROM logs l
        LEFT JOIN channels c ON c.id = l.channel_id
        WHERE {where_sql}
          AND (LOWER(l.content) LIKE '%%insufficient%%'
               OR l.content LIKE '%%余额%%'
               OR LOWER(l.content) LIKE '%%quota%%'
               OR LOWER(l.content) LIKE '%%balance%%'
               OR LOWER(l.content) LIKE '%%credit%%'
               OR LOWER(l.content) LIKE '%%billing%%'
               OR l.content LIKE '%%预扣费%%')
        GROUP BY l.channel_id, channel_name, c.status
        ORDER BY fail_count DESC, last_fail_time DESC
        LIMIT 20
        """,
        params,
    )

    recent_failures = []
    if include_recent:
        recent_failures = query(
            f"""
            SELECT
              l.id,
              l.created_at,
              l.channel_id,
              COALESCE(c.name, l.channel_name, CONCAT('ID:', l.channel_id)) AS channel_name,
              l.model_name,
              l.type,
              l.use_time,
              LEFT(l.content, 300) AS content
            FROM logs l
            LEFT JOIN channels c ON c.id = l.channel_id
            WHERE {where_sql} AND {failure_clause}
            ORDER BY l.id DESC
            LIMIT 10
            """,
            params,
        )

    for row in channel_rows:
        row["error_type"] = classify_error(row.get("sample_error"))
    for row in model_rows:
        row["error_type"] = classify_error(row.get("sample_error"))
    for row in balance_rows:
        row["error_type"] = classify_error(row.get("sample_error"))
    for row in recent_failures:
        row["error_type"] = classify_error(row.get("content"))

    hypotheses = []
    if balance_rows:
        top = balance_rows[0]
        hypotheses.append({
            "type": "balance_or_prepay",
            "confidence": "high",
            "reason": f"近 {minutes} 分钟余额/预扣费相关失败最多的是渠道 #{top.get('channel_id')}",
            "channel_id": top.get("channel_id"),
        })
    if channel_rows:
        top = channel_rows[0]
        hypotheses.append({
            "type": top.get("error_type", {}).get("type", "unknown"),
            "confidence": "medium" if not balance_rows else "high",
            "reason": f"失败聚合 Top 渠道为 #{top.get('channel_id')}，失败 {top.get('fail_count')} 次",
            "channel_id": top.get("channel_id"),
        })

    runtime_failures = collect_runtime_failures(model=model, channel_id=channel_id, minutes=minutes)

    return {
        "success": True,
        "scope": {"model": model, "channel_id": channel_id, "minutes": minutes},
        "summary": summary,
        "channels": channel_rows,
        "models": model_rows,
        "balance_suspects": balance_rows,
        "recent_failures": recent_failures,
        "runtime_failures": runtime_failures,
        "error_types": _summarize_error_types(channel_rows),
        "hypothesis": hypotheses,
    }


def diagnose_model(model: str, minutes: int = 60) -> dict[str, Any]:
    return diagnose_failure_scope(model=model, minutes=minutes)


def diagnose_channel(channel_id: int, minutes: int = 60) -> dict[str, Any]:
    return diagnose_failure_scope(channel_id=channel_id, minutes=minutes)


def diagnose_balance(minutes: int = 120, channel_id: int | None = None) -> dict[str, Any]:
    return diagnose_failure_scope(channel_id=channel_id, minutes=minutes)
