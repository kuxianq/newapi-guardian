"""核心 HTTP 客户端层 - 通用 API 调用能力"""
import requests
from typing import Any
from config import NEWAPI_BASE_URL, NEWAPI_ADMIN_TOKEN, NEWAPI_ADMIN_USER_ID


class HTTPClient:
    """通用 HTTP 客户端"""
    
    def __init__(self, base_url: str = None, api_key: str = None, timeout: int = 30):
        self.base_url = base_url or NEWAPI_BASE_URL
        self.api_key = api_key or NEWAPI_ADMIN_TOKEN
        self.timeout = timeout
        self.session = requests.Session()
        
        # 设置默认 headers
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        if NEWAPI_ADMIN_USER_ID:
            headers["New-Api-User"] = str(NEWAPI_ADMIN_USER_ID)
        self.session.headers.update(headers)

    @staticmethod
    def _extract_error(response_data: Any, fallback_text: str) -> str:
        """从各种响应体结构里提取错误信息。"""
        if isinstance(response_data, dict):
            return (
                response_data.get("message")
                or response_data.get("error")
                or response_data.get("msg")
                or fallback_text
            )
        if isinstance(response_data, list):
            return fallback_text or "请求失败"
        if response_data is None:
            return fallback_text or "请求失败"
        return str(response_data)
    
    def request(self, method: str, endpoint: str, data: dict = None, params: dict = None) -> dict:
        """
        通用 HTTP 请求
        
        Args:
            method: HTTP 方法（GET/POST/PUT/DELETE）
            endpoint: API 端点（如 /api/channel/1）
            data: 请求体（可选）
            params: URL 参数（可选）
        
        Returns:
            {
                "success": bool,
                "status_code": int,
                "data": dict | list | None,
                "error": str | None
            }
        """
        method = method.upper()
        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        
        try:
            response = self.session.request(
                method=method,
                url=url,
                json=data,
                params=params,
                timeout=self.timeout
            )
            
            # 尝试解析 JSON
            try:
                response_data = response.json()
            except Exception:
                response_data = {"text": response.text}

            error = None
            if response.status_code >= 400:
                error = self._extract_error(response_data, response.text)
            
            return {
                "success": response.status_code < 400,
                "status_code": response.status_code,
                "data": response_data,
                "error": error,
            }
        
        except requests.exceptions.Timeout:
            return {
                "success": False,
                "status_code": 0,
                "data": None,
                "error": "请求超时"
            }
        except requests.exceptions.ConnectionError:
            return {
                "success": False,
                "status_code": 0,
                "data": None,
                "error": "连接失败"
            }
        except Exception as e:
            return {
                "success": False,
                "status_code": 0,
                "data": None,
                "error": str(e)
            }
    
    def get(self, endpoint: str, params: dict = None) -> dict:
        """GET 请求"""
        return self.request("GET", endpoint, params=params)
    
    def post(self, endpoint: str, data: dict = None) -> dict:
        """POST 请求"""
        return self.request("POST", endpoint, data=data)
    
    def put(self, endpoint: str, data: dict = None) -> dict:
        """PUT 请求"""
        return self.request("PUT", endpoint, data=data)
    
    def delete(self, endpoint: str) -> dict:
        """DELETE 请求"""
        return self.request("DELETE", endpoint)


# 全局客户端实例
_client = None

def get_client() -> HTTPClient:
    """获取全局 HTTP 客户端实例"""
    global _client
    if _client is None:
        _client = HTTPClient()
    return _client


def call_api(method: str, endpoint: str, data: dict = None, params: dict = None) -> dict:
    """
    AI 专用 API 调用器
    
    Args:
        method: HTTP 方法（GET/POST/PUT/DELETE）
        endpoint: API 端点
        data: 请求体（可选）
        params: URL 参数（可选）
    
    Returns:
        {
            "success": bool,
            "status_code": int,
            "data": dict | list | None,
            "error": str | None
        }
    """
    client = get_client()
    return client.request(method, endpoint, data, params)


# 向后兼容：保留一些常用的快捷方法
def test_channel(channel_id: int, model: str = None) -> dict:
    """快捷方法：测试渠道"""
    data = {"id": channel_id}
    if model:
        data["model"] = model
    return call_api("POST", "/api/channel/test", data=data)


def set_channel_status(channel_id: int, status: int) -> dict:
    """快捷方法：设置渠道状态"""
    return call_api("PUT", f"/api/channel/{channel_id}/status", data={"status": status})
