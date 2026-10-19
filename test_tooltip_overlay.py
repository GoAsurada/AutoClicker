"""Integration checks for the actual CustomTkinter filename label preview.

This covers the widget type used by the real template list rather than only
plain Tk labels, while keeping user config and templates untouched.
"""
import os
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from PIL import Image

from autoclicker.gui.main_window import App
from autoclicker.gui.widgets.tooltip import TemplatePreviewTooltip


@unittest.skipUnless(os.name == "nt", "Windows Tk integration")
class ActualTemplateRowPreviewTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory()
        self.filename="Google Back3.png"
        self.file=os.path.join(self.temp.name,self.filename)
        Image.new("RGB",(110,84),(11,45,95)).save(self.file)
        self.config=patch(
            "autoclicker.gui.main_window.AutoClicker.read_config",
            return_value={"instances":[{"device_address":"127.0.0.1:5557"}]},
        )
        self.save=patch.object(App,"save_app_config",return_value=True)
        self.preload=patch.object(App,"_preload_configured_templates",return_value=None)
        for p in (self.config,self.save,self.preload):p.start()
        self.app=App()
        self.app.withdraw()
        self.frame=self.app.get_current_tab_frame()
        clicker=self.frame.clicker
        clicker.template_dir=self.temp.name
        clicker.template_order=[self.filename]
        clicker.template_counts={self.filename:0}
        clicker.template_actions={self.filename:"click"}
        clicker.load_config=Mock()
        self.frame.refresh_templates()
        self.app.update_idletasks()

    def tearDown(self):
        TemplatePreviewTooltip.get_instance(self.app).hide()
        self.app.destroy()
        for p in (self.preload,self.save,self.config):p.stop()
        self.temp.cleanup()

    def test_real_template_filename_binds_hover_and_embedded_image_shows(self):
        label=self.frame.template_row_widgets[self.filename].label
        # CTkLabel.bind forwards handlers to its internal Tk Label + Canvas
        # but intentionally returns None; inspect the real event receivers.
        self.assertTrue(label._label.bind("<Enter>"))
        self.assertTrue(label._canvas.bind("<Enter>"))
        self.assertTrue(label._label.bind("<Leave>"))
        tip=TemplatePreviewTooltip.get_instance(self.app)
        self.assertTrue(tip.show(label,self.file,self.filename),tip._last_error)
        self.assertIs(tip.tip_window.master,self.app)
        self.assertEqual(tip.tip_window.winfo_manager(),"place")
        self.assertEqual(len([
            widget for widget in self.app.winfo_children()
            if widget.winfo_class()=="Toplevel"
        ]),0)

    def test_template_hover_cleanup_after_tab_switch(self):
        label=self.frame.template_row_widgets[self.filename].label
        tip=TemplatePreviewTooltip.get_instance(self.app)
        self.assertTrue(tip.show(label,self.file,self.filename))
        self.frame.template_tabview.set("⚡ 미매칭 템플릿")
        tip.cancel()
        self.assertIsNone(tip.tip_window)
        self.assertIsNone(tip._dismiss_after_id)


if __name__=="__main__":
    unittest.main()
