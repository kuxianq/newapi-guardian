"""工具注册表 - 支持动态注册"""
import json
from pathlib import Path
from typing import Callable


# 工具定义
CORE_TOOLS = [
    {
        "name": "query_database",
        "description": "执行只读 SQL 查询 NewAPI 数据库。你可以查询 channels、logs、tokens、users 等表。支持标准 SQL SELECT 语法。",
        "parameters": {
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "SQL SELECT 语句"
                },
                "limit": {
                    "type": "integer",
                    "description": "最多返回行数（默认 100）",
                    "default": 100
                }
            },
            "required": ["sql"],
            "additionalProperties": False
        },
        "permission": "safe"
    },
    {
        "name": "call_api",
        "description": "调用 NewAPI 后台 API。可以测试渠道、启用/禁用渠道等操作。",
        "parameters": {
            "type": "object",
            "properties": {
                "method": {
                    "type": "string",
                    "enum": ["GET", "POST", "PUT", "DELETE"],
                    "description": "HTTP 方法"
                },
                "endpoint": {
                    "type": "string",
                    "description": "API 端点路径，如 /api/channel/test"
                },
                "data": {
                    "type": "object",
                    "description": "请求体数据（可选）"
                }
            },
            "required": ["method", "endpoint"],
            "additionalProperties": False
        },
        "permission": "confirm"
    }
]


class ToolRegistry:
    """工具注册表"""
    
    def __init__(self):
        self.tools = {}
        self.executors = {}
        
        # 注册核心工具
        for tool in CORE_TOOLS:
            self.register(
                name=tool["name"],
                description=tool["description"],
                parameters=tool["parameters"],
                permission=tool.get("permission", "safe")
            )
    
    def register(self, name: str, description: str, parameters: dict, permission: str = "safe", executor: Callable = None):
        """
        注册工具
        
        Args:
            name: 工具名称
            description: 工具描述
            parameters: 参数 schema（OpenAI function calling 格式）
            permission: 权限级别（safe/confirm/forbidden）
            executor: 执行函数（可选）
        """
        self.tools[name] = {
            "name": name,
            "description": description,
            "parameters": parameters,
            "permission": permission
        }
        
        if executor:
            self.executors[name] = executor
    
    def get_tool(self, name: str) -> dict | None:
        """获取工具定义"""
        return self.tools.get(name)
    
    def get_all_tools(self) -> list[dict]:
        """获取所有工具定义"""
        return list(self.tools.values())
    
    def get_openai_schema(self) -> list[dict]:
        """获取 OpenAI function calling schema"""
        return [
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["parameters"]
                }
            }
            for tool in self.tools.values()
        ]
    
    def is_allowed(self, name: str) -> bool:
        """检查工具是否允许使用"""
        tool = self.get_tool(name)
        if not tool:
            return False
        return tool.get("permission") != "forbidden"
    
    def needs_confirmation(self, name: str) -> bool:
        """检查工具是否需要确认"""
        tool = self.get_tool(name)
        if not tool:
            return True
        return tool.get("permission") == "confirm"


# 全局注册表实例
_registry = None

def get_registry() -> ToolRegistry:
    """获取全局工具注册表"""
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
    return _registry
