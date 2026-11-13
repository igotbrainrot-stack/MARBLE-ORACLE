"""HOME chart: user's AUGURSPEX watchlist, async history and non-fabricated empty state."""
from __future__ import annotations
import json
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

APP = Path(__file__).resolve().parents[1] / 'Runtime' / 'Marble_Oracle_App'
sys.path.insert(0, str(APP))
from oracle_augurspex_home import MarketCarousel

class FakeRouter:
    def __init__(self):
        self.calls = []
    def fetch(self, symbol, period='D'):
        self.calls.append((symbol,period,threading.current_thread().name))
        if symbol == 'COH.AX':
            raise ValueError('Source unavailable')
        return {'source':'stooq','candles':[
            {'time':'2026-11-09', 'close': 100},
            {'time':'2026-11-10', 'close': 101},
            {'time':'2026-11-11', 'close': 103}], 'cache':'network'}

def set_watchlist(home, symbols):
    path = home/'.config'/'augurspex'/'watchlist.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'markets':[{'symbol':s,'name':s+' NAME'} for s in symbols]}))

class HomeCarouselTests(unittest.TestCase):
    def test_rotates_across_entire_saved_watchlist_without_main_thread_network(self):
        with tempfile.TemporaryDirectory() as d:
            home=Path(d)
            set_watchlist(home,['RMD.AX','COH.AX','NVDA'])
            now=[0]
            router=FakeRouter()
            c=MarketCarousel(home=home, router=router, clock=lambda:now[0],rotate_seconds=12)
            self.assertEqual(c.snapshot()['total'],3)
            self.assertTrue(c.tick())
            self.assertFalse(c.tick())
            deadline=time.time()+2
            while c.snapshot()['state']!='data' and time.time()<deadline:
                time.sleep(.01)
            self.assertEqual(c.snapshot()['candles'][-1]['close'],103)
            self.assertEqual(router.calls[0],('RMD.AX','D','Marble-AUGURSPEX-history'))
            now[0]=12.1
            c.tick()
            self.assertEqual(c.snapshot()['symbol'],'COH.AX')
            deadline=time.time()+2
            while c.snapshot()['state']!='unavailable' and time.time()<deadline:
                time.sleep(.01)
            self.assertEqual(c.snapshot()['state'],'unavailable')
            now[0]=24.2
            c.tick()
            self.assertEqual(c.snapshot()['symbol'],'NVDA')
            now[0]=36.3
            c.tick()
            self.assertEqual(c.snapshot()['symbol'],'RMD.AX')
            self.assertEqual(c.snapshot()['index'],0)
            c.close()

    def test_empty_watchlist_is_intentionally_empty(self):
        with tempfile.TemporaryDirectory() as d:
            home=Path(d)
            set_watchlist(home,[])
            c=MarketCarousel(home=home,router=FakeRouter())
            self.assertEqual(c.snapshot()['total'],0)
            self.assertTrue(c.tick())  # First draw renders an intentional empty state.
            self.assertFalse(c.tick())
            c.close()

    def test_change_watchlist_reflected_without_restart(self):
        with tempfile.TemporaryDirectory() as d:
            home=Path(d)
            set_watchlist(home,['NVDA'])
            now=[100]
            c=MarketCarousel(home=home,router=FakeRouter(),clock=lambda:now[0],enabled=False,reload_seconds=5)
            self.assertEqual(c.snapshot()['state'],'offline')
            set_watchlist(home,['RMD.AX','COH.AX'])
            now[0]=106
            self.assertTrue(c.tick())
            self.assertEqual(c.snapshot()['total'],2)
            self.assertEqual(c.snapshot()['symbol'],'RMD.AX')
            c.close()

    def test_no_network_when_disabled(self):
        with tempfile.TemporaryDirectory() as d:
            home=Path(d)
            set_watchlist(home,['NVDA','RMD.AX'])
            router=FakeRouter()
            c=MarketCarousel(home=home,router=router,enabled=False)
            c.tick()
            c.advance()
            self.assertEqual(c.snapshot()['state'],'offline')
            self.assertEqual(router.calls,[])
            c.close()

if __name__=='__main__': unittest.main()
