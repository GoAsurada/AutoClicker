"""Long-duration UI message burst regression coverage.

No emulator is required. Exercise multiple producers while the Tk consumer is
slower than the event source and verify that transient updates remain bounded.
"""
from concurrent.futures import ThreadPoolExecutor
import threading
import unittest
from unittest.mock import Mock, patch

from autoclicker.gui.ui_mailbox import UIEventMailbox
from autoclicker.gui.tab_view import InstanceTabFrame
from autoclicker.gui.main_window import App


class UIMessageStressTests(unittest.TestCase):
    def test_100k_transient_messages_only_queue_one_per_instance(self):
        mailbox = UIEventMailbox()
        count = 10
        per_instance = 10000
        observed = []

        def worker(index):
            for value in range(per_instance):
                mailbox.put(
                    lambda x=index, v=value: observed.append((x, v)),
                    key=(index, "log"),
                )
        with ThreadPoolExecutor(max_workers=count) as executor:
            list(executor.map(worker, range(count)))
        stats = mailbox.stats()
        self.assertEqual(stats["pending"], count)
        self.assertEqual(stats["peak_pending"], count)
        self.assertEqual(stats["coalesced_replacements"], count * (per_instance - 1))
        for _ in range(count):
            mailbox.get_nowait()()
        self.assertEqual(mailbox.stats()["pending"], 0)
        self.assertEqual(sorted(observed), [(i, per_instance-1) for i in range(count)])

    def test_state_transitions_remain_in_order_when_updates_are_coalesced(self):
        mailbox = UIEventMailbox()
        actual = []
        mailbox.put(lambda: actual.append("start"))
        for i in range(20000):
            mailbox.put(lambda v=i: actual.append(v), key="counters")
        mailbox.put(lambda: actual.append("stop"))
        self.assertEqual(mailbox.stats()["pending"], 3)
        for _ in range(3):
            mailbox.get_nowait()()
        self.assertEqual(actual, ["start", 19999, "stop"])

    def test_hidden_instance_keeps_only_last_150_short_messages(self):
        dummy = Mock()
        dummy._destroyed = False
        dummy._log_lock = threading.Lock()
        dummy._log_buffer = []
        dummy._log_is_visible = False
        dummy._log_flush_scheduled = False
        for _ in range(12000):
            InstanceTabFrame.log_message(dummy, "x" * 2000)
        self.assertEqual(len(dummy._log_buffer), 150)
        self.assertLessEqual(max(map(len, dummy._log_buffer)), 630)
        dummy.request_log_flush.assert_not_called()

    def test_global_modal_dialog_is_rate_limited(self):
        dummy = Mock()
        dummy._closing = False
        dummy._warning_dialog_open = False
        dummy._last_warning_popup_at = -100.0
        with patch("autoclicker.gui.main_window.messagebox.showwarning") as show, patch(
            "autoclicker.gui.main_window.time.monotonic", return_value=100.0
        ):
            self.assertTrue(App.show_runtime_warning(dummy, "alert", "detail"))
            for _ in range(20):
                self.assertFalse(App.show_runtime_warning(dummy, "alert", "detail"))
        show.assert_called_once()


if __name__ == "__main__":
    unittest.main()
