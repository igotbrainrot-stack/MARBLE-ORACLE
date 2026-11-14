"""Native Signals button must remain navigable at the suite's small CRT sizes."""
import sys,tempfile,tkinter as tk
from pathlib import Path
APP=Path(__file__).resolve().parents[1]/'Runtime'/'Marble_Oracle_App';sys.path.insert(0,str(APP))
from oracle_augurspex_tab import AugurspexPanel
from Augurspex.augurspex.providers import MarketRouter

def walk(w):
    yield w
    for c in w.winfo_children():yield from walk(c)

with tempfile.TemporaryDirectory() as d:
    root=tk.Tk()
    panel=AugurspexPanel(root,lambda:None,home=d,router=MarketRouter(),offline=True)
    panel.pack(fill='both',expand=True)
    try:
        for w,h in ((900,580),(1000,650),(1400,870)):
            root.geometry(f'{w}x{h}');root.update()
            buttons=[c for c in walk(panel) if isinstance(c,tk.Button) and 'SIGNALS' in c.cget('text')]
            assert len(buttons)==1
            b=buttons[0]
            assert b.winfo_ismapped() and b.winfo_width()>=75,(w,h,b.winfo_width())
            assert b.winfo_rootx()>=root.winfo_rootx()
            assert b.winfo_rootx()+b.winfo_width()<=root.winfo_rootx()+root.winfo_width()
        print('SIGNALS RESPONSIVE: PASS')
    finally:
        panel.shutdown();root.destroy()
