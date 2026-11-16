"""0.4.9.7: HOME can be used from the keyboard, and its controls answer the pointer.

    xvfb-run -a python3 Application/Tests/test_home_keyboard_0497.py

Before 0.4.9.7 HOME's controls were only rectangles on a canvas: Tab did
nothing there, and nothing but the cursor changed under the pointer.
"""
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'Runtime' / 'Marble_Oracle_App'))
from oggcultist_design_system import COLOR as C  # noqa: E402
from oracle_home_focus import tab_order, RING_TAG, RING_TOP_TAG  # noqa: E402

failures = []
checks = 0


def check(name, ok, detail=''):
    global checks
    checks += 1
    if not ok:
        failures.append(name)
        print('FAIL', name, detail, flush=True)


# ---- the Tab order rule, without a display ---------------------------------
hot = [
    (300, 10, 360, 30, 'tab_eidolith'),
    (10, 11, 60, 31, 'tab_home'),           # a pixel lower, still the same row
    (900, 10, 930, 30, 'quit'),             # never by Tab
    (870, 10, 900, 30, 'min'),
    (100, 200, 200, 260, 'rune_draw'),
    (100, 100, 400, 120, 'slider'),
    (50, 50, 80, 80, 'dial:vol'),
    (100, 300, 200, 360, 'card0'),
    (110, 300, 210, 360, 'card0'),          # redrawn: the later box wins
    (5, 5, 6, 6, 'next'),                   # too small to be a control
]
order = tab_order(hot)
actions = [b[4] for b in order]
check('reading order: one row left to right, then down',
      actions == ['tab_home', 'tab_eidolith', 'rune_draw', 'card0'], actions)
check('close, minimise, the slider and the dials are left out',
      not {'quit', 'min', 'slider', 'dial:vol'} & set(actions))
check('a redrawn control is visited once, at its newest box',
      [b for b in order if b[4] == 'card0'] == [(110, 300, 210, 360, 'card0')])
check('inactive controls are skipped',
      [b[4] for b in tab_order(hot, lambda h: h[4] != 'rune_draw')] == ['tab_home', 'tab_eidolith', 'card0'])
check('no controls, no order', tab_order([]) == [])

# ---- the real window ------------------------------------------------------
from marble_oracle import WindowApp, launch_plan  # noqa: E402

_a, options, _c = launch_plan(['--selftest', '--no-network'])
app = WindowApp(options)
root, scene = app.root, app.scene
root.geometry('1216x848+0+0')
root.update()
scene.resized(1216, 848)


def pump(seconds=0.3):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        root.update()
        scene.tick()
        time.sleep(0.02)


def key(keysym):
    return scene.on_key(type('E', (), {'keysym': keysym, 'char': ''})())


def rings(tag):
    return [scene.c.itemcget(i, 'outline').upper() for i in scene.c.find_withtag(tag)]


pump(0.6)
targets = [t[4] for t in scene.kb_targets()]
check('HOME has controls to reach by keyboard', len(targets) >= 6, targets)
check('every workspace tab is in the Tab order',
      all(t in targets for t in ('tab_home', 'tab_oggcultist', 'tab_eidolith', 'tab_augurspex',
                                 'tab_passphrase', 'tab_touch_type')), targets)
check('close is not in the Tab order', 'quit' not in targets)

check('Tab is taken by HOME, not passed to Tk', key('Tab') == 'break')
first = scene.kb_action
check('the first Tab focuses the first control', first == targets[0], (first, targets[:2]))
pump(0.1)
all_rings = rings(RING_TAG) + rings(RING_TOP_TAG)
check('the focused control has the cream focus ring', C['focus'].upper() in all_rings, all_rings)

key('Tab')
check('Tab moves on', scene.kb_action == targets[1], scene.kb_action)
key('ISO_Left_Tab')
check('Shift+Tab moves back', scene.kb_action == targets[0], scene.kb_action)
key('ISO_Left_Tab')
check('Shift+Tab from the first control wraps to the last', scene.kb_action == targets[-1], scene.kb_action)

# Enter presses the focused control: the RUNES switch.
scene.kb_action = 'mode_runes' if 'mode_runes' in targets else None
check('the RUNES switch is reachable', scene.kb_action == 'mode_runes', targets)
if scene.kb_action:
    key('Return')
    pump(0.3)
    check('Enter presses the focused control', scene.divination_mode == 'runes', scene.divination_mode)
    targets_runes = [t[4] for t in scene.kb_targets()]
    check('the rune controls join the Tab order in rune mode', 'rune_draw' in targets_runes, targets_runes)
    scene.kb_action = 'mode_tarot'
    key('space')
    pump(0.3)
    check('Space presses it too', scene.divination_mode == 'tarot', scene.divination_mode)

check('Escape puts the focus away', key('Escape') == 'break' and scene.kb_action is None)
pump(0.1)
check('and the focus ring goes with it', C['focus'].upper() not in rings(RING_TAG) + rings(RING_TOP_TAG))

quit_called = []
original_quit = app.quit
app.quit = lambda *a, **k: quit_called.append(True)
check('with no focus, Escape still does not quit', key('Escape') is None and not quit_called)
app.quit = original_quit

# Hover: an outline under the pointer, gone when it leaves.
box = next(t for t in scene.kb_targets() if t[4] == 'tab_eidolith')
scene.hover_set(box)
pump(0.1)
hover_rings = rings(RING_TAG) + rings(RING_TOP_TAG)
check('the control under the pointer gets an outline', C['text_3'].upper() in hover_rings, hover_rings)
check('the hover outline is not the focus ring', C['focus'].upper() not in hover_rings, hover_rings)
scene.hover_set(None)
pump(0.1)
check('the outline goes when the pointer leaves', not rings(RING_TAG) + rings(RING_TOP_TAG))

# A resize deletes and rebuilds the canvas; the ring must follow.
scene.kb_action = 'tab_eidolith'
scene.resized(1000, 650)
pump(0.3)
check('the focus ring is redrawn after a resize', C['focus'].upper() in rings(RING_TAG) + rings(RING_TOP_TAG))

# In a workspace the keyboard belongs to the workspace.
scene.kb_action = None
scene.act('tab_eidolith')
pump(0.6)
check('Tab inside a workspace is left to Tk', key('Tab') != 'break')
check('and does not move HOME focus', scene.kb_action is None)
scene.act('tab_home')
pump(0.3)

app.quit()
print(f'HOME KEYBOARD 0.4.9.7: {checks - len(failures)}/{checks} checks passed')
sys.exit(1 if failures else 0)
