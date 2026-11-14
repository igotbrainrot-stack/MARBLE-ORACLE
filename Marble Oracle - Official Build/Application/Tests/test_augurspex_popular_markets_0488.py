"""Popular watchlist migration, FX reference candles and spacious view tests.

Run: python3 Tests/test_augurspex_popular_markets_0488.py
GUI: xvfb-run -a python3 Tests/test_augurspex_popular_markets_0488.py --gui
"""
from __future__ import annotations
import json, os, sys, tempfile, unittest
from pathlib import Path
from urllib.parse import parse_qs, urlparse

APP = Path(__file__).resolve().parents[1] / 'Runtime' / 'Marble_Oracle_App'
sys.path.insert(0,str(APP))
from Augurspex.augurspex.core import (
    DEFAULT_SLOTS, app_folder, read_settings, market_category, merge_watchlists,
    reset_to_popular_markets_once, update_watchlist,
)
from Augurspex.augurspex.providers import MarketRouter, ProviderError, read_frankfurter_history

DEFAULT=APP/'Augurspex/augurspex/default_watchlist.json'

class CuratedTests(unittest.TestCase):
    def test_curated_symbol_identity_and_categories(self):
        with tempfile.TemporaryDirectory() as folder:
            rows,_=merge_watchlists(Path(folder),DEFAULT,read_settings(Path(folder)))
            self.assertEqual(len(rows),23)
            symbols=[x['symbol'] for x in rows]
            self.assertEqual(len(symbols),len(set(symbols)))
            for wanted in ('AAPL','NVDA','MSFT','AMZN','META','GOOG','TSLA','BTC-USD','ETH-USD','SOL-USD','XRP-USD','FX:EURUSD','FX:AUDUSD','FX:USDJPY'):
                self.assertIn(wanted,symbols)
            self.assertEqual(market_category('FX:EURUSD'),'fx')
            self.assertEqual(market_category('BNB-USD'),'crypto')
            self.assertEqual(market_category('AAPL'),'stocks')
            self.assertEqual(DEFAULT_SLOTS[0:2],['BTC-USD','ETH-USD'])

    def test_once_migration_backups_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as d:
            home=Path(d);folder=app_folder(home);folder.mkdir(parents=True)
            prior={'layout':9,'workspace':'Healthcare','symbols':['CSL.AX']*9,'favorites':['CSL.AX']}
            (folder/'settings.json').write_text(json.dumps(prior))
            (folder/'watchlist.json').write_text(json.dumps({'markets':[{'symbol':'CSL.AX','name':'Custom'}]}))
            self.assertTrue(reset_to_popular_markets_once(home,DEFAULT))
            self.assertFalse(reset_to_popular_markets_once(home,DEFAULT))
            saved=json.loads((folder/'watchlist.json').read_text())['markets']
            self.assertEqual(len(saved),23)
            self.assertEqual(read_settings(home)['layout'],2)
            self.assertEqual(read_settings(home)['symbols'][:2],['BTC-USD','ETH-USD'])
            backups=list((folder/'watchlist-backups').rglob('settings.json'))
            self.assertEqual(len(backups),1)
            self.assertEqual(json.loads(backups[0].read_text())['layout'],9)
            archived=list((folder/'watchlist-backups').rglob('watchlist.json'))
            self.assertEqual(len(archived),1)
            self.assertIn('CSL.AX',archived[0].read_text())
            # Post-migration personal edits must persist; no surprise reset.
            update_watchlist(home,DEFAULT,read_settings(home),['GOOG'],mode='replace')
            self.assertFalse(reset_to_popular_markets_once(home,DEFAULT))
            rows,_=merge_watchlists(home,DEFAULT,read_settings(home))
            self.assertEqual([r['symbol'] for r in rows],['GOOG'])

    def test_fx_history_from_genuine_dates_is_close_only(self):
        calls=[]
        def getter(url):
            calls.append(url)
            return json.dumps([
                {'date':'2026-11-10','base':'EUR','quote':'USD','rate':1.15},
                {'date':'2026-11-11','base':'EUR','quote':'USD','rate':1.16},
                {'date':'2026-11-11','base':'USD','quote':'EUR','rate':0.86},
                {'date':'2026-11-12','base':'EUR','quote':'USD','rate':1.17},
            ]).encode()
        x=read_frankfurter_history('FX:EURUSD','D',getter=getter)
        self.assertEqual(len(x['candles']),3)
        self.assertEqual(x['candles'][-1]['close'],1.17)
        self.assertTrue(all(r['close_only'] for r in x['candles']))
        self.assertIn('reference',x['source'].lower())
        q=parse_qs(urlparse(calls[0]).query)
        self.assertEqual(q['base'],['EUR'])
        self.assertEqual(q['quotes'],['USD'])
        self.assertIn('from',q)
        self.assertNotIn('latest',calls[0])
        weekly=read_frankfurter_history('FX:EURUSD','W',getter=getter)
        self.assertEqual(len(weekly['candles']),1)
        self.assertEqual(weekly['candles'][0]['close'],1.17)
        with self.assertRaises(ProviderError):
            read_frankfurter_history('FX:EURUSD','5',getter=getter)

    def test_fx_routing_never_fabricates_minute_history(self):
        router=MarketRouter()
        self.assertEqual(router._routes('FX:EURUSD','auto','D'),['frankfurter-history','ecb-fx','boc-fx'])
        self.assertEqual(router._routes('FX:EURUSD','auto','W'),['frankfurter-history','ecb-fx','boc-fx'])
        self.assertEqual(router._routes('FX:EURUSD','auto','5'),[])
        self.assertEqual(router._routes('BNB-USD','auto','D'),['coingecko','coinpaprika','cryptocompare'])
        self.assertEqual(router._routes('DOGE-USD','auto','1'),['coinbase','kraken','gemini'])

    def test_unofficial_stock_source_is_conscious_opt_in(self):
        with tempfile.TemporaryDirectory() as folder:
            router=MarketRouter(cache_dir=Path(folder))
            previous=os.environ.pop('AUGURSPEX_ALLOW_UNOFFICIAL_SOURCES',None)
            try:
                self.assertNotIn('yahoo',router._routes('AAPL','auto','D'))
                router.allow_unofficial=True
                routes=router._routes('AAPL','auto','D')
                self.assertIn('yahoo',routes)
                self.assertIn('nasdaq',routes)
            finally:
                if previous is not None:os.environ['AUGURSPEX_ALLOW_UNOFFICIAL_SOURCES']=previous

    def test_bad_history_must_fail_and_not_invent_rate(self):
        with self.assertRaises(ProviderError):
            read_frankfurter_history('FX:EURUSD','D',getter=lambda url: b'[{"date":"2026-11-12","base":"USD","quote":"EUR","rate":3.14}]')

    def test_native_ui_space_and_filters(self):
        import tkinter as tk
        from oracle_augurspex_tab import EmbeddedAugurspex
        with tempfile.TemporaryDirectory() as d:
            reset_to_popular_markets_once(Path(d),DEFAULT)
            class FakeRouter:
                def _routes(self,symbol,source,period='D'):return []
                def fetch(self,*args,**kw):raise ProviderError('Offline fixture')
            root=tk.Tk();root.geometry('1400x870')
            canvas=tk.Canvas(root);canvas.pack(fill='both',expand=True)
            tab=EmbeddedAugurspex(canvas,on_home=lambda:None,home=d,router=FakeRouter(),offline=True)
            tab.layout((0,0,1300,820));root.update()
            frame=tab.frame
            self.assertGreaterEqual(frame.rail_shell.winfo_width(),300)
            self.assertEqual(frame.settings['layout'],2)
            self.assertEqual(frame.watch.size(),23)
            frame._set_filter('fx');root.update()
            self.assertEqual(frame.watch.size(),7)
            frame._set_filter('stocks');root.update()
            self.assertEqual(frame.watch.size(),10)
            frame._set_filter('crypto');root.update()
            self.assertEqual(frame.watch.size(),6)
            frame._set_filter('all');root.update()
            self.assertEqual(frame.watch.size(),23)
            self.assertFalse(frame.settings['unofficial_sources'])
            frame._toggle_unofficial();root.update()
            self.assertTrue(read_settings(Path(d))['unofficial_sources'])
            frame._toggle_unofficial();root.update()
            self.assertFalse(read_settings(Path(d))['unofficial_sources'])
            frame._change_layout('1');root.update()
            self.assertEqual(len(frame.cards),1)
            self.assertTrue(tab.shutdown());root.destroy()

if __name__=='__main__':
    suite=unittest.TestSuite()
    cls=CuratedTests
    for method in sorted(x for x in dir(cls) if x.startswith('test_')):
        if method=='test_native_ui_space_and_filters' and '--gui' not in sys.argv:continue
        suite.addTest(cls(method))
    sys.exit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
