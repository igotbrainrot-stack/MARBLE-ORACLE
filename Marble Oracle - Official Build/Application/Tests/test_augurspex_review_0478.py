"""0.4.7.8: documented exchange data, cache freshness and suite-wide cooldown.

All network responses are controlled. These checks do not assert that an
external website will provide data or that an exchange is in a free plan.
"""
from __future__ import annotations
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'Runtime'/'Marble_Oracle_App'))
from Augurspex.augurspex.providers import (
    MarketRouter, ProviderError, read_twelve, twelve_listing, shared_market_router,
)
from oracle_augurspex_home import MarketCarousel


def response(symbol, mic='XASX', currency='AUD'):
    return json.dumps({'status':'ok','meta':{'symbol':symbol,'mic_code':mic,
                                            'currency':currency},'values':[
        {'datetime':'2026-11-12','open':'106.4','high':'111.2','low':'105.8','close':'110.0','volume':'12100'},
        {'datetime':'2026-11-11','open':'105.1','high':'107.3','low':'103.3','close':'106.4','volume':'12200'}
    ]}).encode()


def test_twelve_maps_original_exchange_not_similarly_named_stock():
    for ticker, expected in {
        'COH.AX':('COH','XASX'), 'ASX:RMD':('RMD','XASX'),
        '4568.T':('4568','XJPX'), '005930.KS':('005930','XKRX'),
        '012345.KQ':('012345','XKOS'), 'AAPL':('AAPL',None),
        'NASDAQ:AAPL':('AAPL',None),
    }.items():
        assert twelve_listing(ticker)==expected, (ticker,twelve_listing(ticker))
    for bad in ('BTC-USD','^GSPC','BLARG:NVDA','ASX:',''):
        assert twelve_listing(bad) is None, bad


def test_twelve_response_and_entitlement():
    with patch.dict(os.environ, {'AUGURSPEX_TWELVE_DATA_KEY':'SAMPLE-KEY'}):
        calls=[]
        def getter(url):
            calls.append(url)
            assert 'symbol=COH' in url and 'mic_code=XASX' in url
            assert 'interval=1day' in url and 'apikey=SAMPLE-KEY' in url
            return response('COH')
        result=read_twelve('COH.AX','D',getter=getter)
        assert len(calls)==1
        assert result['source']=='Twelve Data (documented API)'
        assert result['currency']=='AUD' and result['candles'][0]['close']==106.4
        assert 'paid exchange permissions' in result['note']
        def wrong_exchange(_url):return response('COH',mic='XJPX')
        try:read_twelve('COH.AX','D',getter=wrong_exchange)
        except ProviderError as e:assert 'different exchange' in str(e)
        else:raise AssertionError('Different ASX listing accepted')
        def error_response(_url):return b'{"status":"error","code":429,"message":"Restricted"}'
        try:read_twelve('COH.AX','D',getter=error_response)
        except ProviderError as e:assert 'HTTP 429' in str(e)
        else:raise AssertionError('Rate limit accepted as valid candles')


def test_optional_api_never_implicitly_required():
    with patch.dict(os.environ,{'AUGURSPEX_TWELVE_DATA_KEY':''}):
        r=MarketRouter(clock=lambda:100)
        assert 'twelve' not in r._routes('COH.AX','auto')
        try:read_twelve('COH.AX','D',getter=lambda _:response('COH'))
        except ProviderError as e:assert 'not configured' in str(e)
        else:raise AssertionError('Provider should require explicit owner config')
    with patch.dict(os.environ,{'AUGURSPEX_TWELVE_DATA_KEY':'SAMPLE-KEY'}):
        r=MarketRouter(clock=lambda:100)
        assert r._routes('COH.AX','auto')==['twelve']
        assert r._routes('COH.AX','auto','5')==['twelve']
        assert r._routes('NVDA','auto')==['twelve','stooq']
        calls=[]
        def getter(url):
            calls.append(url)
            if 'twelvedata' in url:return response('COH')
            raise AssertionError('Should have used documented fallback before Stooq')
        result=r.fetch('COH.AX','D',getter=getter)
        assert result['source'].startswith('Twelve Data')
        assert len(calls)==1
        assert not result.get('provider_attempts')


def test_future_cache_cannot_masquerade_as_fresh():
    with tempfile.TemporaryDirectory() as td:
        clock=[300.0]
        r=MarketRouter(clock=lambda:clock[0],cache_dir=Path(td))
        r._save(('NVDA','D','nasdaq'),clock[0]+100000,{'source':'fake','candles':[{'time':'x','close':100}]})
        def reject(url):raise ProviderError('NO DATA')
        try:r.fetch('NVDA','D',getter=reject)
        except ProviderError:pass
        else:raise AssertionError('Future cache accepted as fresh or stale')
        # Verify future-dated entries read back from disk are not accepted.
        again=MarketRouter(clock=lambda:clock[0],cache_dir=Path(td))
        try:again.fetch('NVDA','D',getter=reject)
        except ProviderError:pass
        else:raise AssertionError('Disk future cache accepted')
        # FX cache uses rate rather than candles and must still be retained.
        fxkey=('fx','AUD','USD')
        r._save(fxkey, clock[0],{'source':'sample','rate':0.6})
        fx=MarketRouter(clock=lambda:clock[0],cache_dir=Path(td))
        assert fx._cached(fxkey)['value']['rate']==0.6


def test_suite_shared_cooldown():
    with tempfile.TemporaryDirectory() as td:
        location=Path(td)/'.cache/augurspex/market'
        a=shared_market_router(location)
        b=shared_market_router(location)
        assert a is b
        carousel=MarketCarousel(home=td,enabled=False)
        assert carousel.router is a
        carousel.close()
        with a.lock:
            a.blocked['yahoo']=a.clock()+900
        assert b.blocked['yahoo']>b.clock()
        assert a.cache_dir==location.resolve()


def test_credential_errors_are_redacted():
    with patch.dict(os.environ,{'AUGURSPEX_TWELVE_DATA_KEY':'SPECIAL-SECRET'}):
        r=MarketRouter(clock=lambda:100)
        def getter(url):
            if 'yahoo' in url:return b'{"chart":{"error":{"code":"Not Found"}}}'
            raise ProviderError('provider rejected SPECIAL-SECRET')
        try:r.fetch('COH.AX','D',getter=getter)
        except ProviderError as e:
            assert 'SPECIAL-SECRET' not in str(e)
            assert '[REDACTED]' in str(e)
        else:raise AssertionError('Failed request succeeded')




def test_home_carousel_marks_old_good_result_stale_after_refresh_failure():
    import time
    class Alternating:
        def __init__(self):self.good=True
        def fetch(self,symbol,period):
            if not self.good:raise ProviderError('HTTP 429; rate limited')
            return {'source':'Test exchange', 'cache':'network', 'latest_observation':'2026-11-12',
                    'candles':[{'time':'2026-11-11','close':1.0},
                               {'time':'2026-11-12','close':2.0}]}
    with tempfile.TemporaryDirectory() as td:
        home=Path(td)
        p=home/'.config/augurspex/watchlist.json'
        p.parent.mkdir(parents=True)
        p.write_text(json.dumps({'markets':[{'symbol':'NVDA','name':'Nvidia'}]}))
        clock=[10.0]
        router=Alternating()
        widget=MarketCarousel(home=home,router=router,clock=lambda:clock[0])
        def pump(expected):
            end=time.monotonic()+2
            while time.monotonic()<end:
                widget.tick()
                if widget.snapshot()['state']==expected:return
                time.sleep(0.01)
            raise AssertionError(widget.snapshot())
        pump('data')
        router.good=False
        clock[0]+=301
        # Trigger a new failed network request after the 300s request guard.
        widget.tick()
        end=time.monotonic()+2
        while time.monotonic()<end and not widget.snapshot()['error']:
            time.sleep(.01)
        snap=widget.snapshot()
        assert snap['state']=='data' and snap['cache']=='stale'
        assert '429' in snap['error']
        widget._received_at['NVDA']-=8*86400
        snap=widget.snapshot()
        assert snap['state']=='unavailable' and snap['candles']==[]
        widget.close()


if __name__=='__main__':
    for name in sorted(globals()):
        fn=globals()[name]
        if name.startswith('test_') and callable(fn):
            fn()
            print(name,'PASS')
