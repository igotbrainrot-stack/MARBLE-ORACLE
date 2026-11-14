"""Offline end-to-end provider fallback checks; no fabricated market history."""
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Runtime'/'Marble_Oracle_App'))
from Augurspex.augurspex.providers import (MarketRouter, ProviderError, read_nasdaq, read_alpha, _us_listing)


def nasdaq_data():
    return json.dumps({'data':{'tradesTable':{'rows':[
        {'date':'11/10/2026','open':'$150.00','high':'$159.00','low':'$148.00','close':'$155.00','volume':'1,200,000'},
        {'date':'11/11/2026','open':'$155.00','high':'$163.00','low':'$153.00','close':'$161.00','volume':'1,300,000'}
    ]}}}).encode()


@patch.dict(os.environ,{"AUGURSPEX_ALLOW_UNOFFICIAL_SOURCES":"1"})
def test_routers_no_ticker_substitution():
    assert _us_listing('NVDA')=='NVDA'
    assert _us_listing('NASDAQ:NVDA')=='NVDA'
    assert _us_listing('COH.AX') is None
    assert _us_listing('^GSPC') is None
    assert _us_listing('BTC-USD') is None
    r=MarketRouter(clock=lambda:100)
    assert r._routes('NVDA','auto')==['strasmore','stooq','nasdaq','yahoo']
    assert r._routes('COH.AX','auto')==['yahoo','stooq']
    assert r._routes('005930.KS','auto')==['naver','yahoo']
    assert r._routes('ETH-USD','auto')==['coinbase','kraken','gemini','coingecko','coinpaprika','cryptocompare']


@patch.dict(os.environ,{"AUGURSPEX_ALLOW_UNOFFICIAL_SOURCES":"1"})
def test_nasdaq_independent_fallback():
    calls=[]
    def get(url):
        calls.append(url)
        if 'ai.strasmore.com' in url:raise ProviderError('No demo rows')
        if 'stooq.com' in url:return b'N/D'
        assert 'api.nasdaq.com/api/quote/NVDA/historical' in url
        return nasdaq_data()
    r=MarketRouter(clock=lambda:100)
    result=r.fetch('NVDA','D',getter=get)
    assert result['source']=='Nasdaq.com (website history)'
    assert len(result['candles'])==2
    assert result['candles'][-1]['close']==161
    assert result['candles'][-1]['time'].startswith('2026-11-11')
    assert result['currency']=='USD'
    assert len(calls)==3
    assert any('stooq:' in issue for issue in result['provider_attempts'])
    assert r.fetch('NVDA','D',getter=lambda _url: (_ for _ in ()).throw(Exception('cache missed')))['cache']=='fresh'


@patch.dict(os.environ,{"AUGURSPEX_ALLOW_UNOFFICIAL_SOURCES":"1"})
def test_failed_first_source_does_not_hide_fresh_second():
    calls=[]
    def get(url):
        calls.append(url)
        if 'ai.strasmore.com' in url:raise ProviderError('No demo rows')
        if 'stooq.com' in url:raise ProviderError('HTTP 429; provider refused')
        assert 'api.nasdaq.com' in url
        return nasdaq_data()
    r=MarketRouter(clock=lambda:100)
    data=r.fetch('NVDA','D',getter=get)
    assert data['source'].startswith('Nasdaq')
    assert 'stooq' in r.blocked and r.blocked['stooq']>100
    assert len(calls)==3


@patch.dict(os.environ,{"AUGURSPEX_ALLOW_UNOFFICIAL_SOURCES":"1"})
def test_all_fail_uses_labelled_stale_not_invented_data():
    now=[100.0]
    def primary(url):
        if 'ai.strasmore.com' in url:raise ProviderError('No demo rows')
        if 'nasdaq.com' in url:return nasdaq_data()
        if 'ai.strasmore.com' in url:raise ProviderError('No demo rows')
        if 'stooq.com' in url:return b'N/D'
        raise ProviderError('Yahoo unavailable')
    r=MarketRouter(clock=lambda:now[0])
    real=r.fetch('NVDA','D',getter=primary)
    assert real['source'].startswith('Nasdaq')
    now[0]=100+7200
    calls=[]
    def fail(url):
        calls.append(url)
        if 'ai.strasmore.com' in url:raise ProviderError('No demo rows')
        if 'ai.strasmore.com' in url:raise ProviderError('No demo rows')
        if 'stooq.com' in url:return b'N/D'
        raise ProviderError('HTTP 429; provider refused')
    old=r.fetch('NVDA','D',getter=fail)
    assert old['cache']=='stale' and 'All current feeds failed' in old['warning']
    assert len(old['candles'])==len(real['candles'])
    assert old['source']==real['source']
    assert len(calls)==4
    now[0]=100+86400*8
    try:r.fetch('NVDA','D',getter=fail)
    except ProviderError:pass
    else:raise AssertionError('Eight-day old data must not masquerade as current history')


@patch.dict(os.environ,{"AUGURSPEX_ALLOW_UNOFFICIAL_SOURCES":"1"})
def test_optional_alpha_documented_api_and_rate_limit():
    with patch.dict(os.environ,{'AUGURSPEX_ALPHA_VANTAGE_KEY':'TEST-KEY'}):
        assert 'alpha' in MarketRouter()._routes('NVDA','auto')
        def get(url):
            assert url.startswith('https://www.alphavantage.co/query?')
            assert 'apikey=TEST-KEY' in url
            return json.dumps({'Time Series (Daily)':{
                '2026-11-11':{'1. open':'105','2. high':'109','3. low':'104','4. close':'108','5. volume':'2345'}
            }}).encode()
        data=read_alpha('NVDA','D',getter=get)
        assert data['source']=='Alpha Vantage (official API)'
        assert data['candles'][0]['close']==108
        try:read_alpha('COH.AX','D',getter=get)
        except ProviderError:pass
        else:raise AssertionError('Unverified exchange mapping accepted')
    assert 'alpha' not in MarketRouter()._routes('NVDA','auto')


@patch.dict(os.environ,{"AUGURSPEX_ALLOW_UNOFFICIAL_SOURCES":"1"})
def test_missing_provider_data_is_failure():
    try:read_nasdaq('NVDA','D',getter=lambda _url:b'{"data":{"tradesTable":{"rows":[]}}}')
    except ProviderError as exc:assert 'no history' in str(exc)
    else:raise AssertionError('Empty history was accepted')
    try:read_nasdaq('COH.AX','D',getter=lambda _url:nasdaq_data())
    except ProviderError as exc:assert 'US stock/ETF' in str(exc)
    else:raise AssertionError('Incorrect market mapping was accepted')


if __name__=='__main__':
    for name,fn in sorted(globals().items()):
        if name.startswith('test_') and callable(fn):
            fn();print(name,'PASS')
