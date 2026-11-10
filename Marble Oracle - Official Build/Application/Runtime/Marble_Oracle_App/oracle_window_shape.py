"""Windows-specific silhouette region for the photographic CRT monitor.

Alpha in a Tk PhotoImage does NOT make a Tk toplevel window transparent.
Tk's -transparentcolor can also be unreliable with animated/layered windows.
SetWindowRgn instead clips the actual Win32 window to the metal CRT outline;
this deliberately retains the complete inner screen and all clickable buttons.
No third-party dependencies or alpha compositing are required.
"""
from __future__ import annotations
import os
import json
from pathlib import Path
from functools import lru_cache

SOURCE_W, SOURCE_H = 1448, 1086
# Source-art coordinates: conservative edge of the METAL (not studio shadows).
BODY_OUTLINE = (
    (37, 11), (1410, 11), (1436, 35), (1436, 979),
    (1420, 1004), (1395, 1036), (55, 1036), (27, 1006),
    (11, 982), (11, 35),
)


@lru_cache(maxsize=1)
def _alpha_rows():
    """Precomputed alpha edges of the ACTUAL approved master photograph.

    The profile is generated offline from alpha>=180; no Pillow is needed to
    shape the window when running Marble_Oracle on Windows.
    """
    path = (Path(__file__).resolve().parent / 'data' / 'crt_v2' / 'shape_rows.json') if os.environ.get('MARBLE_ORACLE_CRT_V2') == '1' else (Path(__file__).resolve().parent / 'data' / 'bezel_shape_rows.json')
    try:
        obj = json.loads(path.read_text(encoding='utf-8'))
        if tuple(obj['source_size']) != (SOURCE_W, SOURCE_H):
            raise ValueError('incorrect source shape dimensions')
        return obj['rows']
    except (OSError, ValueError, KeyError):
        return None


def region_points(canvas_width, canvas_height, x=0, y=0):
    """Polygon from measured source alpha, in client-window coordinates."""
    if canvas_width < 100 or canvas_height < 100:
        raise ValueError('invalid CRT frame dimensions')
    sx = float(canvas_width) / SOURCE_W
    sy = float(canvas_height) / SOURCE_H
    if abs(sx - sy) > 0.002:
        raise ValueError('CRT region must use a uniformly scaled photograph')
    rows = _alpha_rows()
    if not rows:
        return [(round(x + px*sx), round(y + py*sy)) for px,py in BODY_OUTLINE]
    edge = [(yy, pair) for yy,pair in enumerate(rows) if pair is not None]
    left = [(round(x + lo*sx), round(y + yy*sy)) for yy,(lo,hi) in edge]
    right = [(round(x + hi*sx + 1), round(y + yy*sy)) for yy,(lo,hi) in reversed(edge)]
    # A simple single, full CRT region (NOT a transparent hole in the middle).
    return left + right


def apply_region(root, canvas, enabled=True):
    """Clip the true Windows toplevel; false on non-Windows or failure.

    The root may fill the monitor in fullscreen while canvas is centred.
    Calling this again on resize returns the previous HRGN to Windows, which
    automatically owns/destroys it after a successful SetWindowRgn.
    """
    if os.name != 'nt':
        return False
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.WinDLL('user32', use_last_error=True)
    GetParent = user32.GetParent
    GetParent.argtypes = (wintypes.HWND,)
    GetParent.restype = wintypes.HWND
    SetWindowRgn = user32.SetWindowRgn
    SetWindowRgn.argtypes = (wintypes.HWND, wintypes.HRGN, wintypes.BOOL)
    SetWindowRgn.restype = ctypes.c_int
    hwnd = int(GetParent(root.winfo_id()) or root.winfo_id())
    if not enabled:
        return bool(SetWindowRgn(hwnd, None, True))
    points = region_points(canvas.winfo_width(), canvas.winfo_height(),
                           canvas.winfo_rootx()-root.winfo_rootx(),
                           canvas.winfo_rooty()-root.winfo_rooty())
    class POINT(ctypes.Structure):
        _fields_ = (('x', wintypes.LONG), ('y', wintypes.LONG))
    arr = (POINT * len(points))(*(POINT(x,y) for x,y in points))
    gdi = ctypes.WinDLL('gdi32', use_last_error=True)
    CreatePolygonRgn = gdi.CreatePolygonRgn
    CreatePolygonRgn.argtypes = (ctypes.POINTER(POINT), ctypes.c_int, ctypes.c_int)
    CreatePolygonRgn.restype = wintypes.HRGN
    rgn = CreatePolygonRgn(arr, len(points), 2)  # WINDING fill
    if not rgn:
        return False
    if not SetWindowRgn(hwnd, rgn, True):
        gdi.DeleteObject.argtypes = (wintypes.HANDLE,)
        gdi.DeleteObject(rgn)
        return False
    return True
