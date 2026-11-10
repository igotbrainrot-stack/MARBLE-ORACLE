from pathlib import Path
import sys, os
sys.path.insert(0, str(Path(__file__).resolve().parent.parent/'Runtime'/'Marble_Oracle_App'))
from marble_oracle import WindowApp
from PIL import ImageGrab
for bezel in (False, True):
    opts=dict(theme=None,layout='CLASSIC',fps=30,frameless=False,crt_v2=bezel,
              no_dicekey=False,no_markets=True,no_network=True,crt=bezel,wire=None,
              bezel=bezel,osframe=not bezel,flat=False,retro=False,
              look='OLED',no_pixel_barrel=True,no_audio_scope=True,selftest=True)
    app = WindowApp(opts)
    root=app.root; root.update()
    sc=app.scene
    sc.resized(app.canvas.winfo_width(), app.canvas.winfo_height())
    root.update()
    assert len(sc.nav_tabs)==5
    for h in [h for h in sc.hot if h[4] in ('tab_home','tab_passphrase','tab_oggcultist','tab_touch_type')]:
        assert sc.hit((h[0]+h[2])/2,(h[1]+h[3])/2)[4]==h[4]
    name = 'BEZEL' if bezel else 'DEFAULT'
    root.update()
    x,y=root.winfo_rootx(),root.winfo_rooty()
    ImageGrab.grab(bbox=(x,y,x+root.winfo_width(),y+root.winfo_height())).save(
        str(Path(__file__).parent/f'TAB_LAYOUT_{name}.png'))
    sc.act('tab_oggcultist'); root.update()
    assert sc.ogg and sc.ogg.frame.process is None
    ImageGrab.grab(bbox=(x,y,x+root.winfo_width(),y+root.winfo_height())).save(
        str(Path(__file__).parent/f'TAB_OGGCULTIST_{name}.png'))
    sc.act('tab_home'); sc.act('tab_passphrase'); root.update()
    assert sc.dk
    sc.dk.frame.home_button.invoke(); root.update()
    assert not sc.dk
    app.quit()
    print('MODE PASS',name)
