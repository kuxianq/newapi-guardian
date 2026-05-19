"""Telegram 菜单布局。

只放按钮结构与简单导航，不放业务逻辑。
"""
from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def nav_row(parent: str | None = None) -> list[InlineKeyboardButton]:
    row: list[InlineKeyboardButton] = []
    if parent:
        row.append(InlineKeyboardButton("↩️ 返回上一级", callback_data=parent))
    row.append(InlineKeyboardButton("🏠 主菜单", callback_data="menu"))
    return row


def back_btn(parent: str | None = None) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([nav_row(parent)])


def main_menu_kb(ai_mode_enabled: bool = False) -> InlineKeyboardMarkup:
    mode_status = "开启" if ai_mode_enabled else "关闭"
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 状态", callback_data="menu_status"),
            InlineKeyboardButton("🔎 智能诊断", callback_data="menu_diagnose"),
        ],
        [
            InlineKeyboardButton("🔧 渠道管理", callback_data="menu_channels"),
            InlineKeyboardButton("📈 统计报表", callback_data="menu_stats"),
        ],
        [
            InlineKeyboardButton("💾 数据安全", callback_data="menu_data"),
            InlineKeyboardButton(f"🤖 AI 设置 · {mode_status}", callback_data="menu_ai"),
        ],
        [
            InlineKeyboardButton("🧠 Agent 记忆", callback_data="menu_memory"),
            InlineKeyboardButton("📚 NewAPI 文档", callback_data="newapi_docs_menu"),
        ],
        [
            InlineKeyboardButton("ℹ️ 系统信息", callback_data="system_info"),
            InlineKeyboardButton("🛟 帮助", callback_data="help_prompt"),
        ],
    ])


def status_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 状态概览", callback_data="overview"),
            InlineKeyboardButton("🖥️ Console 面板", callback_data="console"),
        ],
        nav_row(),
    ])


def diagnose_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔎 诊断 gpt-5.5", callback_data="diagnose_model:gpt-5.5"),
            InlineKeyboardButton("🔎 诊断 4-7", callback_data="diagnose_model:claude-opus-4-7"),
        ],
        [
            InlineKeyboardButton("🧩 按模型诊断", callback_data="diagnose_model_prompt"),
            InlineKeyboardButton("🔌 按渠道诊断", callback_data="diagnose_channel_prompt"),
        ],
        [
            InlineKeyboardButton("💰 余额/预扣费异常", callback_data="diagnose_balance"),
        ],
        nav_row(),
    ])


def stats_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📅 今日统计", callback_data="today"),
            InlineKeyboardButton("📋 24h 汇总", callback_data="report"),
        ],
        [
            InlineKeyboardButton("📊 Token/用量", callback_data="usage_summary_btn"),
            InlineKeyboardButton("📋 使用日志", callback_data="recent_logs"),
        ],
        [
            InlineKeyboardButton("📈 模型排行", callback_data="models"),
            InlineKeyboardButton("👤 用户排行", callback_data="users"),
        ],
        [
            InlineKeyboardButton("🔑 Token 排行", callback_data="tokens"),
            InlineKeyboardButton("🐢 慢渠道", callback_data="slow"),
        ],
        nav_row(),
    ])


def channels_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔌 按渠道查", callback_data="channel_prompt"),
            InlineKeyboardButton("🧩 按模型查", callback_data="model_prompt"),
        ],
        [
            InlineKeyboardButton("🧪 测试单渠道", callback_data="test_prompt"),
            InlineKeyboardButton("🧪 按模型测试", callback_data="test_model_prompt"),
        ],
        [
            InlineKeyboardButton("🧪 测试全部", callback_data="test_all"),
            InlineKeyboardButton("⚠️ 禁用失败渠道", callback_data="disable_failed_prompt"),
        ],
        [
            InlineKeyboardButton("🟢 启用渠道", callback_data="enable_prompt"),
            InlineKeyboardButton("🔴 禁用渠道", callback_data="disable_prompt"),
        ],
        nav_row(),
    ])


def data_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💾 立即备份", callback_data="backup"),
            InlineKeyboardButton("📂 备份列表", callback_data="backup_list"),
        ],
        [InlineKeyboardButton("♻️ 恢复说明", callback_data="restore_prompt")],
        nav_row(),
    ])


def ai_menu_kb() -> InlineKeyboardMarkup:
    """AI 设置一级菜单（已扁平化，不再有二级 ai_config_menu）。"""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔁 切换 AI 模式", callback_data="ai_mode_toggle"),
        ],
        [
            InlineKeyboardButton("📝 修改 URL", callback_data="ai_set_url"),
            InlineKeyboardButton("🔑 修改 Key", callback_data="ai_set_key"),
        ],
        [
            InlineKeyboardButton("🤖 修改模型", callback_data="ai_set_model"),
            InlineKeyboardButton("✅ 启用 AI", callback_data="ai_enable"),
        ],
        [
            InlineKeyboardButton("❌ 禁用 AI", callback_data="ai_disable"),
        ],
        nav_row(),
    ])


def memory_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🧠 记忆状态", callback_data="memory_status_btn"),
            InlineKeyboardButton("🧹 整理记忆 (dry-run)", callback_data="memory_compact_btn"),
        ],
        nav_row(),
    ])


def status_kb() -> InlineKeyboardMarkup:
    """`/status` 命令底下的快捷入口。"""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔎 智能诊断", callback_data="menu_diagnose"),
            InlineKeyboardButton("📈 统计报表", callback_data="menu_stats"),
        ],
        [
            InlineKeyboardButton("🔧 渠道管理", callback_data="menu_channels"),
            InlineKeyboardButton("🏠 主菜单", callback_data="menu"),
        ],
    ])


def newapi_docs_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔌 渠道", callback_data="newapi_docs:channels"),
            InlineKeyboardButton("📋 日志", callback_data="newapi_docs:logs"),
        ],
        [
            InlineKeyboardButton("💰 额度", callback_data="newapi_docs:quota"),
            InlineKeyboardButton("🤖 模型", callback_data="newapi_docs:models"),
        ],
        [InlineKeyboardButton("🧩 API", callback_data="newapi_docs:api")],
        nav_row(),
    ])
