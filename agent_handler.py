# Agent 消息处理器 - 替代旧的 ai_brain.py
"""
新的 Agent 模式消息处理：
- 会话记忆
- 多轮思考
- 主动分析
- 智能建议
"""

import json
import logging
import time
from uuid import uuid4
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from agent_core import GuardianAgent
from agent_brain import call_ai_with_agent_mode
from ai_config import get_enabled, get_mode_enabled
from tools_new.registry import get_registry

logger = logging.getLogger("guardian.agent.handler")

# 全局 Agent 实例缓存（按用户 ID）
_agent_cache = {}
_pending_confirmations = {}
PENDING_CONFIRMATION_TTL_SECONDS = 600


def _cleanup_pending_confirmations(now: float | None = None) -> None:
    now = now or time.time()
    expired = [
        confirmation_id
        for confirmation_id, payload in _pending_confirmations.items()
        if now - payload.get("created_at", 0) > PENDING_CONFIRMATION_TTL_SECONDS
    ]
    for confirmation_id in expired:
        _pending_confirmations.pop(confirmation_id, None)


def _store_pending_confirmation(tool: str, arguments: dict) -> str:
    _cleanup_pending_confirmations()
    confirmation_id = uuid4().hex[:12]
    _pending_confirmations[confirmation_id] = {
        "tool": tool,
        "arguments": arguments,
        "created_at": time.time(),
    }
    return confirmation_id


def get_agent(user_id: int) -> GuardianAgent:
    """获取或创建 Agent 实例"""
    if user_id not in _agent_cache:
        _agent_cache[user_id] = GuardianAgent(user_id)
        logger.info(f"Created new Agent instance for user {user_id}")
    return _agent_cache[user_id]


async def handle_agent_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Agent 模式消息处理

    特点：
    - 自动记忆上下文
    - 多轮思考
    - 主动分析
    - 智能建议
    """
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()
    user_id = update.effective_user.id

    # AI 对话模式判断
    mode_enabled = get_mode_enabled()
    has_prefix = text.lower().startswith("@ai")

    # 命令消息交给其他 handler
    if text.startswith("/"):
        return

    # 模式关闭且没有 @ai 前缀时，不处理
    if not mode_enabled and not has_prefix:
        return

    # 检查 AI 是否启用
    if not get_enabled():
        await update.message.reply_text("🤖 AI 功能未启用。使用 `/ai_config enable` 打开。")
        return

    # 移除 @ai 前缀
    if has_prefix:
        user_prompt = text[3:].strip()
        if not user_prompt:
            await update.message.reply_text("⚡ 请在 @ai 后提供内容。例如 `@ai 帮我看下概览`。")
            return
    else:
        user_prompt = text

    # 特殊命令：清空上下文
    if user_prompt.lower() in ["清空上下文", "clear context", "重新开始", "reset"]:
        agent = get_agent(user_id)
        agent.clear_context()
        await update.message.reply_text("✅ 已清空对话上下文，我们重新开始吧！")
        return

    # 获取 Agent 实例
    agent = get_agent(user_id)

    # 调用 Agent 处理
    try:
        registry = get_registry()
        tools_schema = registry.get_openai_schema()

        tools_schema.extend([
            {
                "type": "function",
                "function": {
                    "name": "remember_fact",
                    "description": "记住一个重要事实，以便后续对话使用",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "fact": {"type": "string", "description": "要记住的事实"},
                            "category": {"type": "string", "description": "分类（general/channel/model/user）"}
                        },
                        "required": ["fact"],
                        "additionalProperties": False
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "update_user_preference",
                    "description": "更新用户偏好设置",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "key": {"type": "string", "description": "偏好键（report_style/alert_threshold/preferred_models/watched_channels）"},
                            "value": {"description": "偏好值"}
                        },
                        "required": ["key", "value"],
                        "additionalProperties": False
                    }
                }
            }
        ])

        result = call_ai_with_agent_mode(
            agent=agent,
            user_message=user_prompt,
            tools_schema=tools_schema,
            max_iterations=10
        )

        if not result.get("success"):
            await update.message.reply_text(f"❌ {result.get('message', '未知错误')}")
            return

        # 检查是否需要确认
        if result.get("needs_confirmation"):
            confirm_data = result["needs_confirmation"]
            await _send_confirmation(update, confirm_data)
            return

        # 获取回复
        response = result.get("response", "")

        if not response:
            await update.message.reply_text("⚠️ AI 没有返回内容。")
            return

        # 保存到记忆
        agent.memory.add_turn(user_prompt, response, {
            "tool_results": result.get("tool_results", []),
            "iterations": result.get("iterations", 0)
        })

        # 发送回复
        await update.message.reply_text(response, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Agent message handling failed: {e}", exc_info=True)
        await update.message.reply_text(f"❌ 处理消息时出错：{str(e)}")


async def _send_confirmation(update: Update, confirm_data: dict):
    """发送确认按钮"""
    tool = confirm_data["tool"]
    arguments = confirm_data["arguments"]
    reason = confirm_data.get("reason", "")

    arg_json = json.dumps(arguments, ensure_ascii=False)
    confirmation_id = _store_pending_confirmation(tool, arguments)

    btn = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ 确认执行", callback_data=f"agent_confirm:{confirmation_id}"),
            InlineKeyboardButton("❌ 取消", callback_data="agent_cancel"),
        ]
    ])

    await update.message.reply_text(
        f"⚠️ 操作需要确认\n\n"
        f"工具：`{tool}`\n"
        f"参数：`{arg_json[:200]}`\n"
        f"原因：{reason}",
        reply_markup=btn,
        parse_mode="Markdown",
    )


async def agent_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Agent 确认按钮回调"""
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "agent_cancel":
        await query.edit_message_text("⚡ 已取消操作。")
        return

    if data.startswith("agent_confirm:"):
        from tools_new.executor import execute_tool

        confirmation_id = data.removeprefix("agent_confirm:")
        pending = _pending_confirmations.pop(confirmation_id, None)
        if not pending:
            await query.edit_message_text("⚠️ 确认已过期或不存在，请重新发起操作。")
            return
        tool = pending["tool"]
        arguments = pending["arguments"]

        result = execute_tool(tool, arguments, require_confirmation=True)

        # 获取 Agent 实例
        user_id = update.effective_user.id
        agent = get_agent(user_id)
        agent.memory.add_turn(
            f"[confirmed] {tool}",
            result.get("output", ""),
            {"tool_results": [result], "confirmed": True},
        )

        # 简化版：直接返回结果
        await query.edit_message_text(
            f"✅ 已执行\n\n{result.get('output', '')}",
            parse_mode="Markdown"
        )

        # TODO: 可以让 AI 继续生成更友好的回复
        return


# 导出给 bot.py 使用
__all__ = ["handle_agent_message", "agent_callback_handler", "get_agent"]
