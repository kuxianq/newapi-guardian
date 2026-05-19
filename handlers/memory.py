"""Agent memory maintenance Telegram commands."""
from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from auth import authorized
from agent_memory_maintenance import compact_all_memories, get_memory_status
from formatter import safe_text
from menus import back_btn
from tg_safe import safe_reply

CONFIRM_EXPIRES_MINUTES = 10
PENDING_MEMORY_COMPACT_KEY = "pending_memory_compact"


def create_pending_memory_compact(context: ContextTypes.DEFAULT_TYPE, keep_recent_facts: int) -> str:
    compact_id = uuid4().hex[:12]
    pending = context.user_data.setdefault(PENDING_MEMORY_COMPACT_KEY, {})
    pending[compact_id] = {
        "keep_recent_facts": keep_recent_facts,
        "expires_at": (datetime.now() + timedelta(minutes=CONFIRM_EXPIRES_MINUTES)).isoformat(),
    }
    return compact_id


def pop_valid_pending_memory_compact(context: ContextTypes.DEFAULT_TYPE, compact_id: str) -> int | None:
    pending = context.user_data.get(PENDING_MEMORY_COMPACT_KEY, {})
    item = pending.pop(compact_id, None)
    if not isinstance(item, dict):
        return None
    try:
        expires_at = datetime.fromisoformat(item.get("expires_at", ""))
    except ValueError:
        return None
    if expires_at < datetime.now():
        return None
    try:
        keep_recent_facts = int(item.get("keep_recent_facts", 200))
    except Exception:
        return None
    return keep_recent_facts if keep_recent_facts >= 20 else None


def format_memory_status(status: dict) -> str:
    lines = [
        "🧠 *Agent 记忆状态*",
        "",
        f"目录: `{safe_text(status['memory_dir'])}`",
        f"文件数: `{status['file_count']}`",
        f"总大小: `{status['total_mb']} MB`",
    ]
    for item in status.get("files", []):
        counts = item.get("item_counts") or {}
        lines.extend([
            "",
            f"• `{safe_text(item['filename'])}` — `{item['size_mb']} MB`",
            f"  `short_term`: `{counts.get('short_term', 0)}` / `learned_facts`: `{counts.get('learned_facts', 0)}`",
            f"  `user_profile`: `{counts.get('user_profile', 0)}` / `knowledge_base`: `{counts.get('knowledge_base', 0)}` / `patterns`: `{counts.get('patterns', 0)}`",
        ])
        if item.get("parse_error"):
            lines.append(f"  ⚠️ `parse_error`: `{safe_text(item['parse_error'])}`")
    return "\n".join(lines)


def format_memory_compact_result(result: dict) -> str:
    lines = [
        "🧹 *Agent 记忆整理结果*",
        "",
        f"模式: `{'dry-run' if result.get('dry_run') else 'apply'}`",
        f"文件数: `{result.get('file_count', 0)}`",
        f"预计/实际节省: `{round(result.get('saved_bytes', 0) / 1024 / 1024, 3)} MB`",
    ]
    if result.get("backup_dir"):
        lines.append(f"备份: `{safe_text(result['backup_dir'])}`")
    for item in result.get("results", []):
        before = item.get("before_counts", {})
        after = item.get("after_counts", {})
        lines.extend([
            "",
            f"• `{safe_text(item['filename'])}`",
            f"  size: `{round(item['before_size'] / 1024 / 1024, 3)} MB` → `{round(item['after_size'] / 1024 / 1024, 3)} MB`",
            f"  short_term: `{before.get('short_term', 0)}` → `{after.get('short_term', 0)}`",
            f"  learned_facts: `{before.get('learned_facts', 0)}` → `{after.get('learned_facts', 0)}`",
            f"  duplicates: `{item.get('duplicate_facts', 0)}` / trimmed: `{item.get('trimmed_facts', 0)}`",
            f"  raw_omitted: `{item.get('raw_omitted', 0)}` / output_truncated: `{item.get('output_truncated', 0)}` / metadata_fixed: `{item.get('metadata_fixed', 0)}`",
        ])
    return "\n".join(lines)


def parse_keep_recent_facts(args: list[str]) -> int:
    if not args:
        return 200
    first = args[0]
    if first in {"apply", "dry-run", "dryrun"}:
        if len(args) >= 2:
            return int(args[1])
        return 200
    return int(first)


@authorized
async def cmd_memory_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status = get_memory_status()
    await safe_reply(update.message, format_memory_status(status), reply_markup=back_btn())


@authorized
async def cmd_memory_compact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args or []
    apply_requested = bool(args and args[0] in {"apply", "--apply"})
    try:
        keep_recent_facts = parse_keep_recent_facts(args)
    except ValueError:
        await safe_reply(update.message, "❌ keep_recent_facts 必须是数字，例如 `/memory_compact apply 200`。", reply_markup=back_btn())
        return
    if keep_recent_facts < 20:
        await safe_reply(update.message, "❌ keep_recent_facts 不能小于 20，避免误删长期事实。", reply_markup=back_btn())
        return

    result = compact_all_memories(dry_run=True, keep_recent_facts=keep_recent_facts)
    text = format_memory_compact_result(result)
    if apply_requested:
        compact_id = create_pending_memory_compact(context, keep_recent_facts)
        text += f"\n\n⚠️ 未写入文件。确认执行将先备份再整理，确认有效期 `{CONFIRM_EXPIRES_MINUTES} 分钟`。"
        reply_markup = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ 确认整理", callback_data=f"confirm_memory_compact:{compact_id}"),
            InlineKeyboardButton("❌ 取消", callback_data="menu"),
        ]])
    else:
        text += "\n\n未写入文件。需要执行时请用：`/memory_compact apply 200`"
        reply_markup = back_btn()
    await safe_reply(update.message, text, reply_markup=reply_markup)
