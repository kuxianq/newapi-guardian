"""Telegram 安全发送封装。

目标：
- Markdown 解析失败时自动降级为纯文本，不让单条消息炸掉整个命令。
- 保持原有 reply_text / edit_message_text 接口最小侵入。
- 不做复杂转义，遵循“轻量、可读、不锁死能力”的原则。

使用方式：
    from tg_safe import safe_reply, safe_edit, safe_send

    await safe_reply(update.message, text, reply_markup=kb)
    await safe_edit(query, text, reply_markup=kb)
    await safe_send(app.bot, chat_id, text)
"""
from __future__ import annotations

import logging
from typing import Any

from telegram.constants import ParseMode
from telegram.error import BadRequest

logger = logging.getLogger("guardian.tg_safe")

DEFAULT_PARSE_MODE = ParseMode.MARKDOWN


async def _try_call(coro_factory, *, label: str):
    """先按 Markdown 发送；若 Telegram 解析失败则降级为纯文本。

    coro_factory(parse_mode) 必须返回一个 awaitable，由调用方提供具体动作。
    """
    try:
        return await coro_factory(DEFAULT_PARSE_MODE)
    except BadRequest as exc:
        msg = str(exc).lower()
        if "can't parse entities" in msg or "parse" in msg or "markdown" in msg:
            logger.warning("[tg_safe] %s markdown parse failed, fallback plain: %s", label, exc)
            try:
                return await coro_factory(None)
            except Exception as exc2:  # pragma: no cover - 防御性
                logger.error("[tg_safe] %s fallback plain also failed: %s", label, exc2)
                raise
        raise


async def safe_reply(message, text: str, *, reply_markup: Any = None, **kwargs):
    """安全 reply_text：Markdown 失败自动降级。"""

    async def _do(parse_mode):
        return await message.reply_text(
            text,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
            **kwargs,
        )

    return await _try_call(_do, label="reply_text")


async def safe_edit(query_or_message, text: str, *, reply_markup: Any = None, **kwargs):
    """安全 edit_message_text：Markdown 失败自动降级；edit 失败再退回新消息。"""

    edit_target = getattr(query_or_message, "edit_message_text", None)
    if edit_target is None and hasattr(query_or_message, "edit_text"):
        # message 对象本身
        async def _do(parse_mode):
            return await query_or_message.edit_text(
                text,
                parse_mode=parse_mode,
                reply_markup=reply_markup,
                **kwargs,
            )

        return await _try_call(_do, label="edit_text")

    async def _do(parse_mode):
        return await edit_target(
            text,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
            **kwargs,
        )

    try:
        return await _try_call(_do, label="edit_message_text")
    except BadRequest as exc:
        # 其它情况（消息未变 / 不可编辑）：退回新消息，避免命令“静默吞掉”
        logger.info("[tg_safe] edit failed, fallback to new message: %s", exc)
        msg = getattr(query_or_message, "message", None)
        if msg is not None:
            return await safe_reply(msg, text, reply_markup=reply_markup, **kwargs)
        raise


async def safe_send(bot, chat_id, text: str, *, reply_markup: Any = None, **kwargs):
    """安全 send_message：Markdown 失败自动降级。"""

    async def _do(parse_mode):
        return await bot.send_message(
            chat_id,
            text,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
            **kwargs,
        )

    return await _try_call(_do, label="send_message")
