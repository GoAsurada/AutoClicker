"""Real Tk checks for embedded template thumbnail.

A rendered preview must be a mapped CHILD of AutoClicker rather than a new
OS-managed top-level popup.  Synthetic tests also exercise the actual hover
callback and a display/exit cycle.
"""
import os
import tempfile
import time
import tkinter as tk
import unittest
from unittest.mock import patch

from PIL import Image

from autoclicker.gui.widgets.tooltip import (
    TemplatePreviewTooltip, in_app_preview_position,
)


class InAppPositionTests(unittest.TestCase):
    def test_below_or_above_row_without_covering_the_source(self):
        x,y=in_app_preview_position((50,100,300,125,150),(200,150),(800,600))
        self.assertGreaterEqual(y,131)
        x2,y2=in_app_preview_position((50,520,300,545,150),(200,150),(800,600))
        self.assertLessEqual(y2+150,514)

    def test_inset_clamps_to_small_client_area(self):
        x,y=in_app_preview_position((0,30,270,52,260),(200,145),(350,260))
        self.assertGreaterEqual(x,8)
        self.assertLessEqual(x+200,342)
        self.assertGreaterEqual(y,8)
        self.assertLessEqual(y+145,252)


@unittest.skipUnless(os.name == "nt", "Windows Tk integration")
class InAppPreviewTests(unittest.TestCase):
    def setUp(self):
        self.root=tk.Tk()
        self.root.geometry("650x430+90+90")
        self.source=tk.Label(self.root,text="Google Back3.png")
        self.source.place(x=180,y=115,width=190,height=30)
        self.root.update()
        with tempfile.NamedTemporaryFile(suffix=".png",delete=False) as f:
            self.path=f.name
        Image.new("RGB",(90,55),(50,150,200)).save(self.path)
        self.tooltip=TemplatePreviewTooltip(self.root)

    def tearDown(self):
        self.tooltip.hide()
        self.root.destroy()
        os.unlink(self.path)

    def test_show_creates_mapped_child_not_a_second_window(self):
        before=set(self.root.winfo_children())
        self.assertTrue(self.tooltip.show(self.source,self.path,"Google Back3.png"))
        frame=self.tooltip.tip_window
        self.root.update_idletasks()
        self.assertIs(frame.master,self.root)
        self.assertEqual(frame.winfo_manager(),"place")
        # Detached CI desktops do not map *any* Tk window, even the root.
        # On a real interactive desktop we additionally require mapped UI.
        if self.root.winfo_ismapped():
            self.assertTrue(frame.winfo_ismapped())
        self.assertEqual(len([w for w in self.root.winfo_children() if isinstance(w,tk.Toplevel)]),0)
        self.assertGreater(len(set(self.root.winfo_children())-before),0)

    def test_label_enter_callback_causes_preview_to_appear(self):
        on_enter = lambda e: self.tooltip.schedule_show(
            self.source, self.path, "Google Back3.png"
        )
        self.source.bind("<Enter>", on_enter)
        self.assertTrue(self.source.bind("<Enter>"))
        with patch.object(self.tooltip,"_cursor_inside",return_value=True):
            if self.root.winfo_ismapped():
                self.source.event_generate("<Enter>")
            else:
                on_enter(None)  # Tk cannot dispatch mouse events while unmapped.
            time.sleep(0.14)
            self.root.update()
        self.assertIsNotNone(self.tooltip.tip_window,self.tooltip._last_error)
        self.assertEqual(self.tooltip.tip_window.winfo_manager(),"place")

    def test_internal_canvas_leave_does_not_cancel_hover(self):
        # A CTkLabel fires a short Leave/Enter transition from its canvas and
        # native text label. The user never left the whole filename control.
        with patch.object(self.tooltip,"_cursor_inside",return_value=True):
            self.tooltip.schedule_show(self.source,self.path,"Google Back3.png")
            first_id=self.tooltip._hover_after_id
            self.tooltip.schedule_hide_if_left(self.source)
            self.tooltip.schedule_show(self.source,self.path,"Google Back3.png")
            self.assertEqual(first_id,self.tooltip._hover_after_id)
            time.sleep(0.14)
            self.root.update()
        self.assertIsNotNone(self.tooltip.tip_window,self.tooltip._last_error)

    def test_leaving_entire_label_hides_preview(self):
        self.assertTrue(self.tooltip.show(self.source,self.path))
        with patch.object(self.tooltip,"_cursor_inside",return_value=False):
            self.tooltip.schedule_hide_if_left(self.source)
            time.sleep(0.085)
            self.root.update()
        self.assertIsNone(self.tooltip.tip_window)

    def test_pointer_leaving_hides_preview(self):
        self.assertTrue(self.tooltip.show(self.source,self.path))
        with patch.object(self.tooltip,"_cursor_inside",return_value=False):
            self.tooltip._watch_hover()
        self.assertIsNone(self.tooltip.tip_window)

    def test_focus_out_does_not_destroy_embedded_overlay(self):
        self.assertTrue(self.tooltip.show(self.source,self.path))
        self.root.event_generate("<FocusOut>")
        self.root.update_idletasks()
        self.assertIsNotNone(self.tooltip.tip_window)
        self.assertIs(self.tooltip.tip_window.master, self.root)

    def test_invalid_path_returns_a_diagnostic_error(self):
        self.assertFalse(self.tooltip.show(self.source,self.path+"missing","not here"))
        self.assertIn("파일 없음",self.tooltip._last_error)
        self.assertIsNone(self.tooltip.tip_window)

    def test_destroy_cancel_has_no_pending_event(self):
        self.assertTrue(self.tooltip.show(self.source,self.path))
        self.tooltip.hide()
        self.assertIsNone(self.tooltip.tip_window)
        self.assertIsNone(self.tooltip._dismiss_after_id)


if __name__=="__main__":
    unittest.main()
