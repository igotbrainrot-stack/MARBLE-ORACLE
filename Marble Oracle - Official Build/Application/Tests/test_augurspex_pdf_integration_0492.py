"""PDF-research integration regressions: public stock history and observation-only indicators."""
import json
import os
import sys
import unittest
from pathlib import Path

APP=Path(__file__).resolve().parents[1] / 'Runtime' / 'Marble_Oracle_App'
sys.path.insert(0,str(APP))
from Augurspex.augurspex.providers import MarketRouter, ProviderError, read_strasmore
from oracle_augurspex_signals import valid_closes, sma, rsi, market_signal_report


def payload(symbol='AAPL', n=45, as_dict=False):
    import datetime
    cols=['ticker','date','open','high','low','close','volume']
    rows=[]
    for i in range(n):
        date=(datetime.date(2026,8,1)+datetime.timedelta(days=i)).isoformat()
        row=[symbol,date,100+i,101+i,99+i,100.5+i,1000+i]
        rows.append(dict(zip(cols,row)) if as_dict else row)
    return json.dumps({'columns':cols,'rows':rows,'truncated':False}).encode()


class PDFResearchIntegration(unittest.TestCase):
    def test_no_login_source_is_eligible_for_each_curated_us_stock(self):
        router=MarketRouter()
        for sym in ('AAPL','MSFT','NVDA','AMZN','TSLA','META','GOOG','AMD','SPY','QQQ'):
            routes=router._routes(sym,'auto','D')
            self.assertIn('strasmore',routes,sym)
            self.assertIn('stooq',routes,sym)
            self.assertLess(routes.index('strasmore'),routes.index('stooq'))
        self.assertNotIn('strasmore',router._routes('FX:EURUSD','auto','D'))
        self.assertNotIn('strasmore',router._routes('BTC-USD','auto','D'))
        self.assertNotIn('strasmore',router._routes('AAPL','auto','60'))

    def test_schema_for_list_and_object_rows(self):
        for rows_as_dict in (False,True):
            urls=[]
            def getter(url):
                urls.append(url)
                return payload(as_dict=rows_as_dict)
            value=read_strasmore('AAPL','D',getter)
            self.assertEqual(len(value['candles']),45)
            self.assertEqual(value['source'],'Strasmore SQL public demo')
            self.assertEqual(value['currency'],'USD')
            self.assertTrue(value['demo_limited'])
            self.assertIn('ticker+%3D+%27AAPL%27',urls[0])
            self.assertEqual(value['candles'][0]['open'],100)
            self.assertEqual(value['candles'][-1]['close'],144.5)

    def test_week_month_grouping_not_fake_minute_candles(self):
        for period in ('W','M'):
            data=read_strasmore('MSFT',period,lambda u:payload('MSFT'))
            self.assertLess(len(data['candles']),45)
            self.assertEqual(data['interval'],period)
        with self.assertRaises(ProviderError):
            read_strasmore('AAPL','5',lambda u:payload())

    def test_symbol_identity_fail_closed(self):
        with self.assertRaises(ProviderError):
            read_strasmore('AAPL','D',lambda u:payload('MSFT'))
        with self.assertRaises(ProviderError):
            read_strasmore("AAPL' OR 1=1 --",'D',lambda u:payload())
        with self.assertRaises(ProviderError):
            read_strasmore('AAPL','D',lambda u:b'{"rows": []}')

    def test_router_fallback_on_demo_refusal(self):
        import Augurspex.augurspex.providers as mod
        orig_demo,orig_stooq=mod.read_strasmore,mod.read_stooq
        try:
            def fails(symbol,period,getter):
                raise ProviderError('HTTP 429; provider refused the request')
            def returns(symbol,period,getter):
                return {'source':'Stooq','currency':'USD','interval':'D','asset':'equity',
                        'candles':[{'time':'2026-10-30T00:00:00+00:00','open':1,'high':1,'low':1,'close':1,'volume':0}],
                        'latest_observation':'2026-10-30T00:00:00+00:00'}
            mod.read_strasmore=fails; mod.read_stooq=returns
            router=mod.MarketRouter(clock=lambda:1000)
            result=router.fetch('AAPL','D')
            self.assertEqual(result['source'],'Stooq')
            self.assertTrue(any('strasmore' in s for s in result.get('provider_attempts',[])))
        finally:
            mod.read_strasmore=orig_demo; mod.read_stooq=orig_stooq

    def test_statistics_use_only_actual_observations(self):
        candles=[{'time':f'2026-10-{i:02d}T00:00:00+00:00','close':float(i)} for i in range(1,29)]
        candles += [{'time':'not a date','close':9999}, {'time':'2026-10-30','close':float('nan')}]
        actual=valid_closes(candles)
        self.assertEqual(len(actual),28)
        close=[x[1] for x in actual]
        self.assertAlmostEqual(sma(close,20),18.5)
        self.assertEqual(rsi(close),100.)
        summary=market_signal_report('AAPL',{'source':'test provider','candles':candles})
        self.assertIn('AAPL',summary)
        self.assertIn('test provider',summary)
        self.assertNotIn('9999',summary)
        self.assertIn('RSI(14)',summary)
        self.assertIn('not predictions',summary)


if __name__=='__main__':unittest.main()
