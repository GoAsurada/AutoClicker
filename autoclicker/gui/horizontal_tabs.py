"""One-row instance navigation that fits all tabs without horizontal scrolling.

The complete address remains available in the existing instance selector.
Tab buttons display compact instance numbers at narrower viewport widths.
"""
import re

import customtkinter as ctk

from autoclicker.gui.theme import (
    COLOR_DANGER, COLOR_DANGER_HOVER, COLOR_NEUTRAL, COLOR_NEUTRAL_HOVER,
    COLOR_PRIMARY, COLOR_PRIMARY_HOVER, COLOR_TEXT_PRIMARY,
)


def compact_instance_label(name, slot_width, warning=False):
    """Shorten only the caption, never the identity used to select a tab."""
    match = re.match(r"Inst\s+(\d+)\b", name)
    short = match.group(1) if match else name.split(" (", 1)[0]
    port = re.search(r":(\d+)\)?$", name)
    # Reclaim room without deleting the useful original port numbers.
    if slot_width >= 110:
        caption = f"Inst {short} :{port.group(1)}" if port else f"Inst {short}"
    elif slot_width >= 65:
        caption = f"Inst {short}"
    else:
        caption = short[:4]
    return f"⚠ {caption}" if warning else caption


class HorizontalInstanceTabs(ctk.CTkFrame):
    """Grid-weighted buttons: all configured instances in exactly one row."""

    def __init__(self, master, command):
        super().__init__(master, fg_color="transparent", corner_radius=0)
        self._command = command
        self._buttons = {}
        self._selected = None
        self._warnings = set()
        self._font = ctk.CTkFont(size=13, weight="bold")
        self._last_slot = None
        self.bind("<Configure>", self._on_resize)

    @property
    def names(self):
        return tuple(self._buttons)

    def _on_resize(self, event=None):
        # Tk fires frequent Configure notifications while a window is dragged.
        # Only the three caption-width tiers affect the layout.
        if not self._buttons:
            return
        width = event.width if event is not None else self.winfo_width()
        slot = max(1, (width - 4 * len(self._buttons)) // len(self._buttons))
        tier = 2 if slot >= 110 else (1 if slot >= 65 else 0)
        if tier != self._last_slot:
            self._last_slot = tier
            self._render()

    def set_tabs(self, names, selected=None):
        names = list(dict.fromkeys(names))
        old_names = tuple(self._buttons)
        for name in old_names:
            if name not in names:
                self._buttons.pop(name).destroy()
                self._warnings.discard(name)
        for i in range(len(old_names)):
            self.grid_columnconfigure(i, weight=0, minsize=0)
        for name in names:
            if name not in self._buttons:
                self._buttons[name] = ctk.CTkButton(
                    self, text="", width=1, height=34, corner_radius=5,
                    font=self._font,
                    command=lambda value=name: self._command(value),
                )
            self._buttons[name].grid_forget()
        self._buttons = {name: self._buttons[name] for name in names}
        for index, name in enumerate(names):
            self.grid_columnconfigure(index, weight=1, uniform="instance", minsize=0)
            self._buttons[name].grid(
                row=0, column=index, sticky="ew", padx=2, pady=3
            )
        if selected in self._buttons:
            self._selected = selected
        elif self._selected not in self._buttons:
            self._selected = names[0] if names else None
        self._last_slot = None
        self._render()

    def set_selected(self, name):
        if name in self._buttons:
            self._selected = name
            self._render()

    def set_warning(self, name, warning):
        if warning:
            self._warnings.add(name)
        else:
            self._warnings.discard(name)
        if name in self._buttons:
            self._style_button(name)

    def _render(self):
        for name in self._buttons:
            self._style_button(name)

    def _style_button(self, name):
        count = max(1, len(self._buttons))
        available = self.winfo_width()
        if available < 100:
            available = max(200, self.winfo_toplevel().winfo_width() - 20)
        slot_width = max(1, (available - 4 * count) // count)
        active = name == self._selected
        warning = name in self._warnings
        fg = COLOR_PRIMARY if active else (COLOR_DANGER if warning else COLOR_NEUTRAL)
        hover = COLOR_PRIMARY_HOVER if active else (
            COLOR_DANGER_HOVER if warning else COLOR_NEUTRAL_HOVER
        )
        caption = compact_instance_label(name, slot_width, warning)
        button = self._buttons[name]
        desired = (caption, fg, hover, active)
        if getattr(button, "_instance_style_cache", None) == desired:
            return
        button._instance_style_cache = desired
        button.configure(
            text=caption, fg_color=fg, hover_color=hover,
            text_color=COLOR_TEXT_PRIMARY,
            border_width=2 if active else 0,
            border_color=COLOR_TEXT_PRIMARY if active else fg,
        )
