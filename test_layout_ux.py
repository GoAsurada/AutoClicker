"""Windows Tk regression for one-row instance tabs, full order editor and mass disconnect."""
import threading
import time
import unittest
from unittest.mock import Mock, patch

from autoclicker.gui.horizontal_tabs import (
    HorizontalInstanceTabs, compact_instance_label,
)
from autoclicker.gui.template_order_editor import (
    TemplateOrderEditor, relocate_template,
)


class LayoutLogicTests(unittest.TestCase):
    def test_compact_labels_fit_small_slots(self):
        self.assertEqual(compact_instance_label("Inst 12 (127.0.0.1:5557)", 45), "12")
        self.assertEqual(compact_instance_label("Inst 12 (127.0.0.1:5557)", 80), "#12")
        self.assertEqual(compact_instance_label("Inst 12 (127.0.0.1:5557)", 125), "Inst 12")
        self.assertEqual(compact_instance_label("Inst 12 (127.0.0.1:5557)", 45, True), "⚠ 12")

    def test_relocate_preserves_items_across_page_boundaries(self):
        order = [f"file{i:03d}.png" for i in range(58)]
        changed = relocate_template(order, 2, 46)
        self.assertEqual(changed[46], order[2])
        self.assertEqual(len(set(changed)), 58)
        self.assertEqual(len(changed), len(order))
        self.assertEqual(order[2], "file002.png")


class LayoutGUIWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import sys
        if sys.platform != "win32":
            raise unittest.SkipTest("Windows GUI test")

    def setUp(self):
        from autoclicker.gui.main_window import App

        self.read_config = patch(
            "autoclicker.gui.main_window.AutoClicker.read_config",
            return_value={
                "instances": [
                    {"device_address": f"127.0.0.1:{5557 + i * 2}"}
                    for i in range(10)
                ]
            },
        )
        self.saving = patch.object(App, "save_app_config", return_value=True)
        self.preload = patch.object(App, "_preload_configured_templates", return_value=None)
        self.read_config.start()
        self.saving.start()
        self.preload.start()
        self.app = App()
        self.app.geometry("1050x690")
        self.app.withdraw()
        self.app.update_idletasks()

    def tearDown(self):
        try:
            self.app.destroy()
        finally:
            self.preload.stop()
            self.saving.stop()
            self.read_config.stop()

    def test_all_ten_instance_buttons_fit_one_row_and_switch(self):
        self.assertEqual(len(self.app.instance_tabs.names), 10)
        tabs = self.app.instance_tabs
        self.assertFalse(hasattr(tabs, "scroll"))
        self.assertEqual({button.grid_info()["row"] for button in tabs._buttons.values()}, {0})
        self.assertLess(tabs.winfo_reqwidth(), 1050)
        names = list(tabs.names)
        tabs._buttons[names[8]].invoke()
        self.assertEqual(self.app.tabview.get(), names[8])
        tabs.set_warning(names[7], True)
        self.assertIn("⚠", tabs._buttons[names[7]].cget("text"))
        tabs.set_tabs(names[:4], selected=names[0])
        self.assertEqual(len(tabs.names), 4)

    def test_disconnect_all_stops_then_disconnects_each(self):
        events = []
        frames = list(self.app.tab_frames.values())
        for index, frame in enumerate(frames):
            frame.clicker.device = object()
            frame.clicker.is_running = bool(index % 2)
            frame._loop_starting = False
            frame.stop_clicker_loop = Mock(
                side_effect=lambda i=index: events.append(("stop", i))
            )
            def disconnect(i=index, current=frame):
                events.append(("disconnect", i))
                current.clicker.device = None
            frame.clicker.disconnect = Mock(side_effect=disconnect)
        # Run the deferred disconnect callbacks deterministically.
        with patch.object(self.app, "after", side_effect=lambda _delay, callback: callback()):
            self.app.disconnect_all_instances()
        self.assertEqual(sum(f.clicker.disconnect.call_count for f in frames), 10)
        self.assertEqual(sum(f.stop_clicker_loop.call_count for f in frames), 5)
        self.assertLess(
            max(i for i, item in enumerate(events) if item[0] == "stop"),
            min(i for i, item in enumerate(events) if item[0] == "disconnect"),
        )
        self.assertTrue(all(f.start_button.cget("state") == "disabled" for f in frames))
        for _ in range(100):
            self.app._drain_ui_queue()
            if not self.app._disconnect_all_busy:
                break
            time.sleep(0.01)
        self.assertFalse(self.app._disconnect_all_busy)
        self.assertEqual(self.app.disconnect_all_btn.cget("state"), "normal")

    def test_slow_adb_disconnect_does_not_block_window(self):
        frame = self.app.get_current_tab_frame()
        started = threading.Event()
        release = threading.Event()

        def blocked_disconnect():
            started.set()
            release.wait(timeout=3)
            frame.clicker.device = None

        frame.clicker.disconnect = Mock(side_effect=blocked_disconnect)
        try:
            before = time.perf_counter()
            self.app.disconnect_all_instances()
            elapsed = time.perf_counter() - before
            self.assertLess(elapsed, 0.6)
            self.assertTrue(started.wait(timeout=1))
            self.assertTrue(self.app._disconnect_all_busy)
            self.assertEqual(self.app.disconnect_all_btn.cget("state"), "disabled")
        finally:
            release.set()
            for _ in range(150):
                self.app._drain_ui_queue()
                if not self.app._disconnect_all_busy:
                    break
                time.sleep(0.01)
        self.assertFalse(self.app._disconnect_all_busy)

    def test_hidden_instances_do_not_repaint_all_template_rows(self):
        frames = list(self.app.tab_frames.values())
        for frame in frames:
            frame._templates_rendered = True
            frame.filter_templates = Mock()
            frame.clicker.template_order = ["a.png", "b.png"]
        self.app.update_all_template_order(["b.png", "a.png"])
        self.assertEqual(frames[0].filter_templates.call_count, 1)
        self.assertTrue(all(
            frame.filter_templates.call_count == 0
            for frame in frames[1:]
        ))
        self.assertTrue(all(
            frame._templates_rendered is False
            for frame in frames[1:]
        ))

    def test_editor_drag_move_search_cancel_and_save_propagates(self):
        frame = self.app.get_current_tab_frame()
        order = [f"template{i:03d}.png" for i in range(58)]
        for item in self.app.tab_frames.values():
            item.clicker.template_order = list(order)
            item.clicker.template_counts = {name: 0 for name in order}
        frame.clicker.save_config = Mock(return_value=True)
        editor = TemplateOrderEditor(frame)
        editor.withdraw()
        try:
            self.assertEqual(editor.listbox.size(), 58)
            editor.search_var.set("template045")
            self.assertEqual(editor.selected_index(), 45)
            editor.move_selected("top")
            self.assertEqual(editor.order[0], order[45])
            editor._select(0)
            # Simulate cross-list drag index changes.
            self.assertEqual(relocate_template(editor.order, 0, 40)[40], order[45])
            editor.save()
        finally:
            if editor.winfo_exists():
                editor.close()
        frame.clicker.save_config.assert_called_once()
        for item in self.app.tab_frames.values():
            self.assertEqual(item.clicker.template_order[0], order[45])

        editor2 = TemplateOrderEditor(frame)
        editor2.withdraw()
        try:
            editor2._select(0)
            editor2.move_selected("bottom")
            editor2.close()
        finally:
            if editor2.winfo_exists():
                editor2.close()
        self.assertEqual(frame.clicker.template_order[0], order[45])

    def test_editor_failure_restores_previous_order(self):
        frame = self.app.get_current_tab_frame()
        initial = ["a.png", "b.png", "c.png"]
        frame.clicker.template_order = list(initial)
        frame.clicker.save_config = Mock(return_value=False)
        editor = TemplateOrderEditor(frame)
        editor.withdraw()
        try:
            editor._select(1)
            editor.move_selected("top")
            with patch("autoclicker.gui.template_order_editor.messagebox.showerror") as show:
                editor.save()
                show.assert_called_once()
            self.assertEqual(frame.clicker.template_order, initial)
        finally:
            editor.close()


if __name__ == "__main__":
    unittest.main()
