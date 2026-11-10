"""v1.9.9: visual system, bundled assets, navigation and compact-screen regressions."""
from pathlib import Path
import os
import re
import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_design_tokens_and_custom_fonts_exist():
    from oggcultist.gui import design_system as d
    assert d.SPACING['micro'] < d.SPACING['tight'] < d.SPACING['related'] < d.SPACING['control']
    assert 190 <= d.SIDEBAR_WIDTH <= 240
    # 2.0 "Ember" (Forge pairing) ships these ready-made files
    for n in ['Uberfonto-Refined-Regular.ttf', 'Oggcultist-Interface-Regular.ttf', 'Oggcultist-Interface-Bold.ttf']:
        assert (ROOT/'oggcultist/resources/fonts'/n).stat().st_size > 1024


def test_new_editable_logo_icons_and_wordmark():
    from PIL import Image
    source=ROOT/'branding/forge_knot'
    for n in ['symbol.svg','symbol-small.svg','app-icon.svg','app-icon-small.svg',
              'wordmark-outlined.svg','horizontal-lockup.svg']:
        txt=(source/n).read_text()
        assert '<svg' in txt and '<path' in txt
    assert 'OGGCULTIST' in (source/'wordmark-outlined.svg').read_text()
    resources=ROOT/'oggcultist/resources'
    for n,sz in [('icon-16.png',16),('icon-32.png',32),('icon-48.png',48),('icon.png',256)]:
        with Image.open(resources/n) as im:
            assert im.size == (sz,sz)
    with Image.open(resources/'icon.ico') as ico:
        assert {16,24,32,48,64,128,256}.issubset({x[0] for x in ico.info['sizes']})
    with Image.open(resources/'brand_wordmark.png') as word:
        assert word.width > word.height*3


def test_visual_palette_contrast():
    from oggcultist.gui.theme import PALETTE
    def linear(v):
        v=int(v,16)/255
        return v/12.92 if v <= .04045 else ((v+.055)/1.055)**2.4
    def lum(hexcode):
        return sum(x*y for x,y in zip((.2126,.7152,.0722),
                   [linear(hexcode[i:i+2]) for i in (1,3,5)]))
    def contrast(a,b):
        a,b=sorted((lum(a),lum(b)),reverse=True)
        return (a+.05)/(b+.05)
    assert contrast(PALETTE['text'],PALETTE['bg'])>=7
    assert contrast(PALETTE['muted'],PALETTE['bg'])>=4.5
    assert contrast(PALETTE['sidebar_fg'],PALETTE['sidebar'])>=4.5


@pytest.mark.skipif(not os.environ.get('DISPLAY') and os.name!='nt',reason='requires graphical Tk')
def test_seven_pages_and_minimum_size_navigation(tmp_path, monkeypatch):
    from oggcultist import paths
    from oggcultist.gui.app import OggcultistApp
    monkeypatch.setenv(paths.DATA_ENV,str(tmp_path/'data'))
    a=OggcultistApp()
    try:
        a.set_animations(False)
        for width,height in [(960,600),(1240,780),(1600,900)]:
            a.geometry(f'{width}x{height}+0+0');a.update()
            for key in ('library','artists','albums','playlists','converter','art','settings'):
                a.show_page(key);a.update()
                assert a.current_page == key
                assert a.nav[key].winfo_width() <= 240
                assert a.nav['settings'].winfo_y()+a.nav['settings'].winfo_height() < a._sidebar.winfo_height()
        a.geometry('960x600+0+0');a.show_page('settings');a.update()
        settings=a.pages['settings']
        assert settings._single_settings_column is True
        assert settings._settings_right.winfo_y()>settings._settings_left.winfo_y()
        assert settings.scroll_canvas.yview()[1] < 1.0  # scroll to reach exports
        settings.scroll_canvas.yview_moveto(1);a.update()
        assert settings.scroll_canvas.yview()[0]>0
        a.show_page('art');a.update()
        art=a.pages['art']
        # 2.0: with the 64 px icon rail the editor fits beside the preview at 960×600
        form=art._editor_form
        assert form.winfo_rootx()+form.winfo_reqwidth() <= art.winfo_rootx()+art.winfo_width()
        assert art._preview_size <= 212
        a.show_page('converter');a.update()
        con=a.pages['converter']
        assert con._compact
        assert con.more_button.winfo_manager() == 'pack'
        assert con.keep_btn.winfo_manager() == ''
        assert con._detail_card.winfo_manager() == ''
        con._toggle_folders()
        assert not con._folders_expanded
        con._toggle_folders()
        assert con._folders_expanded
        # 1.9.x heading choices are accepted and change nothing in 2.0
        a.change_heading_font('old');a.update()
        assert all(b.winfo_reqwidth()<=a._sidebar.winfo_width() for b in a.nav.values())
        a.change_heading_font('new');a.update()
    finally:
        a._on_close()
