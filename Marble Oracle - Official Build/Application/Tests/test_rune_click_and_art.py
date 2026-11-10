"""Exercise real Tk click delivery and image clearance for the Rune panel.

Run: xvfb-run -a python3 Application/Tests/test_rune_click_and_art.py
No media network calls, no dependency installation or file-writing required.
"""
from pathlib import Path
import sys
from zipfile import ZipFile
import tkinter as tk
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Runtime' / 'Marble_Oracle_App'))
from marble_oracle import WindowApp, LAYOUTS

options = dict(theme='EMBER', layout='CLASSIC', fps=30, crt=False,
               no_dicekey=False, no_markets=True, no_network=True,
               bezel=False, osframe=True, retro=False, flat=False,
               look=None, crt_v2=False, no_pixel_barrel=True,
               no_audio_scope=True, selftest=True, wire=None)
app = WindowApp(options)
root, scene = app.root, app.scene
clicks = 0

def click_hot(action):
    global clicks
    boxes = [h for h in scene.hot if h[4] == action and scene.hot_active(h)]
    assert boxes, ('missing click target', action, scene.o['layout'])
    h = boxes[-1]
    x, y = round((h[0]+h[2])/2), round((h[1]+h[3])/2)
    found = scene.hit(x,y)
    assert found and found[4] == action, ('covered click target', action, found, scene.o['layout'])
    scene.c.event_generate('<Button-1>', x=x, y=y)
    root.update_idletasks()
    clicks += 1

try:
    root.update()
    for layout in LAYOUTS:
        scene.o['layout'] = layout
        for w, h in ((1216,848), (900,620), (760,550), (640,460)):
            root.geometry(f'{w}x{h}+20+20')
            root.update()
            scene.resized(scene.c.winfo_width(),scene.c.winfo_height())
            root.update()
            if scene.divination_mode != 'tarot':
                click_hot('mode_tarot')
                assert scene.divination_mode == 'tarot'
            click_hot('mode_runes')
            assert scene.divination_mode == 'runes', (layout,w,h,'RUNE toggle ignored')
            # Both first click and repeat clicks must respond, including while animating.
            old = scene.rune_run_id
            click_hot('rune_draw')
            assert scene.rune_run_id == old + 1, (layout,w,h,'Draw click ignored')
            old = scene.rune_run_id
            click_hot('rune_draw')
            assert scene.rune_run_id == old + 1, (layout,w,h,'Restart click ignored')
            assert all(wid.winfo_ismapped() for wid in scene.rune_widgets), (layout,w,h,'stone hidden')
            for wid in scene.rune_widgets:
                l,t,r,b=wid.rune_bounds
                assert 2 <= wid.image.width() <= r-l and wid.image.height() <= b-t, (layout,w,h,'image cropped')
                box=wid.rune_safe_box
                assert box[0] <= l < r <= box[2] and box[1] <= t < b <= box[3], (layout,w,h,'border touched')
            click_hot('mode_tarot')
            assert scene.divination_mode == 'tarot' and all(not wid.winfo_ismapped() for wid in scene.rune_widgets), (layout,w,h,'Tarot toggle ignored')
    # Direct Tk-image click must remain responsive, not just simulated canvas hits.
    scene.o['layout']='CLASSIC'
    root.geometry('1216x848+20+20')
    root.update(); scene.resized(scene.c.winfo_width(),scene.c.winfo_height()); root.update()
    click_hot('mode_runes')
    click_hot('rune_draw')
    scene.rune_sel = 0
    scene.rune_widgets[2].event_generate('<Button-1>', x=4, y=4)
    root.update_idletasks()
    assert scene.rune_sel == 2, 'native stone widget ignored click'
    print(f'RUNE CLICK + ART OK: {clicks} actual canvas clicks, {len(LAYOUTS)} layouts, 4 window sizes; stone widget click')
finally:
    app.quit()
