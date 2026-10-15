"""Scrollable horizontal instance tabs; independent from the content pages.

The original instance tab bar remains available regardless of the number of
emulators. Only the navigation buttons are horizontally scrollable; they can
never expand the application's root geometry.
"""

import customtkinter as ctk

from autoclicker.gui.theme import (
    COLOR_DANGER, COLOR_DANGER_HOVER, COLOR_NEUTRAL, COLOR_NEUTRAL_HOVER,
    COLOR_PRIMARY, COLOR_PRIMARY_HOVER, COLOR_TEXT_PRIMARY,
)


class HorizontalInstanceTabs(ctk.CTkFrame):
    """Always-visible one-row instance navigation with a horizontal scrollbar."""

    def __init__(self, master, command):
        super().__init__(master, fg_color="transparent", corner_radius=0)
        self._command = command
        self._buttons = {}
        self._selected = None
        self._warnings = set()
        self._font = ctk.CTkFont(size=12, weight="bold")

        # Built-in horizontal canvas scrolling prevents layout-width growth.
        self.scroll = ctk.CTkScrollableFrame(
            self,
            orientation="horizontal",
            height=40,
            fg_color="transparent",
        )
        self.scroll.pack(fill="x", expand=True)

    @property
    def names(self):
        return tuple(self._buttons)

    def set_tabs(self, names, selected=None):
        names = list(dict.fromkeys(names))
        live = set(names)
        for name in tuple(self._buttons):
            if name not in live:
                self._buttons.pop(name).destroy()
                self._warnings.discard(name)
        for name in names:
            if name not in self._buttons:
                self._buttons[name] = ctk.CTkButton(
                    self.scroll,
                    text=name,
                    width=158,
                    height=32,
                    corner_radius=5,
                    font=self._font,
                    command=lambda value=name: self._command(value),
                )
            # Updating button order never rebuilds pages or touches ADB.
            self._buttons[name].pack_forget()
            self._buttons[name].pack(side="left", padx=(0, 5), pady=3)

        self._buttons = {name: self._buttons[name] for name in names}
        if selected is not None:
            self.set_selected(selected)
        elif self._selected not in self._buttons:
            self._selected = None
        self._render()

    def set_selected(self, name):
        if name not in self._buttons:
            return
        if self._selected != name:
            self._selected = name
            self._render()
        self.after_idle(self._scroll_selected_into_view)

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
        is_active = name == self._selected
        warning = name in self._warnings
        fg = COLOR_PRIMARY if is_active else (COLOR_DANGER if warning else COLOR_NEUTRAL)
        hover = COLOR_PRIMARY_HOVER if is_active else (
            COLOR_DANGER_HOVER if warning else COLOR_NEUTRAL_HOVER
        )
        self._buttons[name].configure(
            fg_color=fg,
            hover_color=hover,
            text_color=COLOR_TEXT_PRIMARY,
            border_width=2 if is_active else 0,
            border_color=COLOR_TEXT_PRIMARY if is_active else fg,
        )

    def _scroll_selected_into_view(self):
        if not self.winfo_exists() or self._selected not in self._buttons:
            return
        canvas = getattr(self.scroll, "_parent_canvas", None)
        if canvas is None or not canvas.winfo_exists():
            return
        button = self._buttons[self._selected]
        if not button.winfo_exists():
            return
        self.update_idletasks()
        visible_start = canvas.canvasx(0)
        visible_end = visible_start + canvas.winfo_width()
        left = button.winfo_x()
        right = left + button.winfo_width()
        if left >= visible_start and right <= visible_end:
            return
        region = canvas.bbox("all")
        if not region:
            return
        total = max(region[2] - region[0], 1)
        target = left if left < visible_start else right - canvas.winfo_width()
        canvas.xview_moveto(max(0.0, min(1.0, (target - region[0]) / total)))
