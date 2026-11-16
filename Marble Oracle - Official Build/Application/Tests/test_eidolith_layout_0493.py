"""EIDOLITH at every supported window size: no control off the edge, no sentence cut short.

    xvfb-run -a python3 Application/Tests/test_eidolith_layout_0493.py

Before 0.4.9.3, at 900x580: QUEUE lost CLEAR FINISHED / CLEAR ALL / RETRY
SELECTED and the whole CONVERSION LOG off the edges, CONVERT cut its
explanations mid-sentence, and PLAYER lost the volume control.
"""
from pathlib import Path
import os
import sys
import tempfile
import time

os.environ.setdefault('MARBLE_ORACLE_STATE', tempfile.mkdtemp(prefix='eidolith-layout-state-'))
APP = Path(__file__).resolve().parents[1] / 'Runtime' / 'Marble_Oracle_App'
sys.path.insert(0, str(APP))

import tkinter as tk  # noqa: E402
from tkinter import ttk  # noqa: E402

from oracle_design import WrapSettler, flow_layout  # noqa: E402

SIZES = ((900, 580), (1000, 650), (1280, 720), (1920, 1080))
failures = []
checks = 0


def check(name, ok, detail=''):
    global checks
    checks += 1
    if not ok:
        failures.append(f'{name} {detail}')
        print('FAIL', name, detail, flush=True)


def pump(root, seconds):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        root.update()
        time.sleep(0.01)


def descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from descendants(child)


def box(widget):
    x, y = widget.winfo_rootx(), widget.winfo_rooty()
    return x, y, x + widget.winfo_width(), y + widget.winfo_height()


def inside(widget, container, slack=2):
    a, b = box(widget), box(container)
    return a[0] >= b[0] - slack and a[1] >= b[1] - slack and a[2] <= b[2] + slack and a[3] <= b[3] + slack


def inside_horizontally(widget, container, slack=2):
    a, b = box(widget), box(container)
    return a[0] >= b[0] - slack and a[2] <= b[2] + slack


def flow_rule():
    # The arithmetic behind every wrapping toolbar, without a display.
    positions, height = flow_layout([(100, 30)] * 3, 330, gap_x=10, gap_y=5)
    check('three items that fit share one row', positions == [(0, 0), (110, 0), (220, 0)] and height == 30, (positions, height))
    positions, height = flow_layout([(100, 30)] * 3, 250, gap_x=10, gap_y=5)
    check('the third wraps when the row is too narrow', positions == [(0, 0), (110, 0), (0, 35)] and height == 65, (positions, height))
    positions, height = flow_layout([(400, 30), (50, 20)], 250, gap_x=10, gap_y=5)
    check('an item wider than the row still gets a row', positions == [(0, 0), (0, 35)] and height == 55, (positions, height))
    check('nothing to lay out is zero height', flow_layout([], 300) == ([], 0))
    positions, _height = flow_layout([(100, 30), (100, 30)], 0)
    check('a container not yet measured never divides by zero or drops items', len(positions) == 2)


def wrap_rule():
    # 0.4.9.3: on Windows the CONVERT page froze the window. A wrapped label
    # changed its container's width, which changed the wrap, for ever.
    settler = WrapSettler()
    check('a first width is applied', settler.next(300) == 300)
    check('the same width again changes nothing', settler.next(300) is None)
    check('a new width is applied', settler.next(280) == 280)
    check('bouncing back to an earlier width is refused', settler.next(300) is None)
    check('and the text stays on the narrower width however often it bounces',
          [settler.next(w) for w in (280, 300, 280, 300)] == [None, None, None, None])
    check('a genuinely new width (the window was resized) is applied again', settler.next(520) == 520)

    settler = WrapSettler()
    applied = [settler.next(w) for w in (400, 360, 380, 400)]
    check('a three-width cycle settles on its narrowest width', applied == [400, 360, 380, 360], applied)
    check('and then ignores every width of that cycle',
          [settler.next(w) for w in (360, 380, 400, 360)] == [None, None, None, None])

    # Any feedback rule at all must stop changing within a few steps.
    for container_for in (lambda wrap: 300 if wrap == 280 else 280,          # two widths that cause each other
                          lambda wrap: {250: 270, 270: 290, 290: 250}.get(wrap, 250),
                          lambda wrap: wrap - 7 if wrap > 130 else wrap):   # keeps shrinking, then stops
        settler, width, changes = WrapSettler(), 300, 0
        for _step in range(200):
            wrap = settler.next(width)
            if wrap is None:
                break
            changes += 1
            width = container_for(wrap)
        check('the wrap width stops changing', changes < 60, changes)


def gui():
    from marble_oracle import WindowApp, launch_plan
    _args, options, _cls = launch_plan(['--selftest', '--no-network'])
    app = WindowApp(options)
    root, scene = app.root, app.scene
    try:
        for width, height in SIZES:
            label = f'{width}x{height}'
            root.geometry(f'{width}x{height}+0+0')
            root.update()
            scene.resized(width, height)
            pump(root, 0.5)
            scene.act('tab_eidolith')
            pump(root, 0.8)
            frame = scene.eido.frame
            check(f'{label}: EIDOLITH opened inside the window', frame.winfo_ismapped() and frame.winfo_width() <= width)
            for page_name in ('PLAYER', 'CONVERT', 'QUEUE', 'ABOUT'):
                frame._set_nav(page_name)
                pump(root, 0.6)
                page = frame.pages[page_name]
                scroller = frame._convert_canvas
                for widget in descendants(page):
                    if not widget.winfo_ismapped() or not isinstance(widget, (tk.Button, tk.Scale, tk.OptionMenu, tk.Entry)):
                        continue
                    name = str(widget.cget('text')) if isinstance(widget, tk.Button) else widget.winfo_class()
                    in_scroller = str(widget).startswith(str(scroller) + '.')
                    if in_scroller:      # this column scrolls vertically; it must never be cut sideways
                        check(f'{label} {page_name}: "{name}" not cut off sideways', inside_horizontally(widget, scroller),
                              (box(widget), box(scroller)))
                    else:
                        check(f'{label} {page_name}: "{name}" fully inside the page', inside(widget, page),
                              (box(widget), box(page)))
                if page_name == 'CONVERT':
                    for widget in descendants(scroller):
                        if widget.winfo_ismapped() and isinstance(widget, (ttk.Label, tk.Label, tk.Checkbutton)) and widget.cget('text'):
                            check(f'{label} CONVERT: "{str(widget.cget("text"))[:34]}" is not cut short',
                                  widget.winfo_reqwidth() <= widget.master.winfo_width() + 2,
                                  (widget.winfo_reqwidth(), widget.master.winfo_width()))
                    # 0.4.9.6 design: the actions that start the work are in the
                    # page's title row, on screen without scrolling (they used to
                    # be the last controls of the scrolling form). Stricter than
                    # the old 'reachable by scrolling' check it replaces.
                    for wanted in ('QUEUE SELECTED', 'START QUEUE'):
                        button = next((w for w in descendants(frame.header_right) if isinstance(w, tk.Button)
                                       and w.cget('text') == wanted), None)
                        check(f'{label} CONVERT: {wanted} on screen without scrolling',
                              button is not None and button.winfo_ismapped() and inside(button, frame),
                              button is not None and (box(button), box(frame)))
                    output = next((w for w in descendants(scroller) if isinstance(w, tk.Button) and w.cget('text') == 'CHOOSE'), None)
                    check(f'{label} CONVERT: output folder CHOOSE visible without scrolling',
                          output is not None and inside(output, scroller), output is not None and (box(output), box(scroller)))
                if page_name != 'CONVERT':
                    check(f'{label} {page_name}: CONVERT actions hidden on other pages', not frame.convert_actions.winfo_ismapped())
                if page_name == 'QUEUE':
                    for wanted in ('START QUEUE', 'STOP QUEUE', 'CANCEL CURRENT', 'RETRY FAILED', 'CLEAR FINISHED', 'CLEAR ALL',
                                   'REMOVE SELECTED', 'OPEN LOG', 'COPY DIAGNOSTICS', 'LOG FOLDER', 'RETRY SELECTED'):
                        check(f'{label} QUEUE: {wanted} is on screen',
                              any(isinstance(w, tk.Button) and w.cget('text') == wanted and w.winfo_ismapped() and inside(w, page)
                                  for w in descendants(page)))
                    check(f'{label} QUEUE: the job list keeps at least two rows', frame.queue_list.winfo_height() >= 40
                          and inside(frame.queue_list, page), frame.queue_list.winfo_height())
                    check(f'{label} QUEUE: the conversion log is on screen', inside(frame.log_text, page)
                          and frame.log_text.winfo_height() >= 30, (box(frame.log_text), box(page)))
                if page_name == 'PLAYER':
                    check(f'{label} PLAYER: the volume control is on screen', inside(frame.video.volume_slider, page),
                          (box(frame.video.volume_slider), box(page)))
                    check(f'{label} PLAYER: the viewer keeps a usable picture area', frame.video.canvas.winfo_height() >= 100
                          and frame.video.canvas.winfo_width() >= 200,
                          (frame.video.canvas.winfo_width(), frame.video.canvas.winfo_height()))
                    check(f'{label} PLAYER: the media probe text is on screen', inside(frame.probe_text, page)
                          and frame.probe_text.winfo_height() >= 30, (box(frame.probe_text), box(page)))
            frame._set_nav('PLAYER')
            scene.act('tab_home')
            pump(root, 0.3)
    finally:
        app.quit()


if __name__ == '__main__':
    flow_rule()
    wrap_rule()
    gui()
    print(f'EIDOLITH LAYOUT: {checks - len(failures)}/{checks} checks passed')
    sys.exit(1 if failures else 0)
