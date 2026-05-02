# NewAPI Guardian Agent - 核心智能引擎
"""
真正的 Agent 实现，而不是简单的工具调用机器人。

核心能力：
1. 记忆系统（短期 + 长期）
2. 思考引擎（分析 + 推理）
3. 自主决策（主动发现问题）
4. 学习能力（从对话中学习）
"""

from decimal import Decimal
from datetime import datetime, date, time, timedelta


class _SafeJSONEncoder:
    """兼容各种类型的 JSON 编码器帮手"""
    @staticmethod
    def default(obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, (datetime, date, time)):
            return obj.isoformat()
        if isinstance(obj, timedelta):
            return obj.total_seconds()
        if isinstance(obj, bytes):
            try:
                return obj.decode('utf-8')
            except UnicodeDecodeError:
                return obj.hex()
        if isinstance(obj, set):
            return list(obj)
        raise TypeError(f'Object of type {obj.__class__.__name__} is not JSON serializable')

import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger("guardian.agent")

# 数据目录
DATA_DIR = Path(__file__).parent / "data"
MEMORY_DIR = DATA_DIR / "agent_memory"
MEMORY_DIR.mkdir(parents=True, exist_ok=True)


class AgentMemory:
    """Agent 记忆系统 - 三层记忆架构"""
    
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.memory_file = MEMORY_DIR / f"user_{user_id}.json"
        self.load()
    
    def load(self):
        """加载记忆"""
        if self.memory_file.exists():
            data = json.loads(self.memory_file.read_text(encoding="utf-8"))
        else:
            data = self._default_memory()
        
        self.working_memory = []  # 当前对话（运行时）
        self.short_term = data.get("short_term", [])[-20:]  # 最近 20 轮
        self.long_term = data.get("long_term", self._default_long_term())
    
    def save(self):
        """保存记忆"""
        data = {
            "short_term": self.short_term[-20:],  # 只保留最近 20 轮
            "long_term": self.long_term,
            "last_updated": datetime.now().isoformat()
        }
        self.memory_file.write_text(
            json.dumps(data, ensure_ascii=False, indent=2, default=_SafeJSONEncoder.default),
            encoding="utf-8"
        )
    
    def _default_memory(self):
        return {
            "short_term": [],
            "long_term": self._default_long_term()
        }
    
    def _default_long_term(self):
        return {
            "user_profile": {
                "alert_threshold": "medium",  # low/medium/high
                "report_style": "balanced",   # concise/balanced/detailed
                "preferred_models": [],
                "watched_channels": []
            },
            "knowledge_base": {},  # 学到的知识
            "patterns": {},        # 发现的规律
            "learned_facts": []    # 记住的事实
        }
    
    def add_turn(self, user_msg: str, assistant_msg: str, metadata: dict = None):
        """添加一轮对话"""
        turn = {
            "timestamp": datetime.now().isoformat(),
            "user": user_msg,
            "assistant": assistant_msg,
            "metadata": metadata or {}
        }
        self.working_memory.append(turn)
        self.short_term.append(turn)
        self.save()
    
    def get_recent_context(self, max_turns: int = 5) -> list:
        """获取最近对话上下文"""
        recent = self.short_term[-max_turns:]
        context = []
        for turn in recent:
            context.append({"role": "user", "content": turn["user"]})
            context.append({"role": "assistant", "content": turn["assistant"]})
        return context
    
    def remember_fact(self, fact: str, category: str = "general"):
        """记住一个事实"""
        self.long_term["learned_facts"].append({
            "fact": fact,
            "category": category,
            "learned_at": datetime.now().isoformat(),
            "confidence": 1.0
        })
        self.save()
    
    def update_preference(self, key: str, value: any):
        """更新用户偏好"""
        self.long_term["user_profile"][key] = value
        self.save()
    
    def get_preference(self, key: str, default=None):
        """获取用户偏好"""
        return self.long_term["user_profile"].get(key, default)
    
    def learn_pattern(self, pattern_name: str, pattern_data: dict):
        """学习一个行为模式"""
        self.long_term["patterns"][pattern_name] = {
            "data": pattern_data,
            "discovered_at": datetime.now().isoformat(),
            "occurrences": self.long_term["patterns"].get(pattern_name, {}).get("occurrences", 0) + 1
        }
        self.save()


class ThinkingEngine:
    """Agent 思考引擎 - 分析、推理、决策"""
    
    def __init__(self, memory: AgentMemory):
        self.memory = memory
    
    def analyze_intent(self, user_message: str) -> dict:
        """分析用户意图（不依赖 AI，基于规则）"""
        msg_lower = user_message.lower()
        
        intent = {
            "type": "unknown",
            "entities": {},
            "urgency": "normal",
            "needs_action": False
        }
        
        # 检测意图类型
        if any(word in msg_lower for word in ["怎么样", "状态", "情况", "看看"]):
            intent["type"] = "query_status"
        elif any(word in msg_lower for word in ["为什么", "原因", "怎么回事"]):
            intent["type"] = "investigate"
        elif any(word in msg_lower for word in ["帮我", "测试", "检查"]):
            intent["type"] = "action_request"
            intent["needs_action"] = True
        elif any(word in msg_lower for word in ["建议", "怎么办", "该"]):
            intent["type"] = "ask_advice"
        
        # 检测紧急程度
        if any(word in msg_lower for word in ["又", "还", "一直", "总是"]):
            intent["urgency"] = "high"
        
        # 提取实体（渠道 ID、模型名等）
        import re
        channel_ids = re.findall(r'\b\d{2,4}\b', user_message)
        if channel_ids:
            intent["entities"]["channel_ids"] = [int(cid) for cid in channel_ids]
        
        return intent
    
    def should_proactive_check(self) -> bool:
        """判断是否应该主动检查异常"""
        # 如果用户问了开放性问题，主动检查
        # 如果距离上次检查超过 5 分钟，主动检查
        return True  # 简化版：总是主动检查
    
    def generate_insights(self, data: dict, context: str) -> list:
        """从数据中生成洞察"""
        insights = []
        
        # 这里可以加入各种分析逻辑
        # 例如：对比历史、发现趋势、识别异常
        
        return insights


class GuardianAgent:
    """NewAPI Guardian 智能 Agent"""
    
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.memory = AgentMemory(user_id)
        self.thinking = ThinkingEngine(self.memory)
        logger.info(f"Guardian Agent initialized for user {user_id}")
    
    def process_message(self, user_message: str) -> dict:
        """
        处理用户消息 - Agent 主循环
        
        返回：
        {
            "response": "回复内容",
            "actions_taken": [...],
            "suggestions": [...],
            "needs_confirmation": None or {...}
        }
        """
        # 1. 分析意图
        intent = self.thinking.analyze_intent(user_message)
        logger.info(f"Intent analyzed: {intent}")
        
        # 2. 构建上下文（包含记忆）
        context = self._build_context(user_message, intent)
        
        # 3. 制定计划（这里会调用 AI）
        plan = self._make_plan(context)
        
        # 4. 执行计划
        result = self._execute_plan(plan)
        
        # 5. 生成回复（有温度、有建议）
        response = self._generate_response(result, intent)
        
        # 6. 学习和记忆
        self._learn_from_interaction(user_message, response, result)
        
        return response
    
    def _build_context(self, user_message: str, intent: dict) -> dict:
        """构建完整上下文"""
        return {
            "user_message": user_message,
            "intent": intent,
            "recent_history": self.memory.get_recent_context(max_turns=5),
            "user_preferences": self.memory.long_term["user_profile"],
            "learned_facts": self.memory.long_term["learned_facts"][-10:],  # 最近学到的事实
            "timestamp": datetime.now().isoformat()
        }
    
    def _make_plan(self, context: dict) -> dict:
        """制定行动计划"""
        # 这里会调用 AI 来制定计划
        # 但给 AI 更多自由度，不限制在固定工具列表
        return {
            "steps": [],
            "reasoning": ""
        }
    
    def _execute_plan(self, plan: dict) -> dict:
        """执行计划"""
        return {
            "success": True,
            "data": {},
            "insights": []
        }
    
    def _generate_response(self, result: dict, intent: dict) -> dict:
        """生成有温度的回复"""
        return {
            "response": "...",
            "actions_taken": [],
            "suggestions": [],
            "needs_confirmation": None
        }
    
    def _learn_from_interaction(self, user_msg: str, response: dict, result: dict):
        """从交互中学习"""
        # 保存对话
        self.memory.add_turn(user_msg, response["response"])
        
        # 学习用户偏好
        if "简单" in user_msg or "简洁" in user_msg:
            self.memory.update_preference("report_style", "concise")
        
        # 记住重要事实
        # ...
    
    def clear_context(self):
        """清空当前对话上下文"""
        self.memory.working_memory = []
        logger.info(f"Context cleared for user {self.user_id}")
