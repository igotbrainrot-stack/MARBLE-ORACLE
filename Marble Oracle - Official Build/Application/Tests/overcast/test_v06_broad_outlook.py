"""v0.6: broad outlooks (question clusters), ensembles, similar-history and learned calibration."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import random
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'Runtime' / 'Marble_Oracle_App'))
from overcast.engine import NewsOracleEngine, OperationCancelled
from overcast import outlook as om
from overcast.calibration import recalibration, fit_platt, apply, MIN_RESOLVED
from overcast.forecasting import aggregate

NOW = datetime.now(timezone.utc)
TODAY = NOW.date()


def article(i, title, host):
    return {'title': title, 'summary': f'{title}. Officials commented on the {i} development.',
            'url': f'https://{host}/n/{i}', 'source': host, 'category': 'world',
            'published': (NOW - timedelta(hours=i)).isoformat(),
            'collected': (NOW - timedelta(minutes=5)).isoformat()}


def framing(ids, bad_signpost=False):
    d = lambda n: (TODAY + timedelta(days=n)).isoformat()
    sp = [
        {'question': 'Will Arcadia raise tariffs on Borealis steel by the deadline?', 'driver': 'Tariff policy',
         'resolution_criteria': 'Official tariff schedule published.', 'target_date': d(40), 'adverse_if': 'YES',
         'weight': 3, 'evidence_article_ids': [ids[0]]},
        {'question': 'Will Arcadia and Borealis hold ministerial trade talks?', 'driver': 'Diplomacy',
         'resolution_criteria': 'Joint statement on a ministry website.', 'target_date': d(60), 'adverse_if': 'NO',
         'weight': 2, 'evidence_article_ids': [ids[1]]},
        {'question': 'Will the Arcadia central bank cut its policy rate?', 'driver': 'Diplomacy',
         'resolution_criteria': 'Central bank statement.', 'target_date': d(80), 'adverse_if': 'NO',
         'weight': 1, 'evidence_article_ids': [ids[2]]},
        {'question': 'Will container freight rates on the Arcadia route rise 10%?', 'driver': 'Tariff policy',
         'resolution_criteria': 'Published freight index.', 'target_date': d(85), 'adverse_if': 'YES',
         'weight': 2, 'evidence_article_ids': [ids[0], ids[2]]},
    ]
    if bad_signpost:
        sp.append({'question': 'Will things get worse?', 'driver': 'Unknown driver', 'resolution_criteria': 'x',
                   'target_date': d(400), 'adverse_if': 'MAYBE', 'weight': 9, 'evidence_article_ids': [999]})
    return {'strategic_question': 'Over the next 90 days, will Arcadia–Borealis trade tensions escalate or ease?',
            'adverse_direction': 'trade tensions escalate',
            'drivers': [{'name': 'Tariff policy', 'description': 'Tariff decisions.'},
                        {'name': 'Diplomacy', 'description': 'Talks and signals.'}],
            'scenarios': [{'name': 'Escalation', 'description': 'New tariffs.', 'defining_conditions': 'tariff raised'},
                          {'name': 'Muddle through', 'description': 'Status quo.', 'defining_conditions': 'no change'},
                          {'name': 'De-escalation', 'description': 'Deal.', 'defining_conditions': 'agreement'}],
            'signposts': sp}


class OutlookFake:
    def __init__(self, ids, incoherent_runs=(), bad_signpost=False):
        self.ids, self.calls, self.temps, self.incoherent = ids, [], [], set(incoherent_runs)
        self.bad = bad_signpost
        self.run = 0
    def complete(self, model, system, user, max_tokens=1800, **kwargs):
        self.calls.append(user); self.temps.append(kwargs.get('temperature'))
        if 'Build a BROAD OUTLOOK' in user:
            return framing(self.ids, self.bad)
        self.run += 1
        base = [30, 40, 50][(self.run - 1) % 3]
        scen = [40, 40, 40] if self.run in self.incoherent else [30, 50, 20]
        return {'signposts': [{'id': f'S{i}', 'probability_percent': base + i, 'rationale': 'r'} for i in range(1, 5)],
                'scenarios': [{'id': k, 'probability_percent': v} for k, v in zip('ABC', scen)],
                'cited_article_ids': [self.ids[0]], 'key_uncertainty': f'uncertainty {self.run}'}


class BroadOutlook(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.engine = NewsOracleEngine(state_dir=self.tmp.name, model_client=object())
        self.engine.store.save_articles([article(1, 'Arcadia weighs tariffs on Borealis steel', 'a.example'),
                                         article(2, 'Borealis signals readiness for trade talks', 'b.example'),
                                         article(3, 'Arcadia central bank warns on inflation', 'c.example')])
        self.ids = [r['id'] for r in self.engine.store.articles(10)]

    def tearDown(self):
        self.engine.close(); self.tmp.cleanup()

    def test_outlook_saves_cluster_atomically_and_is_coherent(self):
        fake = OutlookFake(self.ids, bad_signpost=True)
        self.engine.client = fake
        steps = []
        result = self.engine.broad_outlook(self.ids, 'm', scope='TRADE & SUPPLY CHAINS', horizon_days=90, runs=3,
                                           progress=lambda s, t, l: steps.append((s, t)))
        self.assertEqual(len(fake.calls), 4, '1 framing call + 3 runs')
        self.assertEqual([s for s, _ in steps], [1, 2, 3, 4])
        self.assertEqual(fake.temps, [None, None, 0.7, 0.7], 'runs after the first are diversified')
        self.assertNotEqual(fake.calls[2].split('CACHED RSS EVIDENCE:')[1], fake.calls[1].split('CACHED RSS EVIDENCE:')[1])
        item = self.engine.outlook_detail(result['id'])
        self.assertEqual(len(item['signposts']), 4, 'the invalid signpost is dropped, not saved')
        self.assertEqual(len(item['audit']['frame']['dropped_signposts']), 1)
        self.assertAlmostEqual(sum(s['probability'] for s in item['scenarios']), 1.0, places=3)
        # Signposts are ordinary, resolvable ledger forecasts with the run median.
        ledger = {f['id']: f for f in self.engine.forecasts()}
        s1 = item['signposts'][0]
        self.assertAlmostEqual(ledger[s1['forecast_id']]['probability'], 0.41)   # median of 31, 41, 51
        self.assertEqual(ledger[s1['forecast_id']]['prompt_version'], om.SIGNPOST_PROMPT_VERSION)
        audit = self.engine.forecast_audit(s1['forecast_id'])
        self.assertEqual(audit['outlook_id'], result['id'])
        self.assertEqual(len(audit['valid_votes']), 3)
        self.assertTrue(self.engine.forecast_packet(s1['forecast_id'])['checksum_valid'])
        # Stress index from the formula, in range, and the report renders.
        probs = {sp['signpost_key']: sp['probability'] for sp in item['signposts']}
        frame_sp = [{'id': sp['signpost_key'], 'weight': sp['weight'], 'adverse_if_yes': bool(sp['adverse_if_yes'])}
                    for sp in item['signposts']]
        self.assertAlmostEqual(item['stress_index'], om.stress_index(frame_sp, probs), places=1)
        text = '\n'.join(h + b for h, b, _ in om.report_sections(item))
        self.assertIn('Scenarios', text); self.assertIn('ledger #', text)

    def test_incoherent_runs_are_rejected_and_too_few_saves_nothing(self):
        self.engine.client = OutlookFake(self.ids, incoherent_runs={1, 2})
        with self.assertRaises(ValueError) as cm:
            self.engine.broad_outlook(self.ids, 'm', scope='GLOBAL EVENTS', runs=3)
        self.assertIn('no outlook was saved', str(cm.exception))
        self.assertEqual(self.engine.outlooks(), []); self.assertEqual(self.engine.forecasts(), [])

    def test_cancel_during_outlook_saves_nothing(self):
        self.engine.client = OutlookFake(self.ids)
        cancel = threading.Event()
        with self.assertRaises(OperationCancelled):
            self.engine.broad_outlook(self.ids, 'm', scope='GLOBAL EVENTS', runs=3,
                                      progress=lambda s, t, l: cancel.set() if s == 2 else None, cancel=cancel)
        self.assertEqual(self.engine.outlooks(), [])

    def test_realised_index_and_scenario_resolution_scoring(self):
        self.engine.client = OutlookFake(self.ids)
        oid = self.engine.broad_outlook(self.ids, 'm', scope='GLOBAL EVENTS', runs=2)['id']
        with self.assertRaises(ValueError):   # horizon has not ended yet
            self.engine.resolve_outlook(oid, 'A', 'https://example.org/x')
        item = self.engine.outlook_detail(oid)
        for sp, outcome in zip(item['signposts'], [1, 0, 0, 1]):
            self.engine.resolve(sp['forecast_id'], outcome, 'https://example.org/r')
        item = self.engine.outlook_detail(oid)
        self.assertEqual(item['realised_index'], 100.0, 'every signpost landed on its adverse side')
        self.engine.store.db.execute('UPDATE outlooks SET deadline=? WHERE id=?', ((TODAY - timedelta(days=1)).isoformat(), oid))
        self.engine.resolve_outlook(oid, 'A', 'https://example.org/scenario')
        with self.assertRaises(ValueError):
            self.engine.resolve_outlook(oid, 'B', 'https://example.org/again')
        report = self.engine.score_report()['scenario_forecasts']
        self.assertEqual(report['resolved'], 1)
        # p(A)=0.30, p(B)=0.50, p(C)=0.20 -> (0.7^2 + 0.5^2 + 0.2^2)
        self.assertAlmostEqual(report['items'][0]['multiclass_brier'], 0.78, places=3)


class EnsembleAndHistory(unittest.TestCase):
    def test_ensemble_rule(self):
        self.assertEqual(om.ensemble([10, 90, 50]), 50)
        self.assertEqual(om.ensemble([10, 40, 60, 99]), 50)      # drops 10 and 99
        votes = [{'probability_percent': v} for v in (20, 30, 40, 50, 95)]
        agg = aggregate(votes)
        self.assertEqual(agg['rule'], 'trimmed-mean(drop min,max)')
        self.assertAlmostEqual(agg['probability'], 0.40)
        self.assertEqual(agg['median_percent'], 40)

    def test_deep_forecast_extra_runs_and_similar_history(self):
        class Fake:
            def __init__(self): self.users, self.temps = [], []
            def complete(self, model, system, user, max_tokens=1800, **kw):
                self.users.append(user); self.temps.append(kw.get('temperature'))
                if 'propose EXACTLY ONE useful' in user:
                    return {'question': 'Will Arcadia raise steel tariffs within 30 days?',
                            'target_date': (TODAY + timedelta(days=20)).isoformat(),
                            'resolution_criteria': 'Official notice.', 'change_mind': 'Talks.'}
                return {'probability_percent': 20 + 10 * len(self.users), 'reasoning': 'r', 'counterargument': 'c',
                        'cited_article_ids': [1], 'reference_class': 'unavailable'}
        with tempfile.TemporaryDirectory() as d:
            fake = Fake()
            e = NewsOracleEngine(state_dir=d, model_client=fake)
            try:
                e.store.save_articles([article(1, 'Arcadia weighs steel tariffs', 'a.example')])
                old = e.store.add_forecast({'question': 'Will Arcadia raise steel tariffs on Borealis?',
                    'probability': 0.7, 'target_date': (TODAY - timedelta(days=5)).isoformat(),
                    'resolution_criteria': 'r', 'reasoning': 'r', 'counterargument': 'c', 'change_mind': 'm'}, [], 'm', 'v', {})
                e.resolve(old, 0, 'https://example.org/old')
                result = e.forecast_multi([1], 'm', 30, expand=False, runs=5)
                audit = e.forecast_audit(result['id'])
                self.assertEqual(audit['ensemble_passes'], 5)
                self.assertEqual(audit['aggregation']['rule'], 'trimmed-mean(drop min,max)')
                self.assertEqual(fake.temps, [None, None, None, None, 0.7, 0.7])
                self.assertEqual(audit['similar_history'][0]['outcome'], 'NO')
                self.assertIn("SIGNAL'S OWN PAST RESOLVED QUESTIONS", fake.users[1])
                ledger = {f['id']: f for f in e.forecasts()}
                self.assertTrue(ledger[result['id']]['prompt_version'].endswith('+history+ensemble5'))
            finally:
                e.close()


class LearnedCalibration(unittest.TestCase):
    def test_not_offered_without_enough_history(self):
        rec = recalibration([0.6] * (MIN_RESOLVED - 1), [1, 0] * 19 + [1])
        self.assertFalse(rec['available'])

    def test_detects_hedged_forecaster_out_of_sample(self):
        rng = random.Random(7)
        probs, outcomes = [], []
        for _ in range(400):
            truth = rng.choice([0.05, 0.15, 0.85, 0.95])
            outcomes.append(1 if rng.random() < truth else 0)
            probs.append(0.5 + (truth - 0.5) * 0.4)          # systematically hedged toward 50%
        rec = recalibration(probs, outcomes)
        self.assertTrue(rec['available'] and rec['recommended'])
        self.assertGreater(rec['a'], 1.5, 'hedging should be corrected by stretching')
        self.assertLess(rec['cv_brier_recalibrated'], rec['cv_brier_raw'])

    def test_well_calibrated_forecaster_is_left_alone(self):
        rng = random.Random(3)
        probs = [rng.uniform(0.05, 0.95) for _ in range(300)]
        outcomes = [1 if rng.random() < p else 0 for p in probs]
        a, b = fit_platt(probs, outcomes)
        self.assertAlmostEqual(a, 1.0, delta=0.35); self.assertAlmostEqual(b, 0.0, delta=0.35)
        self.assertAlmostEqual(apply(0.5, 1.0, 0.0), 0.5)


if __name__ == '__main__':
    unittest.main()


class RealClientEndToEnd(unittest.TestCase):
    """Broad outlook through the real LMStudioClient over loopback HTTP (no fakes in the client path)."""
    def test_outlook_over_http_with_diversified_runs(self):
        from test_v052_refinements import Stub, ok
        with tempfile.TemporaryDirectory() as d:
            e = NewsOracleEngine(state_dir=d, model_client=object())
            try:
                e.store.save_articles([article(1, 'Arcadia weighs tariffs on Borealis steel', 'a.example'),
                                       article(2, 'Borealis signals trade talks', 'b.example'),
                                       article(3, 'Arcadia central bank warns on inflation', 'c.example')])
                ids = [r['id'] for r in e.store.articles(10)]
                run = {'signposts': [{'id': f'S{i}', 'probability_percent': 30 + i, 'rationale': 'r'} for i in range(1, 5)],
                       'scenarios': [{'id': k, 'probability_percent': v} for k, v in zip('ABC', [30, 50, 20])],
                       'cited_article_ids': [ids[0]], 'key_uncertainty': 'u'}
                responses = [ok(json.dumps(framing(ids))), ok('<think>weighing</think>' + json.dumps(run)), ok(json.dumps(run))]
                with Stub(responses) as srv:
                    e.client = srv.client()
                    result = e.broad_outlook(ids, 'qwen2.5-7b-instruct', scope='GLOBAL EVENTS', runs=2)
                    temps = [r['temperature'] for r in srv.requests]
                self.assertEqual(temps, [0.2, 0.2, 0.7])
                self.assertEqual(result['signposts'], 4)
            finally:
                e.close()
