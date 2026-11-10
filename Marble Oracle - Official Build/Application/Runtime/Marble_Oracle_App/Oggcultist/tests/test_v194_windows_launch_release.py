"""Launcher regression tests for the reported Windows v1.9.3 no-window failure."""
from __future__ import annotations

import hashlib
from pathlib import Path
import zipfile
from unittest.mock import patch

from oggcultist import fonts

ROOT = Path(__file__).resolve().parents[1]


def test_windows_launcher_uses_supervised_gui_entrypoint():
    data = (ROOT.parent / 'WINDOWS LAUNCHER.bat').read_bytes()
    assert b'\r\n' in data and b'\n' not in data.replace(b'\r\n', b'')
    text = data.decode('utf-8').lower()
    # 2.0.1: the launcher sits next to the "Oggcultist" folder and switches into it
    assert 'set "oggcultist_home=%~dp0oggcultist"' in text and 'cd /d "%oggcultist_home%"' in text
    assert 'start "" ".venv\\scripts\\pythonw.exe" "%oggcultist_home%\\oggcultist.pyw"' in text
    assert ':missing_folder' in text
    assert ':console_launch' in text and 'python.exe" -u launch.py' in text
    assert ':app_error' in text and 'pause' in text
    assert 'start "" ".venv\\scripts\\pythonw.exe" launch.py' not in text
    diag = (ROOT / 'DIAGNOSE_WINDOWS.bat').read_text(encoding='utf-8')
    assert '..\\windows launcher.bat" --console' in diag.lower()
    assert 'launcher.log' in (ROOT / 'oggcultist/services/windows_launcher.py').read_text(encoding='utf-8')


def test_exact_fonts_are_bundled_with_licenses():
    fonts.require_complete_bundle(strict=True)
    required = [*(info.filename for info in fonts.FONTS), *fonts.LICENCE_FILES]
    assert len(set(required)) == 5          # 2.0: three fonts and two licences
    for name in required:
        assert (ROOT / 'oggcultist/resources/fonts' / name).is_file(), name


def test_bad_windows_font_registration_warns_without_aborting(monkeypatch, capsys):
    # 2.0: no blocking dialog; the check reports False (the window then shows a status-line notice)
    from tkinter import font as tkfont
    monkeypatch.setattr(tkfont, 'families', lambda root: ('Arial', 'Courier'))
    assert fonts.ensure_ui_fonts_loaded(object()) is False
    assert 'system font' in capsys.readouterr().err


def test_source_release_builder_embeds_three_fonts(tmp_path):
    import importlib.util
    spec = importlib.util.spec_from_file_location('ogg_release', ROOT / 'packaging/source_release.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    target = tmp_path / 'program.zip'
    mod.make_archive(target, complete=False)
    with zipfile.ZipFile(target) as z:
        assert z.testzip() is None
        for info in fonts.FONTS:
            name = mod.archive_name(f'oggcultist/resources/fonts/{info.filename}')
            data = z.read(name)
            assert hashlib.sha256(data).digest() == hashlib.sha256(fonts.resource(info.filename).read_bytes()).digest()
        assert mod.archive_name('DIAGNOSE_WINDOWS.bat') in z.namelist()
