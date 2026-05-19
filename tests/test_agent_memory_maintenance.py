import json
import tempfile
import unittest
from pathlib import Path

from agent_memory_maintenance import compact_all_memories, compact_memory_file, get_memory_status


class AgentMemoryMaintenanceTests(unittest.TestCase):
    def _write_memory(self, root: Path, name: str = "user_1.json") -> Path:
        path = root / name
        payload = {
            "short_term": [
                {"timestamp": f"t{i}", "user": f"u{i}", "assistant": f"a{i}", "metadata": {}}
                for i in range(25)
            ],
            "long_term": {
                "user_profile": {"report_style": "concise"},
                "knowledge_base": {"keep": "yes"},
                "patterns": {"p": {"occurrences": 1}},
                "learned_facts": [
                    {"fact": "same", "category": "channel", "learned_at": "1"},
                    {"fact": "unique", "category": "general", "learned_at": "2"},
                    {"fact": "same", "category": "channel", "learned_at": "3"},
                ],
            },
            "last_updated": "old",
        }
        payload["short_term"][-1]["metadata"] = {
            "tool_results": [
                {
                    "tool": "query_database",
                    "arguments": "select 1",
                    "output": "x" * 9000,
                    "raw": {"rows": ["y" * 9000]},
                    "success": True,
                }
            ]
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def test_status_reports_file_counts(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._write_memory(root)
            status = get_memory_status(root)
            self.assertEqual(status["file_count"], 1)
            self.assertEqual(status["files"][0]["item_counts"]["short_term"], 25)
            self.assertEqual(status["files"][0]["item_counts"]["learned_facts"], 3)

    def test_compact_dry_run_does_not_modify_file(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = self._write_memory(root)
            before = path.read_text(encoding="utf-8")
            result = compact_memory_file(path, dry_run=True, keep_recent_facts=10)
            after = path.read_text(encoding="utf-8")
            self.assertEqual(before, after)
            self.assertTrue(result["dry_run"])
            self.assertEqual(result["after_counts"]["short_term"], 20)
            self.assertEqual(result["duplicate_facts"], 1)
            self.assertEqual(result["raw_omitted"], 1)
            self.assertEqual(result["output_truncated"], 1)

    def test_compact_writes_backup_and_preserves_core_sections(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._write_memory(root)
            result = compact_all_memories(memory_dir=root, dry_run=False, keep_recent_facts=1)
            self.assertEqual(result["file_count"], 1)
            self.assertIsNotNone(result["backup_dir"])
            backup_dir = Path(result["backup_dir"])
            self.assertTrue((backup_dir / "user_1.json").exists())

            compacted = json.loads((root / "user_1.json").read_text(encoding="utf-8"))
            self.assertEqual(len(compacted["short_term"]), 20)
            self.assertEqual(len(compacted["long_term"]["learned_facts"]), 1)
            self.assertEqual(compacted["long_term"]["user_profile"]["report_style"], "concise")
            self.assertEqual(compacted["long_term"]["knowledge_base"]["keep"], "yes")
            last_tool_result = compacted["short_term"][-1]["metadata"]["tool_results"][0]
            self.assertTrue(last_tool_result["raw_omitted"])
            self.assertTrue(last_tool_result["output_truncated"])
            self.assertNotIn("raw", last_tool_result)
            self.assertLess(len(last_tool_result["output"]), 5000)
            self.assertIn("last_compacted", compacted)

    def test_status_reports_parse_error_without_breaking_other_files(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._write_memory(root, "user_1.json")
            (root / "user_bad.json").write_text("{bad json", encoding="utf-8")
            status = get_memory_status(root)
            self.assertEqual(status["file_count"], 2)
            bad = [item for item in status["files"] if item["filename"] == "user_bad.json"][0]
            self.assertIsNotNone(bad["parse_error"])


if __name__ == "__main__":
    unittest.main()
