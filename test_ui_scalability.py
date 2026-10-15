"""Regression test for the user's 10-instance / 58-template window geometry.

Tk is exercised on the Windows CI runner; no real ADB device is contacted.
"""
import sys
import unittest
from unittest.mock import patch

from autoclicker.gui.paging import DEFAULT_PAGE_SIZE


@unittest.skipUnless(sys.platform == "win32", "Windows desktop GUI test")
class ScalableWindowTests(unittest.TestCase):
    def test_twelve_tabs_do_not_change_content_requested_width(self):
        import customtkinter as ctk
        from autoclicker.gui.scalable_tabs import ScalableTabView

        root = ctk.CTk()
        root.withdraw()
        try:
            container = ScalableTabView(root)
            container.pack(fill="both", expand=True)
            pages = [
                container.add(f"Instance {index} (127.0.0.1:{5555 + index * 2})")
                for index in range(12)
            ]
            root.update_idletasks()
            self.assertEqual(container.get(), "Instance 0 (127.0.0.1:5555)")
            self.assertEqual(
                sum(page.winfo_manager() == "pack" for page in pages), 1
            )
            for index in range(12):
                name = f"Instance {index} (127.0.0.1:{5555 + index * 2})"
                container.set(name)
                self.assertEqual(container.get(), name)
                self.assertEqual(
                    sum(page.winfo_manager() == "pack" for page in pages), 1
                )
            self.assertLess(container.winfo_reqwidth(), 900)
            container.delete(container.get())
            self.assertEqual(len(container._tabs), 11)
        finally:
            root.destroy()

    def test_real_app_layout_with_ten_instances_and_fifty_eight_templates(self):
        from autoclicker.gui.main_window import App
        config = {
            "instances": [
                {"device_address": f"127.0.0.1:{5557 + 2 * index}"}
                for index in range(10)
            ],
        }
        with patch(
            "autoclicker.gui.main_window.AutoClicker.read_config",
            return_value=config,
        ), patch.object(App, "save_app_config", return_value=None):
            app = App()
            app.withdraw()
            try:
                app.geometry("900x650")
                app.update_idletasks()
                self.assertEqual(len(app.tab_frames), 10)
                self.assertEqual(len(app.instance_tabs.names), 10)
                self.assertLess(app.instance_tabs.winfo_reqwidth(), 850)
                self.assertLess(app.top_bar.winfo_reqwidth(), 900)
                self.assertLess(app.tabview.winfo_reqwidth(), 1050)
                initial = next(iter(app.tab_frames.values()))
                initial.clicker.template_order = [
                    f"template-{index:03d}.png" for index in range(58)
                ]
                initial.clicker.load_config = lambda: None
                initial.refresh_templates()
                app.update_idletasks()
                self.assertEqual(
                    len(initial.template_row_widgets), DEFAULT_PAGE_SIZE
                )
                self.assertEqual(
                    sum(f._templates_rendered for f in app.tab_frames.values()), 1
                )
                self.assertLess(app.winfo_reqwidth(), 1100)
                # Switching to the last instance must not reactivate the others.
                last_name = next(reversed(app.tab_frames))
                app._select_instance(last_name)
                app.update_idletasks()
                self.assertEqual(app.tabview.get(), last_name)
                self.assertEqual(app.instance_tabs._selected, last_name)
                self.assertEqual(
                    sum(
                        page.winfo_manager() == "pack"
                        for page in app.tabview._tabs.values()
                    ), 1
                )
            finally:
                app.destroy()


if __name__ == "__main__":
    unittest.main()
