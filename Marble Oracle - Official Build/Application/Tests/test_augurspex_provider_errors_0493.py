"""0.4.9.3: provider failure states, transport safety, cache bounds and chart logic.

    python3 Application/Tests/test_augurspex_provider_errors_0493.py

Needs no display and no network: transports are replaced by local fakes and
every "price" is an obviously synthetic fixture. Covers defects found in the
0.4.9.2 audit:

* the real transport refused Alpaca's two credential headers, so the Alpaca
  adapter could never work outside a test double;
* HTTP 401 / 403 / 404 / 429 / 5xx all read "provider refused the request";
* an HTML challenge page surfaced as "Expecting value: line 1 column 1";
* an unexpected reply shape leaked a raw Python error and escaped the router;
* a rejected API key was re-sent on every refresh (no cool-down);
* a zero "price" was accepted as an observation;
* sources added after 0.4.7.8 (Strasmore, Gemini, FMP, Alpaca, ECB, BoC…)
  were silently missing from the visible SOURCES line;
* the on-disk history cache grew without limit;
* date labels could overlap, and sub-cent prices were labelled 0.0000.
"""
from __future__ import annotations

import csv
import io
import json
import os
import sys
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from email.message import Message
from pathlib import Path
from urllib.error import HTTPError, URLError

APP = Path(__file__).resolve().parents[1] / 'Runtime' / 'Marble_Oracle_App'
sys.path.insert(0, str(APP))

from Augurspex.augurspex import providers  # noqa: E402
from Augurspex.augurspex.providers import (  # noqa: E402
    ERROR_KINDS, MarketRouter, ProviderError, SOURCE_INFO, candle, classify_error_text, error_kind,
    local_stock_path, read_alpaca, read_local_stock_csv, read_stooq, split_attempts,
)
import oracle_augurspex_logic as logic  # noqa: E402

KEY_NAMES = [name for name in os.environ if name.startswith('AUGURSPEX_')]


def day(back):
    return (datetime.now(timezone.utc).date() - timedelta(days=back)).isoformat()


def stooq_csv(rows=5):
    lines = ['Date,Open,High,Low,Close,Volume']
    for i in range(rows, 0, -1):
        lines.append(f'{day(i)},10,12,9,11,1000')
    return ('\n'.join(lines) + '\n').encode()


class FakeResponse:
    def __init__(self, body=b'{}'):
        self.body = body

    def read(self, _limit=-1):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False


class Transport(unittest.TestCase):
    """get_bytes(): what the provider's HTTP status really means."""

    def setUp(self):
        self.original = providers.urlopen
        self.saved_env = {name: os.environ.pop(name) for name in list(os.environ) if name.startswith('AUGURSPEX_')}

    def tearDown(self):
        providers.urlopen = self.original
        for name in list(os.environ):
            if name.startswith('AUGURSPEX_'):
                del os.environ[name]
        os.environ.update(self.saved_env)

    def fail_with(self, code):
        def opener(request, timeout=None):
            raise HTTPError(request.full_url, code, 'x', Message(), io.BytesIO(b'secret upstream body'))
        providers.urlopen = opener

    def test_http_status_kinds(self):
        expected = {401: 'auth', 403: 'refused', 404: 'unsupported', 429: 'rate_limited',
                    500: 'provider_failure', 503: 'provider_failure', 418: 'refused'}
        for code, kind in expected.items():
            self.fail_with(code)
            with self.assertRaises(ProviderError) as caught:
                providers.get_bytes(providers.URL_STOOQ + '?s=aapl.us')
            self.assertEqual(caught.exception.kind, kind, code)
            self.assertIn(f'HTTP {code}', str(caught.exception))
            self.assertNotIn('stooq.com', str(caught.exception))
            self.assertNotIn('secret upstream body', str(caught.exception))

    def test_network_failure_kind_and_no_url(self):
        def opener(request, timeout=None):
            raise URLError('[Errno -3] Temporary failure in name resolution')
        providers.urlopen = opener
        with self.assertRaises(ProviderError) as caught:
            providers.get_bytes(providers.URL_STOOQ + '?s=aapl.us')
        self.assertEqual(caught.exception.kind, 'network')
        self.assertNotIn('http', str(caught.exception).lower().replace('network problem', ''))

    def test_oversized_body_is_rejected(self):
        providers.urlopen = lambda request, timeout=None: FakeResponse(b'x' * (providers.MAX_BODY + 5))
        with self.assertRaises(ProviderError) as caught:
            providers.get_bytes(providers.URL_STOOQ)
        self.assertEqual(caught.exception.kind, 'invalid_response')

    def test_alpaca_headers_reach_the_real_transport(self):
        """0.4.9.2 raised 'Unsupported custom provider header' before any request."""
        seen = {}

        def opener(request, timeout=None):
            seen['headers'] = {k.lower(): v for k, v in request.header_items()}
            seen['url'] = request.full_url
            bars = [{'t': day(2) + 'T05:00:00Z', 'o': 10, 'h': 12, 'l': 9, 'c': 11, 'v': 5},
                    {'t': day(1) + 'T05:00:00Z', 'o': 11, 'h': 13, 'l': 10, 'c': 12, 'v': 6}]
            return FakeResponse(json.dumps({'bars': bars}).encode())
        providers.urlopen = opener
        os.environ['AUGURSPEX_ALPACA_KEY_ID'] = 'TEST-KEY-ID'
        os.environ['AUGURSPEX_ALPACA_SECRET_KEY'] = 'TEST-SECRET'
        result = read_alpaca('NASDAQ:AAPL', 'D')
        self.assertEqual(len(result['candles']), 2)
        self.assertEqual(seen['headers'].get('apca-api-key-id'), 'TEST-KEY-ID')
        self.assertEqual(seen['headers'].get('apca-api-secret-key'), 'TEST-SECRET')
        self.assertNotIn('TEST-SECRET', seen['url'])
        self.assertNotIn('TEST-KEY-ID', seen['url'])

    def test_unknown_custom_header_is_still_refused(self):
        with self.assertRaises(ProviderError):
            providers.get_bytes(providers.URL_STOOQ, extra_headers={'Cookie': 'x'})


class Classification(unittest.TestCase):
    def test_kinds_for_real_messages(self):
        cases = {
            'HTTP 429; provider rate limit reached': 'rate_limited',
            'HTTP 429; provider refused the request': 'rate_limited',
            'Stooq quota or HTML challenge; automated history temporarily blocked': 'rate_limited',
            'Alpha Vantage rate or plan limit': 'rate_limited',
            'HTTP 401; provider rejected the credentials': 'auth',
            'Twelve Data credential denied (code 401)': 'auth',
            'KRX authentication, approval or rate limit denied': 'rate_limited',
            'Massive denied request or plan entitlement': 'auth',
            'HTTP 403; provider refused the request': 'refused',
            'cooling down (retry in 840s)': 'cooldown',
            'Network problem: timed out': 'network',
            'HTTP 503; provider is having problems': 'provider_failure',
            'HTTP 404; provider has no such listing or endpoint': 'unsupported',
            'Stooq mapping unavailable for this listing': 'unsupported',
            'Strasmore demo adapter supplies daily bars, not intraday bars': 'unsupported',
            'Stooq returned no history for this listing: aapl.us: no CSV': 'no_data',
            'Kraken supplied no usable candles': 'no_data',
            'Yahoo chart returned a different listing': 'invalid_response',
            'Kraken reply was not valid JSON': 'invalid_response',
            'FRED API key not configured': 'not_configured',
            'Network disabled for this run': 'offline',
            '': 'unknown',
            'something nobody anticipated': 'unknown',
        }
        for message, kind in cases.items():
            self.assertEqual(classify_error_text(message), kind, message)
            self.assertIn(kind, ERROR_KINDS)

    def test_overall_kind_prefers_the_actionable_reason(self):
        text = 'strasmore: Strasmore demo returned no valid matching daily bars | stooq: HTTP 429; provider rate limit reached'
        self.assertEqual(error_kind(text), 'rate_limited')
        self.assertEqual(error_kind('stooq: Stooq returned no history | strasmore: Network problem: timed out'), 'network')
        self.assertEqual(error_kind(ProviderError('x', kind='auth')), 'auth')

    def test_attempts_split_knows_every_router_source(self):
        text = ' | '.join(f'{name}: HTTP 429; provider rate limit reached' for name in SOURCE_INFO)
        names = [name for name, _message in split_attempts(text)]
        self.assertEqual(names, list(SOURCE_INFO))
        # A colon inside a free-text error is not mistaken for a provider name.
        self.assertEqual(split_attempts('Imported stock CSV invalid: CSV needs a header'),
                         [('', 'Imported stock CSV invalid: CSV needs a header')])


class Router(unittest.TestCase):
    def setUp(self):
        self.saved_env = {name: os.environ.pop(name) for name in list(os.environ) if name.startswith('AUGURSPEX_')}
        self.now = [1_800_000_000.0]
        self.sleep = providers.time.sleep
        providers.time.sleep = lambda _seconds: None

    def tearDown(self):
        providers.time.sleep = self.sleep
        for name in list(os.environ):
            if name.startswith('AUGURSPEX_'):
                del os.environ[name]
        os.environ.update(self.saved_env)

    def router(self, **kw):
        return MarketRouter(clock=lambda: self.now[0], **kw)

    def test_all_sources_failed_reports_each_attempt_with_a_kind(self):
        def getter(url, *_a):
            if 'strasmore' in url:
                raise ProviderError('HTTP 429; provider rate limit reached', kind='rate_limited')
            return b'N/D'
        with self.assertRaises(ProviderError) as caught:
            self.router().fetch('NASDAQ:AAPL', 'D', getter=getter)
        error = caught.exception
        self.assertEqual([a['provider'] for a in error.attempts], ['strasmore', 'stooq'])
        self.assertEqual([a['kind'] for a in error.attempts], ['rate_limited', 'no_data'])
        self.assertEqual(error.kind, 'rate_limited')
        self.assertEqual(logic.status_for_error(str(error), 'NASDAQ:AAPL'), 'STOCK FEED LIMITED')
        self.assertEqual(logic.provider_diagnostics(str(error)), 'STRASMORE LIMITED · STOOQ NO HISTORY')

    def test_html_challenge_page_is_named_not_a_json_error(self):
        def getter(url, *_a):
            return b'<!DOCTYPE html><html><body>Checking your browser</body></html>'
        with self.assertRaises(ProviderError) as caught:
            self.router().fetch('BTC-USD', '60', getter=getter)
        text = str(caught.exception)
        self.assertNotIn('Expecting value', text)
        self.assertIn('web page instead of data', text)
        self.assertEqual(caught.exception.kind, 'rate_limited')

    def test_unexpected_reply_shape_never_leaks_a_python_error(self):
        def getter(url, *_a):
            return b'["not", "an", "object"]'
        with self.assertRaises(ProviderError) as caught:
            self.router().fetch('BTC-USD', '1', getter=getter)
        text = str(caught.exception)
        for leak in ("object has no attribute", 'Traceback', "'list'", 'NoneType'):
            self.assertNotIn(leak, text)
        self.assertTrue(all(a['kind'] in ERROR_KINDS for a in caught.exception.attempts))

    def test_rejected_key_is_not_resent_on_every_refresh(self):
        os.environ['AUGURSPEX_FMP_KEY'] = 'FMP-TEST-KEY-123456'
        calls = []

        def getter(url, *_a):
            calls.append(url)
            if 'financialmodelingprep' in url:
                raise ProviderError('HTTP 401; provider rejected the credentials', kind='auth')
            if 'strasmore' in url:
                raise ProviderError('Network problem: timed out', kind='network')
            return stooq_csv()
        router = self.router()
        first = router.fetch('NASDAQ:AAPL', 'D', getter=getter)
        self.assertEqual(first['source'], 'Stooq')
        self.assertEqual(first['provider_attempts_detail'][0], {
            'provider': 'fmp', 'kind': 'auth', 'message': 'HTTP 401; provider rejected the credentials'})
        fmp_calls = sum('financialmodelingprep' in url for url in calls)
        self.assertEqual(fmp_calls, 1)
        # A different market a minute later: the rejected key is left alone.
        self.now[0] += 60
        router.fetch('NASDAQ:MSFT', 'D', getter=getter)
        self.assertEqual(sum('financialmodelingprep' in url for url in calls), 1)
        # ...and tried again once the cool-down has passed.
        self.now[0] += providers.PROVIDER_COOLDOWN + 1
        router.fetch('NASDAQ:NVDA', 'D', getter=getter)
        self.assertEqual(sum('financialmodelingprep' in url for url in calls), 2)

    def test_a_source_that_needs_a_key_is_not_tried_without_one(self):
        # CoinDesk Data answered HTTP 401 to every keyless request in the live
        # probe of 15 Nov 2026, so it is a route only once a key is configured.
        router = MarketRouter(cache_dir=None)
        self.assertNotIn('cryptocompare', router._routes('BTC-USD', 'auto', 'D'))
        self.assertNotIn('cryptocompare', router._routes('BNB-USD', 'auto', 'D'))
        plan = {row['id']: row for row in router.provider_plan('BNB-USD', 'D')}
        self.assertFalse(plan['cryptocompare']['active'])
        self.assertIn('API KEY', plan['cryptocompare']['status'])
        os.environ['AUGURSPEX_CRYPTOCOMPARE_KEY'] = 'CC-TEST-KEY'
        self.assertEqual(router._routes('BNB-USD', 'auto', 'D')[-1], 'cryptocompare')
        self.assertEqual(router._routes('BTC-USD', 'auto', '5'), ['coinbase', 'kraken', 'gemini'])

    def test_key_never_appears_in_messages_or_cache(self):
        secret = 'ALPHA-SECRET-VALUE-0001'
        os.environ['AUGURSPEX_ALPHA_VANTAGE_KEY'] = secret

        def getter(url, *_a):
            raise ProviderError('upstream echoed ' + secret + ' back')
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ProviderError) as caught:
                self.router(cache_dir=folder).fetch('NASDAQ:AAPL', 'D', getter=getter)
            self.assertNotIn(secret, str(caught.exception))
            self.assertNotIn(secret, json.dumps(caught.exception.attempts))
            for path in Path(folder).rglob('*'):
                if path.is_file():
                    self.assertNotIn(secret, path.read_text(errors='replace'))

    def test_stale_cache_is_labelled_and_expires(self):
        good = [True]

        def getter(url, *_a):
            if not good[0]:
                raise ProviderError('HTTP 503; provider is having problems', kind='provider_failure')
            return stooq_csv() if 'stooq' in url else b'{"error":"down"}'
        router = self.router()
        self.assertEqual(router.fetch('NASDAQ:AAPL', 'D', getter=getter)['cache'], 'network')
        good[0] = False
        self.now[0] += providers.CACHE_TTL['stooq'] + 5
        stale = router.fetch('NASDAQ:AAPL', 'D', getter=getter)
        self.assertEqual(stale['cache'], 'stale')
        self.assertIn('All current feeds failed', stale['warning'])
        self.now[0] += providers.STALE_HORIZON
        with self.assertRaises(ProviderError):
            router.fetch('NASDAQ:AAPL', 'D', getter=getter)

    @unittest.skipIf('faketime' in os.environ.get('LD_PRELOAD', '') or os.environ.get('FAKETIME'),
                     'file timestamps and the clock disagree under faketime')
    def test_disk_cache_is_bounded_and_only_own_files_are_removed(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            old = folder / ('history-' + 'a' * 64 + '.json')
            old.write_text('{}')
            ancient = time.time() - providers.STALE_HORIZON - 3600
            os.utime(old, (ancient, ancient))
            abandoned = folder / ('history-' + 'b' * 64 + '.json.4242.tmp')
            abandoned.write_text('{}')
            os.utime(abandoned, (ancient, ancient))
            foreign = folder / 'my-notes.json'
            foreign.write_text('{"keep": true}')
            os.utime(foreign, (ancient, ancient))
            lookalike = folder / 'history-notes.json'
            lookalike.write_text('{}')
            os.utime(lookalike, (ancient, ancient))
            router = self.router(cache_dir=folder)
            router.fetch('NASDAQ:AAPL', 'D', getter=lambda url, *_a: stooq_csv() if 'stooq' in url else b'{"error":"x"}')
            self.assertFalse(old.exists(), 'expired cache file should be pruned')
            self.assertFalse(abandoned.exists(), 'abandoned temporary should be pruned')
            self.assertTrue(foreign.exists() and lookalike.exists(), 'files the router did not create must be kept')
            self.assertEqual(len(list(folder.glob('history-*.json'))) - 1, 1)


class Observations(unittest.TestCase):
    def test_zero_or_negative_prices_are_not_observations(self):
        self.assertIsNone(candle('2026-01-02T00:00:00+00:00', 0, 0, 0, 0, 100))
        self.assertIsNone(candle('2026-01-02T00:00:00+00:00', 10, 12, 0, 11, 100))
        self.assertIsNone(candle('2026-01-02T00:00:00+00:00', '10', '12', '-1', '11'))
        self.assertIsNone(candle('2026-01-02T00:00:00+00:00', True, True, True, True))
        self.assertEqual(candle('2026-01-02T00:00:00+00:00', '1,010', '1,020', '1,000', '1,015', 0)['close'], 1015.0)

    def test_stooq_placeholder_rows_are_dropped_not_plotted(self):
        body = ('Date,Open,High,Low,Close,Volume\n' f'{day(3)},10,12,9,11,5\n' f'{day(2)},0,0,0,0,0\n'
                f'{day(1)},11,13,10,12,6\n').encode()
        result = read_stooq('NASDAQ:AAPL', 'D', lambda url: body)
        self.assertEqual([c['close'] for c in result['candles']], [11.0, 12.0])

    def test_csv_export_format_round_trips_through_import(self):
        """The columns AUGURSPEX exports are the columns it imports, value for value."""
        symbol = 'NASDAQ:AAPL'
        rows = [{'time': f'{day(3)}T00:00:00+00:00', 'open': 10.5, 'high': 12.25, 'low': 9.75, 'close': 11.125, 'volume': 1500.0},
                {'time': f'{day(2)}T00:00:00+00:00', 'open': 11.0, 'high': 11.0, 'low': 11.0, 'close': 11.0, 'volume': 0, 'close_only': True},
                {'time': f'{day(1)}T00:00:00+00:00', 'open': 11.5, 'high': 13.0, 'low': 11.25, 'close': 12.875, 'volume': 900.0}]
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(['symbol', 'timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_only', 'source', 'currency'])
        for row in rows:
            only = bool(row.get('close_only'))
            writer.writerow([logic.csv_safe(v) for v in (
                symbol, row['time'], '' if only else row['open'], '' if only else row['high'],
                '' if only else row['low'], row['close'], row['volume'], only, '=HYPERLINK("x")', 'USD')])
        self.assertIn("'=HYPERLINK", buffer.getvalue())
        with tempfile.TemporaryDirectory() as folder:
            path = local_stock_path(folder, symbol)
            path.write_text(buffer.getvalue(), encoding='utf-8')
            back = read_local_stock_csv(path, symbol, 'D')
        self.assertTrue(back['user_imported'])
        self.assertEqual([c['time'] for c in back['candles']], [r['time'] for r in rows])
        self.assertEqual([c['close'] for c in back['candles']], [r['close'] for r in rows])
        self.assertEqual([(c['open'], c['high'], c['low']) for c in back['candles'] if not c.get('close_only')],
                         [(r['open'], r['high'], r['low']) for r in rows if not r.get('close_only')])
        self.assertEqual([bool(c.get('close_only')) for c in back['candles']], [False, True, False])

    def test_import_rejects_another_markets_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'x.csv'
            path.write_text(f'symbol,date,close\nMSFT,{day(1)},100\n')
            with self.assertRaises(ProviderError):
                read_local_stock_csv(path, 'AAPL', 'D')

    def test_local_import_path_cannot_leave_its_folder(self):
        for hostile in ('../../etc/passwd', 'A/../../B', 'C:\\Windows\\x', 'AAPL\x00', ''):
            path = local_stock_path('/tmp/imports', hostile)
            self.assertTrue(path is None or path.parent == Path('/tmp/imports'), hostile)


class ChartLogic(unittest.TestCase):
    def test_date_labels_never_overlap_and_keep_the_newest(self):
        for width in (220, 300, 380, 470, 508, 560, 700, 1046):
            for glyph in (7, 9, 11, 14):
                bars = [{'time': (datetime(2026, 7, 1, tzinfo=timezone.utc) + timedelta(days=i)).isoformat(),
                         'open': 10, 'high': 12, 'low': 9, 'close': 11} for i in range(137)]
                ticks = logic.chart_date_ticks(bars, width)
                placed = logic.fit_date_ticks(ticks, lambda text: len(text) * glyph)
                self.assertTrue(placed)
                self.assertEqual(placed[-1][1], ticks[-1][1], 'newest date label is kept')
                spans = []
                for x, label, anchor in placed:
                    w = len(label) * glyph
                    left = x if anchor == 'nw' else x - w if anchor == 'ne' else x - w / 2
                    spans.append((left, left + w))
                for (_l0, right), (left, _r1) in zip(spans, spans[1:]):
                    self.assertLessEqual(right, left, (width, glyph, placed))
                # Labels stay on the tick of the observation they name.
                self.assertTrue(all((x, label) in ticks for x, label, _anchor in placed))

    def test_single_tick_and_empty(self):
        self.assertEqual(logic.fit_date_ticks([], len), [])
        self.assertEqual(logic.fit_date_ticks([(20, 'NOV 26')], len), [(20, 'NOV 26', 'nw')])

    def test_price_labels_keep_meaning_for_tiny_and_huge_values(self):
        self.assertEqual(logic.format_price(0.00001234), '0.0000123')
        self.assertEqual(logic.format_price(0.0056), '0.00560')
        self.assertEqual(logic.format_price(0.5), '0.5000')
        self.assertEqual(logic.format_price(4.25), '4.250')
        self.assertEqual(logic.format_price(104283.2), '104,283')
        self.assertEqual(logic.format_price(0), '0.0000')
        self.assertEqual(logic.format_quote(0.00001234), '0.00001234')
        self.assertEqual(logic.format_quote(0.25), '0.2500')
        self.assertEqual(logic.format_quote(1234.5), '1,234.50')
        for tiny in (0.00042, 0.0000007, 0.0099):
            self.assertGreater(float(logic.format_price(tiny)), 0)
            self.assertAlmostEqual(float(logic.format_price(tiny)), tiny, delta=tiny * 0.01)

    def test_freshness_states(self):
        now = datetime(2026, 11, 16, 12, tzinfo=timezone.utc)   # a Monday

        def data(*days_back, bad_future=False):
            rows = [{'time': (now - timedelta(days=d)).date().isoformat(), 'open': 10, 'high': 12, 'low': 9, 'close': 11}
                    for d in days_back]
            if bad_future:   # unusable row stamped in the future must not count
                rows.append({'time': (now + timedelta(days=30)).date().isoformat(), 'open': 0, 'high': -1, 'low': 5, 'close': 1})
            return {'candles': rows}
        self.assertEqual(logic.history_health(None, 'AAPL', 'D', now)[0], 'missing')
        self.assertEqual(logic.history_health({'candles': []}, 'AAPL', 'D', now)[0], 'missing')
        self.assertEqual(logic.history_health(data(4, 3), 'AAPL', 'D', now)[0], 'recent')      # Friday close seen on Monday
        self.assertEqual(logic.history_health(data(4, 3), 'BTC-USD', 'D', now)[0], 'stale')   # crypto trades daily
        self.assertEqual(logic.history_health(data(40, 30), 'AAPL', 'D', now)[0], 'stale')
        self.assertEqual(logic.history_health(data(40, 30), 'AAPL', 'M', now)[0], 'recent')
        self.assertEqual(logic.history_health(data(40, 30, bad_future=True), 'AAPL', 'D', now)[0], 'stale')
        self.assertEqual(logic.history_health(data(-9), 'AAPL', 'D', now)[0], 'future')
        self.assertEqual(logic.history_health({'candles': [{'time': 'n/a', 'open': 1, 'high': 2, 'low': 1, 'close': 2}]},
                                              'AAPL', 'D', now)[0], 'undated')

    def test_status_wording_is_distinct_per_cause(self):
        seen = {
            'offline': logic.status_for_error('Network disabled for this run', 'AAPL'),
            'setup': logic.status_for_error('NO ELIGIBLE PROVIDER: …', 'CSL.AX'),
            'limited': logic.status_for_error('kraken: HTTP 429; provider rate limit reached', 'BTC-USD'),
            'stock limited': logic.status_for_error('stooq: Stooq quota or HTML challenge', 'AAPL'),
            'key': logic.status_for_error('fmp: HTTP 401; provider rejected the credentials', 'AAPL'),
            'network': logic.status_for_error('kraken: Network problem: timed out', 'BTC-USD'),
            'fault': logic.status_for_error('kraken: HTTP 502; provider is having problems', 'BTC-USD'),
            'unsupported': logic.status_for_error('stooq: Stooq mapping unavailable for this listing', 'X'),
            'no history': logic.status_for_error('stooq: Stooq returned no history for this listing', 'AAPL'),
            'bad reply': logic.status_for_error('kraken: Kraken reply was not valid JSON', 'BTC-USD'),
            'waiting': logic.status_for_error('', 'AAPL'),
        }
        self.assertEqual(len(set(seen.values())), len(seen), seen)
        for text in seen.values():
            self.assertLessEqual(len(logic.SHORT_STATUS.get(text, text)), 18, text)


if __name__ == '__main__':
    unittest.main(verbosity=1)
