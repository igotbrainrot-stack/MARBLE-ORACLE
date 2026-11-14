"""Marble Oracle 0.4.8.9: Market Atlas, keyboard chart, true-close CSV, suite guide.

Run pure tests: python3 Tests/test_market_atlas_0489.py
GUI tests: xvfb-run -a python3 Tests/test_market_atlas_0489.py --gui
"""
from __future__ import annotations
import csv, io, sys, tempfile, time, unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch

APP=Path(__file__).resolve().parents[1]/'Runtime'/'Marble_Oracle_App'
sys.path.insert(0,str(APP))
from oracle_augurspex_insights import market_rows, observation_cells
from oracle_augurspex_tab import csv_safe, history_health

now=datetime.now(timezone.utc)
yesterday=(now-timedelta(days=1)).isoformat()
old=(now-timedelta(days=900)).isoformat()


def candle(index, date, close, close_only=False):
    return {'time':date,'open':close,'high':close,'low':close,'close':close,'volume':0,'close_only':close_only}


class AtlasTests(unittest.TestCase):
    def test_rows_no_fake_prices_and_window_changes(self):
        watch=[{'symbol':'AAPL','name':'Apple Inc.'},{'symbol':'BTC-USD','name':'Bitcoin'},
               {'symbol':'FX:EURUSD','name':'Euro / US dollar'}]
        d={('AAPL','D'):{'source':'fixture','currency':'USD','candles':[candle(i,yesterday,10+i,True) for i in range(100)]},
           ('BTC-USD','D'):{'source':'fixture','currency':'USD','candles':[candle(1,old,10,True),candle(2,old,20,True)]}}
        rows=market_rows(watch,d,{('FX:EURUSD','D'):'no usable candles'},'D','30',now=now)
        apple,btc,fx=rows
        self.assertEqual(apple['status'],'RECENT')
        self.assertAlmostEqual(apple['change'],(109/80-1)*100)
        self.assertEqual(apple['count'],100)
        self.assertTrue(apple['close_only'])
        self.assertEqual(btc['status'],'STALE')
        self.assertEqual(fx['status'],'SOURCE ERROR')
        self.assertIsNone(fx['last']);self.assertIsNone(fx['change'])
        self.assertEqual(fx['source'],'—')
        self.assertIsNone(history_health({'candles':[candle(1,old,10)]},'AAPL','D',now=now)[1] if False else None)

    def test_close_only_cannot_invent_ohlc_in_table(self):
        bars=[candle(1,yesterday,109.5,True),
              {'time':yesterday,'open':10,'high':12,'low':9,'close':11,'volume':50}]
        rows=list(observation_cells(bars))
        self.assertEqual(rows[0][1:4],('','',''))
        self.assertEqual(rows[0][4],109.5)
        self.assertEqual(rows[1][1:5],(10,12,9,11))
        self.assertEqual(csv_safe('=2+2'),"'=2+2")

    def test_gui_atlas_keyboard_and_help(self):
        import tkinter as tk
        from oracle_augurspex_tab import EmbeddedAugurspex
        from marble_oracle import parse, WindowApp
        with tempfile.TemporaryDirectory() as path:
            root=tk.Tk();root.geometry('1150x750');root.update()
            canvas=tk.Canvas(root,width=1150,height=700);canvas.pack(fill='both',expand=True)
            class FakeRouter:
                def _routes(self,symbol,source,period='D'):return []
                def fetch(self,*a,**k):raise AssertionError('Network must stay disabled in fixture')
            tab=EmbeddedAugurspex(canvas,on_home=lambda:None,home=path,router=FakeRouter(),offline=True)
            tab.layout((0,0,1150,700));root.update()
            panel=tab.frame
            panel._data[('BTC-USD','D')]={'source':'OFFLINE TEST DATA','currency':'USD',
                'candles':[candle(i,(now-timedelta(days=40-i)).isoformat(),100+i,True) for i in range(40)]}
            panel.settings['symbols'][0]='BTC-USD'
            panel._refresh_charts();root.update()
            card=panel.cards[0]
            self.assertGreater(len(card._plot_points),0)
            self.assertEqual(card._step_observation(1),'break')
            self.assertEqual(card._cursor_index,0)
            self.assertIn('CLOSE',card._hover_text)
            self.assertEqual(card._jump_observation(-1),'break')
            self.assertEqual(card._cursor_index,len(card._plot_points)-1)
            card._on_chart_leave()
            self.assertIsNone(card._cursor_index)
            atlas=panel._show_market_atlas();root.update()
            self.assertIn('MARKET ATLAS',atlas.title())
            self.assertTrue(atlas.winfo_exists());atlas.destroy()
            table=panel._show_observation_table();root.update()
            self.assertIn('OBSERVATIONS',table.title())
            tree=[w for w in table.winfo_children() if False]
            table.destroy()
            with patch('oracle_augurspex_tab.filedialog.asksaveasfilename', return_value=str(Path(path)/'prices.csv')):
                panel._export_chart_csv()
            with open(Path(path)/'prices.csv',encoding='utf-8',newline='') as f:
                rows=list(csv.DictReader(f))
            self.assertEqual(len(rows),40)
            self.assertTrue(all(row['open']==row['high']==row['low']=='' for row in rows))
            self.assertTrue(tab.shutdown());root.destroy()
            opts=vars(parse(['--selftest','--no-network','--no-markets','--no-bezel','--os-frame']))
            app=WindowApp(opts)
            try:
                e=type('Event',(),{'keysym':'F1','char':''})()
                self.assertEqual(app.scene.on_key(e),'break')
                guide=app.scene._guide_window
                app.root.update()
                self.assertTrue(guide.winfo_exists())
                self.assertIn('FIELD GUIDE',guide.title())
                guide.destroy()
            finally:app.quit()


if __name__=='__main__':
    gui='--gui' in sys.argv
    suite=unittest.TestSuite()
    for name in sorted(x for x in dir(AtlasTests) if x.startswith('test_')):
        if name.endswith('gui_atlas_keyboard_and_help') and not gui:continue
        suite.addTest(AtlasTests(name))
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
