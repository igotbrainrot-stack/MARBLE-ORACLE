"""Verify stock-data repair controls are usable and secrets remain ephemeral."""
from __future__ import annotations
import os,sys,tkinter as tk,tempfile
from pathlib import Path
from unittest.mock import patch
APP=Path(__file__).resolve().parents[1]/'Runtime/Marble_Oracle_App'
sys.path.insert(0,str(APP))
from oracle_augurspex_tab import AugurspexPanel
from Augurspex.augurspex.providers import MarketRouter, local_stock_path
from Augurspex.augurspex.core import app_folder


def _walk(w):
    yield w
    for child in w.winfo_children():
        yield from _walk(child)


def test_keys_and_csv():
    with tempfile.TemporaryDirectory() as d:
        root=tk.Tk();root.geometry('1300x850');root.update()
        router=MarketRouter(cache_dir=Path(d)/'cache')
        tab=AugurspexPanel(root,lambda:None,home=d,router=router,offline=True)
        tab.pack(expand=True,fill='both');root.update()
        try:
            assert router.import_dir == app_folder(Path(d))/'imported-history'
            assert 'unofficial_sources' in tab.settings
            tab._manage_watchlist();root.update()
            manage=[w for w in _walk(root) if isinstance(w,tk.Toplevel)]
            assert manage
            buttons=[w.cget('text') for w in _walk(manage[0]) if isinstance(w,tk.Button)]
            assert 'CONNECT API KEY' in buttons and 'IMPORT STOCK CSV' in buttons
            manage[0].destroy();root.update()
            tab._stock_key_setup();root.update()
            dialog=[w for w in _walk(root) if isinstance(w,tk.Toplevel)][0]
            entries=[w for w in _walk(dialog) if isinstance(w,tk.Entry)]
            assert len(entries)==4
            testkey='TEST_SESSION_0491_NOT_REAL'
            entries[0].insert(0,testkey)
            btn=next(w for w in _walk(dialog) if isinstance(w,tk.Button) and w.cget('text')=='APPLY + REFRESH')
            btn.invoke();root.update()
            assert os.environ.get('AUGURSPEX_TWELVE_DATA_KEY')==testkey
            settings=app_folder(Path(d))/'settings.json'
            assert not settings.exists() or testkey not in settings.read_text()
            sym='AAPL';tab.settings['symbols'][0]=sym
            tab._refresh_charts();root.update()
            csv=Path(d)/'prices.csv'
            csv.write_text('symbol,Date,Open,High,Low,Close\nAAPL,2026-11-10,10,12,9,11\nAAPL,2026-11-11,11,14,10,13\n')
            with patch('oracle_augurspex_tab.filedialog.askopenfilename',return_value=str(csv)):
                tab._import_stock_csv()
            dest=local_stock_path(router.import_dir,'AAPL')
            assert dest and dest.exists()
            assert router.fetch('AAPL','D',getter=lambda url:(_ for _ in ()).throw(AssertionError('network!')))['cache']=='local'
            assert 'TEST_SESSION' not in dest.read_text()
        finally:
            os.environ.pop('AUGURSPEX_TWELVE_DATA_KEY',None)
            tab.shutdown() if hasattr(tab,'shutdown') else None
            root.destroy()

if __name__=='__main__':
    test_keys_and_csv();print('STOCK FEED CONTROLS: PASS')
