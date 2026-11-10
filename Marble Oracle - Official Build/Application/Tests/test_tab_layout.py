"""Regression: tabs, moved panel controls, and no altered core features.

Run with a graphical display, e.g. xvfb-run -a python3 test_tab_layout.py.
"""
from pathlib import Path
import os
import sys
import tkinter as tk
sys.path.insert(0, str(Path(__file__).resolve().parent.parent/'Runtime'/'Marble_Oracle_App'))
from marble_oracle import parse, WindowApp
from oracle_ogg_tab import OGG_MAIN


def go(flags):
    args = vars(parse(['--selftest','--no-network','--no-markets','--no-bezel','--os-frame'] + flags))
    app = WindowApp(args)
    root, scene, canvas = app.root, app.scene, app.canvas
    root.update()
    scene.resized(1216, 848)
    root.update()
    expected = {'tab_home','tab_passphrase','tab_oggcultist','tab_touch_type','tab_eidolith','next','word','deal','view'}
    assert len(scene.nav_tabs) == 5, scene.nav_tabs
    assert expected.issubset({h[4] for h in scene.hot})
    # Workspace order, left to right: HOME, OGGCULTIST, EIDOLITH, PASSPHRASE, TOUCH TYPE.
    # Check coordinates, not just dictionary insertion order, so hit areas match visuals.
    nav_actions = {'tab_home','tab_oggcultist','tab_eidolith','tab_passphrase','tab_touch_type'}
    left_to_right = [h[4] for h in sorted((h for h in scene.hot if h[4] in nav_actions), key=lambda h: h[0])]
    assert left_to_right == ['tab_home','tab_oggcultist','tab_eidolith','tab_passphrase','tab_touch_type'], left_to_right
    assert OGG_MAIN.is_file()
    # All four former menu actions are now inside their assigned panel.
    for section, action in [('trans','next'),('lex','word'),('cards','deal'),('status','view')]:
        box = scene.rect[section]
        hit_boxes = [b for b in scene.hot if b[4] == action and box[0] <= b[0] < b[2] <= box[2]
                     and box[1] <= b[1] < b[3] <= box[3]]
        assert hit_boxes, (section, action)
        h = hit_boxes[-1]
        assert h[1] >= box[3] - max(55,round(56*scene.k)), (section,h,box)
        # The centre must resolve to the right action (not a covered hotspot).
        cx,cy=(h[0]+h[2])/2,(h[1]+h[3])/2
        result = scene.hit(cx,cy)
        assert result and result[4] == action, (section,action,result)
    # GRADE belongs to the right of the footer, leaving the other three
    # relocated panel controls at their original bottom-left positions.
    status = scene.rect['status']
    grade = next(h for h in scene.hot if h[4] == 'view')
    assert (grade[0] + grade[2]) / 2 > (status[0] + status[2]) / 2, (grade, status)
    for action in ('tab_home','tab_oggcultist','tab_eidolith','tab_passphrase','tab_touch_type'):
        h = next(h for h in scene.hot if h[4] == action)
        assert scene.hit((h[0]+h[2])/2,(h[1]+h[3])/2)[4] == action
    assert scene._which_overlay() is None
    scene.act('tab_passphrase'); root.update()
    assert scene.dk is not None and scene._which_overlay() == 'dk'
    assert scene.dk.frame.home_button.winfo_exists()
    scene.act('tab_oggcultist'); root.update()
    assert scene.dk is None and scene.ogg is not None
    assert scene._which_overlay() == 'ogg'
    assert scene.ogg.frame.process is None, 'selftest must never launch external process'
    assert scene.ogg.frame.ogg_app is not None, scene.ogg.frame.status.get()
    assert scene.ogg.frame.ogg_app._embedded
    assert len(scene.ogg.frame.ogg_app.pages) == 7
    scene.act('tab_home'); root.update()
    assert scene.dk is None and scene.ogg is None and scene._which_overlay() is None
    scene.act('tab_eidolith'); root.update()
    assert scene.eido is not None and scene._which_overlay() == 'eido'
    scene.act('tab_home'); root.update()
    assert scene.eido is None and scene._which_overlay() is None
    scene.act('tab_oggcultist'); root.update()
    assert scene.ogg is not None
    scene.on_key(type('E',(),{'keysym':'Escape','char':''})())
    assert scene.ogg is None
    scene.act('tab_passphrase'); root.update()
    assert scene.dk.frame.engine.check(scene.dk.phrase)
    scene.dk.frame.home_button.invoke()
    assert scene.dk is None
    assert len(scene.nav_tabs) == 5
    # Screenshot if configured; headless screenshot is diagnostic only.
    if os.environ.get('CAPTURE_ORACLE'):
        try:
            from PIL import ImageGrab
            scene.act('tab_home')
            root.update()
            x,y=root.winfo_rootx(),root.winfo_rooty()
            ImageGrab.grab(bbox=(x,y,x+root.winfo_width(),y+root.winfo_height())).save(
                str(Path(__file__).parent/'TAB_LAYOUT_PREVIEW.png'))
        except Exception as exc:
            print('SCREENSHOT UNAVAILABLE:', exc)
    app.quit()
    print('TABS AND BOTTOM ACTIONS OK', flags)

if __name__ == '__main__':
    for flags in ([],['--retro'],['--flat']):
        go(flags)
