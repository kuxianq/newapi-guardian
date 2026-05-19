"""Inline callback handlers for stats/report buttons."""
from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

import db as newapi_db
from formatter import (
    fmt_console,
    fmt_model_usage,
    fmt_overview,
    fmt_recent_logs,
    fmt_slow_channels,
    fmt_today_stats,
    fmt_token_usage,
    fmt_user_usage,
)
from menus import back_btn


def handle_stats_callback(data: str) -> tuple[str, object] | None:
    """Return (text, markup) for stats callbacks, or None if not handled."""
    markup = back_btn()
    if data == "overview":
        return build_overview_text(minutes=60), markup

    if data == "slow":
        return fmt_slow_channels(newapi_db.get_slow_channels(minutes=60)), markup

    if data == "report":
        stats = newapi_db.get_overview_stats(minutes=1440)
        fail_ch = newapi_db.get_channel_failure_stats(minutes=1440)
        fail_m = newapi_db.get_model_failure_stats(minutes=1440)
        today = newapi_db.get_today_stats()
        slow = newapi_db.get_slow_channels(minutes=1440)
        balance = newapi_db.get_balance_suspect_channels(minutes=1440)
        return fmt_overview(stats, fail_ch, fail_m, today, slow, balance).replace("最近 1h", "最近 24h"), markup

    if data == "recent_logs":
        logs = newapi_db.get_recent_logs(limit=10)
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 刷新", callback_data="recent_logs")],
            [InlineKeyboardButton("🔙 返回统计报表", callback_data="menu_stats")],
        ])
        return fmt_recent_logs(logs), markup

    if data == "console":
        stats = newapi_db.get_today_stats()
        today_models = newapi_db.get_today_model_usage(15)
        all_models = newapi_db.get_model_usage_stats(0, 10)
        users = newapi_db.get_user_usage_stats(5)
        tokens = newapi_db.get_token_usage_stats(5)
        return fmt_console(stats, today_models, all_models, users, tokens), markup

    if data == "today":
        stats = newapi_db.get_today_stats()
        yesterday_stats = newapi_db.get_yesterday_stats()
        models = newapi_db.get_today_model_usage(15)
        return fmt_today_stats(stats, models, yesterday_stats), markup

    if data == "models":
        all_models = newapi_db.get_model_usage_stats(0, 20)
        return fmt_model_usage(all_models, "模型使用排行（全部时间）"), markup

    if data == "users":
        users_data = newapi_db.get_user_usage_stats(10)
        return fmt_user_usage(users_data), markup

    if data == "tokens":
        tokens_data = newapi_db.get_token_usage_stats(10)
        return fmt_token_usage(tokens_data), markup

    return None


def build_overview_text(minutes: int = 60) -> str:
    stats = newapi_db.get_overview_stats(minutes=minutes)
    fail_ch = newapi_db.get_channel_failure_stats(minutes=minutes)
    fail_m = newapi_db.get_model_failure_stats(minutes=minutes)
    today = newapi_db.get_today_stats()
    slow = newapi_db.get_slow_channels(minutes=minutes)
    balance = newapi_db.get_balance_suspect_channels(minutes=120)
    return fmt_overview(stats, fail_ch, fail_m, today, slow, balance)
