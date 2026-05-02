# AI 大脑核心逻辑
"""实现 @ai 消息的处理入口。
- 检查 AI 是否已启用（/ai_config enable/disable）
- 通过 OpenAI Function Calling 调度本地工具
- 最多 5 轮工具调用
- confirm 权限生成确认按钮，safe 权限直接执行
"""

import json
import logging
import urllib.request
import urllib.error

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from ai_config import get_enabled, get_mode_enabled, load_config
from ai_tools import (
    PermissionManager,
    ToolRegistry,
    execute_tool,
    DEFAULT_TOOL_DEFS,
    get_openai_tools_schema,
)

logger = logging.getLogger("guardian.ai")

_permission_manager = PermissionManager()
_tool_registry = ToolRegistry(_permission_manager)
_tool_registry.auto_discover(DEFAULT_TOOL_DEFS)


def _request_ai(messages: list[dict]) -> dict:
    cfg = load_config()
    url = (cfg.get("url") or "").rstrip("/") + "/chat/completions"
    key = cfg.get("key") or ""
    model = cfg.get("model") or ""
    if not url or not key or not model:
        return {"success": False, "message": "AI 配置不完整，请先设置 URL / KEY / MODEL。"}

    payload = {
        "model": model,
        "messages": messages,
        "tools": get_openai_tools_schema(),
        "tool_choice": "auto",
        "temperature": 0.2,
    }
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return {"success": True, "data": json.loads(resp.read().decode("utf-8"))}
    except urllib.error.HTTPError as e:
        body_text = e.read().decode("utf-8", errors="replace")[:1000]
        logger.error(f"AI API HTTPError: {e.code} {body_text}")
        return {"success": False, "message": f"HTTP {e.code}: {body_text[:300]}"}
    except Exception as e:
        logger.error(f"AI API error: {e}")
        return {"success": False, "message": str(e)}


def _tool_args_to_cli_args(tool_name: str, arguments: dict) -> list[str]:
    if tool_name in {"get_channel_detail", "get_channel_health", "enable_channel", "disable_channel"}:
        return [str(arguments["channel_id"])]
    if tool_name == "test_channel":
        args = [str(arguments["channel_id"])]
        if arguments.get("model"):
            args.append(arguments["model"])
        return args
    if tool_name in {"get_model_channels", "test_model_channels"}:
        return [arguments["model_name"]]
    if tool_name in {"test_channels_batch", "batch_enable", "batch_disable"}:
        return [",".join(str(x) for x in arguments["channel_ids"])]
    return []


async def _send_confirmation(update: Update, tool: str, arguments: dict):
    arg_json = json.dumps(arguments, ensure_ascii=False)
    btn = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ 确认执行", callback_data=f"ai_confirm:{tool}:{arg_json}"),
            InlineKeyboardButton("❌ 取消", callback_data="ai_cancel"),
        ]
    ])
    await update.message.reply_text(
        f"⚠️ 工具 `{tool}` 需要确认执行。\n参数: `{arg_json[:200]}`",
        reply_markup=btn,
        parse_mode="Markdown",
    )


async def handle_ai_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    text = update.message.text.strip()

    # AI 对话模式：
    # - mode_enabled=True: 所有非命令文本都走 AI
    # - mode_enabled=False: 只有 @ai 前缀才走 AI
    mode_enabled = get_mode_enabled()
    has_prefix = text.lower().startswith("@ai")

    # 命令消息交给其他 handler，不在这里处理
    if text.startswith("/"):
        return

    # 模式关闭且没有 @ai 前缀时，不处理
    if not mode_enabled and not has_prefix:
        return

    if not get_enabled():
        await update.message.reply_text("🤖 AI 功能未启用。使用 `/ai_config enable` 打开。")
        return

    # 有前缀则移除前缀；否则直接把整条消息作为提示词
    if has_prefix:
        user_prompt = text[3:].strip()
        # 如果 @ai 后面没内容，提示用户
        if not user_prompt:
            await update.message.reply_text("⚡ 请在 @ai 后提供指令。例如 `@ai 帮我看下概览`。")
            return
    else:
        user_prompt = text

    system_prompt = _tool_registry.build_system_prompt()
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    for _ in range(5):
        ai_result = _request_ai(messages)
        if not ai_result.get("success"):
            await update.message.reply_text(f"❌ AI 调用失败：{ai_result.get('message', '未知错误')}")
            return

        try:
            msg = ai_result["data"]["choices"][0]["message"]
        except Exception:
            await update.message.reply_text("❌ AI 返回结构异常。")
            return

        tool_calls = msg.get("tool_calls") or []
        content = msg.get("content") or msg.get("reasoning") or msg.get("reasoning_content")
        messages.append(msg)

        if tool_calls:
            pending_confirm = None
            for call in tool_calls:
                fn = call.get("function", {})
                tool_name = fn.get("name", "")
                try:
                    arguments = json.loads(fn.get("arguments") or "{}")
                except Exception:
                    arguments = {}
                level = _permission_manager.get_level(tool_name)
                if level == "forbidden":
                    tool_output = f"❌ 工具 {tool_name} 被禁止使用。"
                elif level == "confirm":
                    pending_confirm = (tool_name, arguments)
                    break
                else:
                    cli_args = _tool_args_to_cli_args(tool_name, arguments)
                    tool_output = execute_tool(tool_name, cli_args)
                messages.append({
                    "role": "tool",
                    "tool_call_id": call.get("id"),
                    "name": tool_name,
                    "content": tool_output,
                })
            if pending_confirm:
                tool_name, arguments = pending_confirm
                await _send_confirmation(update, tool_name, arguments)
                return
            continue

        if content:
            await update.message.reply_text(content)
            return

        await update.message.reply_text("⚠️ AI 没有返回可用内容。")
        return

    await update.message.reply_text("⚠️ AI 对话达到最大 5 轮，已停止。")


async def ai_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data == "ai_cancel":
        await query.edit_message_text("⚡ 已取消 AI 操作。")
        return
    if data.startswith("ai_confirm:"):
        _, tool, arg_json = data.split(":", 2)
        try:
            arguments = json.loads(arg_json)
        except Exception:
            arguments = {}
        cli_args = _tool_args_to_cli_args(tool, arguments)
        result = execute_tool(tool, cli_args)
        await query.edit_message_text(f"✅ 已确认执行\n\n{result}", parse_mode="Markdown")
        return
