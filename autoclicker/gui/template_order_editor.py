"""Dedicated full-list template priority editor.

The regular template view remains paginated for runtime performance. This
window temporarily shows the complete order so dragging across page
boundaries, moving to the beginning/end, and finding an item are easy.
"""
import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk

from autoclicker.gui.theme import (
    COLOR_CARD_BG, COLOR_NEUTRAL, COLOR_PRIMARY, COLOR_SUCCESS,
)


def relocate_template(order, source, target):
    """Return a reordered copy. Preserve every item exactly once."""
    if not (0 <= source < len(order) and 0 <= target < len(order)):
        return list(order)
    result = list(order)
    result.insert(target, result.pop(source))
    return result


class TemplateOrderEditor(ctk.CTkToplevel):
    def __init__(self, frame, is_fallback=False):
        super().__init__(frame)
        self.frame = frame
        self.is_fallback = bool(is_fallback)
        clicker = frame.clicker
        self.original = list(
            clicker.fallback_template_order if is_fallback
            else clicker.template_order
        )
        self.order = list(self.original)
        self._drag_index = None

        self.title("미매칭 템플릿 순서" if is_fallback else "기본 템플릿 순서")
        self.geometry("650x740")
        self.minsize(450, 440)
        self.transient(frame.winfo_toplevel())
        self.protocol("WM_DELETE_WINDOW", self.close)

        header = ctk.CTkLabel(
            self, text="☰ 끌어서 순서 변경", font=ctk.CTkFont(size=19, weight="bold"),
        )
        header.pack(anchor="w", padx=18, pady=(15, 0))
        self.help_label = ctk.CTkLabel(
            self, text=f"전체 {len(self.order)}개 · 마우스로 드래그하거나 우측 버튼으로 이동",
            font=ctk.CTkFont(size=13),
        )
        self.help_label.pack(anchor="w", padx=18, pady=(1, 9))

        search_bar = ctk.CTkFrame(self, fg_color="transparent")
        search_bar.pack(fill="x", padx=18, pady=(0, 8))
        self.search_var = tk.StringVar()
        self.search_box = ctk.CTkEntry(
            search_bar, placeholder_text="🔎 템플릿 찾아 선택", textvariable=self.search_var,
        )
        self.search_box.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(
            search_bar, text="다음 찾기", width=92, command=self.find_next,
        ).pack(side="right")
        self.search_box.bind("<Return>", lambda _event: self.find_next())
        self.search_var.trace_add("write", lambda *_: self.find_match())

        content = ctk.CTkFrame(self, fg_color=COLOR_CARD_BG)
        content.pack(fill="both", expand=True, padx=18, pady=(0, 8))
        self.listbox = tk.Listbox(
            content, selectmode="browse", activestyle="none", exportselection=False,
            bg="#252A33", fg="#F2F4F8", selectbackground="#2468D4",
            selectforeground="#FFFFFF", highlightthickness=0, borderwidth=0,
            font=("Malgun Gothic", 12),
        )
        self.listbox.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=8)
        scroll = ctk.CTkScrollbar(content, command=self.listbox.yview)
        scroll.pack(side="left", fill="y", padx=(0, 8), pady=8)
        self.listbox.configure(yscrollcommand=scroll.set)
        self.listbox.bind("<ButtonPress-1>", self._drag_start)
        self.listbox.bind("<B1-Motion>", self._drag_motion)
        self.listbox.bind("<ButtonRelease-1>", self._drag_end)

        controls = ctk.CTkFrame(self, fg_color="transparent")
        controls.pack(fill="x", padx=18, pady=(0, 10))
        for caption, method in (
            ("맨 위", lambda: self.move_selected("top")),
            ("▲ 한 칸", lambda: self.move_selected("up")),
            ("▼ 한 칸", lambda: self.move_selected("down")),
            ("맨 아래", lambda: self.move_selected("bottom")),
        ):
            ctk.CTkButton(
                controls, text=caption, width=95,
                fg_color=COLOR_NEUTRAL, command=method,
            ).pack(side="left", padx=(0, 5))

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=18, pady=(0, 14))
        ctk.CTkLabel(
            footer, text="저장 전에는 실제 템플릿 순서가 변경되지 않습니다.",
            font=ctk.CTkFont(size=12),
        ).pack(side="left")
        ctk.CTkButton(
            footer, text="저장", width=84, fg_color=COLOR_SUCCESS,
            command=self.save,
        ).pack(side="right", padx=(6, 0))
        ctk.CTkButton(
            footer, text="취소", width=84, fg_color=COLOR_NEUTRAL,
            command=self.close,
        ).pack(side="right")

        self._render()
        self.grab_set()

    def _render(self, selected=None):
        top = self.listbox.yview()[0]
        self.listbox.delete(0, "end")
        for index, filename in enumerate(self.order):
            self.listbox.insert("end", f"{index + 1:>3}.  {filename}")
        if selected is not None and self.order:
            self._select(selected)
        elif self.order:
            self.listbox.yview_moveto(top)

    def _select(self, index):
        index = min(max(index, 0), len(self.order) - 1)
        self.listbox.selection_clear(0, "end")
        self.listbox.selection_set(index)
        self.listbox.activate(index)
        self.listbox.see(index)

    def selected_index(self):
        selection = self.listbox.curselection()
        return selection[0] if selection else None

    def move_selected(self, direction):
        source = self.selected_index()
        if source is None:
            return
        target = {
            "top": 0, "up": source - 1, "down": source + 1,
            "bottom": len(self.order) - 1,
        }[direction]
        if 0 <= target < len(self.order) and source != target:
            self.order = relocate_template(self.order, source, target)
            self._render(target)

    def _drag_start(self, event):
        self._drag_index = None
        if self.order:
            index = self.listbox.nearest(event.y)
            bbox = self.listbox.bbox(index)
            if bbox and bbox[1] <= event.y < bbox[1] + bbox[3]:
                self._drag_index = index

    def _drag_motion(self, event):
        if self._drag_index is None:
            return
        if event.y < 0:
            self.listbox.yview_scroll(-1, "units")
        elif event.y > self.listbox.winfo_height():
            self.listbox.yview_scroll(1, "units")
        target = self.listbox.nearest(event.y)
        if target != self._drag_index:
            previous = self._drag_index
            self.order = relocate_template(self.order, previous, target)
            self._drag_index = target
            # Refresh only rows affected by the drag, instead of repainting
            # every template on every mouse-motion notification.
            first, last = sorted((previous, target))
            self.listbox.delete(first, last)
            for offset, filename in enumerate(self.order[first:last + 1]):
                index = first + offset
                self.listbox.insert(index, f"{index + 1:>3}.  {filename}")
            self._select(target)

    def _drag_end(self, _event):
        self._drag_index = None

    def find_match(self):
        needle = self.search_var.get().strip().casefold()
        if not needle:
            return
        for index, filename in enumerate(self.order):
            if needle in filename.casefold():
                self._select(index)
                break

    def find_next(self):
        needle = self.search_var.get().strip().casefold()
        if not needle or not self.order:
            return
        start = self.selected_index()
        start = -1 if start is None else start
        for n in range(1, len(self.order) + 1):
            index = (start + n) % len(self.order)
            if needle in self.order[index].casefold():
                self._select(index)
                return

    def save(self):
        if self.order == self.original:
            self.close()
            return
        clicker = self.frame.clicker
        attr = ("fallback_template_order" if self.is_fallback else "template_order")
        previous = list(getattr(clicker, attr))
        setattr(clicker, attr, list(self.order))
        try:
            if clicker.save_config() is False:
                raise RuntimeError("설정 파일 저장에 실패했습니다.")
        except Exception as error:
            setattr(clicker, attr, previous)
            messagebox.showerror("순서 저장 실패", str(error), parent=self)
            return

        self.frame._template_pages[self.is_fallback] = 0
        self.frame.app_owner.update_all_template_order(self.order, self.is_fallback)
        self.close()

    def close(self):
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()
