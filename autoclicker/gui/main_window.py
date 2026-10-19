import os
import sys
from collections import deque
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk

from autoclicker import __version__

VERSION = f"v{__version__}"

from autoclicker.core.constants import (
    CONFIG_FILENAME,
    DEVICE_ADDRESS,
    DEFAULT_ADB_MODE,
    DEFAULT_CUSTOM_ADB_PATH,
    VALID_ADB_MODES,
)
from autoclicker.core.environment import (
    get_app_dir,
    get_default_adb_path,
    resolve_adb_path,
    CONFIG_PATH,
)
from autoclicker.core.clicker import AutoClicker
from autoclicker.gui.theme import (
    COLOR_PRIMARY,
    COLOR_PRIMARY_HOVER,
    COLOR_SUCCESS,
    COLOR_SUCCESS_HOVER,
    COLOR_DANGER,
    COLOR_DANGER_HOVER,
    COLOR_DANGER_MUTED,
    COLOR_DANGER_MUTED_HOVER,
    COLOR_WARNING,
    COLOR_WARNING_HOVER,
    COLOR_INFO,
    COLOR_INFO_HOVER,
    COLOR_NEUTRAL,
    COLOR_NEUTRAL_HOVER,
    COLOR_CARD_BG,
    COLOR_CARD_INNER,
    COLOR_BORDER,
    COLOR_TEXT_MUTED,
    COLOR_TEXT_PRIMARY,
    RADIUS_SM,
    RADIUS_MD,
    RADIUS_LG,
    NO_MATCH_ACTION_MAP,
    REVERSE_NO_MATCH_ACTION_MAP,
    get_action_button_style,
    get_delay_button_style,
)
from autoclicker.gui.win32_utils import draw_korean_banner, set_opencv_window_title
from autoclicker.gui.widgets import (
    TemplateRowWidgets,
    CTKContextMenu,
    TemplatePreviewTooltip,
)
from autoclicker.gui.dialogs import (
    SettingsWindow,
    LicenseNoticeWindow,
    AddInstanceWindow,
)
from autoclicker.gui.tab_view import InstanceTabFrame
from autoclicker.gui.scalable_tabs import ScalableTabView
from autoclicker.gui.horizontal_tabs import HorizontalInstanceTabs
from autoclicker.gui.ui_mailbox import UIEventMailbox
from autoclicker.gui.font_setup import configure_app_fonts
from autoclicker.gui.device_discovery import discover_devices

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.ui_font_family = configure_app_fonts(self)

        self.title(f"Auto Clicker {VERSION}")
        self.geometry("1300x760")
        self.minsize(900, 600)
        
        self.tab_frames = {}
        self.warning_tabs = set()
        self.tab_counter = 0
        self._closing = False
        self._start_all_generation = 0
        self._initializing_tabs = True
        self._ui_queue = UIEventMailbox()
        self._ui_error_total = 0
        self._ui_recent_errors = deque(maxlen=20)
        self._ui_latest_match_counts = {}
        self._last_warning_popup_at = 0.0
        self._warning_dialog_open = False
        self._disconnect_all_busy = False
        self.opencv_lock = threading.Lock()
        self._ui_pump_id = self.after(50, self._drain_ui_queue)
        self._timer_pump_id = self.after(500, self._pump_timer_updates)

        # Preload templates in background thread
        threading.Thread(
            target=self._preload_configured_templates,
            daemon=True,
        ).start()

        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        # --- Top Global Control Toolbar ---
        self.top_bar = ctk.CTkFrame(self, fg_color=COLOR_CARD_BG, corner_radius=RADIUS_MD)
        self.top_bar.pack(fill="x", padx=8, pady=(6, 3))
        # The global toolbar uses one line when the window is wide enough,
        # and a compact two-line layout only when necessary. Nothing is hidden.
        self.brand_bar = ctk.CTkFrame(self.top_bar, fg_color="transparent")
        self.nav_bar = ctk.CTkFrame(self.top_bar, fg_color="transparent")
        self.action_bar = ctk.CTkFrame(self.top_bar, fg_color="transparent")
        self._toolbar_compact = None

        self.logo_label = ctk.CTkLabel(
            self.brand_bar,
            text="⚡ Auto Clicker", 
            font=ctk.CTkFont(size=18, weight="bold")
        )
        self.logo_label.pack(side="left", padx=(10, 6), pady=4)

        # Top Bar Control Buttons (Unified style & font)
        btn_font = ctk.CTkFont(size=13, weight="bold")

        self.connect_all_btn = ctk.CTkButton(
            self.action_bar,
            text="전체 연결",
            font=btn_font,
            width=105,
            height=34,
            fg_color=COLOR_PRIMARY,
            hover_color=COLOR_PRIMARY_HOVER,
            corner_radius=RADIUS_MD,
            command=self.connect_all_instances
        )
        self.connect_all_btn.pack(side="left", padx=3, pady=4)

        self.disconnect_all_btn = ctk.CTkButton(
            self.action_bar,
            text="전체 연결 끊기",
            font=btn_font,
            width=122,
            height=34,
            fg_color=COLOR_NEUTRAL,
            hover_color=COLOR_NEUTRAL_HOVER,
            corner_radius=RADIUS_MD,
            command=self.disconnect_all_instances,
        )
        self.disconnect_all_btn.pack(side="left", padx=3, pady=4)

        self.start_all_btn = ctk.CTkButton(
            self.action_bar,
            text="전체 시작",
            font=btn_font,
            width=105,
            height=34,
            fg_color=COLOR_SUCCESS,
            hover_color=COLOR_SUCCESS_HOVER,
            corner_radius=RADIUS_MD,
            command=self.start_all_clickers
        )
        self.start_all_btn.pack(side="left", padx=3, pady=4)

        self.stop_all_btn = ctk.CTkButton(
            self.action_bar,
            text="전체 중지",
            font=btn_font,
            width=105,
            height=34,
            fg_color=COLOR_DANGER,
            hover_color=COLOR_DANGER_HOVER,
            corner_radius=RADIUS_MD,
            command=self.stop_all_clickers
        )
        self.stop_all_btn.pack(side="left", padx=3, pady=4)

        self.add_tab_btn = ctk.CTkButton(
            self.action_bar,
            text="인스턴스 추가",
            font=btn_font,
            width=120,
            height=34,
            fg_color=COLOR_NEUTRAL,
            hover_color=COLOR_NEUTRAL_HOVER,
            corner_radius=RADIUS_MD,
            command=self.add_new_instance_dialog
        )
        self.add_tab_btn.pack(side="left", padx=3, pady=4)

        # Settings Button (Top-Right 최상단 우측)
        self.settings_btn = ctk.CTkButton(
            self.nav_bar,
            text="설정",
            font=btn_font,
            width=80,
            height=34,
            fg_color=COLOR_NEUTRAL,
            hover_color=COLOR_NEUTRAL_HOVER,
            corner_radius=RADIUS_MD,
            command=self.open_global_settings
        )
        self.settings_btn.pack(side="right", padx=(3, 8), pady=4)
        self.instance_selector = ctk.CTkOptionMenu(
            self.nav_bar, values=["인스턴스 선택"], width=140,
            height=34, font=ctk.CTkFont(size=13),
            command=self._select_instance,
        )
        self.instance_selector.pack(side="right", padx=(3, 5), pady=4)
        self.warning_button = ctk.CTkButton(
            self.nav_bar, text="⚠ 0", width=45, height=34,
            fg_color=COLOR_WARNING, hover_color=COLOR_WARNING_HOVER,
            command=self._jump_to_warning, state="disabled",
        )
        self.warning_button.pack(side="right", padx=(2, 3), pady=4)
        # Start conservatively so the initial requested width remains small
        # even before the window is mapped; expand to one row on Configure.
        self._arrange_toolbar_layout(compact=True)
        self.top_bar.bind("<Configure>", self._on_toolbar_resize)

        # All instance tabs stay on one row without a horizontal scrollbar.
        self.instance_tabs = HorizontalInstanceTabs(self, command=self._select_instance)
        self.instance_tabs.pack(fill="x", padx=8, pady=(0, 3))

        # --- Main Workspace: Tab View ---
        self.tabview = ScalableTabView(self)
        self.tabview.pack(fill="both", expand=True, padx=8, pady=(0, 6))

        # Load saved instances or create initial tab
        self.load_and_initialize_tabs()

        # Keyboard shortcuts
        self.bind("<Control-f>", self.on_ctrl_f)
        self.bind("<Control-F>", self.on_ctrl_f)
        self.bind("<Control-Shift-D>", self.show_runtime_diagnostics)

        # Auto refresh devices after short delay
        self.after(500, self.refresh_all_devices)

    def _on_toolbar_resize(self, event):
        # 1,110px fits full controls and current 10-tab bar at default DPI;
        # only re-pack when crossing the breakpoint.
        self._arrange_toolbar_layout(compact=event.width < 1110)

    def _arrange_toolbar_layout(self, compact):
        if self._toolbar_compact == compact:
            return
        self._toolbar_compact = compact
        for bar in (self.brand_bar, self.action_bar, self.nav_bar):
            bar.pack_forget()
        if compact:
            self.action_bar.pack(side="bottom", fill="x", padx=5, pady=(0, 2))
        self.brand_bar.pack(side="left", padx=(3, 0))
        self.nav_bar.pack(side="right", padx=(0, 3))
        if not compact:
            self.action_bar.pack(side="left", padx=(4, 0))

    def update_instance_warning(self, tab_name, is_warning):
        if is_warning == (tab_name in self.warning_tabs):
            return
        if is_warning:
            self.warning_tabs.add(tab_name)
        else:
            self.warning_tabs.discard(tab_name)
        count = len(self.warning_tabs)
        self.warning_button.configure(
            text=f"⚠ {count}", state="normal" if count else "disabled"
        )
        self.instance_tabs.set_warning(tab_name, is_warning)

    def _jump_to_warning(self):
        for tab_name in self.tab_frames:
            if tab_name in self.warning_tabs:
                self._select_instance(tab_name)
                return

    def _select_instance(self, tab_name):
        if tab_name not in self.tab_frames:
            return
        self.tabview.set(tab_name)
        self.instance_selector.set(tab_name)
        self.instance_tabs.set_selected(tab_name)
        self._set_active_log_frame(tab_name)
        self.after_idle(self.tab_frames[tab_name].ensure_templates_rendered)
        self.after_idle(self.tab_frames[tab_name].update_timer_display)
        self.after_idle(lambda: self._sync_visible_template_counts(
            self.tab_frames[tab_name]
        ) if tab_name in self.tab_frames else None)

    def _set_active_log_frame(self, tab_name):
        for name, frame in tuple(self.tab_frames.items()):
            frame._log_is_visible = name == tab_name
        active = self.tab_frames.get(tab_name)
        if active is not None:
            active.request_log_flush()

    def get_current_tab_frame(self):
        try:
            curr_tab_name = self.tabview.get()
            return self.tab_frames.get(curr_tab_name)
        except Exception:
            return None

    def on_ctrl_f(self, event=None):
        frame = self.get_current_tab_frame()
        if frame and hasattr(frame, "focus_search_box"):
            frame.focus_search_box()
            return "break"

    @staticmethod
    def _preload_configured_templates():
        config = AutoClicker.read_config(CONFIG_PATH)
        default_mode = AutoClicker._safe_bool(
            config.get("global_grayscale_matching", True),
            True,
        )
        modes = {default_mode}
        for inst in config.get("instances", []):
            modes.add(
                AutoClicker._safe_bool(
                    inst.get("grayscale_matching", default_mode),
                    default_mode,
                )
            )
        AutoClicker.preload_templates(grayscales=tuple(modes))

    def format_tab_name(self, index, device_address):
        addr_str = str(device_address).strip()
        if addr_str.startswith("emulator-"):
            short_addr = addr_str.replace("emulator-", "")
        elif addr_str.startswith("127.0.0.1:"):
            short_addr = addr_str.replace("127.0.0.1:", ":")
        elif len(addr_str) > 14:
            short_addr = addr_str[-12:]
        else:
            short_addr = addr_str
        return f"Inst {index} ({short_addr})"

    def post_to_ui(self, callback, coalesce_key=None):
        if not self._closing:
            self._ui_queue.put(callback, key=coalesce_key)

    def ui_backlog_stats(self):
        info = self._ui_queue.stats()
        info["ui_callback_errors"] = self._ui_error_total
        info["latest_callback_error"] = (
            self._ui_recent_errors[-1] if self._ui_recent_errors else None
        )
        return info

    def show_runtime_diagnostics(self, event=None):
        """Inspect queue pressure and UI errors without writing disk logs."""
        stats = self.ui_backlog_stats()
        tail = "\n".join(list(self._ui_recent_errors)[-5:]) or "없음"
        messagebox.showinfo(
            "AutoClicker UI 진단",
            f"인스턴스: {len(self.tab_frames)}개\n"
            f"UI 대기 작업: {stats['pending']}개\n"
            f"최고 대기 작업: {stats['peak_pending']}개\n"
            f"중복 이벤트 통합: {stats['coalesced_replacements']}건\n"
            f"UI 콜백 오류: {stats['ui_callback_errors']}건\n\n"
            f"최근 오류:\n{tail}",
            parent=self,
        )

    def show_runtime_warning(self, title, message):
        """Show at most one blocking warning across all emulator instances.

        Other instances still show red warning indicators, but cannot create
        a chain of modal Tk dialogs that stops the entire automation UI.
        """
        if self._closing or self._warning_dialog_open:
            return False
        now = time.monotonic()
        if now - self._last_warning_popup_at < 30.0:
            return False
        self._last_warning_popup_at = now
        self._warning_dialog_open = True
        try:
            messagebox.showwarning(title, message)
        finally:
            self._warning_dialog_open = False
        return True

    def _drain_ui_queue(self):
        if self._closing:
            return
        started = time.perf_counter()
        for _ in range(40):
            if time.perf_counter() - started > 0.008:
                break
            try:
                callback = self._ui_queue.get_nowait()
            except IndexError:
                break
            try:
                callback()
            except Exception as error:
                self._ui_error_total += 1
                self._ui_recent_errors.append(
                    f"{type(error).__name__}: {error}"[:350]
                )
        self._ui_pump_id = self.after(50, self._drain_ui_queue)

    def _pump_timer_updates(self):
        if self._closing:
            return
        try:
            current_tab = self.tabview.get()
        except Exception:
            current_tab = None

        if current_tab in self.tab_frames:
            self.tab_frames[current_tab].ensure_templates_rendered()
            if self.instance_selector.get() != current_tab:
                self.instance_selector.set(current_tab)
        for name, frame in tuple(self.tab_frames.items()):
            try:
                if name == current_tab:
                    frame.update_timer_display()
                else:
                    # Hidden timer labels are not visible. Track alert badges,
                    # but do not render/update ten background widget trees.
                    frame.check_tab_warning_status()
            except Exception:
                pass
        self._timer_pump_id = self.after(500, self._pump_timer_updates)

    def load_and_initialize_tabs(self):
        config = AutoClicker.read_config(CONFIG_PATH)
        saved_addresses = []
        instances = config.get("instances", [])
        if isinstance(instances, list):
            for instance in instances:
                if not isinstance(instance, dict):
                    continue
                address = instance.get("device_address")
                if address and address not in saved_addresses:
                    saved_addresses.append(address)
        if not saved_addresses and config.get("device_address"):
            saved_addresses.append(config["device_address"])
        if not saved_addresses:
            saved_addresses = ["127.0.0.1:5555"]

        first_tab = None
        try:
            for address in saved_addresses:
                frame = self.add_instance_tab(device_address=address)
                if frame is not None and first_tab is None:
                    first_tab = frame.tab_name
        finally:
            self._initializing_tabs = False

        if first_tab:
            self.tabview.set(first_tab)
            self.instance_selector.set(first_tab)
            self.instance_tabs.set_selected(first_tab)
            self._set_active_log_frame(first_tab)
            self.tab_frames[first_tab].ensure_templates_rendered()

        if config.get("reset_counts_on_startup", False):
            self.reset_all_template_counts(is_fallback=False)
            self.reset_all_template_counts(is_fallback=True)

        self.save_app_config()

    def add_new_instance_dialog(self):
        AddInstanceWindow(self)

    def open_global_settings(self):
        try:
            current_tab = self.tabview.get()
            tab_frame = self.tab_frames.get(current_tab)
        except Exception:
            tab_frame = None
        if tab_frame is None and self.tab_frames:
            tab_frame = next(iter(self.tab_frames.values()))
        if tab_frame is not None:
            tab_frame.open_settings_window()

    def add_instance_tab(self, device_address="127.0.0.1:5555"):
        device_address = str(device_address).strip()
        if not device_address:
            return None
        for frame in self.tab_frames.values():
            if frame.clicker.device_address == device_address:
                self._select_instance(frame.tab_name)
                return None

        self.tab_counter += 1
        tab_name = self.format_tab_name(self.tab_counter, device_address)
        suffix = 1
        base_name = tab_name
        while tab_name in self.tab_frames:
            suffix += 1
            tab_name = f"{base_name}_{suffix}"

        tab_obj = self.tabview.add(tab_name)
        frame = InstanceTabFrame(
            tab_obj,
            app_owner=self,
            tab_name=tab_name,
            device_address=device_address,
        )
        frame.pack(fill="both", expand=True)
        self.tab_frames[tab_name] = frame
        self.instance_selector.configure(values=list(self.tab_frames))
        self.instance_tabs.set_tabs(list(self.tab_frames), selected=self.tabview.get())
        if not self._initializing_tabs:
            self.tabview.set(tab_name)
            self.instance_selector.set(tab_name)
            self.instance_tabs.set_selected(tab_name)
            self._set_active_log_frame(tab_name)
            self.after_idle(frame.ensure_templates_rendered)
            self.save_app_config()
        return frame

    def remove_instance_tab(self, tab_name):
        if len(self.tab_frames) <= 1:
            from tkinter import messagebox
            messagebox.showwarning("삭제 불가", "최소 1개의 인스턴스 탭이 존재해야 합니다.")
            return

        frame = self.tab_frames.pop(tab_name, None)
        if frame is None:
            return
        frame.shutdown()
        self.update_instance_warning(tab_name, False)
        self.tabview.delete(tab_name)
        self.instance_selector.configure(values=list(self.tab_frames))
        current = self.tabview.get()
        self.instance_selector.set(current)
        self.instance_tabs.set_tabs(list(self.tab_frames), selected=current)
        self._set_active_log_frame(current)
        if current in self.tab_frames:
            self.tab_frames[current].ensure_templates_rendered()
        self.save_app_config()

    def refresh_all_tabs_templates(self):
        active = self.tabview.get()
        for frame in tuple(self.tab_frames.values()):
            if frame.tab_name == active:
                frame.refresh_templates()
            else:
                frame._templates_rendered = False

    def update_all_template_actions(self, filename, action, is_fallback=False):
        action_text, action_fg, action_hover = get_action_button_style(action)
        for frame in tuple(self.tab_frames.values()):
            if is_fallback:
                frame.clicker.fallback_template_actions[filename] = action
                row_dict = frame.fallback_template_row_widgets
            else:
                frame.clicker.template_actions[filename] = action
                row_dict = frame.template_row_widgets
            if filename in row_dict:
                row_dict[filename].action_btn.configure(
                    text=action_text, fg_color=action_fg, hover_color=action_hover
                )

    def update_all_template_delays(self, filename, delay, delay_type, is_fallback=False):
        delay_text, delay_fg, delay_hover = get_delay_button_style(delay, delay_type)
        for frame in tuple(self.tab_frames.values()):
            if is_fallback:
                frame.clicker.fallback_template_delays[filename] = delay
                frame.clicker.fallback_template_delay_types[filename] = delay_type
                row_dict = frame.fallback_template_row_widgets
            else:
                frame.clicker.template_delays[filename] = delay
                frame.clicker.template_delay_types[filename] = delay_type
                row_dict = frame.template_row_widgets
            if filename in row_dict:
                row_dict[filename].delay_btn.configure(
                    text=delay_text, fg_color=delay_fg, hover_color=delay_hover
                )

    def update_all_template_order(self, order, is_fallback=False):
        active = self.tabview.get()
        for frame in tuple(self.tab_frames.values()):
            if is_fallback:
                frame.clicker.fallback_template_order = list(order)
                row_dict = frame.fallback_template_row_widgets
            else:
                frame.clicker.template_order = list(order)
                row_dict = frame.template_row_widgets
            if frame.tab_name != active:
                # Preserve the global order in memory, but postpone 10+
                # hidden pages' widget re-creation until selection.
                frame._templates_rendered = False
                continue
            for w in row_dict.values():
                w.frame.pack_forget()
            for idx, filename in enumerate(order):
                if filename in row_dict:
                    w = row_dict[filename]
                    w.frame.pack(fill="x", padx=5, pady=1)
                    w.priority.configure(text=f"{idx+1}.")
            frame.filter_templates(is_fallback=is_fallback)

    def remove_template_from_all_tabs(self, filename, is_fallback=False):
        # A deleted template must not retain its old display count if another
        # file is later created with the same name.
        self._ui_latest_match_counts.pop((filename, bool(is_fallback)), None)
        for frame in tuple(self.tab_frames.values()):
            if is_fallback:
                order = frame.clicker.fallback_template_order
                if filename in order:
                    order.remove(filename)
                frame.clicker.fallback_template_counts.pop(filename, None)
                frame.clicker.fallback_template_actions.pop(filename, None)
                frame.clicker.fallback_template_offsets.pop(filename, None)
                frame.clicker.fallback_template_delays.pop(filename, None)
                frame.clicker.fallback_template_delay_types.pop(filename, None)
                frame.clicker.fallback_template_rois.pop(filename, None)
                row_dict = frame.fallback_template_row_widgets
                count_dict = frame.fallback_template_count_labels
            else:
                order = frame.clicker.template_order
                if filename in order:
                    order.remove(filename)
                frame.clicker.template_counts.pop(filename, None)
                frame.clicker.template_actions.pop(filename, None)
                frame.clicker.template_offsets.pop(filename, None)
                frame.clicker.template_delays.pop(filename, None)
                frame.clicker.template_delay_types.pop(filename, None)
                frame.clicker.template_rois.pop(filename, None)
                row_dict = frame.template_row_widgets
                count_dict = frame.template_count_labels
            if filename in row_dict:
                w = row_dict.pop(filename)
                w.frame.destroy()
            if filename in count_dict:
                count_dict.pop(filename, None)
            for idx, fn in enumerate(order):
                if fn in row_dict:
                    row_dict[fn].priority.configure(text=f"{idx+1}.")
            frame.filter_templates(is_fallback=is_fallback)

    def add_template_to_all_tabs(self, filename, offset_x=0, offset_y=0, is_fallback=False):
        existed = any(
            filename in (
                frame.clicker.fallback_template_order if is_fallback
                else frame.clicker.template_order
            )
            for frame in self.tab_frames.values()
        )
        if not existed:
            self._ui_latest_match_counts.pop((filename, bool(is_fallback)), None)
        for frame in tuple(self.tab_frames.values()):
            if is_fallback:
                order = frame.clicker.fallback_template_order
                parent = frame.fallback_templates_frame
                frame.clicker.fallback_template_offsets[filename] = [offset_x, offset_y]
                frame.clicker.fallback_template_counts.setdefault(filename, 0)
                frame.clicker.fallback_template_actions.setdefault(filename, "click")
                frame.clicker.fallback_template_delays.setdefault(filename, 0.0)
                frame.clicker.fallback_template_delay_types.setdefault(filename, "pre")
            else:
                order = frame.clicker.template_order
                parent = frame.templates_frame
                frame.clicker.template_offsets[filename] = [offset_x, offset_y]
                frame.clicker.template_counts.setdefault(filename, 0)
                frame.clicker.template_actions.setdefault(filename, "click")
                frame.clicker.template_delays.setdefault(filename, 0.0)
                frame.clicker.template_delay_types.setdefault(filename, "pre")
            if filename not in order:
                order.append(filename)
            idx = order.index(filename)
            row_dict = frame.fallback_template_row_widgets if is_fallback else frame.template_row_widgets
            if getattr(frame, "_templates_rendered", False):
                frame.filter_templates(is_fallback=is_fallback)

    def reset_all_template_counts(self, is_fallback=False):
        """Reset shared persisted counts once, then sync every instance UI.

        All instances use the same config path. Repeating the reset on every
        clicker creates redundant writes and can race with pending count saves.
        """
        if not self.tab_frames:
            return
        frames = tuple(self.tab_frames.values())
        source = frames[0].clicker
        if is_fallback:
            source.reset_fallback_counts()
        else:
            source.reset_counts()

        # An older UI match callback must never resurrect pre-reset counters.
        for key in tuple(self._ui_latest_match_counts):
            if bool(key[1]) == bool(is_fallback):
                del self._ui_latest_match_counts[key]

        for frame in frames:
            # Drop pre-reset match notifications that are still waiting for
            # the UI event pump. They must not restore stale counter values.
            match_lock = getattr(frame, "_match_ui_lock", None)
            pending_matches = getattr(frame, "_pending_match_counts", None)
            if match_lock is not None and pending_matches is not None:
                with match_lock:
                    for pending_key in tuple(pending_matches):
                        if bool(pending_key[1]) == bool(is_fallback):
                            pending_matches.pop(pending_key, None)
            counts = (
                frame.clicker.fallback_template_counts if is_fallback
                else frame.clicker.template_counts
            )
            if frame.clicker is not source:
                for filename in tuple(counts):
                    counts[filename] = 0
            labels = (
                frame.fallback_template_count_labels if is_fallback
                else frame.template_count_labels
            )
            for label in labels.values():
                if label is not None and label.winfo_exists():
                    label.configure(text="0회")

    def update_template_count_for_all(self, filename, count, is_fallback):
        # Keep compact latest state; never redraw ten hidden instances on each
        # rapid match event. Switching tabs resynchronizes visible counters.
        key = (filename, bool(is_fallback))
        self._ui_latest_match_counts[key] = count
        frame = self.get_current_tab_frame()
        if frame is None or frame._destroyed:
            return
        labels = (
            frame.fallback_template_count_labels
            if is_fallback else frame.template_count_labels
        )
        label = labels.get(filename)
        if label is not None and label.winfo_exists():
            label.configure(text=f"{count}회")

    def _sync_visible_template_counts(self, frame):
        for is_fallback, labels in (
            (False, frame.template_count_labels),
            (True, frame.fallback_template_count_labels),
        ):
            counts = (
                frame.clicker.fallback_template_counts
                if is_fallback else frame.clicker.template_counts
            )
            for filename, label in tuple(labels.items()):
                if label is not None and label.winfo_exists():
                    current = self._ui_latest_match_counts.get(
                        (filename, is_fallback), counts.get(filename, 0)
                    )
                    text = f"{current}회"
                    if label.cget("text") != text:
                        label.configure(text=text)

    def start_all_clickers(self):
        self._start_all_generation += 1
        generation = self._start_all_generation
        def start_frame(frame):
            if (
                generation == self._start_all_generation
                and not frame._destroyed
                and frame.clicker.device
                and not frame.clicker.is_running
            ):
                frame.start_clicker_loop()

        scheduled = 0
        for frame in self.tab_frames.values():
            if frame.clicker.device and not frame.clicker.is_running:
                self.after(scheduled * 150, lambda target=frame: start_frame(target))
                scheduled += 1

    def stop_all_clickers(self):
        self._start_all_generation += 1
        for frame in self.tab_frames.values():
            # Pending staggered starts were invalidated before iteration.
            if frame.clicker.is_running or frame._loop_starting:
                frame.stop_clicker_loop()

    def connect_all_instances(self):
        for frame in self.tab_frames.values():
            if frame.clicker.device is None:
                frame.toggle_connection()

    def disconnect_all_instances(self):
        """Disconnect every instance without waiting on ADB from Tk's thread.

        Stop/cancel automation first and invalidate any in-flight connection
        callbacks. Actual ADB disconnects can block; process them in a worker
        while Tk remains responsive. Keep all saved addresses and templates.
        """
        if self._closing or self._disconnect_all_busy:
            return
        self._disconnect_all_busy = True
        self.disconnect_all_btn.configure(state="disabled", text="연결 해제 중…")
        self.connect_all_btn.configure(state="disabled")
        self.start_all_btn.configure(state="disabled")
        self._start_all_generation += 1
        frames = tuple(self.tab_frames.values())
        for frame in frames:
            frame._connection_generation += 1
            frame.connect_button.configure(state="disabled", text="연결 해제 중…")
            if frame.clicker.is_running or frame._loop_starting:
                frame.stop_clicker_loop()

        def worker():
            try:
                for frame in frames:
                    if self._closing or frame._destroyed:
                        continue
                    try:
                        frame.clicker.disconnect()
                        error = None
                    except Exception as exc:
                        error = f"{type(exc).__name__}: {exc}"
                    def apply(target=frame, failure=error):
                        if self._closing or target._destroyed:
                            return
                        target._set_disconnected_ui()
                        target.clear_warning_ui()
                        if failure:
                            target.log_message(f"연결 해제 오류: {failure}")
                    self.post_to_ui(apply)
            finally:
                def finished():
                    if self._closing:
                        return
                    self._disconnect_all_busy = False
                    self.disconnect_all_btn.configure(
                        state="normal", text="전체 연결 끊기"
                    )
                    self.connect_all_btn.configure(state="normal")
                    self.start_all_btn.configure(state="normal")
                self.post_to_ui(finished)

        threading.Thread(target=worker, daemon=True).start()

    def refresh_all_devices(self):
        def task():
            dummy_clicker = AutoClicker()
            try:
                devices = discover_devices(dummy_clicker)
            except Exception:
                devices = []
            finally:
                dummy_clicker.shutdown()

            def update_ui():
                if self._closing:
                    return
                for frame in tuple(self.tab_frames.values()):
                    current_list = list(devices)
                    address = frame.clicker.device_address
                    if address and address not in current_list:
                        current_list.append(address)
                    frame.update_device_combo_values(current_list)

            self.post_to_ui(update_ui)

        threading.Thread(target=task, daemon=True).start()

    def sync_shared_settings_to_all(self, source_frame=None):
        """Synchronize shared settings across all tab frames and their clicker instances."""
        if not self.tab_frames:
            return
        if source_frame is None:
            source_frame = next(iter(self.tab_frames.values()))
        master_settings = source_frame.clicker._settings_dict()

        for frame in tuple(self.tab_frames.values()):
            if frame is not source_frame:
                frame.clicker._apply_settings(master_settings)
                if hasattr(frame, "fb_final_combo") and frame.fb_final_combo.winfo_exists():
                    curr_fb_action = getattr(frame.clicker, "fallback_final_action", "none")
                    curr_fb_label = NO_MATCH_ACTION_MAP.get(curr_fb_action, "사용 안 함 (Disabled)")
                    frame.fb_final_combo.set(curr_fb_label)
                    coords = getattr(frame.clicker, "fallback_final_coords", [500, 500])
                    frame.fb_final_x_entry.delete(0, "end")
                    frame.fb_final_x_entry.insert(0, str(coords[0]))
                    frame.fb_final_y_entry.delete(0, "end")
                    frame.fb_final_y_entry.insert(0, str(coords[1]))
                    frame.update_fb_final_coord_visibility(curr_fb_action)

    def save_app_config(self):
        instances_data = [
            {"device_address": frame.clicker.device_address}
            for frame in self.tab_frames.values()
        ]
        primary_settings = None
        if self.tab_frames:
            primary_settings = next(iter(self.tab_frames.values())).clicker._settings_dict()
        return AutoClicker.update_instances_config(
            instances_data,
            CONFIG_PATH,
            primary_settings=primary_settings,
        )

    def on_closing(self):
        if self._closing:
            return
        self._closing = True
        TemplatePreviewTooltip.get_instance().hide()
        self._start_all_generation += 1
        frames = tuple(self.tab_frames.values())
        for frame in frames:
            frame.begin_shutdown()
        for frame in frames:
            frame.shutdown()
        self.save_app_config()
        try:
            self.after_cancel(self._ui_pump_id)
        except Exception:
            pass
        try:
            self.after_cancel(self._timer_pump_id)
        except Exception:
            pass
        self.destroy()

    def destroy(self):
        """Cancel queued Tk jobs before tearing down the widget tree.

        CustomTkinter scrollbars and root timers register Tcl callbacks. If
        destroyed widgets leave them queued, the next Tk event pump reports
        invalid-command errors and may keep references to stale UI objects.
        """
        self._closing = True
        try:
            for after_id in self.tk.call("after", "info"):
                self.tk.call("after", "cancel", after_id)
        except tk.TclError:
            pass
        self._ui_queue.clear()
        super().destroy()


# Backward compatibility aliases
AutoClickerApp = App
TeraboxClickerApp = App


if __name__ == "__main__":
    app = App()
    app.mainloop()

