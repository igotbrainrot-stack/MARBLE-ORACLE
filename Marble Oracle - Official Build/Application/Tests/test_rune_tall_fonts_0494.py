"""0.4.9.4: rune stones keep a real height when system fonts are tall.

    xvfb-run -a python3 Application/Tests/test_rune_tall_fonts_0494.py

0.4.9.3 failed one check on Windows only: at 640x460 in the STATUE layout the
stones were given no height, because Windows fonts are taller than Linux ones
and the caption band swallowed the column. This reproduces the condition on
any system by reporting a taller line height, as Windows does. It is a
simulation: the real proof is test_rune_click_and_art.py passing on Windows.
"""
import os
os.environ.setdefault('MARBLE_ORACLE_APPEARANCE', 'classic')   # 0.5.1: this test checks Classic's labels and surfaces
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Runtime' / 'Marble_Oracle_App'))
from marble_oracle import WindowApp  # noqa: E402

opts = dict(theme='EMBER', layout='STATUE', fps=30, crt=False, no_dicekey=False,
            no_markets=True, no_network=True, bezel=False, osframe=True,
            retro=False, flat=False, look=None, crt_v2=False, no_pixel_barrel=True,
            no_audio_scope=True, selftest=True, wire=None)


class TallFont:
    """A real Tk font that reports a taller line, like Windows system fonts."""
    def __init__(self, font, factor):
        self._font, self._factor = font, factor

    def metrics(self, name=None):
        value = self._font.metrics(name)
        return int(round(value * self._factor)) if name == 'linespace' else value

    def __getattr__(self, name):
        return getattr(self._font, name)

    def __str__(self):
        return str(self._font)


app = WindowApp(opts)
checks = 0
try:
    root, scene = app.root, app.scene
    real_font = scene.font
    for layout in ('STATUE', 'CLASSIC'):
        scene.o['layout'] = layout
        # Windows fonts are about 1.2-1.4x Linux ones, so 1.8x on Linux covers
        # Windows with room to spare. On Windows the real metrics are already
        # tall: 1.4x on top of them is the headroom checked there (1.8x on top
        # leaves 12 px in total and is not a size any system produces).
        for factor in ((1.0, 1.4) if sys.platform == 'win32' else (1.0, 1.4, 1.8)):
            scene.font = lambda *a, _f=factor, **k: TallFont(real_font(*a, **k), _f)
            for width, height in ((640, 460), (760, 550), (900, 620)):
                root.geometry(f'{width}x{height}+16+16')
                root.update(); scene.resized(scene.c.winfo_width(), scene.c.winfo_height()); root.update()
                scene.divination_mode = 'runes'
                scene.rune_drawn = [scene.rune_deck.runes[i] for i in (4, 9, 10)]
                scene.rune_revealed = 3; scene.rune_state = 'complete'; scene.rune_anim_index = -1; scene.rune_sel = 1
                scene.draw_cards(); root.update()
                x0, y0, x1, y1 = scene.rect['cards']
                reading_top = y1 - max(75, int((y1 - y0) * .30)) + 4
                where = (layout, factor, width, height)
                assert scene.rune_art_error is None, (where, scene.rune_art_error)
                for i, wid in enumerate(scene.rune_widgets):
                    left, top, right, bottom = wid.rune_bounds
                    assert wid.winfo_ismapped(), (where, 'stone hidden')
                    assert wid.image.height() >= 20 and wid.image.width() >= 20, (where, 'stone has no real size', wid.image.height())
                    assert bottom <= reading_top, (where, 'stone enters the reading pane', bottom, reading_top)
                    box = wid.rune_safe_box
                    assert box[0] <= left < right <= box[2] and box[1] <= top < bottom <= box[3], (where, 'outside its cell')
                    assert scene.hit((left + right) // 2, (top + bottom) // 2)[4] == f'rune_select{i}', (where, 'not clickable')
                    checks += 1
    scene.font = real_font
    print('RUNE TALL FONTS OK:', checks, 'stones checked with taller line heights in two layouts')
finally:
    app.quit()
