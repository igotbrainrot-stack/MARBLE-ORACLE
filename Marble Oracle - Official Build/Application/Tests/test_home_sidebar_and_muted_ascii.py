"""HOME uses the true Oggcultist sidebar texture with muted, crisp ASCII art.

Run with a display: xvfb-run -a python3 test_home_sidebar_and_muted_ascii.py
"""
import sys
from pathlib import Path
from io import BytesIO
from PIL import Image

APP = Path(__file__).resolve().parent.parent / 'Runtime' / 'Marble_Oracle_App'
sys.path.insert(0, str(APP))
from oggcultist_design_system import COLOR
from oracle_ogg_texture import png_bytes
from oracle_skin import warm_grain
from oracle_ascii_bitmap import INKS, render
from oracle_media import Statue
from marble_oracle import EMBER_SURFACES, WindowApp, parse

assert EMBER_SURFACES['bg'] == COLOR['sidebar'] == '#130F0D'
assert EMBER_SURFACES['panel'] == COLOR['sidebar']
assert warm_grain(COLOR['sidebar']) == png_bytes('side')

# The new renderer retains the original crisp/full-opacity pixels but removes
# the near-white highlight that was too harsh against the dark background.
assert len(INKS) == 10
luma = [sum(int(c[i:i+2],16)*w for i,w in ((1,.2126),(3,.7152),(5,.0722))) for c in INKS]
assert luma == sorted(luma),luma
assert luma[-1] < 210, luma[-1]
assert luma[-1] > 175, luma[-1]  # still visible on dark sidebar

s = Statue()
for plate in range(len(s.plates)):
    s.set_fit(plate, 55, 48)
    with Image.open(BytesIO(render(s, plate, 0, 3, 6))) as image:
        alpha = image.getchannel('A').histogram()
        assert sum(alpha[1:]) > 50
        assert sum(alpha[1:]) == alpha[255], 'Glyphs must remain crisp, never partially transparent'

app = WindowApp(vars(parse(['--selftest','--no-network','--no-markets','--no-bezel','--os-frame'])))
try:
    app.root.update()
    app.scene.resized(1216,848)
    app.root.update()
    assert app.scene.th['bg'] == COLOR['sidebar']
    assert app.scene.th['panel'] == COLOR['sidebar']
    assert app.scene.marble_ramp == list(INKS), 'Fallback and bitmap palettes must agree'
    # The canvas panel texture is generated from the Oggcultist side tile
    # and cached under the exact same image payload.
    assert png_bytes('side') in app.scene.skin_ph
    app.scene._arch_draw(0,0)
    assert app.scene.c.find_withtag('statue')
    print('HOME SIDEBAR SURFACE + MUTED ASCII: PASS')
finally:
    app.quit()
