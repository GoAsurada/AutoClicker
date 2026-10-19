"""Preview template images as an in-app overlay rather than an OS popup.

Separate Tk Toplevel windows were not reliably visible in packaged Windows
builds.  A regular child Frame lives within AutoClicker's root window, so it
cannot get lost behind the parent or remain on top of another application.
"""
from collections import OrderedDict
import os
import tkinter as tk

from PIL import Image, ImageTk


def in_app_preview_position(anchor, preview_size, client_size, margin=8):
    """Place below/above the hovered row, inside the app, without covering it.

    anchor: (row_left, row_top, row_right, row_bottom, pointer_x).
    """
    left, top, right, bottom, pointer = anchor
    width, height = preview_size
    client_w, client_h = client_size
    x = max(margin, min(pointer + 12, max(margin, client_w - width - margin)))
    below = bottom + 6
    above = top - height - 6
    if below + height + margin <= client_h:
        y = below
    elif above >= margin:
        y = above
    else:
        # Narrow windows still display the image inside the available area.
        y = max(margin, min(below, max(margin, client_h - height - margin)))
    return int(x), int(y)


class TemplatePreviewTooltip:
    """One bounded thumbnail overlay for the AutoClicker application."""

    _instance = None
    _image_cache = OrderedDict()
    _IMAGE_CACHE_MAX = 50

    @classmethod
    def get_instance(cls, root_window=None):
        if cls._instance is None:
            cls._instance = cls(root_window)
        elif root_window is not None:
            cls._instance._set_root(root_window)
        return cls._instance

    def __init__(self, root_window=None):
        self.root = None
        self._bound_root = None
        self.tip_window = None  # compatibility: now an in-app tk.Frame
        self._hover_after_id = None
        self._dismiss_after_id = None
        self._scheduled_widget = None
        self._visible_widget = None
        self._leave_after_id = None
        self._leave_widget = None
        self._last_error = None
        self._show_attempts = 0
        self._panel_creations = 0
        if root_window is not None:
            self._set_root(root_window)

    def _set_root(self, root_window):
        if self.root is root_window:
            return
        self.hide()
        self.root = root_window
        if root_window is not self._bound_root:
            self._bound_root = root_window
            try:
                # A child panel cannot float above other applications.
                # Avoid FocusOut entirely: it can also fire while focus
                # moves between controls inside AutoClicker.
                root_window.bind("<Unmap>", lambda _evt: self.hide(), add="+")
            except tk.TclError:
                pass

    @staticmethod
    def _cursor_inside(widget):
        try:
            if not widget.winfo_exists() or not widget.winfo_viewable():
                return False
            x, y = widget.winfo_pointerx(), widget.winfo_pointery()
            left, top = widget.winfo_rootx(), widget.winfo_rooty()
            return left <= x < left + widget.winfo_width() and (
                top <= y < top + widget.winfo_height()
            )
        except tk.TclError:
            return False

    def schedule_show(self, widget, image_path, title_text="", offset_text=""):
        # CTkLabel sends Enter/Leave from BOTH its canvas and inner Tk label.
        # Do not restart the 100ms delay whenever the cursor crosses between
        # those two children without leaving the overall template label.
        self._cancel_pending_leave()
        if self._scheduled_widget is widget and self._hover_after_id is not None:
            return
        if self._visible_widget is widget and self.tip_window is not None:
            return
        self.hide()
        self._scheduled_widget = widget
        try:
            self._hover_after_id = widget.after(
                100, lambda: self.show(
                    widget, image_path, title_text, offset_text,
                    from_hover=True,
                )
            )
        except tk.TclError as exc:
            self._last_error = str(exc)

    def _cancel_pending_leave(self):
        if self._leave_after_id is not None and self._leave_widget is not None:
            try:
                self._leave_widget.after_cancel(self._leave_after_id)
            except tk.TclError:
                pass
        self._leave_after_id = None
        self._leave_widget = None

    def schedule_hide_if_left(self, widget):
        # An immediate Leave handler used to kill the popup when pointer
        # crossed the native CTkLabel canvas/text boundary.
        self._cancel_pending_leave()
        self._leave_widget = widget
        try:
            self._leave_after_id = widget.after(65, self._hide_if_left)
        except tk.TclError:
            self.hide()

    def _hide_if_left(self):
        widget = self._leave_widget
        self._leave_after_id = None
        self._leave_widget = None
        if widget is None or not self._cursor_inside(widget):
            self.hide()

    def cancel(self, event=None):
        self.hide()

    def hide(self):
        self._cancel_pending_leave()
        if self._scheduled_widget is not None and self._hover_after_id is not None:
            try:
                self._scheduled_widget.after_cancel(self._hover_after_id)
            except tk.TclError:
                pass
        self._hover_after_id = None
        self._scheduled_widget = None

        if self._visible_widget is not None and self._dismiss_after_id is not None:
            try:
                self._visible_widget.after_cancel(self._dismiss_after_id)
            except tk.TclError:
                pass
        self._dismiss_after_id = None
        self._visible_widget = None

        if self.tip_window is not None:
            try:
                self.tip_window.destroy()
            except tk.TclError:
                pass
            self.tip_window = None

    def _watch_hover(self):
        # Avoid timers surviving a destroyed label or its parent tab.
        self._dismiss_after_id = None
        widget = self._visible_widget
        if widget is None or not self._cursor_inside(widget):
            self.hide()
            return
        if self.tip_window is None or not self.tip_window.winfo_exists():
            self.hide()
            return
        try:
            self._dismiss_after_id = widget.after(130, self._watch_hover)
        except tk.TclError:
            self.hide()

    @classmethod
    def _resized_image(cls, path):
        stat = os.stat(path)
        sig = (os.path.normcase(os.path.abspath(path)), stat.st_mtime_ns)
        cached = cls._image_cache.get(sig)
        if cached is not None:
            cls._image_cache.move_to_end(sig)
            return cached
        with Image.open(path) as original:
            width, height = original.size
            original.load()
            scale = min(200 / max(1, width), 140 / max(1, height), 1.0)
            image = original.convert("RGBA")
            if scale < 1:
                image = image.resize(
                    (max(1, round(width * scale)), max(1, round(height * scale))),
                    Image.Resampling.LANCZOS,
                )
        result = (image, width, height)
        cls._image_cache[sig] = result
        while len(cls._image_cache) > cls._IMAGE_CACHE_MAX:
            cls._image_cache.popitem(last=False)
        return result

    def show(self, widget, image_path, title_text="", offset_text="",
             from_hover=False):
        # A genuine Enter event is more reliable than rechecking viewability
        # in an isolated Windows desktop. The watchdog handles pointer exit.
        self.hide()
        self._show_attempts += 1
        self._last_error = None
        if not os.path.isfile(image_path):
            self._last_error = f"미리보기 파일 없음: {image_path}"
            return False
        try:
            root = self.root
            if root is None or not root.winfo_exists():
                root = widget.winfo_toplevel()
                self._set_root(root)
            if not root.winfo_exists():
                self._last_error = "미리보기 본창이 이미 닫혔습니다."
                return False

            image, image_width, image_height = self._resized_image(image_path)
            photo = ImageTk.PhotoImage(image, master=root)
            panel = tk.Frame(
                root, background="#1A1D20", highlightbackground="#3B82F6",
                highlightthickness=1, borderwidth=0, padx=8, pady=6,
            )
            self.tip_window = panel
            tk.Label(
                panel, text=f"🖼️ {title_text or os.path.basename(image_path)}",
                font=("Segoe UI", 10, "bold"), foreground="#60A5FA",
                background="#1A1D20", anchor="w",
            ).pack(fill="x", pady=(0, 4))
            picture = tk.Label(
                panel, image=photo, background="#0D1117",
                relief="solid", borderwidth=1,
            )
            picture.image = photo  # Keep the Tk image alive.
            picture.pack(pady=(0, 4))
            meta = f"크기: {image_width}x{image_height}px"
            if offset_text:
                meta += f"  |  {offset_text}"
            tk.Label(
                panel, text=meta, font=("Segoe UI", 9),
                foreground="#9CA3AF", background="#1A1D20",
            ).pack(fill="x")

            panel.update_idletasks()
            label_left = widget.winfo_rootx() - root.winfo_rootx()
            label_top = widget.winfo_rooty() - root.winfo_rooty()
            label_right = label_left + widget.winfo_width()
            label_bottom = label_top + widget.winfo_height()
            pointer = widget.winfo_pointerx() - root.winfo_rootx()
            x, y = in_app_preview_position(
                (label_left, label_top, label_right, label_bottom, pointer),
                (panel.winfo_reqwidth(), panel.winfo_reqheight()),
                (root.winfo_width(), root.winfo_height()),
            )
            panel.place(x=x, y=y)
            panel.lift()
            self._visible_widget = widget
            self._dismiss_after_id = widget.after(130, self._watch_hover)
            self._panel_creations += 1
            return True
        except (OSError, tk.TclError, RuntimeError, ValueError) as exc:
            self._last_error = f"{type(exc).__name__}: {exc}"
            self.hide()
            return False

    def diagnostics(self):
        return {
            "hover_scheduled": self._hover_after_id is not None,
            "show_attempts": self._show_attempts,
            "panel_creations": self._panel_creations,
            "panel_exists": bool(
                self.tip_window is not None and self.tip_window.winfo_exists()
            ),
            "last_error": self._last_error or "없음",
        }
