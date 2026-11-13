"""Typing engine, UI and Oracle tab integration regressions (Tk uses Xvfb)."""
from pathlib import Path
import os
import sys
import random
import tkinter as tk
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'Runtime'/'Marble_Oracle_App'))
from oracle_touch_type import TypingEngine, TouchTypePanel, MODES, finger_for
from marble_oracle import WindowApp, parse


def engine_tests():
    assert finger_for('f') == 'LEFT INDEX'
    assert finger_for('j') == 'RIGHT INDEX'
    assert finger_for(' ') == 'THUMBS · SPACE'
    now=[100.0]
    clock=lambda:now[0]
    e=TypingEngine(rng=random.Random(44),clock=clock)
    assert e.phase=='ready' and e.mode=='keys'
    assert e.press('x')=='inactive'
    e.start()
    first=e.expected
    assert e.press('Z')=='wrong' and e.index==0 and e.errors==1
    for key in e.prompt:
        assert e.press(key) in ('correct','finished')
    assert e.phase=='complete' and e.correct==len(e.prompt)
    assert e.accuracy < 100
    e.set_mode('words')
    e.start()
    for char in e.prompt:
        e.press(char)
    assert e.completed==1 and e.phase=='running'
    now[0]+=2.5
    e.tick()
    assert e.wpm>0 and e.elapsed >=2.5
    e.pause()
    before=e.elapsed
    now[0]+=45
    e.tick()
    assert e.elapsed==before
    e.start()
    now[0]+=60
    e.tick()
    assert e.phase=='complete' and e.elapsed==60
    e.set_mode('sentences')
    e.start()
    for _ in range(3):
        prompt=e.prompt
        for ch in prompt:
            e.press(ch)
    assert e.phase=='complete' and e.completed==3
    e.set_mode('fall')
    e.start()
    for _ in range(4):
        now[0]+=10
        e.tick()
    assert e.lives==0 and e.phase=='complete'
    e.set_mode('fall')
    e.start()
    for _ in range(12):
        for ch in e.prompt:
            e.press(ch)
    assert e.phase=='complete' and e.completed==12 and e.lives==4
    print('TOUCH TYPE ENGINE: modes, scoring, pause, countdown, falling lives PASS')


def gui_tests():
    opts=vars(parse(['--selftest','--no-network','--no-markets','--no-bezel','--os-frame']))
    app=WindowApp(opts)
    root,scene=app.root,app.scene
    try:
        root.update()
        scene.resized(1216,848)
        root.update()
        assert len(scene.nav_tabs)==6
        assert 'tab_touch_type' in scene.nav_tabs
        scene.act('tab_touch_type')
        root.update()
        assert scene.touch is not None and scene._which_overlay() == 'touch', scene.msg
        panel=scene.touch.frame
        assert panel.winfo_ismapped() and panel.winfo_width()>500, panel.winfo_width()
        assert panel.typing_entry.winfo_exists()
        panel._invoke(panel._start)
        assert panel.engine.phase=='running'
        first=panel.engine.expected
        panel.focus_input();root.update()
        assert root.focus_get() == panel.typing_entry, 'typing field did not get focus'
        panel.typing_entry.event_generate('<KeyPress>', keysym=first)
        root.update()
        assert panel.engine.index==1, 'native Tk key event was not accepted'
        panel._invoke(lambda:panel.set_mode('fall'))
        panel._invoke(panel._start)
        assert panel.fall_area.winfo_manager() == 'pack'
        root.update()
        assert panel.fall_area.winfo_width()>200
        panel._invoke(lambda:panel.set_mode('keys'))
        assert not panel.fall_area.winfo_manager()
        # switching to HOME must suspend the lesson and hide its window
        panel._invoke(panel._start)
        assert panel.engine.phase=='running'
        cached=scene.touch
        scene.act('tab_home')
        root.update()
        assert scene.touch is None and panel.engine.phase=='paused'
        assert not panel.winfo_ismapped()
        scene.act('tab_passphrase')
        root.update()
        assert scene.dk and scene._which_overlay()=='dk'
        scene.act('tab_touch_type')
        root.update()
        assert scene.touch is cached and panel.engine.phase=='paused'
        assert panel.winfo_ismapped()
        assert 'tab_touch_type' in scene.nav_tabs
        scene.act('tab_oggcultist')
        root.update()
        assert scene.ogg and not panel.winfo_ismapped()
        scene.act('tab_touch_type')
        root.update()
        assert scene.touch is cached
        if os.environ.get('CAPTURE_TOUCH_TYPE'):
            root.update()
            from PIL import ImageGrab
            x,y=root.winfo_rootx(),root.winfo_rooty()
            ImageGrab.grab(bbox=(x,y,x+root.winfo_width(),y+root.winfo_height())).save(
                str(HERE/'TOUCH_TYPE_PREVIEW.png'))
        scene.act('tab_home')
        # run a tighter layout and ensure the TYPE tab exists and is clickable
        scene.resized(760,550)
        root.update()
        assert 'tab_touch_type' in scene.nav_tabs
        ht=next(h for h in scene.hot if h[4]=='tab_touch_type')
        assert scene.hit((ht[0]+ht[2])/2,(ht[1]+ht[3])/2)[4]=='tab_touch_type'
        scene.act('tab_touch_type')
        root.update()
        assert scene.touch and panel.winfo_ismapped()
        assert panel.typing_entry.winfo_exists()
        if os.environ.get('CAPTURE_TOUCH_TYPE'):
            root.update()
            from PIL import ImageGrab
            x,y=root.winfo_rootx(),root.winfo_rooty()
            ImageGrab.grab(bbox=(x,y,x+root.winfo_width(),y+root.winfo_height())).save(
                str(HERE/'TOUCH_TYPE_SMALL.png'))
        print('TOUCH TYPE UI: overlay, 6 tabs, pause, restore, modes, resize PASS')
    finally:
        app.quit()

if __name__=='__main__':
    engine_tests()
    gui_tests()
