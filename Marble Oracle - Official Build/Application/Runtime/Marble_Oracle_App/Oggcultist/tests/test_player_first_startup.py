"""Music-player-first navigation and console-free Windows launcher regression."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import launch

ROOT = Path(__file__).resolve().parents[1]


def test_console_free_windows_entry_has_recovery_path():
    primary = (ROOT / 'Oggcultist.pyw').read_text(encoding='utf-8').lower()
    batch = (ROOT.parent / 'WINDOWS LAUNCHER.bat').read_text(encoding='utf-8').lower()
    assert 'windows_launcher' in primary
    # v1.7: run_windows.bat is itself the console recovery launcher (formerly run_windows_debug.bat).
    assert 'launch.py' in batch and ':app_error' in batch and 'pause' in batch
    assert not (ROOT / 'Oggcultist.vbs').exists()
    assert not (ROOT / 'run_windows_silent.bat').exists()


def test_windowless_ffmpeg_uses_dialog_instead_of_hidden_input(monkeypatch):
    import tkinter as tk
    from tkinter import messagebox
    events = []
    class FakeTk:
        def withdraw(self): events.append('hide')
        def destroy(self): events.append('destroy')
    monkeypatch.setattr(tk, 'Tk', FakeTk)
    monkeypatch.setattr(messagebox, 'askyesno', lambda *a, **k: (events.append('prompt') or True))
    monkeypatch.setattr(messagebox, 'showerror', lambda *a, **k: events.append('error'))
    def setup(**kwargs):
        assert kwargs['input_fn']('question') == 'y'
        kwargs['on_installed']()
        return True
    success = []
    assert launch._windowless_ffmpeg_setup(SimpleNamespace(ensure_ffmpeg=setup), lambda: success.append(True))
    assert events == ['hide', 'prompt', 'destroy']
    assert success == [True]


def test_windowless_ffmpeg_setup_failure_reports_dialog(monkeypatch):
    import tkinter as tk
    from tkinter import messagebox
    errors = []
    class FakeTk:
        def withdraw(self): pass
        def destroy(self): pass
    monkeypatch.setattr(tk, 'Tk', FakeTk)
    monkeypatch.setattr(messagebox, 'showerror', lambda *a, **k: errors.append((a, k)))
    assert not launch._windowless_ffmpeg_setup(
        SimpleNamespace(ensure_ffmpeg=lambda **kwargs: kwargs['print_fn']('Download failed') or False),
        lambda: None)
    assert 'Download failed' in errors[0][0][1]


# v1.7 replaced the hidden converter window + separate player window with one
# window (sidebar navigation). The intent of the two former tests is kept:
# the player is the home screen, the converter is optional and one click away,
# and closing never abandons a running conversion.
@pytest.mark.skipif(sys.platform != 'win32' and not os.environ.get('DISPLAY'),
                    reason='Requires an X display or a Windows desktop')
def test_player_is_first_and_converter_is_optional(tmp_path, monkeypatch):
    import tkinter as tk
    monkeypatch.setenv('OGGCULTIST_DATA_DIR', str(tmp_path / 'data'))
    from oggcultist.app import OggcultistApp
    app = OggcultistApp()
    try:
        app.update()
        assert app.current_page == 'library'
        assert app.state() == 'normal' and app.pages['library'].winfo_viewable()
        app.show_converter()
        app.update()
        assert app.current_page == 'converter' and app.pages['converter'].winfo_viewable()
        app.show_player()
        app.update()
        assert app.current_page == 'library'
        app._on_close()
        with pytest.raises(tk.TclError):
            app.winfo_exists()
    finally:
        try: app.destroy()
        except tk.TclError: pass


@pytest.mark.skipif(sys.platform != 'win32' and not os.environ.get('DISPLAY'),
                    reason='Requires an X display or a Windows desktop')
def test_closing_is_refused_while_a_conversion_runs(tmp_path, monkeypatch):
    import tkinter as tk
    from tkinter import messagebox
    monkeypatch.setenv('OGGCULTIST_DATA_DIR', str(tmp_path / 'data'))
    from oggcultist.app import OggcultistApp
    shown = []
    monkeypatch.setattr(messagebox, 'showinfo', lambda *a, **k: shown.append(a))
    app = OggcultistApp()
    try:
        app.update()
        app.converter.busy = True
        app._on_close()
        app.update()
        assert app.winfo_exists() and shown and app.current_page == 'converter'
        app.converter.busy = False
        app._on_close()
        with pytest.raises(tk.TclError):
            app.winfo_exists()
    finally:
        try: app.destroy()
        except Exception: pass
