import unittest

from core.diagnostics import classify_error
from core.newapi_version import _find_version
from skills.newapi import get_newapi_docs
from tools_new.executor import execute_tool
from tools_new.registry import get_registry


class DiagnosticsLogicTests(unittest.TestCase):
    def test_classify_balance_error(self):
        result = classify_error("403 账户余额过低不足以支持本次请求")
        self.assertEqual(result["type"], "balance_insufficient")

    def test_classify_prepay_error(self):
        result = classify_error("403 预扣费额度失败, 用户剩余额度不足")
        self.assertEqual(result["type"], "prepay_failed")

    def test_find_version_nested_payload(self):
        payload = {"data": {"version": "v0.6.1"}}
        self.assertEqual(_find_version(payload), "v0.6.1")


class DocsAndRegistryTests(unittest.TestCase):
    def test_get_newapi_docs_topic(self):
        docs = get_newapi_docs("quota")
        self.assertTrue(docs["success"])
        self.assertEqual(docs["topic"], "quota")
        self.assertIn("quota", docs["topics"])

    def test_registry_has_new_tools(self):
        registry = get_registry()
        for name in ["diagnose_newapi_failure", "get_newapi_runtime_info", "get_newapi_docs"]:
            self.assertIsNotNone(registry.get_tool(name))
            self.assertEqual(registry.permission_for(name, {}), "safe")

    def test_get_docs_tool_executes(self):
        result = execute_tool("get_newapi_docs", {"topic": "api"})
        self.assertTrue(result["success"])
        self.assertIn("NewAPI 文档参考", result["output"])


if __name__ == "__main__":
    unittest.main()
