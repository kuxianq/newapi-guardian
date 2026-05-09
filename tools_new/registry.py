"""工具注册表 - 支持动态注册。

设计口径：保持小 Agent 的灵活性，不把能力锁死；但对工具调用做轻量风险分层：
- safe：只读 / 低风险，可直接执行
- confirm：会产生外部动作或不确定影响，需要用户确认
- forbidden：明显越界，不允许执行
"""
from typing import Callable


SAFE_API_PREFIXES = (
    "/api/channel/",
    "/api/log/",
    "/api/log/stat",
    "/api/task/",
)

DANGEROUS_API_KEYWORDS = (
    "/delete",
    "/remove",
    "/restore",
    "/disable",
    "/enable",
    "/status",
    "/update",
)


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
        "name": "diagnose_newapi_failure",
        "description": "只读诊断 NewAPI 按模型、渠道、余额/预扣费相关失败，返回失败范围、疑似原因、Top 失败渠道和最近失败样本。适合回答“某模型刚才哪个渠道报错”“余额不足是哪条渠道”“为什么 fallback”等问题。",
        "parameters": {
            "type": "object",
            "properties": {
                "model": {
                    "type": "string",
                    "description": "可选，模型名，如 gpt-5.5 或 claude-opus-4-7"
                },
                "channel_id": {
                    "type": "integer",
                    "description": "可选，渠道 ID"
                },
                "minutes": {
                    "type": "integer",
                    "description": "回看最近多少分钟，默认 60，最大 10080",
                    "default": 60
                },
                "include_recent": {
                    "type": "boolean",
                    "description": "是否返回最近失败样本",
                    "default": True
                }
            },
            "additionalProperties": False
        },
        "permission": "safe"
    },
    {
        "name": "get_newapi_runtime_info",
        "description": "只读检测当前 NewAPI 实例版本、官方 GitHub 和文档入口。版本字段取不到时返回 unknown，不猜测。",
        "parameters": {
            "type": "object",
            "properties": {},
            "additionalProperties": False
        },
        "permission": "safe"
    },
    {
        "name": "get_newapi_docs",
        "description": "获取内置 NewAPI 文档参考入口和常见排查主题。用于不确定渠道、日志、额度、模型或 API 行为时先查文档。",
        "parameters": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "enum": ["channels", "logs", "quota", "models", "api"],
                    "description": "可选文档主题"
                }
            },
            "additionalProperties": False
        },
        "permission": "safe"
    },
    {
        "name": "call_api",
        "description": "调用 NewAPI 后台 API。只读 GET 可直接执行；会修改状态的 POST/PUT/DELETE 或高风险端点需要确认。",
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
                    "description": "API 端点路径，如 /api/channel/1"
                },
                "data": {
                    "type": "object",
                    "description": "请求体数据（可选）"
                }
            },
            "required": ["method", "endpoint"],
            "additionalProperties": False
        },
        "permission": "dynamic"
    }
]


class ToolRegistry:
    """工具注册表"""

    def __init__(self):
        self.tools = {}
        self.executors = {}

        for tool in CORE_TOOLS:
            self.register(
                name=tool["name"],
                description=tool["description"],
                parameters=tool["parameters"],
                permission=tool.get("permission", "safe")
            )

    def register(self, name: str, description: str, parameters: dict, permission: str = "safe", executor: Callable = None):
        self.tools[name] = {
            "name": name,
            "description": description,
            "parameters": parameters,
            "permission": permission
        }

        if executor:
            self.executors[name] = executor

    def get_tool(self, name: str) -> dict | None:
        return self.tools.get(name)

    def get_all_tools(self) -> list[dict]:
        return list(self.tools.values())

    def get_openai_schema(self) -> list[dict]:
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

    def classify_api_risk(self, method: str, endpoint: str) -> str:
        """轻量 API 风险分级。"""
        method = (method or "GET").upper()
        endpoint = (endpoint or "").strip()
        endpoint_lower = endpoint.lower()

        if method not in {"GET", "POST", "PUT", "DELETE"}:
            return "forbidden"
        if not endpoint.startswith("/api/"):
            return "forbidden"

        if method == "GET":
            return "safe" if endpoint.startswith(SAFE_API_PREFIXES) else "confirm"

        if any(keyword in endpoint_lower for keyword in DANGEROUS_API_KEYWORDS):
            return "confirm"

        return "confirm"

    def permission_for(self, name: str, arguments: dict | None = None) -> str:
        tool = self.get_tool(name)
        if not tool:
            return "forbidden"
        if name == "call_api":
            arguments = arguments or {}
            return self.classify_api_risk(arguments.get("method", "GET"), arguments.get("endpoint", ""))
        return tool.get("permission", "forbidden")

    def is_allowed(self, name: str, arguments: dict | None = None) -> bool:
        return self.permission_for(name, arguments) != "forbidden"

    def needs_confirmation(self, name: str, arguments: dict | None = None) -> bool:
        return self.permission_for(name, arguments) == "confirm"


_registry = None


def get_registry() -> ToolRegistry:
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
    return _registry
