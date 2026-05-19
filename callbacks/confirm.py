"""Confirmation callback handlers for mutating inline actions."""
from __future__ import annotations

from typing import Awaitable, Callable

from telegram.ext import ContextTypes

from backup import restore_backup
from formatter import safe_text
from handlers.memory import (
    compact_all_memories,
    format_memory_compact_result,
    pop_valid_pending_memory_compact,
)
from tg_safe import safe_edit

ParseTimedCallback = Callable[[str, str], tuple[bool, str]]
PopPendingRestore = Callable[[ContextTypes.DEFAULT_TYPE, str], str | None]
ExecuteBatchStatus = Callable[[object, list[int], int, bool], Awaitable[None]]


def _parse_ids(payload: str) -> list[int]:
    return [int(x) for x in payload.split(",") if x]


async def handle_confirm_callback(
    q,
    context: ContextTypes.DEFAULT_TYPE,
    data: str,
    *,
    parse_timed_callback: ParseTimedCallback,
    execute_batch_status: ExecuteBatchStatus,
    pop_valid_pending_restore: PopPendingRestore,
) -> tuple[str | None, bool]:
    """Handle confirmation callbacks.

    Returns (text, handled). Some branches edit/execute and return (None, True)
    to signal that the caller should stop without a final safe_edit.
    """
    if data.startswith("confirm_enable"):
        valid, payload = parse_timed_callback(data, "confirm_enable")
        if not valid:
            return "❌ 启用确认已过期，请重新执行 /enable。", True
        await execute_batch_status(q, _parse_ids(payload), 1, True)
        return None, True

    if data.startswith("confirm_disable_failed"):
        valid, payload = parse_timed_callback(data, "confirm_disable_failed")
        if not valid:
            return "❌ 一键禁用确认已过期，请重新执行 /disable_failed。", True
        threshold_str, ids_str = payload.split("_", 1)
        int(threshold_str)  # validate callback shape; ids carry the actual operation target
        await execute_batch_status(q, _parse_ids(ids_str), 2, True)
        return None, True

    if data.startswith("confirm_disable"):
        valid, payload = parse_timed_callback(data, "confirm_disable")
        if not valid:
            return "❌ 禁用确认已过期，请重新执行 /disable。", True
        await execute_batch_status(q, _parse_ids(payload), 2, True)
        return None, True

    if data.startswith("confirm_restore:"):
        restore_id = data.removeprefix("confirm_restore:")
        filename = pop_valid_pending_restore(context, restore_id)
        if not filename:
            return "❌ 恢复确认已过期或备份文件无效，请重新执行 /restore。", True
        await safe_edit(q, f"♻️ 正在恢复 `{safe_text(filename)}`...\n恢复前会自动备份当前状态。")
        ok, info = restore_backup(filename)
        return (f"✅ {info}" if ok else f"❌ {info}"), True

    if data.startswith("confirm_memory_compact:"):
        compact_id = data.removeprefix("confirm_memory_compact:")
        keep_recent_facts = pop_valid_pending_memory_compact(context, compact_id)
        if keep_recent_facts is None:
            return "❌ 记忆整理确认已过期或无效，请重新执行 /memory_compact apply。", True
        await safe_edit(q, "🧹 正在整理 Agent 记忆...\n会先备份再写入。")
        result = compact_all_memories(dry_run=False, keep_recent_facts=keep_recent_facts)
        return format_memory_compact_result(result) + "\n\n✅ 已先备份再整理。", True

    return None, False
