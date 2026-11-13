"""Account-free localhost application. Python stdlib only; zero market-data scraping."""
from __future__ import annotations
import argparse
import json
import os
import shutil
import subprocess
import secrets
import sys
import threading
import webbrowser
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
from .providers import MarketRouter, ProviderError, SOURCE_INFO
from .core import (read_settings, merge_watchlists, save_settings, tv_symbol, sanitize_settings, update_watchlist)

ROOT = Path(__file__).resolve().parent
HOME = Path.home()
MEDIA = {'/': ('index.html', 'text/html; charset=utf-8'),
         '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
         '/style.css': ('style.css', 'text/css; charset=utf-8'),
         '/icon.svg': ('icon.svg', 'image/svg+xml')}

class LocalServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    def __init__(self, address, handler, home=HOME, root=ROOT):
        self.home = Path(home)
        self.root = Path(root)
        self.token = secrets.token_urlsafe(32)
        self.market_router = MarketRouter(cache_dir=self.home / '.cache/augurspex/market')
        super().__init__(address, handler)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Do not log watchlist symbols or arbitrary network data to disk.
        if urlsplit(self.path).path not in ('/api/settings', '/api/bootstrap', '/api/history', '/api/fx'):
            super().log_message(format, *args)

    def _headers(self, status, content_type, size):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(size))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('X-Frame-Options', 'DENY')
        self.end_headers()

    def _send(self, payload: bytes, status=200, mime='application/json; charset=utf-8'):
        self._headers(status, mime, len(payload))
        self.wfile.write(payload)

    def _json(self, obj, status=200):
        self._send(json.dumps(obj, ensure_ascii=False).encode('utf-8'), status)

    def _valid_host(self):
        host = self.headers.get('Host', '')
        return host in {f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}

    def do_GET(self):
        if not self._valid_host():
            return self._json({'error':'Invalid local host'}, 403)
        parts = urlsplit(self.path)
        path = parts.path
        if path == '/api/providers':
            return self._json({'sources':SOURCE_INFO, 'key_free':True, 'optional_api_key_sources':['alpha','twelve'], 'no_login':True})
        if path == '/api/history':
            query = parse_qs(parts.query)
            symbol=query.get('symbol',[''])[0][:48]
            period=query.get('period',['D'])[0][:5]
            provider=query.get('source',['auto'])[0][:12]
            try:
                return self._json(self.server.market_router.fetch(symbol,period,provider))
            except ProviderError as exc:
                return self._json({'error':str(exc),'symbol':symbol,'provider':provider},503)
        if path == '/api/fx':
            query = parse_qs(parts.query)
            base=query.get('base',['AUD'])[0][:5]
            quote=query.get('quote',['USD'])[0][:5]
            try:return self._json(self.server.market_router.fx(base,quote))
            except ProviderError as exc:return self._json({'error':str(exc)},503)
        if path == '/api/bootstrap':
            settings = read_settings(self.server.home)
            watch, source = merge_watchlists(self.server.home, self.server.root/'default_watchlist.json', settings)
            return self._json({'token':self.server.token, 'settings':settings, 'watchlist':watch,
                               'source':source, 'provider':'TradingView widgets; Kraken/Coinbase public WebSockets; Coinbase/Kraken/Stooq/Naver/Nasdaq/Yahoo/Frankfurter history; Alpha Vantage/Twelve Data optional with API keys',
                               'notes':'No account required for public sources; optional API-key feeds require your own credentials and exchange entitlements. Stocks may be delayed or EOD; crypto trade prices are venue-specific.'})
        if path in MEDIA:
            name, mime = MEDIA[path]
            try: payload = (self.server.root/name).read_bytes()
            except OSError: return self._json({'error':'Missing asset'}, 404)
            return self._send(payload, mime=mime)
        self._json({'error':'Not found'}, 404)

    def do_POST(self):
        if not self._valid_host():
            return self._json({'error':'Invalid local host'}, 403)
        origin = self.headers.get('Origin', '')
        if origin and origin not in (f'http://127.0.0.1:{self.server.server_port}', f'http://localhost:{self.server.server_port}'):
            return self._json({'error':'Invalid origin'}, 403)
        if self.headers.get('X-Augurspex-Token') != self.server.token:
            return self._json({'error':'Invalid session token'}, 403)
        if self.headers.get('Content-Type', '').split(';',1)[0].strip().lower() != 'application/json':
            return self._json({'error':'JSON required'}, 415)
        try:
            size = int(self.headers.get('Content-Length','0'))
            if size < 2 or size > 65536: raise ValueError('Invalid request size')
            data = json.loads(self.rfile.read(size))
            if not isinstance(data, dict): raise ValueError('Object expected')
        except (ValueError, UnicodeError) as exc:
            return self._json({'error':str(exc)},400)
        path = urlsplit(self.path).path
        if path == '/api/watchlist':
            try:
                result = update_watchlist(self.server.home, self.server.root/'default_watchlist.json',
                    read_settings(self.server.home), data.get('items'), data.get('mode', 'merge'),
                    data.get('confirm_empty') is True)
                return self._json({'ok':True, **result})
            except ValueError as exc:
                return self._json({'error':str(exc)},400)
        if path == '/api/settings':
            clean = save_settings(self.server.home, data)
            return self._json({'ok':True, 'settings':clean})
        if path == '/api/quit':
            self._json({'ok':True})
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return
        self._json({'error':'Unknown action'},404)


def open_dashboard_window(url):
    """Prefer an app-style Chromium window; fall back to the default browser."""
    for name in ('chromium', 'chromium-browser', 'google-chrome',
                 'google-chrome-stable', 'brave-browser', 'microsoft-edge'):
        executable = shutil.which(name)
        if executable:
            try:
                subprocess.Popen([executable, '--new-window', '--app=' + url],
                                 stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL, start_new_session=True)
                return
            except OSError:
                continue
    webbrowser.open(url)


def main(argv=None):
    p = argparse.ArgumentParser(description='AUGURSPEX - no-account multi-market charts')
    p.add_argument('--no-browser', action='store_true', help='Do not open a browser automatically')
    p.add_argument('--port', type=int, default=0, help='Local listen port (0 = find an available port)')
    p.add_argument('--ready-file', type=Path, default=None, help='Write a localhost URL for suite relaunches')
    args = p.parse_args(argv)
    with LocalServer(('127.0.0.1',args.port), Handler) as srv:
        url = f'http://127.0.0.1:{srv.server_port}/'
        if args.ready_file is not None:
            # The suite can re-open this browser window after its own restart.
            # Never publish a remote address or a token in this file.
            ready = args.ready_file
            ready.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            tmp = ready.with_name(ready.name + '.' + str(os.getpid()) + '.tmp')
            try:
                fd = os.open(tmp, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
                with os.fdopen(fd, 'w', encoding='utf-8') as out:
                    json.dump({'url':url, 'pid':os.getpid()}, out)
                os.replace(tmp, ready)
            finally:
                tmp.unlink(missing_ok=True)
        print('AUGURSPEX READY: '+url, flush=True)
        print('No login/API keys. Independent crypto feeds: Kraken + Coinbase. Cached stock EOD: Stooq/Naver; widgets: TradingView.', flush=True)
        if not args.no_browser: open_dashboard_window(url)
        try: srv.serve_forever(poll_interval=.2)
        except KeyboardInterrupt: pass
        finally:
            # Do not delete a newer server's rendezvous file.
            if args.ready_file is not None:
                try:
                    current = json.loads(args.ready_file.read_text(encoding='utf-8'))
                    if current.get('url') == url and current.get('pid') == os.getpid():
                        args.ready_file.unlink(missing_ok=True)
                except (OSError, ValueError, TypeError):
                    pass
    return 0

if __name__ == '__main__':
    sys.exit(main())
