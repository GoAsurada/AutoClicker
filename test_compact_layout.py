"""Regression checks for the compact, readable v0.5.6 layout.

Validate actual Tk widget parenting and toolbar reflow; no emulator touches
or changes to the user's installed configuration.
"""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import customtkinter as ctk

from autoclicker.gui.main_window import App


class CompactLayoutTests(unittest.TestCase):
    def setUp(self):
        config = {
            "instances": [
                {"device_address": f"127.0.0.1:{5557 + 2 * i}"}
                for i in range(10)
            ]
        }
        self.patches = [
            patch("autoclicker.gui.main_window.AutoClicker.read_config", return_value=config),
            patch.object(App, "save_app_config", return_value=True),
            patch.object(App, "_preload_configured_templates", return_value=None),
        ]
        for item in self.patches:
            item.start()
        self.app = App()
        self.app.withdraw()
        self.app.update_idletasks()

    def tearDown(self):
        try:
            self.app.destroy()
        finally:
            for item in reversed(self.patches):
                item.stop()

    def test_status_device_connect_start_and_close_share_same_row(self):
        frame = self.app.get_current_tab_frame()
        header = frame.header_control_row
        self.assertIs(frame.header_status_row, header)
        for widget in (
            frame.device_addr_label,
            frame.device_combo,
            frame.connect_button,
            frame.start_button,
            frame.status_label,
            frame.delete_tab_btn,
        ):
            self.assertIs(widget.master, header)
            self.assertIs(widget.pack_info()["in"], header)
        self.assertIs(frame.status_label.master, frame.start_button.master)
        self.assertEqual(frame.status_label.cget("text"), "상태: 연결 안 됨")
        self.assertLess(frame.header_frame.winfo_reqheight(), 80)

    def test_toolbar_one_row_when_wide_and_wraps_when_narrow(self):
        self.app._on_toolbar_resize(SimpleNamespace(width=1270))
        self.assertFalse(self.app._toolbar_compact)
        self.assertEqual(self.app.action_bar.pack_info()["side"], "left")
        self.assertEqual(self.app.nav_bar.pack_info()["side"], "right")
        self.assertEqual(self.app.brand_bar.pack_info()["side"], "left")
        self.app._on_toolbar_resize(SimpleNamespace(width=900))
        self.assertTrue(self.app._toolbar_compact)
        self.assertEqual(self.app.action_bar.pack_info()["side"], "bottom")
        self.assertEqual(
            {button.grid_info()["row"] for button in self.app.instance_tabs._buttons.values()},
            {0},
        )
        self.app._on_toolbar_resize(SimpleNamespace(width=1270))
        self.assertFalse(self.app._toolbar_compact)
        self.assertEqual(self.app.action_bar.pack_info()["side"], "left")

    def test_real_window_positions_remain_compact_at_two_widths(self):
        # A mapped window generates actual <Configure> events; tests that
        # manually invoke the resize handler would miss geometry regressions.
        self.app.deiconify()
        try:
            self.app.geometry("1300x760")
            self.app.update()
            if self.app.winfo_width() < 1100:
                self.skipTest("Detached Windows Tk session cannot map requested window width")
            self.assertFalse(self.app._toolbar_compact)
            frame = self.app.get_current_tab_frame()
            frame.status_label.configure(text="상태: 실행 중 (127.0.0.1:5557)")
            self.app.update_idletasks()
            header_y = frame.connect_button.winfo_rooty()
            status_y = frame.status_label.winfo_rooty()
            self.assertLess(abs(status_y - header_y), 12)
            self.assertLess(frame.header_frame.winfo_height(), 80)

            self.app.geometry("900x640")
            self.app.update()
            self.assertTrue(self.app._toolbar_compact)
            self.assertEqual(
                {btn.grid_info()["row"] for btn in self.app.instance_tabs._buttons.values()},
                {0},
            )
        finally:
            self.app.withdraw()

    def test_explicit_fonts_one_point_larger_and_default_stays_stable(self):
        frame = self.app.get_current_tab_frame()
        self.assertEqual(frame.status_label.cget("font").cget("size"), 13)
        self.assertEqual(frame.no_match_timer_label.cget("font").cget("size"), 13)
        self.assertEqual(self.app.instance_tabs._font.cget("size"), 13)
        font_size = ctk.ThemeManager.theme["CTkFont"]["size"]
        from autoclicker.gui.font_setup import configure_app_fonts
        configure_app_fonts(self.app)
        self.assertEqual(ctk.ThemeManager.theme["CTkFont"]["size"], font_size)


if __name__ == "__main__":
    unittest.main()
