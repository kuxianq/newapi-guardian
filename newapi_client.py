"""NewAPI Guardian Bot - NewAPI 管理 API 客户端"""
import logging
import urllib.request
import urllib.error
import json
import asyncio
from config import NEWAPI_BASE_URL, NEWAPI_ADMIN_TOKEN, NEWAPI_ADMIN_USER_ID
from async_utils import run_many_blocking

logger = logging.getLogger("guardian.api")


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {NEWAPI_ADMIN_TOKEN}",
        "New-Api-User": str(NEWAPI_ADMIN_USER_ID),
        "Content-Type": "application/json",
    }


def _request(method: str, path: str, data: dict | None = None, timeout: int = 30) -> dict:
    url = f"{NEWAPI_BASE_URL}{path}"
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=_headers(), method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body_text = e.read().decode("utf-8", errors="replace")[:500]
        logger.error(f"API {method} {path} -> {e.code}: {body_text}")
        try:
            return json.loads(body_text)
        except Exception:
            return {"success": False, "message": f"HTTP {e.code}: {body_text[:200]}"}
    except Exception as e:
        logger.error(f"API {method} {path} error: {e}")
        return {"success": False, "message": str(e)}


def test_channel(channel_id: int, model: str = "") -> dict:
    """测试单个渠道,返回 {success, time, message}"""
    import urllib.parse
    path = f"/api/channel/test/{channel_id}"
    if model:
        path += f"?model={urllib.parse.quote(model)}"
    result = _request("GET", path, timeout=60)
    return {
        "success": result.get("success", False),
        "time": result.get("time", 0),
        "message": result.get("message", ""),
    }


async def async_test_channels_batch(channel_ids: list[int], model: str = "", max_workers: int = 10) -> dict:
    """批量并发测试多个渠道（异步入口，供 Bot 事件循环内调用）。"""
    def _test(channel_id: int) -> dict:
        logger.info(f"Testing channel {channel_id}...")
        result = test_channel(channel_id, model)
        result["id"] = channel_id
        return result

    results = await run_many_blocking(channel_ids, _test, max_workers=max_workers)

    success_count = sum(1 for result in results if result.get("success"))
    return {
        "total": len(channel_ids),
        "success_count": success_count,
        "failed_count": len(channel_ids) - success_count,
        "results": results,
    }


def test_channels_batch(channel_ids: list[int], model: str = "", max_workers: int = 10) -> dict:
    """批量并发测试多个渠道（同步入口；事件循环内请 await async_test_channels_batch）。"""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(async_test_channels_batch(channel_ids, model, max_workers=max_workers))

    logger.warning("test_channels_batch called inside a running event loop; falling back to sequential tests")
    results = []
    for channel_id in channel_ids:
        result = test_channel(channel_id, model)
        result["id"] = channel_id
        results.append(result)
    success_count = sum(1 for result in results if result.get("success"))
    return {
        "total": len(channel_ids),
        "success_count": success_count,
        "failed_count": len(channel_ids) - success_count,
        "results": results,
    }


def set_channel_status(channel_id: int, status: int) -> dict:
    """启用(1)/禁用(2)渠道

    修复:NewAPI 没有单独的 status 端点,需要通过 PUT /api/channel/ 更新整个渠道对象
    """
    # 先获取当前渠道信息
    channel = get_channel(channel_id)
    if not channel.get("success", False):
        return {"success": False, "message": "获取渠道信息失败"}

    # 更新 status 字段
    channel_data = channel.get("data", {})
    channel_data["id"] = channel_id
    channel_data["status"] = status

    # 调用更新接口
    return update_channel(channel_id, channel_data)


def get_channel_list(page: int = 0, page_size: int = 100) -> dict:
    """获取渠道列表"""
    return _request("GET", f"/api/channel/?p={page}&page_size={page_size}")


def update_all_balances() -> dict:
    """更新所有渠道余额"""
    return _request("GET", "/api/channel/update_balance")


def get_channel(channel_id: int) -> dict:
    """获取单个渠道详情"""
    return _request("GET", f"/api/channel/{channel_id}")


def create_channel(channel_data: dict) -> dict:
    """创建新渠道

    channel_data 示例:
    {
        "type": 1,  # 渠道类型
        "name": "渠道名称",
        "base_url": "https://api.example.com",
        "key": "sk-xxx",  # API Key
        "models": "gpt-4,gpt-3.5-turbo",  # 逗号分隔
        "group": "default",
        "priority": 0,
        "weight": 0,
        "status": 1,  # 1=启用, 2=禁用
        "auto_ban": 1,  # 1=启用自动禁用
    }
    """
    return _request("POST", "/api/channel/", data=channel_data)


def update_channel(channel_id: int, channel_data: dict) -> dict:
    """更新渠道信息

    channel_data: 必须包含 id 字段和要更新的字段
    """
    if "id" not in channel_data:
        channel_data["id"] = channel_id
    return _request("PUT", "/api/channel/", data=channel_data)


def delete_channel(channel_id: int) -> dict:
    """删除渠道"""
    return _request("DELETE", f"/api/channel/{channel_id}")
