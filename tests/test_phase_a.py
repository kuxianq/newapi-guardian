import asyncio
import unittest
from unittest.mock import patch

import agent_handler
import newapi_client


class PhaseAStabilityTests(unittest.TestCase):
    def test_disable_failed_callback_prefix_parsing(self):
        data = "confirm_disable_failed_5_1,2,3"
        rest = data.removeprefix("confirm_disable_failed_")
        threshold_str, ids_str = rest.split("_", 1)
        self.assertEqual(int(threshold_str), 5)
        self.assertEqual([int(x) for x in ids_str.split(",") if x], [1, 2, 3])

    def test_agent_confirmation_callback_data_is_short(self):
        agent_handler._pending_confirmations.clear()
        confirmation_id = agent_handler._store_pending_confirmation("dangerous_tool", {"payload": "x" * 500})
        callback_data = f"agent_confirm:{confirmation_id}"
        self.assertLessEqual(len(callback_data.encode("utf-8")), 64)
        self.assertEqual(agent_handler._pending_confirmations[confirmation_id]["tool"], "dangerous_tool")

    def test_sync_batch_inside_loop_does_not_leak_coroutine(self):
        def fake_test_channel(channel_id, model=""):
            return {"success": channel_id % 2 == 1, "time": 0.1, "message": model}

        async def run():
            return newapi_client.test_channels_batch([1, 2], "m")

        with patch.object(newapi_client, "test_channel", fake_test_channel):
            result = asyncio.run(run())

        self.assertEqual(result["success_count"], 1)
        self.assertEqual(result["failed_count"], 1)
        self.assertEqual([item["id"] for item in result["results"]], [1, 2])

    def test_async_batch_helper(self):
        def fake_test_channel(channel_id, model=""):
            return {"success": True, "time": 0.1, "message": model}

        with patch.object(newapi_client, "test_channel", fake_test_channel):
            result = asyncio.run(newapi_client.async_test_channels_batch([3, 4], "m", max_workers=2))

        self.assertEqual(result["total"], 2)
        self.assertEqual(result["success_count"], 2)
        self.assertEqual([item["id"] for item in result["results"]], [3, 4])


if __name__ == "__main__":
    unittest.main()
