"""工具输出格式化。

把 executor 的执行路由和展示逻辑分开，避免工具越来越多时 executor 膨胀。
"""
from __future__ import annotations

import json
from typing import Any

from core.formatter import format_kv, format_list, format_table, truncate


def format_tool_output(tool_name: str, raw: dict[str, Any]) -> str:
    if not raw.get("success"):
        return f"❌ {raw.get('error', '执行失败')}"

    if tool_name == "query_database":
        return _format_query_database(raw)
    if tool_name == "diagnose_newapi_failure":
        return _format_diagnose_newapi_failure(raw)
    if tool_name == "get_newapi_runtime_info":
        return _format_newapi_runtime_info(raw)
    if tool_name == "get_newapi_docs":
        return _format_newapi_docs(raw)
    if tool_name == "call_api":
        return _format_call_api(raw)

    return truncate(json.dumps(raw, ensure_ascii=False, indent=2), 2000)


def _format_query_database(raw: dict[str, Any]) -> str:
    rows = raw.get("data") or []
    if not rows:
        return "✅ 查询成功，但没有返回数据。"

    table = format_table(rows, max_width=40)
    if raw.get("limited"):
        suffix = f"⚠️ 结果已按安全上限截断，当前返回 {raw.get('row_count', len(rows))} 行"
    else:
        suffix = f"✅ 查询成功，共返回 {raw.get('row_count', len(rows))} 行"
    return table + "\n\n" + suffix


def _most_suspicious_channel(raw: dict[str, Any]) -> dict[str, Any] | None:
    runtime = raw.get("runtime_failures") or {}
    newapi_events = runtime.get("newapi_events") or []
    if newapi_events:
        return newapi_events[-1]
    balance = raw.get("balance_suspects") or []
    if balance:
        return balance[0]
    channels = raw.get("channels") or []
    return channels[0] if channels else None


def _format_diagnose_newapi_failure(raw: dict[str, Any]) -> str:
    scope = raw.get("scope", {})
    summary = raw.get("summary", {})
    suspect = _most_suspicious_channel(raw)
    parts = [
        "🔎 NewAPI 故障诊断",
        f"范围: model={scope.get('model') or '全部'} channel={scope.get('channel_id') or '全部'} 最近 {scope.get('minutes')} 分钟",
        f"总请求: {summary.get('total', 0)} | 失败: {summary.get('failed', 0)} | 失败率: {float(summary.get('fail_rate') or 0) * 100:.1f}%",
    ]
    if suspect:
        et = suspect.get("error_type", {})
        parts.append(
            f"\n最可疑渠道: #{suspect.get('channel_id')} "
            f"{truncate(str(suspect.get('channel_name') or ''), 36)}｜{et.get('label', '未知错误')}"
        )

    channels = raw.get("channels") or []
    if channels:
        parts.append("\nTop 失败渠道:")
        for row in channels[:5]:
            et = row.get("error_type", {})
            parts.append(
                f"- #{row.get('channel_id')} {truncate(str(row.get('channel_name') or ''), 36)} "
                f"失败 {row.get('fail_count')} 次｜{et.get('label', '未知错误')}"
            )

    balance = raw.get("balance_suspects") or []
    if balance:
        parts.append("\n余额/预扣费疑似:")
        for row in balance[:3]:
            parts.append(f"- #{row.get('channel_id')} {truncate(str(row.get('channel_name') or ''), 36)} 失败 {row.get('fail_count')} 次")

    recent = raw.get("recent_failures") or []
    if recent:
        parts.append("\n最近失败样本:")
        for row in recent[:3]:
            et = row.get("error_type", {})
            parts.append(
                f"- #{row.get('channel_id')} {row.get('model_name') or ''}｜{et.get('label', '未知错误')}｜"
                f"{truncate(str(row.get('content') or ''), 80)}"
            )

    runtime = raw.get("runtime_failures") or {}
    newapi_events = runtime.get("newapi_events") or []
    openclaw_events = runtime.get("openclaw_events") or []
    if newapi_events:
        parts.append("\n运行日志定位:")
        for row in newapi_events[-5:]:
            et = row.get("error_type", {})
            parts.append(
                f"- NewAPI #{row.get('channel_id')} {row.get('model_name') or ''}｜HTTP {row.get('status_code')}｜"
                f"{et.get('label', '未知错误')}｜{truncate(str(row.get('content') or ''), 80)}"
            )
    if openclaw_events:
        parts.append("\nOpenClaw fallback:")
        for row in openclaw_events[-3:]:
            et = row.get("error_type", {})
            parts.append(
                f"- {row.get('failed_model') or row.get('requested_model') or ''}｜"
                f"{et.get('label', '未知错误')}｜{truncate(str(row.get('content') or ''), 80)}"
            )

    hypo = raw.get("hypothesis") or []
    if hypo:
        parts.append("\n建议判断:")
        for item in hypo[:3]:
            parts.append(f"- {item.get('reason')}")

    return "\n".join(parts)


def _format_newapi_runtime_info(raw: dict[str, Any]) -> str:
    parts = ["ℹ️ NewAPI 运行信息"]
    parts.append(f"版本: {raw.get('version', 'unknown')}")
    parts.append(f"来源: {raw.get('source', 'unknown')}")
    parts.append(f"GitHub: {raw.get('github')}")
    parts.append(f"Docs: {raw.get('docs')}")
    if raw.get("message"):
        parts.append(str(raw.get("message")))
    return "\n".join(parts)


def _format_newapi_docs(raw: dict[str, Any]) -> str:
    parts = ["📚 NewAPI 文档参考", f"GitHub: {raw.get('github')}", f"Docs: {raw.get('docs')}"]
    for key, item in (raw.get("topics") or {}).items():
        parts.append(f"\n{item.get('title', key)}")
        for note in item.get("notes", []):
            parts.append(f"- {note}")
    return "\n".join(parts)


def _format_call_api(raw: dict[str, Any]) -> str:
    parts = ["✅ API 调用完成"]
    if "status_code" in raw:
        parts.append(f"HTTP {raw['status_code']}")
    payload = raw.get("data")
    if isinstance(payload, dict):
        parts.append("")
        parts.append(format_kv(payload, title="返回数据"))
    elif isinstance(payload, list):
        parts.append("")
        parts.append(format_list(payload[:20]))
        if len(payload) > 20:
            parts.append(f"\n... 还有 {len(payload) - 20} 项")
    elif payload is not None:
        parts.append("")
        parts.append(truncate(json.dumps(payload, ensure_ascii=False), 1200))
    return "\n".join(parts)
