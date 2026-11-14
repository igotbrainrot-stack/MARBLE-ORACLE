"""0.4.8.4: tested sourced-only market visibility and spacious graph layout.

Uses deterministic fixture providers only. No market results are fabricated by
production code, and failed requests do not erase a saved personal watchlist.
"""
import json
import sys
import tempfile
import time
import tkinter as tk
from pathlib import Path
APP=Path(__file__).resolve().parents[1]/'Runtime'/'Marble_Oracle_App'
sys.path.insert(0,str(APP))
from oracle_augurspex_tab import EmbeddedAugurspex

class TestRouter:
    def __init__(self):self.fail={'AAPL'};self.calls=[]
    def _routes(self,symbol,source,period='D'):
        return [] if symbol=='COH.AX' else ['test-only']
    def fetch(self,symbol,period='D'):
        self.calls.append((symbol,period))
        if symbol in self.fail:raise ValueError('PROVIDER TIMEOUT OR QUOTA')
        return {'source':'TEST FIXTURE, NOT LIVE','currency':'USD',
                'latest_observation':'2026-11-12',
                'candles':[{'time':'2026-11-10','open':100,'high':104,'low':99,'close':102},
                           {'time':'2026-11-11','open':102,'high':105,'low':100,'close':103}]}

def pump(root, predicate, limit=5):
    until=time.monotonic()+limit
    while time.monotonic()<until:
        root.update()
        if predicate():return
        time.sleep(.025)
    raise AssertionError('Timed out during fixture verification')

def test_sources_and_spacious_layout():
    with tempfile.TemporaryDirectory() as td:
        cfg=Path(td)/'.config'/'augurspex'
        cfg.mkdir(parents=True)
        original=[{'symbol':x,'name':x} for x in ('BTC-USD','AAPL','COH.AX','ETH-USD')]
        (cfg/'watchlist.json').write_text(json.dumps({'markets':original}))
        (cfg/'settings.json').write_text(json.dumps({'layout':4,'symbols':['BTC-USD','AAPL','COH.AX','ETH-USD','','','','',''],'style':'2'}))
        root=tk.Tk();root.geometry('1500x860');root.update()
        canvas=tk.Canvas(root,width=1470,height=820);canvas.pack(fill='both',expand=True)
        provider=TestRouter();tab=EmbeddedAugurspex(canvas,lambda:None,home=td,router=provider)
        tab.layout((0,0,1450,810));root.update()
        p=tab.frame
        # Popular-markets layout starts with the complete list visible; enable
        # sourced-only explicitly to exercise the historical filtering feature.
        if not p.sourced_only:p._toggle_sourced()
        assert p.sourced_only
        assert p.watch.size()==0  # no assumed initial market availability
        pump(root,lambda:p._market_verified('BTC-USD') and p._market_verified('ETH-USD') and ('AAPL','D') in p._errors)
        root.update()
        assert [row['symbol'] for row in p.rows]==['BTC-USD','ETH-USD'],p.rows
        assert [p.settings['symbols'][i] for i in p._chart_indices()]==['BTC-USD','ETH-USD']
        assert p._chart_columns<=2
        for i in p._chart_indices():
            card=p.cards[i]
            assert card.winfo_ismapped()
            # 0.4.8.5: card size follows the area (4 spaces -> 2x2 grid).
            assert card.winfo_height()>=280,card.winfo_height()
            assert card.canvas.winfo_width()>=260,card.canvas.winfo_width()
        # 0.4.8.5: CHARTS=4 always shows four spaces. With no other watchlist
        # market to auto-fill from, AAPL/COH.AX show their own status (no chart).
        assert p.cards[1].winfo_ismapped() and p.cards[2].winfo_ismapped()
        assert not p.cards[1].canvas.find_withtag('price-mark') and not p.cards[2].canvas.find_withtag('price-mark')
        assert len(json.loads((cfg/'watchlist.json').read_text())['markets'])==4
        p._toggle_sourced();root.update()
        assert p.watch.size()==4
        assert sum(card.winfo_ismapped() for card in p.cards)==4  # SHOW ALL: every space is a card
        provider.fail.clear()
        p._force_refresh();pump(root,lambda:p._market_verified('AAPL'))
        assert p.cards[1].result is not None
        p._toggle_sourced();root.update()
        assert 'AAPL' in [row['symbol'] for row in p.rows]
        assert p.cards[1].winfo_ismapped()
        assert tab.shutdown()
        root.destroy()

if __name__=='__main__':
    test_sources_and_spacious_layout()
    print('SOURCED-ONLY VISIBILITY + LARGE CHARTS + RESTORE: PASS')
