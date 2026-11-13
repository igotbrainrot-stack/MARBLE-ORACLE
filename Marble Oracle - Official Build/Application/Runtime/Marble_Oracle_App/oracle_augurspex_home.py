"""Rotating AUGURSPEX historical-price charts for Marble Oracle HOME.

The user's saved AUGURSPEX watchlist is authoritative. We never invent prices,
we do not fetch inside Tk's UI thread, and unavailable assets still rotate.
"""
from __future__ import annotations
import math
import threading
import time
from pathlib import Path
from Augurspex.augurspex.core import merge_watchlists, read_settings
from Augurspex.augurspex.providers import MarketRouter, shared_market_router

class MarketCarousel:
    def __init__(self, *, home=None, router=None, enabled=True, rotate_seconds=12,
                 clock=None, reload_seconds=20):
        self.home = Path(home) if home is not None else Path.home()
        self.router = router if router is not None else shared_market_router(self.home/'.cache/augurspex/market')
        self.enabled = bool(enabled)
        self.rotate_seconds = rotate_seconds
        self.reload_seconds = reload_seconds
        self.clock = clock or time.monotonic
        self._lock = threading.Lock()
        self._rows = []
        self._index = 0
        self._selected_at = self.clock()
        self._reloaded_at = -float('inf')
        self._results = {}
        self._received_at = {}
        self._errors = {}
        self._requested_at = {}
        self._inflight = None
        self._closed = False
        self._revision = 0
        self._display_revision = -1
        self._load()

    def _load(self):
        default = Path(__file__).resolve().parent/'Augurspex/augurspex/default_watchlist.json'
        try:
            new, _ = merge_watchlists(self.home, default, read_settings(self.home))
        except (OSError, TypeError, ValueError):
            new = []
        oldsymbol = self._rows[self._index]['symbol'] if self._rows else None
        oldrows = [(r['symbol'],r['name']) for r in self._rows]
        if [(r['symbol'],r['name']) for r in new] != oldrows:
            self._rows = new
            self._index = next((i for i, r in enumerate(new) if r['symbol'] == oldsymbol),0)
            self._revision += 1
        self._reloaded_at = self.clock()

    def advance(self, delta=1):
        if self._rows:
            self._index = (self._index+delta) % len(self._rows)
            self._selected_at = self.clock()
            self._revision += 1
            self._fetch_current()

    def _fetch_current(self):
        if not self.enabled or not self._rows or self._closed:
            return
        symbol = self._rows[self._index]['symbol']
        now = self.clock()
        with self._lock:
            if self._inflight is not None or now-self._requested_at.get(symbol,-1e12)<300:
                return
            self._inflight = symbol
            self._requested_at[symbol] = now
        def worker():
            try:
                data = self.router.fetch(symbol, 'D')
                candles = data.get('candles',[]) if isinstance(data,dict) else []
                if not isinstance(candles,list) or len(candles)<2:
                    raise ValueError('Insufficient historical prices')
                values=[r.get('close') for r in candles if isinstance(r,dict)]
                if len(values)<2 or any(type(v) not in (int,float) or not math.isfinite(v) for v in values):
                    raise ValueError('Invalid historical prices')
                with self._lock:
                    if not self._closed:
                        self._results[symbol]=data
                        self._received_at[symbol]=time.time()
                        self._errors.pop(symbol,None)
                        self._revision+=1
            except Exception as exc:
                with self._lock:
                    if not self._closed:
                        self._errors[symbol] = str(exc)[:240]
                        self._revision += 1
            finally:
                with self._lock:
                    self._inflight = None
        threading.Thread(target=worker, name='Marble-AUGURSPEX-history', daemon=True).start()

    def tick(self):
        now=self.clock()
        if now-self._reloaded_at>=self.reload_seconds:
            self._load()
        if self._rows and now-self._selected_at>=self.rotate_seconds:
            self.advance(1)
        self._fetch_current()
        with self._lock:
            changed = self._display_revision != self._revision
            self._display_revision = self._revision
        return changed

    def snapshot(self):
        with self._lock:
            if not self._rows:
                return {'state':'idle','total':0,'index':0,'symbol':'','name':'',
                        'candles':[],'source':''}
            item=self._rows[self._index]
            symbol=item['symbol']
            data=self._results.get(symbol)
            error=self._errors.get(symbol,'')
            # If a later provider request fails, the last known-good graph
            # may still be useful for up to seven days. Label it STALE,
            # never imply that its old values are a fresh market quote.
            received=self._received_at.get(symbol,0)
            age=time.time()-received
            if data and (received<=0 or age<0 or age>7*86400):
                data=None
            stale=bool(data and error)
            status='data' if data else ('offline' if not self.enabled else
                    'unavailable' if error else
                    'loading' if self._inflight == symbol else 'idle')
            return {'state':status,'total':len(self._rows),'index':self._index,
                    'symbol':symbol,'name':item['name'],
                    'candles':data.get('candles',[]) if data else [],
                    'source':data.get('source','') if data else '',
                    'cache':'stale' if stale else data.get('cache','') if data else '',
                    'observed':data.get('latest_observation','') if data else '',
                    'error':error}

    def close(self):
        with self._lock:
            self._closed = True
