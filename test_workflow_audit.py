"""Real Tk workflow regression checks with ADB and disk writes mocked.

No user's configuration, stored templates, or emulator connections are changed.
"""
import time
import unittest
from unittest.mock import Mock, patch

from autoclicker.gui.main_window import App


class GUIWorkflowsAuditTests(unittest.TestCase):
    def setUp(self):
        config = {
            "instances": [
                {"device_address": f"127.0.0.1:{5557 + n * 2}"}
                for n in range(4)
            ]
        }
        self.patch_config = patch(
            "autoclicker.gui.main_window.AutoClicker.read_config",
            return_value=config,
        )
        self.patch_save = patch.object(App, "save_app_config", return_value=True)
        self.patch_config.start()
        self.patch_save.start()
        self.app = App()
        self.app.withdraw()
        self.app.update_idletasks()

    def tearDown(self):
        try:
            self.app.destroy()
        finally:
            self.patch_save.stop()
            self.patch_config.stop()

    def _set_templates(self, count=52):
        active = self.app.get_current_tab_frame()
        order = [f"template-{i:03d}.png" for i in range(count)]
        for frame in self.app.tab_frames.values():
            frame.clicker.template_order = list(order)
            frame.clicker.load_config = Mock()
            frame.clicker.template_actions = {name: "click" for name in order}
            frame.clicker.template_counts = {name: 0 for name in order}
        active.refresh_templates()
        self.app.update_idletasks()
        return active, order

    def test_horizontal_switch_add_remove_and_hidden_log_state(self):
        old_names = list(self.app.tab_frames)
        self.assertEqual(len(old_names), 4)
        self.assertEqual(len(self.app.instance_tabs.names), 4)
        new_frame = self.app.add_instance_tab("127.0.0.1:5599")
        self.assertIsNotNone(new_frame)
        self.assertEqual(len(self.app.tab_frames), 5)
        self.assertEqual(self.app.tabview.get(), new_frame.tab_name)
        self.assertEqual(len(self.app.instance_tabs.names), 5)

        self.app.instance_tabs._buttons[old_names[1]].invoke()
        self.assertEqual(self.app.tabview.get(), old_names[1])
        self.assertTrue(self.app.tab_frames[old_names[1]]._log_is_visible)
        self.assertEqual(
            sum(frame._log_is_visible for frame in self.app.tab_frames.values()), 1
        )
        self.app.tab_frames[new_frame.tab_name].shutdown = Mock()
        self.app.remove_instance_tab(new_frame.tab_name)
        self.assertNotIn(new_frame.tab_name, self.app.tab_frames)
        self.assertEqual(len(self.app.instance_tabs.names), 4)
        self.assertEqual(self.app.tabview.get(), old_names[1])

    def test_search_pagination_reorder_action_and_add_delete(self):
        frame, order = self._set_templates()
        self.assertEqual(len(frame.template_row_widgets), 20)
        self.assertEqual(frame.primary_page_label.cget("text"), "1 / 3  (전체 52개)")
        frame.primary_next_btn.invoke()
        self.assertEqual(list(frame.template_row_widgets)[0], order[20])

        frame.primary_search_var.set("047")
        frame._apply_scheduled_filter(is_fallback=False)
        self.assertEqual(list(frame.template_row_widgets), ["template-047.png"])
        frame.primary_search_var.set("")
        frame._apply_scheduled_filter(is_fallback=False)
        self.assertEqual(len(frame.template_row_widgets), 20)

        # A GUI click invokes the actual action event, but config file saves
        # and ADB are replaced with deterministic mocks.
        frame.clicker.toggle_action = Mock(return_value="double_click")
        frame.template_row_widgets[order[0]].action_btn.invoke()
        for sibling in self.app.tab_frames.values():
            self.assertEqual(
                sibling.clicker.template_actions[order[0]], "double_click"
            )

        frame.clicker.save_config = Mock(return_value=True)
        frame.move_template(order[0], 1)
        self.assertEqual(frame.clicker.template_order[1], order[0])
        self.assertEqual(list(frame.template_row_widgets)[0], order[1])

        # The previous 50/20-item pagination made cross-page dragging
        # impossible. Moving a row across the boundary must keep it visible.
        frame.move_template(order[19], 1)
        self.assertEqual(frame._template_pages[False], 1)
        self.assertEqual(frame.clicker.template_order[20], order[19])
        self.assertIn(order[19], frame.template_row_widgets)

        self.app.add_template_to_all_tabs("new.png")
        self.assertTrue(all(
            "new.png" in sibling.clicker.template_order
            for sibling in self.app.tab_frames.values()
        ))
        self.app._ui_latest_match_counts[("new.png", False)] = 87
        self.app.remove_template_from_all_tabs("new.png")
        self.assertNotIn(("new.png", False), self.app._ui_latest_match_counts)
        self.assertTrue(all(
            "new.png" not in sibling.clicker.template_order
            for sibling in self.app.tab_frames.values()
        ))
        self.app._ui_latest_match_counts[("new.png", False)] = 87
        self.app.add_template_to_all_tabs("new.png")
        self.assertNotIn(("new.png", False), self.app._ui_latest_match_counts)

    def test_ui_callback_errors_are_recorded_for_diagnostics(self):
        self.app.post_to_ui(lambda: 1 / 0)
        self.app._drain_ui_queue()
        stats = self.app.ui_backlog_stats()
        self.assertGreaterEqual(stats["ui_callback_errors"], 1)
        self.assertIn("ZeroDivisionError", stats["latest_callback_error"])
        with patch("autoclicker.gui.main_window.messagebox.showinfo") as notice:
            self.app.show_runtime_diagnostics()
            message = notice.call_args.args[1]
            self.assertIn("\nUI 콜백 오류:", message)
            self.assertIn("ZeroDivisionError", message)

    def test_connection_and_disconnection_controls_without_real_adb(self):
        frame = self.app.get_current_tab_frame()

        def connected():
            frame.clicker.device = Mock()
            return True

        def disconnected():
            frame.clicker.device = None

        frame.clicker.start_adb_server = Mock(side_effect=connected)
        frame.clicker.disconnect = Mock(side_effect=disconnected)
        frame.connect_button.invoke()
        for _ in range(60):
            self.app._drain_ui_queue()
            if frame.connect_button.cget("text") == "연결 해제":
                break
            time.sleep(0.01)
        frame.clicker.start_adb_server.assert_called_once()
        self.assertEqual(frame.start_button.cget("state"), "normal")
        self.assertEqual(frame.connect_button.cget("text"), "연결 해제")

        frame.connect_button.invoke()
        frame.clicker.disconnect.assert_called_once()
        self.assertIsNone(frame.clicker.device)
        self.assertEqual(frame.start_button.cget("state"), "disabled")

    def test_add_instance_dialog_manual_address_without_port_scan(self):
        from autoclicker.gui.dialogs.instance_dialog import AddInstanceWindow

        with patch.object(AddInstanceWindow, "start_device_scan", return_value=None):
            dialog = AddInstanceWindow(self.app)
            dialog.withdraw()
            dialog.custom_entry.insert(0, "127.0.0.1:5999")
            dialog.add_selected()
        self.assertTrue(any(
            frame.clicker.device_address == "127.0.0.1:5999"
            for frame in self.app.tab_frames.values()
        ))

    def test_settings_window_edit_save_syncs_all_instances(self):
        from autoclicker.gui.dialogs.settings_dialog import SettingsWindow

        frame = self.app.get_current_tab_frame()
        window = SettingsWindow(frame)
        window.withdraw()
        try:
            window.interval_entry.delete(0, "end")
            window.interval_entry.insert(0, "1.7")
            window.threshold_entry.delete(0, "end")
            window.threshold_entry.insert(0, "0.86")
            window.post_delay_entry.delete(0, "end")
            window.post_delay_entry.insert(0, "0.25")
            window.save_settings()
            self.assertTrue(all(
                sibling.clicker.scan_interval == 1.7
                for sibling in self.app.tab_frames.values()
            ))
            self.assertTrue(all(
                sibling.clicker.similarity_threshold == 0.86
                for sibling in self.app.tab_frames.values()
            ))
            self.assertTrue(all(
                sibling.clicker.post_action_delay == 0.25
                for sibling in self.app.tab_frames.values()
            ))
        finally:
            window.destroy()

    def test_shared_settings_sync_preserves_distinct_device_addresses(self):
        frames = list(self.app.tab_frames.values())
        before = [f.clicker.device_address for f in frames]
        frames[1].clicker.scan_interval = 1.5
        frames[1].clicker.similarity_threshold = 0.88
        self.app.sync_shared_settings_to_all(frames[1])
        self.assertEqual([f.clicker.device_address for f in frames], before)
        self.assertTrue(all(f.clicker.scan_interval == 1.5 for f in frames))
        self.assertTrue(all(
            f.clicker.similarity_threshold == 0.88 for f in frames
        ))


if __name__ == "__main__":
    unittest.main()
