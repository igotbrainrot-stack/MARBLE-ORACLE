"""Bundled Uberata Clear v3 font loader for the Marble desktop apps."""
from __future__ import annotations
import ctypes
import ctypes.util
import sys
from pathlib import Path

FAMILY = "Uberata Clear"
_FILE = Path(__file__).resolve().parent / "fonts" / "Uberata-Clear.ttf"
_registered = False

def register():
    """Load the bundled font privately; no system-wide installation required."""
    global _registered
    if _registered:
        return True
    if not _FILE.is_file():
        raise FileNotFoundError(f"Bundled Uberata font missing: {_FILE}")
    if sys.platform == "win32":
        try:
            _registered = bool(ctypes.windll.gdi32.AddFontResourceExW(str(_FILE), 0x10, None))
        except (AttributeError, OSError):
            _registered = False
    elif sys.platform.startswith("linux"):
        try:
            lib = ctypes.CDLL(ctypes.util.find_library("fontconfig") or "libfontconfig.so.1")
            lib.FcConfigGetCurrent.restype = ctypes.c_void_p
            lib.FcConfigAppFontAddFile.argtypes = (ctypes.c_void_p, ctypes.c_char_p)
            lib.FcConfigAppFontAddFile.restype = ctypes.c_int
            _registered = bool(lib.FcConfigAppFontAddFile(lib.FcConfigGetCurrent(), str(_FILE).encode()))
        except (AttributeError, OSError):
            _registered = False
    else:
        # macOS Tk generally requires installing the font in Font Book.
        _registered = False
    return _registered

def apply_tk_fonts(root):
    """Make Tk text, native dialogs, menu items and named fonts Uberata."""
    import tkinter.font as tkfont
    register()
    for name in ("TkDefaultFont","TkTextFont","TkFixedFont","TkMenuFont","TkHeadingFont",
                 "TkCaptionFont","TkSmallCaptionFont","TkIconFont","TkTooltipFont"):
        try:
            tkfont.nametofont(name, root=root).configure(family=FAMILY)
        except Exception:
            pass
    root.option_add("*Font", (FAMILY, 11))
