"""Native AUGURSPEX suite tab: no browser, shared watchlist, palette and persistence.

Run: xvfb-run -a python3 Tests/test_augurspex_native_tab.py
"""
import sys, tempfile, time, tkinter as tk
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'Runtime'/'Marble_Oracle_App'))
from oracle_augurspex_tab import EmbeddedAugurspex, chart_geometry, plot_points
from Augurspex.augurspex.core import read_settings, merge_watchlists
from marble_oracle import parse, WindowApp

class FakeRouter:
    def __init__(self):self.calls=[]
    def fetch(self,symbol,period):
        self.calls.append((symbol,period))
        return {'source':'TEST / NOT LIVE','currency':'USD','interval':period,'cache':'network',
                'latest_observation':'2026-11-10',
                'candles':[{'time':str(i),'open':10+i,'high':12+i,'low':9+i,'close':11+i} for i in range(20)]}

def pump(root,check,limit=2):
    until=time.monotonic()+limit
    while time.monotonic()<until:
        root.update()
        if check():return
        time.sleep(.03)
    raise AssertionError('UI did not reach expected state')

def test_native_panel():
    assert chart_geometry(6)==(2,3)
    pts,bounds=plot_points([{'open':5,'high':7,'low':4,'close':6}],500,200)
    assert len(pts)==1 and bounds==(4.0,7.0)
    with tempfile.TemporaryDirectory() as td:
        root=tk.Tk();root.geometry('1170x750');root.update()
        can=tk.Canvas(root,width=1150,height=710);can.pack(fill='both',expand=True)
        router=FakeRouter()
        tab=EmbeddedAugurspex(can,on_home=lambda:None,home=td,router=router)
        tab.layout((0,0,1150,700));root.update()
        panel=tab.frame
        assert panel._visible and panel.watch.size()<=len(panel.watchlist)
        # Opt into review mode to verify watchlist editing; default visible
        # market list is restricted to charts with observed history.
        panel._toggle_sourced();root.update()
        assert panel.watch.size()>=20
        assert panel.settings['workspace']=='Overview'
        assert len(panel.cards)==4
        pump(root,lambda:panel.cards[0].result is not None)
        assert router.calls, 'native chart must load backend provider history'
        assert panel.p['accent']
        panel._change_layout('6');root.update()
        assert len(panel.cards)==6
        panel.style_var.set('LINE');panel._change_style('LINE');root.update()
        assert panel.cards[0].style=='2'
        panel.active=2;panel.settings['symbols'][2]='RMD.AX';panel._save();panel._refresh_charts()
        assert read_settings(Path(td))['symbols'][2]=='RMD.AX'
        panel._change_workspace('Healthcare');root.update()
        panel.settings['symbols'][0]='COH.AX';panel._save()
        panel._change_workspace('Overview')
        assert panel.settings['symbols'][2]=='RMD.AX'
        panel.symbol_input.set('NASDAQ:AMD');panel._add_symbol();root.update()
        assert any(r['symbol']=='NASDAQ:AMD' for r in panel.watchlist)
        tab.clear();root.update();assert not panel._visible
        tab.layout((0,0,1150,700));root.update();assert panel._visible
        assert tab.shutdown() is True
        root.destroy()

def test_scene_native_entry():
    opts=vars(parse(['--selftest','--no-network','--no-markets','--no-bezel','--os-frame']))
    app=WindowApp(opts);scene=app.scene;root=app.root
    root.update();scene.resized(1216,848);root.update()
    import oracle_augurspex_bridge
    original=oracle_augurspex_bridge.launch
    def fail():raise AssertionError('old browser launcher used')
    oracle_augurspex_bridge.launch=fail
    try:
        scene.act('tab_augurspex');root.update()
        assert scene._which_overlay()=='aug'
        assert scene.aug is not None and scene.aug.frame.winfo_exists()
        assert not scene.aug.frame._visible is False
        assert scene.c.type(scene.aug.window)=='window'
        old=scene.aug
        scene.act('tab_home');root.update()
        assert scene._which_overlay() is None and old.frame.winfo_exists()
        scene.act('tab_augurspex');root.update()
        assert scene.aug is old, 'tab state should survive switching workspaces'
        scene.act('view');root.update()
        assert scene._which_overlay()=='aug', 'GRADE must not discard the AUGURSPEX tab'
        assert scene.aug.frame.p['accent']==scene.th['cyan'], 'AUGURSPEX should follow GRADE colours'
        assert scene.c.type(scene.aug.window)=='window'
        scene.on_key(type('E',(),{'keysym':'Escape','char':''})());root.update()
        assert scene._which_overlay() is None
    finally:
        oracle_augurspex_bridge.launch=original
        app.quit()

if __name__=='__main__':
    test_native_panel();print('NATIVE PANEL + SETTINGS OK')
    test_scene_native_entry();print('NATIVE SUITE NAVIGATION + NO BROWSER OK')
