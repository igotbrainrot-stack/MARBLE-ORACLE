"""0.4.9.5: every workspace uses the same page shell (oracle_shell).

    xvfb-run -a python3 Application/Tests/test_unified_shell_0495.py

Before 0.4.9.5 the tabs had rails of 225/240/312 px (and none on PASSPHRASE),
titles from 15 to 23 pt in three colours, buttons at 10 or 11 pt and HOME in
a different corner on each tab. This checks, in the real suite window, that:

* EIDOLITH, PASSPHRASE and TOUCH TYPE have the same rail width; AUGURSPEX's
  wider list rail is the one documented exception;
* every rail starts with its name in the same brand type, and every page
  title uses the same page-title type;
* HOME is a full-width button at the foot of the rail on every tab,
  OGGCULTIST included, and nothing in the rail sits below it but the
  version line;
* buttons use the one suite button font;
* AUGURSPEX uses the same surface colours as the others;
* PASSPHRASE never cuts a word off, from the 640x460 minimum upwards.
"""
import os
os.environ.setdefault('MARBLE_ORACLE_APPEARANCE', 'classic')   # 0.5.1: this test checks Classic's labels and surfaces
from pathlib import Path
import sys
import time
import tkinter as tk
from tkinter import ttk

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'Runtime' / 'Marble_Oracle_App'))
from marble_oracle import WindowApp, launch_plan  # noqa: E402
import oracle_shell as shell  # noqa: E402
from oggcultist_design_system import COLOR  # noqa: E402

failures = []
checks = 0


def check(name, ok, detail=''):
    global checks
    checks += 1
    if not ok:
        failures.append(f'{name}: {detail}')
        print('FAIL', name, detail)


def descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from descendants(child)


def font_of(widget):
    spec = widget.cget('font')
    root = widget.winfo_toplevel()
    actual = root.tk.call('font', 'actual', spec)
    pairs = dict(zip(actual[::2], actual[1::2]))
    return int(pairs['-size']), str(pairs['-weight'])


def same_font(widget, role):
    size, weight = shell.TYPE[role]
    return font_of(widget) == (size, weight)


def pump(seconds=0.6):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        root.update()
        time.sleep(0.02)


# The window exactly as a normal launch opens it, at the default size.
_args, options, _cls = launch_plan(['--selftest', '--no-network'])
app = WindowApp(options)
root, scene = app.root, app.scene
root.geometry('1216x848+0+0')
root.update()
scene.resized(1216, 848)
pump()

ATTR = {'tab_eidolith': 'eido', 'tab_passphrase': 'dk', 'tab_touch_type': 'touch',
        'tab_augurspex': 'aug', 'tab_oggcultist': 'ogg'}


def open_tab(action):
    """Show a workspace and return its frame (PASSPHRASE is rebuilt each time it opens)."""
    scene.act(action)
    pump()
    return getattr(scene, ATTR[action]).frame


frames = {action: open_tab(action) for action in ATTR}

# ---- rails -----------------------------------------------------------------
nav_tabs = ('tab_eidolith', 'tab_passphrase', 'tab_touch_type')
for action in nav_tabs:
    frame = frames[action] = open_tab(action)
    check(f'{action} uses the suite shell', isinstance(getattr(frame, 'shell', None), shell.Shell))
    width = frame.shell.rail_shell.winfo_width()
    check(f'{action} rail is {shell.RAIL_WIDTH} px', width == shell.RAIL_WIDTH, width)
aug = frames['tab_augurspex'] = open_tab('tab_augurspex')
check('AUGURSPEX list rail is the documented width', aug.rail_shell.winfo_width() == shell.LIST_RAIL_WIDTH,
      aug.rail_shell.winfo_width())

# ---- titles ----------------------------------------------------------------
eido, touch = frames['tab_eidolith'], frames['tab_touch_type']
dk = open_tab('tab_passphrase')
check('EIDOLITH page title type', same_font(eido.page_title, 'page_title'), font_of(eido.page_title))
check('TOUCH TYPE page title type', same_font(touch.mode_title, 'page_title'), font_of(touch.mode_title))
check('TOUCH TYPE brand type', same_font(touch.rail_title, 'brand'), font_of(touch.rail_title))
check('AUGURSPEX page title type', same_font(aug.selected_market, 'page_title'), font_of(aug.selected_market))
dk_titles = [w for w in descendants(dk) if isinstance(w, ttk.Label) and w.cget('text') == 'YOUR PASSPHRASE']
check('PASSPHRASE page title type', dk_titles and same_font(dk_titles[0], 'page_title'))
dk_brand = [w for w in descendants(dk.shell.rail) if isinstance(w, ttk.Label) and w.cget('text') == 'PASSPHRASE']
check('PASSPHRASE brand type', dk_brand and same_font(dk_brand[0], 'brand'))
# 0.5.4: a textured ttk label (a flat tk.Label showed as a slab on the rail's texture).
aug_brand = [w for w in descendants(aug.rail) if isinstance(w, (tk.Label, ttk.Label)) and w.cget('text') == 'AUGURSPEX']
check('AUGURSPEX brand type and colour', aug_brand and same_font(aug_brand[0], 'brand')
      and str(aug_brand[0].cget('foreground' if isinstance(aug_brand[0], ttk.Label) else 'fg')).upper()
      == COLOR['text_bright'].upper())

# ---- HOME at the foot of every rail -----------------------------------------
for action in ('tab_eidolith', 'tab_passphrase', 'tab_touch_type', 'tab_augurspex', 'tab_oggcultist'):
    frame = open_tab(action)
    homes = [w for w in descendants(frame) if isinstance(w, tk.Button) and w.cget('text') == 'HOME' and w.winfo_ismapped()]
    check(f'{action} has one HOME button', len(homes) == 1, len(homes))
    if not homes:
        continue
    home = homes[0]
    check(f'{action} HOME uses the suite button type', same_font(home, 'button'), font_of(home))
    x = home.winfo_rootx() - frame.winfo_rootx()
    check(f'{action} HOME is in the left rail', x < 60, x)
    # Measured to the bottom of the rail itself (OGGCULTIST's rail ends above its player bar).
    rail = home.master
    while rail.winfo_height() < 300 and rail is not frame:
        rail = rail.master
    bottom_gap = rail.winfo_rooty() + rail.winfo_height() - (home.winfo_rooty() + home.winfo_height())
    check(f'{action} HOME is at the foot of the rail', 0 <= bottom_gap <= 70, bottom_gap)
    rail_width = home.master.winfo_width()
    check(f'{action} HOME fills the rail', home.winfo_width() >= rail_width - 2 * shell.RAIL_PADX - 2,
          (home.winfo_width(), rail_width))

# ---- buttons ----------------------------------------------------------------
for action in ('tab_eidolith', 'tab_passphrase', 'tab_touch_type', 'tab_augurspex'):
    frame = open_tab(action)
    buttons = [w for w in descendants(frame) if isinstance(w, tk.Button) and w.winfo_ismapped()
               and w.cget('text') and len(w.cget('text')) > 2]
    nav = set(getattr(frame, 'nav_buttons', {}).values()) | set(getattr(frame, 'mode_buttons', {}).values())
    odd = [(w.cget('text'), font_of(w)) for w in buttons if w not in nav and not same_font(w, 'button')]
    check(f'{action} every push button uses the suite button type', not odd, odd[:5])

# ---- colours ------------------------------------------------------------------
for key, token in (('bg', 'canvas'), ('panel', 'raised'), ('rail', 'sidebar'), ('inset', 'sunken')):
    check(f'AUGURSPEX {key} is the suite {token}', aug.p[key].upper() == COLOR[token].upper(), aug.p[key])

# ---- PASSPHRASE: no word cut off at any size -----------------------------------
from oracle_dicekey import PARTS  # noqa: E402
dk = open_tab('tab_passphrase')
for width, height in ((1216, 848), (900, 580), (640, 460)):
    root.geometry(f'{width}x{height}+0+0'); root.update()
    scene.resized(root.winfo_width(), root.winfo_height()); pump()
    cut = []
    for _ in range(40):
        dk.roll(); root.update()
        for part in PARTS:
            lab = dk.part_labels[part]
            need = int(root.tk.call('font', 'measure', lab.cget('font'), lab.cget('text')))
            if need > lab.winfo_width():
                cut.append((lab.cget('text'), need, lab.winfo_width()))
    check(f'PASSPHRASE {width}x{height}: no word cut off', not cut, cut[:3])
    # Not left to chance: the widest word in the list must fit every card.
    for word in ('mammogram', 'womanhood'):
        for part in PARTS:
            lab = dk.part_labels[part]
            need = int(root.tk.call('font', 'measure', dk._part_font(lab, word), word))
            check(f'PASSPHRASE {width}x{height}: "{word}" fits {part}', need <= lab.winfo_width(),
                  (need, lab.winfo_width()))
    copy = dk.copy_button
    inside = copy.winfo_rooty() + copy.winfo_height() <= dk.winfo_rooty() + dk.winfo_height()
    check(f'PASSPHRASE {width}x{height}: actions on screen', copy.winfo_ismapped() and inside)

# ---- the smallest window: HOME stays reachable and the logo fits ----------------
# (0.4.9.5 review: HOME had dropped off OGGCULTIST's short rail and the
# EIDOLITH wordmark was cut at the narrowed rail.)
root.geometry('640x460+0+0'); root.update()
scene.resized(root.winfo_width(), root.winfo_height()); pump()
for action in ('tab_oggcultist', 'tab_eidolith', 'tab_touch_type', 'tab_augurspex'):
    frame = open_tab(action)
    homes = [w for w in descendants(frame) if isinstance(w, tk.Button) and w.cget('text') == 'HOME']
    visible = [h for h in homes if h.winfo_ismapped() and h.winfo_height() > 10
               and h.winfo_rooty() + h.winfo_height() <= frame.winfo_rooty() + frame.winfo_height() + 1]
    check(f'640x460 {action}: HOME visible', len(visible) == 1, [(h.winfo_ismapped(), h.winfo_height()) for h in homes])
eido = open_tab('tab_eidolith')
logo = eido.shell._logo[0]
items = [logo.bbox(i) for i in logo.find_all() if logo.type(i) == 'text']
check('640x460 EIDOLITH wordmark fits its rail', items and max(b[2] for b in items) <= int(logo.cget('width')),
      (items, logo.cget('width')))

app.quit()
print(f'UNIFIED SHELL: {checks - len(failures)}/{checks} checks passed')
sys.exit(1 if failures else 0)
