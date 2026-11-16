"""0.4.9.6 design prototype: the promises the new tokens and behaviour make.

    xvfb-run -a python3 Application/Tests/test_design_tokens_0496.py

* every text colour meets WCAG AA (4.5:1) on every surface it is allowed on;
* control edges meet the 3:1 non-text minimum against what surrounds them;
* the focus colour is not the accent, so focus never looks like 'current';
* Escape on HOME does not quit the suite;
* a workspace covers the GRADE footer (GRADE acts only on HOME);
* four charts form a 2x2 grid in the default window's chart area;
* month and year axis labels sit on calendar boundaries at a steady step.
"""
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'Runtime' / 'Marble_Oracle_App'))
from oggcultist_design_system import COLOR as C  # noqa: E402
import oracle_augurspex_logic as logic  # noqa: E402

failures = []
checks = 0


def check(name, ok, detail=''):
    global checks
    checks += 1
    if not ok:
        failures.append(name)
        print('FAIL', name, detail)


def luminance(colour):
    rgb = [int(colour[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    rgb = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in rgb]
    return 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]


def ratio(a, b):
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


SURFACES = ('canvas', 'raised', 'sunken', 'sidebar', 'control', 'hover')
for text in ('text', 'text_2', 'text_3', 'text_bright', 'accent', 'danger_text', 'failed', 'done', 'rise', 'fall'):
    for surface in SURFACES:
        r = ratio(C[text], C[surface])
        check(f'{text} on {surface} >= 4.5:1', r >= 4.5, round(r, 2))
for text in ('text', 'text_bright', 'accent'):           # the only text allowed on the selected fill
    check(f'{text} on accent_soft >= 4.5:1', ratio(C[text], C['accent_soft']) >= 4.5)
check('text_on_accent on accent >= 4.5:1', ratio(C['text_on_accent'], C['accent']) >= 4.5)
for surface in ('canvas', 'raised', 'sidebar', 'sunken', 'control'):
    check(f'control_line against {surface} >= 3:1', ratio(C['control_line'], C[surface]) >= 3.0,
          round(ratio(C['control_line'], C[surface]), 2))
    check(f'focus ring against {surface} >= 3:1', ratio(C['focus'], C[surface]) >= 3.0)
check('focus is not the accent colour', C['focus'].upper() != C['accent'].upper(), C['focus'])

plan = logic.chart_grid_plan(4, 840, 560)
check('four charts: 2x2 without scrolling in an 840x560 chart area', (plan['cols'], plan['rows'], plan['scroll']) == (2, 2, False), plan)

# Month axes: labels on the first bar of a month, the same number of months apart,
# newest month kept. 0.4.9.5 picked evenly spaced bars, so a narrow card read
# JUN '26  AUG '26  SEP '26  NOV '26.
from datetime import datetime, timedelta, timezone  # noqa: E402

MONTHS = {m: i for i, m in enumerate('JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC'.split())}


def daily(start, n, step=1):
    return [{'time': (start + timedelta(days=i * step)).isoformat(), 'open': 1, 'high': 2, 'low': 0.5, 'close': 1.5}
            for i in range(n)]


for start, n in ((datetime(2026, 5, 20, tzinfo=timezone.utc), 180), (datetime(2025, 6, 1, tzinfo=timezone.utc), 160),
                 (datetime(2025, 11, 3, tzinfo=timezone.utc), 365)):
    bars = daily(start, n)
    for width, glyph in ((220, 9), (300, 9), (380, 9), (470, 11), (560, 9), (560, 13), (700, 11), (1046, 11)):
        # What the card draws: labels that fit the axis font, none dropped mid-run.
        placed = logic.axis_date_labels(bars, width, lambda text, g=glyph: len(text) * g)
        labels = [label for _x, label, _anchor in placed]
        index = [MONTHS[label[:3]] + 12 * int(label[-2:]) for label in labels]
        gaps = {b - a for a, b in zip(index, index[1:])}
        newest = bars[-1]['time'][:7]
        # Below the 380 px minimum card two month labels may not fit; then only the newest shows.
        check(f'month axis {start:%b %Y}+{n}d at {width}px/{glyph}: steady step',
              len(gaps) <= 1 and len(labels) >= (2 if width >= 380 else 1), labels)
        check(f'month axis {start:%b %Y}+{n}d at {width}px/{glyph}: newest month kept',
              index[-1] == int(newest[5:7]) - 1 + 12 * int(newest[2:4]), labels)
years = [label for _x, label in logic.chart_date_ticks(daily(datetime(2018, 3, 1, tzinfo=timezone.utc), 300, 10), 700)]
check('year axis: steady step', len({int(b) - int(a) for a, b in zip(years, years[1:])}) == 1, years)

from marble_oracle import WindowApp, launch_plan  # noqa: E402

_a, options, _c = launch_plan(['--selftest', '--no-network'])
app = WindowApp(options)
root, scene = app.root, app.scene
root.geometry('1216x848+0+0')
root.update()
scene.resized(1216, 848)


def pump(seconds=0.5):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        root.update()
        time.sleep(0.02)


pump()
quit_called = []
original_quit = app.quit
app.quit = lambda *a, **k: quit_called.append(True)
scene.on_key(type('E', (), {'keysym': 'Escape', 'char': '\x1b'})())
pump(0.3)
check('Escape on HOME does not quit', not quit_called)
app.quit = original_quit

box = scene.overlay_box()
check('a workspace covers the GRADE footer', box[3] >= scene.rect['status'][3], (box, scene.rect['status']))
scene.act('tab_eidolith')
pump(0.8)
frame = scene.eido.frame
bottom = frame.winfo_rooty() + frame.winfo_height()
footer_top = app.canvas.winfo_rooty() + scene.rect['status'][1]
check('EIDOLITH reaches over the footer area', bottom > footer_top, (bottom, footer_top))
scene.act('tab_home')
pump(0.3)
app.quit()
print(f'DESIGN TOKENS 0.4.9.6: {checks - len(failures)}/{checks} checks passed')
sys.exit(1 if failures else 0)
