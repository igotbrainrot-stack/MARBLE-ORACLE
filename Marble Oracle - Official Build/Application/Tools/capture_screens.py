#!/usr/bin/env python3
"""Save a screenshot of every workspace at the supported window sizes.

For reviewing layout by eye (overlaps, clipping, balance) on a real or
virtual display. Networking is off; AUGURSPEX is shown twice: as it opens
with no network, and again with clearly labelled synthetic fixture history so
the charts themselves can be inspected. Nothing here is market data.

    xvfb-run -a -s "-screen 0 1920x1080x24" python3 Application/Tools/capture_screens.py OUT_DIR
    python3 Application/Tools/capture_screens.py OUT_DIR --sizes 1280x720

User state is redirected to a temporary folder; real settings are not read
or written.
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / 'Runtime' / 'Marble_Oracle_App'
DEFAULT_SIZES = ('900x580', '1000x650', '1216x848', '1280x720', '1920x1080')   # 1216x848 is the default window
TABS = ('tab_home', 'tab_oggcultist', 'tab_eidolith', 'tab_augurspex', 'tab_passphrase', 'tab_touch_type')


def isolate_state():
    state = Path(tempfile.mkdtemp(prefix='marble-oracle-shots-'))
    for name, sub in (('MARBLE_ORACLE_STATE', 'state'), ('HOME', ''), ('USERPROFILE', ''),
                      ('XDG_CONFIG_HOME', 'config'), ('XDG_CACHE_HOME', 'cache'), ('XDG_STATE_HOME', 'xdg-state'),
                      ('XDG_DATA_HOME', 'data'), ('LOCALAPPDATA', 'local'), ('APPDATA', 'roaming')):
        os.environ[name] = str(state / sub) if sub else str(state)
    for name in list(os.environ):
        if name.startswith('AUGURSPEX_'):
            del os.environ[name]
    return state


def grab(root, target):
    from PIL import ImageGrab
    root.update_idletasks()
    x, y = root.winfo_rootx(), root.winfo_rooty()
    ImageGrab.grab(bbox=(x, y, x + root.winfo_width(), y + root.winfo_height())).save(str(target))


def pump(root, seconds):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        root.update()
        time.sleep(0.02)


class FixtureRouter:
    """Synthetic history for layout review only; every source is labelled as a fixture."""

    def _routes(self, symbol, source, period='D'):
        return ['test-only']

    def fetch(self, symbol, period='D'):
        if symbol.startswith('FX:GBP'):
            raise ValueError('frankfurter-history: HTTP 429; provider rate limit reached | ecb-fx: Network problem: timed out')
        seed = sum(map(ord, symbol))
        base = {'BTC-USD': 104000.0, 'ETH-USD': 3900.0, 'DOGE-USD': 0.21}.get(symbol, 40 + seed % 400)
        end = datetime.now(timezone.utc) - timedelta(days=1)
        bars, price = [], base
        for i in range(160):
            opened = price
            price = price * (1 + (((i * (7 + seed % 5)) % 13) - 6) / 420)
            close_only = symbol.startswith('FX:')
            high, low = (max(opened, price) * 1.006, min(opened, price) * 0.994)
            bar = {'time': (end - timedelta(days=159 - i)).strftime('%Y-%m-%dT00:00:00+00:00'),
                   'open': price if close_only else opened, 'high': price if close_only else high,
                   'low': price if close_only else low, 'close': price, 'volume': 0}
            if close_only:
                bar['close_only'] = True
            bars.append(bar)
        return {'source': 'TEST FIXTURE, NOT LIVE', 'currency': 'USD', 'candles': bars,
                'latest_observation': bars[-1]['time'], 'cache': 'network'}


def capture_suite(size, out, extra=(), prefix=''):
    """The window exactly as a launch opens it (launch_plan), driven tab by tab."""
    from marble_oracle import WindowApp, launch_plan
    width, height = (int(v) for v in size.split('x'))
    _args, options, _cls = launch_plan(['--selftest', '--no-network', *extra])
    app = WindowApp(options)
    root, scene = app.root, app.scene
    if not extra:               # the photographic CRT chooses its own fixed sizes
        root.geometry(f'{width}x{height}+0+0')
        root.update()
        scene.resized(width, height)
    pump(root, 1.0)
    for tab in TABS:
        scene.act(tab)
        pump(root, 1.6)
        grab(root, out / f'{prefix}{size}_{TABS.index(tab) + 1}_{tab[4:]}.png')
    scene.act('tab_home')
    pump(root, 0.3)
    app.quit()


def capture_augurspex_fixture(size, out, home):
    import tkinter as tk
    from oracle_augurspex_tab import EmbeddedAugurspex
    width, height = (int(v) for v in size.split('x'))
    root = tk.Tk()
    root.geometry(f'{width}x{height}+0+0')
    canvas = tk.Canvas(root, width=width, height=height, highlightthickness=0, bg='#000000')
    canvas.pack(fill='both', expand=True)
    root.update()
    tab = EmbeddedAugurspex(canvas, lambda: None, home=str(home), router=FixtureRouter())
    tab.layout((0, 0, width, height))
    panel = tab.frame
    for count in ('1', '4', '9'):
        panel.layout_var.set(count)
        panel._change_layout(count)
        pump(root, 3.0)
        grab(root, out / f'{size}_7_augurspex_fixture_{count}_charts.png')
    panel.style_var.set('CANDLES')
    panel._change_style('CANDLES')
    panel.layout_var.set('2')
    panel._change_layout('2')
    pump(root, 1.5)
    grab(root, out / f'{size}_7_augurspex_fixture_2_candles.png')
    tab.shutdown()
    root.destroy()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('out', help='folder for the PNG files')
    parser.add_argument('--sizes', nargs='*', default=list(DEFAULT_SIZES))
    args = parser.parse_args(argv)
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    state = isolate_state()
    sys.path.insert(0, str(APP))
    failures = 0
    try:
        for size in args.sizes:
            for label, job in (('suite', lambda: capture_suite(size, out)),
                               ('augurspex fixture', lambda: capture_augurspex_fixture(size, out, state / 'fixture-home'))):
                try:
                    job()
                    print(f'captured {label} at {size}', flush=True)
                except Exception as exc:  # keep going: one size failing must not hide the others
                    failures += 1
                    import traceback
                    print(f'FAILED {label} at {size}: {exc}', flush=True)
                    traceback.print_exc()
        try:        # the optional photographic CRT housing, at the size it picks for this display
            capture_suite('auto', out, extra=('--crt-v2',), prefix='crt_')
            print('captured CRT housing', flush=True)
        except Exception as exc:
            failures += 1
            print(f'FAILED CRT housing: {exc}', flush=True)
    finally:
        shutil.rmtree(state, ignore_errors=True)
    print(f'{len(list(out.glob("*.png")))} screenshots in {out}')
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
