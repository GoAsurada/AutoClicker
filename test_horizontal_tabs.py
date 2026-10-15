"""Regression tests for restored horizontally scrollable instance tabs."""

import sys
import unittest


@unittest.skipUnless(sys.platform == "win32", "Tk integration requires Windows")
class HorizontalInstanceTabTests(unittest.TestCase):
    def test_twenty_tabs_keep_fixed_window_width_and_restore_clicks(self):
        import customtkinter as ctk
        from autoclicker.gui.horizontal_tabs import HorizontalInstanceTabs

        root = ctk.CTk()
        root.geometry("900x600")
        root.withdraw()
        chosen = []
        try:
            tabs = HorizontalInstanceTabs(root, command=chosen.append)
            tabs.pack(fill="x", padx=10)
            names = [
                f"Inst {i + 1} (:{5557 + i * 2})"
                for i in range(20)
            ]
            tabs.set_tabs(names, selected=names[0])
            root.update_idletasks()
            self.assertEqual(tabs.names, tuple(names))
            self.assertEqual(tabs._selected, names[0])
            self.assertLess(tabs.winfo_reqwidth(), 800)

            tabs._buttons[names[9]].invoke()
            self.assertEqual(chosen, [names[9]])
            tabs.set_selected(names[9])
            root.update_idletasks()
            self.assertEqual(tabs._selected, names[9])

            tabs.set_warning(names[13], True)
            self.assertIn(names[13], tabs._warnings)
            tabs.set_warning(names[13], False)
            self.assertNotIn(names[13], tabs._warnings)

            tabs.set_tabs(names[:10], selected=names[4])
            root.update_idletasks()
            self.assertEqual(len(tabs.names), 10)
            self.assertEqual(tabs._selected, names[4])
            self.assertNotIn(names[13], tabs._buttons)
            self.assertLess(tabs.winfo_reqwidth(), 800)
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
