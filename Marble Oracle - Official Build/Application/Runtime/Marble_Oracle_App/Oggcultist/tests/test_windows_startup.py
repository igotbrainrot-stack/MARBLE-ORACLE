"""Offline startup regression tests for the first-run Windows user experience."""
from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType
from types import SimpleNamespace

import pytest

import launch
import setup_ffmpeg


def test_first_install_opens_gui_in_same_process(monkeypatch, capsys):
    launched, messages = [], []

    def fake_setup(**kwargs):
        messages.append('setup')
        kwargs['on_installed']()
        return True

    def fake_gui(**kwargs):
        launched.append(kwargs)
        messages.append('gui')

    monkeypatch.setattr(setup_ffmpeg, 'ensure_ffmpeg', fake_setup)
    monkeypatch.setitem(sys.modules, 'oggcultist.app', SimpleNamespace(main=fake_gui))
    launch._start_desktop()
    assert messages == ['setup', 'gui']
    assert len(launched) == 1
    assert 'installed successfully' in launched[0]['startup_message']
    assert 'Opening Oggcultist' in capsys.readouterr().out


def test_relaunch_opens_gui_without_reinstallation(monkeypatch):
    launched = []
    monkeypatch.setattr(setup_ffmpeg, 'ensure_ffmpeg', lambda **kwargs: True)
    monkeypatch.setitem(sys.modules, 'oggcultist.app',
                        SimpleNamespace(main=lambda **kwargs: launched.append(kwargs)))
    launch._start_desktop()
    assert len(launched) == 1
    assert 'FFmpeg is ready' in launched[0]['startup_message']


def test_startup_error_is_visible_and_logged(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(setup_ffmpeg, 'ensure_ffmpeg', lambda **kwargs: True)
    from oggcultist import paths
    monkeypatch.setattr(paths, 'logs_dir', lambda *a, **k: tmp_path / 'Oggcultist' / 'logs')
    def broken_gui(**kwargs):
        raise RuntimeError('synthetic Tk launch error')
    monkeypatch.setitem(sys.modules, 'oggcultist.app', SimpleNamespace(main=broken_gui))
    with pytest.raises(SystemExit) as exc:
        launch._start_desktop()
    assert exc.value.code == 1
    assert 'synthetic Tk launch error' in capsys.readouterr().err
    assert 'synthetic Tk launch error' in (tmp_path / 'Oggcultist' / 'logs' / 'startup-error.log').read_text()


def test_windows_entry_is_pythonw_not_blocked_windows_script_host():
    root = Path(__file__).resolve().parents[1]
    default = (root / 'Oggcultist.pyw').read_text().lower()
    # v1.7: run_windows_debug.bat was merged into run_windows.bat (one console launcher).
    batch = (root.parent / 'WINDOWS LAUNCHER.bat').read_text().lower()
    debug = batch
    launcher = (root / 'oggcultist' / 'services' / 'windows_launcher.py').read_text().lower()
    assert 'windows_launcher' in default and 'main(' in default
    assert not (root / 'run_windows_debug.bat').exists()
    assert 'python.exe" -u launch.py' in debug
    assert ':app_error' in debug and 'pause' in debug
    assert 'pythonw.exe' in launcher and 'creationflags' in launcher
    assert 'launcher.log' in launcher
    assert 'setup_ffmpeg.py' not in batch


def test_installer_announces_success_and_notifies_runner(tmp_path):
    from test_ffmpeg_setup import archive_bytes, fake_open
    seen = []
    local = setup_ffmpeg.local_bin('win32', {'LOCALAPPDATA':str(tmp_path)})
    def detected(_):
        return (local / 'ffmpeg.exe').is_file() and (local / 'ffprobe.exe').is_file()
    ready = setup_ffmpeg.ensure_ffmpeg(
        platform='win32', env={'LOCALAPPDATA':str(tmp_path),'PATH':'/usr/bin'},
        opener=fake_open(archive_bytes()), input_fn=lambda q: 'y',
        check_fn=detected, on_installed=lambda: seen.append('installed'),
        print_fn=seen.append)
    assert ready
    assert seen[-1] == 'installed'
    assert 'installed successfully' in seen[-2]
