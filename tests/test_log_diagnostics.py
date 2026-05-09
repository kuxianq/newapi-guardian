import unittest

from core.log_diagnostics import parse_newapi_log_lines, parse_openclaw_log_lines


class RuntimeLogDiagnosticsTests(unittest.TestCase):
    def test_parse_newapi_channel_error(self):
        lines = [
            '[ERR] 2026/05/09 - 06:45:14 | abc | channel error (channel #151, status code: 403): 预扣费额度失败, 用户剩余额度不足 (request id: req-1)',
        ]
        events = parse_newapi_log_lines(lines)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["channel_id"], 151)
        self.assertEqual(events[0]["status_code"], 403)
        self.assertEqual(events[0]["error_type"]["type"], "prepay_failed")

    def test_parse_openclaw_fallback_event(self):
        line = '{"1":{"event":"model_fallback_decision","requestedModel":"gpt-5.5","candidateModel":"claude-opus-4-7","status":401,"errorPreview":"403 预扣费额度失败"}}'
        events = parse_openclaw_log_lines([line], model="gpt-5.5")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["failed_model"], "gpt-5.5")
        self.assertEqual(events[0]["requested_model"], "gpt-5.5")
        self.assertEqual(events[0]["candidate_model"], "claude-opus-4-7")
        self.assertEqual(events[0]["error_type"]["type"], "prepay_failed")


if __name__ == "__main__":
    unittest.main()
