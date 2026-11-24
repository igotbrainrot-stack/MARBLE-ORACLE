"""Regression tests: a nested LM Studio HTTP 400 may actually mean GPU device loss."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
import threading
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'Runtime' / 'Marble_Oracle_App'))
from overcast.lmstudio import (LMStudioClient, LMStudioDeviceLostError,
                                  LMStudioHTTPError)


class StubServer:
    def __init__(self, responses):
        self.responses = responses
        self.requests = []
        outer = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_POST(self):
                length = int(self.headers.get('Content-Length', '0'))
                outer.requests.append(json.loads(self.rfile.read(length)))
                i = min(len(outer.requests)-1, len(outer.responses)-1)
                status, body = outer.responses[i]
                encoded = json.dumps(body).encode('utf-8')
                self.send_response(status)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)
        self.http = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.http.serve_forever,daemon=True)
    def __enter__(self):
        self.thread.start()
        return self
    def __exit__(self, *_):
        self.http.shutdown()
        self.http.server_close()
        self.thread.join(timeout=2)
    def client(self):
        return LMStudioClient(f'http://127.0.0.1:{self.http.server_port}/v1', timeout=3)


class VulkanRecoveryTests(unittest.TestCase):
    def test_nested_gpu_failure_is_not_retried(self):
        nested = {'code':500,'message':'decode() failed: vk::Queue::submit: ErrorDeviceLost','type':'server_error'}
        payload = {'error':f'Engine protocol predict stream returned an error: {json.dumps(nested)}'}
        with StubServer([(400,payload)]) as srv:
            with self.assertRaises(LMStudioDeviceLostError) as cm:
                srv.client().complete('test-model','system','briefing')
            self.assertEqual(len(srv.requests),1, 'Device lost must not cause a retry')
            self.assertIn('restart LM Studio',str(cm.exception))
            self.assertIn('ErrorDeviceLost',str(cm.exception))

    def test_unsupported_json_mode_gets_one_compatibility_retry(self):
        first={'error':'Unsupported response_format: json_object'}
        second={'choices':[{'message':{'content':'{"ok":true}'}}]}
        with StubServer([(400,first),(200,second)]) as srv:
            output=srv.client().complete('test-model','system','test')
            self.assertTrue(output['ok'])
            self.assertEqual(len(srv.requests),2)
            self.assertIn('response_format',srv.requests[0])
            self.assertNotIn('response_format',srv.requests[1])

    def test_other_http_400_is_not_retried(self):
        with StubServer([(400, {'error':'Invalid model configuration: context exceeded'})]) as srv:
            with self.assertRaises(LMStudioHTTPError):
                srv.client().complete('test-model','system','test')
            self.assertEqual(len(srv.requests),1)

    def test_optional_gpu_loss_aborts_deep_pipeline(self):
        from tempfile import TemporaryDirectory
        from datetime import date,timedelta,datetime,timezone
        from overcast.engine import NewsOracleEngine
        class Fake:
            calls=0
            def complete(self,*args,**kwargs):
                self.calls+=1
                if self.calls==1:
                    return {'question':'Will Arcadia publish a new tariff decision in 21 days?',
                        'target_date':(date.today()+timedelta(days=21)).isoformat(),
                        'resolution_criteria':'Official published tariff notice by deadline.',
                        'change_mind':'Updated government trade notice.'}
                raise LMStudioDeviceLostError(400,'decode() failed: vk::Queue::submit: ErrorDeviceLost')
        with TemporaryDirectory() as d:
            fake=Fake()
            engine=NewsOracleEngine(state_dir=d,model_client=fake)
            try:
                stamp=datetime.now(timezone.utc).isoformat()
                engine.store.save_articles([{'title':'Arcadia announces consideration of tariff increase',
                    'summary':'Government considering higher tariffs.', 'source':'Example Publisher',
                    'url':'https://example.org/news/1', 'published':stamp,'collected':stamp,
                    'category':'world'}])
                article_id=engine.store.articles(1)[0]['id']
                with self.assertRaises(LMStudioDeviceLostError):
                    engine.forecast_multi([article_id],'fake',30,expand=False,
                                           investigate=True,gap_search=False,timing=False)
                self.assertEqual(fake.calls,2, 'Do not continue to probability passes after the GPU dies')
                self.assertEqual(len(engine.forecasts()),0)
            finally:engine.close()

if __name__ == '__main__': unittest.main()
