#!/usr/bin/env python3
"""Run every Marble Oracle regression script and print an honest summary.

Each test script runs in its own process with a throw-away state folder, so a
test can never touch real preferences, watchlists or queues. A script that
cannot start because Tk (or an optional library) is missing is reported as
SKIPPED with the reason; it is never counted as a pass.

Usage (from the release root or anywhere):
    python3 Application/Tools/run_tests.py            # everything
    python3 Application/Tools/run_tests.py augurspex  # only names containing "augurspex"
    python3 Application/Tools/run_tests.py --json results.json

On headless Linux, start it under a virtual display:
    xvfb-run -a python3 Application/Tools/run_tests.py
Exit status is 0 only when nothing failed.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

APPLICATION = Path(__file__).resolve().parents[1]
ROOT = APPLICATION.parent
TEST_DIRS = (APPLICATION / 'Tests', APPLICATION / 'Runtime' / 'Marble_Oracle_App')
SKIP_MARKERS = (
    ("No module named 'tkinter'", 'Tk is not installed for this Python'),
    ("No module named '_tkinter'", 'Tk is not installed for this Python'),
    ('no display name and no $DISPLAY', 'no graphical display (use xvfb-run on Linux)'),
    ("couldn't connect to display", 'no graphical display (use xvfb-run on Linux)'),
    ("No module named 'mutagen'", 'optional library mutagen is not installed'),
    ("No module named 'PIL'", 'Pillow is not installed'),
)


def discover(filters):
    found = []
    for folder in TEST_DIRS:
        found.extend(sorted(folder.glob('test_*.py')))
    if filters:
        found = [p for p in found if any(f.lower() in p.name.lower() for f in filters)]
    return found


# Runs a test script exactly as `python script.py` would, but shortly before the
# time limit prints where every thread is, so a hang names its own line.
HANG_REPORTER = (
    "import faulthandler, os, runpy, sys\n"
    "script = sys.argv[1]\n"
    "faulthandler.dump_traceback_later(float(sys.argv[2]), exit=False)\n"
    "sys.argv = [script]\n"
    "sys.path[0] = os.path.dirname(script)\n"
    "runpy.run_path(script, run_name='__main__')\n"
)


def run_one(path: Path, timeout: float, tail_lines: int = 12):
    state = Path(tempfile.mkdtemp(prefix='marble-oracle-test-'))
    env = dict(os.environ)
    env.update({
        'MARBLE_ORACLE_STATE': str(state / 'state'),
        'HOME': str(state), 'USERPROFILE': str(state),
        'XDG_CONFIG_HOME': str(state / 'config'), 'XDG_CACHE_HOME': str(state / 'cache'),
        'XDG_STATE_HOME': str(state / 'xdg-state'), 'XDG_DATA_HOME': str(state / 'data'),
        'LOCALAPPDATA': str(state / 'localappdata'), 'APPDATA': str(state / 'appdata'),
        'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONIOENCODING': 'utf-8', 'PYTHONUNBUFFERED': '1',
    })
    # Never let a developer's real API keys reach a test run.
    for name in list(env):
        if name.startswith('AUGURSPEX_'):
            del env[name]
    started = time.monotonic()
    try:
        done = subprocess.run([sys.executable, '-c', HANG_REPORTER, str(path), str(max(5.0, timeout - 10))],
                              cwd=str(ROOT), env=env, timeout=timeout,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors='replace')
        output, code = done.stdout, done.returncode
    except subprocess.TimeoutExpired as exc:
        output = exc.stdout if isinstance(exc.stdout, str) else (exc.stdout or b'').decode('utf-8', 'replace')
        code = None
    finally:
        shutil.rmtree(state, ignore_errors=True)
    seconds = time.monotonic() - started
    tail = [line for line in output.strip().splitlines() if line.strip()][-tail_lines:]
    if code == 0:
        status, reason = 'PASS', ''
    elif code is None:
        status, reason = 'FAIL', f'timed out after {timeout:.0f}s'
    else:
        status, reason = 'FAIL', f'exit code {code}'
        for marker, why in SKIP_MARKERS:
            if marker in output:
                status, reason = 'SKIP', why
                break
    return {'test': path.name, 'status': status, 'reason': reason, 'seconds': round(seconds, 1), 'tail': tail}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('filters', nargs='*', help='only run tests whose file name contains one of these')
    parser.add_argument('--timeout', type=float, default=420, help='seconds allowed per test script')
    parser.add_argument('--json', dest='json_path', help='also write the results to this JSON file')
    parser.add_argument('--tail', type=int, default=12, help='output lines to keep for each failed test')
    parser.add_argument('--verbose', action='store_true', help='print the output tail of every test')
    args = parser.parse_args(argv)
    tests = discover(args.filters)
    if not tests:
        print('No tests matched.')
        return 2
    results = []
    for path in tests:
        result = run_one(path, args.timeout, max(1, args.tail))
        results.append(result)
        note = f' — {result["reason"]}' if result['reason'] else ''
        print(f'{result["status"]:4} {result["seconds"]:6.1f}s  {result["test"]}{note}', flush=True)
        if result['status'] == 'FAIL' or args.verbose:
            for line in result['tail']:
                print('        | ' + line[:220])
    counts = {key: sum(r['status'] == key for r in results) for key in ('PASS', 'FAIL', 'SKIP')}
    print(f'\n{len(results)} test scripts: {counts["PASS"]} passed, {counts["FAIL"]} failed, {counts["SKIP"]} skipped')
    if counts['SKIP']:
        reasons = sorted({r['reason'] for r in results if r['status'] == 'SKIP'})
        print('Skipped tests were NOT verified: ' + '; '.join(reasons))
    if args.json_path:
        Path(args.json_path).write_text(json.dumps({
            'python': sys.version.split()[0], 'platform': sys.platform, 'counts': counts, 'results': results,
        }, indent=2) + '\n', encoding='utf-8')
    return 1 if counts['FAIL'] else 0


if __name__ == '__main__':
    sys.exit(main())
