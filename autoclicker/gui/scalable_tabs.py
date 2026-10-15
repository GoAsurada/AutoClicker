"""Tab content container that does not grow a hidden segmented-button strip.

CustomTkinter's CTkTabview eagerly maintains one clickable segment per tab.
Even when its segmented control is hidden, managing many tabs can produce
layout and geometry recalculations. The caller owns instance selection.
"""
import customtkinter as ctk


class ScalableTabView(ctk.CTkFrame):
    """Lightweight, selector-driven tab pages with CTkTabview-compatible API."""

    def __init__(self, master, **kwargs):
        kwargs.setdefault("fg_color", "transparent")
        super().__init__(master, **kwargs)
        self._tabs = {}
        self._current = None

    def add(self, name):
        if name in self._tabs:
            raise ValueError(f"Tab already exists: {name}")
        child = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        self._tabs[name] = child
        if self._current is None:
            self.set(name)
        return child

    def get(self):
        return self._current or ""

    def set(self, name):
        if name not in self._tabs:
            raise ValueError(f"Unknown tab: {name}")
        if self._current == name:
            return
        previous = self._tabs.get(self._current)
        if previous is not None:
            previous.pack_forget()
        self._current = name
        self._tabs[name].pack(fill="both", expand=True)

    def delete(self, name):
        if name not in self._tabs:
            return
        child = self._tabs.pop(name)
        was_current = self._current == name
        if was_current:
            self._current = None
        child.destroy()
        if was_current and self._tabs:
            self.set(next(iter(self._tabs)))
