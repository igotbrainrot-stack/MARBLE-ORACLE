"""0.4.9.7 polish: things that were cut off or drawn on top of each other at 900x580.

    xvfb-run -a python3 Application/Tests/test_polish_0497.py

* HOME THREE CUTS: the card captions ("REVERSED · ALREADY") ran into each other,
  and the TAROT / RUNES switch covered the top of the third card;
* PASSPHRASE and TOUCH TYPE: the page description ran off the right edge,
  cut mid-word.
"""
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'Runtime' / 'Marble_Oracle_App'))

failures = []
checks = 0


def check(name, ok, detail=''):
    global checks
    checks += 1
    if not ok:
        failures.append(name)
        print('FAIL', name, detail, flush=True)


def overlaps(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


# ---- ellipsize, on its own ---------------------------------------------------
import tkinter as tk  # noqa: E402
import tkinter.font  # noqa: E402,F401
from oracle_widgets import ellipsize  # noqa: E402

root = tk.Tk()
root.geometry('300x80+0+0')
long_text = 'Learn the home row. Start with F and J, then unlock more letters as you practise.'
holder = tk.Frame(root, width=200, height=30)
holder.pack(fill='x')
label = tk.Label(holder, text=long_text, anchor='w')
label.pack(fill='x')
ellipsize(label)
root.update()
shown = label.cget('text')
check('a long description is shortened to fit', shown != long_text and shown.endswith('…'), shown)
check('what is shown fits the label',
      tk.font.Font(font=label.cget('font')).measure(shown) <= label.winfo_width(), (shown, label.winfo_width()))
label.configure(text='Short.')
root.update()
check('a later short text is shown whole', label.cget('text') == 'Short.', label.cget('text'))
label.configure(text=long_text)
root.update()
check('a later long text is shortened again', label.cget('text').endswith('…'))
root.geometry('1400x80')
root.update()
root.update()
check('widening the window shows the whole text again', label.cget('text') == long_text, label.cget('text'))
check('configure() with no arguments still returns the options', isinstance(label.configure(), dict))
check("configure('text') still answers a query", label.configure('text')[0] == 'text')
root.destroy()

# ---- the real window at 900x580 ------------------------------------------
from marble_oracle import WindowApp, launch_plan  # noqa: E402

_a, options, _c = launch_plan(['--selftest', '--no-network'])
app = WindowApp(options)
root, scene = app.root, app.scene
root.geometry('900x580+0+0')
root.update()
scene.resized(*app.canvas_size())


def pump(seconds=0.4):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        root.update()
        scene.tick()
        time.sleep(0.02)


pump(0.8)
c = scene.c
# Card captions: the text items tagged "cards" below the card art.
cards_box = scene.rect['cards']
toggles = [h for h in scene.hot if h[4] in ('mode_tarot', 'mode_runes')]
card_boxes = [h for h in scene.hot if str(h[4]).startswith('card')]
check('three cards and the switch are drawn', len(card_boxes) == 3 and len(toggles) == 2, (card_boxes, toggles))
for t in toggles:
    for card in card_boxes:
        art = (card[0], card[1], card[2], card[3] - int(34 * scene.k))   # the hot box includes the captions below
        check(f'{t[4]} does not cover {card[4]}', not overlaps(t[:4], art), (t[:4], art))

caption_boxes = []
for item in c.find_withtag('cards'):
    if c.type(item) != 'text':
        continue
    text = c.itemcget(item, 'text')
    if 'REVERSED' in text or text in ('ALREADY', 'LOAD', 'DUE') or text.endswith('…'):
        caption_boxes.append((text, c.bbox(item)))
for i, (ta, a) in enumerate(caption_boxes):
    for tb, b in caption_boxes[i + 1:]:
        check(f'captions "{ta}" and "{tb}" do not overlap', not overlaps(a, b), (a, b))
for text, box in caption_boxes:
    check(f'caption "{text}" stays inside the panel', cards_box[0] <= box[0] and box[2] <= cards_box[2], (box, cards_box))

# Page descriptions fit their line on every tab that has one.
for tab, attr in (('tab_passphrase', 'dk'), ('tab_touch_type', 'touch')):
    scene.act(tab)
    pump(0.8)
    frame = getattr(getattr(scene, attr), 'frame', None) or getattr(scene, attr)
    stack, found = [frame], []
    while stack:
        widget = stack.pop()
        stack.extend(widget.winfo_children())
        if hasattr(widget, '_full_text') and widget.winfo_ismapped():
            found.append(widget)
    check(f'{tab}: the page description is managed', bool(found), tab)
    for widget in found:
        shown = widget.cget('text')
        width = widget.winfo_width()
        need = tk.font.Font(font=widget.cget('font')).measure(shown)
        check(f'{tab}: the description fits its line', need <= width + 1, (shown, need, width))
        check(f'{tab}: it is never cut mid-word without a mark',
              shown == widget._full_text or shown.endswith('…'), shown)
scene.act('tab_home')
pump(0.3)

app.quit()
print(f'POLISH 0.4.9.7: {checks - len(failures)}/{checks} checks passed')
sys.exit(1 if failures else 0)
