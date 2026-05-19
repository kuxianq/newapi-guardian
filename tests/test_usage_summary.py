import unittest
from unittest.mock import patch

from core.usage_summary import get_usage_summary
from tools_new.executor import execute_tool


class UsageSummaryTests(unittest.TestCase):
    def test_usage_summary_totals(self):
        with patch("core.usage_summary.query") as mock_query:
            mock_query.return_value = [{
                "total_calls": 2,
                "total_prompt_tokens": 100,
                "total_completion_tokens": 50,
                "total_tokens": 150,
                "total_quota": 250000,
                "avg_time": 1.2,
            }]
            result = get_usage_summary(scope="all")
            self.assertTrue(result["success"])
            self.assertEqual(result["scope"], "all")
            self.assertEqual(result["totals"]["total_tokens"], 150)
            self.assertEqual(result["groups"], [])

    def test_usage_summary_group_by_model(self):
        with patch("core.usage_summary.query") as mock_query:
            mock_query.side_effect = [
                [{"total_calls": 3, "total_prompt_tokens": 300, "total_completion_tokens": 120, "total_tokens": 420, "total_quota": 500000, "avg_time": 2}],
                [{"name": "gpt-5.5", "calls": 3, "prompt_tokens": 300, "completion_tokens": 120, "total_tokens": 420, "quota": 500000, "avg_time": 2}],
            ]
            result = get_usage_summary(scope="last_hours", hours=24, group_by="model", limit=5)
            self.assertEqual(result["scope"], "last_24_hours")
            self.assertEqual(result["group_by"], "model")
            self.assertEqual(result["groups"][0]["name"], "gpt-5.5")
            self.assertEqual(result["limit"], 5)

    def test_executor_routes_usage_summary(self):
        with patch("tools_new.executor.get_usage_summary") as mock_summary:
            mock_summary.return_value = {
                "success": True,
                "scope": "today",
                "group_by": "none",
                "limit": 10,
                "totals": {
                    "total_calls": 1,
                    "total_prompt_tokens": 10,
                    "total_completion_tokens": 5,
                    "total_tokens": 15,
                    "total_quota": 0,
                },
                "groups": [],
            }
            result = execute_tool("get_usage_summary", {"scope": "today"})
            self.assertTrue(result["success"])
            self.assertIn("总 Tokens", result["output"])
            mock_summary.assert_called_once()


if __name__ == "__main__":
    unittest.main()
