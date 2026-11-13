"""Regression for screenshot 2026-11-13: nine cards used to have 1x1 canvases.
Run: xvfb-run -a python3 Application/Tests/test_augurspex_scrollable_0483.py
"""
import sys
import tempfile
import tkinter as tk
from pathlib import Path
from datetime import datetime, timedelta, timezone

APP=Path(__file__).resolve().parents[1]/'Runtime'/'Marble_Oracle_App'
sys.path.insert(0,str(APP))
from oracle_augurspex_tab import EmbeddedAugurspex
from marble_oracle import WindowApp, parse


def verify_cards(tab,root):
    panel=tab.frame
    panel._change_layout('9');root.update()
    assert len(panel.cards)==9
    assert panel._chart_columns>=1
    assert panel.chart_scroll.winfo_ismapped(), 'Scroll bar must be present'
    assert panel.chart_canvas.winfo_width()>100
    assert panel.chart_canvas.winfo_height()>90
    assert panel.grid_frame.winfo_height()>panel.chart_canvas.winfo_height(), 'Small viewport must scroll'
    for card in panel.cards:
        assert card.winfo_height()>=250, (card.winfo_height(),card.index)
        assert card.canvas.winfo_width()>170,(card.index,card.canvas.winfo_width())
        assert card.canvas.winfo_height()>120,(card.index,card.canvas.winfo_height())
        assert card.info.winfo_ismapped()
    before=panel.chart_canvas.yview()
    panel.chart_canvas.yview_scroll(5,'units');root.update()
    after=panel.chart_canvas.yview()
    assert after[0]>before[0],(before,after)
    # Persistence of a whole 9-slot list, even if not all charts are on screen.
    assert len(panel.settings['symbols'])==9
    return panel


def test_embedded_small_viewport():
    with tempfile.TemporaryDirectory() as temp:
        root=tk.Tk();root.geometry('950x620');root.update()
        cv=tk.Canvas(root, width=950,height=580);cv.pack(fill='both',expand=True)
        tab=EmbeddedAugurspex(cv,on_home=lambda:None,home=temp,offline=True)
        tab.layout((0,0,930,570));root.update()
        panel=verify_cards(tab,root)
        # Inject *synthetic* provider-format history solely for Tk rendering.
        t=datetime(2026,9,1,tzinfo=timezone.utc)
        data={'source':'TEST ONLY','currency':'USD','latest_observation':'2026-11-10',
              'candles':[{'time':(t+timedelta(days=i)).isoformat(),'open':200+i,
                          'high':204+i,'low':198+i,'close':202+i} for i in range(90)]}
        panel.cards[0].display('NVDA','NVIDIA',data,None,False,'2',True)
        root.update()
        can=panel.cards[0].canvas
        assert can.find_withtag('price-line') and can.find_withtag('chart-grid')
        # Date tick labels fit vertically; tiny canvases previously hid all labels.
        height=can.winfo_height()
        for item in can.find_all():
            if can.type(item)=='text':
                bbox=can.bbox(item)
                assert bbox is not None and bbox[1]>=-7 and bbox[3]<=height+7,(can.itemcget(item,'text'),bbox,height)
        assert tab.shutdown()
        root.destroy()


def test_actual_suite_aperture():
    opt=vars(parse(['--selftest','--no-network','--no-markets','--no-bezel','--os-frame']))
    app=WindowApp(opt)
    try:
        app.root.update();app.scene.resized(1216,848);app.root.update()
        app.scene.act('tab_augurspex');app.root.update()
        assert app.scene.aug is not None
        panel=verify_cards(app.scene.aug,app.root)
        assert panel.rail_shell.winfo_width()>=285
    finally:app.quit()

if __name__=='__main__':
    test_embedded_small_viewport();print('SMALL APERTURE SCROLL + AXES: PASS')
    test_actual_suite_aperture();print('SUITE 9-CHART SCROLL: PASS')
