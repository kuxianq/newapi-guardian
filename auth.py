"""Authorization helpers for Telegram handlers."""
from __future__ import annotations

from functools import wraps

from telegram import Update
from telegram.ext import ContextTypes

from config import AUTHORIZED_IDS
from tg_safe import safe_reply


def authorized(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id if update.effective_user else 0
        if uid not in AUTHORIZED_IDS:
            msg = update.effective_message or (update.callback_query and update.callback_query.message)
            if msg:
                await safe_reply(msg, "⛔ 无权限。")
            return
        return await func(update, context)
    return wrapper
