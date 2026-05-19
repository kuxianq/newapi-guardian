"""Telegram 菜单布局冒烟测试。"""
import unittest

from menus import (
    ai_menu_kb,
    channels_menu_kb,
    data_menu_kb,
    diagnose_menu_kb,
    main_menu_kb,
    newapi_docs_menu_kb,
    stats_menu_kb,
    status_menu_kb,
)


class MenuLayoutTests(unittest.TestCase):
    def _callback_data(self, markup):
        return [button.callback_data for row in markup.inline_keyboard for button in row if button.callback_data]

    def test_main_menu_contains_expected_sections(self):
        data = self._callback_data(main_menu_kb(False))
        for item in ["menu_status", "menu_diagnose", "menu_channels", "menu_stats", "menu_data", "menu_ai"]:
            self.assertIn(item, data)

    def test_submenus_have_home_navigation(self):
        for markup in [status_menu_kb(), diagnose_menu_kb(), stats_menu_kb(), channels_menu_kb(), data_menu_kb(), ai_menu_kb()]:
            self.assertIn("menu", self._callback_data(markup))

    def test_docs_menu_returns_to_main(self):
        # 📚 NewAPI 文档 现在独立挂在主菜单，不再返回诊断中心。
        data = self._callback_data(newapi_docs_menu_kb())
        self.assertIn("menu", data)


if __name__ == "__main__":
    unittest.main()
