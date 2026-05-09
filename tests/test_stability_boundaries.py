import unittest
from unittest.mock import AsyncMock, Mock, patch

from telegram.error import BadRequest

from tools_new.executor import execute_tool
from tools_new.registry import get_registry
from tg_safe import safe_reply, safe_edit


class ToolBoundaryTests(unittest.TestCase):
    def test_readonly_api_get_is_safe(self):
        registry = get_registry()
        args = {"method": "GET", "endpoint": "/api/channel/1"}
        self.assertEqual(registry.permission_for("call_api", args), "safe")
        self.assertFalse(registry.needs_confirmation("call_api", args))

    def test_mutating_api_needs_confirmation(self):
        registry = get_registry()
        args = {"method": "PUT", "endpoint": "/api/channel/1/status", "data": {"status": 2}}
        self.assertEqual(registry.permission_for("call_api", args), "confirm")
        self.assertTrue(registry.needs_confirmation("call_api", args))

    def test_non_api_endpoint_forbidden(self):
        registry = get_registry()
        args = {"method": "GET", "endpoint": "http://example.com"}
        self.assertEqual(registry.permission_for("call_api", args), "forbidden")

    def test_confirm_required_before_mutating_api_execution(self):
        result = execute_tool("call_api", {"method": "PUT", "endpoint": "/api/channel/1/status"})
        self.assertFalse(result["success"])
        self.assertTrue(result["needs_confirmation"])
        self.assertEqual(result["permission"], "confirm")

    def test_forbidden_endpoint_not_executed(self):
        result = execute_tool("call_api", {"method": "GET", "endpoint": "http://example.com"})
        self.assertFalse(result["success"])
        self.assertFalse(result["needs_confirmation"])
        self.assertEqual(result["permission"], "forbidden")


class TelegramSafeTests(unittest.IsolatedAsyncioTestCase):
    async def test_safe_reply_falls_back_to_plain_text_on_markdown_parse_error(self):
        message = Mock()
        message.reply_text = AsyncMock(side_effect=[BadRequest("Can't parse entities"), "ok"])

        result = await safe_reply(message, "bad_markdown")

        self.assertEqual(result, "ok")
        self.assertEqual(message.reply_text.await_count, 2)
        self.assertEqual(message.reply_text.await_args_list[0].kwargs["parse_mode"], "Markdown")
        self.assertIsNone(message.reply_text.await_args_list[1].kwargs["parse_mode"])

    async def test_safe_edit_falls_back_to_new_message_when_edit_fails(self):
        query = Mock()
        query.edit_message_text = AsyncMock(side_effect=BadRequest("Message is not modified"))
        query.message = Mock()
        query.message.reply_text = AsyncMock(return_value="new")

        result = await safe_edit(query, "same text")

        self.assertEqual(result, "new")
        query.message.reply_text.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
