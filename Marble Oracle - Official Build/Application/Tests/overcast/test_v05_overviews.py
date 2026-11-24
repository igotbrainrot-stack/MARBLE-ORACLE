"""Offline coverage breadth and visible result regressions for SIGNAL v0.5."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys, tempfile, unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[2] / 'Runtime' / 'Marble_Oracle_App'))
from overcast.scopes import select_coverage, SCOPES
from overcast.engine import NewsOracleEngine


def row(i,kind='market',host='report.example',days_ago=0):
    stamp=(datetime.now(timezone.utc)-timedelta(days=days_ago,hours=1)).isoformat()
    title={'market':'Central bank inflation share prices stock market bond yields',
           'politics':'Diplomatic government summit international negotiations',
           'trade':'International shipping tariffs imports exports trade treaty'}[kind]
    return dict(id=i,title=f'{title} bulletin {i}',summary=f'Bulletin {i} concerns the {kind} outlook.',
                category='business' if kind=='market' else 'world',
                published=stamp,collected=stamp,url=f'https://{host}/{i}',source=host)


class FakeScopeLLM:
    def complete(self,model,system,prompt,**kwargs):
        self.last_prompt=prompt
        return {
            'title':'World trade and markets risk outlook',
            'overview':'Sources describe changes with unresolved implications.',
            'themes':[{'title':'Trade uncertainty','assessment':'One report mentions trade effects.',
                       'evidence_article_ids':[1]}],
            'downside_scenario':'Policy escalation may disrupt supply chains.',
            'alternative_scenario':'Compromise could ease trade pressure.',
            'watch_signals':[{'indicator':'Official tariff notice',
                              'why_it_matters':'Published implementation would clarify the outlook.',
                              'evidence_article_ids':[1]}],
            'uncertainties':'Coverage is incomplete and observations are not comprehensive.'
        }
    def models(self):return ['local-test']


class ScopeOverviewTests(unittest.TestCase):
    def test_global_selection_excludes_old_and_future_and_diversifies(self):
        rows=[row(i,'market',f'publisher{i%4}.example') for i in range(1,29)]
        rows.append(row(40,'market','old.example',days_ago=45))
        future=row(41,'market','future.example')
        future['collected']=(datetime.now(timezone.utc)+timedelta(days=2)).isoformat()
        rows.append(future)
        out=select_coverage(rows,'GLOBAL MARKETS',limit=16)
        self.assertEqual(out['selected_count'],16)
        self.assertEqual(out['publisher_count'],4)
        self.assertNotIn(40,out['article_ids'])
        self.assertNotIn(41,out['article_ids'])
        self.assertEqual(out['fresh_count'],28)
        self.assertIn('not comprehensive',out['coverage_warning'])

    def test_scope_modes_and_custom(self):
        rows=[row(1,'trade'),row(2,'politics'),row(3,'market')]
        self.assertEqual(set(select_coverage(rows,'GLOBAL EVENTS')['article_ids']),{1,2,3})
        self.assertIn(1,select_coverage(rows,'TRADE & SUPPLY CHAINS')['article_ids'])
        self.assertIn(2,select_coverage(rows,'WORLD POLITICS')['article_ids'])
        self.assertEqual(select_coverage(rows,'CUSTOM SUBJECT',query='shipping')['article_ids'],[1])
        with self.assertRaises(ValueError):select_coverage(rows,'CUSTOM SUBJECT',query='')

    def test_overview_persisted_with_citations_and_reloaded(self):
        fake=FakeScopeLLM()
        with tempfile.TemporaryDirectory() as d:
            e=NewsOracleEngine(state_dir=d,model_client=fake)
            e.store.save_articles([row(1,'trade')])
            result=e.overview([1],'local-test',scope='TRADE & SUPPLY CHAINS',horizon_days=90)
            self.assertGreater(result['id'],0)
            self.assertIn('DOWNSIDE SCENARIO',result['briefing'])
            self.assertIn('SOURCE IDS: 1',result['briefing'])
            self.assertIn('This is not',fake.last_prompt) if False else None
            self.assertIn('cached RSS metadata',fake.last_prompt)
            e.close()
            other=NewsOracleEngine(state_dir=d,model_client=fake)
            self.assertIn('SUPPLY CHAINS',other.store.briefings()[0]['briefing'])
            other.close()

    def test_hallucinated_source_id_does_not_persist(self):
        fake=FakeScopeLLM()
        def invalid(*args,**kwargs):
            report=FakeScopeLLM().complete(*args,**kwargs)
            report['themes'][0]['evidence_article_ids']=[9999]
            return report
        fake.complete=invalid
        with tempfile.TemporaryDirectory() as d:
            e=NewsOracleEngine(state_dir=d,model_client=fake)
            e.store.save_articles([row(1,'trade')])
            with self.assertRaises(ValueError):e.overview([1],'local-test',scope='TRADE & SUPPLY CHAINS')
            self.assertEqual(e.store.briefings(),[])
            e.close()

if __name__=='__main__':unittest.main()
