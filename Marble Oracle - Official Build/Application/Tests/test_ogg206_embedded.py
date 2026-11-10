"""Check Oggcultist 2.0.6 is a functioning in-suite tab, not a launcher.
Run: xvfb-run -a python3 test_ogg206_embedded.py
"""
from pathlib import Path
import sys, time
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'Runtime'/'Marble_Oracle_App'))
from marble_oracle import parse, WindowApp

opts=vars(parse(['--selftest','--no-network','--no-markets','--no-bezel','--os-frame']))
suite=WindowApp(opts)
root,scene = suite.root,suite.scene
root.update()
scene.resized(1216,848);root.update()
scene.act('tab_oggcultist');root.update()
assert scene.ogg is not None
panel=scene.ogg.frame
assert panel.ogg_app is not None, panel.status.get()
ogg=panel.ogg_app
assert ogg._embedded
assert len(ogg.pages)==7, list(ogg.pages)
assert sorted(ogg.pages)==sorted(['library','artists','albums','playlists','converter','art','settings'])
assert ogg.winfo_ismapped(), 'Oggcultist content not visible'
assert ogg.winfo_width()>600 and ogg.winfo_height()>350, (ogg.winfo_width(),ogg.winfo_height())
for key in ['artists','albums','playlists','converter','art','settings','library']:
    ogg.show_page(key)
    root.update()
    assert ogg.current_page==key, key
assert ogg.converter is ogg.pages['converter']
first=ogg
scene.act('tab_home');root.update()
assert scene.ogg is None
assert not first.winfo_ismapped(), 'Oggcultist should hide on HOME'
assert not first.closed, 'Oggcultist must persist while on HOME'
scene.act('tab_passphrase');root.update()
assert scene.dk is not None
scene.act('tab_oggcultist');root.update()
assert scene.ogg.frame.ogg_app is first, 'Switching tabs recreated Oggcultist'
assert first.winfo_ismapped(), 'Oggcultist not visible after returning'
assert first.current_page == 'library'
scene.act('tab_home');root.update()
print('OGGCULTIST 2.0.6 EMBEDDED: seven pages, lifecycle, HOME and PASS tab OK')
suite.quit()
