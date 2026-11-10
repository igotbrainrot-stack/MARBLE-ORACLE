"""Regression for Windows Script Host blocking the former .vbs entrypoint."""
from __future__ import annotations

import io
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from oggcultist import windows_launcher as start

ROOT = Path(__file__).resolve().parents[1]


def test_only_console_free_python_entrypoint_no_wsh():
    source = (ROOT / 'Oggcultist.pyw').read_text(encoding='utf-8')
    assert 'windows_launcher' in source and 'main(' in source
    assert not (ROOT / 'Oggcultist.vbs').exists()
    assert not (ROOT / 'run_windows_silent.bat').exists()
    # v1.7: a single console launcher (run_windows.bat) replaces the former pair.
    data = (ROOT.parent / 'WINDOWS LAUNCHER.bat').read_text(encoding='utf-8').lower()
    assert 'wscript' not in data and '.vbs' not in data
    assert not (ROOT / 'run_windows_debug.bat').exists()


def test_already_installed_launch_is_quiet_and_cached(tmp_path):
    (tmp_path / 'requirements.txt').write_text('mutagen>=1.47,<2\n', encoding='utf-8')
    (tmp_path / 'launch.py').write_text('pass\n', encoding='utf-8')
    gui = start.venv_gui_python(tmp_path)
    gui.parent.mkdir(parents=True)
    gui.write_bytes(b'exe')
    (gui.parent / 'python.exe').write_bytes(b'exe')
    marker = tmp_path / '.venv' / '.oggcultist_requirements'
    marker.write_text(start._requirements_signature(tmp_path), encoding='ascii')
    calls = []
    def runner(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(returncode=0)
    start.run(tmp_path, io.StringIO(), runner=runner)
    assert len(calls) == 1
    assert calls[0][0][-2:] == [str(tmp_path / 'launch.py'), '--windowless']
    assert calls[0][1]['stdin'] == -3   # subprocess.DEVNULL
    assert calls[0][1]['stderr'] == -2  # subprocess.STDOUT


def test_first_run_creates_env_and_installs_once(tmp_path):
    (tmp_path / 'requirements.txt').write_text('Pillow>=10\n', encoding='utf-8')
    (tmp_path / 'launch.py').write_text('pass\n', encoding='utf-8')
    calls = []
    def runner(args, **kwargs):
        calls.append(args)
        if len(calls) == 1:  # venv creation
            pyw = start.venv_gui_python(tmp_path)
            pyw.parent.mkdir(parents=True)
            pyw.write_bytes(b'fake-pythonw')
            (pyw.parent / 'python.exe').write_bytes(b'fake-python')
        return SimpleNamespace(returncode=0)
    start.run(tmp_path, io.StringIO(), runner=runner)
    assert len(calls) == 3
    assert calls[0][1:3] == ['-m', 'venv']
    assert calls[1][1:4] == ['-m', 'pip', 'install']
    assert calls[2][-1] == '--windowless'
    start.run(tmp_path, io.StringIO(), runner=runner)
    assert len(calls) == 4  # no new venv / pip on next launch


def test_command_failures_raise_useful_errors(tmp_path):
    (tmp_path / 'requirements.txt').write_text('', encoding='utf-8')
    (tmp_path / 'launch.py').write_text('pass', encoding='utf-8')
    def fail(args, **kwargs):
        return SimpleNamespace(returncode=9)
    with pytest.raises(start.StartupError, match='exit 9'):
        start.run(tmp_path, io.StringIO(), runner=fail)


def test_main_raises_dialog_on_missing_application(tmp_path, monkeypatch):
    seen = []
    monkeypatch.setattr(start, 'logs_dir', lambda: tmp_path / 'logs')
    monkeypatch.setattr(start, '_show_error', seen.append)
    assert start.main(tmp_path / 'no_app') == 1
    assert 'Extract the entire Oggcultist ZIP' in seen[0]
    assert (tmp_path / 'logs' / 'launcher.log').is_file()


def test_windows_creation_flag_is_no_console(monkeypatch, tmp_path):
    monkeypatch.setattr(start.sys, 'platform', 'win32')
    opts = []
    def runner(args, **kwargs):
        opts.append(kwargs['creationflags'])
        return SimpleNamespace(returncode=0)
    start._run(['fake-pythonw.exe', 'launch.py'], tmp_path, io.StringIO(), runner=runner)
    assert opts == [start.CREATE_NO_WINDOW]
