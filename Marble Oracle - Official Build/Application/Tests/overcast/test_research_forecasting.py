"""No web or real model required: reproducible verification of v0.2 pipeline."""
from datetime import datetime, timedelta, timezone, date
import tempfile
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[2] / 'Runtime' / 'Marble_Oracle_App'))
from overcast.engine import NewsOracleEngine
from overcast.research import news_events, find_related, dossier, eligible, similarity
from overcast.forecasting import validate_vote, aggregate

NOW=datetime.now(timezone.utc)


def item(i, title, host, *, published=None, collected=None):
    return {'id':i,'title':title,'summary':'Excerpt about '+title,
        'url':f'https://{host}/story/{i}','source':host,
        'published':(published or NOW-timedelta(hours=2)).isoformat(),
        'collected':(collected or NOW-timedelta(minutes=10)).isoformat(),
        'category':'world'}


class ThreeLensFake:
    """Reports varying probabilistic lenses from the same local model."""
    def __init__(self,invalid=False):self.count=0;self.invalid=invalid;self.calls=[]
    def models(self):return ['mock-local-llm']
    def complete(self, model, system, user, max_tokens=1800):
        self.calls.append((model,system,user))
        if 'propose EXACTLY ONE useful' in user:
            return {'question':'Will the Arcadia central bank cut rates within three weeks?',
                'target_date':(date.today()+timedelta(days=21)).isoformat(),
                'resolution_criteria':'A central bank statement announces a rate cut by the target date.',
                'change_mind':'New central bank statement.'}
        self.count+=1
        return {'probability_percent':[25,55,75][min(self.count-1,2)],
            'reasoning':'A possible causal chain, inferred only from feed snippets.',
            'counterargument':'The situation can remain unchanged.',
            'cited_article_ids':[999] if self.invalid else [1],
            'reference_class':'Historical frequencies unavailable.'}


class MultiSourceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.rows=[item(1,'Arcadia central bank raises interest rates as inflation grows','first.example'),
              item(2,'Arcadia central bank raises rates as inflation grows','second.example'),
              item(3,'Arcadia inflation rates climb with central bank policy','third.example'),
              item(4,'Riverton football team wins home match','sports.example'),
              item(5,'Arcadia central bank raises interest rates as inflation grows','future.example',
                   collected=NOW+timedelta(days=2))]
        self.engine=NewsOracleEngine(state_dir=self.tmp.name,model_client=ThreeLensFake())
        self.engine.store.save_articles(self.rows)
    def tearDown(self):
        self.engine.close();self.tmp.cleanup()

    def test_relevance_and_source_diversity(self):
        self.assertGreater(similarity(self.rows[0],self.rows[1]),0.32)
        self.assertEqual(similarity(self.rows[0],self.rows[3]),0)
        expanded=self.engine.research_preview([1])
        ids=expanded['article_ids']
        self.assertIn(1,ids);self.assertIn(2,ids);self.assertNotIn(4,ids);self.assertNotIn(5,ids)
        self.assertGreaterEqual(expanded['publisher_count'],2)
        self.assertIn('second.example',expanded['publisher_domains'])
        self.assertTrue(any('NOT proof' in c for c in expanded['cautions']))

    def test_event_grouping_and_publisher_domains(self):
        events=self.engine.events(days=14)
        self.assertTrue(any(1 in e['article_ids'] and 2 in e['article_ids'] for e in events))
        for e in events:self.assertNotIn(5,e['article_ids'])

    def test_temporal_no_future_leakage(self):
        self.assertFalse(eligible(self.rows[4],as_of=NOW))
        past=NOW-timedelta(hours=1)
        # Articles were first seen just ten minutes ago, after historical cutoff.
        with self.assertRaises(ValueError):
            self.engine.research_preview([1],as_of=past)
        with self.assertRaises(ValueError):
            self.engine.forecast_multi([1],'mock-local-llm',as_of=past)
        with self.assertRaises(ValueError):
            self.engine.forecast_multi([1],'mock-local-llm',as_of=NOW+timedelta(days=1))

    def test_three_lens_median_audit_atomic_ledger(self):
        result=self.engine.forecast_multi([1],'mock-local-llm',30)
        self.assertEqual(len(self.engine.client.calls),4)
        self.assertEqual(result['probability'],0.55)
        self.assertEqual(result['valid_passes'],3)
        self.assertEqual(result['spread_percent'],50)
        self.assertGreaterEqual(result['independent_sources'],2)
        self.assertGreaterEqual(result['expanded_count'],1)
        stored=self.engine.forecasts()[0]
        self.assertAlmostEqual(stored['probability'],.55)
        audit=self.engine.forecast_audit(result['id'])
        self.assertEqual(len(audit['valid_votes']),3)
        self.assertIn('not necessarily statistically independent',audit['caveat'])
        self.assertEqual(audit['seed_article_ids'],[1])
        self.assertEqual(len(self.engine.export_json()['audits']),1)
        self.engine.resolve(result['id'],1,'https://centralbank.example/announcement')
        score=self.engine.score_report()
        self.assertEqual(score['total_forecasts'],1)
        self.assertEqual(score['unresolved'],0)
        self.assertEqual(score['reliability_bins'][0]['n'],1)
        self.assertAlmostEqual(score['brier']['score'],(1-.55)**2)

    def test_hallucinated_citations_rejected_without_saving(self):
        self.engine.client=ThreeLensFake(invalid=True)
        with self.assertRaises(ValueError):
            self.engine.forecast_multi([1],'mock-local-llm',30)
        self.assertEqual(self.engine.forecasts(),[])

    def test_base_rate_requires_provenance(self):
        with self.assertRaises(ValueError):
            self.engine.forecast_multi([1],'mock-local-llm',30,baseline=.20)
        with self.assertRaises(ValueError):
            self.engine.forecast_multi([1],'mock-local-llm',30,baseline=1.3,
                                       baseline_source='imaginary')
        self.assertEqual(self.engine.client.calls,[])
        r=self.engine.forecast_multi([1],'mock-local-llm',30,
                                     baseline=.2,baseline_source='User-supplied dated archive')
        self.assertAlmostEqual(self.engine.forecast_audit(r['id'])['base_rate'],.2)

    def test_optional_pool_cycles_distinct_local_model_ids(self):
        r=self.engine.forecast_multi([1],'model-one',30,
                  model_ids=['model-one','model-two','model-three'])
        audit=self.engine.forecast_audit(r['id'])
        self.assertEqual([v['model_id'] for v in audit['valid_votes']],
                         ['model-one','model-two','model-three'])
        self.assertEqual([call[0] for call in self.engine.client.calls],
                         ['model-one','model-one','model-two','model-three'])
        self.assertIn('model-three',self.engine.forecasts()[0]['model_id'])

    def test_bad_votes_and_aggregation(self):
        for p in (float('nan'),float('inf'),0,100,True):
            with self.subTest(p=p),self.assertRaises(ValueError):
                validate_vote({'probability_percent':p,'reasoning':'x',
                  'counterargument':'y','cited_article_ids':[1]}, {1})
        with self.assertRaises(ValueError):
            validate_vote({'probability_percent':40,'reasoning':'x',
                 'counterargument':'y','cited_article_ids':[999]}, {1})
        with self.assertRaises(ValueError):aggregate([{'probability_percent':60}])

    def test_migrates_legacy_v01_ledger_without_losing_forecast(self):
        old={'question':'Will the test event happen?', 'probability':.42,
             'target_date':(date.today()+timedelta(days=7)).isoformat(),
             'resolution_criteria':'Official statement.', 'reasoning':'Old record.',
             'counterargument':'Could fail.', 'change_mind':'New evidence.'}
        original=self.engine.store.add_forecast(old,[], 'old-model','signal-v1.0',old)
        self.engine.store.db.execute('DROP TABLE forecast_audits')
        self.engine.store.db.commit();self.engine.close()
        self.engine=NewsOracleEngine(state_dir=self.tmp.name,model_client=ThreeLensFake())
        self.assertEqual(self.engine.get_forecast(original) if hasattr(self.engine,'get_forecast')
                         else self.engine.forecasts()[0]['id'],original)
        self.assertIsNone(self.engine.forecast_audit(original))
        self.assertTrue(self.engine.forecast_multi([1],'mock-local-llm',30)['id']>original)

    def test_two_of_three_valid_lenses_succeeds_and_preserves_failure(self):
        class OccasionallyInvalid(ThreeLensFake):
            def complete(self,*args,**kwargs):
                output=super().complete(*args,**kwargs)
                if self.count==2:output['cited_article_ids']=[5000]
                return output
        self.engine.client=OccasionallyInvalid()
        result=self.engine.forecast_multi([1],'mock-local-llm',30)
        self.assertEqual(result['valid_passes'],2)
        self.assertEqual(result['probability'],.5) # median of 25% and 75%
        audit=self.engine.forecast_audit(result['id'])
        self.assertEqual(len(audit['failed_lenses']),1)
        self.assertEqual(audit['failed_lenses'][0]['lens'],'INSIDE VIEW')

    def test_reopens_existing_ledger_schema(self):
        self.engine.close()
        self.engine=NewsOracleEngine(state_dir=self.tmp.name,model_client=ThreeLensFake())
        result=self.engine.forecast_multi([1],'mock-local-llm',30)
        self.engine.close()
        self.engine=NewsOracleEngine(state_dir=self.tmp.name,model_client=ThreeLensFake())
        self.assertIsNotNone(self.engine.forecast_audit(result['id']))
        self.assertEqual(len(self.engine.forecasts()),1)


if __name__=='__main__':unittest.main()
