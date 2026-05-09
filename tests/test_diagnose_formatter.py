import unittest

from tools_new.formatter import format_tool_output


class DiagnoseFormatterTests(unittest.TestCase):
    def test_most_suspicious_channel_from_runtime(self):
        raw = {
            "success": True,
            "scope": {"model": "gpt-5.5", "channel_id": None, "minutes": 60},
            "summary": {"total": 10, "failed": 0, "fail_rate": 0},
            "channels": [],
            "balance_suspects": [],
            "recent_failures": [],
            "runtime_failures": {
                "newapi_events": [
                    {"channel_id": 266, "channel_name": "chan", "status_code": 403, "content": "预扣费额度失败", "error_type": {"label": "预扣费额度失败"}}
                ],
                "openclaw_events": [],
            },
            "hypothesis": [],
        }
        text = format_tool_output("diagnose_newapi_failure", raw)
        self.assertIn("最可疑渠道: #266", text)
        self.assertIn("预扣费额度失败", text)


if __name__ == "__main__":
    unittest.main()
