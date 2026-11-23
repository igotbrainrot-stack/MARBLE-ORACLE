"""Offline v0.3 regression: downside scenarios, provenance, windows, and ICS."""
from datetime import datetime, date, timedelta, timezone
from pathlib import Path
import json
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[2] / 'Runtime' / 'Marble_Oracle_App'))
from overcast.engine import NewsOracleEngine
from overcast.risk import focus_tags, validate_investigation
from overcast.calendar import iso_day, validate_window, calendar_entries, on_day, export_ics

NOW=datetime.now(timezone.utc)


def feed_item(id,title,domain,category='world'):
    return dict(id=id,title=title,summary='RSS excerpt regarding '+title,
                source=domain,url=f'https://{domain}/news/{id}',category=category,
                published=(NOW-timedelta(hours=3)).isoformat(),
                collected=(NOW-timedelta(minutes=8)).isoformat())


class DeepFake:
    def __init__(self,bad_ids=False, bad_window=False):
        self.calls=[];self.vote=0;self.bad_ids=bad_ids;self.bad_window=bad_window
    def models(self):return ['localhost-mock']
    def complete(self,model,system,prompt,max_tokens=2000):
        self.calls.append(prompt)
        if 'propose EXACTLY ONE useful' in prompt:
            today=date.today()
            return {'question':'Will Arcadia announce a new import tariff in 15 days?',
              'target_date':(today+timedelta(days=15)).isoformat(),
              'resolution_criteria':'Published government statement by the target date.',
              'change_mind':'Dated government announcement or public cancellation.',
              'expected_window_start':(today+timedelta(days=4)).isoformat(),
              'expected_window_end':(today+timedelta(days=20 if self.bad_window else 9)).isoformat(),
              'timing_basis':'A tentative window inferred from dated reporting, not a confirmed meeting.'}
        if 'Investigate competing explanations' in prompt:
            return {'actors':[{'actor':'Arcadia central bank',
                 'observed_action':'RSS reports discussed interest rates.',
                 'possible_incentive':'Possible effort to stabilise financing.',
                 'alternative_explanation':'Routine response to published inflation data.',
                 'evidence_article_ids':[999] if self.bad_ids else [1]}],
              'connections':[{'from':'Arcadia interest rates', 'to':'Arcadia tariff proposal',
                 'mechanism_hypothesis':'Higher costs could affect import demand.',
                 'noncausal_alternative':'Both stories concern Arcadia without causal linkage.',
                 'disconfirming_signal':'No policy statement connecting the issues.',
                 'evidence_article_ids':[1,3]}],
              'downside_path':'If tariffs expand, import cost pressure might rise.',
              'stabilising_path':'Negotiations could avert a tariff change.',
              'watch_signals':['Government gazette date','Published trade schedule']}
        self.vote+=1
        return {'probability_percent':[22,42,68][self.vote-1],
                'reasoning':'Limited source snippets and conditional downside reasoning.',
                'counterargument':'Policy could remain unchanged.',
                'cited_article_ids':[1], 'reference_class':'No validated base rate available.'}


class RiskCalendarTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.client=DeepFake()
        self.engine=NewsOracleEngine(state_dir=self.tmp.name,model_client=self.client)
        self.engine.store.save_articles([
            feed_item(1,'Arcadia central bank raises rates as inflation returns','a.example','business'),
            feed_item(2,'Arcadia central bank raises rates after inflation','b.example','business'),
            feed_item(3,'Arcadia announces import tariff proposal on metals','wto.example','trade'),
            feed_item(4,'A different football team wins tournament','sports.example','sports')])
    def tearDown(self):
        self.engine.close();self.tmp.cleanup()

    def test_focus_sectors_are_deterministic_not_risk_probabilities(self):
        self.assertIn('TRADE',focus_tags({'title':'Export controls and tariffs target semiconductors'}))
        self.assertIn('MARKETS',focus_tags({'title':'Central bank interest rates and bond yields'}))
        self.assertIn('WORLD POLITICS',focus_tags({'title':'Parliament debates a new border treaty'}))
        self.assertEqual(focus_tags({'title':'Tennis training session','category':'sports'}),[])
        counts=self.engine.topic_summary()
        self.assertGreaterEqual(counts['MARKETS'],2)

    def test_cross_sector_bridge_is_research_lead_not_proof(self):
        dossier=self.engine.research_preview([1])
        found=[x for x in dossier['cross_sector_bridges'] if x['article_id']==3]
        self.assertTrue(found)
        self.assertIn('Arcadia'.lower(),found[0]['shared_terms'])
        self.assertIn('NOT evidence',found[0]['warning'])
        self.assertNotIn(4,dossier['article_ids'])

    def test_deep_investigation_is_separate_from_probability(self):
        result=self.engine.forecast_multi([1],'localhost-mock',30,investigate=True)
        self.assertEqual(len(self.client.calls),5)
        self.assertEqual(result['probability'],.42)  # Median unchanged by pessimistic layer
        self.assertEqual(result['method'],'risk-investigation-three-lens-v3')
        self.assertEqual(result['window_start'],(date.today()+timedelta(days=4)).isoformat())
        audit=self.engine.forecast_audit(result['id'])
        self.assertEqual(len(audit['investigation']['actors']),1)
        self.assertIn('hypotheses',audit['investigation']['method_note'])
        self.assertIn('cross_sector_bridges',audit)
        self.assertIsNone(audit['investigation_error'])
        self.assertTrue(audit['investigation_in_quantification'])
        self.assertTrue(all('UNVERIFIED INCENTIVE' in text for text in self.client.calls[2:]))

    def test_invalid_investigation_citation_exposed_not_fabricated(self):
        self.engine.client=DeepFake(bad_ids=True)
        result=self.engine.forecast_multi([1],'localhost-mock',30,investigate=True)
        audit=self.engine.forecast_audit(result['id'])
        self.assertIsNone(audit['investigation'])
        self.assertIn('unsupported article IDs',audit['investigation_error'])
        self.assertFalse(result['investigation_valid'])

    def test_window_after_deadline_rejected_atomically(self):
        self.engine.client=DeepFake(bad_window=True)
        with self.assertRaises(ValueError):
            self.engine.forecast_multi([1],'localhost-mock',30,investigate=True)
        self.assertEqual(self.engine.forecasts(),[])
        self.assertEqual(len(self.engine.client.calls),1)

    def test_manual_dates_provenance_validation_and_persistence(self):
        d=(date.today()+timedelta(days=12)).isoformat()
        for url in ('not a link','http://official.example/dates','https://'):
            with self.subTest(url=url),self.assertRaises(ValueError):
                self.engine.add_scheduled_event('Official date',d,d,url)
        with self.assertRaises(ValueError):
            self.engine.add_scheduled_event('Date',d,(date.today()+timedelta(days=4)).isoformat(),
                         'https://official.example/schedule')
        recorded=self.engine.add_scheduled_event('Monetary policy meeting',d,d,
                               'https://official.example/calendar','Sourced by user; not verified')
        self.assertEqual(recorded,1)
        items=self.engine.calendar_items()
        self.assertEqual(len(items),1)
        self.assertEqual(items[0]['kind'],'reported_schedule')
        self.engine.close()
        self.engine=NewsOracleEngine(state_dir=self.tmp.name,model_client=DeepFake())
        self.assertEqual(self.engine.store.schedules()[0]['source_note'],'Sourced by user; not verified')

    def test_calendar_contains_window_and_distinct_deadline_with_correct_ics(self):
        r=self.engine.forecast_multi([1],'localhost-mock',30,investigate=True)
        dates=self.engine.calendar_items()
        self.assertEqual({x['kind'] for x in dates},{'forecast_window','forecast_deadline'})
        start=date.fromisoformat(r['window_start'])
        self.assertEqual(len(on_day(dates,start)),1)
        deadline=date.fromisoformat(r['target_date'])
        self.assertTrue(any(i['kind']=='forecast_deadline' for i in on_day(dates,deadline)))
        ics=self.engine.calendar_ics()
        self.assertIn('BEGIN:VCALENDAR\r\n',ics)
        self.assertIn('MODEL-ESTIMATED WINDOW',ics.replace('\r\n ',''))
        self.assertIn('RESOLUTION DEADLINE',ics.replace('\r\n ',''))
        self.assertIn('DTSTART;VALUE=DATE:'+start.strftime('%Y%m%d'),ics)
        self.assertIn('DTEND;VALUE=DATE:'+(date.fromisoformat(r['window_end'])+timedelta(days=1)).strftime('%Y%m%d'),ics)

    def test_missing_window_does_not_guess_occurrence_date(self):
        today=date.today();deadline=(today+timedelta(days=10)).isoformat()
        forecasts=[dict(id=5,question='Will X occur?',target_date=deadline,probability=.31)]
        items=calendar_entries(forecasts,[])
        self.assertEqual([i['kind'] for i in items],['forecast_deadline'])

    def test_window_validate_non_destructive(self):
        today=date.today()
        with self.assertRaises(ValueError):
            validate_window((today+timedelta(days=1)).isoformat(),None,
                earliest=today,deadline=today+timedelta(days=10))
        with self.assertRaises(ValueError):
            validate_window(today.isoformat(),(today+timedelta(days=2)).isoformat(),
                earliest=today,deadline=today+timedelta(days=10))
        self.assertIsNone(validate_window(None,None,earliest=today,deadline=today+timedelta(days=10)))

    def test_invalid_investigation_structure_rejected(self):
        with self.assertRaises(ValueError):
            validate_investigation({'actors':[{'evidence_article_ids':[404]}],
                'connections':[],'downside_path':'bad','stabilising_path':'good',
                'watch_signals':[]}, {1})


if __name__=='__main__': unittest.main()
