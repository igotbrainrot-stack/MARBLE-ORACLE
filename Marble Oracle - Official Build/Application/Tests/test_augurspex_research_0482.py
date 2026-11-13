"""Research-led AUGURSPEX adapters: offline deterministic fixtures and identity checks.
Run: python3 Tests/test_augurspex_research_0482.py
"""
from __future__ import annotations
import json, os, sys, tempfile, time
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Runtime'/'Marble_Oracle_App'))
from Augurspex.augurspex.providers import (MarketRouter,ProviderError,read_massive,read_jquants,
    read_krx,read_coingecko,read_coinpaprika,_tse_code,_krx_code)


def tests():
    def no_http(_url):raise AssertionError('Must not send request')
    with patch.dict(os.environ,{},clear=True):
        r=MarketRouter(clock=lambda:100)
        assert r._routes('BTC-USD','auto')==['coinbase','kraken','coingecko','coinpaprika']
        assert r._routes('COH.AX','auto')==[]
        assert r._routes('4568.T','auto')==[]
        assert r._routes('005930.KS','auto')==[]
        assert r._routes('NVDA','auto')==['stooq']
        for sym in ('COH.AX','4568.T','005930.KS'):
            try:r.fetch(sym,getter=no_http)
            except ProviderError as e:assert 'NO ELIGIBLE PROVIDER' in str(e)
            else:raise AssertionError('Unlicensed route must fail before network')
        assert _tse_code('4568.T')=='4568'
        assert _krx_code('005930.KS')==('005930','KS')
    with patch.dict(os.environ,{'AUGURSPEX_ALLOW_UNOFFICIAL_SOURCES':'1'},clear=True):
        r=MarketRouter(clock=lambda:100)
        assert r._routes('COH.AX','auto')==['yahoo','stooq']
        assert r._routes('NVDA','auto')==['stooq','nasdaq','yahoo']
    with patch.dict(os.environ,{'AUGURSPEX_MASSIVE_KEY':'MASSIVE-TEST',
                                'AUGURSPEX_JQUANTS_KEY':'JQUANTS-TEST',
                                'AUGURSPEX_KRX_KEY':'KRX-TEST'},clear=True):
        r=MarketRouter(clock=lambda:100)
        assert r._routes('NVDA','auto')[0]=='massive'
        assert r._routes('4568.T','auto')[0]=='jquants'
        assert r._routes('005930.KS','auto')[0]=='krx'
        def massive_good(url):
            assert '/NVDA/range/1/day/' in url and 'apiKey=MASSIVE-TEST' in url
            return json.dumps({'ticker':'NVDA','status':'OK','results':[
                {'t':1794355200000,'o':100,'h':110,'l':95,'c':107,'v':3000}
            ]}).encode()
        data=read_massive('NVDA','D',getter=massive_good)
        assert data['source'].startswith('Massive') and data['candles'][0]['close']==107
        def massive_wrong(url):
            return b'{"ticker":"TSLA","status":"OK","results":[{"t":1794355200000,"o":1,"h":2,"l":1,"c":2}]}'
        try:read_massive('NVDA','D',getter=massive_wrong)
        except ProviderError as e:assert 'different ticker' in str(e)
        else:raise AssertionError('Wrong ticker accepted')
        captured=[]
        def jquants(url,headers):
            captured.append((url,headers))
            return json.dumps({'data':[{'Date':'2026-09-08','Code':'45680',
                'O':100,'H':110,'L':98,'C':103,'Vo':12000}]}).encode()
        # Official J-Quants accepts four-character code matching common stock's 5-digit output.
        jq=read_jquants('4568.T','D',getter=jquants)
        assert jq['currency']=='JPY' and jq['candles'][0]['close']==103
        assert captured[0][1]=={'x-api-key':'JQUANTS-TEST'}
        assert 'JQUANTS-TEST' not in captured[0][0]
        def krx(url,headers):
            assert 'AUTH_KEY' in headers and headers['AUTH_KEY']=='KRX-TEST'
            assert 'KRX-TEST' not in url
            date=url.split('basDd=')[-1]
            return json.dumps({'OutBlock_1':[
                {'BAS_DD':date,'ISU_CD':'005930','TDD_OPNPRC':'80,000','TDD_HGPRC':'83,000',
                 'TDD_LWPRC':'79,000','TDD_CLSPRC':'82,000','ACC_TRDVOL':'1,000,000'},
                {'BAS_DD':date,'ISU_CD':'000660','TDD_OPNPRC':'70,000','TDD_HGPRC':'73,000',
                 'TDD_LWPRC':'69,000','TDD_CLSPRC':'72,000','ACC_TRDVOL':'500,000'},
            ]}).encode()
        k=read_krx('005930.KS','D',getter=krx)
        assert k['currency']=='KRW' and k['candles'][-1]['close']==82000
        assert len(k['candles'])>=8
    # CoinGecko and CoinPaprika are cross-exchange aggregated USD observations,
    # and MUST NOT be rendered as venue-specific OHLC candles.
    values=[(1794355200000,200.5),(1794441600000,203.2),(1794528000000,201.1)]
    with patch.dict(os.environ,{},clear=True):
        c=read_coingecko('ETH-USD','D',getter=lambda _:json.dumps({'prices':values}).encode())
        assert c['aggregated_market'] is True
        assert all(x['close_only'] for x in c['candles'])
        assert c['source'].startswith('CoinGecko')
        p=read_coinpaprika('ETH-USD','D',getter=lambda _:json.dumps([
            {'timestamp':'2026-11-10T00:00:00Z','price':201},
            {'timestamp':'2026-11-11T00:00:00Z','price':203},
        ]).encode())
        assert p['aggregated_market'] and all(x['close_only'] for x in p['candles'])
        def fallthrough(url):
            if 'api.exchange.coinbase.com' in url or 'api.kraken.com' in url:
                raise ProviderError('HTTP 429; upstream provider rate limited')
            if 'coingecko.com' in url:return json.dumps({'prices':values}).encode()
            raise AssertionError('CoinGecko should finish fallback')
        result=MarketRouter(clock=lambda:100).fetch('ETH-USD','D',getter=fallthrough)
        assert result['source'].startswith('CoinGecko')
        assert result['provider_attempts'][0].startswith('coinbase:')
        assert result['aggregated_market']
        # CoinGecko cannot claim it has actual 1-minute OHLC bars.
        assert MarketRouter()._routes('ETH-USD','auto','1')==['coinbase','kraken']
    return True

if __name__=='__main__':
    tests()
    print('AUGURSPEX 0.4.8.2 RESEARCH ADAPTERS: PASS')


def test_fred_index_close_only_and_no_equity_proxy():
    from Augurspex.augurspex.providers import read_fred
    with patch.dict(os.environ,{'AUGURSPEX_FRED_KEY':'KEY_FOR_TEST'}):
        def getter(url):
            assert 'series_id=SP500' in url and 'api_key=KEY_FOR_TEST' in url
            return json.dumps({'observations':[
                {'date':'2026-11-10','value':'6100.4'},
                {'date':'2026-11-11','value':'.'},
                {'date':'2026-11-12','value':'6200.8'}]}).encode()
        result=read_fred('^GSPC','D',getter=getter)
        assert len(result['candles'])==2
        assert all(row['close_only'] for row in result['candles'])
        assert result['candles'][1]['close']==6200.8
        assert 'FRED' in result['source']
        for ticker in ('SPY','NVDA','^FAKE'):
            try:read_fred(ticker,'D',getter=getter)
            except ProviderError:pass
            else:raise AssertionError('Unrelated index identity was accepted')


def test_concurrent_same_symbol_singleflight():
    from concurrent.futures import ThreadPoolExecutor
    import threading
    count=[]; gate=threading.Lock()
    def get(url):
        with gate:count.append(url)
        time.sleep(.10)
        assert 'stooq.com' in url
        return (b'Date,Open,High,Low,Close,Volume\n'
                b'2026-11-11,100,105,98,104,100\n')
    with patch.dict(os.environ,{},clear=True):
        router=MarketRouter()
        with ThreadPoolExecutor(max_workers=4) as pool:
            responses=list(pool.map(lambda _:router.fetch('NVDA','D',getter=get),range(4)))
        assert len(count)==1,len(count)
        assert all(r['candles'][0]['close']==104 for r in responses)


if __name__=='__main__':
    test_fred_index_close_only_and_no_equity_proxy()
    test_concurrent_same_symbol_singleflight()
    print('FRED CLOSE-ONLY + SHARED REQUEST COALESCING: PASS')
