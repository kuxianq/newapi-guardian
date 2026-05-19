"""Usage summary Telegram command."""
from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from auth import authorized
from core.usage_summary import get_usage_summary
from menus import back_btn
from tg_safe import safe_reply
from tools_new.formatter import format_tool_output


def parse_usage_summary_args(args: list[str]) -> dict:
    scope = "today"
    hours = None
    group_by = "none"
    limit = 10
    idx = 0
    if args:
        first = args[0].lower()
        if first in {"today", "yesterday", "all"}:
            scope = first
            idx = 1
        elif first in {"last_hours", "last", "hours", "24h", "7d"}:
            scope = "last_hours"
            idx = 1
            if first == "24h":
                hours = 24
            elif first == "7d":
                hours = 24 * 7
            elif len(args) > idx:
                hours = int(args[idx])
                idx += 1
        elif first.endswith("h") and first[:-1].isdigit():
            scope = "last_hours"
            hours = int(first[:-1])
            idx = 1
        elif first.endswith("d") and first[:-1].isdigit():
            scope = "last_hours"
            hours = int(first[:-1]) * 24
            idx = 1
    if hours is None and scope == "last_hours":
        hours = 24
    if len(args) > idx:
        maybe_group = args[idx].lower()
        if maybe_group in {"none", "model", "user", "token"}:
            group_by = maybe_group
            idx += 1
    if len(args) > idx:
        limit = int(args[idx])
    return {"scope": scope, "hours": hours, "group_by": group_by, "limit": limit}


@authorized
async def cmd_usage_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Deterministic token/quota usage summary without invoking AI."""
    try:
        kwargs = parse_usage_summary_args(context.args or [])
    except ValueError:
        await safe_reply(
            update.message,
            "用法:\n`/usage_summary [today|yesterday|all|24h|7d|last_hours N] [none|model|user|token] [limit]`\n\n示例:\n`/usage_summary all`\n`/usage_summary 24h model`\n`/usage_summary all token 20`",
            reply_markup=back_btn(),
        )
        return
    raw = get_usage_summary(**kwargs)
    text = format_tool_output("get_usage_summary", raw)
    await safe_reply(update.message, text, reply_markup=back_btn())
