"""Focused checks for dated/charted provider history without live network calls.

Run: xvfb-run -a python3 Tests/test_augurspex_chart_axes_and_history.py
"""
from __future__ import annotations
import json
import os
from unittest.mock import patch
import sys
import tkinter as tk
from datetime import datetime, timedelta, timezone
from pathlib import Path

APP=Path(__file__).resolve().parents[1]/'Runtime'/'Marble_Oracle_App'
sys.path.insert(0,str(APP))
from oracle_augurspex_tab import (CHART_PAD_B,CHART_PAD_R,PriceChart,
                                  chart_date_ticks,plot_points)
from Augurspex.augurspex.providers import read_yahoo,MarketRouter,ProviderError


def history(n=120,step=1):
    start=datetime(2025,11,1,tzinfo=timezone.utc)
    return [dict(time=(start+timedelta(days=i*step)).isoformat(),
                 open=100+i, high=103+i,low=99+i,close=101+i)
            for i in range(n)]


def test_axes_use_actual_dates_and_prices():
    data=history()
    pts,bounds=plot_points(data,500,220)
    assert len(pts)==120
    assert min(x[0] for x in pts)>0 and max(x[0] for x in pts)<500-CHART_PAD_R
    assert all(15<=y<=220-CHART_PAD_B for pt in pts for y in pt[1:])
    ticks=chart_date_ticks(data,500)
    assert len(ticks)>=3 and all("'" in label for _,label in ticks)
    assert ticks[0][0]<ticks[-1][0]
    year_ticks=chart_date_ticks(history(8,365),500)
    assert len(year_ticks)>=3 and all(label.isdigit() and len(label)==4 for _,label in year_ticks)
    short_ticks=chart_date_ticks(history(20),500)
    assert all('NOV' in label for _,label in short_ticks)


def test_yahoo_close_only_is_real_line_history():
    symbol='COH.AX'
    payload={'chart':{'error':None,'result':[{
        'meta':{'symbol':symbol,'currency':'AUD'},
        'timestamp':[1794182400,1794268800,1794355200],
        'indicators':{'quote':[{'open':[100,None,None],
            'high':[102,None,None],'low':[99,None,None],
            'close':[101,103,105], 'volume':[123,None,None]}]}
    }]}}
    data=read_yahoo(symbol,'D',getter=lambda url:json.dumps(payload).encode())
    assert len(data['candles'])==3
    assert data['close_only_observations']==2
    assert [bar['close'] for bar in data['candles']]==[101,103,105]
    assert data['candles'][2]['close_only'] is True
    root=tk.Tk();root.geometry('580x320')
    try:
        chart=PriceChart(root,dict(bg='#160e0b',panel='#261f1b',inset='#16110f',
            rail='#130f0d',border='#483a32',control='#392a22',active='#4a2c18',
            accent='#ff9725',ink='#fff0dc',muted='#d6bcb0',weak='#b29a8b',
            green='#94c77e',red='#e0706a'),0,lambda _:None)
        chart.pack(fill='both',expand=True)
        root.update()
        chart.display(symbol,symbol,data,None,False,'1',True)
        root.update()
        texts=[chart.canvas.itemcget(i,'text') for i in chart.canvas.find_all() if chart.canvas.type(i)=='text']
        assert any('CLOSE-ONLY HISTORY' in item for item in texts)
        assert any('NOV' in item for item in texts),texts
        lines=[i for i in chart.canvas.find_all() if chart.canvas.type(i)=='line' and float(chart.canvas.itemcget(i,'width'))>=3]
        assert lines,'closing-only bars must be connected by a visibly thick line'
    finally:
        root.destroy()


@patch.dict(os.environ,{"AUGURSPEX_ALLOW_UNOFFICIAL_SOURCES":"1"})
def test_all_sources_unavailable_does_not_fake_history():
    r=MarketRouter(clock=lambda:100.0)
    def getter(url):
        if 'yahoo.com' in url:raise ProviderError('HTTP 429; provider refused the request')
        if 'stooq.com' in url:return b'N/D'
        raise AssertionError(url)
    try:r.fetch('COH.AX','D',getter=getter)
    except ProviderError as exc:
        assert 'yahoo' in str(exc) and 'stooq' in str(exc)
    else:raise AssertionError('Missing data must not be represented as success')
    assert r.blocked['yahoo']>100


if __name__=='__main__':
    test_axes_use_actual_dates_and_prices();print('CHART AXES / DATES: PASS')
    test_yahoo_close_only_is_real_line_history();print('CLOSE-ONLY PROVIDER HISTORY: PASS')
    test_all_sources_unavailable_does_not_fake_history();print('FAILURE / COOLDOWN: PASS')
