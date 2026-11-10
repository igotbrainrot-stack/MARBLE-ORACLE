"""v1.8.3: dark Windows title bar / border (DWM attributes), checked with fake Windows APIs."""
from __future__ import annotations

import ctypes

from oggcultist.gui.window_frame import (DWMWA_BORDER_COLOR, DWMWA_CAPTION_COLOR, DWMWA_TEXT_COLOR,
                                         DWMWA_USE_IMMERSIVE_DARK_MODE, DWMWA_USE_IMMERSIVE_DARK_MODE_OLD,
                                         colorref, dark_frame)


class FakeWindow:
    def update_idletasks(self): pass
    def winfo_id(self): return 1234


class FakeUser32:
    def __init__(self): self.positions = []
    def GetParent(self, hwnd): return 5678
    def SetWindowPos(self, *args): self.positions.append(args); return 1


class FakeDwm:
    def __init__(self, refuse=()):
        self.refuse, self.calls = set(refuse), {}

    def DwmSetWindowAttribute(self, hwnd, attribute, pointer, size):
        assert hwnd == 5678 and size == ctypes.sizeof(ctypes.c_int)
        self.calls[attribute] = ctypes.cast(pointer, ctypes.POINTER(ctypes.c_int)).contents.value
        return 0x80070057 if attribute in self.refuse else 0       # E_INVALIDARG for unsupported


def test_colorref_is_bgr():
    assert colorref('#130F0D') == 0x0D0F13 and colorref('#FF0000') == 0x0000FF


def test_windows_11_gets_dark_mode_and_app_colours():
    dwm, user32 = FakeDwm(), FakeUser32()
    assert dark_frame(FakeWindow(), '#130F0D', '#F2E8DE', '#2A211C', platform='win32', dwmapi=dwm, user32=user32)
    assert dwm.calls[DWMWA_USE_IMMERSIVE_DARK_MODE] == 1
    assert dwm.calls[DWMWA_CAPTION_COLOR] == 0x0D0F13
    assert dwm.calls[DWMWA_TEXT_COLOR] == colorref('#F2E8DE')
    assert dwm.calls[DWMWA_BORDER_COLOR] == colorref('#2A211C')
    assert user32.positions and user32.positions[0][0] == 5678       # frame redrawn at once


def test_early_windows_10_falls_back_to_the_old_attribute():
    dwm = FakeDwm(refuse={DWMWA_USE_IMMERSIVE_DARK_MODE, DWMWA_CAPTION_COLOR, DWMWA_TEXT_COLOR, DWMWA_BORDER_COLOR})
    assert dark_frame(FakeWindow(), platform='win32', dwmapi=dwm, user32=FakeUser32())
    assert dwm.calls[DWMWA_USE_IMMERSIVE_DARK_MODE_OLD] == 1


def test_other_platforms_and_failures_do_nothing():
    assert dark_frame(FakeWindow(), platform='linux') is False

    class Broken(FakeDwm):
        def DwmSetWindowAttribute(self, *a): raise OSError('no DWM')
    assert dark_frame(FakeWindow(), platform='win32', dwmapi=Broken(), user32=FakeUser32()) is False
