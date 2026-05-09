"""工具执行器 - 统一路由、权限检查和结果格式化"""
from __future__ import annotations

import logging
from typing import Any

from core.database import execute_readonly_sql
from core.diagnostics import diagnose_failure_scope
from core.http_client import call_api
from core.newapi_version import detect_newapi_version
from skills.newapi import get_newapi_docs
from tools_new.formatter import format_tool_output
from tools_new.registry import get_registry

logger = logging.getLogger("guardian.tools.executor")


class ToolExecutionError(Exception):
    """工具执行异常"""


class ToolExecutor:
    """统一工具执行器"""

    def __init__(self):
        self.registry = get_registry()

    def get_permission(self, tool_name: str, arguments: dict[str, Any] | None = None) -> str:
        return self.registry.permission_for(tool_name, arguments)

    def execute(self, tool_name: str, arguments: dict[str, Any] | None = None, *, require_confirmation: bool = False) -> dict[str, Any]:
        arguments = arguments or {}
        tool = self.registry.get_tool(tool_name)
        if not tool:
            return self._result(False, tool_name, arguments, error=f"未知工具: {tool_name}")

        permission = self.registry.permission_for(tool_name, arguments)
        if permission == "forbidden":
            return self._result(False, tool_name, arguments, error=f"工具 {tool_name} 当前调用被禁止", permission=permission)

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
            elif tool_name == "diagnose_newapi_failure":
                raw = diagnose_failure_scope(
                    model=arguments.get("model") or None,
                    channel_id=arguments.get("channel_id"),
                    minutes=int(arguments.get("minutes", 60)),
                    include_recent=bool(arguments.get("include_recent", True)),
                )
            elif tool_name == "get_newapi_runtime_info":
                raw = detect_newapi_version()
            elif tool_name == "get_newapi_docs":
                raw = get_newapi_docs(arguments.get("topic"))
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
                output=format_tool_output(tool_name, raw),
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
            "permission": permission or self.get_permission(tool_name, arguments),
            "needs_confirmation": needs_confirmation,
            "data": data,
            "output": output or (f"❌ {error}" if error else ""),
            "error": error,
        }


_executor: ToolExecutor | None = None


def get_executor() -> ToolExecutor:
    global _executor
    if _executor is None:
        _executor = ToolExecutor()
    return _executor


def execute_tool(tool_name: str, arguments: dict[str, Any] | None = None, *, require_confirmation: bool = False) -> dict[str, Any]:
    return get_executor().execute(tool_name, arguments, require_confirmation=require_confirmation)
