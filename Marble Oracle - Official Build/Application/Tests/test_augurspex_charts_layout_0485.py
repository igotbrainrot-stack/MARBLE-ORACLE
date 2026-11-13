"""0.4.8.5: CHARTS count, chart sizing and text fit, measured in the real Tk panel.

    xvfb-run -a python3 Application/Tests/test_augurspex_charts_layout_0485.py

Synthetic candles labelled TEST FIXTURE are served by a fake router; no
network is used and production code never fabricates data. Checks, for window
sizes 900x580, 1000x650 and 1400x870 and CHARTS 1/2/4/6/9, with data only in
saved slots 1/5/9 and then only in 4/8:

* CHARTS N always represents saved slots 1..N: each is a full chart when it
  has real history, otherwise a compact status tab (never silently dropped);
* the full charts are exactly the slots with data among 1..N;
* one chart is substantially larger than each of four, and fills the view;
* no text inside a chart overlaps other text or the canvas edge;
* status, footer, counter, badge and slot-tab text fit their widgets;
* controls stay inside the window; all nine saved slots survive CHARTS 1;
* SHOW ALL MARKETS shows N full cards; CHARTS persists across a restart.
"""
from __future__ import annotations

import itertools
import json
import sys
import tempfile
import time
import tkinter as tk
from tkinter import font as tkfont
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / 'Runtime' / 'Marble_Oracle_App'
sys.path.insert(0, str(APP))
import oracle_augurspex_tab as tab_module  # noqa: E402
from oracle_augurspex_tab import EmbeddedAugurspex  # noqa: E402

SYMS = ['BTC-USD', '4568.T', 'NVDA', 'COH.AX', '005930.KS', 'ETH-USD', 'RMD.AX', 'CSL.AX', '4519.T']
SIZES = ((900, 580), (1000, 650), (1400, 870))
COUNTS = (1, 2, 4, 6, 9)
RESULTS = []


def check(name, ok, detail=''):
    RESULTS.append((name, bool(ok)))
    if not ok:
        print(f'FAIL {name} — {detail}')


def candles(n=120):
    out, price = [], 100.0
    for i in range(n):
        o = price
        price = price * (1 + ((i * 37) % 11 - 5) / 400)
        out.append({'time': f'2026-{1 + i // 28:02d}-{1 + i % 28:02d}', 'open': o,
                    'high': max(o, price) * 1.01, 'low': min(o, price) * .99, 'close': price})
    return out


class TestRouter:
    """Deterministic fixture router. Success only for the given symbols."""
    def __init__(self, ok):
        self.ok = set(ok)

    def _routes(self, symbol, source, period='D'):
        return ['test-only']

    def fetch(self, symbol, period='D'):
        if symbol not in self.ok:
            raise ValueError('TEST: PROVIDER TIMEOUT')
        return {'source': 'TEST FIXTURE, NOT LIVE', 'currency': 'USD',
                'latest_observation': '2026-05-08', 'candles': candles()}


def pump(root, seconds):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        root.update()
        time.sleep(.02)


def pump_until(root, predicate, limit=8):
    end = time.monotonic() + limit
    while time.monotonic() < end:
        root.update()
        if predicate():
            return True
        time.sleep(.02)
    return False


def text_items(canvas):
    items = []
    for item in canvas.find_all():
        if canvas.type(item) == 'text' and canvas.itemcget(item, 'text').strip():
            box = canvas.bbox(item)
            if box:
                items.append((box, canvas.itemcget(item, 'text')))
    return items


def canvas_text_problems(canvas):
    boxes = text_items(canvas)
    w, h = canvas.winfo_width(), canvas.winfo_height()
    overlaps = [(a[1][:16], b[1][:16]) for a, b in itertools.combinations(boxes, 2)
                if a[0][0] < b[0][2] and b[0][0] < a[0][2] and a[0][1] < b[0][3] and b[0][1] < a[0][3]]
    clipped = [t[:16] for (x0, y0, x1, y1), t in boxes if x0 < 0 or y0 < 0 or x1 > w or y1 > h]
    return overlaps, clipped


def label_fits(label):
    """The label's current text fits its on-screen width (no Tk cropping)."""
    if not label.winfo_ismapped():
        return True
    text = label.cget('text')
    if not text or '\n' in text or int(label.cget('wraplength') or 0):
        return True
    font = tkfont.Font(font=label.cget('font'))
    return font.measure(text) <= label.winfo_width() - 2 * int(label.cget('padx') or 0)


def inside(widget, root):
    x = widget.winfo_rootx() - root.winfo_rootx()
    y = widget.winfo_rooty() - root.winfo_rooty()
    return (widget.winfo_ismapped() and x >= 0 and y >= 0 and
            x + widget.winfo_width() <= root.winfo_width() + 1 and
            y + widget.winfo_height() <= root.winfo_height() + 1)


def open_panel(home, router, size, layout=9):
    w, h = size
    cfg = Path(home) / '.config' / 'augurspex'
    cfg.mkdir(parents=True, exist_ok=True)
    settings = cfg / 'settings.json'
    if not settings.exists():
        settings.write_text(json.dumps({'layout': layout, 'symbols': SYMS, 'style': '1', 'interval': 'D'}))
    root = tk.Tk()
    root.geometry(f'{w}x{h}+0+0')
    root.update()
    canvas = tk.Canvas(root, width=w, height=h, highlightthickness=0)
    canvas.pack(fill='both', expand=True)
    tab = EmbeddedAugurspex(canvas, lambda: None, home=home, router=router)
    tab.layout((0, 0, w, h))
    return root, tab, tab.frame


def mapped_cards(panel):
    return [i for i, card in enumerate(panel.cards) if card.winfo_ismapped()]


def chip_slots(panel):
    return sorted(getattr(panel, 'chip_slots', lambda: [])())


def plan_tests():
    plan = getattr(tab_module, 'chart_grid_plan', None)
    check('plan: chart_grid_plan exists (pure layout function)', plan is not None)
    if plan is None:
        return
    one = plan(1, 1078, 600)
    four = plan(4, 1078, 600)
    check('plan: one chart fills the viewport', one['cols'] == 1 and one['card_h'] >= 560 and not one['scroll'], one)
    check('plan: one chart is far larger than each of four',
          one['card_w'] * one['card_h'] > 2.5 * four['card_w'] * four['card_h'], (one, four))
    check('plan: four charts use a 2x2 grid when wide enough', (four['cols'], four['rows']) == (2, 2), four)
    nine = plan(9, 1078, 600)
    check('plan: nine charts keep a legible minimum and scroll', nine['scroll']
          and nine['card_h'] >= tab_module.MIN_CARD_H and nine['card_w'] >= tab_module.MIN_CARD_W, nine)
    small = plan(1, 560, 300)
    check('plan: one chart in a small view does not scroll needlessly', not small['scroll'], small)
    check('plan: zero charts is safe', plan(0, 500, 300)['rows'] == 0)


def gui_tests():
    for ok_slots in ((0, 4, 8), (3, 7)):
        ok = {SYMS[i] for i in ok_slots}
        for size in SIZES:
            with tempfile.TemporaryDirectory() as home:
                root, tab, p = open_panel(home, TestRouter(ok), size)
                ready = pump_until(root, lambda: all(p._market_verified(SYMS[i]) for i in ok_slots), 30)
                check(f'fixture data loaded for slots {[i + 1 for i in ok_slots]} at {size}', ready)
                pump(root, .4)
                label = f'data in slots {[i + 1 for i in ok_slots]} at {size[0]}x{size[1]}'
                areas = {}
                for n in COUNTS:
                    p.layout_var.set(str(n))
                    p._change_layout(str(n))
                    pump(root, .5)
                    shown, chips = mapped_cards(p), chip_slots(p)
                    want = [i for i in ok_slots if i < n]
                    check(f'{label} CHARTS={n}: full charts are the slots with data', shown == want, (shown, want))
                    check(f'{label} CHARTS={n}: every slot 1..{n} is a chart or a status tab',
                          sorted(shown + chips) == list(range(n)), (shown, chips))
                    for i in shown:
                        over, clip = canvas_text_problems(p.cards[i].canvas)
                        check(f'{label} CHARTS={n} slot {i + 1}: no overlapping chart text', not over, over[:3])
                        check(f'{label} CHARTS={n} slot {i + 1}: no chart text past the edge', not clip, clip[:3])
                    if shown:
                        card = p.cards[shown[0]]
                        areas[n] = card.canvas.winfo_width() * card.canvas.winfo_height()
                    for widget in (p.status_label, p.source_count, getattr(p, 'footer_note', None),
                                   getattr(p, 'count_badge', None)):
                        if widget is not None:
                            check(f'{label} CHARTS={n}: "{widget.cget("text")[:24]}" fits its label',
                                  label_fits(widget), (widget.cget('text'), widget.winfo_width()))
                    for chip in getattr(p, 'chip_widgets', []):
                        check(f'{label} CHARTS={n}: slot tab "{chip.cget("text")[:20]}" fits', label_fits(chip))
                    badge = getattr(p, 'count_badge', None)
                    check(f'{label} CHARTS={n}: badge states requested and with-data counts', badge is not None
                          and f'{n} REQUESTED' in badge.cget('text') and f'{len(want)} WITH DATA' in badge.cget('text'),
                          badge.cget('text') if badge is not None else 'no badge')
                    for name in ('BACK TO HOME', 'SOURCE DETAILS', 'REFRESH'):
                        button = next((w for w in iter_widgets(p) if isinstance(w, tk.Button)
                                       and w.cget('text') == name), None)
                        check(f'{label} CHARTS={n}: {name} visible inside the window',
                              button is not None and inside(button, root))
                if 1 in areas:
                    view = p.chart_canvas.winfo_width() * p.chart_canvas.winfo_height()
                    check(f'{label}: a single chart uses most of the chart area', areas[1] > .55 * view,
                          (areas[1], view))
                if ok_slots == (3, 7):
                    p._change_layout('1')
                    pump(root, .4)
                    text = p.count_badge.cget('text') if hasattr(p, 'count_badge') else ''
                    check(f'{label}: CHARTS=1 with data only in later slots says where data is',
                          'SLOT 4' in text.upper() or 'SLOTS 4' in text.upper(), text)
                saved = json.loads((Path(home) / '.config' / 'augurspex' / 'settings.json').read_text())
                check(f'{label}: all nine saved slots survive CHARTS changes',
                      saved.get('symbols', [])[:9] == SYMS, saved.get('symbols'))
                p._toggle_sourced()
                p._change_layout('4')
                pump(root, .5)
                check(f'{label}: SHOW ALL MARKETS shows four full cards for CHARTS=4',
                      mapped_cards(p) == [0, 1, 2, 3], mapped_cards(p))
                four = max(p.cards[i].canvas.winfo_width() * p.cards[i].canvas.winfo_height() for i in range(4))
                scrolls = p.grid_frame.winfo_height() > p.chart_canvas.winfo_height()
                p._change_layout('1')
                pump(root, .5)
                one = p.cards[0].canvas.winfo_width() * p.cards[0].canvas.winfo_height()
                # Handover acceptance: clearly larger at 1400x870. In smaller
                # windows the chart area is only ~300-370 px tall: one chart
                # fills it and four sit at the legible minimum and scroll.
                if size == (1400, 870):
                    check(f'{label}: one chart is much larger than each of four shown charts',
                          one > 1.8 * four, (one, four))
                else:
                    check(f'{label}: one chart is at least as large as each of four, four scroll',
                          one >= four and scrolls, (one, four, scrolls))
                tab.shutdown()
                root.destroy()


def iter_widgets(widget):
    yield widget
    for child in widget.winfo_children():
        yield from iter_widgets(child)


def restart_test():
    with tempfile.TemporaryDirectory() as home:
        router = TestRouter({SYMS[0], SYMS[1]})
        root, tab, p = open_panel(home, router, (1400, 870))
        pump_until(root, lambda: p._market_verified(SYMS[1]), 8)
        p.layout_var.set('2')
        p._change_layout('2')
        pump(root, .4)
        tab.shutdown()
        root.destroy()
        root, tab, p = open_panel(home, router, (1400, 870))
        pump_until(root, lambda: p._market_verified(SYMS[0]) and p._market_verified(SYMS[1]), 30)
        pump(root, .5)
        if mapped_cards(p) != [0, 1]:
            import traceback, threading as _th
            frames = sys._current_frames()
            for t in _th.enumerate():
                if 'augurspex' in t.name and t.ident in frames:
                    print('THREAD', t.name, ''.join(traceback.format_stack(frames[t.ident])[-4:]).replace('\n', ' | ')[:900])
        check('restart: CHARTS=2 restored with both charts shown', p.settings['layout'] == 2
              and mapped_cards(p) == [0, 1], (p.settings['layout'], mapped_cards(p), sorted(p._data),
                                              p._errors.get((SYMS[0], 'D')), p._pending,
                                              'queue', p._pool._work_queue.qsize(), 'threads',
                                              [t.is_alive() for t in p._pool._threads], 'results', p._results.qsize(),
                                              'visible', p._visible, 'after', p._after))
        tab.shutdown()
        root.destroy()


def drawn(panel, tag):
    return any(panel.cards[i].canvas.find_withtag(tag) for i in mapped_cards(panel))


def line_style_tests():
    router = TestRouter({SYMS[0]})
    # Fresh install: line graphs.
    with tempfile.TemporaryDirectory() as home:
        root = tk.Tk()
        root.geometry('1400x870+0+0')
        canvas = tk.Canvas(root, width=1400, height=870, highlightthickness=0)
        canvas.pack(fill='both', expand=True)
        tab = EmbeddedAugurspex(canvas, lambda: None, home=home, router=router)
        tab.layout((0, 0, 1400, 870))
        p = tab.frame
        pump_until(root, lambda: p._market_verified(SYMS[0]), 8)
        pump(root, .4)
        check('line: fresh install draws line graphs', p.settings['style'] == '2' and p.style_var.get() == 'LINE'
              and drawn(p, 'price-line') and not drawn(p, 'candle-body'), p.settings['style'])
        tab.shutdown()
        root.destroy()
    # Settings saved by 0.4.8.4 (candles were only the default) convert once.
    with tempfile.TemporaryDirectory() as home:
        cfg = Path(home) / '.config' / 'augurspex'
        cfg.mkdir(parents=True)
        (cfg / 'settings.json').write_text(json.dumps({
            'layout': 1, 'symbols': SYMS, 'style': '1', 'interval': 'D', 'workspace': 'Overview',
            'workspaces': {'Healthcare': {'layout': 4, 'interval': 'D', 'style': '1', 'symbols': SYMS}}}))
        root, tab, p = open_panel(home, router, (1400, 870))
        pump_until(root, lambda: p._market_verified(SYMS[0]), 8)
        pump(root, .4)
        saved = json.loads((cfg / 'settings.json').read_text()) if (cfg / 'settings.json').exists() else {}
        check('line: 0.4.8.4 candle settings convert to line graphs', p.settings['style'] == '2'
              and p.style_var.get() == 'LINE' and drawn(p, 'price-line') and not drawn(p, 'candle-body'))
        check('line: saved workspaces convert too',
              p.settings['workspaces'].get('Healthcare', {}).get('style') == '2', p.settings['workspaces'])
        # Choosing CANDLES afterwards is respected and remembered.
        p.style_var.set('CANDLES')
        p._change_style('CANDLES')
        pump(root, .3)
        check('line: CANDLES can still be chosen', drawn(p, 'candle-body'))
        tab.shutdown()
        root.destroy()
        root, tab, p = open_panel(home, router, (1400, 870))
        pump_until(root, lambda: p._market_verified(SYMS[0]), 8)
        pump(root, .4)
        saved = json.loads((cfg / 'settings.json').read_text())
        check('line: a CANDLES choice survives a restart', p.settings['style'] == '1' and p.style_var.get() == 'CANDLES'
              and drawn(p, 'candle-body') and saved.get('line_default_0485') is True, saved.get('style'))
        tab.shutdown()
        root.destroy()


if __name__ == '__main__':
    line_style_tests()
    plan_tests()
    gui_tests()
    restart_test()
    passed = sum(ok for _, ok in RESULTS)
    print(f'AUGURSPEX CHARTS COUNT / SIZE / TEXT FIT: {passed}/{len(RESULTS)} checks passed')
    if passed != len(RESULTS):
        raise SystemExit(1)
