"""Guardian Agent 大脑 - 通用 Agent + NewAPI Skill"""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import Any

from agent_core import AgentMemory, GuardianAgent
from ai_config import load_config
from skills.newapi import DATABASE_SCHEMA
from tools_new.executor import execute_tool

logger = logging.getLogger("guardian.agent.brain")


def build_agent_system_prompt(memory: AgentMemory, tools_schema: list[dict[str, Any]]) -> str:
    """构建系统提示词：通用 Agent + NewAPI Skill。"""
    user_profile = memory.long_term["user_profile"]
    learned_facts = memory.long_term["learned_facts"][-5:]

    tool_lines = []
    for item in tools_schema:
        fn = item.get("function", {})
        if not fn:
            continue
        tool_lines.append(f"- {fn.get('name')}：{fn.get('description', '')}")

    return f"""你是一个通用运维 Agent，擅长分析、推理、总结，并能在必要时调用工具完成任务。

## 角色定位
- 你不是只会机械调用工具的机器人，而是会先理解用户目标，再决定是否查询数据或调用 API。
- 你当前挂载了 NewAPI 运维 Skill，这是你的核心技能之一。
- 你要充分利用上下文记忆，保持多轮对话连续性。

## 用户偏好
- 报告风格：{user_profile.get('report_style', 'balanced')}
- 提醒阈值：{user_profile.get('alert_threshold', 'medium')}
- 关注的模型：{', '.join(user_profile.get('preferred_models', [])) or '暂无'}
- 关注的渠道：{', '.join(map(str, user_profile.get('watched_channels', []))) or '暂无'}

## 你记住的事实
{chr(10).join(f"- {fact['fact']}" for fact in learned_facts) if learned_facts else '（暂无）'}

## 当前挂载 Skill：NewAPI
{DATABASE_SCHEMA}

## 可用工具
{chr(10).join(tool_lines) if tool_lines else '（暂无工具）'}
- remember_fact：记住长期有用的事实
- update_user_preference：更新用户偏好

## 工作原则
1. 先回答用户问题，再根据需要补充分析和建议。
2. 需要数据支撑时优先调用工具，不要凭空猜测运行状态。
3. 用户询问 token、tokens、用量、消耗、额度、请求量、按模型/用户/Token 统计时，优先调用 `get_usage_summary`，不要先自由编写 SQL。
4. `query_database` 只用于专用工具无法覆盖的只读 SQL；不要用它返回大批原始日志。
5. 需要改状态时使用 `call_api`，并遵守确认流程。
6. 遇到需要确认的操作，不要假装已经执行，等系统回传确认流程。
7. 工具返回结果后，要做归纳和解释，而不是原样照抄。
8. 对话保持自然、简洁、专业。
"""


def call_ai_with_agent_mode(
    agent: GuardianAgent,
    user_message: str,
    tools_schema: list[dict[str, Any]],
    max_iterations: int = 10,
) -> dict[str, Any]:
    """通用 Agent 模式 AI 调用，支持多轮工具推理。"""
    cfg = load_config()
    url = (cfg.get("url") or "").rstrip("/") + "/chat/completions"
    key = cfg.get("key") or ""
    model = cfg.get("model") or ""

    if not url or not key or not model:
        return {"success": False, "message": "AI 配置不完整，请先设置 URL / KEY / MODEL。"}

    system_prompt = build_agent_system_prompt(agent.memory, tools_schema)
    recent_context = agent.memory.get_recent_context(max_turns=5)
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        *recent_context,
        {"role": "user", "content": user_message},
    ]

    iteration = 0
    tool_results: list[dict[str, Any]] = []

    while iteration < max_iterations:
        iteration += 1
        payload = {
            "model": model,
            "messages": messages,
            "tools": tools_schema,
            "tool_choice": "auto",
            "temperature": 0.3,
        }

        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                result = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            logger.error("AI call failed: %s", exc)
            return {"success": False, "message": f"AI 调用失败：{exc}"}

        msg = result["choices"][0]["message"]
        messages.append(msg)
        tool_calls = msg.get("tool_calls") or []

        if not tool_calls:
            return {
                "success": True,
                "response": msg.get("content") or "",
                "tool_results": tool_results,
                "iterations": iteration,
            }

        for call in tool_calls:
            fn = call.get("function", {})
            tool_name = fn.get("name", "")
            try:
                arguments = json.loads(fn.get("arguments") or "{}")
            except Exception:
                arguments = {}

            if tool_name == "remember_fact":
                fact = arguments.get("fact", "")
                category = arguments.get("category", "general")
                if fact:
                    agent.memory.remember_fact(fact, category)
                    tool_output = f"✅ 已记住：{fact}（{category}）"
                else:
                    tool_output = "❌ fact 不能为空"
                tool_results.append({"tool": tool_name, "arguments": arguments, "output": tool_output})
            elif tool_name == "update_user_preference":
                key_name = arguments.get("key", "")
                value = arguments.get("value")
                if key_name:
                    agent.memory.update_preference(key_name, value)
                    tool_output = f"✅ 已更新偏好：{key_name} = {value}"
                else:
                    tool_output = "❌ key 不能为空"
                tool_results.append({"tool": tool_name, "arguments": arguments, "output": tool_output})
            else:
                execution = execute_tool(tool_name, arguments)
                if execution.get("needs_confirmation"):
                    return {
                        "success": True,
                        "needs_confirmation": {
                            "tool": tool_name,
                            "arguments": arguments,
                            "reason": f"操作 {tool_name} 需要用户确认",
                        },
                        "tool_results": tool_results,
                        "iterations": iteration,
                    }
                tool_output = execution.get("output") or execution.get("error") or ""
                raw_data = execution.get("data")
                if isinstance(raw_data, dict):
                    raw_data = {
                        "success": raw_data.get("success"),
                        "row_count": raw_data.get("row_count"),
                        "limited": raw_data.get("limited"),
                        "scope": raw_data.get("scope"),
                        "group_by": raw_data.get("group_by"),
                    }
                tool_results.append(
                    {
                        "tool": tool_name,
                        "arguments": arguments,
                        "output": tool_output[:4000] + ("\n... [truncated]" if len(tool_output) > 4000 else ""),
                        "raw": raw_data,
                    }
                )

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.get("id"),
                    "name": tool_name,
                    "content": tool_output,
                }
            )

    return {
        "success": True,
        "response": "我已经做了多轮分析，但还需要再整理一下结论。",
        "tool_results": tool_results,
        "iterations": iteration,
    }
