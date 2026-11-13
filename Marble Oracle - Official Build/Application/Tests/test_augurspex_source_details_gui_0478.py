"""Verify native in-suite diagnostics remain accessible without a browser.
Run: xvfb-run -a python3 Tests/test_augurspex_source_details_gui_0478.py
"""
import os
import sys
import tempfile
import time
import tkinter as tk
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Runtime'/'Marble_Oracle_App'))
from oracle_augurspex_tab import AugurspexPanel


def test_native_source_details_and_texture():
    with tempfile.TemporaryDirectory() as td:
        root=tk.Tk()
        root.geometry('1250x740')
        p=AugurspexPanel(root,on_home=lambda:None,home=td,offline=True)
        p.pack(fill='both',expand=True)
        try:
            root.update()
            assert p.rail.cget('style').startswith('MarbleOgg.')
            assert p.work.cget('style').startswith('MarbleOgg.')
            texts=[]
            def walk(node):
                for child in node.winfo_children():
                    if isinstance(child,tk.Button):texts.append(child.cget('text'))
                    walk(child)
            walk(p)
            assert 'SOURCE DETAILS' in texts, texts
            p.settings['symbols'][p.active]='NVDA'
            p.offline=False
            key=('NVDA',p.settings['interval'])
            p._errors[key]='yahoo: HTTP 429; provider refused | nasdaq: no history | stooq: cooling down'
            p._failed_at[key]=time.monotonic()-100
            text=p._source_details_text()
            assert 'NVDA' in text
            assert 'yahoo' in text and 'nasdaq' in text
            assert 'Automatic retry' in text
            assert 'seconds' in text
            p._data[key]={'source':'Test historical source','latest_observation':'2026-11-11',
                           'cache':'stale','currency':'USD','note':'Not a live quote',
                           'candles':[{'time':'2026-11-11','open':1,'high':2,'low':1,'close':2}],
                           'provider_attempts':['yahoo: limited']}
            text=p._source_details_text()
            assert 'Cache: stale' in text and 'Not a live quote' in text
            with patch('oracle_augurspex_tab.messagebox.showinfo') as info:
                p._show_source_details()
                assert info.call_count==1
        finally:
            p.shutdown()
            root.destroy()


if __name__=='__main__':
    test_native_source_details_and_texture()
    print('AUGURSPEX NATIVE SOURCE DETAILS: PASS')
