"""0.4.8.7 independent second pass: validity, range controls, CSV completeness.

Synthetic data only; no external market access. Run under xvfb-run.
"""
from __future__ import annotations
import csv, json, sys, tempfile, tkinter as tk, time
from datetime import datetime,timedelta,timezone
from pathlib import Path

APP=Path(__file__).resolve().parents[1]/'Runtime'/'Marble_Oracle_App'
sys.path.insert(0,str(APP))
from oracle_augurspex_tab import (
    _plotted_candles, observed_at, history_health, chart_display_bars,
    chart_date_ticks, plot_points, csv_safe, EmbeddedAugurspex)
from Augurspex.augurspex.core import sanitize_settings,read_settings
import oracle_augurspex_tab


def history(count=250, age=0):
    end=(datetime.now(timezone.utc).date()-timedelta(days=age))
    return [dict(time=(end-timedelta(days=count-1-i)).isoformat(),
            open=100.0+i, high=102.0+i, low=99.0+i, close=101.0+i, volume=i)
            for i in range(count)]

class FixtureRouter:
    def _routes(self,*_):return ['fixture']
    def fetch(self,symbol,period='D'):
        bars=history()
        return {'source':'LOCAL FIXTURE (NOT LIVE)','currency':'USD',
                'interval':period,'latest_observation':bars[-1]['time'],'candles':bars}


def test_data_integrity():
    rows=history(count=250,age=70)
    invalid=dict(time=datetime.now(timezone.utc).isoformat(),open=-1,low=-1,high=-1,close=-1)
    rows.append(invalid)
    data={'candles':rows, 'latest_observation':rows[-2]['time']}
    health,date=history_health(data,'AAPL','D')
    assert health=='stale' and date.date()==datetime.fromisoformat(rows[-2]['time']).date(),(health,date)
    assert len(_plotted_candles(rows,limit=None))==250
    assert len(_plotted_candles(rows))==119
    assert len(chart_display_bars(rows,700,'2','30'))==30
    assert len(chart_display_bars(rows,700,'2','90'))==90
    assert len(chart_display_bars(rows,700,'2','MAX'))==250
    assert len(chart_display_bars(rows,300,'1','MAX'))<250  # density safeguard
    assert len(plot_points(history(),700,320)[0])==250
    ticks=chart_date_ticks(history(),700)
    assert 2<=len(ticks)<=5
    assert csv_safe('\t=1+2').startswith("'"),csv_safe('\t=1+2')
    assert csv_safe('＝HYPERLINK(...)').startswith("'"),csv_safe('＝HYPERLINK(...)')
    assert sanitize_settings({'view_bars':'15'})['view_bars']=='MAX'
    assert sanitize_settings({'view_bars':'30'})['view_bars']=='30'


def test_native_gui():
    with tempfile.TemporaryDirectory() as folder:
        home=Path(folder)
        config=home/'.config'/'augurspex';config.mkdir(parents=True)
        (config/'settings.json').write_text(json.dumps({'symbols':['AAPL']+['']*8,'layout':1,'style':'2',
                                                        'view_bars':'90'}))
        (config/'watchlist.json').write_text(json.dumps({'markets':[{'symbol':'AAPL','name':'Apple'}]}))
        root=tk.Tk();root.geometry('1100x740+0+0');root.update()
        canvas=tk.Canvas(root,width=1080,height=710);canvas.pack(fill='both',expand=True)
        tab=EmbeddedAugurspex(canvas,lambda:None,home=home,router=FixtureRouter())
        tab.layout((0,0,1060,690))
        panel=tab.frame
        assert panel.view_bars_var.get()=='90 BARS'
        # Fixture responses can be async; real UI loop runs their event handlers.
        for i in range(100):
            root.update()
            if ('AAPL','D') in panel._data:break
            time.sleep(.02)
        assert ('AAPL','D') in panel._data,'fixture was not loaded'
        panel._refresh_charts();root.update();root.update()
        chart=panel.cards[0]
        assert len(chart._plot_bars)==90,len(chart._plot_bars)
        panel._change_view_bars('30 BARS');root.update()
        assert len(chart._plot_bars)==30
        view_change=(history()[-1]['close']/history()[-30]['close']-1)*100
        assert f'VIEW {view_change:+.2f}%' in chart._info_text,chart._info_text
        assert read_settings(home)['view_bars']=='30'
        panel._change_view_bars('MAX BARS');root.update()
        assert len(chart._plot_bars)==250
        # CSV must export all 250 records, independent of chosen visible range.
        panel._change_view_bars('30 BARS');root.update()
        target=home/'actual.csv'
        original=oracle_augurspex_tab.filedialog.asksaveasfilename
        oracle_augurspex_tab.filedialog.asksaveasfilename=lambda **kwargs:str(target)
        try:panel._export_chart_csv()
        finally:oracle_augurspex_tab.filedialog.asksaveasfilename=original
        with target.open(newline='',encoding='utf8') as f:records=list(csv.DictReader(f))
        assert len(records)==250,len(records)
        assert records[0]['close']=='101.0'
        assert records[-1]['close']==str(history()[-1]['close'])
        # Narrow viewport preserves explicit control, with chart canvas still real.
        tab.layout((0,0,920,580));root.update();root.update()
        assert panel.view_bars_var.get()=='30 BARS'
        assert chart.canvas.winfo_width()>200,(chart.canvas.winfo_width(),chart.canvas.winfo_height())
        tab.shutdown();root.destroy()

if __name__=='__main__':
    test_data_integrity();print('SECOND PASS DATA INTEGRITY: PASS',flush=True)
    test_native_gui();print('SECOND PASS UI / RANGE / CSV: PASS',flush=True)
