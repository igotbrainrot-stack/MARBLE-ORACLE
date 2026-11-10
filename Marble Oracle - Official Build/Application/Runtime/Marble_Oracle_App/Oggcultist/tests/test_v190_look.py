"""v1.9.0: modern sliders and progress bar, slight rounding with a bevel on every surface."""
from __future__ import annotations

import os
import time

import pytest

pytest.importorskip('tkinter')
pytest.importorskip('PIL')

from oggcultist.gui import sliders, textures  # noqa: E402

GRADIENT = ('#FED154', '#FDA629', '#EC4406')


def test_slider_render_fills_up_to_the_thumb():
    image = sliders.render(400, 22, 0.5, behind='#211915', grain_amount=0.18, stops=GRADIENT, shift=0.0,
                           track=6, thumb=8, pad=10)
    assert image.size == (400, 22)
    filled = image.getpixel((100, 11))          # left of the thumb: amber
    empty = image.getpixel((330, 11))           # right of the thumb: the dark groove
    assert filled[0] > 200 and filled[1] > 120
    assert max(empty) < 60
    knob = image.getpixel((200, 9))             # the cream knob in the middle
    assert min(knob) > 180


def test_progress_render_has_no_thumb_and_rounded_ends():
    image = sliders.render(300, 14, 1.0, behind='#1D1714', grain_amount=0.2, stops=GRADIENT, shift=None,
                           track=8, thumb=None)
    middle = image.getpixel((150, 7))
    corner = image.getpixel((1, 3))             # outside the rounded end: background
    assert middle[0] > 200
    assert max(corner) < 60


def test_bevel_lights_the_top_left_and_shades_the_bottom_right():
    flat = textures.surface((60, 30), '#555555', '#555555', behind='#000000', radius=4, edge=0, amount=0.0)
    raised = textures.surface((60, 30), '#555555', '#555555', behind='#000000', radius=4, edge=0, amount=0.0,
                              bevel=0.3)
    sunken = textures.surface((60, 30), '#555555', '#555555', behind='#000000', radius=4, edge=0, amount=0.0,
                              bevel=-0.3)
    top, bottom = (30, 0), (30, 29)
    assert sum(raised.getpixel(top)) > sum(flat.getpixel(top)) > sum(sunken.getpixel(top))
    assert sum(raised.getpixel(bottom)) < sum(flat.getpixel(bottom)) < sum(sunken.getpixel(bottom))
    assert raised.getpixel((30, 15)) == flat.getpixel((30, 15))          # the middle is untouched


def test_rounded_pictures_have_soft_corners():
    from PIL import Image
    picture = textures.rounded_picture(Image.new('RGB', (60, 60), (200, 0, 200)), '#211915')
    assert picture.getpixel((0, 0)) != (200, 0, 200)                    # corner: the panel shows
    assert picture.getpixel((30, 30)) == (200, 0, 200)


needs_display = pytest.mark.skipif(not os.environ.get('DISPLAY'), reason='needs a display')


@pytest.fixture
def root():
    import tkinter as tk
    window = tk.Tk()
    window.geometry('500x200')
    yield window
    window.destroy()


def _pump(widget, seconds=0.0):
    end = time.monotonic() + seconds
    widget.update()
    while time.monotonic() < end:
        widget.update()
        time.sleep(0.01)


@needs_display
def test_slider_click_drag_keys_wheel_and_disabled(root):
    import tkinter as tk
    var = tk.DoubleVar(value=0)
    calls = []
    slider = sliders.GradientSlider(root, from_=0, to=100, variable=var, length=300,
                                    on_press=lambda: calls.append('press'), on_drag=lambda: calls.append('drag'),
                                    on_release=lambda: calls.append('release'))
    slider.pack()
    _pump(root)
    width = slider.winfo_width()
    slider.event_generate('<ButtonPress-1>', x=width // 2, y=10)
    slider.event_generate('<B1-Motion>', x=int(width * 0.8), y=10)
    slider.event_generate('<ButtonRelease-1>', x=int(width * 0.8), y=10)
    assert calls[:2] == ['press', 'drag'] and calls[-1] == 'release'
    assert var.get() == pytest.approx(80, abs=5)
    slider.focus_force(); _pump(root)
    before = var.get()
    slider.event_generate('<Right>')
    assert var.get() == pytest.approx(before + 2)
    slider.event_generate('<Home>')
    assert var.get() == 0
    slider.configure(to=10)
    assert slider.cget('to') == 10
    slider.state(['disabled'])
    slider.event_generate('<ButtonPress-1>', x=width - 5, y=10)
    assert var.get() == 0 and slider.instate(['disabled'])


@needs_display
def test_slider_grows_on_hover_and_shrinks_after(root):
    slider = sliders.GradientSlider(root, length=200)
    slider.pack()
    _pump(root)
    slider.event_generate('<Enter>')
    _pump(root, 0.2)
    assert slider._grow == pytest.approx(1.0)
    slider.event_generate('<Leave>')
    _pump(root, 0.2)
    assert slider._grow == pytest.approx(0.0)


@needs_display
def test_progress_bar_takes_value_like_ttk(root):
    bar = sliders.GradientBar(root, maximum=100)
    bar.pack(fill='x')
    bar['value'] = 40
    assert bar['value'] == 40 and bar._fraction() == pytest.approx(0.4)
    bar.configure(maximum=80)
    assert bar._fraction() == pytest.approx(0.5)
    _pump(root)


@needs_display
def test_theme_uses_rounded_bevelled_elements(root):
    from tkinter import ttk
    from oggcultist.gui.theme import apply_theme
    apply_theme(root)
    s = ttk.Style(root)
    def first(style):
        return s.layout(style)[0][0]
    assert first('TEntry') == 'Og.Field' and first('Card.TEntry') == 'Og.Field.card'
    assert first('TCombobox') == 'Og.Field'
    assert first('Treeview') == 'Og.TableField'
    assert first('Card.TFrame') == 'Og.cardframe' and first('CardInner.TFrame') == 'Og.card'
    flat = repr(s.layout('Vertical.TScrollbar'))
    assert 'OgV.thumb' in flat and 'arrow' not in flat                  # slim thumb, no arrow buttons
    assert 'Og.Check' in repr(s.layout('TCheckbutton')) and 'Og.Check.card' in repr(s.layout('Card.TCheckbutton'))


@needs_display
def test_scrollbar_still_scrolls(root):
    from tkinter import ttk
    from oggcultist.gui.theme import apply_theme
    apply_theme(root)
    tree = ttk.Treeview(root, height=3)
    for i in range(50):
        tree.insert('', 'end', text=str(i))
    bar = ttk.Scrollbar(root, orient='vertical', command=tree.yview)
    tree.configure(yscrollcommand=bar.set)
    tree.pack(side='left'); bar.pack(side='left', fill='y')
    _pump(root)
    bar.set(0.5, 0.6)
    _pump(root)
    height = bar.winfo_height()
    assert bar.identify(bar.winfo_width() // 2, int(height * 0.57)).endswith('thumb')
    assert bar.identify(bar.winfo_width() // 2, 2) == 'trough'


@needs_display
def test_swatch_shows_colours_and_ignores_clicks_when_disabled(root):
    from oggcultist.gui.widgets import Swatch
    clicks = []
    swatch = Swatch(root, command=lambda: clicks.append(1))
    swatch.pack()
    _pump(root)
    swatch.configure(background='#1B4D3E', activebackground='#1B4D3E')
    assert swatch._colour == '#1B4D3E' and str(swatch.cget('image'))
    swatch.event_generate('<Button-1>')
    swatch.configure(state='disabled')
    swatch.event_generate('<Button-1>')
    assert clicks == [1]
