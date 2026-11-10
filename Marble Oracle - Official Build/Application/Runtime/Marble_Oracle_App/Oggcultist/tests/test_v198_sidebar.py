"""Sidebar: readable items that never clip; 2.0 adds the 64 px icon rail below 1100 px."""
from __future__ import annotations

import os
import pytest

pytest.importorskip('tkinter')

needs_display = pytest.mark.skipif(not os.getenv('DISPLAY') and os.name != 'nt',
                                   reason='requires a graphical Tk display')


@needs_display
def test_sidebar_tab_titles_maximise_width_and_keep_legend_visible(tmp_path, monkeypatch):
    from tkinter import ttk
    from oggcultist import paths
    from oggcultist.gui.app import OggcultistApp, SIDEBAR_WIDTH
    monkeypatch.setenv(paths.DATA_ENV, str(tmp_path / 'settings'))
    app = OggcultistApp()
    try:
        from oggcultist.gui import design_system as ds
        for geometry in ('1240x780', '960x600'):
            app.geometry(geometry)
            app.update()
            rail = app.winfo_width() < ds.COMPACT_BREAKPOINT
            width = ds.SIDEBAR_COMPACT_WIDTH if rail else SIDEBAR_WIDTH
            assert app.compact is rail
            assert app._sidebar.winfo_width() == width
            assert all(button.winfo_width() == width - 2 * ds.SPACE['s'] for button in app.nav.values())
            assert all(int(button.cget('width')) == 0 for button in app.nav.values())
            assert all(button.winfo_reqwidth() <= width - 2 * ds.SPACE['s'] for button in app.nav.values())
            assert all(str(button.cget('text')) == ('' if rail else app._nav_text[key])
                       for key, button in app.nav.items())
            assert app._nav_title_size > abs(int(app.fonts['body'].actual('size')))
            # The bottom Settings entry must not run below the sidebar at the minimum window size.
            settings = app.nav['settings']
            assert settings.winfo_height() > 0
            assert settings.winfo_y() + settings.winfo_height() < app._sidebar.winfo_height()
            assert str(ttk.Style(app).lookup('Nav.TButton', 'anchor')) == 'w'
            assert str(ttk.Style(app).lookup('NavRail.TButton', 'anchor')) == 'center'
    finally:
        app._on_close()


@needs_display
def test_rail_and_full_sidebar_switch_back_and_forth_without_clipping(tmp_path, monkeypatch):
    # 2.0 replaces the 1.9 heading-font switch test: the only layout change left is the icon rail
    from oggcultist import paths
    from oggcultist.gui import design_system as ds
    from oggcultist.gui.app import OggcultistApp, SIDEBAR_WIDTH
    monkeypatch.setenv(paths.DATA_ENV, str(tmp_path / 'settings'))
    app = OggcultistApp()
    try:
        for geometry, width in (('960x600', ds.SIDEBAR_COMPACT_WIDTH), ('1280x800', SIDEBAR_WIDTH),
                                ('1000x640', ds.SIDEBAR_COMPACT_WIDTH)):
            app.geometry(geometry)
            for key in ('library', 'settings', 'art'):
                app.show_page(key)
                app.update()
                assert app._sidebar.winfo_width() == width
                assert app.nav[key].cget('style').startswith('NavActive')
                assert all(b.winfo_reqwidth() <= width for b in app.nav.values())
                assert app.nav['settings'].winfo_y() + app.nav['settings'].winfo_height() < app._sidebar.winfo_height()
    finally:
        app._on_close()
