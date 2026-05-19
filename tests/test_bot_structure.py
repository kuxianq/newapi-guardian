import ast
import unittest
from pathlib import Path


BOT_PATH = Path(__file__).resolve().parents[1] / "bot.py"


class BotStructureTests(unittest.TestCase):
    def setUp(self):
        self.source = BOT_PATH.read_text()
        self.tree = ast.parse(self.source)

    def test_channel_label_is_top_level_function(self):
        top_level_funcs = {
            node.name
            for node in self.tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        self.assertIn("_channel_label", top_level_funcs)

    def test_stats_callbacks_are_routed_through_module(self):
        self.assertIn("stats_result = handle_stats_callback(data)", self.source)
        for callback_name in [
            "overview",
            "slow",
            "report",
            "recent_logs",
            "console",
            "today",
            "models",
            "users",
            "tokens",
        ]:
            self.assertNotIn(f'elif data == "{callback_name}"', self.source)

    def test_confirm_callbacks_are_routed_through_module(self):
        self.assertIn("from callbacks.confirm import handle_confirm_callback", self.source)
        self.assertIn("await handle_confirm_callback(", self.source)
        for callback_prefix in [
            "confirm_enable",
            "confirm_disable_failed",
            "confirm_disable",
            "confirm_restore:",
            "confirm_memory_compact:",
        ]:
            self.assertNotIn(f'elif data.startswith("{callback_prefix}")', self.source)

    def test_channel_callbacks_are_routed_through_module(self):
        self.assertIn("from callbacks.channel import handle_channel_callback", self.source)
        self.assertIn("await handle_channel_callback(", self.source)
        self.assertNotIn('elif data == "test_all":', self.source)
        self.assertNotIn('elif data.startswith("toggle_")', self.source)
        self.assertNotIn('elif data.startswith("test_") and not data.startswith("test_all")', self.source)

    def test_menu_callbacks_are_routed_through_module(self):
        self.assertIn("from callbacks.menu import handle_backup_callback, handle_menu_callback", self.source)
        self.assertIn("handle_menu_callback(data)", self.source)
        self.assertIn("await handle_backup_callback(", self.source)
        for menu_key in [
            "menu_status",
            "menu_diagnose",
            "menu_stats",
            "menu_channels",
            "menu_data",
            "model_prompt",
            "channel_prompt",
            "enable_prompt",
            "disable_prompt",
            "disable_failed_prompt",
            "restore_prompt",
            "backup",
            "backup_list",
        ]:
            self.assertNotIn(f'elif data == "{menu_key}":\n        text = (', self.source)

    def test_ai_callbacks_are_routed_through_module(self):
        self.assertIn("from callbacks.ai_config import handle_ai_callback", self.source)
        self.assertIn("handle_ai_callback(data)", self.source)
        self.assertNotIn('elif data == "ai_config_menu":', self.source)
        self.assertNotIn('elif data == "ai_enable":', self.source)
        self.assertNotIn('elif data == "ai_disable":', self.source)

    def test_diagnose_callbacks_are_routed_through_module(self):
        self.assertIn("from callbacks.diagnose import handle_diagnose_callback", self.source)
        self.assertIn("handle_diagnose_callback(data)", self.source)
        self.assertNotIn('elif data.startswith("diagnose_model:")', self.source)
        self.assertNotIn('elif data == "newapi_docs_menu":', self.source)
        self.assertNotIn('elif data.startswith("newapi_docs:")', self.source)

    def test_callback_handler_initializes_text_and_markup_defaults(self):
        # Avoid UnboundLocalError when branches only assign text.
        self.assertIn("text: str | None = None", self.source)
        self.assertIn("markup = back_btn()", self.source)


    def test_callback_routes_cover_all_button_callback_data(self):
        """Static check: every callback_data referenced in source is routable."""
        import re
        from pathlib import Path

        root = Path(__file__).resolve().parents[1]
        files = [root / "bot.py", root / "menus.py"] + list((root / "callbacks").glob("*.py")) + list((root / "handlers").glob("*.py"))

        defined: set[str] = set()
        templates: set[str] = set()
        button_re = re.compile(r"callback_data=[\'\"]([^\'\"]+)[\'\"]")
        template_re = re.compile(r"callback_data=f[\'\"]([^\'\"]+)[\'\"]")
        for f in files:
            content = f.read_text()
            defined.update(button_re.findall(content))
            templates.update(template_re.findall(content))

        sources = {f: f.read_text() for f in files}
        bot_src = (root / "bot.py").read_text()
        cb_files = [f for f in files if f.name != "menus.py"]
        cb_src = "\n".join(sources[f] for f in cb_files)

        handled_eq: set[str] = set(re.findall(r"data == [\'\"]([^\'\"]+)[\'\"]", cb_src))
        for m in re.findall(r"data in \{([^}]+)\}", cb_src):
            handled_eq.update(re.findall(r"[\'\"]([^\'\"]+)[\'\"]", m))
        for m in re.findall(r"^\s*[\'\"]([a-zA-Z_]+)[\'\"]\s*:\s*\(", cb_src, flags=re.MULTILINE):
            handled_eq.add(m)
        handled_starts: set[str] = set(re.findall(r"data\.startswith\([\'\"]([^\'\"]+)[\'\"]\)", cb_src))
        for t in templates:
            prefix = t.split(":")[0].split("_{")[0]
            handled_starts.add(prefix)

        missing = []
        for cb in sorted(defined):
            if cb in handled_eq:
                continue
            if any(cb.startswith(p) for p in handled_starts):
                continue
            missing.append(cb)
        self.assertFalse(missing, f"unrouted callback_data: {missing}")


if __name__ == "__main__":
    unittest.main()
