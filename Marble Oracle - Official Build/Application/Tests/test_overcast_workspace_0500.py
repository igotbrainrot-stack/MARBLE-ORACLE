"""0.5.0: OVERCAST as the suite's seventh workspace.

Checks, under a real Tk display:
* the OVERCAST tab opens the panel inside the workspace box at the five supported sizes, with every
  sidebar page, the model status, Refresh and Cancel inside the panel (nothing cut off);
* opening it makes no network request;
* the ledger is created in the suite's state folder (news_oracle/);
* a feed refresh started in OVERCAST keeps running while HOME is shown, lands, and is reported in the suite's
  status line; switching back finds the same panel;
* Escape returns HOME; closing the suite while a refresh is pending stops cleanly;
* no Tk call is made from a worker thread ("main thread is not in main loop").
"""
import io
import os
import sys
import tempfile
import threading
import time
from contextlib import redirect_stderr
from pathlib import Path

HERE = Path(__file__).resolve().parent
APP = HERE.parent / 'Runtime' / 'Marble_Oracle_App'
sys.path.insert(0, str(APP))
STATE = tempfile.mkdtemp(prefix='mo-ovc-')
os.environ['MARBLE_ORACLE_STATE'] = STATE
os.environ['MARBLE_ORACLE_NO_WELCOME'] = '1'

results = []


def check(name, ok, detail=''):
    results.append(ok)
    print(('PASS ' if ok else 'FAIL ') + name + ('' if ok else f'  {detail}'))


if not (os.environ.get('DISPLAY') or os.name == 'nt'):
    print('SKIP no display')
    sys.exit(0)

import urllib.request  # noqa: E402

calls = []


def no_network(*args, **kwargs):
    calls.append(args[:1])
    raise OSError('network disabled in this test')


urllib.request.urlopen = no_network

from marble_oracle import launch_plan, WindowApp  # noqa: E402
import overcast.engine as engine_mod  # noqa: E402

stderr = io.StringIO()
with redirect_stderr(stderr):
    app = WindowApp(launch_plan(['--selftest', '--no-network'])[1])
    root, scene = app.root, app.scene

    def pump(n=8):
        for _ in range(n):
            root.update()
            if scene.W == 0 or getattr(scene, 'need_build', False):
                scene.resized(*app.canvas_size())
            scene.tick()
            time.sleep(0.01)

    def inside(widget, panel):
        x = widget.winfo_rootx() - panel.winfo_rootx()
        y = widget.winfo_rooty() - panel.winfo_rooty()
        return (widget.winfo_ismapped() and x >= 0 and y >= 0 and x + widget.winfo_width() <= panel.winfo_width() + 1
                and y + widget.winfo_height() <= panel.winfo_height() + 1)

    for size in ('900x580', '1000x650', '1216x848', '1280x720', '1920x1080'):
        w, h = map(int, size.split('x'))
        root.geometry(f'{w}x{h}+0+0'); root.update(); scene.resized(w, h)
        pump()
        scene.act('tab_overcast')
        pump(14)
        check(f'{size}: the OVERCAST tab opens OVERCAST', scene._which_overlay() == 'ovc')
        panel = scene.ovc.frame
        x0, y0, x1, y1 = scene.overlay_box()
        check(f'{size}: the panel fills the workspace box',
              abs(panel.winfo_width() - (x1 - x0)) <= 2 and abs(panel.winfo_height() - (y1 - y0)) <= 2,
              (panel.winfo_width(), panel.winfo_height(), scene.overlay_box()))
        navs = list(panel._nav_map.values())
        cut = [b.cget('text') for b in navs if not inside(b, panel)]
        check(f'{size}: all {len(navs)} sidebar pages are visible', not cut and len(navs) == 11, cut)
        check(f'{size}: the model status is visible', inside(panel.conn_label, panel))
        check(f'{size}: Refresh and Cancel are visible',
              inside(panel.cancel_button, panel) and panel.cancel_button.winfo_x() >= 0)
        tab = scene.nav_tabs.get('tab_overcast')
        check(f'{size}: the OVERCAST tab is drawn as the open one',
              tab is not None and scene.c.itemcget(tab[0], 'fill').lower() != scene.c.itemcget(
                  scene.nav_tabs['tab_home'][0], 'fill').lower())
        scene.act('tab_home')
        pump()
        check(f'{size}: HOME hides it', scene._which_overlay() is None
              and scene.c.itemcget(scene._ovc_cached.window, 'state') == 'hidden')

    check('opening OVERCAST made no network request', not calls, calls)
    ledger = Path(STATE) / 'news_oracle' / 'news_oracle.sqlite3'
    check('the ledger is in the suite state folder', ledger.is_file(), ledger)

    # A refresh that keeps running while HOME is shown.
    release = threading.Event()
    started = threading.Event()

    def slow_refresh(self):
        started.set()
        release.wait(20)
        return {'new': 0, 'total_fetched': 0, 'sources': []}

    engine_mod.NewsOracleEngine.refresh = slow_refresh
    scene.act('tab_overcast')
    pump()
    first_panel = scene.ovc.frame
    first_panel.refresh()
    started.wait(5)
    check('the refresh is running', first_panel._running)
    scene.act('tab_home')
    pump()
    release.set()
    deadline = time.time() + 5
    while first_panel._running and time.time() < deadline:
        pump(2)
    check('it finished while HOME was shown', not first_panel._running)
    check('the suite status line reported it', 'OVERCAST' in (scene.msg or ''), scene.msg)
    scene.act('tab_overcast')
    pump()
    check('switching back finds the same panel', scene.ovc.frame is first_panel)

    # Escape returns HOME.
    class Key:
        keysym, char = 'Escape', ''
    scene.on_key(Key)
    pump()
    check('Escape returns HOME', scene._which_overlay() is None)

    # Larger type than this machine's (another font or DPI, as on CI): the sidebar compacts until every page fits.
    import tkinter as tk
    import overcast.theme as theme_mod
    from overcast.ui import NewsOraclePanel
    plain_f = theme_mod.Theme.f
    theme_mod.Theme.f = lambda self, size=11, weight='normal': plain_f(self, size + 2, weight)
    try:
        top = tk.Toplevel(root)
        top.geometry('1038x680+0+0')
        big = NewsOraclePanel(top, state_dir=tempfile.mkdtemp())
        big.pack(fill='both', expand=True)
        pump(14)
        cut = [b.cget('text') for b in big._nav_map.values() if not inside(b, big)]
        check('with larger type (+2 pt) every sidebar page still fits at 1038x680', not cut, cut)
        big.destroy()
        top.destroy()
    finally:
        theme_mod.Theme.f = plain_f

    # Closing the suite while a refresh is pending.
    release.clear()
    started.clear()
    scene.act('tab_overcast')
    pump()
    scene.ovc.frame.refresh()
    started.wait(5)
    try:
        app.quit()
        closed = True
    except SystemExit:
        closed = True
    except Exception as exc:
        closed = exc
    release.set()
    check('the suite closes while a refresh is pending', closed is True, closed)

warnings = stderr.getvalue()
check('no Tk call from a worker thread', 'main thread is not in main loop' not in warnings, warnings[-400:])
print(f'OVERCAST WORKSPACE 0.5.0: {sum(results)}/{len(results)} checks passed')
sys.exit(0 if all(results) else 1)
