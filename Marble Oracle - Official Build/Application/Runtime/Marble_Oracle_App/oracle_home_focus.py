"""Keyboard focus and pointer hover for HOME's canvas-drawn controls.

HOME is painted on one canvas, so its buttons (the workspace tabs, the section
buttons, DRAW THREE, the tarot cards, the rune stones …) are rectangles in
`Scene.hot`, not Tk widgets. Before 0.4.9.7 that meant:

* Tab did nothing on HOME, so HOME could only be used with a mouse;
* nothing changed under the pointer except the cursor shape.

This mixin adds both without touching how the controls are drawn:

* **Tab / Shift+Tab** move a keyboard focus through the visible controls in
  reading order (top to bottom, then left to right). **Enter** or **Space**
  presses the focused control. **Escape** puts the focus away. With no focus,
  Enter and Space keep their old meanings (speak, next quote).
* The focused control gets the suite's 2 px cream focus ring
  (`COLOR['focus']`, the same as every Tk workspace since 0.4.9.6).
* The control under the pointer gets a quiet 1 px outline in the tertiary
  text colour: visible, and never mistaken for focus or for "current".

Controls that end the session or hide the window (close, minimise) and the
continuous ones (volume slider, dials) are left out of the Tab order; they are
still clicked as before.

Rings on the dashboard itself are drawn under the bending CRT picture, so they
bend with what they surround; rings on the menu row, status row and bezel are
drawn on top, like those controls.
"""
from __future__ import annotations

from oggcultist_design_system import COLOR

# Actions that are never reached with Tab: they close or hide the suite, or
# need dragging rather than a press.
SKIP_ACTIONS = frozenset({'quit', 'min', 'bz7', 'bz9', 'slider'})
SKIP_PREFIXES = ('dial:',)

FOCUS_COLOUR = COLOR['focus']
HOVER_COLOUR = COLOR['text_3']
RING_TAG = 'kbring'           # under the CRT picture: bends with the dashboard
RING_TOP_TAG = 'kbring-top'   # above everything: menu row, status row, bezel

# A hover outline round something this large (a whole panel) is noise, not feedback.
HOVER_MAX_SHARE = 0.18

# Friendly names for the status line when focus arrives on a control.
NAMES = {
    'tab_home': 'HOME', 'tab_oggcultist': 'OGGCULTIST', 'tab_eidolith': 'EIDOLITH',
    'tab_augurspex': 'AUGURSPEX', 'tab_overcast': 'OVERCAST', 'appearance': 'APPEARANCE', 'tab_passphrase': 'PASSPHRASE', 'tab_touch_type': 'TOUCH TYPE',
    'mode_tarot': 'TAROT', 'mode_runes': 'RUNES', 'rune_draw': 'DRAW THE RUNES',
    'rune_select0': 'RUNE · PAST', 'rune_select1': 'RUNE · PRESENT', 'rune_select2': 'RUNE · POSSIBLE FUTURE',
    'card0': 'TAROT CARD 1', 'card1': 'TAROT CARD 2', 'card2': 'TAROT CARD 3',
    'speak': 'SPEAK THE LATIN', 'lexvoice': 'VOICE', 'ecc': 'ECCLESIASTICAL / CLASSICAL',
    'say_c': 'SPEAK · CLASSICAL', 'say_e': 'SPEAK · ECCLESIASTICAL',
    'next': 'NEXT QUOTE', 'word': 'NEW WORD', 'deal': 'DEAL', 'view': 'GRADE', 'full': 'FULL SCREEN',
    'aug_next': 'NEXT MARKET', 'aug_previous': 'PREVIOUS MARKET', 'dk': 'PASSPHRASE',
    'guide': 'WELCOME GUIDE',
}


def tab_order(hot, active=lambda h: True):
    """The controls Tab visits, in reading order, one entry per action.

    `hot` is Scene.hot: (x0, y0, x1, y1, action) boxes, where a later entry for
    the same action replaces an earlier one (that is how the scene redraws a
    control). Rows are grouped with a tolerance so a row of buttons drawn a
    pixel or two apart is still read left to right.
    """
    latest = {}
    for h in hot:
        action = h[4]
        if not isinstance(action, str) or action in SKIP_ACTIONS or action.startswith(SKIP_PREFIXES):
            continue
        if h[2] - h[0] < 2 or h[3] - h[1] < 2 or not active(h):
            continue
        latest[action] = tuple(h[:5])
    boxes = list(latest.values())
    if not boxes:
        return []
    tolerance = max(4, min(b[3] - b[1] for b in boxes) / 2)
    boxes.sort(key=lambda b: (b[1], b[0]))
    rows, row, row_top = [], [], None
    for b in boxes:
        if row and b[1] - row_top > tolerance:
            rows.append(row)
            row = []
        if not row:
            row_top = b[1]
        row.append(b)
    rows.append(row)
    return [b for r in rows for b in sorted(r, key=lambda b: b[0])]


class HomeFocusMixin:
    """Mixed into Scene. Needs: self.c, self.hot, self.W, self.H, self.rect,
    self.hot_active(h), self._which_overlay(), self.act(name), self.say(text)."""

    kb_action = None        # the focused control's action, or None
    hover_action = None     # the control under the pointer, or None
    _ring_seen = None       # what the rings on the canvas currently show

    # ---- keyboard -----------------------------------------------------------
    def kb_targets(self):
        return tab_order(self.hot, self.hot_active)

    def kb_move(self, step):
        targets = self.kb_targets()
        if not targets:
            return
        actions = [t[4] for t in targets]
        if self.kb_action in actions:
            index = (actions.index(self.kb_action) + step) % len(actions)
        else:
            index = 0 if step > 0 else len(actions) - 1
        self.kb_action = actions[index]
        name = NAMES.get(self.kb_action)
        if name:
            self.say(name + ' · ENTER TO SELECT · ESC TO LEAVE')
        self.paint_rings()

    def kb_clear(self):
        if self.kb_action is None:
            return False
        self.kb_action = None
        self.paint_rings()
        return True

    def kb_activate(self):
        """Press the focused control. False when nothing usable is focused."""
        if self.kb_action is None:
            return False
        if self.kb_action not in {t[4] for t in self.kb_targets()}:
            self.kb_clear()                       # it has gone (mode changed, window resized)
            return False
        box = next(t for t in self.kb_targets() if t[4] == self.kb_action)
        self.act(self.kb_action, (box[0] + box[2]) / 2.0)
        self.paint_rings()
        return True

    def kb_key(self, keysym):
        """Handle a HOME key if it belongs to focus navigation. Returns True when used."""
        k = keysym.lower()
        if k in ('tab', 'iso_left_tab'):
            self.kb_move(-1 if k == 'iso_left_tab' else 1)
            return True
        if self.kb_action is not None:
            if k in ('return', 'kp_enter', 'space'):
                return self.kb_activate()
            if k == 'escape':
                return self.kb_clear()
        return False

    # ---- pointer ------------------------------------------------------------
    def hover_set(self, h):
        action = h[4] if h else None
        if action is not None and isinstance(action, str) and action.startswith(SKIP_PREFIXES):
            action = None
        if action != self.hover_action:
            self.hover_action = action
            self.paint_rings()

    # ---- drawing ------------------------------------------------------------
    def _chrome_box(self, box):
        """True for boxes on the menu row, status row or bezel (drawn above the CRT picture)."""
        try:
            menu_bottom, status_top = self.rect['menu'][3], self.rect['status'][1]
        except (AttributeError, KeyError, TypeError, IndexError):
            return True
        return (box[3] <= menu_bottom or box[1] >= status_top
                or box[0] < 0 or box[1] < 0 or box[2] > self.W or box[3] > self.H)

    def _box_for(self, action):
        if action is None:
            return None
        found = None
        for h in self.hot:
            if h[4] == action and self.hot_active(h):
                found = h
        return found

    def paint_rings(self, force=False):
        """Draw the focus ring and the hover outline where they belong now.

        Cheap to call every frame: it redraws only when what it would draw has
        changed, or when a resize has deleted the rings.
        """
        c = self.c
        focus = self._box_for(self.kb_action)
        hover = self._box_for(self.hover_action) if self.hover_action != self.kb_action else None
        if hover is not None:
            area = max(1.0, float(self.W) * float(self.H))
            if (hover[2] - hover[0]) * (hover[3] - hover[1]) > HOVER_MAX_SHARE * area:
                hover = None
        wanted = (tuple(focus[:4]) if focus else None, tuple(hover[:4]) if hover else None)
        try:
            drawn = bool(c.find_withtag(RING_TAG) or c.find_withtag(RING_TOP_TAG))
        except Exception:
            return
        if not force and wanted == self._ring_seen and (drawn or wanted == (None, None)):
            return
        c.delete(RING_TAG)
        c.delete(RING_TOP_TAG)
        self._ring_seen = wanted
        for box, colour, width, pad in ((hover, HOVER_COLOUR, 1, 2), (focus, FOCUS_COLOUR, 2, 3)):
            if box is None:
                continue
            tag = RING_TOP_TAG if self._chrome_box(box) else RING_TAG
            c.create_rectangle(box[0] - pad, box[1] - pad, box[2] + pad, box[3] + pad,
                               outline=colour, width=width, tags=tag)
        c.tag_raise(RING_TOP_TAG)
