"""Preview tooltip regression: monitor boundaries and no stuck topmost popup."""
import os
import tempfile
import unittest
from unittest.mock import patch

import tkinter as tk
from PIL import Image

from autoclicker.gui.widgets.tooltip import (
    TemplatePreviewTooltip, preview_position, _cursor_monitor_work_area,
)


class PositionTests(unittest.TestCase):
    def test_primary_monitor_flip_does_not_cross_right_edge(self):
        left, top, right, bottom = (0, 0, 1024, 558)
        x, y = preview_position(995, 265, 135, 115, (left, top, right, bottom))
        self.assertGreaterEqual(x, left + 8)
        self.assertLessEqual(x + 135, right - 8)
        self.assertLessEqual(y + 115, bottom - 8)

    def test_negative_origin_monitor_is_supported(self):
        x, y = preview_position(-5, 330, 150, 120, (-1024, 0, 0, 768))
        self.assertGreaterEqual(x, -1016)
        self.assertLessEqual(x + 150, -8)
        self.assertGreaterEqual(y, 8)
        self.assertLessEqual(y + 120, 760)

    def test_bottom_and_upper_edges_flip_and_clamp(self):
        x, y = preview_position(250, 980, 140, 90, (0, 0, 600, 1000))
        self.assertLessEqual(y + 90, 992)
        x, y = preview_position(3, 3, 900, 120, (0, 0, 480, 300))
        self.assertEqual((x, y), (8, 15))


@unittest.skipUnless(os.name == "nt", "Windows Tk popup test")
class TooltipLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.geometry("600x400")
        self.root.update_idletasks()
        self.widget = tk.Label(self.root, text="test label")
        self.widget.pack()
        self.widget.update_idletasks()
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            self.image_path = tmp.name
        Image.new("RGB", (80, 48), (15, 20, 35)).save(self.image_path)
        self.tooltip = TemplatePreviewTooltip(self.root)

    def tearDown(self):
        self.tooltip.hide()
        self.root.destroy()
        os.unlink(self.image_path)

    def test_popup_is_not_topmost_and_disappears_when_pointer_leaves(self):
        with patch.object(self.tooltip, "_hover_still_valid", return_value=True), patch(
            "autoclicker.gui.widgets.tooltip._cursor_monitor_work_area",
            return_value=(0, 0, 1024, 768),
        ):
            self.tooltip.show(self.widget, self.image_path, "Google Back3.png")
        self.assertIsNotNone(self.tooltip.tip_window)
        tip = self.tooltip.tip_window
        self.assertEqual(str(tip.wm_attributes("-topmost")), "0")
        self.assertEqual(str(tip.wm_transient()), str(self.root))
        self.assertIsNotNone(self.tooltip._dismiss_after_id)

        with patch.object(self.tooltip, "_hover_still_valid", return_value=False):
            self.tooltip._watch_hover()
        self.assertIsNone(self.tooltip.tip_window)
        self.assertIsNone(self.tooltip._dismiss_after_id)

    def test_hiding_preview_cancels_pending_watchdog(self):
        with patch.object(self.tooltip, "_hover_still_valid", return_value=True):
            self.tooltip.show(self.widget, self.image_path, "Image")
        self.assertIsNotNone(self.tooltip._dismiss_after_id)
        self.tooltip.hide()
        self.assertIsNone(self.tooltip._dismiss_after_id)
        self.assertIsNone(self.tooltip.tip_window)

    def test_root_focus_out_does_not_immediately_destroy_preview(self):
        # Windows can emit root FocusOut when Tk creates a transient popup.
        # This must not cancel a valid thumbnail still hovered in AutoClicker.
        with patch.object(self.tooltip, "_hover_still_valid", return_value=True):
            self.tooltip.show(self.widget, self.image_path, "Image")
        self.assertIsNotNone(self.tooltip.tip_window)
        self.root.event_generate("<FocusOut>")
        self.root.update_idletasks()
        self.assertIsNotNone(self.tooltip.tip_window)

    def test_foreground_process_detection_cannot_block_initial_show(self):
        with patch.object(self.tooltip, "_cursor_inside", return_value=True), patch(
            "autoclicker.gui.widgets.tooltip._our_app_is_foreground",
            return_value=False,
        ):
            self.tooltip.show(self.widget, self.image_path, "Image")
        self.assertIsNotNone(self.tooltip.tip_window)

    def test_background_app_hides_on_watchdog_not_on_show(self):
        with patch.object(self.tooltip, "_hover_still_valid", return_value=True):
            self.tooltip.show(self.widget, self.image_path, "Image")
        self.assertIsNotNone(self.tooltip.tip_window)
        with patch(
            "autoclicker.gui.widgets.tooltip._our_app_is_foreground",
            return_value=False,
        ), patch.object(self.tooltip, "_cursor_inside", return_value=True):
            self.tooltip._watch_hover()
        self.assertIsNone(self.tooltip.tip_window)

    def test_delayed_hover_creates_a_preview_when_pointer_is_still_inside(self):
        import time
        with patch.object(self.tooltip, "_cursor_inside", return_value=True):
            self.tooltip.schedule_show(
                self.widget, self.image_path, "Google Back3.png"
            )
            time.sleep(0.23)
            self.root.update()
        self.assertIsNotNone(self.tooltip.tip_window)



if __name__ == "__main__":
    unittest.main()
