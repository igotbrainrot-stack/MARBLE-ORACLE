"""0.4.9.3: chart axis text never overlaps or leaves the chart, at any size.

    xvfb-run -a python3 Application/Tests/test_augurspex_axis_labels_0493.py

Draws real PriceChart widgets with synthetic fixtures (never shown as market
data) and measures the text Tk actually rendered. The 0.4.9.2 build drew
"OCT '26" over "NOV '26" on charts around 500 px wide, labelled sub-cent
prices 0.0000, and had no guard for six- and seven-figure prices.
"""
from __future__ import annotations

import itertools
import sys
import tkinter as tk
from datetime import datetime, timedelta, timezone
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / 'Runtime' / 'Marble_Oracle_App'
sys.path.insert(0, str(APP))
from oracle_augurspex_tab import PriceChart, palette  # noqa: E402

FAILURES = []
CHECKS = [0]


def check(name, ok, detail=''):
    CHECKS[0] += 1
    if not ok:
        FAILURES.append(name)
        print(f'FAIL {name} — {detail}')


def history(count, start_price, step, days_per_bar=1, end=None):
    """Synthetic OHLC ending yesterday. TEST FIXTURE, not market data."""
    end = end or (datetime.now(timezone.utc) - timedelta(days=1))
    bars = []
    for i in range(count):
        base = start_price + step * i
        moment = end - timedelta(days=(count - 1 - i) * days_per_bar)
        bars.append({'time': moment.strftime('%Y-%m-%dT00:00:00+00:00'), 'open': base, 'high': base * 1.012,
                     'low': base * 0.99, 'close': base * 1.004, 'volume': 10})
    return {'source': 'TEST FIXTURE, NOT LIVE', 'currency': 'USD', 'candles': bars,
            'latest_observation': bars[-1]['time']}


def text_boxes(canvas):
    boxes = []
    for item in canvas.find_all():
        if canvas.type(item) == 'text' and canvas.itemcget(item, 'text').strip():
            box = canvas.bbox(item)
            if box:
                boxes.append((box, canvas.itemcget(item, 'text'), canvas.gettags(item)))
    return boxes


def problems(canvas):
    boxes = text_boxes(canvas)
    w, h = canvas.winfo_width(), canvas.winfo_height()
    overlaps = [(a[1], b[1]) for a, b in itertools.combinations(boxes, 2)
                if a[0][0] < b[0][2] and b[0][0] < a[0][2] and a[0][1] < b[0][3] and b[0][1] < a[0][3]]
    clipped = [text for (x0, y0, x1, y1), text, _tags in boxes if x0 < 0 or y0 < 0 or x1 > w or y1 > h]
    return overlaps, clipped


FIXTURES = {
    'four months of daily bars (month labels)': history(124, 100, 0.4),
    'three weeks of daily bars (day labels)': history(21, 42, 0.3),
    'six years of monthly bars (year labels)': history(72, 300, 4, days_per_bar=30),
    'two bars': history(2, 10, 1),
    'one bar': history(1, 10, 1),
    'seven-figure prices': history(90, 1_234_567, 950),
    'six-figure prices': history(90, 104_283, 120),
    'sub-cent prices': history(90, 0.0000123, 0.00000004),
    'fractional prices': history(90, 0.1432, 0.0006),
}
SIZES = ((300, 230), (380, 250), (470, 260), (508, 300), (560, 330), (760, 420), (1046, 496), (1500, 640))


def main():
    root = tk.Tk()
    root.geometry('1600x760+0+0')
    colours = palette()
    holder = tk.Frame(root)
    holder.place(x=0, y=0, width=600, height=400)
    chart = PriceChart(holder, colours, 0, lambda _index: None)
    chart.pack(fill='both', expand=True)
    root.update()
    for (width, height), (name, data), style in itertools.product(SIZES, FIXTURES.items(), ('1', '2')):
        holder.place_configure(width=width, height=height)
        root.update()
        chart.display('TEST-USD', 'Synthetic fixture', data, None, False, style, True)
        root.update()
        label = f'{name} · {"candles" if style == "1" else "line"} · card {width}x{height}'
        overlaps, clipped = problems(chart.canvas)
        check(f'{label}: no overlapping axis text', not overlaps, overlaps[:3])
        check(f'{label}: no axis text outside the chart', not clipped, clipped[:3])
        dates = [text for _box, text, tags in text_boxes(chart.canvas) if 'date-label' in tags]
        prices = [text for _box, text, tags in text_boxes(chart.canvas) if 'price-label' in tags]
        check(f'{label}: the newest date is labelled', bool(dates), dates)
        check(f'{label}: price axis is labelled top and bottom', len(prices) >= 2, prices)
        check(f'{label}: price labels are not all the same', len(set(prices)) == len(prices), prices)
        if 'sub-cent' in name:
            check(f'{label}: sub-cent prices keep significant digits',
                  all(float(text) > 0 for text in prices), prices)
            check(f'{label}: header quote keeps significant digits', float(chart.price.cget('text')) > 0,
                  chart.price.cget('text'))
        if 'seven-figure' in name:
            check(f'{label}: seven-figure labels are complete', all(',' in text and len(text) >= 9 for text in prices), prices)
    # A chart with nothing to draw says why, in one centred line.
    chart.display('TEST-USD', 'Synthetic fixture', None, 'stooq: HTTP 429; provider rate limit reached', False, '2', True)
    root.update()
    texts = [text for _box, text, _tags in text_boxes(chart.canvas)]
    check('empty chart shows one status line', len(texts) == 1 and 'LIMITED' in texts[0], texts)
    check('empty chart lists the source that was tried', 'STOOQ LIMITED' in chart._info_text, chart._info_text)
    chart.display('TEST-USD', 'Synthetic fixture', None,
                  'strasmore: HTTP 401; provider rejected the credentials', False, '2', True)
    root.update()
    check('a rejected key is reported as such, and names Strasmore',
          'STRASMORE KEY/PLAN' in chart._info_text, chart._info_text)
    root.destroy()
    print(f'AUGURSPEX AXIS LABELS: {CHECKS[0] - len(FAILURES)}/{CHECKS[0]} checks passed')
    return 1 if FAILURES else 0


if __name__ == '__main__':
    sys.exit(main())
