"""Diagnose / NewAPI docs callback handlers."""
from __future__ import annotations

from core.diagnostics import diagnose_failure_scope
from menus import back_btn, diagnose_menu_kb, newapi_docs_menu_kb
from tools_new.formatter import format_tool_output


def handle_diagnose_callback(data: str) -> tuple[str, object] | None:
    """Return (text, markup) for diagnose/docs callbacks, or None."""
    if data.startswith("diagnose_model:"):
        model = data.split(":", 1)[1]
        raw = diagnose_failure_scope(model=model, minutes=60, include_recent=True)
        return format_tool_output("diagnose_newapi_failure", raw), back_btn("menu_diagnose")

    if data == "diagnose_balance":
        raw = diagnose_failure_scope(minutes=120, include_recent=True)
        return format_tool_output("diagnose_newapi_failure", raw), back_btn("menu_diagnose")

    if data == "diagnose_model_prompt":
        return (
            "🧩 *按模型诊断*\n\n请发送：\n`/diagnose gpt-5.5`\n`/diagnose claude-opus-4-7`\n\n也可以指定时间：\n`/diagnose gpt-5.5 90`",
            diagnose_menu_kb(),
        )

    if data == "diagnose_channel_prompt":
        return (
            "🔌 *按渠道诊断*\n\n请发送：\n`/diagnose 266`\n\n也可以指定时间：\n`/diagnose 266 90`",
            diagnose_menu_kb(),
        )

    if data == "newapi_docs_menu":
        return (
            "📚 *NewAPI 文档参考*\n\n选择一个主题查看。真实状态仍以当前实例数据库 / API 为准。",
            newapi_docs_menu_kb(),
        )

    if data.startswith("newapi_docs:"):
        from skills.newapi import get_newapi_docs
        topic = data.split(":", 1)[1]
        return format_tool_output("get_newapi_docs", get_newapi_docs(topic)), back_btn("newapi_docs_menu")

    return None
