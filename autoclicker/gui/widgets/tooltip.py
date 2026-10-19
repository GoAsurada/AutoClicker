"""Safe, parent-owned hover preview for template thumbnails.

A preview must never remain on top of other applications after the user
switches windows. Placement is bounded to the cursor's monitor work area,
not the primary screen's width (which is wrong for multiple monitors).
"""
import ctypes
import os
import sys
import tkinter as tk

from PIL import Image, ImageTk


def _cursor_monitor_work_area(x, y, widget):
    """Return (left, top, right, bottom) of the cursor monitor's work area."""
    if sys.platform == "win32":
        try:
            class POINT(ctypes.Structure):
                _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

            class RECT(ctypes.Structure):
                _fields_ = [
                    ("left", ctypes.c_long), ("top", ctypes.c_long),
                    ("right", ctypes.c_long), ("bottom", ctypes.c_long),
                ]

            class MONITORINFO(ctypes.Structure):
                _fields_ = [
                    ("cbSize", ctypes.c_ulong), ("rcMonitor", RECT),
                    ("rcWork", RECT), ("dwFlags", ctypes.c_ulong),
                ]

            user32 = ctypes.windll.user32
            user32.MonitorFromPoint.argtypes = [POINT, ctypes.c_ulong]
            user32.MonitorFromPoint.restype = ctypes.c_void_p
            user32.GetMonitorInfoW.argtypes = [ctypes.c_void_p, ctypes.POINTER(MONITORINFO)]
            user32.GetMonitorInfoW.restype = ctypes.c_int
            monitor = user32.MonitorFromPoint(POINT(int(x), int(y)), 2)
            info = MONITORINFO()
            info.cbSize = ctypes.sizeof(MONITORINFO)
            if monitor and user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
                rect = info.rcWork
                return rect.left, rect.top, rect.right, rect.bottom
        except (AttributeError, OSError, ValueError):
            pass

    try:
        # The virtual root may include monitors left or above the primary.
        left = widget.winfo_vrootx()
        top = widget.winfo_vrooty()
        return (left, top,
                left + widget.winfo_vrootwidth(),
                top + widget.winfo_vrootheight())
    except (tk.TclError, AttributeError):
        return 0, 0, widget.winfo_screenwidth(), widget.winfo_screenheight()


def preview_position(pointer_x, pointer_y, width, height, bounds):
    """Keep the preview within one monitor; flip when near its edges."""
    left, top, right, bottom = bounds
    left += 8
    top += 8
    right -= 8
    bottom -= 8
    x = pointer_x + 16
    y = pointer_y + 12
    if x + width > right:
        x = pointer_x - width - 12
    if y + height > bottom:
        y = pointer_y - height - 10
    x = max(left, min(x, max(left, right - width)))
    y = max(top, min(y, max(top, bottom - height)))
    return int(x), int(y)


def _our_app_is_foreground():
    """On Windows, never float a thumbnail above an unrelated application."""
    if sys.platform != "win32":
        return True
    try:
        user32 = ctypes.windll.user32
        user32.GetForegroundWindow.restype = ctypes.c_void_p
        hwnd = user32.GetForegroundWindow()
        if not hwnd:  # Inaccessible desktop: rely on cursor containment.
            return True
        pid = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(pid))
        return pid.value == os.getpid()
    except (AttributeError, OSError):
        return True


class TemplatePreviewTooltip:
    """Small hover preview owned by AutoClicker, never globally topmost."""

    _instance = None
    _image_cache = {}
    _image_cache_order = []
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
        self.tip_window = None
        self._hover_after_id = None
        self._dismiss_after_id = None
        self._scheduled_widget = None
        self._visible_widget = None
        if root_window is not None:
            self._set_root(root_window)

    def _set_root(self, root_window):
        if root_window is self.root:
            return
        self.cancel()
        self.root = root_window
        if root_window is not self._bound_root:
            self._bound_root = root_window
            try:
                root_window.bind("<FocusOut>", lambda _event: self.hide(), add="+")
                root_window.bind("<Unmap>", lambda _event: self.hide(), add="+")
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
        self.cancel()
        self._scheduled_widget = widget
        self._hover_after_id = widget.after(
            200, lambda: self.show(widget, image_path, title_text, offset_text)
        )

    def cancel(self, event=None):
        self.hide()

    def hide(self):
        if self._hover_after_id is not None and self._scheduled_widget is not None:
            try:
                if self._scheduled_widget.winfo_exists():
                    self._scheduled_widget.after_cancel(self._hover_after_id)
            except tk.TclError:
                pass
        self._hover_after_id = None
        self._scheduled_widget = None

        if self._dismiss_after_id is not None and self._visible_widget is not None:
            try:
                if self._visible_widget.winfo_exists():
                    self._visible_widget.after_cancel(self._dismiss_after_id)
            except tk.TclError:
                pass
        self._dismiss_after_id = None
        self._visible_widget = None

        if self.tip_window is not None:
            try:
                if self.tip_window.winfo_exists():
                    self.tip_window.destroy()
            except tk.TclError:
                pass
            self.tip_window = None

    def _hover_still_valid(self, widget):
        return self._cursor_inside(widget) and _our_app_is_foreground()

    def _watch_hover(self):
        pending = self._dismiss_after_id
        widget = self._visible_widget
        self._dismiss_after_id = None
        # Normally the scheduled callback is now running. If this method is
        # also called directly during focus/hover races, cancel the previous
        # Tcl callback so no orphaned _watch_hover survives widget shutdown.
        if pending is not None and widget is not None:
            try:
                if widget.winfo_exists():
                    widget.after_cancel(pending)
            except tk.TclError:
                pass
        if widget is None or not self._hover_still_valid(widget):
            self.hide()
            return
        if self.tip_window is None or not self.tip_window.winfo_exists():
            self.hide()
            return
        self._dismiss_after_id = widget.after(150, self._watch_hover)

    def show(self, widget, image_path, title_text="", offset_text=""):
        if not os.path.isfile(image_path):
            return
        if not self._hover_still_valid(widget):
            self.hide()
            return

        self.hide()
        try:
            stat = os.stat(image_path)
            sig = (image_path, stat.st_mtime_ns)
            if sig in self._image_cache:
                photo_img, orig_w, orig_h = self._image_cache[sig]
            else:
                with Image.open(image_path) as pil_img:
                    orig_w, orig_h = pil_img.size
                    max_w, max_h = 200, 140
                    scale = min(max_w / max(1, orig_w), max_h / max(1, orig_h), 1.0)
                    if scale < 1.0:
                        new_w = max(1, int(orig_w * scale))
                        new_h = max(1, int(orig_h * scale))
                        scaled_img = pil_img.resize(
                            (new_w, new_h), Image.Resampling.LANCZOS
                        )
                    else:
                        scaled_img = pil_img.copy()
                photo_img = ImageTk.PhotoImage(scaled_img)
                self._image_cache[sig] = (photo_img, orig_w, orig_h)
                self._image_cache_order.append(sig)
                while len(self._image_cache_order) > self._IMAGE_CACHE_MAX:
                    evict_sig = self._image_cache_order.pop(0)
                    self._image_cache.pop(evict_sig, None)

            parent = (
                self.root if self.root is not None and self.root.winfo_exists()
                else widget.winfo_toplevel()
            )
            self.tip_window = tw = tk.Toplevel(parent)
            tw.wm_overrideredirect(True)
            tw.wm_transient(parent)
            # NEVER use wm_attributes("-topmost", True): that caused the
            # preview to float above Chrome and onto a different monitor.
            try:
                tw.wm_attributes("-alpha", 0.97)
            except tk.TclError:
                pass

            container = tk.Frame(
                tw, background="#1A1D20", highlightbackground="#3B82F6",
                highlightthickness=1, padx=8, pady=6,
            )
            container.pack(fill="both", expand=True)
            tk.Label(
                container, text=f"🖼️ {title_text or os.path.basename(image_path)}",
                font=("Segoe UI", 10, "bold"), foreground="#60A5FA",
                background="#1A1D20", anchor="w",
            ).pack(fill="x", pady=(0, 4))
            image_label = tk.Label(
                container, image=photo_img, background="#0D1117",
                relief="solid", borderwidth=1,
            )
            image_label.image = photo_img
            image_label.pack(pady=(0, 4))
            meta = f"크기: {orig_w}x{orig_h}px"
            if offset_text:
                meta += f"  |  {offset_text}"
            tk.Label(
                container, text=meta, font=("Segoe UI", 9),
                foreground="#9CA3AF", background="#1A1D20",
            ).pack(fill="x")

            tw.update_idletasks()
            x, y = widget.winfo_pointerx(), widget.winfo_pointery()
            bounds = _cursor_monitor_work_area(x, y, widget)
            pos_x, pos_y = preview_position(
                x, y, tw.winfo_reqwidth(), tw.winfo_reqheight(), bounds,
            )
            tw.wm_geometry(f"+{pos_x}+{pos_y}")
            self._visible_widget = widget
            self._dismiss_after_id = widget.after(150, self._watch_hover)
        except (OSError, tk.TclError, RuntimeError, ValueError):
            self.hide()
