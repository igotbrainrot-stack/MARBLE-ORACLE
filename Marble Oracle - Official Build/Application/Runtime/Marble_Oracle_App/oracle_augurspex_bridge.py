"""Launch/reopen the bundled AUGURSPEX companion without creating duplicate servers.

Uses only the local loopback interface and the user's private cache folder.
The suite does not collect passwords, API keys or account information.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

_process: subprocess.Popen | None = None
_URL_PATTERN = re.compile(r'^http://127\.0\.0\.1:(\d{1,5})/$')


def _ready_file() -> Path:
    cache_root = os.environ.get('XDG_CACHE_HOME') if os.name != 'nt' else None
    return Path(cache_root or (Path.home() / '.cache')) / 'augurspex' / 'marble_oracle_bridge.json'


def _read_active_url(path: Path) -> str | None:
    try:
        obj = json.loads(path.read_text(encoding='utf-8'))
        url = obj['url']
        if not isinstance(url, str):
            return None
        match = _URL_PATTERN.fullmatch(url)
        if not match or not 1 <= int(match.group(1)) <= 65535:
            return None
        # A listening arbitrary service is not sufficient. Verify the app endpoint.
        # Always connect directly to the loopback service, never via proxy env vars.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(url + 'api/providers', timeout=.45) as response:
            payload = json.load(response)
            if response.status == 200 and payload.get('key_free') is True and payload.get('no_login') is True:
                return url
    except (OSError, ValueError, TypeError, KeyError, TimeoutError, json.JSONDecodeError):
        pass
    return None


def launch() -> bool:
    """Return True if a new instance starts; False if an existing window is reopened."""
    global _process
    runner = Path(__file__).resolve().parent / 'Augurspex' / 'run.py'
    if not runner.is_file():
        raise FileNotFoundError('Bundled AUGURSPEX runner is missing')
    ready = _ready_file()
    running = _read_active_url(ready)
    if running:
        if not webbrowser.open(running, new=1):
            raise RuntimeError('AUGURSPEX is running, but no browser could be opened')
        return False
    # Do not launch a duplicate while an earlier child is still starting.
    if _process is not None and _process.poll() is None:
        raise RuntimeError('AUGURSPEX is still starting; try again in a moment')
    ready.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    ready.unlink(missing_ok=True)  # stale status left by a crash
    _process = subprocess.Popen(
        [sys.executable, str(runner), '--ready-file', str(ready)],
        cwd=str(runner.parent), stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True, close_fds=True,
    )
    deadline = time.monotonic() + 4.0
    while time.monotonic() < deadline:
        if _process.poll() is not None:
            raise RuntimeError(f'AUGURSPEX exited on startup (code {_process.returncode}); run Augurspex/run.py for diagnostics')
        if _read_active_url(ready):
            return True
        time.sleep(.08)
    raise RuntimeError('AUGURSPEX did not become ready; run Augurspex/run.py for diagnostics')
