# AI 工具权限与注册表
import json
import fnmatch
from pathlib import Path

try:
    import db as newapi_db
except Exception:
    newapi_db = None
from formatter import fmt_overview, fmt_channel_detail, fmt_slow_channels, fmt_health_score
try:
    from newapi_client import test_channel as api_test_channel, set_channel_status as api_set_channel_status
except Exception:
    api_test_channel = None
    api_set_channel_status = None

DATA_DIR = Path(__file__).parent / "data"
PERMISSIONS_PATH = DATA_DIR / "permissions.json"
REGISTRY_PATH = DATA_DIR / "tool_registry.json"

DEFAULT_PERMISSIONS = {
    "safe": [
        "get_*",
        "test_*"
    ],
    "confirm": [
        "enable_channel",
        "disable_channel",
        "batch_enable",
        "batch_disable"
    ],
    "forbidden": [
        "delete_channel",
        "update_channel",
        "create_channel",
        "backup_database",
        "restore_database"
    ]
}

DEFAULT_REGISTRY = {
    "version": "phase4",
    "tools": {}
}

DEFAULT_TOOL_DEFS = [
    {"name": "get_bot_capabilities", "description": "查看 AI 当前可用工具与权限"},
    {"name": "get_overview", "description": "查看最近 1 小时总览"},
    {"name": "get_channel_list", "description": "查看渠道列表"},
    {"name": "get_channel_detail", "description": "查看单个渠道详情，参数: channel_id"},
    {"name": "get_failed_channels", "description": "查看最近失败较多的渠道"},
    {"name": "get_slow_channels", "description": "查看慢渠道排行"},
    {"name": "get_model_stats", "description": "查看模型使用排行"},
    {"name": "get_model_channels", "description": "查看某模型挂载的渠道，参数: model_name"},
    {"name": "get_today_stats", "description": "查看今日统计"},
    {"name": "get_yesterday_stats", "description": "查看昨日统计"},
    {"name": "get_user_stats", "description": "查看用户排行"},
    {"name": "get_token_stats", "description": "查看 Token 排行"},
    {"name": "get_channel_health", "description": "查看渠道健康度，参数: channel_id"},
    {"name": "test_channel", "description": "测试单个渠道，参数: channel_id [model]"},
    {"name": "test_channels_batch", "description": "批量测试渠道，参数: id1,id2,... 最多 50 个"},
    {"name": "test_model_channels", "description": "测试某模型的所有启用渠道，参数: model_name"},
    {"name": "enable_channel", "description": "启用单个渠道，参数: channel_id"},
    {"name": "disable_channel", "description": "禁用单个渠道，参数: channel_id"},
    {"name": "batch_enable", "description": "批量启用渠道，参数: id1,id2,... 最多 50 个"},
    {"name": "batch_disable", "description": "批量禁用渠道，参数: id1,id2,... 最多 50 个"},
    {"name": "delete_channel", "description": "删除渠道（禁止）"},
    {"name": "update_channel", "description": "更新渠道（禁止）"},
    {"name": "create_channel", "description": "创建渠道（禁止）"},
    {"name": "backup_database", "description": "备份数据库（禁止）"},
    {"name": "restore_database", "description": "恢复数据库（禁止）"},
]


def _ensure_json(path: Path, default_data: dict):
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(default_data, indent=2, ensure_ascii=False), encoding="utf-8")


def _parse_ids(raw: str) -> list[int]:
    ids = []
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        ids.append(int(item))
    return ids


class PermissionManager:
    def __init__(self, path: Path = PERMISSIONS_PATH):
        self.path = path
        _ensure_json(self.path, DEFAULT_PERMISSIONS)
        self.data = json.loads(self.path.read_text(encoding="utf-8"))

    def reload(self):
        self.data = json.loads(self.path.read_text(encoding="utf-8"))

    def get_level(self, tool_name: str) -> str:
        for level in ("forbidden", "confirm", "safe"):
            for pattern in self.data.get(level, []):
                if fnmatch.fnmatch(tool_name, pattern):
                    return level
        return "forbidden"

    def is_allowed(self, tool_name: str) -> bool:
        return self.get_level(tool_name) != "forbidden"


class ToolRegistry:
    def __init__(self, permission_manager: PermissionManager, path: Path = REGISTRY_PATH):
        self.path = path
        self.permission_manager = permission_manager
        _ensure_json(self.path, DEFAULT_REGISTRY)
        self.data = json.loads(self.path.read_text(encoding="utf-8"))

    def reload(self):
        self.data = json.loads(self.path.read_text(encoding="utf-8"))

    def save(self):
        self.path.write_text(json.dumps(self.data, indent=2, ensure_ascii=False), encoding="utf-8")

    def register_tool(self, name: str, description: str, version: str = "phase4"):
        self.data.setdefault("tools", {})[name] = {
            "description": description,
            "permission": self.permission_manager.get_level(name),
            "version": version,
        }
        self.save()

    def auto_discover(self, tool_defs: list[dict], version: str = "phase4"):
        changed = False
        for item in tool_defs:
            name = item["name"]
            new_meta = {
                "description": item.get("description", ""),
                "permission": self.permission_manager.get_level(name),
                "version": version,
            }
            if self.data.setdefault("tools", {}).get(name) != new_meta:
                self.data["tools"][name] = new_meta
                changed = True
        if changed:
            self.save()

    def get_tools(self) -> dict:
        return self.data.get("tools", {})

    def build_system_prompt(self) -> str:
        lines = ["你是 NewAPI Guardian Bot 的 AI 大脑。你只能使用已注册工具，并严格遵守权限级别。"]
        for name, meta in sorted(self.get_tools().items()):
            lines.append(f"- {name} [{meta.get('permission','forbidden')}]: {meta.get('description','')}")
        return "\n".join(lines)


def get_openai_tools_schema() -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": "get_bot_capabilities",
                "description": "查看 AI 当前可用工具与权限",
                "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_overview",
                "description": "查看最近 1 小时总览",
                "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_channel_list",
                "description": "查看渠道列表",
                "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_channel_detail",
                "description": "查看单个渠道详情",
                "parameters": {"type": "object", "properties": {"channel_id": {"type": "integer"}}, "required": ["channel_id"], "additionalProperties": False},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_failed_channels",
                "description": "查看最近失败较多的渠道",
                "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_slow_channels",
                "description": "查看慢渠道排行",
                "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_model_stats",
                "description": "查看模型使用排行",
                "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_model_channels",
                "description": "查看某模型挂载的渠道",
                "parameters": {"type": "object", "properties": {"model_name": {"type": "string"}}, "required": ["model_name"], "additionalProperties": False},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_today_stats",
                "description": "查看今日统计",
                "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_yesterday_stats",
                "description": "查看昨日统计",
                "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_user_stats",
                "description": "查看用户排行",
                "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_token_stats",
                "description": "查看 Token 排行",
                "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_channel_health",
                "description": "查看渠道健康度",
                "parameters": {"type": "object", "properties": {"channel_id": {"type": "integer"}}, "required": ["channel_id"], "additionalProperties": False},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "test_channel",
                "description": "测试单个渠道",
                "parameters": {"type": "object", "properties": {"channel_id": {"type": "integer"}, "model": {"type": "string"}}, "required": ["channel_id"], "additionalProperties": False},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "test_channels_batch",
                "description": "批量测试渠道，最多 50 个",
                "parameters": {"type": "object", "properties": {"channel_ids": {"type": "array", "items": {"type": "integer"}, "maxItems": 50}}, "required": ["channel_ids"], "additionalProperties": False},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "test_model_channels",
                "description": "测试某模型的所有启用渠道",
                "parameters": {"type": "object", "properties": {"model_name": {"type": "string"}}, "required": ["model_name"], "additionalProperties": False},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "enable_channel",
                "description": "启用单个渠道",
                "parameters": {"type": "object", "properties": {"channel_id": {"type": "integer"}}, "required": ["channel_id"], "additionalProperties": False},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "disable_channel",
                "description": "禁用单个渠道",
                "parameters": {"type": "object", "properties": {"channel_id": {"type": "integer"}}, "required": ["channel_id"], "additionalProperties": False},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "batch_enable",
                "description": "批量启用渠道，最多 50 个",
                "parameters": {"type": "object", "properties": {"channel_ids": {"type": "array", "items": {"type": "integer"}, "maxItems": 50}}, "required": ["channel_ids"], "additionalProperties": False},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "batch_disable",
                "description": "批量禁用渠道，最多 50 个",
                "parameters": {"type": "object", "properties": {"channel_ids": {"type": "array", "items": {"type": "integer"}, "maxItems": 50}}, "required": ["channel_ids"], "additionalProperties": False},
            },
        },
    ]


def execute_tool(name: str, args: list[str]) -> str:
    try:
        if newapi_db is None and name.startswith(("get_", "test_")) and name != "get_bot_capabilities":
            return "❌ 运行环境缺少数据库依赖（如 pymysql），暂时无法执行该工具。"
        if api_test_channel is None and name.startswith("test_"):
            return "❌ 运行环境缺少 NewAPI 客户端依赖，暂时无法执行测试工具。"
        if api_set_channel_status is None and name in {"enable_channel", "disable_channel", "batch_enable", "batch_disable"}:
            return "❌ 运行环境缺少 NewAPI 客户端依赖，暂时无法执行状态变更工具。"
        if name == "get_bot_capabilities":
            pm = PermissionManager()
            reg = ToolRegistry(pm)
            reg.auto_discover(DEFAULT_TOOL_DEFS)
            lines = ["🤖 *Bot Capabilities*", ""]
            for tool_name, meta in sorted(reg.get_tools().items()):
                lines.append(f"- `{tool_name}` [{meta.get('permission')}] — {meta.get('description','')}")
            return "\n".join(lines)

        if name == "get_overview":
            stats = newapi_db.get_overview_stats(minutes=60)
            fail_ch = newapi_db.get_channel_failure_stats(minutes=60)
            fail_m = newapi_db.get_model_failure_stats(minutes=60)
            return fmt_overview(stats, fail_ch, fail_m)

        if name == "get_channel_list":
            channels = newapi_db.get_all_channels()
            lines = [f"🔌 *渠道列表*（共 {len(channels)} 个）", ""]
            for ch in channels[:50]:
                status = "🟢" if ch.get("status") == 1 else "🔴"
                lines.append(f"{status} ID:{ch['id']} `{ch.get('name') or ''}`")
            if len(channels) > 50:
                lines.append(f"\n... 还有 {len(channels) - 50} 个")
            return "\n".join(lines)

        if name == "get_channel_detail":
            if not args:
                return "❌ 缺少参数: channel_id"
            cid = int(args[0])
            ch = newapi_db.get_channel_by_id(cid)
            if not ch:
                return f"❌ 渠道 {cid} 不存在。"
            health_map = newapi_db.get_channel_health_scores(minutes=1440)
            if cid in health_map:
                ch = {**ch, "health_score": health_map[cid]["health_score"]}
            logs = newapi_db.get_channel_recent_logs(cid, minutes=60)
            return fmt_channel_detail(ch, logs)

        if name == "get_failed_channels":
            rows = newapi_db.get_channel_failure_stats(minutes=60)
            if not rows:
                return "✅ 最近 1 小时没有异常渠道。"
            lines = ["🚨 *异常渠道*（最近 1 小时）", ""]
            for row in rows[:15]:
                lines.append(f"- ID:{row['channel_id']} `{row.get('channel_name') or ''}` 失败 {row.get('fail_count',0)} 次")
            return "\n".join(lines)

        if name == "get_slow_channels":
            return fmt_slow_channels(newapi_db.get_slow_channels(minutes=60))

        if name == "get_model_stats":
            rows = newapi_db.get_model_usage_stats(0, 20)
            lines = ["📈 *模型使用排行*", ""]
            for i, row in enumerate(rows, 1):
                lines.append(f"{i}. `{row.get('model_name','')}` — {row.get('call_count',0)} 次")
            return "\n".join(lines)

        if name == "get_model_channels":
            if not args:
                return "❌ 缺少参数: model_name"
            model_name = " ".join(args)
            rows = newapi_db.get_model_channels(model_name)
            if not rows:
                return f"❌ 没有找到支持 `{model_name}` 的启用渠道。"
            lines = [f"🧩 *模型渠道* `{model_name}`", ""]
            for row in rows:
                lines.append(f"- ID:{row['id']} `{row.get('name') or ''}`")
            return "\n".join(lines)

        if name == "get_today_stats":
            stats = newapi_db.get_today_stats()
            return (
                "📅 *今日统计*\n\n"
                f"请求: {stats.get('total_calls', 0)}\n"
                f"Quota: {stats.get('total_quota', 0)}\n"
                f"Prompt: {stats.get('total_prompt', 0)}\n"
                f"Completion: {stats.get('total_completion', 0)}"
            )

        if name == "get_yesterday_stats":
            stats = newapi_db.get_yesterday_stats()
            return (
                "📆 *昨日统计*\n\n"
                f"请求: {stats.get('total_calls', 0)}\n"
                f"Quota: {stats.get('total_quota', 0)}\n"
                f"Prompt: {stats.get('total_prompt', 0)}\n"
                f"Completion: {stats.get('total_completion', 0)}"
            )

        if name == "get_user_stats":
            rows = newapi_db.get_user_usage_stats(10)
            lines = ["👤 *用户排行*", ""]
            for i, row in enumerate(rows, 1):
                lines.append(f"{i}. `{row.get('username') or 'N/A'}` — {row.get('calls',0)} 次")
            return "\n".join(lines)

        if name == "get_token_stats":
            rows = newapi_db.get_token_usage_stats(10)
            lines = ["🔑 *Token 排行*", ""]
            for i, row in enumerate(rows, 1):
                lines.append(f"{i}. `{row.get('token_name') or 'N/A'}` — {row.get('calls',0)} 次")
            return "\n".join(lines)

        if name == "get_channel_health":
            if not args:
                return "❌ 缺少参数: channel_id"
            cid = int(args[0])
            health_map = newapi_db.get_channel_health_scores(minutes=1440)
            row = health_map.get(cid)
            if not row:
                return f"❌ 渠道 {cid} 不存在或暂无数据。"
            return (
                f"💚 *渠道健康度*\n\n"
                f"渠道: `{row.get('name') or ''}` (ID:{cid})\n"
                f"健康度: {fmt_health_score(row.get('health_score', 0))}\n"
                f"成功/总数: {row.get('success_count',0)}/{row.get('total_count',0)}\n"
                f"失败: {row.get('fail_count',0)}\n"
                f"平均响应: {row.get('avg_time',0):.1f}s"
            )

        if name == "test_channel":
            if not args:
                return "❌ 缺少参数: channel_id"
            cid = int(args[0])
            ch = newapi_db.get_channel_by_id(cid)
            if not ch:
                return f"❌ 渠道 {cid} 不存在。"
            model = " ".join(args[1:]) if len(args) > 1 else (ch.get("test_model", "") or "")
            result = api_test_channel(cid, model)
            return (
                f"🧪 *渠道测试结果*\n\n"
                f"渠道: `{ch.get('name') or ''}` (ID:{cid})\n"
                f"结果: {'成功' if result.get('success') else '失败'}\n"
                f"耗时: {result.get('time', 0):.1f}s\n"
                f"信息: {str(result.get('message',''))[:200]}"
            )

        if name == "test_channels_batch":
            if not args:
                return "❌ 缺少参数: id1,id2,..."
            ids = _parse_ids(args[0])
            if len(ids) > 50:
                return "❌ 批量操作最多 50 个渠道。"
            lines = ["🧪 *批量测试结果*", ""]
            ok = 0
            fail = 0
            for cid in ids:
                ch = newapi_db.get_channel_by_id(cid)
                if not ch:
                    lines.append(f"❌ ID:{cid} 不存在")
                    fail += 1
                    continue
                result = api_test_channel(cid, ch.get("test_model", "") or "")
                if result.get("success"):
                    ok += 1
                else:
                    fail += 1
                icon = "✅" if result.get("success") else "❌"
                lines.append(f"{icon} ID:{cid} `{ch.get('name') or ''}` {result.get('time',0):.1f}s")
            lines.append(f"\n汇总: 成功 {ok} / 失败 {fail}")
            return "\n".join(lines)

        if name == "test_model_channels":
            if not args:
                return "❌ 缺少参数: model_name"
            model_name = " ".join(args)
            rows = newapi_db.get_model_channels(model_name)
            if not rows:
                return f"❌ 没有找到支持 `{model_name}` 的启用渠道。"
            lines = [f"🧪 *模型测试* `{model_name}`", ""]
            ok = 0
            fail = 0
            for row in rows:
                result = api_test_channel(row["id"], model_name)
                if result.get("success"):
                    ok += 1
                else:
                    fail += 1
                icon = "✅" if result.get("success") else "❌"
                lines.append(f"{icon} ID:{row['id']} `{row.get('name') or ''}` {result.get('time',0):.1f}s")
            lines.append(f"\n汇总: 成功 {ok} / 失败 {fail}")
            return "\n".join(lines)

        if name in {"enable_channel", "disable_channel"}:
            if not args:
                return "❌ 缺少参数: channel_id"
            cid = int(args[0])
            ch = newapi_db.get_channel_by_id(cid)
            if not ch:
                return f"❌ 渠道 {cid} 不存在。"
            status = 1 if name == "enable_channel" else 2
            result = api_set_channel_status(cid, status)
            ok = bool(result.get("success"))
            action = "启用" if status == 1 else "禁用"
            return f"{'✅' if ok else '❌'} {action}渠道 ID:{cid} `{ch.get('name') or ''}`：{result.get('message', '')}"

        if name in {"batch_enable", "batch_disable"}:
            if not args:
                return "❌ 缺少参数: id1,id2,..."
            ids = _parse_ids(args[0])
            if len(ids) > 50:
                return "❌ 批量操作最多 50 个渠道。"
            status = 1 if name == "batch_enable" else 2
            action = "启用" if status == 1 else "禁用"
            lines = [f"🔧 *批量{action}结果*", ""]
            ok = 0
            fail = 0
            for cid in ids:
                ch = newapi_db.get_channel_by_id(cid)
                if not ch:
                    lines.append(f"❌ ID:{cid} 不存在")
                    fail += 1
                    continue
                result = api_set_channel_status(cid, status)
                success = bool(result.get("success"))
                if success:
                    ok += 1
                else:
                    fail += 1
                icon = "✅" if success else "❌"
                lines.append(f"{icon} ID:{cid} `{ch.get('name') or ''}` {result.get('message','')}")
            lines.append(f"\n汇总: 成功 {ok} / 失败 {fail}")
            return "\n".join(lines)
        
        # Agent 专属工具
        if name == "remember_fact":
            if len(args) < 1:
                return "❌ 缺少参数: fact"
            fact = args[0]
            category = args[1] if len(args) > 1 else "general"
            # 这里只返回成功消息，实际保存由 agent_brain.py 处理
            return f"✅ 已记住: {fact} (分类: {category})"
        
        if name == "update_user_preference":
            if len(args) < 2:
                return "❌ 缺少参数: key, value"
            key = args[0]
            value = args[1]
            # 这里只返回成功消息，实际保存由 agent_brain.py 处理
            return f"✅ 已更新偏好: {key} = {value}"

        return f"❌ 未知工具 `{name}`。可用工具请用 `get_bot_capabilities` 查看。"
    except ValueError:
        return "❌ 参数格式错误。"
    except Exception as e:
        return f"❌ 工具执行失败: {str(e)[:300]}"
