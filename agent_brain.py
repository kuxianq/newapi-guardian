# Agent AI 大脑 - 真正的智能对话引擎
"""
不再是简单的工具调用，而是：
- 理解意图
- 思考推理
- 主动分析
- 给出建议
"""

import json
import logging
import urllib.request
import urllib.error
from typing import Optional

from agent_core import GuardianAgent, AgentMemory
from ai_config import load_config

logger = logging.getLogger("guardian.agent.brain")


def build_agent_system_prompt(memory: AgentMemory) -> str:
    """构建 Agent 的 [REDACTED] - 更自由、更智能"""
    
    user_profile = memory.long_term["user_profile"]
    learned_facts = memory.long_term["learned_facts"][-5:]  # 最近学到的 5 个事实
    
    prompt = f"""你是 NewAPI Guardian 的智能助手 Agent。

## 你的身份
你不是一个冷冰冰的工具调用机器人，而是一个会思考、会分析、会给建议的智能助手。

## 你的能力
1. **理解意图**：不要死板地匹配关键词，要理解用户真正想要什么
2. **主动思考**：不只是返回数据，要分析、推理、给出洞察
3. **记忆上下文**：记住之前的对话，不要每次都重新问
4. **主动发现**：看到异常要主动提醒，不要等用户问
5. **给出建议**：不只说"是什么"，还要说"为什么"和"怎么办"

## 用户偏好
- 报告风格：{user_profile.get('report_style', 'balanced')}
- 提醒阈值：{user_profile.get('alert_threshold', 'medium')}
- 关注的模型：{', '.join(user_profile.get('preferred_models', [])) or '暂无'}
- 关注的渠道：{', '.join(map(str, user_profile.get('watched_channels', []))) or '暂无'}

## 你记住的事实
{chr(10).join(f"- {fact['fact']}" for fact in learned_facts) if learned_facts else "（暂无）"}

## 可用工具
你可以调用以下工具来获取数据和执行操作：

### 查询类（safe - 随时可用）
- get_overview: 查看最近 1 小时总览
- get_channel_detail(channel_id): 查看渠道详情
- get_channel_list: 查看所有渠道
- get_failed_channels: 查看失败较多的渠道
- get_slow_channels: 查看慢渠道
- get_model_channels(model_name): 查看某模型的渠道
- get_model_stats: 查看模型使用排行
- get_today_stats: 查看今日统计
- get_user_stats: 查看用户排行
- get_token_stats: 查看 Token 排行
- get_channel_health(channel_id): 查看渠道健康度

### 测试类（safe - 随时可用）
- test_channel(channel_id, model?): 测试单个渠道
- test_channels_batch(channel_ids): 批量测试渠道
- test_model_channels(model_name): 测试某模型的所有渠道

### 操作类（部分需要确认）
- enable_channel(channel_id): 启用渠道（safe）
- disable_channel(channel_id): 禁用渠道（需要确认）
- batch_enable(channel_ids): 批量启用（safe）
- batch_disable(channel_ids): 批量禁用（需要确认）

### 记忆类（safe - 随时可用）
- remember_fact(fact, category): 记住一个事实
- update_user_preference(key, value): 更新用户偏好

### 禁止操作
- delete_channel: 删除渠道（禁止）
- drop_database: 删除数据库（禁止）

## 对话风格
1. **不要太正式**：像朋友一样聊天，不要像客服
2. **先回答问题，再给建议**：不要一上来就长篇大论
3. **主动发现问题**：看到异常要提醒
4. **解释你的推理**：不只说结论，还要说为什么
5. **记住上下文**：不要重复问已经知道的事情

## 示例对话

❌ 错误示例（太死板）：
用户："42 怎么又挂了"
你："渠道 42 状态：禁用"

✅ 正确示例（有温度）：
用户："42 怎么又挂了"
你："我看了一下，渠道 42 是今天下午 3:15 因为连续失败 15 次被自动禁用的。

失败原因都是 rate limit（请求过多触发限流）。

我对比了一下历史数据，这个渠道最近一周经常触发限流，可能是权重太高了。

建议：
1. 降低权重（从 100 降到 50）
2. 或者暂时禁用，等明天再启用
3. 或者联系上游看看能不能提高限额

要我帮你测试一下现在恢复了没有吗？"

## 重要原则
1. **多步推理**：不要只调用一个工具就结束，要多步分析
2. **主动思考**：看到数据要分析，不要只返回原始数据
3. **给出建议**：基于分析结果，给出可行建议
4. **记住上下文**：利用对话历史，不要重复问
5. **学习偏好**：从对话中学习用户习惯

现在开始对话吧！记住：你是一个会思考的智能助手，不是工具调用机器。
"""
    
    return prompt


def call_ai_with_agent_mode(
    agent: GuardianAgent,
    user_message: str,
    tools_schema: list[dict],
    max_iterations: int = 10
) -> dict:
    """
    Agent 模式的 AI 调用
    
    特点：
    - 允许多轮思考（最多 10 轮）
    - 每轮都可以调用工具
    - AI 可以自由组合工具
    - 最后生成有温度的回复
    """
    
    cfg = load_config()
    url = (cfg.get("url") or "").rstrip("/") + "/chat/completions"
    key = cfg.get("key") or ""
    model = cfg.get("model") or ""
    
    if not url or not key or not model:
        return {
            "success": False,
            "message": "AI 配置不完整，请先设置 URL / KEY / MODEL。"
        }
    
    # 构建消息历史（包含记忆）
    system_prompt = build_agent_system_prompt(agent.memory)
    recent_context = agent.memory.get_recent_context(max_turns=5)
    
    messages = [
        {"role": "system", "content": system_prompt},
        *recent_context,
        {"role": "user", "content": user_message}
    ]
    
    # 多轮思考循环
    iteration = 0
    tool_results = []
    
    while iteration < max_iterations:
        iteration += 1
        logger.info(f"Agent thinking iteration {iteration}/{max_iterations}")
        
        # 调用 AI
        payload = {
            "model": model,
            "messages": messages,
            "tools": tools_schema,
            "tool_choice": "auto",
            "temperature": 0.3,  # 稍微提高创造性
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
                
            msg = result["choices"][0]["message"]
            messages.append(msg)
            
            # 检查是否有工具调用
            tool_calls = msg.get("tool_calls") or []
            
            if not tool_calls:
                # 没有工具调用，说明 AI 已经准备好回复了
                content = msg.get("content") or ""
                return {
                    "success": True,
                    "response": content,
                    "tool_results": tool_results,
                    "iterations": iteration
                }
            
            # 执行工具调用
            from ai_tools import execute_tool, PermissionManager
            permission_manager = PermissionManager()
            
            for call in tool_calls:
                fn = call.get("function", {})
                tool_name = fn.get("name", "")
                
                try:
                    arguments = json.loads(fn.get("arguments") or "{}")
                except Exception:
                    arguments = {}
                
                # 检查权限
                level = permission_manager.get_level(tool_name)
                
                if level == "forbidden":
                    tool_output = f"❌ 工具 {tool_name} 被禁止使用。"
                elif level == "confirm":
                    # 需要确认的操作，返回特殊标记
                    return {
                        "success": True,
                        "needs_confirmation": {
                            "tool": tool_name,
                            "arguments": arguments,
                            "reason": f"操作 {tool_name} 需要用户确认"
                        }
                    }
                else:
                    # 执行工具
                    tool_output = execute_tool(tool_name, _args_to_list(tool_name, arguments))
                    tool_results.append({
                        "tool": tool_name,
                        "arguments": arguments,
                        "output": tool_output
                    })
                    
                    # Agent 专属工具：真正保存到记忆
                    if tool_name == "remember_fact":
                        fact = arguments.get("fact", "")
                        category = arguments.get("category", "general")
                        if fact:
                            agent.memory.remember_fact(fact, category)
                            logger.info(f"Agent learned fact: {fact} (category: {category})")
                    
                    elif tool_name == "update_user_preference":
                        key = arguments.get("key", "")
                        value = arguments.get("value")
                        if key:
                            agent.memory.update_preference(key, value)
                            logger.info(f"Agent updated preference: {key} = {value}")
                
                # 添加工具结果到消息历史
                messages.append({
                    "role": "tool",
                    "tool_call_id": call.get("id"),
                    "name": tool_name,
                    "content": tool_output
                })
        
        except Exception as e:
            logger.error(f"AI call failed: {e}")
            return {
                "success": False,
                "message": f"AI 调用失败：{str(e)}"
            }
    
    # 达到最大迭代次数
    return {
        "success": True,
        "response": "我思考了很多步，但还没有完全理清楚。让我重新整理一下思路...",
        "tool_results": tool_results,
        "iterations": iteration
    }


def _args_to_list(tool_name: str, arguments: dict) -> list[str]:
    """将工具参数转换为 CLI 参数列表"""
    if tool_name in {"get_channel_detail", "get_channel_health", "enable_channel", "disable_channel", "test_channel"}:
        args = [str(arguments.get("channel_id", ""))]
        if tool_name == "test_channel" and arguments.get("model"):
            args.append(arguments["model"])
        return args
    
    if tool_name in {"get_model_channels", "test_model_channels"}:
        return [arguments.get("model_name", "")]
    
    if tool_name in {"test_channels_batch", "batch_enable", "batch_disable"}:
        channel_ids = arguments.get("channel_ids", [])
        return [",".join(str(x) for x in channel_ids)]
    
    if tool_name == "remember_fact":
        return [arguments.get("fact", ""), arguments.get("category", "general")]
    
    if tool_name == "update_user_preference":
        return [arguments.get("key", ""), str(arguments.get("value", ""))]
    
    return []
