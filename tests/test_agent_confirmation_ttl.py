import time
import unittest

import agent_handler


class AgentConfirmationTtlTests(unittest.TestCase):
    def setUp(self):
        agent_handler._pending_confirmations.clear()

    def tearDown(self):
        agent_handler._pending_confirmations.clear()

    def test_pop_pending_confirmation_returns_and_removes_valid_item(self):
        cid = agent_handler._store_pending_confirmation("call_api", {"method": "POST"})
        pending = agent_handler._pop_pending_confirmation(cid, now=time.time())
        self.assertIsNotNone(pending)
        self.assertEqual(pending["tool"], "call_api")
        self.assertNotIn(cid, agent_handler._pending_confirmations)

    def test_pop_pending_confirmation_rejects_expired_item(self):
        cid = "expired123"
        agent_handler._pending_confirmations[cid] = {
            "tool": "call_api",
            "arguments": {},
            "created_at": 1000,
        }
        pending = agent_handler._pop_pending_confirmation(
            cid,
            now=1000 + agent_handler.PENDING_CONFIRMATION_TTL_SECONDS + 1,
        )
        self.assertIsNone(pending)
        self.assertNotIn(cid, agent_handler._pending_confirmations)


if __name__ == "__main__":
    unittest.main()
