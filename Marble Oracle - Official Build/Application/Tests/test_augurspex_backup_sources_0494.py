"""0.4.9.4: Stooq key handling and the added backup market-data sources.

    python3 Application/Tests/test_augurspex_backup_sources_0494.py

Needs no display and no network. Every transport is a local fake and every
"price" is an obviously synthetic fixture shaped like the provider's
documented reply. These tests prove the adapters parse, validate, label and
route correctly; they cannot prove a provider answers today. Use
Tools/probe_providers.py from a real connection for that.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

APP = Path(__file__).resolve().parents[1] / 'Runtime' / 'Marble_Oracle_App'
sys.path.insert(0, str(APP))

from Augurspex.augurspex import providers  # noqa: E402
from Augurspex.augurspex.providers import (  # noqa: E402
    MarketRouter, ProviderError, SOURCE_INFO, CACHE_TTL, eodhd_code, read_binance, read_bitfinex,
    read_bitstamp, read_coinbase_adv, read_datagokr, read_eodhd, read_stooq, read_tiingo,
)

NEW_KEYS = ('AUGURSPEX_STOOQ_KEY', 'AUGURSPEX_TIINGO_KEY', 'AUGURSPEX_EODHD_KEY', 'AUGURSPEX_DATA_GO_KR_KEY')
NOW = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)


def day(back):
    return (NOW - timedelta(days=back)).date().isoformat()


def stamp(back):
    return int((NOW - timedelta(days=back)).timestamp())


def bars(count=40):
    """(days back, open, high, low, close, volume) - synthetic TEST values."""
    return [(count - i, 100 + i, 103 + i, 99 + i, 101 + i, 1000 + i) for i in range(count)]


class CleanEnvironment(unittest.TestCase):
    def setUp(self):
        self._saved = {k: v for k, v in os.environ.items() if k.startswith('AUGURSPEX_')}
        for name in self._saved:
            del os.environ[name]

    def tearDown(self):
        for name in [k for k in os.environ if k.startswith('AUGURSPEX_')]:
            del os.environ[name]
        os.environ.update(self._saved)


class StooqKey(CleanEnvironment):
    CSV = 'Date,Open,High,Low,Close,Volume\n' + '\n'.join(
        f'{day(b)},{o},{h},{l},{c},{v}' for b, o, h, l, c, v in bars())

    def test_keyless_instruction_page_is_a_missing_key_not_no_data(self):
        page = b'Get your apikey:\n\n1. Open https://stooq.com/q/d/?s=aapl.us&get_apikey\n2. Enter the captcha code.'
        with self.assertRaises(ProviderError) as caught:
            read_stooq('AAPL', 'D', lambda url: page)
        self.assertEqual(caught.exception.kind, 'auth')
        self.assertIn('free personal key', str(caught.exception))
        self.assertNotIn('http', str(caught.exception).lower())

    def test_rejected_key_says_so(self):
        os.environ['AUGURSPEX_STOOQ_KEY'] = 'TESTKEY123'
        with self.assertRaises(ProviderError) as caught:
            read_stooq('AAPL', 'D', lambda url: b'Get your apikey: ...')
        self.assertEqual(caught.exception.kind, 'auth')
        self.assertIn('not accepted', str(caught.exception))
        self.assertNotIn('TESTKEY123', str(caught.exception))

    def test_key_is_sent_and_csv_parsed(self):
        os.environ['AUGURSPEX_STOOQ_KEY'] = 'TESTKEY123'
        seen = []

        def getter(url):
            seen.append(url)
            return self.CSV.encode()
        result = read_stooq('RMD.AX', 'D', getter)
        query = parse_qs(urlparse(seen[0]).query)
        self.assertEqual(query['apikey'], ['TESTKEY123'])
        self.assertEqual(query['s'], ['rmd.au'])
        self.assertEqual((result['source'], result['currency'], len(result['candles'])), ('Stooq', 'AUD', 40))

    def test_no_key_parameter_without_a_key(self):
        seen = []
        read_stooq('AAPL', 'D', lambda url: seen.append(url) or self.CSV.encode())
        self.assertNotIn('apikey', seen[0])

    def test_router_stops_resending_after_key_page(self):
        calls = []
        with tempfile.TemporaryDirectory() as cache:
            router = MarketRouter(cache_dir=cache)
            router._routes = lambda *a, **k: ['stooq']
            for _ in range(3):
                with self.assertRaises(ProviderError):
                    router.fetch('AAPL', 'D', getter=lambda url: calls.append(url) or b'Get your apikey: x')
            self.assertEqual(len(calls), 1, 'a missing key must start a cool-down, not a request per refresh')
            # Entering a key ends the wait: the very next refresh asks again.
            os.environ['AUGURSPEX_STOOQ_KEY'] = 'TESTKEY123'
            router.credentials_changed()
            result = router.fetch('AAPL', 'D', getter=lambda url: calls.append(url) or self.CSV.encode())
            self.assertEqual((len(calls), result['source']), (2, 'Stooq'))
            self.assertIn('apikey=TESTKEY123', calls[1])


class KeyedStockSources(CleanEnvironment):
    def test_tiingo_sends_key_in_header_only(self):
        os.environ['AUGURSPEX_TIINGO_KEY'] = 'TIINGOSECRET'
        seen = []
        payload = [{'date': day(b) + 'T00:00:00.000Z', 'open': o, 'high': h, 'low': l, 'close': c, 'volume': v,
                    'adjClose': c / 2} for b, o, h, l, c, v in bars()]

        def getter(url, headers):
            seen.append((url, headers))
            return json.dumps(payload).encode()
        result = read_tiingo('NASDAQ:NVDA', 'D', getter)
        url, headers = seen[0]
        self.assertNotIn('TIINGOSECRET', url)
        self.assertEqual(headers, {'Authorization': 'Token TIINGOSECRET'})
        self.assertIn('/tiingo/daily/nvda/prices', url)
        self.assertEqual(result['candles'][-1]['close'], 140.0, 'raw close, not the adjusted one')
        self.assertEqual(result['currency'], 'USD')

    def test_tiingo_error_object_and_missing_key(self):
        with self.assertRaises(ProviderError) as caught:
            read_tiingo('AAPL', 'D', lambda url, headers: b'[]')
        self.assertEqual(caught.exception.kind, 'not_configured')
        os.environ['AUGURSPEX_TIINGO_KEY'] = 'k'
        with self.assertRaises(ProviderError) as caught:
            read_tiingo('AAPL', 'D', lambda url, headers: b'{"detail":"Invalid token."}')
        self.assertIn('Invalid token', str(caught.exception))
        with self.assertRaises(ProviderError):
            read_tiingo('RMD.AX', 'D', lambda url, headers: b'[]')

    def test_real_transport_accepts_the_authorization_header(self):
        # get_bytes must not refuse Tiingo's header (the Alpaca defect of 0.4.9.2).
        original = providers.urlopen
        captured = {}

        class Reply:
            def __enter__(self): return self
            def __exit__(self, *exc): return False
            def read(self, n): return b'[]'

        def fake_urlopen(request, timeout=0):
            captured.update(request.header_items())
            return Reply()
        providers.urlopen = fake_urlopen
        try:
            providers.get_bytes(providers.URL_TIINGO + 'aapl/prices', extra_headers={'Authorization': 'Token x'})
        finally:
            providers.urlopen = original
        self.assertEqual(captured.get('Authorization'), 'Token x')

    def test_eodhd_codes_keep_the_same_listing(self):
        self.assertEqual(eodhd_code('RMD.AX'), ('RMD.AU', 'AUD'))
        self.assertEqual(eodhd_code('4568.T'), ('4568.TSE', 'JPY'))
        self.assertEqual(eodhd_code('005930.KS'), ('005930.KO', 'KRW'))
        self.assertEqual(eodhd_code('035720.KQ'), ('035720.KQ', 'KRW'))
        self.assertEqual(eodhd_code('^GSPC'), ('GSPC.INDX', 'USD'))
        self.assertEqual(eodhd_code('NASDAQ:NVDA'), ('NVDA.US', 'USD'))
        self.assertEqual(eodhd_code('BRK.B'), ('BRK-B.US', 'USD'))
        self.assertEqual(eodhd_code('BTC-USD')[0] in (None, 'BTC-USD.US'), True)

    def test_eodhd_parses_and_never_leaks_key(self):
        os.environ['AUGURSPEX_EODHD_KEY'] = 'EODSECRET'
        seen = []
        payload = [{'date': day(b), 'open': o, 'high': h, 'low': l, 'close': c, 'adjusted_close': c, 'volume': v}
                   for b, o, h, l, c, v in bars()]
        result = read_eodhd('CSL.AX', 'W', lambda url: seen.append(url) or json.dumps(payload).encode())
        self.assertIn('/api/eod/CSL.AU?', seen[0])
        self.assertEqual(result['currency'], 'AUD')
        self.assertLess(len(result['candles']), 40, 'weekly bars are aggregated from real daily bars')
        self.assertEqual(read_eodhd('^IXIC', 'D', lambda url: json.dumps(payload).encode())['asset'], 'index')
        with tempfile.TemporaryDirectory() as cache:
            router = MarketRouter(cache_dir=cache)
            with self.assertRaises(ProviderError) as caught:
                router.fetch('CSL.AX', 'D', 'eodhd', getter=lambda url: b'"Unauthenticated EODSECRET"')
        self.assertNotIn('EODSECRET', str(caught.exception))
        with self.assertRaises(ProviderError):
            read_eodhd('CSL.AX', '60', lambda url: b'[]')

    def test_datagokr_accepts_only_the_exact_listing(self):
        os.environ['AUGURSPEX_DATA_GO_KR_KEY'] = 'KRSECRET'
        items = [{'basDt': (NOW - timedelta(days=b)).strftime('%Y%m%d'), 'srtnCd': '005930', 'mkp': str(o * 500),
                  'hipr': str(h * 500), 'lopr': str(l * 500), 'clpr': str(c * 500), 'trqu': str(v)}
                 for b, o, h, l, c, v in bars(20)]
        items.append({'basDt': (NOW - timedelta(days=1)).strftime('%Y%m%d'), 'srtnCd': '005935', 'mkp': '1',
                      'hipr': '2', 'lopr': '1', 'clpr': '2', 'trqu': '5'})   # preferred share: different listing
        body = {'response': {'header': {'resultCode': '00'}, 'body': {'items': {'item': items}, 'totalCount': 21}}}
        result = read_datagokr('005930.KS', 'D', lambda url: json.dumps(body).encode())
        self.assertEqual((len(result['candles']), result['currency']), (20, 'KRW'))
        self.assertEqual(result['candles'][-1]['close'], 120 * 500.0)
        with self.assertRaises(ProviderError) as caught:
            read_datagokr('005930.KS', 'D', lambda url: b'<OpenAPI_ServiceResponse>SERVICE_KEY_IS_NOT_REGISTERED_ERROR</OpenAPI_ServiceResponse>')
        self.assertNotIn('KRSECRET', str(caught.exception))
        with self.assertRaises(ProviderError):
            read_datagokr('AAPL', 'D', lambda url: b'{}')


class CryptoVenues(CleanEnvironment):
    def test_coinbase_advanced(self):
        payload = {'candles': [{'start': str(stamp(b)), 'low': str(l), 'high': str(h), 'open': str(o),
                                'close': str(c), 'volume': str(v)} for b, o, h, l, c, v in reversed(bars())]}
        seen = []
        result = read_coinbase_adv('BTC-USD', 'D', lambda url: seen.append(url) or json.dumps(payload).encode())
        self.assertIn('/market/products/BTC-USD/candles?', seen[0])
        self.assertIn('granularity=ONE_DAY', seen[0])
        self.assertEqual((result['currency'], len(result['candles'])), ('USD', 40))
        self.assertEqual(result['candles'][-1]['close'], 140.0)

    def test_bitstamp(self):
        payload = {'data': {'pair': 'ETH/USD', 'ohlc': [
            {'timestamp': str(stamp(b)), 'open': str(o), 'high': str(h), 'low': str(l), 'close': str(c),
             'volume': str(v)} for b, o, h, l, c, v in bars()]}}
        seen = []
        result = read_bitstamp('ETH-USD', 'D', lambda url: seen.append(url) or json.dumps(payload).encode())
        self.assertIn('/ohlc/ethusd/?step=86400', seen[0])
        self.assertEqual((result['source'], result['currency'], len(result['candles'])), ('Bitstamp', 'USD', 40))
        with self.assertRaises(ProviderError):
            read_bitstamp('BNB-USD', 'D', lambda url: b'{}')

    def test_bitfinex_column_order_is_open_close_high_low(self):
        payload = [[stamp(b) * 1000, o, c, h, l, v] for b, o, h, l, c, v in reversed(bars())]
        seen = []
        result = read_bitfinex('BTC-USD', 'D', lambda url: seen.append(url) or json.dumps(payload).encode())
        self.assertIn('trade:1D:tBTCUSD/hist', seen[0])
        last = result['candles'][-1]
        self.assertEqual((last['open'], last['high'], last['low'], last['close']), (139.0, 142.0, 138.0, 140.0))
        with self.assertRaises(ProviderError):
            read_bitfinex('BTC-USD', 'D', lambda url: b'["error",10020,"limit: invalid"]')

    def test_binance_is_labelled_usdt_never_usd(self):
        payload = [[stamp(b) * 1000, str(o), str(h), str(l), str(c), str(v), 0, '0', 1, '0', '0', '0']
                   for b, o, h, l, c, v in bars()]
        seen = []
        result = read_binance('BTC-USD', 'D', lambda url: seen.append(url) or json.dumps(payload).encode())
        self.assertIn('data-api.binance.vision', seen[0])
        self.assertIn('symbol=BTCUSDT', seen[0])
        self.assertEqual(result['currency'], 'USDT')
        self.assertEqual(result['source'], 'Binance BTC/USDT')
        self.assertEqual(result['quote_substitute'], 'USDT')
        self.assertIn('NOT US dollars', result['note'])

    def test_bad_rows_are_dropped_not_invented(self):
        payload = {'data': {'ohlc': [
            {'timestamp': str(stamp(3)), 'open': '0', 'high': '0', 'low': '0', 'close': '0', 'volume': '0'},
            {'timestamp': str(stamp(2)), 'open': '10', 'high': '9', 'low': '8', 'close': '9.5', 'volume': '1'},
            {'timestamp': 'x', 'open': '10', 'high': '11', 'low': '9', 'close': '10', 'volume': '1'},
            {'timestamp': str(stamp(1)), 'open': '10', 'high': '11', 'low': '9', 'close': '10', 'volume': '1'}]}}
        result = read_bitstamp('BTC-USD', 'D', lambda url: json.dumps(payload).encode())
        self.assertEqual(len(result['candles']), 1)


class Routing(CleanEnvironment):
    def routes(self, symbol, period='D'):
        return MarketRouter()._routes(symbol, 'auto', period)

    def test_crypto_order_true_usd_then_aggregates_then_usdt(self):
        self.assertEqual(self.routes('BTC-USD'),
                         ['coinbase', 'kraken', 'bitstamp', 'gemini', 'bitfinex', 'coinbase-adv',
                          'coingecko', 'coinpaprika', 'binance'])
        self.assertEqual(self.routes('DOGE-USD', '5'),
                         ['coinbase', 'kraken', 'bitstamp', 'gemini', 'coinbase-adv', 'binance'])
        self.assertEqual(self.routes('BNB-USD'), ['coingecko', 'coinpaprika', 'binance'])
        self.assertEqual(self.routes('BNB-USD', '5'), ['binance'], 'BNB gains real intraday candles, labelled USDT')

    def test_no_new_stock_route_without_a_key(self):
        for symbol in ('RMD.AX', '4568.T', '005930.KS', '^GSPC'):
            self.assertEqual(self.routes(symbol), [], symbol)
        self.assertEqual(self.routes('AAPL'), ['strasmore', 'stooq'])

    def test_keys_unlock_asx_tokyo_korea_and_indices(self):
        os.environ['AUGURSPEX_STOOQ_KEY'] = 'a'
        self.assertEqual(self.routes('RMD.AX'), ['stooq'])
        self.assertEqual(self.routes('4568.T'), ['stooq'])
        self.assertEqual(self.routes('^GSPC'), ['stooq'])
        self.assertEqual(self.routes('RMD.AX', '60'), [], 'Stooq is daily only')
        os.environ['AUGURSPEX_EODHD_KEY'] = 'b'
        self.assertEqual(self.routes('RMD.AX'), ['stooq', 'eodhd'])
        self.assertEqual(self.routes('005930.KS'), ['eodhd'])
        os.environ['AUGURSPEX_DATA_GO_KR_KEY'] = 'c'
        self.assertEqual(self.routes('005930.KS'), ['datagokr', 'eodhd'])
        os.environ['AUGURSPEX_TIINGO_KEY'] = 'd'
        self.assertEqual(self.routes('AAPL'), ['tiingo', 'eodhd', 'strasmore', 'stooq'])
        os.environ['AUGURSPEX_ALLOW_UNOFFICIAL_SOURCES'] = '1'
        self.assertEqual(self.routes('RMD.AX').count('stooq'), 1, 'no duplicate route')

    def test_usd_series_is_preferred_and_usdt_only_when_usd_venues_fail(self):
        good = {'data': {'ohlc': [{'timestamp': str(stamp(b)), 'open': str(o), 'high': str(h), 'low': str(l),
                                   'close': str(c), 'volume': str(v)} for b, o, h, l, c, v in bars()]}}
        klines = [[stamp(b) * 1000, str(o), str(h), str(l), str(c), str(v)] for b, o, h, l, c, v in bars()]

        def getter(url, *headers):
            if 'bitstamp' in url:
                return json.dumps(good).encode()
            if 'binance' in url:
                return json.dumps(klines).encode()
            raise ProviderError('HTTP 503; provider is having problems', kind='provider_failure')
        with tempfile.TemporaryDirectory() as cache:
            router = MarketRouter(cache_dir=cache)
            router.last_call = {}
            import Augurspex.augurspex.providers as module
            real_sleep, module.time.sleep = module.time.sleep, lambda s: None
            try:
                first = router.fetch('BTC-USD', 'D', getter=getter)
                self.assertEqual((first['source'], first['currency']), ('Bitstamp', 'USD'))
                self.assertEqual([a.split(':')[0] for a in first['provider_attempts']], ['coinbase', 'kraken'])

                def only_binance(url, *headers):
                    if 'binance' in url:
                        return json.dumps(klines).encode()
                    raise ProviderError('HTTP 503; provider is having problems', kind='provider_failure')
                other = MarketRouter(cache_dir=tempfile.mkdtemp())
                last = other.fetch('BTC-USD', 'D', getter=only_binance)
                self.assertEqual((last['source'], last['currency']), ('Binance BTC/USDT', 'USDT'))
                self.assertEqual(len(last['provider_attempts']), 8)
            finally:
                module.time.sleep = real_sleep

    def test_every_route_has_metadata_reader_and_cache_rule(self):
        for name in ('tiingo', 'eodhd', 'datagokr', 'coinbase-adv', 'bitstamp', 'bitfinex', 'binance'):
            self.assertIn(name, SOURCE_INFO)
            self.assertIn(name, CACHE_TTL)
            self.assertEqual(MarketRouter()._routes('BTC-USD', name), [name])
        self.assertIn('USDT', SOURCE_INFO['binance']['coverage'])
        self.assertIn('AUGURSPEX_STOOQ_KEY', SOURCE_INFO['stooq']['coverage'])

    def test_plan_shows_what_a_free_key_would_unlock(self):
        plan = MarketRouter().provider_plan('RMD.AX', 'D')
        self.assertEqual([row['id'] for row in plan], ['stooq', 'eodhd', 'twelve'])
        self.assertFalse(any(row['active'] for row in plan))
        os.environ['AUGURSPEX_STOOQ_KEY'] = 'a'
        plan = MarketRouter().provider_plan('RMD.AX', 'D')
        self.assertTrue(plan[0]['active'])


if __name__ == '__main__':
    unittest.main(verbosity=1)
