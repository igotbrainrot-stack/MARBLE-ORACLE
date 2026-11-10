"""v1.8.9: the gradient drift, button hover/press motion, the Animations setting, bigger headings."""
from __future__ import annotations

import os
import time

import pytest

pytest.importorskip('tkinter')
pytest.importorskip('PIL')
from oggcultist.gui import animation  # noqa: E402


def test_shift_cycle_goes_down_and_back_up_smoothly():
    shifts = [animation.shift_for(i) for i in range(animation.PHASES + 1)]
    assert shifts[0] == pytest.approx(0) and shifts[-1] == pytest.approx(0)
    assert max(shifts) == pytest.approx(1)
    steps = [abs(b - a) for a, b in zip(shifts, shifts[1:])]
    assert max(steps) < 0.15                                   # slow: no visible jumps


def test_gradient_drift_moves_the_colours_but_keeps_the_size():
    from oggcultist.gui import textures
    from oggcultist.gui.theme import GRADIENT
    still = textures.gradient((96, 30), GRADIENT, behind='#1D1714', radius=0, seed=31)
    top = textures.gradient((96, 30), GRADIENT, behind='#1D1714', radius=0, seed=31, shift=0.0)
    bottom = textures.gradient((96, 30), GRADIENT, behind='#1D1714', radius=0, seed=31, shift=1.0)
    assert still.size == top.size == bottom.size
    # at the bottom of its drift the middle of the button is redder (less green) than at the top
    assert bottom.getpixel((48, 15))[1] < top.getpixel((48, 15))[1]
    assert textures.drift(0.5, None) == 0.5


def test_icons_drift_too():
    from oggcultist.gui import icons
    from oggcultist.gui.theme import GRADIENT
    a = icons.render('stop', 24, GRADIENT, icons.OUTLINE, 0.0).convert('RGB').getpixel((12, 12))
    b = icons.render('stop', 24, GRADIENT, icons.OUTLINE, 1.0).convert('RGB').getpixel((12, 12))
    assert a != b


needs_display = pytest.mark.skipif(not os.environ.get('DISPLAY'), reason='needs a display')


@pytest.fixture
def app(tmp_path, monkeypatch):
    pytest.importorskip('tkinter')
    from oggcultist import paths
    monkeypatch.setenv(paths.DATA_ENV, str(tmp_path / 'data'))
    from oggcultist.gui import app as app_module
    application = app_module.OggcultistApp()
    application.update()
    yield application
    try:
        application._on_close()
    except Exception:
        pass


def _pump(widget, seconds):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        widget.update()
        time.sleep(0.01)


@needs_display
def test_animated_images_change_frame_and_reset_when_switched_off(app):
    anim = app._og_anim
    assert anim.targets and len(anim.targets) >= 16          # buttons, nav marker, icons
    anim.prepare_all()
    photo = anim.targets[0][0]
    first = app.tk.call(str(photo), 'get', 48, 10)
    anim.show(animation.PHASES // 2)
    middle = app.tk.call(str(photo), 'get', 48, 10)
    assert first != middle
    app.set_animations(False)
    assert anim.phase == 0 and app.tk.call(str(photo), 'get', 48, 10) == first
    app.set_animations(True)
    assert anim.enabled


@needs_display
def test_every_button_style_has_hover_steps_and_a_press_sink(app):
    from tkinter import ttk
    s = ttk.Style(app)
    for style in ('TButton', 'Accent.TButton', 'Ghost.TButton', 'Transport.TButton', 'Mode.TButton',
                  'ModeOn.TButton', 'Play.TButton', 'Nav.TButton'):
        assert style in app._og_motion.styles
        for level in (1, 2, 3, 'F'):
            assert s.layout(animation.variant(level, style)), (style, level)
        pressed = dict((tuple(state), value) for *state, value in s.map(style, 'padding'))
        assert pressed, style                                   # the label sinks while pressed
    assert s.lookup('OgH2.Accent.TButton', 'font') == s.lookup('Accent.TButton', 'font')   # options inherited


def _accent_button(app):
    from tkinter import ttk
    import tkinter as tk
    frame = ttk.Frame(app)
    frame.place(x=0, y=0)
    button = ttk.Button(frame, text='Test', style='Accent.TButton')
    button.pack()
    app.update()
    return button


@needs_display
def test_hover_fades_in_and_out(app):
    button = _accent_button(app)
    button.event_generate('<Enter>')
    seen = set()
    for _ in range(30):
        seen.add(button.cget('style'))
        _pump(app, 0.01)
    assert {'OgH1.Accent.TButton', 'OgH2.Accent.TButton', 'OgH3.Accent.TButton'} <= seen
    assert button.cget('style') == 'Accent.TButton'
    button.event_generate('<Leave>')
    _pump(app, 0.3)
    assert button.cget('style') == 'Accent.TButton'


@needs_display
def test_the_app_changing_a_style_mid_fade_wins(app):
    from tkinter import ttk
    frame = ttk.Frame(app)
    frame.place(x=0, y=0)
    button = ttk.Button(frame, text='Shuffle', style='Mode.TButton')
    button.pack()
    app.update()
    button.event_generate('<Enter>')
    app.update()
    button.configure(style='ModeOn.TButton')                    # e.g. shuffle switched on
    _pump(app, 0.3)
    assert button.cget('style') == 'ModeOn.TButton'


@needs_display
def test_no_motion_when_animations_are_off(app):
    app.set_animations(False)
    button = _accent_button(app)
    button.event_generate('<Enter>')
    _pump(app, 0.1)
    assert button.cget('style') == 'Accent.TButton'


@needs_display
def test_gradient_rule_follows_the_drift(app):
    from oggcultist.gui.widgets import GradientRule
    rule = next(w for w in app.winfo_children() if isinstance(w, GradientRule))
    app.update()
    item = rule._cells[len(rule._cells) // 2][0]
    before = rule.itemcget(item, 'fill')
    rule.set_shift(1.0)
    assert rule.itemcget(item, 'fill') != before


@needs_display
def test_headings_are_bigger(app):
    from tkinter import font as tkfont
    size = lambda name: abs(int(tkfont.nametofont(name, root=app).actual('size')))
    body = size('OgBody')
    # 2.0 "Ember" type scale (design_system.TYPE): display-xl titles, display-l now playing,
    # bold text-face section titles, small capitals for column headings
    assert size('OgTitle') >= body + 14
    assert size('OgHeading') >= body + 2
    assert size('OgNowTitle') >= body + 6
    assert body - 2 <= size('OgColumn') < body


@needs_display
def test_settings_toggle_saves_and_applies(app):
    from oggcultist.gui import app as app_module
    page = app.pages['settings']
    page.animations.set(False)
    page._animations_changed()
    assert app_module.load_settings()['animations'] is False
    assert not app._og_anim.enabled and not app._og_motion.enabled
