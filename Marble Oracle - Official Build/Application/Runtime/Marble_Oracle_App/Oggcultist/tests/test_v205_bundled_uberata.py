"""v2.0.5: exact Uberata Clear v3.0 bundled and used by every GUI role."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from oggcultist import fonts, paths


def test_only_one_bundled_font_and_correct_checksum():
    font = paths.resource_path('fonts', 'Uberata-Clear.ttf')
    assert font.is_file()
    assert hashlib.sha256(font.read_bytes()).hexdigest() == fonts.FONT_SHA256
    assert fonts.resource(fonts.FONT_NAME) == font
    assert len(fonts.FONTS) == 1
    assert fonts.HEADING_FAMILY == fonts.BODY_FAMILY == fonts.FAMILY == 'Uberata Clear'
    for name in fonts.LICENCE_FILES:
        assert fonts.resource(name) and fonts.resource(name).is_file()
    assert fonts.prepare_uberata()
    fonts.require_complete_bundle(strict=True)


def test_missing_font_never_overridden_by_stale_user_cache(tmp_path, monkeypatch):
    missing = tmp_path / 'no-bundled-font.ttf'
    monkeypatch.setattr(paths, 'resource_path', lambda *parts: missing if parts[-1]=='Uberata-Clear.ttf' else tmp_path / parts[-1])
    # The old cache must never count as proof of a bundled font.
    monkeypatch.setattr(fonts, 'font_cache', lambda: tmp_path)
    (tmp_path / 'Uberata-Clear.ttf').write_bytes(b'fake stale cache')
    assert fonts.resource(fonts.FONT_NAME) is None
    assert not fonts.prepare_uberata()
    with pytest.raises(FileNotFoundError, match='Bundled Uberata'):
        fonts.require_complete_bundle(strict=True)


def test_font_exports_without_original_downloads(tmp_path):
    exported = fonts.export_fonts(tmp_path)
    assert (exported / fonts.FONT_NAME).read_bytes() == fonts.resource(fonts.FONT_NAME).read_bytes()
    for name in fonts.LICENCE_FILES:
        assert (exported / name).is_file()


def test_only_uberata_for_existing_font_choices():
    for choice in ('old', 'aero', 'new', 'uberata', None, 'display'):
        assert fonts.heading_family(choice) == 'Uberata Clear'
        assert fonts.body_family(choice) == 'Uberata Clear'
        assert fonts.font_file(choice=choice) == fonts.resource(fonts.FONT_NAME)


@pytest.mark.skipif(not os.environ.get('DISPLAY'), reason='requires GUI display')
def test_actual_tk_font_roles(tmp_path, monkeypatch):
    import tkinter as tk
    from tkinter import font as tkfont
    from oggcultist.gui import theme
    monkeypatch.setenv(paths.DATA_ENV, str(tmp_path / 'isolated-data'))
    fonts._registered = None
    assert fonts.register_private_fonts()
    root = tk.Tk()
    try:
        assert 'Uberata Clear' in tkfont.families(root)
        named = theme.apply_theme(root)
        for role, item in named.items():
            assert item.actual('family') == 'Uberata Clear', (role, item.actual())
    finally:
        root.destroy()
