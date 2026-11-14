"""Embedded read-only signals GUI entry, no network requests or generated observations."""
import sys,tkinter as tk,tempfile
from pathlib import Path
from unittest.mock import patch
APP=Path(__file__).resolve().parents[1]/'Runtime'/'Marble_Oracle_App'
sys.path.insert(0,str(APP))
from oracle_augurspex_tab import AugurspexPanel
from Augurspex.augurspex.providers import MarketRouter

def walk(w):
    yield w
    for c in w.winfo_children():yield from walk(c)

with tempfile.TemporaryDirectory() as d:
    root=tk.Tk();root.geometry('1050x720');root.update()
    panel=AugurspexPanel(root,lambda:None,home=d,router=MarketRouter(),offline=True)
    panel.pack(fill='both',expand=True);root.update()
    try:
        buttons=[w for w in walk(panel) if isinstance(w,tk.Button)]
        assert any('SIGNALS' in w.cget('text') for w in buttons)
        market=panel._space_plan()[0][0]
        data={'source':'MOCK · NOT LIVE','currency':'USD','candles':[
            {'time':f'2026-10-{i:02d}T00:00:00+00:00','close':float(i)}
            for i in range(1,29)]}
        panel._data[(market,panel.settings['interval'])]=data
        with patch('oracle_augurspex_tab.messagebox.showinfo') as alert:
            panel._show_market_signals()
        assert alert.call_count==1
        assert market in alert.call_args.args[1]
        assert '20-observation mean' in alert.call_args.args[1]
        assert 'MOCK · NOT LIVE' in alert.call_args.args[1]
        panel._change_layout('9');root.update()
        assert panel.settings['layout']==9
        assert panel.chart_canvas.winfo_width()>100
        print('PDF SOURCES + SIGNALS GUI: PASS')
    finally:
        panel.shutdown()
        root.destroy()
