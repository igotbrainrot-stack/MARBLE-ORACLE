"""0.4.9.9: the welcome window, the ? button, slim scrollbars and the dropdown look.

    xvfb-run -a python3 Application/Tests/test_welcome_and_widgets_0499.py
"""
from pathlib import Path
import json
import os
import sys
import tempfile
import time

os.environ['MARBLE_ORACLE_STATE'] = tempfile.mkdtemp(prefix='mo-welcome-')
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'Runtime' / 'Marble_Oracle_App'))
import tkinter as tk  # noqa: E402

from oracle_widgets import SlimScrollbar, style_dropdown  # noqa: E402

failures = []
checks = 0


def check(name, ok, detail=''):
    global checks
    checks += 1
    if not ok:
        failures.append(name)
        print('FAIL', name, detail, flush=True)


# ---- SlimScrollbar ---------------------------------------------------------
root = tk.Tk()
root.geometry('300x200+0+0')
calls = []
frame = tk.Frame(root)
frame.pack(fill='both', expand=True)
bar = SlimScrollbar(frame, orient='vertical', command=lambda *a: calls.append(a))
text = tk.Text(frame, height=3, width=20)
bar.pack(side='right', fill='y')
text.pack(side='left', fill='both', expand=True)
root.update()
check('the scrollbar asks for little height (it must not squeeze what it scrolls)', bar.winfo_reqheight() <= 30,
      bar.winfo_reqheight())
check('the scrollbar is stretched to the full height', bar.winfo_height() >= 150, bar.winfo_height())
bar.set(0.0, 1.0)
check('no thumb when everything is visible', not bar.find_withtag('thumb'))
bar.set(0.25, 0.5)
check('a thumb when there is more to see', bool(bar.find_withtag('thumb')))
check('get() returns what set() gave', bar.get() == (0.25, 0.5))
h = bar.winfo_height()
bar.event_generate('<ButtonPress-1>', x=5, y=int(h * 0.9))
root.update()
check('clicking the track below the thumb pages down', calls and calls[-1] == ('scroll', 1, 'pages'), calls[-1:])
bar.event_generate('<ButtonPress-1>', x=5, y=int(h * 0.3))
bar.event_generate('<B1-Motion>', x=5, y=int(h * 0.5))
bar.event_generate('<ButtonRelease-1>', x=5, y=int(h * 0.5))
root.update()
check('dragging the thumb asks to move to a fraction', any(c[0] == 'moveto' for c in calls), calls[-2:])
later = []
bar.configure(command=lambda *a: later.append(a))
bar.event_generate('<ButtonPress-1>', x=5, y=2)
root.update()
check('configure(command=...) replaces the command, as on tk.Scrollbar', later and later[-1][0] == 'scroll', later)
text.configure(yscrollcommand=bar.set)
text.insert('end', '\n'.join(str(i) for i in range(200)))
root.update()
check('a Text widget drives it through yscrollcommand', bar.get()[1] < 1.0, bar.get())

# ---- dropdowns -------------------------------------------------------------
var = tk.StringVar(root, 'one')
menu = tk.OptionMenu(root, var, 'one', 'two', 'three')
style_dropdown(menu)
menu.pack()
root.update()
check('the Motif indicator is gone', str(menu.cget('indicatoron')) in ('0', 'False', 'false'))
check('a chevron image is shown', bool(str(menu.cget('image'))))
wide = tk.OptionMenu(root, var, 'one', 'two')
style_dropdown(wide)
wide.pack(fill='x')
root.geometry('600x260')
root.update()
root.update()
pinned = [w for w in wide.winfo_children() if isinstance(w, tk.Label) and w.winfo_manager() == 'place']
check('a stretched dropdown pins its chevron to the right edge', bool(pinned) and not str(wide.cget('image')),
      (pinned, wide.cget('image')))
root.destroy()

root = tk.Tk()                         # a second Tk reuses the window name "."
var = tk.StringVar(root, 'a')
menu = tk.OptionMenu(root, var, 'a', 'b')
try:
    style_dropdown(menu)
    ok = True
except tk.TclError as exc:
    ok = exc
check('dropdowns work in a second Tk instance (the chevron image is not stale)', ok is True, ok)
root.destroy()

# ---- the welcome window -----------------------------------------------------
import oracle_suite_guide as guide  # noqa: E402
from marble_oracle import WindowApp, launch_plan  # noqa: E402

check('the welcome is shown at start by default', guide.should_show_at_start())
_a, options, _c = launch_plan(['--selftest', '--no-network'])
app = WindowApp(options)
root, scene = app.root, app.scene
root.geometry('900x580+0+0')


def pump(seconds=0.4):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        root.update()
        if scene.W == 0 or getattr(scene, 'need_build', False):
            scene.resized(*app.canvas_size())
        scene.tick()
        time.sleep(0.02)


pump(0.8)
check('never during the self-test or tests', guide.maybe_show_welcome(scene) is None)
check('the ? button is in the tab strip', any(h[4] == 'guide' for h in scene.hot))
tabs = [h for h in scene.hot if str(h[4]).startswith('tab_')]
qbox = next(h for h in scene.hot if h[4] == 'guide')
check('the ? button sits after the six tabs', len(tabs) == 6 and qbox[0] > max(t[2] for t in tabs), (qbox, tabs))
check('the ? button does not run into the window buttons',
      all(qbox[2] <= h[0] for h in scene.hot if h[4] in ('min', 'max', 'quit', 'full') and h[1] < qbox[3]))
if os.name != 'nt':
    check('Linux gets a window icon', getattr(root, '_marble_icon', None) is not None)

scene.act('guide')
pump(0.6)
win = scene._guide_window
check('? opens the welcome window', win is not None and win.winfo_exists())
check('the window sits inside the suite window',
      win.winfo_width() <= root.winfo_width() and win.winfo_height() <= root.winfo_height(),
      (win.winfo_width(), win.winfo_height(), root.winfo_width(), root.winfo_height()))


def all_widgets(widget):
    out = [widget]
    for child in widget.winfo_children():
        out.extend(all_widgets(child))
    return out


buttons = {w.cget('text'): w for w in all_widgets(win) if isinstance(w, tk.Button)}
for name in ('HOME', 'OGGCULTIST', 'EIDOLITH', 'AUGURSPEX', 'PASSPHRASE', 'TOUCH TYPE'):
    check(f'there is an OPEN {name} button', 'OPEN ' + name in buttons, sorted(buttons))
check('a close button is always reachable', any(t in buttons for t in ('CLOSE', 'START EXPLORING')))
check('F1 brings the same window forward, not a second one',
      scene.on_key(type('E', (), {'keysym': 'F1', 'char': ''})()) == 'break' and scene._guide_window is win)
for name, overlay in (('EIDOLITH', 'eido'), ('PASSPHRASE', 'dk'), ('TOUCH TYPE', 'touch')):
    scene.act('guide')
    pump(0.3)
    win = scene._guide_window
    found = {w.cget('text'): w for w in all_widgets(win) if isinstance(w, tk.Button)}
    found['OPEN ' + name].invoke()
    pump(0.6)
    check(f'OPEN {name} opens that workspace and closes the guide',
          scene._which_overlay() == overlay and scene._guide_window is None, (scene._which_overlay(), overlay))
scene.act('tab_home')
pump(0.3)

# Unticking "Show this when Marble Oracle starts" is remembered.
scene.act('guide')
pump(0.3)
win = scene._guide_window
checkbox = next(w for w in all_widgets(win) if isinstance(w, tk.Checkbutton))
checkbox.invoke()
win.event_generate('<Escape>')
pump(0.3)
saved = json.loads((Path(os.environ['MARBLE_ORACLE_STATE']) / guide.PREFS_FILE).read_text())
check('unticking is saved', saved.get('show_at_start') is False, saved)
check('and the welcome then stays away at start', not guide.should_show_at_start())

app.quit()
print(f'WELCOME AND WIDGETS 0.4.9.9: {checks - len(failures)}/{checks} checks passed')
sys.exit(1 if failures else 0)
