"""OVERCAST 1.0: rename compatibility, risk-first outlooks, risk register, gloom bias, revisions, feeds."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'Runtime' / 'Marble_Oracle_App'))
import overcast
from overcast.engine import NewsOracleEngine
from overcast import outlook as om, feeds
from overcast.risk import focus_tags
from overcast.scopes import SCOPES
from test_v06_broad_outlook import OutlookFake, article, framing

NOW = datetime.now(timezone.utc)
TODAY = NOW.date()


def risk_framing(ids):
    f = framing(ids)
    f['scenarios'] = [
        {'name': 'Tariff spiral', 'kind': 'adverse', 'severity': 4, 'description': 'd', 'defining_conditions': 'c'},
        {'name': 'Grinding stalemate', 'kind': 'status_quo', 'severity': 2, 'description': 'd', 'defining_conditions': 'c'},
        {'name': 'Grand bargain', 'kind': 'stabilising', 'severity': 1, 'description': 'd', 'defining_conditions': 'c'},
        {'name': 'Trade war', 'kind': 'tail_risk', 'severity': 5, 'description': 'd', 'defining_conditions': 'c'}]
    for sp, sev in zip(f['signposts'], [5, 2, 3, 4]):
        sp['severity'] = sev
    f['premortem'] = 'Talks collapse [1], tariffs rise, freight spikes [3].'
    return f


class RiskFake(OutlookFake):
    def complete(self, model, system, user, max_tokens=1800, **kw):
        if 'Build a BROAD OUTLOOK' in user:
            self.calls.append(user); self.temps.append(kw.get('temperature'))
            return risk_framing(self.ids)
        out = super().complete(model, system, user, max_tokens, **kw)
        out['scenarios'] = [{'id': k, 'probability_percent': v} for k, v in zip('ABCD', [30, 45, 15, 10])]
        return out


class Compatibility(unittest.TestCase):
    def test_old_package_name_still_works(self):
        import news_oracle
        import news_oracle.engine
        import overcast.engine
        self.assertIs(news_oracle.engine, overcast.engine)
        self.assertIs(news_oracle.engine.NewsOracleEngine, overcast.OvercastEngine)
        self.assertEqual(news_oracle.__version__, overcast.__version__)
        self.assertEqual(overcast.APP_NAME, 'OVERCAST')

    def test_state_directory_name_is_unchanged(self):
        from overcast.store import default_state_dir
        self.assertEqual(default_state_dir().name, 'news_oracle', 'renaming must not orphan existing user data')

    def test_v06_database_migrates_additively(self):
        with tempfile.TemporaryDirectory() as d:
            db = sqlite3.connect(str(Path(d) / 'news_oracle.sqlite3'))
            db.executescript('''CREATE TABLE outlooks (id INTEGER PRIMARY KEY AUTOINCREMENT, scope TEXT NOT NULL,
                query TEXT NOT NULL DEFAULT '', horizon_days INTEGER NOT NULL, deadline TEXT NOT NULL,
                strategic_question TEXT NOT NULL, adverse_direction TEXT NOT NULL, stress_index REAL NOT NULL,
                scenarios_json TEXT NOT NULL, drivers_json TEXT NOT NULL, audit_json TEXT NOT NULL,
                model_id TEXT NOT NULL, method TEXT NOT NULL, prompt_version TEXT NOT NULL, created TEXT NOT NULL);
                INSERT INTO outlooks VALUES (1,'GLOBAL EVENTS','',90,'2027-01-01','Old?','x',5,'[]','[]','{}','m','v','p','2026-11-01');''')
            db.commit(); db.close()
            e = NewsOracleEngine(state_dir=d, model_client=object())
            try:
                rows = e.outlooks()
                self.assertEqual(rows[0]['strategic_question'], 'Old?')
                self.assertIsNone(rows[0]['revision_of'])
            finally:
                e.close()


class RiskFirstOutlook(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.e = NewsOracleEngine(state_dir=self.tmp.name, model_client=object())
        self.e.store.save_articles([article(1, 'Arcadia weighs tariffs on Borealis steel', 'a.example'),
                                    article(2, 'Borealis signals trade talks', 'b.example'),
                                    article(3, 'Arcadia central bank warns on inflation', 'c.example')])
        self.ids = [r['id'] for r in self.e.store.articles(10)]
        self.e.client = RiskFake(self.ids)

    def tearDown(self):
        self.e.close(); self.tmp.cleanup()

    def test_adverse_probability_severity_premortem_and_report_order(self):
        r = self.e.broad_outlook(self.ids, 'm', scope='TRADE & SUPPLY CHAINS', runs=2)
        self.assertAlmostEqual(r['p_adverse_scenarios'], 0.40)        # adverse 30% + tail 10%
        item = self.e.outlook_detail(r['id'])
        self.assertEqual({s['kind'] for s in item['scenarios']}, {'adverse', 'status_quo', 'stabilising', 'tail_risk'})
        self.assertEqual([sp['severity'] for sp in item['signposts']], [5, 2, 3, 4])
        sections = om.report_sections(item)
        self.assertEqual(sections[1][0], 'Bad news first')
        text = '\n'.join(h + '\n' + b for h, b, _ in sections)
        self.assertIn('Pre-mortem', text)
        self.assertLess(text.index('[Adverse'), text.index('[Stabilising'), 'adverse scenarios listed first')

    def test_one_sided_doom_is_rejected(self):
        f = risk_framing(self.ids)
        for s in f['scenarios']:
            s['kind'] = 'adverse'
        with self.assertRaises(ValueError):
            om.validate_framing(f, allowed_ids=set(self.ids), today=TODAY, deadline=TODAY + timedelta(days=90))

    def test_missing_kinds_inferred_only_from_clear_names(self):
        self.assertEqual(om.infer_kind('Escalation into a trade war'), 'adverse')
        self.assertEqual(om.infer_kind('Muddle through'), 'status_quo')
        self.assertEqual(om.infer_kind('De-escalation deal'), 'stabilising')
        self.assertIsNone(om.infer_kind('Scenario 2'))

    def test_risk_register_ranks_expected_harm_and_hides_superseded_copies(self):
        r = self.e.broad_outlook(self.ids, 'm', scope='TRADE & SUPPLY CHAINS', runs=2)
        register = self.e.risk_register(10)
        self.assertEqual(len(register), 4)
        scores = [x['risk_score'] for x in register]
        self.assertEqual(scores, sorted(scores, reverse=True))
        top = register[0]
        self.assertAlmostEqual(top['risk_score'], top['p_adverse'] * top['severity'], places=3)
        self.e.revise_outlook(r['id'], 'm', runs=2)
        self.assertEqual(len(self.e.risk_register(10)), 4, 'a revision replaces, not duplicates, its risks')

    def test_revision_links_keeps_deadline_and_propagates_resolution(self):
        first = self.e.broad_outlook(self.ids, 'm', scope='TRADE & SUPPLY CHAINS', runs=2)
        steps = []
        rev = self.e.revise_outlook(first['id'], 'm', runs=2, progress=lambda s, t, l: steps.append(t))
        self.assertEqual(steps, [2, 2], 'a revision skips the framing call')
        a, b = self.e.outlook_detail(first['id']), self.e.outlook_detail(rev['id'])
        self.assertEqual(b['revision_of'], first['id'])
        self.assertEqual(a['deadline'], b['deadline'])
        self.assertEqual(a['strategic_question'], b['strategic_question'])
        resolved = self.e.resolve(a['signposts'][0]['forecast_id'], 1, 'https://example.org/r')
        self.assertEqual(len(resolved), 2, 'the copy in the revision is resolved too')
        self.assertEqual(self.e.gloom_bias()['resolved'], 1, 'one real-world question counts once')
        self.assertEqual(len(self.e.store.resolved_forecasts(unique=True)), 1)
        self.assertEqual(len(self.e.store.resolved_forecasts()), 2)
        self.assertEqual(self.e.outlook_detail(rev['id'])['signposts'][0]['outcome'], 1)
        self.assertIn(a['signposts'][0]['forecast_id'], [f['id'] for f in self.e.forecasts() if f['outcome'] == 1])

    def test_gloom_bias_detects_pessimism(self):
        for i in range(20):
            fid = self.e.store.add_forecast({'question': f'Will crisis {i} erupt?', 'probability': 0.8,
                'target_date': (TODAY - timedelta(days=1)).isoformat(), 'resolution_criteria': 'r',
                'reasoning': 'r', 'counterargument': 'c', 'change_mind': 'm'}, [], 'm', 'v', {})
            self.e.set_orientation(fid, True, 4)
            self.e.resolve(fid, 1 if i < 6 else 0, 'https://example.org/x')   # bad news only 30% of the time
        g = self.e.gloom_bias()
        self.assertEqual(g['resolved'], 20)
        self.assertAlmostEqual(g['gloom_bias_points'], 50.0)
        self.assertTrue(g['verdict'].startswith('TOO GLOOMY'))
        self.assertIn('gloom_bias', self.e.score_report())
        with self.assertRaises(ValueError):
            self.e.set_orientation(fid, True, 9)


class EarlyWarningFeeds(unittest.TestCase):
    def test_new_sources_and_crisis_scope(self):
        names = [s[0] for s in feeds.SOURCES]
        for name in ('Crisis Group', 'GDACS Disaster Alerts', 'Bank of England', 'UN Meetings Coverage'):
            self.assertIn(name, names)
        self.assertTrue(all(s[1].startswith('https://') for s in feeds.SOURCES))
        self.assertIn('CRISES & DISASTERS', SCOPES)
        self.assertIn('CRISES', focus_tags({'title': 'Cyclone forces mass evacuation'}))
        self.assertNotIn('CRISES', focus_tags({'title': 'App adds default dark mode'}))

    def test_gdacs_green_alerts_filtered_and_crisis_group_dates_parsed(self):
        xml = (b'<rss><channel>'
               b'<item><title>Green forest fire notification in Australia</title><link>https://gdacs.example/1</link></item>'
               b'<item><title>Red earthquake alert in Chile</title><link>https://gdacs.example/2</link></item>'
               b'</channel></rss>')
        items = feeds.parse_feed(xml, 'GDACS Disaster Alerts', 'crisis', keep=feeds.ITEM_FILTERS['GDACS Disaster Alerts'])
        self.assertEqual([i['title'] for i in items], ['Red earthquake alert in Chile'])
        self.assertTrue(feeds._date('Friday, November 13, 2026 - 15:32').startswith('2026-11-13T15:32'))


if __name__ == '__main__':
    unittest.main()
