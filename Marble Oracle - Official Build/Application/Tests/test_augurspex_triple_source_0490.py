"""Regressions for independent public-source chains and official optional stock APIs.
Run: python3 Tests/test_augurspex_triple_source_0490.py
All responses below are clearly simulated fixtures, never live price quotes.
"""
from __future__ import annotations
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

APP=Path(__file__).resolve().parents[1]/'Runtime'/'Marble_Oracle_App'
sys.path.insert(0,str(APP))
from Augurspex.augurspex import providers as p

STOCKS=['AAPL','MSFT','NVDA','AMZN','TSLA','META','GOOG','AMD','SPY','QQQ']
CRYPTO=['BTC-USD','ETH-USD','SOL-USD','XRP-USD','BNB-USD','DOGE-USD']
FX=['FX:EURUSD','FX:USDJPY','FX:GBPUSD','FX:AUDUSD','FX:USDCAD','FX:USDCHF','FX:USDAUD']

class TestThreeIndependentRoutes(unittest.TestCase):
    def test_three_source_options_each_curated_market(self):
        router=p.MarketRouter(cache_dir=None)
        for symbol in CRYPTO+FX:
            with self.subTest(market=symbol):
                routes=router._routes(symbol,'auto','D')
                self.assertGreaterEqual(len(routes),3,(symbol,routes))
                self.assertEqual(len(routes),len(set(routes)))
        for symbol in STOCKS:
            with self.subTest(market=symbol):
                # US stocks need keys for documented primary providers. With no keys,
                # only Stooq is automatic; unofficial website feeds stay opt-in.
                with patch.dict(os.environ,{
                    'AUGURSPEX_TWELVE_DATA_KEY':'fixture',
                    'AUGURSPEX_MASSIVE_KEY':'fixture',
                    'AUGURSPEX_FMP_KEY':'fixture',
                    'AUGURSPEX_ALPACA_KEY_ID':'fixture',
                    'AUGURSPEX_ALPACA_SECRET_KEY':'fixture'},clear=False):
                    routes=router._routes(symbol,'auto','D')
                    self.assertGreaterEqual(len(routes),3,(symbol,routes))
                    self.assertIn('fmp',routes)
                    self.assertIn('alpaca',routes)

    def test_unsupported_intraday_fx_not_disguised_as_daily(self):
        router=p.MarketRouter()
        self.assertEqual(router._routes('FX:USDJPY','auto','5'),[])
        with self.assertRaises(p.ProviderError):p.read_ecb_fx('FX:GBPUSD','5',lambda _:b'')
        with self.assertRaises(p.ProviderError):p.read_boc_fx('FX:GBPUSD','5',lambda _:b'')

    def test_ecb_cross_rate_same_date_with_no_missing_fill(self):
        csvdata=('KEY,CURRENCY,TIME_PERIOD,OBS_VALUE\n'
                 'EXR,USD,2026-11-10,1.20\n'
                 'EXR,JPY,2026-11-10,180\n'
                 'EXR,USD,2026-11-11,1.21\n'
                 'EXR,JPY,2026-11-12,181\n')
        urls=[]
        def getter(url):urls.append(url);return csvdata.encode()
        result=p.read_ecb_fx('FX:USDJPY','D',getter)
        self.assertEqual(result['currency'],'JPY')
        self.assertEqual(len(result['candles']),1)
        self.assertAlmostEqual(result['candles'][0]['close'],150.0)
        self.assertTrue(result['candles'][0]['close_only'])
        self.assertIn('JPY+USD',urls[0])

    def test_boc_cross_rate_and_cad_direct(self):
        data={'observations':[
            {'d':'2026-11-09','FXUSDCAD':{'v':'1.40'},'FXEURCAD':{'v':'1.68'}},
            {'d':'2026-11-10','FXUSDCAD':{'v':'1.50'},'FXEURCAD':{'v':'1.80'}}]}
        result=p.read_boc_fx('FX:EURUSD','D',lambda _:json.dumps(data).encode())
        self.assertEqual(len(result['candles']),2)
        self.assertAlmostEqual(result['candles'][0]['close'],1.20)
        cad=p.read_boc_fx('FX:USDCAD','D',lambda _:json.dumps(data).encode())
        self.assertAlmostEqual(cad['candles'][0]['close'],1.40)

    def test_fx_failover_skips_refused_frankfurter(self):
        router=p.MarketRouter(cache_dir=None)
        def failing(*_):raise p.ProviderError('HTTP 429; temporarily rate limited')
        payload=(b'CURRENCY,TIME_PERIOD,OBS_VALUE\nUSD,2026-11-10,1.2\n')
        with patch.object(p,'read_frankfurter_history',side_effect=failing):
            result=router.fetch('FX:EURUSD','D',getter=lambda _:payload)
        self.assertEqual(result['source'],'ECB (daily reference / EUR cross)')
        self.assertTrue(any('frankfurter-history' in x for x in result['provider_attempts']))

    def test_gemini_verified_pairs_and_actual_candles(self):
        for sym in p.GEMINI_USD:
            with self.subTest(sym=sym):
                bars=[[1794268800000,10,12,9,11,100],[1794355200000,11,13,10,12,80]]
                result=p.read_gemini(sym,'D',lambda _:json.dumps(bars).encode())
                self.assertEqual(len(result['candles']),2)
                self.assertEqual(result['candles'][1]['high'],13)
                self.assertEqual(result['source'],'Gemini Exchange')

    def test_cryptocompare_bnb_true_aggregated_ohlc(self):
        response={'Response':'Success','Data':{'ConversionType':{'type':'direct'},
            'Data':[{'time':1794268800,'open':1000,'high':1020,'low':990,'close':1005,'volumefrom':100},
                    {'time':1794355200,'open':1005,'high':1050,'low':1000,'close':1020,'volumefrom':200}]}}
        urls=[]
        def getter(u):urls.append(u);return json.dumps(response).encode()
        data=p.read_cryptocompare('BNB-USD','D',getter)
        self.assertTrue(data['aggregated_market'])
        self.assertEqual(data['candles'][0]['high'],1020)
        self.assertIn('tryConversion=false',urls[0])
        response['Data']['ConversionType']['type']='multiply'
        with self.assertRaisesRegex(p.ProviderError,'synthetic pair conversion'):
            p.read_cryptocompare('BNB-USD','D',getter)

    def test_fmp_and_alpaca_bars_require_personal_credentials(self):
        with patch.dict(os.environ,{'AUGURSPEX_FMP_KEY':'fixture','AUGURSPEX_ALPACA_KEY_ID':'id-fixture',
                                     'AUGURSPEX_ALPACA_SECRET_KEY':'secret-fixture'}):
            fmp=[{'symbol':'NVDA','date':'2026-11-10','open':120,'high':123,'low':119,'close':121,'volume':1000}]
            result=p.read_fmp('NVDA','D',lambda _:json.dumps(fmp).encode())
            self.assertEqual(result['candles'][0]['close'],121)
            def getter(url,headers):
                assert headers['APCA-API-KEY-ID']=='id-fixture'
                assert headers['APCA-API-SECRET-KEY']=='secret-fixture'
                return json.dumps({'bars':[{'t':'2026-11-10T00:00:00Z','o':10,'h':12,'l':9,'c':11,'v':100}]}).encode()
            result=p.read_alpaca('AAPL','D',getter)
            self.assertEqual(result['candles'][0]['close'],11)
            self.assertIn('IEX',result['source'])

if __name__=='__main__':unittest.main()
