"""Regression for reported AUGURSPEX 0.4.8.4 usability defects.

Deterministic test observations only; no external market requests or fake
market values introduced into production code.
Run: xvfb-run -a python3 Application/Tests/test_augurspex_chart_repair_0485.py
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import sys
import tempfile
import tkinter as tk

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Runtime' / 'Marble_Oracle_App'))
from oracle_augurspex_tab import EmbeddedAugurspex, chart_grid_plan

SYMBOLS=('AAPL','MSFT','NVDA','BTC-USD','ETH-USD','SOL-USD','RMD.AX','COH.AX','XRP-USD')


def sample(symbol):
    day=datetime(2026,8,1,tzinfo=timezone.utc)
    candles=[]
    for i in range(110):
        val=50+i*0.5
        candles.append({'time':(day+timedelta(days=i)).isoformat(),
                        'open':val,'high':val+2,'low':val-2,'close':val+1})
    return {'source':'TEST OBSERVATIONS / NOT LIVE', 'currency':'USD',
            'latest_observation':candles[-1]['time'], 'candles':candles}


def no_overlap(box1,box2):
    if box1 is None or box2 is None:return True
    return box1[2]<=box2[0] or box2[2]<=box1[0] or box1[3]<=box2[1] or box2[3]<=box1[1]


def validate_axis(card):
    c=card.canvas
    c.update_idletasks()
    w,h=c.winfo_width(),c.winfo_height()
    assert w>=260 and h>=180,(w,h)
    date_ids=c.find_withtag('date-axis-label')
    prices=c.find_withtag('price-axis-label')
    assert len(date_ids)>=2 and len(prices)>=3,(len(date_ids),len(prices))
    for item in date_ids+prices:
        bb=c.bbox(item)
        assert bb and bb[0]>=-3 and bb[1]>=-3 and bb[2]<=w+3 and bb[3]<=h+3,(
            'clipped',item,c.itemcget(item,'text'),bb,w,h)
    for index,a in enumerate(date_ids):
        for b in date_ids[index+1:]:
            assert no_overlap(c.bbox(a),c.bbox(b)),('colliding dates',c.itemcget(a,'text'),c.itemcget(b,'text'))
    for a in date_ids:
        for b in prices:
            assert no_overlap(c.bbox(a),c.bbox(b)),('date/price collision',c.itemcget(a,'text'),c.itemcget(b,'text'))
    for index,a in enumerate(prices):
        for b in prices[index+1:]:
            assert no_overlap(c.bbox(a),c.bbox(b)),('price axis collision',c.itemcget(a,'text'),c.itemcget(b,'text'))


def test_repairs():
    assert chart_grid_plan(1,1,950,520)[2]>chart_grid_plan(9,9,950,520)[2]
    with tempfile.TemporaryDirectory() as td:
        config=Path(td)/'.config'/'augurspex'
        config.mkdir(parents=True)
        (config/'watchlist.json').write_text(json.dumps({'markets':[{'symbol':s,'name':s} for s in SYMBOLS]}))
        (config/'settings.json').write_text(json.dumps({'layout':9,'symbols':list(SYMBOLS),'style':'2'}))
        root=tk.Tk();root.geometry('1400x870+0+0')
        holder=tk.Canvas(root);holder.pack(fill='both',expand=True)
        tab=EmbeddedAugurspex(holder,lambda:None,home=td,offline=True)
        tab.layout((0,0,1400,870))
        root.update()
        p=tab.frame
        # Real-source-only mode, with deterministic known-good history across
        # the *whole* saved 9-slot list, including last slot.
        p.offline=False
        p.sourced_only=True
        for s in SYMBOLS:
            p._data[(s,'D')]=sample(s)
        sizes={}
        for count in (1,2,4,6,9):
            p._change_layout(str(count));root.update();root.update_idletasks()
            assert int(p.settings['layout'])==count
            assert len(p.cards)==count
            assert len(p._chart_slots())==count
            assert len([c for c in p.cards if c.winfo_ismapped()])==count
            assert p._display_slots==list(range(count)), p._display_slots
            assert f'{count} DISPLAYED / {count} REQUESTED' in p.display_count.cget('text')
            chart=p.cards[0]
            validate_axis(chart)
            sizes[count]=(chart.canvas.winfo_width(),chart.canvas.winfo_height())
            assert p.chart_canvas.winfo_width()>250
        assert sizes[1][0]>sizes[4][0]*1.6,(sizes[1],sizes[4])
        assert sizes[1][1]>sizes[9][1]*1.2,(sizes[1],sizes[9])
        # A valid saved slot 9 remains visible even in one-chart mode. This was
        # the user's bug: filtering the first N saved *indices* lost it.
        p._data={(SYMBOLS[-1],'D'):sample(SYMBOLS[-1])}
        p._change_layout('1');root.update()
        assert p._display_slots==[8],p._display_slots
        assert p.cards[0].symbol==SYMBOLS[-1]
        assert p.cards[0].winfo_ismapped()
        assert '1 DISPLAYED / 1 REQUESTED' in p.display_count.cget('text')
        p._change_layout('9');root.update()
        assert p._display_slots==[8]
        assert '1 DISPLAYED / 9 REQUESTED' in p.display_count.cget('text')
        # Reassignment targets original saved slot, not screen position zero.
        p._select_chart(0)
        assert p.active==8
        assert p.settings['symbols'][8]==SYMBOLS[-1]
        # Three desktop sizes; source-only view and all-markets view must remain
        # accessible, without clipped date or price ticks.
        p._data={(s,'D'):sample(s) for s in SYMBOLS}
        for w,h in ((1400,870),(1000,650),(900,580)):
            root.geometry(f'{w}x{h}+0+0');root.update()
            tab.layout((0,0,w,h));root.update()
            p._change_layout('9');root.update()
            assert p.chart_canvas.winfo_height()>90
            assert p.grid_frame.winfo_height()>p.chart_canvas.winfo_height()
            assert p.option_parts[-1].winfo_ismapped()
            assert p.watch.winfo_height()>40
            validate_axis(p.cards[0])
        # Source-only panel updates without deleting saved markets.
        p._toggle_sourced();root.update()
        assert len(p._chart_slots())==9 and len(p.cards)==9
        assert len(p.settings['symbols'])==9
        assert tab.shutdown()
        root.destroy()
    print('AUGURSPEX 0.4.8.5 REAL LAYOUT + SOURCE-SLOT + LABEL COLLISIONS: PASS')


if __name__=='__main__':test_repairs()
