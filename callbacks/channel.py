"""Channel-related callback handlers: test_all / test_<id> / toggle_<id>."""
from __future__ import annotations

from typing import Any, Awaitable, Callable

import db as newapi_db
from async_utils import run_blocking, run_many_blocking
from formatter import safe_text, truncate
from newapi_client import (
    set_channel_status as api_set_channel_status,
    test_channel as api_test_channel,
)
from tg_safe import safe_edit


SafeEditFn = Callable[..., Awaitable[Any]]


async def handle_channel_callback(q, data: str) -> tuple[str | None, bool]:
    """Handle channel callbacks. Returns (text, handled)."""
    if data == "test_all":
        await safe_edit(q, "🧪 正在并发测试全部启用渠道，请稍候...")
        channels = newapi_db.get_enabled_channels()
        results = await run_many_blocking(
            channels,
            lambda ch: (ch, api_test_channel(ch["id"], ch.get("test_model", "") or "")),
            max_workers=10,
        )
        ok_count = sum(1 for _, r in results if r["success"])
        fail_count = len(results) - ok_count
        lines = [f"🧪 *全量渠道测试*\n", f"✅ 成功: {ok_count} | ❌ 失败: {fail_count}\n"]
        failed = [(ch, r) for ch, r in results if not r["success"]]
        if failed:
            lines.append("*失败渠道:*")
            for ch, r in failed:
                name = truncate(ch.get("name", ""), 25)
                lines.append(f"  ❌ `{name}` (ID:{ch['id']}) {r.get('time',0):.1f}s")
        passed = [(ch, r) for ch, r in results if r["success"]]
        if passed:
            lines.append(f"\n*成功渠道 ({len(passed)}个):*")
            for ch, r in passed[:15]:
                name = truncate(ch.get("name", ""), 25)
                lines.append(f"  ✅ `{name}` (ID:{ch['id']}) {r.get('time',0):.1f}s")
            if len(passed) > 15:
                lines.append(f"  ... 还有 {len(passed)-15} 个")
        return "\n".join(lines), True

    if data.startswith("test_") and not data.startswith("test_all") and not data.startswith("test_prompt") and not data.startswith("test_model_prompt"):
        cid_str = data.replace("test_", "")
        try:
            cid = int(cid_str)
        except ValueError:
            return "❌ 无效渠道 ID", True
        ch = newapi_db.get_channel_by_id(cid)
        if not ch:
            return f"❌ 渠道 {cid} 不存在。", True
        await safe_edit(q, f"🧪 正在测试渠道 {cid}...")
        result = await run_blocking(api_test_channel, cid, ch.get("test_model", ""))
        icon = "✅" if result["success"] else "❌"
        text = (
            f"{icon} *渠道测试结果*\n\n"
            f"渠道: `{safe_text(ch.get('name',''))}` (ID:{cid})\n"
            f"结果: {'成功' if result['success'] else '失败'}\n"
            f"耗时: {result.get('time', 0):.1f}s"
        )
        if result.get("message"):
            text += f"\n信息: {safe_text(str(result['message'])[:100])}"
        return text, True

    if data.startswith("toggle_"):
        cid_str = data.replace("toggle_", "")
        try:
            cid = int(cid_str)
        except ValueError:
            return "❌ 无效渠道 ID", True
        ch = newapi_db.get_channel_by_id(cid)
        if not ch:
            return f"❌ 渠道 {cid} 不存在。", True
        new_status = 2 if ch.get("status") == 1 else 1
        result = api_set_channel_status(cid, new_status)
        if result.get("success"):
            icon = "🟢" if new_status == 1 else "🔴"
            action = "启用" if new_status == 1 else "禁用"
            return f"{icon} 渠道 `{safe_text(ch.get('name',''))}` (ID:{cid}) 已{action}。", True
        return f"❌ 操作失败: {result.get('message', '')}", True

    return None, False
