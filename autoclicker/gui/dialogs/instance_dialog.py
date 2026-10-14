import os
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
import cv2
import numpy as np

from autoclicker.core.constants import (
    DEFAULT_ADB_MODE,
    DEFAULT_CUSTOM_ADB_PATH,
    VALID_ADB_MODES,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_DOUBLE_CLICK_INTERVAL,
    DEFAULT_POST_ACTION_DELAY,
    DEFAULT_SIMILARITY_THRESHOLD,
    DEFAULT_NO_MATCH_TIMEOUT,
    DEFAULT_CONSECUTIVE_MATCH_THRESHOLD,
    DEFAULT_RESET_COUNTS_ON_STARTUP,
)
from autoclicker.core.environment import get_default_adb_path, resolve_adb_path
from autoclicker.core.clicker import AutoClicker
from autoclicker.gui.device_discovery import discover_devices
from autoclicker.gui.theme import (
    COLOR_PRIMARY,
    COLOR_PRIMARY_HOVER,
    COLOR_SUCCESS,
    COLOR_SUCCESS_HOVER,
    COLOR_DANGER,
    COLOR_DANGER_HOVER,
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

class AddInstanceWindow(ctk.CTkToplevel):
    def __init__(self, parent_app):
        super().__init__(parent_app)
        self.parent_app = parent_app
        self.title("인스턴스 탭 추가 / 선택")
        self.geometry("460x480")
        self.resizable(False, False)

        self.transient(parent_app)
        self.grab_set()

        self.header_label = ctk.CTkLabel(self, text="➕ 새 인스턴스 탭 추가", font=ctk.CTkFont(size=16, weight="bold"))
        self.header_label.pack(pady=(15, 10))

        # 검색된 디바이스 영역
        self.dev_frame = ctk.CTkFrame(self)
        self.dev_frame.pack(fill="both", expand=True, padx=20, pady=5)

        self.dev_title = ctk.CTkLabel(self.dev_frame, text="📱 검색된 ADB 디바이스 목록 (선택):", font=ctk.CTkFont(weight="bold"))
        self.dev_title.pack(anchor="w", padx=15, pady=(10, 5))

        self.scroll_frame = ctk.CTkScrollableFrame(self.dev_frame, height=200)
        self.scroll_frame.pack(fill="both", expand=True, padx=10, pady=5)

        self.checkbox_vars = {} # dev_addr -> BooleanVar

        self.loading_label = ctk.CTkLabel(self.scroll_frame, text="디바이스 검색 중 (ADB scanning)...", text_color=COLOR_TEXT_MUTED)
        self.loading_label.pack(pady=20)

        # 수동 주소 입력 영역
        self.custom_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.custom_frame.pack(fill="x", padx=20, pady=5)
        
        self.custom_label = ctk.CTkLabel(self.custom_frame, text="직접 입력 (IP:Port):")
        self.custom_label.pack(side="left", padx=(5, 5))

        self.custom_entry = ctk.CTkEntry(self.custom_frame, placeholder_text="예: 127.0.0.1:5565")
        self.custom_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))

        # 하단 버튼 영역
        self.btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.btn_frame.pack(fill="x", padx=20, pady=(10, 15))

        self.add_selected_btn = ctk.CTkButton(
            self.btn_frame,
            text="➕ 선택 항목 탭 추가",
            height=34,
            fg_color=COLOR_PRIMARY,
            hover_color=COLOR_PRIMARY_HOVER,
            corner_radius=RADIUS_MD,
            command=self.add_selected
        )
        self.add_selected_btn.pack(side="left", fill="x", expand=True, padx=(0, 5))

        self.add_and_connect_btn = ctk.CTkButton(
            self.btn_frame,
            text="⚡ 전체 추가 & 자동 연결",
            height=34,
            fg_color=COLOR_SUCCESS,
            hover_color=COLOR_SUCCESS_HOVER,
            corner_radius=RADIUS_MD,
            command=self.add_and_connect_all
        )
        self.add_and_connect_btn.pack(side="right", fill="x", expand=True, padx=(5, 0))

        # A plain refresh reads 'adb devices' only. Broad port probing requires
        # a separate, explicit user click to avoid touching unrelated services.
        self.scan_controls = ctk.CTkFrame(self.dev_frame, fg_color="transparent")
        self.scan_controls.pack(fill="x", padx=10, pady=(0, 5), before=self.scroll_frame)
        self.refresh_btn = ctk.CTkButton(
            self.scan_controls, text="↻ 연결 목록 갱신", width=135,
            command=lambda: self.start_device_scan(scan_ports=False),
        )
        self.refresh_btn.pack(side="left", padx=(0, 6))
        self.port_scan_btn = ctk.CTkButton(
            self.scan_controls, text="🔎 전체 포트 탐색", width=135,
            fg_color=COLOR_NEUTRAL, hover_color=COLOR_NEUTRAL_HOVER,
            command=lambda: self.start_device_scan(scan_ports=True),
        )
        self.port_scan_btn.pack(side="left")
        self._scan_busy = False
        self.start_device_scan()

    def start_device_scan(self, scan_ports=False):
        """Prevent parallel scans and keep all Tk mutations on the UI thread."""
        if self._scan_busy:
            return
        self._scan_busy = True
        self.refresh_btn.configure(state="disabled")
        self.port_scan_btn.configure(state="disabled")
        self.loading_label = ctk.CTkLabel(
            self.scroll_frame,
            text=("ADB 전체 포트 검색 중..." if scan_ports else "연결된 ADB 장치 확인 중..."),
            text_color=COLOR_TEXT_MUTED,
        )
        self.loading_label.pack(pady=8)
        threading.Thread(
            target=self.fetch_devices, args=(scan_ports,), daemon=True
        ).start()

    def fetch_devices(self, scan_ports=False):
        devices, error_message = [], None
        dummy = None
        try:
            dummy = AutoClicker()
            devices = discover_devices(dummy, scan_ports=scan_ports)
        except Exception as error:
            error_message = str(error)
        finally:
            if dummy is not None:
                try:
                    dummy.shutdown()
                except Exception:
                    pass

        def update_ui():
            if not self.winfo_exists():
                return
            self._scan_busy = False
            self.refresh_btn.configure(state="normal")
            self.port_scan_btn.configure(state="normal")
            for child in self.scroll_frame.winfo_children():
                child.destroy()
            self.checkbox_vars.clear()

            if error_message:
                ctk.CTkLabel(
                    self.scroll_frame,
                    text=f"ADB 조회 오류: {error_message}",
                    text_color=COLOR_DANGER,
                    wraplength=370,
                ).pack(pady=12)
                return

            existing_addrs = {
                frame.clicker.device_address
                for frame in self.parent_app.tab_frames.values()
            }
            if not devices:
                ctk.CTkLabel(
                    self.scroll_frame,
                    text="ADB에 연결된 장치가 없습니다.\\n"
                         "기존 장치를 갱신하거나 '전체 포트 탐색'을 선택하세요.",
                    text_color=COLOR_WARNING,
                ).pack(pady=16)
                return

            for dev in devices:
                is_already = dev in existing_addrs
                var = ctk.BooleanVar(value=not is_already)
                self.checkbox_vars[dev] = var
                chk = ctk.CTkCheckBox(
                    self.scroll_frame,
                    text=f"{dev} (이미 추가됨)" if is_already else dev,
                    variable=var,
                )
                if is_already:
                    chk.configure(state="disabled")
                chk.pack(anchor="w", padx=10, pady=5)

        self.parent_app.post_to_ui(update_ui)

    def add_selected(self, auto_connect=False):
        to_add = []
        for dev, var in self.checkbox_vars.items():
            if var.get():
                to_add.append(dev)
        
        custom_val = self.custom_entry.get().strip()
        if custom_val:
            to_add.append(custom_val)
            
        if not to_add:
            from tkinter import messagebox
            messagebox.showinfo("알림", "추가할 디바이스를 하나 이상 선택하거나 주소를 입력하세요.")
            return

        added_frames = []
        for addr in dict.fromkeys(to_add):
            frame = self.parent_app.add_instance_tab(device_address=addr)
            if frame:
                added_frames.append(frame)

        if auto_connect:
            for frame in added_frames:
                frame.toggle_connection()

        self.parent_app.save_app_config()
        self.grab_release()
        self.destroy()

    def add_and_connect_all(self):
        existing_addrs = {
            frame.clicker.device_address
            for frame in self.parent_app.tab_frames.values()
        }
        for dev, var in self.checkbox_vars.items():
            if dev not in existing_addrs:
                var.set(True)
        self.add_selected(auto_connect=True)
