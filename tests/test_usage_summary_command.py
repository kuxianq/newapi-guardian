import unittest

from handlers.usage import parse_usage_summary_args


class UsageSummaryCommandParseTests(unittest.TestCase):
    def test_default_args(self):
        self.assertEqual(
            parse_usage_summary_args([]),
            {"scope": "today", "hours": None, "group_by": "none", "limit": 10},
        )

    def test_all_token_limit(self):
        self.assertEqual(
            parse_usage_summary_args(["all", "token", "20"]),
            {"scope": "all", "hours": None, "group_by": "token", "limit": 20},
        )

    def test_24h_model(self):
        self.assertEqual(
            parse_usage_summary_args(["24h", "model"]),
            {"scope": "last_hours", "hours": 24, "group_by": "model", "limit": 10},
        )

    def test_last_hours_user(self):
        self.assertEqual(
            parse_usage_summary_args(["last_hours", "72", "user", "5"]),
            {"scope": "last_hours", "hours": 72, "group_by": "user", "limit": 5},
        )


if __name__ == "__main__":
    unittest.main()
