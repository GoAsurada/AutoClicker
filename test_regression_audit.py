"""Regression audit for settings/counter integrity and Tk lifecycle.

These tests use isolated mocks and disposable test windows. They do not change
the user's installed AutoClicker, emulator state, or template files.
"""
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from autoclicker.gui.main_window import App


class GUIStateAuditTests(unittest.TestCase):
    @staticmethod
    def make_frame():
        counts = {"a.png": 7, "b.png": 11}
        fallback = {"fallback.png": 4}
        clicker = Mock()
        clicker.template_counts = counts
        clicker.fallback_template_counts = fallback

        def reset_counts():
            counts.update({name: 0 for name in counts})

        def reset_fallback_counts():
            fallback.update({name: 0 for name in fallback})

        clicker.reset_counts.side_effect = reset_counts
        clicker.reset_fallback_counts.side_effect = reset_fallback_counts

        label = Mock()
        value = {"text": "11회"}
        label.winfo_exists.return_value = True
        label.cget.side_effect = lambda key: value[key]
        label.configure.side_effect = lambda **kw: value.update(kw)
        frame = SimpleNamespace(
            clicker=clicker,
            template_count_labels={"b.png": label},
            fallback_template_count_labels={},
            _match_ui_lock=threading.Lock(),
            _pending_match_counts={
                ("b.png", False): 11,
                ("fallback.png", True): 4,
            },
        )
        return frame, value

    def test_reset_is_single_shared_operation_and_old_cache_is_not_replayed(self):
        frames = [self.make_frame()[0] for _ in range(5)]
        label_values = {}
        for index, f in enumerate(frames):
            labels = self.make_frame()[0].template_count_labels
            f.template_count_labels = labels
            label_values[index] = labels["b.png"]
        app = SimpleNamespace(
            tab_frames={str(i): f for i, f in enumerate(frames)},
            _ui_latest_match_counts={("b.png", False): 11, ("fallback.png", True): 4},
        )
        App.reset_all_template_counts(app, is_fallback=False)
        # Shared on-disk count table should be reset only once, not per tab.
        self.assertEqual(sum(f.clicker.reset_counts.call_count for f in frames), 1)
        self.assertEqual([f.clicker.template_counts["b.png"] for f in frames], [0] * 5)
        self.assertNotIn(("b.png", False), app._ui_latest_match_counts)
        self.assertEqual(app._ui_latest_match_counts[("fallback.png", True)], 4)
        for f in frames:
            self.assertNotIn(("b.png", False), f._pending_match_counts)
            self.assertEqual(f._pending_match_counts[("fallback.png", True)], 4)
        App._sync_visible_template_counts(app, frames[0])
        self.assertEqual(frames[0].template_count_labels["b.png"].cget("text"), "0회")

    def test_reset_fallback_does_not_touch_normal_counts(self):
        frames = [self.make_frame()[0] for _ in range(3)]
        app = SimpleNamespace(
            tab_frames={str(i): f for i, f in enumerate(frames)},
            _ui_latest_match_counts={("a.png", False): 7, ("fallback.png", True): 4},
        )
        App.reset_all_template_counts(app, is_fallback=True)
        self.assertEqual(sum(f.clicker.reset_fallback_counts.call_count for f in frames), 1)
        self.assertEqual([f.clicker.fallback_template_counts["fallback.png"] for f in frames], [0] * 3)
        self.assertEqual([f.clicker.template_counts["a.png"] for f in frames], [7] * 3)
        self.assertNotIn(("fallback.png", True), app._ui_latest_match_counts)
        self.assertEqual(app._ui_latest_match_counts[("a.png", False)], 7)

    def test_empty_instance_list_reset_does_not_crash(self):
        app = SimpleNamespace(tab_frames={}, _ui_latest_match_counts={})
        App.reset_all_template_counts(app, is_fallback=False)

    def test_destroy_cancels_all_pending_tk_callbacks(self):
        configuration = {"instances": [{"device_address": "127.0.0.1:5557"}]}
        with patch("autoclicker.gui.main_window.AutoClicker.read_config",
                   return_value=configuration), patch.object(
            App, "save_app_config", return_value=None
        ):
            app = App()
            app.withdraw()
            before = tuple(app.tk.call("after", "info"))
            self.assertGreater(len(before), 0)
            app.destroy()
            self.assertEqual(tuple(app.tk.call("after", "info")), ())


if __name__ == "__main__":
    unittest.main()
