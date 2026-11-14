"""Regression checks for the integrated AUGURSPEX companion (no remote HTTP)."""
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

APP = Path(__file__).resolve().parents[1] / 'Runtime' / 'Marble_Oracle_App'
sys.path.insert(0, str(APP))
from Augurspex.augurspex.core import read_settings, save_settings
from Augurspex.augurspex.server import LocalServer, Handler
import oracle_augurspex_bridge as bridge


class AugurspexRegressionTests(unittest.TestCase):
    def test_explicitly_empty_chart_slots_survive_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            save_settings(home, {'layout': 4, 'symbols': [''] * 9})
            actual = read_settings(home)
            self.assertEqual(actual['symbols'], [''] * 9)

    def test_no_saved_settings_uses_starter_symbols(self):
        with tempfile.TemporaryDirectory() as directory:
            data = read_settings(Path(directory))
            self.assertTrue(any(data['symbols']))

    def test_loopback_dashboard_and_api_security(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            root = APP / 'Augurspex' / 'augurspex'
            srv = LocalServer(('127.0.0.1', 0), Handler, home=home, root=root)
            t = threading.Thread(target=srv.serve_forever, kwargs={'poll_interval': .05}, daemon=True)
            t.start()
            url = 'http://127.0.0.1:%d/' % srv.server_port
            try:
                with urlopen(url, timeout=2) as response:
                    self.assertIn(b'AUGURSPEX', response.read())
                with urlopen(url + 'api/bootstrap', timeout=2) as response:
                    initial = json.load(response)
                    self.assertEqual(len(initial['settings']['symbols']), 9)
                    token = initial['token']
                data = json.dumps({'symbols': [''] * 9}).encode()
                unauth = Request(url+'api/settings', data=data, headers={'Content-Type':'application/json'},method='POST')
                with self.assertRaises(HTTPError) as e:
                    urlopen(unauth, timeout=2)
                self.assertEqual(e.exception.code, 403)
                malicious = Request(url+'api/settings', data=data,
                                    headers={'Content-Type':'application/json','X-Augurspex-Token':token,
                                             'Origin':'https://not-the-suite.invalid'}, method='POST')
                with self.assertRaises(HTTPError) as e:
                    urlopen(malicious, timeout=2)
                self.assertEqual(e.exception.code,403)
                authorized = Request(url+'api/settings', data=data,
                                     headers={'Content-Type':'application/json','X-Augurspex-Token':token},method='POST')
                with urlopen(authorized, timeout=2) as response:
                    self.assertTrue(json.load(response)['ok'])
                with urlopen(url+'api/bootstrap', timeout=2) as response:
                    self.assertEqual(json.load(response)['settings']['symbols'], [''] * 9)
                # A server restart/reopen can confirm the active endpoint.
                ready = home/'bridge.json'
                ready.write_text(json.dumps({'url':url,'pid':os.getpid()}))
                self.assertEqual(bridge._read_active_url(ready),url)
                ready.write_text(json.dumps({'url':'https://example.com/','pid':os.getpid()}))
                self.assertIsNone(bridge._read_active_url(ready))
                with patch.object(bridge, '_ready_file', return_value=home/'bridge.json'), \
                     patch.object(bridge, '_process', None), \
                     patch.object(bridge.webbrowser,'open', return_value=True) as open_browser:
                    (home/'bridge.json').write_text(json.dumps({'url':url,'pid':os.getpid()}))
                    self.assertFalse(bridge.launch())
                    open_browser.assert_called_once_with(url, new=1)
                quit_request = Request(url+'api/quit', data=b'{}', headers={
                    'Content-Type':'application/json','X-Augurspex-Token':token},method='POST')
                with urlopen(quit_request,timeout=2) as response:
                    self.assertTrue(json.load(response)['ok'])
            finally:
                srv.shutdown()
                t.join(timeout=2)
                srv.server_close()

    def test_cli_ready_file_lifecycle_no_browser(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'ready.json'
            env = dict(os.environ, XDG_CONFIG_HOME=str(Path(directory)/'config'),
                       XDG_CACHE_HOME=str(Path(directory)/'cache'))
            cmd = [sys.executable, str(APP/'Augurspex'/'run.py'),
                   '--no-browser','--ready-file',str(path)]
            proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
            try:
                deadline=time.monotonic()+5
                while time.monotonic()<deadline and not path.exists() and proc.poll() is None:
                    time.sleep(.05)
                self.assertTrue(path.is_file(), f'child exited: {proc.poll()}')
                ready=json.loads(path.read_text())
                self.assertEqual(ready['pid'],proc.pid)
                self.assertEqual(bridge._read_active_url(path),ready['url'])
                with urlopen(ready['url']+'api/bootstrap') as response:
                    token=json.load(response)['token']
                quit_request=Request(ready['url']+'api/quit',data=b'{}',method='POST',
                    headers={'Content-Type':'application/json','X-Augurspex-Token':token})
                urlopen(quit_request,timeout=2).close()
                proc.wait(timeout=5)
                self.assertFalse(path.exists(), 'ready file not removed after quit')
            finally:
                if proc.poll() is None:
                    proc.terminate()
                    proc.wait(timeout=5)

if __name__ == '__main__':
    unittest.main()
