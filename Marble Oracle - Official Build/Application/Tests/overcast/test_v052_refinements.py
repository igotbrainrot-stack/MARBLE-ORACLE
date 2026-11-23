"""v0.5.2 regressions: local-model robustness, context budgets, progress/cancel, ledger scoring."""
from datetime import date, datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'Runtime' / 'Marble_Oracle_App'))
from overcast import feeds
from overcast.calendar import export_ics
from overcast.engine import NewsOracleEngine, OperationCancelled, CONTEXT_PROFILES
from overcast.forecasting import compact_investigation
from overcast.lmstudio import (LMStudioClient, LMStudioContextError, LMStudioDeviceLostError,
                                  LMStudioError, LMStudioGPUMemoryError, LMStudioTimeoutError,
                                  parse_json_response)
from overcast.research import dossier

NOW = datetime.now(timezone.utc)


class Stub:
    """Loopback LM Studio stand-in. Each response is (status, body[, delay_seconds])."""
    def __init__(self, responses, models=None):
        self.responses, self.requests, outer = responses, [], self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a): pass
            def _send(self, status, body):
                data = json.dumps(body).encode()
                self.send_response(status); self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(data))); self.end_headers(); self.wfile.write(data)
            def do_GET(self):
                self._send(200, {'data': [{'id': m} for m in (models or [])]})
            def do_POST(self):
                outer.requests.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
                spec = outer.responses[min(len(outer.requests) - 1, len(outer.responses) - 1)]
                if len(spec) > 2: time.sleep(spec[2])
                try: self._send(spec[0], spec[1])
                except (BrokenPipeError, ConnectionResetError): pass
        self.http = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
    def __enter__(self): self.thread.start(); return self
    def __exit__(self, *_):
        self.http.shutdown(); self.http.server_close(); self.thread.join(timeout=3)
    def client(self, timeout=3):
        return LMStudioClient(f'http://127.0.0.1:{self.http.server_port}/v1', timeout=timeout)


def ok(content, finish='stop'):
    return (200, {'choices': [{'message': {'content': content}, 'finish_reason': finish}]})


class ClientRobustness(unittest.TestCase):
    def test_reasoning_blocks_and_prose_are_ignored(self):
        self.assertEqual(parse_json_response('<think>maybe {"a": 2}?</think>\n{"a": 1}'), {'a': 1})
        self.assertEqual(parse_json_response('Here you go {not json} then {"q": "x?"} done'), {'q': 'x?'})
        self.assertEqual(parse_json_response('```json\n{"k": [1, 2]}\n```'), {'k': [1, 2]})
        self.assertEqual(parse_json_response('reasoning without opener</think>{"z": true}'), {'z': True})
        with self.assertRaises(LMStudioError):
            parse_json_response('<think>{"unfinished": 1}')

    def test_token_budget_exhaustion_is_explained(self):
        with Stub([ok('<think>long reasoning', 'length')]) as srv:
            with self.assertRaises(LMStudioError) as cm:
                srv.client().complete('qwen3-8b', 's', 'u', max_tokens=900)
        self.assertIn('900-token reply budget', str(cm.exception))

    def test_json_mode_rejection_is_remembered(self):
        reject = (400, {'error': "'response_format.type' must be 'json_schema' or 'text'"})
        with Stub([reject, ok('{"n": 1}'), ok('{"n": 2}')]) as srv:
            client = srv.client()
            self.assertEqual(client.complete('m', 's', 'u'), {'n': 1})
            self.assertEqual(client.complete('m', 's', 'u'), {'n': 2})
            self.assertEqual(len(srv.requests), 3, 'second call must not repeat the rejected format')
            self.assertNotIn('response_format', srv.requests[2])

    def test_slow_generation_is_a_timeout_not_unreachable(self):
        with Stub([(200, {'choices': []}, 2.5)]) as srv:
            with self.assertRaises(LMStudioTimeoutError) as cm:
                srv.client(timeout=1).complete('m', 's', 'u')
        self.assertIn('did not finish', str(cm.exception))
        self.assertNotIn('Cannot reach', str(cm.exception))

    def test_context_and_gpu_memory_errors_are_classified_and_not_retried(self):
        overflow = (400, {'error': 'The number of tokens to keep from the initial prompt is greater than the context length'})
        with Stub([overflow]) as srv:
            with self.assertRaises(LMStudioContextError) as cm:
                srv.client().complete('m', 's', 'u')
            self.assertEqual(len(srv.requests), 1)
        self.assertIn('MODEL CONTEXT', str(cm.exception))
        oom = (400, {'error': 'vk::Device::allocateMemory: ErrorOutOfDeviceMemory'})
        with Stub([oom]) as srv:
            with self.assertRaises(LMStudioGPUMemoryError) as cm:
                srv.client().complete('m', 's', 'u')
            self.assertEqual(len(srv.requests), 1)
        self.assertIsInstance(cm.exception, LMStudioDeviceLostError, 'pipelines must fail fast on GPU OOM')

    def test_embedding_models_sorted_last_and_refused(self):
        with Stub([ok('{}')], models=['text-embedding-nomic-embed-text-v1.5', 'qwen2.5-7b-instruct']) as srv:
            client = srv.client()
            self.assertEqual(client.models(), ['qwen2.5-7b-instruct', 'text-embedding-nomic-embed-text-v1.5'])
            with self.assertRaises(LMStudioError):
                client.complete('text-embedding-nomic-embed-text-v1.5', 's', 'u')
            self.assertEqual(srv.requests, [])


def row(i, title, host, summary_len=60):
    return {'id': i, 'title': title, 'summary': ('Detail about ' + title + '. ') * (summary_len // 20 + 1),
            'url': f'https://{host}/s/{i}', 'source': host,
            'published': (NOW - timedelta(hours=i)).isoformat(),
            'collected': (NOW - timedelta(minutes=5)).isoformat(), 'category': 'world'}


class ContextBudgets(unittest.TestCase):
    def test_dossier_shortens_excerpts_before_failing(self):
        rows = [row(i, f'Arcadia tariff ruling {i} prompts Borealis response', f'p{i}.example', 1500) for i in range(1, 13)]
        full = dossier(rows)
        self.assertEqual(full['excerpt_chars'], 850)
        tight = dossier(rows, max_chars=9000)
        self.assertLessEqual(len(tight['text']), 9000)
        self.assertEqual(len(tight['articles']), 12, 'no article may be dropped')
        self.assertLess(tight['excerpt_chars'], 850)
        self.assertTrue(any('shortened' in c for c in tight['cautions']))
        with self.assertRaises(ValueError):
            dossier(rows, max_chars=1500)

    def test_8k_profile_bounds_research_packet(self):
        with tempfile.TemporaryDirectory() as d:
            engine = NewsOracleEngine(state_dir=d, model_client=object(), context_profile='8K')
            try:
                engine.store.save_articles([row(i, f'Country{i % 5} sanctions decision on oil exports {i}',
                                                f'pub{i % 8}.example', 1400) for i in range(1, 41)])
                coverage = engine.coverage('GLOBAL EVENTS')
                packet = engine.research_preview(coverage['article_ids'])
                self.assertLessEqual(len(packet['text']), CONTEXT_PROFILES['8K']['packet'])
            finally:
                engine.close()
        with self.assertRaises(ValueError):
            NewsOracleEngine(state_dir=d, model_client=object(), context_profile='4K')

    def test_compacted_hypotheses_remain_parseable(self):
        inv = {'actors': [{'actor': 'A' * 300, 'evidence_article_ids': [1]}] * 5,
               'connections': [{'from': 'B' * 300, 'evidence_article_ids': [1]}] * 5,
               'downside_path': 'd', 'stabilising_path': 's', 'watch_signals': ['w'], 'method_note': 'n'}
        text = compact_investigation(inv, 1200)
        data = json.loads(text)
        self.assertTrue(data['omitted_for_context'])
        self.assertLessEqual(len(text), 1200)
        self.assertNotIn('method_note', data)


class StagedFake:
    def __init__(self): self.calls = 0
    def complete(self, model, system, user, max_tokens=1800):
        self.calls += 1
        if 'propose EXACTLY ONE useful' in user:
            return {'question': 'Will Arcadia publish a tariff notice within three weeks?',
                    'target_date': (NOW.date() + timedelta(days=21)).isoformat(),
                    'resolution_criteria': 'Official notice published.', 'change_mind': 'Later notice.'}
        if 'Inspect this prediction' in user:
            return {'gaps': ['Is a notice scheduled?'], 'support_terms': ['tariff'], 'disconfirm_terms': ['delay']}
        return {'probability_percent': 30 + self.calls, 'reasoning': 'r', 'counterargument': 'c',
                'cited_article_ids': [1], 'reference_class': 'unavailable'}


class ProgressAndCancel(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.fake = StagedFake()
        self.engine = NewsOracleEngine(state_dir=self.tmp.name, model_client=self.fake)
        self.engine.store.save_articles([row(1, 'Arcadia considers tariff notice', 'a.example')])
    def tearDown(self):
        self.engine.close(); self.tmp.cleanup()

    def test_progress_reports_every_model_call(self):
        seen = []
        result = self.engine.forecast_multi([1], 'm', 30, expand=False,
                                            progress=lambda s, t, l: seen.append((s, t, l)))
        self.assertEqual([s for s, _, _ in seen], [1, 2, 3, 4])
        self.assertTrue(all(t == 4 for _, t, _ in seen))
        self.assertEqual(self.fake.calls, 4)
        self.assertEqual(self.engine.forecast_audit(result['id'])['context_profile'], '16K')

    def test_cancel_between_calls_saves_nothing(self):
        cancel = threading.Event()
        def progress(step, total, label):
            if step == 2: cancel.set()   # user presses CANCEL while the gap-plan call runs
        with self.assertRaises(OperationCancelled):
            self.engine.forecast_multi([1], 'm', 30, expand=False, gap_search=True,
                                       progress=progress, cancel=cancel)
        self.assertEqual(self.fake.calls, 2, 'no further model call after cancellation')
        self.assertEqual(self.engine.forecasts(), [])
        self.assertFalse(issubclass(OperationCancelled, RuntimeError),
                         'optional-stage handlers catch RuntimeError and must not swallow a cancel')


class LedgerAndCalendar(unittest.TestCase):
    def test_resolution_scoring_and_overdue(self):
        with tempfile.TemporaryDirectory() as d:
            engine = NewsOracleEngine(state_dir=d, model_client=object())
            try:
                def add(p, days):
                    return engine.store.add_forecast({'question': 'Q?', 'probability': p,
                        'target_date': (date.today() + timedelta(days=days)).isoformat(),
                        'resolution_criteria': 'r', 'reasoning': 'r', 'counterargument': 'c',
                        'change_mind': 'm'}, [], 'm', 'v', {})
                a, b, overdue = add(0.8, 20), add(0.3, 120), add(0.5, -3)
                engine.resolve(a, 1, 'https://example.org/a')
                engine.resolve(b, 0, 'https://example.org/b')
                with self.assertRaises(ValueError):
                    engine.resolve(a, 0, 'https://example.org/again')
                with self.assertRaises(ValueError):
                    engine.resolve(overdue, 1, 'https://')
                self.assertEqual(engine.store.get_forecast(a)['outcome'], 1)
                report = engine.score_report()
                self.assertAlmostEqual(report['log_loss'], 0.28991, places=4)
                self.assertEqual({h['horizon'] for h in report['by_horizon']}, {'8-30 days', '91-180 days'})
                self.assertEqual(report['overdue_unresolved'], 1)
                self.assertIn('past deadline', report['warning'])
            finally:
                engine.close()

    def test_ics_has_dtstamp_per_event(self):
        items = [{'id': 'deadline-1', 'kind': 'forecast_deadline', 'start_date': '2026-12-01',
                  'end_date': '2026-12-01', 'title': 'Q?', 'probability': 0.4, 'timing_basis': 'x',
                  'notes': '', 'source_url': ''}]
        ics = export_ics(items)
        self.assertEqual(ics.count('BEGIN:VEVENT'), ics.count('DTSTAMP:'))
        from overcast import __version__
        self.assertIn('OVERCAST '+__version__, ics)
        self.assertIn('@signal.marble-oracle.local', ics, 'UIDs unchanged so calendar re-imports update, not duplicate')


class FeedParsing(unittest.TestCase):
    def test_empty_atom_self_link_does_not_hide_rss_link(self):
        xml = (b'<rss xmlns:atom="http://www.w3.org/2005/Atom"><channel><item>'
               b'<atom:link rel="self" href="https://feed.example/rss"/>'
               b'<title>Port strike halts exports</title><link>https://news.example/a?utm_source=x</link>'
               b'<description>&lt;p&gt;Dockers walk out&lt;/p&gt;</description></item></channel></rss>')
        items = feeds.parse_feed(xml, 'Example')
        self.assertEqual(items[0]['url'], 'https://news.example/a')
        self.assertEqual(items[0]['summary'], 'Dockers walk out')
        self.assertEqual(feeds.clean_text('&lt;b&gt;bold&lt;/b&gt;'), 'bold')

    def test_parallel_collection_keeps_source_order_and_isolates_errors(self):
        original = feeds.fetch_rss
        def fake(url, name, category='general', timeout=12):
            if name == 'B': raise OSError('down')
            time.sleep(0.05 if name == 'A' else 0)
            return [{'title': name, 'summary': '', 'url': url, 'source': name, 'category': category,
                     'published': NOW.isoformat(), 'collected': NOW.isoformat()}]
        feeds.fetch_rss = fake
        try:
            items, report = feeds.collect_feeds((('A', 'https://a.example', 'world'),
                                                 ('B', 'https://b.example', 'world'),
                                                 ('C', 'https://c.example', 'world')))
        finally:
            feeds.fetch_rss = original
        self.assertEqual([r['source'] for r in report], ['A', 'B', 'C'])
        self.assertEqual([i['source'] for i in items], ['A', 'C'])
        self.assertIn('down', report[1]['error'])


if __name__ == '__main__':
    unittest.main()
