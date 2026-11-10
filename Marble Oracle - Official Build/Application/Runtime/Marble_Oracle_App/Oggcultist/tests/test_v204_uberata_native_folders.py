"""v2.0.4 regression tests: sole Uberata font and native directory selection."""
from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import font as tkfont
from unittest import mock

import pytest

from oggcultist import fonts, paths
from oggcultist.gui import native_folders as folders
from oggcultist.gui import theme


RELEASE = Path(__file__).resolve().parents[3] / 'font_release' / 'Uberata-Clear-v3.0'


def test_only_uberata_family_configured():
    assert len(fonts.FONTS) == 1
    assert fonts.HEADING_FAMILY == fonts.BODY_FAMILY == 'Uberata Clear'
    assert fonts.heading_family('old') == fonts.body_family('new') == 'Uberata Clear'
    assert fonts.HEADING_FILE == fonts.BODY_FILES['bold'] == 'Uberata-Clear.ttf'


def test_uberata_is_bundled_and_needs_no_downloads(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, 'home', classmethod(lambda cls: tmp_path))
    monkeypatch.setenv(paths.DATA_ENV, str(tmp_path / 'appdata'))
    assert fonts.prepare_uberata()
    font = fonts.resource(fonts.FONT_NAME)
    assert font and hashlib.sha256(font.read_bytes()).hexdigest() == fonts.FONT_SHA256
    assert all(fonts.resource(name) for name in fonts.LICENCE_FILES)
    assert fonts.heading_file() == fonts.body_file('bold') == font
    assert not (tmp_path / 'appdata' / 'fonts' / 'uberata-v3').exists()


def test_linux_gtk_uses_standard_chooser(monkeypatch, tmp_path):
    class Result:
        returncode = 0
        stdout = '/home/mint/Music Collection\n'
    monkeypatch.setattr(folders.sys, 'platform', 'linux')
    monkeypatch.setattr(folders.shutil, 'which', lambda item: '/usr/bin/zenity' if item == 'zenity' else None)
    commands = []
    monkeypatch.setattr(folders.subprocess, 'run', lambda cmd, **kwargs: (commands.append(cmd), Result())[1])
    chosen = folders.choose_directory(title='Choose source', initialdir=tmp_path)
    assert chosen == '/home/mint/Music Collection'
    assert commands[0][0] == '/usr/bin/zenity'
    assert '--file-selection' in commands[0] and '--directory' in commands[0]
    assert any(arg.startswith('--filename=') for arg in commands[0])


def test_gtk_cancel_keeps_existing_path(monkeypatch, tmp_path):
    monkeypatch.setattr(folders.sys, 'platform', 'linux')
    monkeypatch.setattr(folders.shutil, 'which', lambda item: '/usr/bin/zenity' if item == 'zenity' else None)
    class Result:
        returncode = 1
        stdout = ''
    monkeypatch.setattr(folders.subprocess, 'run', lambda cmd, **kwargs: Result())
    monkeypatch.setattr(folders.filedialog, 'askdirectory', lambda **kwargs: (_ for _ in ()).throw(AssertionError('unexpected fallback')))
    assert folders.choose_directory(initialdir=tmp_path) == ''


def test_windows_routes_to_explorer_dialog(monkeypatch, tmp_path):
    monkeypatch.setattr(folders.sys, 'platform', 'win32')
    monkeypatch.setattr(folders, '_windows_explorer_directory', lambda parent, title, initial: r'C:\Music\Albums')
    monkeypatch.setattr(folders.filedialog, 'askdirectory', lambda **kwargs: (_ for _ in ()).throw(AssertionError('not native')))
    assert folders.choose_directory(initialdir=tmp_path) == r'C:\Music\Albums'


def test_native_missing_falls_back_to_tk(monkeypatch, tmp_path):
    monkeypatch.setattr(folders.sys, 'platform', 'linux')
    monkeypatch.setattr(folders.shutil, 'which', lambda name: None)
    monkeypatch.setattr(folders.filedialog, 'askdirectory', lambda **kwargs: '/chosen/fallback')
    assert folders.choose_directory(initialdir=tmp_path) == '/chosen/fallback'


def test_launcher_has_windowless_start_and_no_success_pause():
    bat = (Path(__file__).resolve().parents[2] / 'WINDOWS LAUNCHER.bat').read_text()
    assert 'start "" ".venv\\Scripts\\pythonw.exe"' in bat
    assert 'if defined OGGCULTIST_CONSOLE goto console_launch' in bat
    assert 'exit /b 0' in bat
    assert 'pause >nul' not in bat


@pytest.mark.skipif(not os.environ.get('DISPLAY'), reason='needs a virtual/real desktop')
def test_real_tk_uses_uberata_for_every_font_role(tmp_path, monkeypatch):
    monkeypatch.setenv(paths.DATA_ENV, str(tmp_path / 'data'))
    fonts._registered = None
    assert fonts.register_private_fonts()
    root = tk.Tk()
    try:
        assert 'Uberata Clear' in set(tkfont.families(root))
        themed = theme.apply_theme(root)
        for key, font in themed.items():
            assert font.actual('family') == 'Uberata Clear', (key, font.actual())
    finally:
        root.destroy()
