"""oracle_vhs.py -- the 90s infomercial pieces the tabs share (build 0985; cut down to those pieces in 1020).

The intermission-card art (Art, the banner() widget, its mascots, sky, ticker and their geometry) came off the tabs in 0993 and was deleted in 1020: nothing called it.
What is left is what the DICEKEY card draws with.

Stdlib only.  Nothing here imports Tk: every function draws on a canvas-LIKE object (create_rectangle, create_line, create_oval, create_text, itemconfigure,
delete), so it is tested with a fake canvas.

    palette(theme)             the colours, all derived from the active VIEW theme's tokens (plus black and white); mix(a, b, t) blends two
    wordart(...)               extruded, outlined, highlighted text (a stack of text items), returns its item ids
    BulbRing(c, rect, ...)     game-show bulbs round a rectangle, three chasing: .animate(now), .destroy()
    bevel_box(...)             a chunky raised button face
    calm()                     True when MARBLE_ORACLE_CALM=1 (the --calm flag): the bulbs are drawn once and never move

Safety: nothing blinks faster than 3 times a second and the flashing parts are small.  `calm` freezes everything.  Every colour comes from the active VIEW
theme's tokens (or black / white), so the look follows the colour preset.
"""
import os
import time

BLACK, WHITE = "#000000", "#ffffff"

THEME = dict(bg="#06060d", panel="#0a0c18", edge="#17415a", edge2="#0f2233", cyan="#19e6ff", mag="#ff2bd6",
             gold="#ffd23f", lime="#7cff6b", red="#ff4d5e", txt="#c9d4e8", dim="#5d6d8a", orange="#ff8a2a")


def calm():
    """True when the owner asked for no motion (the --calm flag sets MARBLE_ORACLE_CALM=1)."""
    return os.environ.get("MARBLE_ORACLE_CALM", "") == "1"


# ---------------------------------------------------------------------------------------------------------------------
# Colour
# ---------------------------------------------------------------------------------------------------------------------
def hexrgb(h):
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def rgbhex(r, g, b):
    return "#%02x%02x%02x" % (max(0, min(255, int(round(r)))), max(0, min(255, int(round(g)))), max(0, min(255, int(round(b)))))


def mix(a, b, t):
    """a at 0, b at 1."""
    ra, ga, ba = hexrgb(a)
    rb, gb, bb = hexrgb(b)
    return rgbhex(ra + (rb - ra) * t, ga + (gb - ga) * t, ba + (bb - ba) * t)


def palette(theme=None):
    """The art's colours, all derived from the VIEW theme's tokens (plus black and white)."""
    p = dict(THEME)
    if theme:
        p.update({k: v for k, v in theme.items() if k in THEME})
    p["dark"] = mix(p["bg"], BLACK, 0.45)
    p["deep"] = mix(p["panel"], BLACK, 0.55)
    p["steel"] = mix(p["txt"], BLACK, 0.55)
    p["steel2"] = mix(p["txt"], BLACK, 0.78)
    p["paper"] = mix(p["txt"], WHITE, 0.65)
    p["glint"] = mix(p["txt"], WHITE, 0.85)
    p["violet"] = mix(p["mag"], p["cyan"], 0.35)
    p["room"] = mix(p["bg"], BLACK, 0.7)
    p["black"], p["white"] = BLACK, WHITE
    return p


# ---------------------------------------------------------------------------------------------------------------------
# Pure geometry (tested on its own)
# ---------------------------------------------------------------------------------------------------------------------
def tw(text, px):
    """Width of `text` in a monospace face at `px` pixels (0.6 em a character)."""
    return int(len(text) * px * 0.6)


def perimeter(x0, y0, x1, y1, step):
    """Points spaced `step` apart round the rectangle's border, clockwise from the top-left corner."""
    pts = []
    n = max(1, int((x1 - x0) // step))
    for i in range(n):
        pts.append((x0 + i * (x1 - x0) / float(n), y0))
    m = max(1, int((y1 - y0) // step))
    for i in range(m):
        pts.append((x1, y0 + i * (y1 - y0) / float(m)))
    for i in range(n):
        pts.append((x1 - i * (x1 - x0) / float(n), y1))
    for i in range(m):
        pts.append((x0, y1 - i * (y1 - y0) / float(m)))
    return pts


# ---------------------------------------------------------------------------------------------------------------------
# WordArt: a stack of text items (extrusion, outline, highlight, face)
# ---------------------------------------------------------------------------------------------------------------------
RING = ((-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1))


def wordart(c, x, y, text, px, family, face, outline=BLACK, shadow=None, depth=4, anchor="w", tags=(), italic=True, glint=None,
            bloom=None, bleed=None):
    """Chunky 90s text: an optional phosphor bloom round it and a red/blue chroma bleed to either side, then an extruded shadow `depth` pixels
    deep, a black outline, a pale highlight a pixel up and left, then the face.  `bloom` is a colour, `bleed` a (left, right) pair of colours.
    Returns {"face": id, "all": [ids], "w": approximate width}.  Every item gets `tags`."""
    font = (family, -int(px), "bold italic" if italic else "bold")
    shadow = shadow or mix(face, BLACK, 0.7)
    ids = []
    if bloom:
        for dx, dy in ((-4, 0), (4, 0), (0, -3), (0, 3), (-3, -2), (3, -2), (-3, 3), (3, 3)):
            ids.append(c.create_text(x + dx, y + dy, text=text, font=font, fill=bloom, anchor=anchor, tags=tags))
    if bleed:
        ids.append(c.create_text(x - 2, y, text=text, font=font, fill=bleed[0], anchor=anchor, tags=tags))
        ids.append(c.create_text(x + 3, y + 1, text=text, font=font, fill=bleed[1], anchor=anchor, tags=tags))
    for d in range(depth, 0, -1):
        ids.append(c.create_text(x + d, y + d, text=text, font=font, fill=shadow, anchor=anchor, tags=tags))
    r = 2 if px >= 20 else 1
    for dx, dy in RING:
        ids.append(c.create_text(x + dx * r, y + dy * r, text=text, font=font, fill=outline, anchor=anchor, tags=tags))
    if glint:
        ids.append(c.create_text(x - 1, y - 1, text=text, font=font, fill=glint, anchor=anchor, tags=tags))
    face_id = c.create_text(x, y, text=text, font=font, fill=face, anchor=anchor, tags=tags)
    ids.append(face_id)
    return {"face": face_id, "all": ids, "w": tw(text, px)}


# ---------------------------------------------------------------------------------------------------------------------
# Small pieces the tabs share
# ---------------------------------------------------------------------------------------------------------------------
class BulbRing:
    """Game-show bulbs round a rectangle, three of them chasing.  Stand-alone, so a card or a panel can have its own."""

    def __init__(self, c, rect, theme=None, u=1.0, tags=(), calm_mode=None, clock=None):
        self.c, self.pal = c, palette(theme)
        self.calm = calm() if calm_mode is None else bool(calm_mode)
        self.clock = clock or time.monotonic
        self.t0 = self.clock()
        u = max(0.5, float(u))
        x0, y0, x1, y1 = rect
        r = max(2.0, 3 * u)
        off = mix(self.pal["gold"], self.pal["bg"], 0.70)
        self.ids = [c.create_oval(bx - r, by - r, bx + r, by + r, fill=off, outline=BLACK, tags=tags)
                    for (bx, by) in perimeter(x0, y0, x1, y1, max(12, int(16 * u)))]
        self._step = None
        self.animate(self.t0)

    def animate(self, now=None):
        t = 0.0 if self.calm else (self.clock() if now is None else now) - self.t0
        step = int(t * 4) % 3
        if step == self._step:
            return
        self._step = step
        on, off = self.pal["gold"], mix(self.pal["gold"], self.pal["bg"], 0.70)
        for i, b in enumerate(self.ids):
            self.c.itemconfigure(b, fill=on if i % 3 == step else off)

    def destroy(self):
        for i in self.ids:
            try:
                self.c.delete(i)
            except Exception:
                pass
        self.ids = []


def bevel_box(c, x0, y0, x1, y1, face, depth=2, tags=()):
    """(Grey `paper` for a plain button, gold for the one that matters.)  A chunky raised button face: black outline, a light edge top and left, a dark edge bottom and right.  Returns the ids."""
    hi, lo = mix(face, WHITE, 0.55), mix(face, BLACK, 0.5)
    ids = [c.create_rectangle(x0, y0, x1, y1, fill=face, outline=BLACK, width=2, tags=tags)]
    for d in range(depth):
        ids.append(c.create_line(x0 + 2 + d, y1 - 2 - d, x0 + 2 + d, y0 + 2 + d, x1 - 2 - d, y0 + 2 + d, fill=hi, width=1, tags=tags))
        ids.append(c.create_line(x0 + 3 + d, y1 - 2 - d, x1 - 2 - d, y1 - 2 - d, x1 - 2 - d, y0 + 3 + d, fill=lo, width=1, tags=tags))
    return ids
