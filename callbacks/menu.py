"""Menu / prompt / backup callback handlers."""
from __future__ import annotations

from typing import Callable

from backup import create_backup, list_backups
from menus import (
    channels_menu_kb,
    data_menu_kb,
    diagnose_menu_kb,
    memory_menu_kb,
    stats_menu_kb,
    status_menu_kb,
)
from tg_safe import safe_edit


_MENU_TEXTS = {
    "menu_status": (
        "📊 *状态*\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "运行状态与 Console 面板。今日统计与 24h 汇总请看「📈 统计报表」。",
        status_menu_kb,
    ),
    "menu_diagnose": (
        "🔎 *智能诊断*\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "用于定位模型失败、渠道异常、余额/预扣费问题和 fallback 原因。",
        diagnose_menu_kb,
    ),
    "menu_stats": (
        "📈 *统计报表*\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "今日/24h 汇总、Token 使用量、模型/用户/Token 排行、使用日志、慢渠道。",
        stats_menu_kb,
    ),
    "menu_channels": (
        "🔧 *渠道管理*\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "查询 · 测试 · 启用/禁用 · 异常处理。\n"
        "💡 添加、编辑、删除渠道仍建议在 NewAPI 网页端操作。",
        channels_menu_kb,
    ),
    "menu_data": (
        "💾 *数据安全*\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "备份、备份列表、恢复说明。\n"
        "⚠️ 恢复数据库属于高风险操作，仍需要二次确认。",
        data_menu_kb,
    ),
    "menu_memory": (
        "🧠 *Agent 记忆*\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "查看 Agent 长期记忆状态、指导 dry-run 整理。\n"
        "⚠️ 如果要真正写盘整理，请使用命令 `/memory_compact apply`。",
        memory_menu_kb,
    ),
}


_PROMPT_TEXTS = {
    "model_prompt": (
        "🧩 *按模型查询*\n\n请发送模型名称：\n`/model gpt-5.4`",
        channels_menu_kb,
    ),
    "channel_prompt": (
        "🔌 *按渠道查询*\n\n请发送渠道 ID：\n`/channel 105`",
        channels_menu_kb,
    ),
    "test_prompt": (
        "🧪 *测试单渠道*\n\n请发送：\n`/test 渠道ID`\n\n可以同时传多个渠道：\n`/test 101 102 103`",
        channels_menu_kb,
    ),
    "test_model_prompt": (
        "🧪 *按模型测试*\n\n请发送：\n`/test_model 模型名`\n\n会测试该模型下所有启用的渠道。例：\n`/test_model gpt-5.5`",
        channels_menu_kb,
    ),
    "enable_prompt": (
        "🟢 *启用渠道*\n\n请发送：\n`/enable 渠道ID`\n\n多个渠道可以空格分隔：\n`/enable 101 102 103`",
        channels_menu_kb,
    ),
    "disable_prompt": (
        "🔴 *禁用渠道*\n\n请发送：\n`/disable 渠道ID`\n\n多个渠道可以空格分隔：\n`/disable 101 102 103`",
        channels_menu_kb,
    ),
    "disable_failed_prompt": (
        "⚠️ *一键禁用失败渠道*\n\n请发送：\n`/disable_failed`\n\n也可以指定失败阈值：\n`/disable_failed 5`",
        channels_menu_kb,
    ),
    "restore_prompt": (
        "♻️ *恢复数据库*\n\n先查看备份：\n`/backup_list`\n\n再发送：\n`/restore 文件名`\n\n⚠️ 恢复会覆盖当前数据库，执行前会再次确认。",
        data_menu_kb,
    ),
}


def handle_menu_callback(data: str) -> tuple[str, Callable[[], object]] | None:
    """Return (text, markup_factory) for menu/prompt callbacks, or None."""
    if data in _MENU_TEXTS:
        text, kb = _MENU_TEXTS[data]
        return text, kb
    if data in _PROMPT_TEXTS:
        text, kb = _PROMPT_TEXTS[data]
        return text, kb
    return None


async def handle_backup_callback(q, data: str) -> tuple[str, bool]:
    """Handle backup/backup_list callbacks. Returns (text, handled)."""
    if data == "backup":
        await safe_edit(q, "💾 正在备份数据库...")
        ok, info, filepath = create_backup(tag="manual")
        if ok:
            text = f"✅ {info}"
            if filepath and filepath.stat().st_size < 50 * 1024 * 1024:
                try:
                    await q.message.reply_document(
                        document=open(filepath, "rb"),
                        filename=filepath.name,
                        caption="💾 NewAPI 数据库备份",
                    )
                except Exception as e:
                    text += f"\n⚠️ 文件发送失败: {e}"
        else:
            text = f"❌ {info}"
        return text, True

    if data == "backup_list":
        backups = list_backups()
        if not backups:
            return "📂 没有找到备份文件。", True
        lines = ["📂 *备份列表*\n"]
        for i, b in enumerate(backups[:15], 1):
            lines.append(f"  {i}. `{b['filename']}`\n     {b['created']} | {b['size_mb']}MB")
        lines.append(f"\n共 {len(backups)} 份备份")
        lines.append("\n恢复: `/restore 文件名`")
        return "\n".join(lines), True

    return "", False
