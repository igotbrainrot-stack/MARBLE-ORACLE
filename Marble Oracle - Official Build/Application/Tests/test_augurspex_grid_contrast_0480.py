"""0.4.8.0 canvas verification: real grid and visibly outlined price marks.

Run: xvfb-run -a python3 Tests/test_augurspex_grid_contrast_0480.py
"""
from pathlib import Path
import sys
import tkinter as tk
from datetime import datetime, timedelta, timezone

ROOT = Path(__file__).resolve().parent.parent / 'Runtime' / 'Marble_Oracle_App'
sys.path.insert(0, str(ROOT))
from oracle_augurspex_tab import PriceChart, palette, chart_display_bars


def observations(count=120):
    first = datetime(2026, 7, 1, tzinfo=timezone.utc)
    return [dict(time=(first + timedelta(days=i)).isoformat(),
                 open=100+i*0.15, high=104+i*0.15, low=98+i*0.15,
                 close=102+i*0.15) for i in range(count)]


def tagged(canvas, name):
    return canvas.find_withtag(name)


def test_grid_lines_and_candle_outlines():
    root=tk.Tk(); root.geometry('520x340')
    try:
        card=PriceChart(root,palette(),0,lambda *_:None)
        card.pack(fill='both',expand=True)
        root.update()
        candles=observations()
        data=dict(candles=candles,source='TEST',currency='USD',latest_observation='2026-11-11')
        card.display('NVDA','NVIDIA',data,None,False,'1',True)
        root.update()
        canvas=card.canvas
        assert len(tagged(canvas,'horizontal-grid'))>=4
        assert len(tagged(canvas,'vertical-grid'))>=1
        assert len(tagged(canvas,'plot-frame'))==1
        assert len(tagged(canvas,'candle-body'))>12
        assert len(tagged(canvas,'candle-body'))<120, 'Narrow cards must show fewer, actual recent candles'
        assert len(tagged(canvas,'candle-wick'))==2*len(tagged(canvas,'candle-body'))
        outer=tagged(canvas,'price-outline')
        assert outer and max(float(canvas.itemcget(i,'width')) for i in outer)>=5
        assert all(canvas.itemcget(i,'outline') for i in tagged(canvas,'candle-body'))
        assert len(chart_display_bars(candles,300,'1'))<len(candles)
        assert chart_display_bars(candles,300,'1')[-1]['time']==candles[-1]['time']
        labels=[canvas.itemcget(i,'text') for i in tagged(canvas,'all') if canvas.type(i)=='text']
        assert 'LAST ' in card._observation_note and 'REAL BARS' in card._observation_note, card._observation_note
        assert 'LAST ' in card._info_text and 'REAL BARS' in card._info_text
        # A thick line outline is used in LINE mode even if CANDLES is default.
        card.display('NVDA','NVIDIA',data,None,False,'2',True)
        root.update()
        line_items=tagged(canvas,'price-line')
        assert len(line_items)==2
        assert sorted(float(canvas.itemcget(i,'width')) for i in line_items)==[4.4,7.4]
        assert len(tagged(canvas,'vertical-grid'))>=1
    finally:
        root.destroy()


def test_chart_colors_change_without_data_loss():
    root=tk.Tk(); root.geometry('360x270')
    try:
        card=PriceChart(root,palette(),0,lambda *_:None)
        card.pack(fill='both',expand=True)
        root.update()
        single=dict(candles=observations(35),source='TEST',currency='USD')
        card.display('COH.AX','Cochlear',single,None,False,'1',True)
        assert card.result is single
        assert tagged(card.canvas,'chart-grid')
    finally:
        root.destroy()


if __name__=='__main__':
    test_grid_lines_and_candle_outlines()
    test_chart_colors_change_without_data_loss()
    print('AUGURSPEX HIGH-CONTRAST GRID, PRICE OUTLINES, DENSE CANDLES: PASS')
