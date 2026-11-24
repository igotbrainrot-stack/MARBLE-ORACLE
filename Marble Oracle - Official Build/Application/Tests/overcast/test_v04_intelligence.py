"""v0.4 feature regression tests; no internet, graphics, or real LM Studio needed."""
from __future__ import annotations

from datetime import date, datetime, timezone, timedelta
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[2] / 'Runtime' / 'Marble_Oracle_App'))
from overcast.engine import NewsOracleEngine
from overcast.timing import checkpoints,validate_timing
from overcast.event_graph import validate_claims,relationship_leads
from overcast.gap_research import validate_plan,retrieve_gap_evidence


def row(i,title,domain,*,collected=None):
    now=datetime.now(timezone.utc)
    return {'id':i,'title':title,'summary':title+' investigation excerpt.',
        'url':f'https://{domain}/news/{i}','source':domain,
        'category':'world', 'published':(now-timedelta(hours=3)).isoformat(),
        'collected':(collected or now-timedelta(hours=2)).isoformat()}


class V04Fake:
    def __init__(self):self.prompts=[]
    def models(self):return ['local-only']
    def complete(self,model,system,user,max_tokens=1500):
        self.prompts.append(user)
        if 'propose EXACTLY ONE useful' in user:
            return {'question':'Will Arcadia announce a trade tariff by the deadline?',
                'target_date':(date.today()+timedelta(days=20)).isoformat(),
                'resolution_criteria':'Government gazette publishes a tariff notice by the deadline.',
                'change_mind':'A signed trade agreement.',
                'expected_window_start':None,'expected_window_end':None,'timing_basis':None}
        if 'crucial missing or CONFLICTING information' in user:
            return {'gaps':['Does the government contradict its trade statement?'],
                'support_terms':['Arcadia trade tariffs'],
                'disconfirm_terms':['Arcadia tariff exemption']}
        if 'UNVERIFIED incentive' in user or 'STRATEGIC' in user:
            return {'actors':[], 'connections':[], 'downside_path':'Trade conflict may escalate.',
                    'stabilising_path':'Trade compromise may stabilize.',
                    'watch_signals':['Official government tariff statements']}
        if 'TIMING CONDITIONAL' in user:
            # Checkpoints supplied by the implementation; recover exact JSON list.
            import json,re
            match=re.search(r'Checkpoints: (\[.*?\])\n',user)
            days=json.loads(match.group(1))
            vals=[round((i+1)*100/len(days),3) for i in range(len(days))]
            vals[-1]=100
            return {'checkpoints':[{'date':day,'conditional_cumulative_percent':v}
                                   for day,v in zip(days,vals)],
                    'timing_reasoning':'No specific event date established from sources.',
                    'evidence_article_ids':[1]}
        if 'EXACT contiguous fragment' in user:
            return {'claims':[{'article_id':1,'actor':'Arcadia','action':'discussed tariffs',
                 'target':'Foreign exporters','location':'Arcadia','event_date':None,
                 'kind':'announced_intent','evidence_quote':'Arcadia government discusses trade tariff',
                 'claim_text':'A report says Arcadia discussed trade tariffs.'}]}
        return {'probability_percent':40,'reasoning':'Possible tariff but thin sources.',
                'counterargument':'A trade deal might resolve the issue.',
                'reference_class':'unavailable','cited_article_ids':[1]}


class V04Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.client=V04Fake()
        self.engine=NewsOracleEngine(state_dir=self.tmp.name,model_client=self.client)
        self.engine.store.save_articles([row(1,'Arcadia government discusses trade tariff','news.example'),
                     row(2,'Arcadia trade agreement negotiations continue','other.example'),
                     row(3,'Arcadia tariff exemption discussed in parliament','third.example'),
                     row(4,'Arcadia tariff exemption report from future','future.example',
                        collected=datetime.now(timezone.utc)+timedelta(days=1))])
    def tearDown(self):self.engine.close();self.tmp.cleanup()

    def test_gap_search_historical_safe_and_required_countersearch(self):
        plan={'gaps':['What does the parliament say?'],'support_terms':['tariff'],
              'disconfirm_terms':['tariff exemption']}
        hits=retrieve_gap_evidence(plan,self.engine.store.articles(),[1],
                        as_of=datetime.now(timezone.utc))
        self.assertTrue(any(hit['matched_disconfirm_terms'] for hit in hits))
        self.assertNotIn(4,[x['article']['id'] for x in hits])
        with self.assertRaises(ValueError):validate_plan({**plan,'disconfirm_terms':[]})

    def test_multi_pipeline_timing_gap_and_frozen_packet(self):
        result=self.engine.forecast_multi([1],'local-only',30,expand=False,
                           gap_search=True,timing=True)
        self.assertTrue(result['conditional_timing'])
        self.assertGreaterEqual(result['gap_research_added'],1)
        self.assertEqual(result['probability'],0.4)
        audit=self.engine.forecast_audit(result['id'])
        self.assertTrue(audit['gap_research']['attempted'])
        self.assertEqual(audit['conditional_timing']['non_occurrence_probability'],0.6)
        frozen=self.engine.forecast_packet(result['id'])
        self.assertTrue(frozen['checksum_valid'])
        self.assertEqual(frozen['packet']['mode'],audit['method'])
        self.assertEqual(len(frozen['packet']['articles']),len(audit['expanded_article_ids']))
        ids=[a['id'] for a in frozen['packet']['articles']]
        self.assertNotIn(4,ids)
        calendar=self.engine.calendar_items()
        self.assertTrue(any(x['kind']=='forecast_timing_bucket' for x in calendar))
        self.assertTrue(any(x['kind']=='forecast_deadline' for x in calendar))
        self.assertIn('MODEL-ESTIMATED PROBABILITY BUCKET',self.engine.calendar_ics())
        with self.engine.store.db:
            self.engine.store.db.execute('UPDATE forecast_packets SET packet_json=? WHERE forecast_id=?',
                                         ('{"tampered":true}',result['id']))
        self.assertFalse(self.engine.forecast_packet(result['id'])['checksum_valid'])

    def test_timing_monotonic_and_buckets_consistent(self):
        days=checkpoints(date.today(),date.today()+timedelta(days=17))
        data={'checkpoints':[{'date':d,'conditional_cumulative_percent':(i+1)*100/len(days)}
                             for i,d in enumerate(days)],
              'evidence_article_ids':[1],'timing_reasoning':'uncertain'}
        result=validate_timing(data,days,{1},0.3)
        self.assertAlmostEqual(sum(x['unconditional_event_bucket'] for x in result['checkpoints']),.3,places=4)
        data['checkpoints'][1]['conditional_cumulative_percent']=-1
        with self.assertRaises(ValueError):validate_timing(data,days,{1},.3)
        data['checkpoints'][1]['conditional_cumulative_percent']=20
        data['evidence_article_ids']=[999]
        with self.assertRaises(ValueError):validate_timing(data,days,{1},.3)

    def test_claim_extraction_quotes_and_relationships(self):
        output=self.engine.extract_events([1],'local-only')
        self.assertEqual(output['new_claims'],1)
        self.assertEqual(output['claims'][0]['status'],'unverified_reported_claim')
        self.assertEqual(self.engine.event_claims()[0]['source_article_id'],1)
        self.assertEqual(self.engine.extract_events([1],'local-only')['new_claims'],0)
        invalid={'claims':[{**output['claims'][0],'evidence_quote':'Unrelated unobserved secret meeting'}]}
        with self.assertRaises(ValueError):
            validate_claims(invalid,self.engine.store.article_ids([1]),as_of=datetime.now(timezone.utc))
        claims=[{'id':1,'article_id':1,'actor':'Arcadia Finance Ministry'},
                {'id':2,'article_id':2,'actor':'Arcadia Trade Ministry'},
                {'id':3,'article_id':3,'actor':'Other'}]
        leads=relationship_leads(claims)
        self.assertEqual(len(leads),1)
        self.assertEqual(leads[0]['relation'],'unverified_shared_actor')

    def test_reference_class_needs_sources_and_sample_adequacy(self):
        a=date.today()-timedelta(days=365);b=date.today()-timedelta(days=1)
        rid=self.engine.add_reference_class('Trade policy announcements','TRADE',40,12,
                     a.isoformat(),b.isoformat(),'https://stats.example/history')
        self.assertEqual(self.engine.reference_classes()[0]['observed_rate'],.3)
        self.assertAlmostEqual(self.engine.reference_classes()[0]['smoothed_rate'],13/42,places=6)
        with self.assertRaises(ValueError):
            self.engine.add_reference_class('Invalid','TRADE',4,5,a.isoformat(),b.isoformat(),'https://example.org')
        # Matching reference class is opt-in, source-tagged and does not force the odds.
        result=self.engine.forecast_multi([1],'local-only',30,reference_class_id=rid)
        self.assertAlmostEqual(result['probability'],.4)
        audit=self.engine.forecast_audit(result['id'])
        self.assertEqual(audit['reference_class_id'],rid)
        self.assertIn('User-entered',audit['base_rate_source'])
        # Wrong topic is rejected.
        wrong=self.engine.add_reference_class('Markets only','MARKETS',40,12,
                     a.isoformat(),b.isoformat(),'https://stats.example/market')
        with self.assertRaises(ValueError):self.engine.forecast_multi([1],'local-only',30,reference_class_id=wrong)

    def test_legacy_quick_forecast_snapshot_and_brier_reference(self):
        output={'question':'Will the tariff occur?', 'probability':.6,
                'target_date':(date.today()+timedelta(days=10)).isoformat(),
                'resolution_criteria':'A public official notice.',
                'reasoning':'Based on announcement.',
                'counterargument':'May be withdrawn.', 'change_mind':'Negotiations.'}
        rid=self.engine.store.add_forecast(output,[],'test','signal-v1.0',output,
                      snapshot={'as_of_utc':datetime.now(timezone.utc).isoformat(),'articles':[]})
        self.engine.resolve(rid,1,'https://authority.example/outcome')
        score=self.engine.score_report()
        self.assertEqual(score['naive_50_brier'],.25)
        self.assertAlmostEqual(score['skill_vs_naive_50'],1-(.4*.4)/.25)


if __name__=='__main__':unittest.main()
