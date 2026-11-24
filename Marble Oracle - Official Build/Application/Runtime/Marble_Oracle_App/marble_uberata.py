"""Bundled Uberata Clear v3 font loader for the Marble desktop apps."""
from __future__ import annotations
import ctypes
import ctypes.util
import sys
from pathlib import Path

FAMILY = "Uberata Clear"
# HOME's ASCII statue and other art keep this face in every appearance (oracle_appearance may change FAMILY).
ART_FAMILY = FAMILY
_FILE = Path(__file__).resolve().parent / "fonts" / "Uberata-Clear.ttf"
_registered = False

def _register_file(path):
    """Load one font file privately for this process (no system-wide installation). True when it worked."""
    if sys.platform == "win32":
        try:
            return bool(ctypes.windll.gdi32.AddFontResourceExW(str(path), 0x10, None))
        except (AttributeError, OSError):
            return False
    if sys.platform.startswith("linux"):
        try:
            lib = ctypes.CDLL(ctypes.util.find_library("fontconfig") or "libfontconfig.so.1")
            lib.FcConfigGetCurrent.restype = ctypes.c_void_p
            lib.FcConfigAppFontAddFile.argtypes = (ctypes.c_void_p, ctypes.c_char_p)
            lib.FcConfigAppFontAddFile.restype = ctypes.c_int
            return bool(lib.FcConfigAppFontAddFile(lib.FcConfigGetCurrent(), str(path).encode()))
        except (AttributeError, OSError):
            return False
    # macOS Tk generally requires installing the font in Font Book.
    return False


def register():
    """Load the bundled font privately; no system-wide installation required."""
    global _registered
    if _registered:
        return True
    if not _FILE.is_file():
        raise FileNotFoundError(f"Bundled Uberata font missing: {_FILE}")
    _registered = _register_file(_FILE)
    return _registered


# 0.5.3: Inter, the interface face of the Dark and Light appearances (SIL Open Font License; fonts/Inter-OFL.txt).
INTER_FAMILY = "Inter"
INTER_FILES = tuple(Path(__file__).resolve().parent / "fonts" / f"Inter-{style}.otf"
                    for style in ("Regular", "Bold", "Italic", "BoldItalic"))
_inter = None


def register_inter():
    """Load the bundled Inter files privately. True when all of them loaded (or were already loaded)."""
    global _inter
    if _inter is None:
        _inter = all(path.is_file() and _register_file(path) for path in INTER_FILES)
    return _inter


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
