"""Dark window frame (title bar and border) on Windows, to match the dark app.

- Windows 10 (20H1+) and 11: ``DWMWA_USE_IMMERSIVE_DARK_MODE`` gives a dark title bar
  and border (attribute 20; 19 on early Windows 10 builds).
- Windows 11: the caption, its text and the border are also given Oggcultist's own
  colours (``DWMWA_CAPTION_COLOR`` / ``TEXT_COLOR`` / ``BORDER_COLOR``).

Older Windows simply ignores the requests. Elsewhere the window manager draws the frame,
so nothing is done. Never raises.
"""
from __future__ import annotations

import sys

DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_USE_IMMERSIVE_DARK_MODE_OLD = 19
DWMWA_BORDER_COLOR = 34
DWMWA_CAPTION_COLOR = 35
DWMWA_TEXT_COLOR = 36
SWP_FRAME_REFRESH = 0x0001 | 0x0002 | 0x0004 | 0x0010 | 0x0020   # NOSIZE|NOMOVE|NOZORDER|NOACTIVATE|FRAMECHANGED


def colorref(hex_colour: str) -> int:
    """'#RRGGBB' → Windows COLORREF (0x00BBGGRR)."""
    value = hex_colour.lstrip('#')
    r, g, b = int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)
    return r | (g << 8) | (b << 16)


def dark_frame(window, caption: str = '#130F0D', text: str = '#F2E8DE', border: str = '#2A211C',
               *, platform: str | None = None, dwmapi=None, user32=None) -> bool:
    """Ask Windows for a dark frame around ``window``; True if dark mode was accepted."""
    if (platform or sys.platform) != 'win32':
        return False
    try:
        import ctypes
        if dwmapi is None or user32 is None:
            dwmapi = ctypes.WinDLL('dwmapi')
            user32 = ctypes.WinDLL('user32')
        window.update_idletasks()
        hwnd = user32.GetParent(window.winfo_id()) or window.winfo_id()   # Tk's outer frame window

        def set_attribute(attribute: int, value: int) -> bool:
            data = ctypes.c_int(value)
            return dwmapi.DwmSetWindowAttribute(hwnd, attribute, ctypes.byref(data), ctypes.sizeof(data)) == 0

        dark = set_attribute(DWMWA_USE_IMMERSIVE_DARK_MODE, 1) or set_attribute(DWMWA_USE_IMMERSIVE_DARK_MODE_OLD, 1)
        set_attribute(DWMWA_CAPTION_COLOR, colorref(caption))      # Windows 11 only; ignored before
        set_attribute(DWMWA_TEXT_COLOR, colorref(text))
        set_attribute(DWMWA_BORDER_COLOR, colorref(border))
        user32.SetWindowPos(hwnd, None, 0, 0, 0, 0, SWP_FRAME_REFRESH)   # redraw the frame now
        return bool(dark)
    except Exception:  # noqa: BLE001 - purely cosmetic
        return False


def follow_new_windows(root, **colours) -> None:
    """Give the main window and every dialog that opens later the dark frame."""
    done: set[int] = set()

    def apply(widget) -> None:
        try:
            key = int(widget.winfo_id())
        except Exception:  # noqa: BLE001
            return
        if key not in done:
            done.add(key)
            dark_frame(widget, **colours)

    root.bind('<Map>', lambda event: apply(event.widget) if event.widget is root else None, add='+')
    root.bind_class('Toplevel', '<Map>', lambda event: apply(event.widget), add='+')
    if root.winfo_ismapped():
        apply(root)
