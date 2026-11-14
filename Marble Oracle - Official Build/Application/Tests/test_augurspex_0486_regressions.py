"""0.4.8.6 phase-1/phase-2 fixes: source identity, freshness, chart, CSV.

All quote values below are artificial test fixtures, never live market data.
Run: xvfb-run -a python3 Application/Tests/test_augurspex_0486_regressions.py
"""
from __future__ import annotations
import csv
import json
import sys
import tempfile
import time
import tkinter as tk
from datetime import datetime, timedelta, timezone
from pathlib import Path

APP=Path(__file__).resolve().parents[1]/'Runtime'/'Marble_Oracle_App'
sys.path.insert(0,str(APP))
from oracle_augurspex_tab import EmbeddedAugurspex, PriceChart, history_health, chart_grid_plan, csv_safe
from Augurspex.augurspex.core import sanitize_settings
import oracle_augurspex_tab


def bars(days_ago=1):
    today=datetime.now(timezone.utc).date()-timedelta(days=days_ago)
    return [{'time':(today-timedelta(days=9-i)).isoformat(), 'open':float(100+i),
             'high':float(104+i),'low':float(99+i),'close':float(102+i), 'volume':1234} for i in range(10)]


class FakeRouter:
    def _routes(self,sym,source,period='D'):
        return ['fixture']
    def fetch(self,sym,period='D'):
        if sym=='BTC-USD':
            raise ValueError('FIXTURE: no data')
        return {'source':'FIXTURE NOT LIVE','currency':'USD','interval':period,
                'latest_observation':bars()[-1]['time'],'candles':bars()}


def pump(root,n=.4):
    until=time.monotonic()+n
    while time.monotonic()<until:
        root.update()
        time.sleep(.02)


def test_pure():
    assert csv_safe('=HYPERLINK("https://example.com")').startswith("'=HYPERLINK")
    assert csv_safe('STOOQ')=='STOOQ'
    assert history_health({'candles':bars(days_ago=1)},'AAPL','D')[0]=='recent'
    assert history_health({'candles':bars(days_ago=5)},'AAPL','D')[0]=='recent'  # weekend/holiday allowance
    assert history_health({'candles':bars(days_ago=50)},'AAPL','D')[0]=='stale'
    assert history_health({'candles':bars(days_ago=50)},'AAPL','M')[0]=='stale'
    assert history_health({'candles':bars(days_ago=40)},'AAPL','M')[0]=='recent'
    assert history_health({'candles':bars(days_ago=5)},'BTC-USD','D')[0]=='stale'
    bad={'candles':bars(days_ago=-40)}
    assert history_health(bad,'AAPL','D')[0]=='future'
    assert history_health({'candles':[{'open':1,'high':2,'low':1,'close':2}]},'AAPL','D')[0]=='undated'
    assert chart_grid_plan(1,555,240)['card_h']>chart_grid_plan(4,555,240)['card_h']
    settings=sanitize_settings({'style':'1','slot_styles':['1','2'], 'line_default_0485':False,
                  'workspaces':{'Overview':{'style':'1','slot_styles':['1','2']}}})
    assert settings['style']=='1' and settings['slot_styles'][:2]==['1','2'],settings
    assert settings['workspaces']['Overview']['style']=='1'
    assert sanitize_settings({})['style']=='2'


def test_gui():
    with tempfile.TemporaryDirectory() as home:
        cfg=Path(home)/'.config'/'augurspex';cfg.mkdir(parents=True)
        (cfg/'watchlist.json').write_text(json.dumps({'markets':[
            {'symbol':'BTC-USD','name':'Bitcoin'},{'symbol':'AAPL','name':'Apple Inc.'}]}))
        (cfg/'settings.json').write_text(json.dumps({'layout':1,'style':'2',
            'symbols':['BTC-USD','','','','','','','','']}))
        root=tk.Tk();root.geometry('1350x830+0+0');root.update()
        can=tk.Canvas(root,width=1340,height=810,highlightthickness=0);can.pack(fill='both',expand=True)
        tab=EmbeddedAugurspex(can,lambda:None,home=home,router=FakeRouter())
        tab.layout((0,0,1300,790));root.update()
        p=tab.frame
        p._data[('AAPL','D')]={'source':'FIXTURE NOT LIVE','currency':'USD','interval':'D',
                              'latest_observation':bars()[-1]['time'],'candles':bars()}
        p.sourced_only=True
        p._refresh_charts();pump(root,.4)
        assert p._space_plan()[0]==('AAPL',True),p._space_plan()
        assert 'Market: AAPL' in p._source_details_text()
        assert 'Saved target for this slot: BTC-USD' in p._source_details_text()
        card=p.cards[0]
        assert card.canvas.winfo_width()>300
        # No in-canvas note can overlap dates; source remains in card footer.
        texts=[card.canvas.itemcget(item,'text') for item in card.canvas.find_all()
               if card.canvas.type(item)=='text']
        assert not any('observations' in s.lower() for s in texts),texts
        card._on_chart_motion(type('Evt',(),{'x':card.canvas.winfo_width()//2})())
        assert 'CLOSE' in card._hover_text
        assert card.canvas.find_withtag('cursor-guide')
        card._on_chart_leave()
        assert not card.canvas.find_withtag('cursor-guide')
        target=Path(home)/'actual_chart.csv'
        original=oracle_augurspex_tab.filedialog.asksaveasfilename
        oracle_augurspex_tab.filedialog.asksaveasfilename=lambda **_k:str(target)
        try:p._export_chart_csv()
        finally:oracle_augurspex_tab.filedialog.asksaveasfilename=original
        with target.open(newline='',encoding='utf8') as file:
            rows=list(csv.DictReader(file))
        assert len(rows)==10 and all(r['symbol']=='AAPL' for r in rows)
        assert rows[-1]['close']==str(bars()[-1]['close'])
        # Deliberately stale cached history must NOT replace the saved market as verified.
        p._data[('AAPL','D')]={'source':'OLD FIXTURE','currency':'USD','interval':'D','cache':'stale',
                               'latest_observation':'2021-08-02','candles':bars(days_ago=1800)}
        assert not p._market_verified('AAPL')
        assert p._market_health('AAPL')[0]=='stale'
        p._refresh_charts();pump(root,.1)
        assert p._space_plan()[0]==('BTC-USD',False)
        assert tab.shutdown();root.destroy()

if __name__=='__main__':
    test_pure();print('PURE/SETTINGS/RECENCY CHECKS PASS',flush=True)
    test_gui();print('NATIVE/EXPORT/CURSOR/SOURCE CHECKS PASS',flush=True)
