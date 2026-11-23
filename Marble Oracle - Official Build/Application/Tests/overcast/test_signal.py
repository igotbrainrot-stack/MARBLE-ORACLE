import json
import os
from datetime import date, timedelta
from pathlib import Path
import sys
import tempfile
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[2] / 'Runtime' / 'Marble_Oracle_App'))
from overcast.engine import NewsOracleEngine
from overcast.feeds import parse_feed, normalize_url
from overcast.lmstudio import LMStudioClient, LMStudioError, parse_json_response
from overcast.store import Store

RSS=b'''<?xml version="1.0"?><rss version="2.0"><channel>
<item><title>Sample event A</title><link>https://example.org/a?utm_source=z&amp;lang=en</link>
<description><![CDATA[<b>Excerpt</b> text]]></description><pubDate>Sat, 21 Nov 2026 09:00:00 GMT</pubDate></item>
<item><title>Sample event B</title><link>https://example.org/b</link>
<description>Story B</description></item></channel></rss>'''
ATOM=b'''<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Atom story</title><link rel="alternate" href="https://example.com/atom"/><summary>Claim only</summary><updated>2026-11-19T09:00:00Z</updated></entry></feed>'''


class FakeModel:
    def __init__(self):self.messages=[]
    def models(self):return ['mock/local']
    def complete(self,model,system,user,max_tokens=1800):
        self.messages.append((model,system,user))
        if 'probability_percent' in user:
            return {'question':'Will a measurable event occur by the target date?',
                    'probability_percent':63,'target_date':(date.today()+timedelta(days=20)).isoformat(),
                    'resolution_criteria':'An official independent source reports the event.',
                    'reasoning':'Based on selected headline evidence, this is an inference.',
                    'counterargument':'Evidence is thin.','change_mind':'New official data.'}
        return {'title':'Current headline summary','briefing':'Publisher claims an event.',
                'uncertainties':'Need to verify primary records.'}


class SignalTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.store=Store(Path(self.tmp.name))

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_feed_rss_and_atom(self):
        items=parse_feed(RSS,'Mock','world')
        self.assertEqual(len(items),2)
        self.assertEqual(items[0]['url'],'https://example.org/a?lang=en')
        self.assertEqual(items[0]['summary'],'Excerpt text')
        self.assertTrue(items[0]['published'].startswith('2026-11-21'))
        atom=parse_feed(ATOM,'Mock')
        self.assertEqual(atom[0]['title'],'Atom story')
        self.assertEqual(atom[0]['url'],'https://example.com/atom')

    def test_disallow_xml_entities(self):
        with self.assertRaises(ValueError):
            parse_feed(b'<!DOCTYPE a [<!ENTITY b SYSTEM "file:///etc/passwd">]><rss/>','x')

    def test_deduplicate_evidence(self):
        items=parse_feed(RSS,'Mock')
        self.assertEqual(self.store.save_articles(items),2)
        self.assertEqual(self.store.save_articles(items),0)
        self.assertEqual(len(self.store.articles()),2)
        self.assertEqual(len(self.store.article_ids([1,2])),2)
        with self.assertRaises(ValueError):self.store.article_ids([1,999])

    def test_forecast_immutable_score(self):
        self.store.close()
        engine=NewsOracleEngine(state_dir=self.tmp.name,model_client=FakeModel())
        try:
            engine.store.save_articles(parse_feed(RSS,'Mock'))
            ids=[x['id'] for x in engine.articles()]
            b=engine.briefing(ids,'mock/local')
            self.assertEqual(b['id'],1)
            f=engine.forecast(ids,'mock/local',30)
            self.assertAlmostEqual(f['probability'],0.63)
            self.assertEqual(f['independent_sources'],1)
            self.assertEqual(len(engine.forecasts()),1)
            engine.resolve(f['id'],1,'https://example.com/verified','Verified record')
            self.assertAlmostEqual(engine.performance()['score'],(0.63-1)**2)
            with self.assertRaises(Exception):engine.resolve(f['id'],0,'https://example.com/incorrect')
            entry=engine.forecasts()[0]
            self.assertEqual(entry['probability'],0.63)
            self.assertEqual(entry['outcome'],1)
            self.assertEqual(engine.export_json()['format'],'news-oracle-ledger-v1')
        finally:
            engine.close()
            self.store=Store(self.tmp.name)

    def test_local_only_model(self):
        for url in ['https://127.0.0.1:1234/v1','http://192.168.1.1:1234/v1',
                    'http://example.com/v1','http://localhost:1234/untrusted','file:///etc/passwd']:
            with self.subTest(url=url):
                with self.assertRaises(ValueError):LMStudioClient(url)
        LMStudioClient('http://localhost:1234/v1')
        LMStudioClient('http://127.0.0.1:1234/v1')

    def test_parse_model_json(self):
        self.assertEqual(parse_json_response('```json\n{"a": 1}\n```')['a'],1)
        self.assertEqual(parse_json_response('answer: {"ok": true}')['ok'],True)
        with self.assertRaises(LMStudioError):parse_json_response('not json')


    def test_real_http_protocol_with_mock_local_server(self):
        """Exercise the actual /v1/models and chat JSON HTTP contract offline."""
        seen=[]
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_GET(self):
                self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers()
                self.wfile.write(b'{"data":[{"id":"mock/local"}]}')
            def do_POST(self):
                size=int(self.headers.get('Content-Length',0))
                body=json.loads(self.rfile.read(size))
                seen.append((self.path,body))
                content=json.dumps({'title':'Test','briefing':'One sentence','uncertainties':'Needs corroboration'})
                response=json.dumps({'choices':[{'message':{'content':content}}]}).encode()
                self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers()
                self.wfile.write(response)
        server=HTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            client=LMStudioClient(f'http://127.0.0.1:{server.server_port}/v1',timeout=4)
            self.assertEqual(client.models(),['mock/local'])
            self.assertEqual(client.complete('mock/local','System','User')['title'],'Test')
            self.assertEqual(seen[0][0],'/v1/chat/completions')
            self.assertEqual(seen[0][1]['model'],'mock/local')
            self.assertEqual(seen[0][1]['stream'],False)
        finally:
            server.shutdown();server.server_close();thread.join(timeout=2)

    def test_invalid_probability_does_not_store(self):
        self.store.close()
        class Wrong(FakeModel):
            def complete(self,*args,**kwargs):
                x=super().complete(*args,**kwargs);x['probability_percent']=180;return x
        engine=NewsOracleEngine(state_dir=self.tmp.name,model_client=Wrong())
        try:
            engine.store.save_articles(parse_feed(RSS,'Mock'))
            with self.assertRaises(ValueError):engine.forecast([1],'mock/local',30)
            self.assertFalse(engine.forecasts())
        finally:
            engine.close()
            self.store=Store(self.tmp.name)


if __name__=='__main__':unittest.main()
