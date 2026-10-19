"""Regression probes for geometry feedback between primary/fallback template pages.

Use a throwaway mocked 10-instance app, never modify saved user state.
"""
import unittest
from unittest.mock import patch

from autoclicker.gui.main_window import App


class TemplateGeometryRegression(unittest.TestCase):
    def setUp(self):
        config={"instances":[{"device_address":f"127.0.0.1:{5557+2*i}"} for i in range(10)]}
        self.mocks=[
            patch("autoclicker.gui.main_window.AutoClicker.read_config", return_value=config),
            patch.object(App, "save_app_config", return_value=True),
            patch.object(App, "_preload_configured_templates", return_value=None),
        ]
        for mock in self.mocks: mock.start()
        self.app=App()
        self.app.withdraw()
        self.frame=self.app.get_current_tab_frame()
        order=[f"long-template-test-{i:02}.png" for i in range(64)]
        self.frame.clicker.template_order=list(order)
        self.frame.clicker.fallback_template_order=["cat.png"]
        self.frame.clicker.load_config=lambda:None
        self.frame.refresh_templates()
        self.app.update_idletasks()

    def tearDown(self):
        try: self.app.destroy()
        finally:
            for mock in reversed(self.mocks): mock.stop()

    def sizes(self):
        f=self.frame
        return {
            name: (widget.winfo_reqwidth(),widget.winfo_reqheight(),
                   widget.winfo_width(),widget.winfo_height())
            for name,widget in (
                ("body",f.body_frame),("log",f.log_frame),
                ("templates_outer",f.templates_main_frame),
                ("tabview",f.template_tabview),
                ("primary",f.tab_primary),("fallback",f.tab_fallback),
                ("primary_list",f.templates_frame),
                ("fallback_list",f.fallback_templates_frame),
            )
        }

    def test_forty_switches_preserve_parent_split_and_page_width(self):
        f=self.frame
        baseline=self.sizes()
        assert baseline["primary_list"][0] != baseline["fallback_list"][0]
        for _ in range(20):
            for selected in ("⚡ 미매칭 템플릿", "📋 기본 템플릿"):
                f.template_tabview.set(selected)
                self.app.update_idletasks()
                sizes=self.sizes()
                for name in ("body", "log", "templates_outer", "tabview", "primary", "fallback"):
                    self.assertEqual(
                        sizes[name][:2], baseline[name][:2],
                        f"{name} changed its requested geometry after switching to {selected}",
                    )

    def test_both_panes_have_fixed_parent_geometry(self):
        f=self.frame
        self.assertFalse(f.body_frame.grid_propagate())
        self.assertFalse(f.templates_main_frame.grid_propagate())
        self.assertFalse(f.tab_primary.pack_propagate())
        self.assertFalse(f.tab_fallback.pack_propagate())
        self.assertEqual(
            f.body_frame.grid_columnconfigure(0)["uniform"], "body-split"
        )
        self.assertEqual(
            f.body_frame.grid_columnconfigure(1)["uniform"], "body-split"
        )

    def test_instance_toolbar_breathing_room(self):
        self.assertGreaterEqual(self.app.top_bar.pack_info()["pady"][1], 5)
        self.assertGreaterEqual(self.app.instance_tabs.pack_info()["pady"][0], 4)
        self.assertGreaterEqual(self.app.instance_tabs.pack_info()["pady"][1], 6)


if __name__=="__main__":
    unittest.main()
