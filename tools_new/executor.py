"""工具执行器 - 统一路由、权限检查和结果格式化"""
from __future__ import annotations

import json
import logging
from typing import Any

from core.database import execute_readonly_sql
from core.formatter import format_kv, format_list, format_table, truncate
from core.http_client import call_api
from tools_new.registry import get_registry

logger = logging.getLogger("guardian.tools.executor")


class ToolExecutionError(Exception):
    """工具执行异常"""


class ToolExecutor:
    """统一工具执行器"""

    def __init__(self):
        self.registry = get_registry()

    def get_permission(self, tool_name: str) -> str:
        tool = self.registry.get_tool(tool_name)
        if not tool:
            return "forbidden"
        return tool.get("permission", "forbidden")

    def execute(self, tool_name: str, arguments: dict[str, Any] | None = None, *, require_confirmation: bool = False) -> dict[str, Any]:
        arguments = arguments or {}
        tool = self.registry.get_tool(tool_name)
        if not tool:
            return self._result(False, tool_name, arguments, error=f"未知工具: {tool_name}")

        permission = tool.get("permission", "forbidden")
        if permission == "forbidden":
            return self._result(False, tool_name, arguments, error=f"工具 {tool_name} 被禁止使用", permission=permission)

        if permission == "confirm" and not require_confirmation:
            return self._result(
                False,
                tool_name,
                arguments,
                error=f"工具 {tool_name} 需要确认后才能执行",
                permission=permission,
                needs_confirmation=True,
            )

        try:
            if tool_name == "query_database":
                raw = execute_readonly_sql(
                    sql=str(arguments.get("sql", "")).strip(),
                    limit=int(arguments.get("limit", 100)),
                )
            elif tool_name == "call_api":
                raw = call_api(
                    method=str(arguments.get("method", "GET")).upper(),
                    endpoint=str(arguments.get("endpoint", "")).strip(),
                    data=arguments.get("data"),
                )
            else:
                raise ToolExecutionError(f"工具 {tool_name} 暂无执行器")

            return self._result(
                bool(raw.get("success")),
                tool_name,
                arguments,
                permission=permission,
                data=raw,
                output=self._format_output(tool_name, raw),
                error=raw.get("error"),
            )
        except Exception as exc:
            logger.exception("Tool execution failed: %s", tool_name)
            return self._result(False, tool_name, arguments, permission=permission, error=str(exc))

    def _result(
        self,
        success: bool,
        tool_name: str,
        arguments: dict[str, Any],
        *,
        permission: str | None = None,
        data: dict[str, Any] | None = None,
        output: str | None = None,
        error: str | None = None,
        needs_confirmation: bool = False,
    ) -> dict[str, Any]:
        return {
            "success": success,
            "tool": tool_name,
            "arguments": arguments,
            "permission": permission or self.get_permission(tool_name),
            "needs_confirmation": needs_confirmation,
            "data": data,
            "output": output or (f"❌ {error}" if error else ""),
            "error": error,
        }

    def _format_output(self, tool_name: str, raw: dict[str, Any]) -> str:
        if not raw.get("success"):
            return f"❌ {raw.get('error', '执行失败')}"

        if tool_name == "query_database":
            rows = raw.get("data") or []
            if not rows:
                return "✅ 查询成功，但没有返回数据。"

            table = format_table(rows, max_width=40)
            suffix = []
            if raw.get("limited"):
                suffix.append(f"⚠️ 结果已按安全上限截断，当前返回 {raw.get('row_count', len(rows))} 行")
            else:
                suffix.append(f"✅ 查询成功，共返回 {raw.get('row_count', len(rows))} 行")
            return table + "\n\n" + "\n".join(suffix)

        if tool_name == "call_api":
            parts = ["✅ API 调用完成"]
            if "status_code" in raw:
                parts.append(f"HTTP {raw['status_code']}")
            payload = raw.get("data")
            if isinstance(payload, dict):
                parts.append("")
                parts.append(format_kv(payload, title="返回数据"))
            elif isinstance(payload, list):
                parts.append("")
                parts.append(format_list(payload[:20]))
                if len(payload) > 20:
                    parts.append(f"\n... 还有 {len(payload) - 20} 项")
            elif payload is not None:
                parts.append("")
                parts.append(truncate(json.dumps(payload, ensure_ascii=False), 1200))
            return "\n".join(parts)

        return truncate(json.dumps(raw, ensure_ascii=False, indent=2), 2000)


_executor: ToolExecutor | None = None


def get_executor() -> ToolExecutor:
    global _executor
    if _executor is None:
        _executor = ToolExecutor()
    return _executor


def execute_tool(tool_name: str, arguments: dict[str, Any] | None = None, *, require_confirmation: bool = False) -> dict[str, Any]:
    return get_executor().execute(tool_name, arguments, require_confirmation=require_confirmation)
