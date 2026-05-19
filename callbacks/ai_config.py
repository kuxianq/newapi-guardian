"""AI configuration callback handlers."""
from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from ai_config import (
    get_mode_enabled,
    load_config,
    set_enabled as ai_set_enabled,
    set_mode_enabled,
)
from formatter import safe_text
from menus import ai_menu_kb, back_btn


def _mask_key(raw_key: str) -> str:
    if len(raw_key) > 10:
        return f"{raw_key[:6]}...{raw_key[-4:]}"
    if raw_key:
        return raw_key[:3] + "***"
    return "未设置"


def _ai_settings_text() -> str:
    cfg = load_config()
    masked_key = _mask_key(cfg.get("key", "") or "")
    return (
        "🤖 *AI 设置*\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"AI 功能: {'已启用 ✅' if cfg.get('enabled') else '未启用 ❌'}\n"
        f"对话模式: {'开启 ✅' if get_mode_enabled() else '关闭 ❌'}\n"
        f"API: `{safe_text(cfg.get('url') or '未设置')}`\n"
        f"模型: `{safe_text(cfg.get('model') or '未设置')}`\n"
        f"Key: `{safe_text(masked_key)}`"
    )


def _ai_config_panel() -> tuple[str, InlineKeyboardMarkup]:
    cfg = load_config()
    masked_key = _mask_key(cfg.get("key", "") or "")
    text = (
        "🤖 *AI 配置*\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"状态: {'已启用 ✅' if cfg.get('enabled') else '未启用 ❌'}\n"
        f"API: `{safe_text(cfg.get('url') or '未设置')}`\n"
        f"模型: `{safe_text(cfg.get('model') or '未设置')}`\n"
        f"Key: `{safe_text(masked_key)}`"
    )
    markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📝 修改 URL", callback_data="ai_set_url"),
            InlineKeyboardButton("🔑 修改 Key", callback_data="ai_set_key"),
        ],
        [
            InlineKeyboardButton("🤖 修改模型", callback_data="ai_set_model"),
            InlineKeyboardButton("✅ 启用", callback_data="ai_enable"),
            InlineKeyboardButton("❌ 禁用", callback_data="ai_disable"),
        ],
        [InlineKeyboardButton("🔙 返回 AI 设置", callback_data="menu_ai")],
    ])
    return text, markup


def handle_ai_callback(data: str) -> tuple[str, object] | None:
    """Return (text, markup) for AI callbacks, or None if not handled."""
    if data == "menu_ai":
        return _ai_settings_text(), ai_menu_kb()

    if data == "ai_mode_toggle":
        enabled = not get_mode_enabled()
        set_mode_enabled(enabled)
        status = "开启" if enabled else "关闭"
        body = (
            "现在所有非命令文本都会交给 AI 处理。"
            if enabled
            else "现在只有 `@ai` 前缀消息会交给 AI 处理。"
        )
        return f"🤖 AI 对话模式已切换为: *{status}*\n\n{body}", ai_menu_kb()

    if data == "ai_config_menu":
        # 平化：ai_config_menu 不再独立呈现，直接返回 menu_ai 详情面。
        return _ai_settings_text(), ai_menu_kb()

    if data == "ai_set_url":
        return "📝 请使用命令设置 AI URL：\n`/ai_config set_url <URL>`", back_btn()
    if data == "ai_set_key":
        return "🔑 请使用命令设置 AI Key：\n`/ai_config set_key <KEY>`", back_btn()
    if data == "ai_set_model":
        return "🤖 请使用命令设置 AI 模型：\n`/ai_config set_model <MODEL>`", back_btn()

    if data == "ai_enable":
        ai_set_enabled(True)
        return "✅ AI 功能已启用。", back_btn()
    if data == "ai_disable":
        ai_set_enabled(False)
        return "❌ AI 功能已禁用。", back_btn()

    return None
