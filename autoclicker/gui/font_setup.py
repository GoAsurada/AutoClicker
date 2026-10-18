"""Load Pretendard for the Windows UI without installing a system-wide font.

The packaged release includes regular and bold OTF files from the upstream
Pretendard distribution. Source checkouts also work if the font is installed.
"""

import os
import sys
import tkinter.font as tkfont

import customtkinter as ctk

FONT_FAMILY = "Pretendard"
FALLBACK_FAMILY = "Malgun Gothic"
_private_font_files = []
_theme_size_adjusted = False


def configure_app_fonts(root):
    """Register private fonts, set CustomTkinter and native Tk defaults."""
    candidates = []
    if hasattr(sys, "_MEIPASS"):
        candidates.append(os.path.join(sys._MEIPASS, "assets", "fonts"))
    candidates.append(
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "assets", "fonts"))
    )
    if sys.platform == "win32":
        try:
            import ctypes
            gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
            add_font = gdi32.AddFontResourceExW
            add_font.argtypes = (ctypes.c_wchar_p, ctypes.c_uint, ctypes.c_void_p)
            add_font.restype = ctypes.c_int
            for directory in candidates:
                for filename in ("Pretendard-Regular.otf", "Pretendard-Bold.otf"):
                    path = os.path.join(directory, filename)
                    if os.path.isfile(path) and path not in _private_font_files:
                        if add_font(path, 0x10, None):  # FR_PRIVATE
                            _private_font_files.append(path)
        except (OSError, AttributeError):
            pass

    try:
        installed = set(tkfont.families(root))
    except Exception:
        installed = set()
    family = FONT_FAMILY if FONT_FAMILY in installed or _private_font_files else FALLBACK_FAMILY
    global _theme_size_adjusted
    font_theme = ctk.ThemeManager.theme.setdefault("CTkFont", {})
    font_theme["family"] = family
    # A single process-wide +1pt adjustment; constructing multiple App
    # windows must not repeatedly inflate the default font.
    if not _theme_size_adjusted:
        font_theme["size"] = int(font_theme.get("size", 13)) + 1
        _theme_size_adjusted = True
    for font_name in (
        "TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont",
        "TkCaptionFont", "TkSmallCaptionFont",
    ):
        try:
            named = tkfont.nametofont(font_name, root=root)
            existing_size = int(named.cget("size"))
            named.configure(
                family=family,
                size=existing_size + 1 if existing_size >= 0 else existing_size - 1,
            )
        except Exception:
            pass
    return family
