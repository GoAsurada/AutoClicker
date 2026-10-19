"""Regression tests for stable template pane geometry and lower startup cost."""
import time
import unittest
from unittest.mock import Mock, patch

from autoclicker.gui.main_window import App
from autoclicker.gui.horizontal_tabs import compact_instance_label


class LightweightLayoutTests(unittest.TestCase):
    def setUp(self):
        self.config = {
            "instances": [
                {"device_address": f"127.0.0.1:{5557 + 2*i}"}
                for i in range(10)
            ],
        }
        self.read = patch(
            "autoclicker.gui.main_window.AutoClicker.read_config",
            return_value=self.config,
        )
        self.save = patch.object(App, "save_app_config", return_value=True)
        self.preload = patch("autoclicker.gui.main_window.AutoClicker.preload_templates")
        for item in (self.read, self.save, self.preload):
            item.start()
        self.app = App()
        self.app.withdraw()
        self.app.update_idletasks()

    def tearDown(self):
        try:
            self.app.destroy()
        finally:
            for item in (self.preload, self.save, self.read):
                item.stop()

    def test_primary_fallback_share_same_pane_and_footer_height(self):
        frame = self.app.get_current_tab_frame()
        self.assertIs(frame.fallback_final_frame.master, frame.templates_main_frame)
        self.assertIs(frame.fb_final_action_row, frame.fb_final_header_row)
        self.assertEqual(int(frame.fallback_final_frame.grid_info()["row"]), 1)
        self.assertEqual(int(frame.template_tabview.grid_info()["row"]), 0)
        self.assertEqual(frame.templates_main_frame.grid_rowconfigure(0)["weight"], 1)
        self.assertEqual(frame.fallback_final_frame.winfo_manager(), "grid")
        for selected in ("📋 기본 템플릿", "⚡ 미매칭 템플릿"):
            frame.template_tabview.set(selected)
            self.assertEqual(frame.fallback_final_frame.winfo_manager(), "grid")

    def test_switch_keeps_both_rendered_pages_without_rebuilding(self):
        frame = self.app.get_current_tab_frame()
        names = [f"file-{i:03d}.png" for i in range(64)]
        frame.clicker.template_order = list(names)
        frame.clicker.fallback_template_order = ["fallback.png"]
        frame.clicker.load_config = Mock()
        frame.refresh_templates()
        before_primary = {
            key: id(value.frame) for key, value in frame.template_row_widgets.items()
        }
        before_fallback = {
            key: id(value.frame) for key, value in
            frame.fallback_template_row_widgets.items()
        }
        repaint = patch.object(frame, "filter_templates")
        with repaint as call:
            start = time.perf_counter()
            for _ in range(20):
                frame.template_tabview.set("⚡ 미매칭 템플릿")
                frame.template_tabview.set("📋 기본 템플릿")
            elapsed = time.perf_counter() - start
            call.assert_not_called()
        self.assertEqual(
            {key: id(w.frame) for key, w in frame.template_row_widgets.items()},
            before_primary,
        )
        self.assertEqual(
            {key: id(w.frame) for key, w in frame.fallback_template_row_widgets.items()},
            before_fallback,
        )
        self.assertLess(elapsed, 3.0)

    def test_first_launch_no_eager_full_image_preload(self):
        from autoclicker.core.clicker import AutoClicker
        # The startup read_config stub has no opt-in preload flag.
        with patch.object(AutoClicker, "preload_templates") as preload:
            self.app.update_idletasks()
            preload.assert_not_called()

    def test_instance_buttons_are_original_compact_height(self):
        tabs = self.app.instance_tabs
        self.assertEqual(len(tabs.names), 10)
        self.assertTrue(all(button.cget("height") == 26 for button in tabs._buttons.values()))
        self.assertFalse(tabs.grid_propagate())
        self.assertLess(tabs.winfo_reqwidth(), 400)
        self.assertEqual(
            compact_instance_label("Inst 1 (:5557)", 100), "Inst 1 :5557"
        )


if __name__ == "__main__":
    unittest.main()
