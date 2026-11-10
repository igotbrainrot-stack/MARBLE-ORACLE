"""oracle_wire.py -- THE WIRE scene (build 1025): the night city, the train, and nine timed scenes.  Stdlib only; Tk only through the canvas it is given.

Ported from the owner's web version (wire/*.ts, a canvas-2D page): the same skyline, spire, crossing gate, train and timed scenes, the same clock and
the same timings.  Not ported: the captions under the picture (the owner chose to leave them out), the pause and next-scene buttons (no slot in the
host), and the page itself.

    Wire(canvas, box, col, tags)   draws the scene into the panel `box` (the whole panel, title row included, as in the web version) with the host's
                                   theme lookup `col(token)`; everything it makes carries `tags`, so the host's delete("content") clears it
    Wire.update(clock)             moves it to `clock` seconds (any value; the host passes seconds since the program started)

The loop: the train passes DEFAULT_RUNS times (LEAD seconds), then one timed scene plays, then the train again, through CLIP in order, forever.

How it maps onto Tk: the web version repaints the whole canvas every frame.  Here each layer owns a pool of polygon items, created once in paint order
(back to front: sky, city, ground, track, marks + city scenes, train, sky scenes, poles, gate + street), and a frame only moves, recolours, shows or
hides them.  Rectangles, ellipses, arcs and lines all become polygons (a line is a polygon with no fill and an outline), so any slot can take any shape.
Canvas transparency becomes Tk stipple (12 / 25 / 50 / 75 %).  Rotation and scaling are done here, on the points.  Static layers are drawn once;
the city redraws only when a window blinks or the demolished building changes.
"""
import math

import oracle_train as T                 # the train model, the camera and the clipping (shared with the old scene)

S = 2                                    # logical units per panel pixel at the reference size (the web version's density)
W, H = 484 * S, 526 * S                  # the panel, title row included
SY0, SY1, HZ, VX = 263 * S, 452 * S, 395 * S, 174 * S
BOX = (10 * S, SY0, W - 10 * S, SY1)     # the scene: everything is clipped to it
WIN_W, WIN_H = 6 * S, 10 * S

NL, CL, LTOT, V, Z0 = T.NL, T.CL, T.LTOT, T.V, T.Z0
TRAIN_CYCLE, TRAIN_RUN = 11.0, 7.4
POOL_TRAIN = 330

DEFAULT_RUNS = 3
LEAD = DEFAULT_RUNS * TRAIN_CYCLE
CLIP = (                                 # id, duration (s), layer
    ("crane", 22, "city"), ("wash", 11, "city"), ("ship", 13, "sky"), ("cone", 11, "sky"), ("burn", 30, "city"),
    ("cross", 14, "front"), ("pass", 16, "city"), ("hold", 30, "city"), ("lift", 18, "city"),
)
SPANS = []
_acc = 0.0
for _id, _dur, _layer in CLIP:
    SPANS.append((_id, _dur, _layer, _acc, _acc + _dur))
    _acc += _dur + LEAD
LOOP = _acc


class Live:
    __slots__ = ("id", "dur", "layer", "local", "n", "t")

    def __init__(self, sid, dur, layer, local, n, t):
        self.id, self.dur, self.layer, self.local, self.n, self.t = sid, dur, layer, local, n, t


def live_at(t):
    if t < LEAD:
        return None
    u = (t - LEAD) % LOOP
    cycle = int((t - LEAD) // LOOP)
    for i, (sid, dur, layer, a, b) in enumerate(SPANS):
        if a <= u < b:
            return Live(sid, dur, layer, u - a, cycle * len(SPANS) + i, t)
    return None


def clamp01(v):
    return min(1.0, max(0.0, v))


def span(u, a, b):
    return clamp01((u - a) / (b - a))


def ease(t):
    x = clamp01(t)
    return x * x * (3 - 2 * x)


def mix(a, b, t):
    """The web version's mix (rounds; the host's truncates)."""
    ra, ga, ba = int(a[1:3], 16), int(a[3:5], 16), int(a[5:7], 16)
    rb, gb, bb = int(b[1:3], 16), int(b[3:5], 16), int(b[5:7], 16)
    return "#%02x%02x%02x" % (int(round(ra + (rb - ra) * t)), int(round(ga + (gb - ga) * t)), int(round(ba + (bb - ba) * t)))


# ------------------------------------------------------------------------------------------------------------------ skyline
_RAW = ((8, 56, 108), (70, 50, 84), (126, 60, 100), (192, 46, 72), (244, 64, 112), (314, 52, 90), (372, 44, 76))


def _windows(x, y, w, h):
    wins = []
    col_gap, row_gap = 12 * S, 16 * S
    cols = max(1, int((w - 12 * S) // col_gap))
    rows = max(1, int((h - 16 * S) // row_gap))
    for r in range(rows):
        for c in range(cols):
            if (r * 2 + c) % 7 == 0:
                continue
            wx, wy = x + 7 * S + c * col_gap, y + 10 * S + r * row_gap
            if wx + WIN_W > x + w - 3 * S or wy + WIN_H > y + h - 4 * S:
                continue
            wins.append((wx, wy, (r + c) % 3 != 0))
    return wins


class Bldg:
    __slots__ = ("x", "y", "w", "h", "wins")

    def __init__(self, x, w, h):
        self.x, self.w, self.h = x * S, w * S, h * S
        self.y = HZ - self.h
        self.wins = _windows(self.x, self.y, self.w, self.h)


BUILDINGS = [Bldg(*r) for r in _RAW]
SPIRE_X, SPIRE_H = int(W * 0.8), 124 * S
BLINKERS = [i for i in range(sum(len(b.wins) for b in BUILDINGS)) if (i * 13 + 5) % 23 == 0]      # the windows window_on can turn off


def window_on(i, clock, blink):
    pick = (i * 13 + 5) % 23
    if not blink or pick > 0:
        return True
    period = 18 + (i % 5) * 7
    phase = (i % 6) * 4
    return int((clock + phase) // period) % 2 == 0


# ------------------------------------------------------------------------------------------------------------------ painter
_STIPPLE = ((0.88, ""), (0.62, "gray75"), (0.37, "gray50"), (0.18, "gray25"), (0.06, "gray12"))


def _stipple(a):
    for lim, st in _STIPPLE:
        if a >= lim:
            return st
    return None                               # too faint to draw


class Painter:
    """A tiny canvas-2D: save / restore, translate / rotate / scale, an axis-aligned clip, global alpha.  Shapes are recorded as polygon commands in
    screen pixels: (flat points, fill, outline, width, stipple)."""

    def __init__(self, ox, oy, kx, ky):
        self.ox, self.oy, self.kx, self.ky = ox, oy, kx, ky
        self.kw = (kx + ky) / 2.0
        self.m = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
        self.clip = None
        self.alpha = 1.0
        self.stack = []
        self.out = []

    # -- state
    def save(self):
        self.stack.append((self.m, self.clip, self.alpha))

    def restore(self):
        self.m, self.clip, self.alpha = self.stack.pop()

    def translate(self, x, y):
        a, b, c, d, e, f = self.m
        self.m = (a, b, c, d, e + a * x + c * y, f + b * x + d * y)

    def scale(self, sx, sy):
        a, b, c, d, e, f = self.m
        self.m = (a * sx, b * sx, c * sy, d * sy, e, f)

    def rotate(self, r):
        cs, sn = math.cos(r), math.sin(r)
        a, b, c, d, e, f = self.m
        self.m = (a * cs + c * sn, b * cs + d * sn, -a * sn + c * cs, -b * sn + d * cs, e, f)

    def clip_rect(self, x0, y0, x1, y1):
        """Clip to a rectangle given in the CURRENT transform's untransformed space (the web version only clips at identity)."""
        r = (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
        if self.clip:
            r = (max(r[0], self.clip[0]), max(r[1], self.clip[1]), min(r[2], self.clip[2]), min(r[3], self.clip[3]))
        self.clip = r

    # -- helpers
    def _tx(self, pts):
        a, b, c, d, e, f = self.m
        return [(a * x + c * y + e, b * x + d * y + f) for x, y in pts]

    def _lw(self, lw):
        a, b, c, d, _e, _f = self.m
        return lw * math.sqrt(abs(a * d - b * c)) * self.kw

    def _screen(self, pts):
        ox, oy, kx, ky = self.ox, self.oy, self.kx, self.ky
        return [v for x, y in pts for v in (ox + x * kx, oy + y * ky)]

    # -- shapes
    def fill_poly(self, pts, fill, alpha=1.0):
        st = _stipple(self.alpha * alpha)
        if st is None or len(pts) < 3:
            return
        p = self._tx(pts)
        if self.clip:
            p = T.clip_rect(p, *self.clip)
            if len(p) < 3:
                return
        self.out.append((self._screen(p), fill, "", 1, st))

    def fill_rect(self, x, y, w, h, fill, alpha=1.0):
        if w <= 0 or h <= 0:
            return
        self.fill_poly([(x, y), (x + w, y), (x + w, y + h), (x, y + h)], fill, alpha)

    def line(self, pts, color, lw, alpha=1.0, closed=False):
        """A stroked path: a polygon with no fill whose outline is the line (forth and back, so it does not close)."""
        st = _stipple(self.alpha * alpha)
        if st is None or len(pts) < 2:
            return
        p = self._tx(pts)
        if closed:
            p = p + [p[0]]
        width = max(1.0, self._lw(lw))
        runs = []
        if self.clip:
            cur = []
            for i in range(len(p) - 1):
                seg = T._clip_line(p[i], p[i + 1], *self.clip)
                if not seg:
                    if len(cur) >= 2:
                        runs.append(cur)
                    cur = []
                    continue
                if cur and abs(cur[-1][0] - seg[0][0]) < 1e-6 and abs(cur[-1][1] - seg[0][1]) < 1e-6:
                    cur.append(seg[1])
                else:
                    if len(cur) >= 2:
                        runs.append(cur)
                    cur = [seg[0], seg[1]]
            if len(cur) >= 2:
                runs.append(cur)
        else:
            runs = [p]
        for r in runs:
            path = r + r[-2:0:-1] if len(r) > 2 else [r[0], r[1], r[0]]
            self.out.append((self._screen(path), "", color, width, st))

    def stroke_rect(self, x, y, w, h, color, lw, alpha=1.0):
        self.line([(x, y), (x + w, y), (x + w, y + h), (x, y + h)], color, lw, alpha, closed=True)

    @staticmethod
    def arc_pts(cx, cy, rx, ry, a0, a1, n=None):
        n = n or max(10, min(40, int(abs(a1 - a0) * max(rx, ry) / (3.0 * S)) + 6))
        return [(cx + rx * math.cos(a0 + (a1 - a0) * i / n), cy + ry * math.sin(a0 + (a1 - a0) * i / n)) for i in range(n + 1)]

    def fill_ellipse(self, cx, cy, rx, ry, fill, alpha=1.0):
        if rx <= 0 or ry <= 0:
            return
        self.fill_poly(self.arc_pts(cx, cy, rx, ry, 0, 2 * math.pi)[:-1], fill, alpha)

    def fill_circle(self, cx, cy, r, fill, alpha=1.0):
        self.fill_ellipse(cx, cy, r, r, fill, alpha)


# ------------------------------------------------------------------------------------------------------------------ layers
class Layer:
    """A pool of polygon items, in paint order.  draw(cmds) puts command i on item i, touching Tk only where something changed, and hides the rest.
    A frame that needs more items than the pool holds grows it once; the new items are slid under this layer's top marker, so the stacking holds."""

    def __init__(self, canvas, tags, size):
        self.c, self.tags = canvas, tags
        self.slots = [self._make() for _ in range(size)]
        self.top = canvas.create_polygon(0, 0, 0, 0, 0, 0, fill="", outline="", state="hidden", tags=tags)     # marks where this layer ends
        self.shown = 0
        self.key = object()
        self.grown = 0

    def _make(self):
        it = self.c.create_polygon(0, 0, 0, 0, 0, 0, fill="", outline="", state="hidden", joinstyle="round", tags=self.tags)
        return [it, None, None]                    # item, coords, style

    def draw(self, cmds):
        c, slots = self.c, self.slots
        while len(slots) < len(cmds):
            s = self._make()
            c.tag_lower(s[0], self.top)
            slots.append(s)
            self.grown += 1
        for i, (pts, fill, outline, width, st) in enumerate(cmds):
            s = slots[i]
            co = tuple(int(round(v)) for v in pts)
            if co != s[1]:
                c.coords(s[0], *co)
                s[1] = co
            style = (fill, outline, int(round(width)), st)
            if style != s[2] or i >= self.shown:
                c.itemconfigure(s[0], fill=fill, outline=outline, width=style[2], stipple=st, state="normal")
                s[2] = style
        for i in range(len(cmds), self.shown):
            c.itemconfigure(slots[i][0], state="hidden")
        self.shown = len(cmds)


# ------------------------------------------------------------------------------------------------------------------ the scene
class Wire:
    # Pool sizes: the peak each layer reached over a whole loop at 10 fps (build 1025: city 248 + 45, under 48, train 189, sky 15, front 47), plus room.
    # Static layers start empty and grow once, at build.  A frame that needs more grows the pool (Layer.draw); it never needs to.
    SIZES = dict(back=0, city=300, city0=80, ground=0, track=0, under=64, train=POOL_TRAIN + 2, sky=24, poles=0, front=64)

    def __init__(self, canvas, box, col, tags=("content", "train")):
        self.c, self.tags = canvas, tuple(tags)
        x0, y0, x1, y1 = box
        self.kx, self.ky = (x1 - x0) / float(W), (y1 - y0) / float(H)
        self.ox, self.oy = x0, y0
        self.C = dict(PANEL=col("panel"), MAG=col("mag"), CYAN=col("cyan"), GOLD=col("gold"), EDGE=col("edge"), RED=col("red"), SUN=col("sun1"),
                      DIM=col("dim"), TXT=col("txt"), ORANGE=col("orange"))
        self.C["FOG"] = mix(self.C["PANEL"], self.C["MAG"], 0.35)
        self.C["GROUND"] = self.C["PANEL"]
        self.rig = T.Rig(HZ, VX, SY1, 14.0)
        self.parts = T._model()
        self.cols = {}
        self.layers = {name: Layer(canvas, self.tags, n) for name, n in self.SIZES.items()}     # created in paint order: the dict keeps it
        L = self.layers
        L["back"].draw(self._paint(self._back))
        L["ground"].draw(self._paint(self._ground))
        L["track"].draw(self._paint(self._track))
        L["poles"].draw(self._paint(self._poles))
        self.clock = None
        self.update(0.0)

    # -- plumbing
    def _paint(self, fn, *a):
        p = Painter(self.ox, self.oy, self.kx, self.ky)
        fn(p, *a)
        return p.out

    def update(self, clock):
        """Move everything to `clock` seconds."""
        self.clock = clock
        live = live_at(clock)
        L = self.layers
        cut = building_cut(live)
        blink = live is not None
        lit = tuple(window_on(i, clock, blink) for i in BLINKERS) if blink else ()
        gone = bool(cut and cut[1] <= 0.01)                       # building 0 fully down: the web version stops counting its windows
        for name, which, key in (("city", range(1, len(BUILDINGS)), (gone, lit)), ("city0", (0,), (cut, lit))):
            if key != L[name].key:                                # the demolished building is its own layer: only it redraws while it moves
                L[name].key = key
                L[name].draw(self._paint(self._city, cut, clock, blink, which))
        L["under"].draw(self._paint(self._under, live))
        L["train"].draw(self._paint(self._train_frame, live, clock))
        L["sky"].draw(self._paint(self._sky, live))
        L["front"].draw(self._paint(self._front, live, clock))
        return live

    # -- static: sky bands, sun, mountain
    def _back(self, p):
        C = self.C
        hz, sy0, pw = HZ, SY0, W
        cx = int(pw / 2)
        R = int(min(pw * 0.26, (hz - sy0) * 0.85))
        band = mix(C["PANEL"], C["MAG"], 0.55)
        stip = (0.12, 0.12, 0.25, 0.5, 0.75)
        nb = 5
        for j in range(nb):
            ya, yb = sy0 + (hz - sy0) * j / nb, sy0 + (hz - sy0) * (j + 1) / nb
            p.fill_rect(10 * S, ya, W - 20 * S, yb - ya + 1, mix(C["PANEL"], band, stip[j]))
        half = [(cx, hz)] + Painter.arc_pts(cx, hz, R, R, math.pi, 2 * math.pi, 48)
        p.fill_poly(half, C["SUN"])
        for j in range(1, 6):                                   # the stripes, cut to the half disc
            yy = hz - R + int(R * (0.45 + 0.1 * j))
            if yy < hz:
                band_pts = T.clip_rect(half, cx - R, yy, cx + R, yy + max(S, j * S))
                if len(band_pts) >= 3:
                    p.fill_poly(band_pts, C["PANEL"])
        p.line(Painter.arc_pts(cx, hz, R, R, math.pi, 2 * math.pi, 48), C["MAG"], 2 * S)
        fx, fh, fw = 10 * S + int(pw * 0.22), (hz - sy0) * 0.92, pw * 0.34
        step = 4
        left, right = [], []
        yy = hz
        while yy > hz - fh:
            t = (hz - yy) / fh
            hw = fw * (1 - t ** 0.62) if t < 1 else 0
            left.append((fx - hw, yy))
            right.append((fx + hw, yy))
            yy -= step
        body = []
        for lx, ly in left:
            body += [(max(10 * S, lx), ly), (max(10 * S, lx), ly - step)]
        for rx, ry in reversed(right):
            body += [(min(W - 10 * S, rx), ry - step), (min(W - 10 * S, rx), ry)]
        p.fill_poly(body, mix(C["PANEL"], "#7a4fd0", 0.55))
        cap_n = max(2, int(len(left) * 0.24))
        cap = []
        for lx, ly in left[-cap_n:]:
            jog = step if int(ly / step) % 2 else 0
            cap += [(lx + jog + 2, ly), (lx + jog + 2, ly - step)]
        for i in range(cap_n - 1, -1, -1):
            rx, ry = right[len(right) - cap_n + i]
            jog = step if int(ry / step) % 2 else 0
            cap += [(rx - jog - 2, ry - step), (rx - jog - 2, ry)]
        if len(cap) >= 3:
            p.fill_poly(cap, mix("#ffd6f2", C["MAG"], 0.25))

    # -- the city: redrawn only when a blinking window or the demolished building changes
    def _city(self, p, cut, clock, blink, which):
        C = self.C
        wi = 0
        for i, b in enumerate(BUILDINGS):
            if i not in which:                                    # not drawn by this layer, but its windows still count toward the blink index
                if not (cut and cut[0] == i and cut[1] <= 0.01):
                    wi += len(b.wins)
                continue
            top, h = b.y, b.h
            if cut and cut[0] == i:
                if cut[1] <= 0.01:
                    continue                                     # (the web version skips its windows without counting them; kept)
                h = b.h * cut[1]
                top = b.y + b.h - h
            whole = top <= b.y + S
            crown = whole and b.h >= 100 * S
            p.fill_rect(b.x, top, b.w, h, "#0c101c")
            p.fill_rect(b.x, top, 3 * S, h, "#1a2744")
            if whole:
                p.fill_rect(b.x - 2 * S, b.y, b.w + 4 * S, 5 * S, "#24304c")
                p.fill_rect(b.x, b.y + 5 * S, b.w, 3 * S, "#12182a")
            if crown:
                sw = int(b.w * 0.5)
                sx = b.x + int((b.w - sw) / 2)
                p.fill_rect(sx, b.y - 14 * S, sw, 14 * S, "#101624")
                p.fill_rect(sx - S, b.y - 14 * S, sw + 2 * S, 3 * S, "#2a3858")
                p.fill_rect(sx + 3 * S, b.y - 10 * S, 3 * S, 4 * S, C["GOLD"])
            elif whole and b.w >= 50 * S:
                p.fill_rect(b.x + b.w - 16 * S, b.y - 9 * S, 12 * S, 9 * S, "#1a2236")
                p.stroke_rect(b.x + b.w - 16 * S + 0.5, b.y - 9 * S + 0.5, 12 * S - 1, 9 * S - 1, C["EDGE"], S)
                p.fill_rect(b.x + b.w - 13 * S, b.y - 12 * S, 2 * S, 4 * S, "#8ea9c4")
            for wx, wy, gold in b.wins:
                if wy < top:
                    wi += 1
                    continue
                on = window_on(wi, clock, blink)
                wi += 1
                p.fill_rect(wx - S, wy - S, WIN_W + 2 * S, WIN_H + 2 * S, "#070910")
                p.fill_rect(wx, wy, WIN_W, WIN_H, (C["GOLD"] if gold else C["CYAN"]) if on else "#070910")   # off = the frame's own black: same picture, same item count
                p.fill_rect(wx + int(WIN_W / 2) - S / 2.0, wy, S, WIN_H, "#070910")
            p.stroke_rect(b.x + 0.5, top + 0.5, b.w - 1, h - 1, C["EDGE"], S)

    # -- static: spire, ground, horizon, grid, the street
    def _ground(self, p):
        C = self.C
        hz, tx, th, tw = HZ, SPIRE_X, SPIRE_H, 9 * S
        spire = [(tx - tw, hz), (tx - tw * 0.85, hz - th * 0.38), (tx - tw * 0.4, hz - th * 0.62), (tx - tw * 0.15, hz - th * 0.86), (tx, hz - th),
                 (tx + tw * 0.15, hz - th * 0.86), (tx + tw * 0.4, hz - th * 0.62), (tx + tw * 0.85, hz - th * 0.38), (tx + tw, hz)]
        p.fill_poly(spire, "#0b0e1c")
        p.line(spire, C["EDGE"], S, closed=True)
        p.fill_rect(tx - 5 * S, hz - th * 0.42, 10 * S, 3 * S, "#2a3858")
        p.fill_rect(tx - 3 * S, hz - th * 0.68, 6 * S, 2 * S, "#2a3858")
        p.fill_circle(tx, hz - th, 3 * S, "#ff4d5e")
        p.fill_rect(10 * S, hz, W - 20 * S, SY1 - hz, C["PANEL"])
        p.line([(10 * S, hz), (W - 10 * S, hz)], C["MAG"], 2 * S)
        for j in range(1, 5):
            gy = hz + (SY1 - hz) * (j / 4.0) ** 2
            p.line([(10 * S, gy), (W - 10 * S, gy)], C["EDGE"], S)
        p.fill_rect(12 * S, hz + 7 * S, 136 * S, 7 * S, "#141b30")
        p.fill_rect(12 * S, hz + 7 * S, 136 * S, 2 * S, C["MAG"])

    # -- static: ballast, sleepers, rails (the old scene's track, at this density)
    def _track(self, p):
        r, C = self.rig, self.C
        x0, y0, x1, y1 = BOX
        C0, zn, zfar = r.C0, 14.0, 2500.0
        P = lambda X, Z: r.proj(X, 0.0, Z)
        ball = T.clip_rect([P(C0 - 2.3, zn), P(C0 + 2.3, zn), P(C0 + 2.3, zfar), P(C0 - 2.3, zfar)], x0, y0, x1, y1)
        if len(ball) >= 3:
            p.fill_poly(ball, mix(C["GROUND"], "#6b78b4", 0.62))
        last, z = 1e9, zn
        sleeper = mix(C["GROUND"], "#d9b4f0", 0.78)
        while z < 900.0:
            a, b = P(C0 - 1.6, z), P(C0 + 1.6, z)
            if last - a[1] >= 2.4 * S and y0 <= a[1] <= y1:
                xa, xb = max(a[0], x0), min(b[0], x1)
                if xb > xa:
                    p.line([(xa, a[1]), (xb, a[1])], sleeper, max(S, int(4 * S * zn / z + 0.7)))
                last = a[1]
            elif last > 1e8:
                last = a[1] + 3
            z += 0.65
        for sg in (-1, 1):
            for off, colr, wd in ((sg * 0.717, "#8fa0e8", 3 * S), (sg * 0.717 - sg * 0.03, "#f2f6ff", S)):
                seg = T._clip_line(P(C0 + off, zn), P(C0 + off, zfar), x0, y0, x1, y1)
                if seg:
                    p.line([seg[0], seg[1]], colr, wd)

    # -- static: telegraph poles (above the train and the sky scenes)
    def _poles(self, p):
        r = self.rig
        x0, y0, x1, y1 = BOX
        colr = mix("#2a2148", self.C["FOG"], 0.15)
        px, z = r.C0 - 4.6, 15.0
        while z < 520.0:
            k = r.f / z
            cx = r.vx + px * k
            w = max(1.0, 0.24 * k)
            top, bot = r.hz - (7.6 - r.H) * k, r.hz + r.H * k
            if x0 < cx < x1 and bot > y0 and top < y1:
                ya, yb = max(y0, top), min(y1, bot)
                p.fill_rect(cx - w / 2, ya, w, yb - ya, colr)
                for hy, ln in ((7.1, 1.5), (6.2, 1.1)):
                    ay = r.hz - (hy - r.H) * k
                    if y0 < ay < y1:
                        xa, xb = max(x0, cx - ln * k), min(x1, cx + ln * k)
                        p.fill_rect(xa, ay, xb - xa, max(1.0, 0.16 * k), colr)
            z *= 1.32

    # -- per frame
    def _under(self, p, live):
        if live is None:
            return
        draw_marks(self, p, live)
        if live.layer == "city":
            p.save()
            p.clip_rect(*BOX)
            CITY[live.id](self, p, live)
            p.restore()

    def _sky(self, p, live):
        if live is None or not (live.layer == "sky" or live.id == "hold"):
            return
        p.save()
        p.clip_rect(*BOX)
        if live.id == "ship":
            draw_ship(self, p, live)
        elif live.id == "cone":
            draw_cone(self, p, live)
        elif live.id == "hold":
            draw_hold_heli(self, p, live)
        p.restore()

    def _front(self, p, live, clock):
        p.save()
        p.clip_rect(*BOX)
        u = live.local / live.dur if (live and live.id == "cross") else -1
        draw_gate(self, p, u, gate_drop(active_train_z(live, clock)))
        p.restore()
        if live is not None:
            p.save()
            p.clip_rect(*BOX)
            draw_street(self, p, live)
            p.restore()

    def _train_frame(self, p, live, clock):
        hit = inbound_train_z(live)
        ph = clock % TRAIN_CYCLE
        if hit is not None:
            self._train(p, hit, 0.0)
        elif (live is None or live.id != "cross") and ph < TRAIN_RUN:
            zf = Z0 - V * ph
            amp = min(2.0 * S, (0.6 + (120 - zf) / 60.0) * S) if zf < 120 else 0.0
            s = math.sin(clock * 9)
            jy = ((1 if s > 0.45 else -1 if s < -0.45 else 0) * amp) if amp else 0.0
            self._train(p, zf, jy)

    def _color(self, key, z):
        b = int(min(15, max(0.0, z / 40.0)))
        k = (key, b)
        v = self.cols.get(k)
        if v is None:
            v = mix(T.BASE[key], self.C["FOG"], min(0.75, (b / 15.0) ** 1.3 * 0.8))
            self.cols[k] = v
        return v

    def _train(self, p, zf, jy):
        """drawTrain: the old Train3D.update loop, emitting into the painter (same model, camera, haze, clipping and pool cap)."""
        r = self.rig
        x0, y0, x1, y1 = BOX
        C0, f, vx, hz, Hc = r.C0, r.f, r.vx, r.hz, r.H
        near = lambda car: zf + NL + car * CL < 75.0
        used = 0
        ZC = T.ZCLIP
        for pt in self.parts:
            if pt.lod and not near(pt.car):
                continue
            if pt.car >= 0 and not pt.lod and near(pt.car) and pt.key == "win":
                continue
            if zf + pt.v[0][2] > Z0 + LTOT:
                continue
            if pt.n is not None:
                v0 = pt.v[0]
                nx, ny, nz = pt.n
                if nx * (0 - (C0 + v0[0])) + ny * (Hc - v0[1]) + nz * (0 - (zf + v0[2])) <= 0:
                    continue
            p3 = [(C0 + v[0], v[1], zf + v[2]) for v in pt.v]
            zmin = min(q[2] for q in p3)
            zmax = max(q[2] for q in p3)
            if zmax < ZC:
                continue
            if zmin < ZC:
                p3 = T.clip_near(p3)
                if len(p3) < 3:
                    continue
            s2 = [(vx + X * f / Z, hz - (Y - Hc) * f / Z + jy) for X, Y, Z in p3]
            xs = [q[0] for q in s2]
            if max(xs) < x0 or min(xs) > x1:
                continue
            s2 = T.clip_rect(s2, x0, y0, x1, y1)
            if len(s2) < 3:
                continue
            zc = (zmin + zmax) * 0.5
            ys = [q[1] for q in s2]
            fill = self._color(pt.key, zc)
            p.fill_poly(s2, fill, 0.45 if pt.stipple else 1.0)
            if pt.outline and max(ys) - min(ys) > 7:
                p.line(s2, self._color("line", zc), S, closed=True)
            used += 1
            if used >= POOL_TRAIN:
                break
        for sg in (-1, 1):                                          # the lamps: a soft halo, then the lamp
            X, Y, Z = C0 + sg * 0.32, 1.12, zf - 0.03
            if Z < ZC:
                continue
            k = f / Z
            px, py = vx + X * k, hz - (Y - Hc) * k + jy
            rr = max(1.4, 0.16 * k)
            if px <= x0 or px >= x1 or py <= y0 or py >= y1:
                continue
            p.fill_circle(px, py, rr * 2.6, T.BASE["glow"], 0.35)
            p.fill_circle(px, py, rr, T.BASE["lamp"])


# ------------------------------------------------------------------------------------------------------------------ the timed scenes (events.ts)
def street_y():
    return HZ + 6 * S


def rail_spot(w):
    r = w.rig
    return r.proj(r.C0, 0.05, 32.0)


def inbound_train_z(live):
    """CROSS: a train at the same speed as the regular one, timed to reach the crossing at 46 % of the scene."""
    if live is None or live.id != "cross":
        return None
    hit_at = 0.46 * live.dur
    z = 32 - V * (live.local - hit_at)
    z_end = Z0 - V * TRAIN_RUN
    if z > Z0 or z < z_end:
        return None
    return z


def active_train_z(live, clock):
    hit = inbound_train_z(live)
    if hit is not None:
        return hit
    if live is not None and live.id == "cross":
        return None
    ph = clock % TRAIN_CYCLE
    if ph >= TRAIN_RUN:
        return None
    return Z0 - V * ph


def gate_drop(z):
    if z is None:
        return 0.0
    close = ease(clamp01((240 - z) / 80.0))
    clear = ease(clamp01((36 - (z + LTOT)) / 44.0))
    return close * (1 - clear)


def building_cut(live):
    """LIFT: (building index, how much of it stands).  Five blasts down, then the frame goes back up."""
    if live is None or live.id != "lift":
        return None
    u = live.local / live.dur
    if u < 0.02:
        return (0, 1.0)
    if u < 0.34:
        i = min(5, int(span(u, 0.02, 0.34) * 5) + 1)
        return (0, 1 - i / 5.0)
    if u < 0.42:
        return (0, 0.0)
    if u < 0.68:
        return (0, span(u, 0.42, 0.68))
    return (0, 1.0)


def train_in_the_way(t):
    ph = t % TRAIN_CYCLE
    if ph >= TRAIN_RUN:
        return False
    z = Z0 - V * ph
    return z < 180 and z + LTOT > 10


def leave_when_clear(live, ready_u):
    ready_at = live.t - live.local + ready_u * live.dur
    leave_at = ready_at
    if train_in_the_way(ready_at):
        ph_end = min(TRAIN_RUN, (Z0 + LTOT - 10) / V)
        ph = ready_at % TRAIN_CYCLE
        cycle = ready_at - ph
        leave_at = cycle + ph_end
        if leave_at < ready_at:
            leave_at = cycle + TRAIN_CYCLE + ph_end
    if live.t < leave_at:
        return 0.0
    return ease(min(1.0, (live.t - leave_at) / 2.2))


def ambulance_leave(live):
    parked_at = live.t - live.local + 0.36 * live.dur
    ph = parked_at % TRAIN_CYCLE
    cycle = parked_at - ph
    leave_at = cycle + TRAIN_RUN if ph < TRAIN_RUN else cycle + TRAIN_CYCLE + TRAIN_RUN
    if live.t < leave_at:
        return 0.0
    return ease(min(1.0, (live.t - leave_at) / 2.4))


def fallen_pane(b):
    mid = [wn for wn in b.wins if b.y + b.h * 0.3 < wn[1] < b.y + b.h * 0.72]
    return mid[len(mid) // 2] if mid else b.wins[0]


def figure(p, x, feet, s, coat, step, arm, skin="#f4f7fb", hair="", skull=True):
    k = s * S
    p.fill_rect(x - 4 * k, feet - S, 8 * k, 2 * S, "#05030f")
    leg = math.sin(step) * 2.4 * k
    p.fill_rect(x - 2.3 * k + leg, feet - 9 * k, 2 * k, 9 * k, coat)
    p.fill_rect(x + 0.4 * k - leg, feet - 9 * k, 2 * k, 9 * k, coat)
    p.fill_rect(x - 2.8 * k, feet - 19 * k, 5.6 * k, 11 * k, coat)
    if skull:
        if hair:
            p.fill_poly(Painter.arc_pts(x, feet - 22 * k, 3.1 * k, 3.1 * k, math.pi * 1.05, math.pi * 1.95, 12), hair)
        p.fill_circle(x, feet - 21.4 * k, 2.7 * k, skin)
    p.save()
    p.translate(x + 1.4 * k, feet - 16 * k)
    p.rotate(arm)
    p.fill_rect(0, -0.9 * k, 7 * k, 1.8 * k, coat)
    p.restore()


def glass_pane(w, p, x, y, rot):
    p.save()
    p.translate(x, y)
    p.rotate(rot)
    p.fill_rect(-WIN_W / 2.0 - S, -WIN_H / 2.0 - S, WIN_W + 2 * S, WIN_H + 2 * S, "#070910")
    p.fill_rect(-WIN_W / 2.0, -WIN_H / 2.0, WIN_W, WIN_H, w.C["CYAN"])
    p.fill_rect(-WIN_W / 2.0, -WIN_H / 2.0, S, WIN_H * 0.45, "#e7eef8")
    p.restore()


def stain(w, p, x, y, rx, ry, a):
    if a <= 0.01:
        return
    p.fill_ellipse(x, y, rx, ry, "#6e0c18", a)
    p.fill_ellipse(x - rx * 0.12, y, rx * 0.58, ry * 0.5, w.C["RED"], a)


def wheel(p, x, y):
    p.fill_circle(x, y, 0.85 * S, "#0b0d14")
    p.fill_circle(x, y, 0.35 * S, "#c3d6e6")


def draw_ambulance(w, p, x, y, lamp=0.0):
    C = w.C
    p.fill_rect(x, y - 3.2 * S, 14 * S, 3.2 * S, "#e7eef8")
    p.fill_rect(x + 9 * S, y - 4.4 * S, 4 * S, 1.6 * S, "#d5deea")
    p.fill_rect(x, y - 2 * S, 14 * S, S, C["RED"])
    p.fill_rect(x + 6 * S, y - 3.2 * S, S, 2.2 * S, C["RED"])
    p.fill_rect(x + 5 * S, y - 2.4 * S, 3 * S, S, C["RED"])
    p.fill_rect(x + 9.5 * S, y - 4 * S, 2.5 * S, S, "#1b2262")
    p.fill_rect(x + 2 * S, y - 5.4 * S, 2.2 * S, 1.2 * S, C["RED"] if lamp > 0 else C["CYAN"])
    p.fill_rect(x + 4.6 * S, y - 5.4 * S, 2.2 * S, 1.2 * S, C["CYAN"] if lamp > 0 else C["RED"])
    wheel(p, x + 3 * S, y)
    wheel(p, x + 11 * S, y)


def draw_fire_truck(w, p, x, y, lamp=0.0):
    C = w.C
    p.fill_rect(x, y - 3.4 * S, 18 * S, 3.4 * S, "#b4232e")
    p.fill_rect(x + 12 * S, y - 4.6 * S, 5 * S, 1.8 * S, "#e7eef8")
    p.fill_rect(x + 13 * S, y - 4.2 * S, 3 * S, S, "#1b2262")
    p.fill_rect(x + 2 * S, y - 4.2 * S, 6 * S, S, "#f4f7fb")
    p.fill_rect(x + 13 * S, y - 5.6 * S, 1.8 * S, 1.2 * S, C["RED"] if lamp > 0 else C["CYAN"])
    p.fill_rect(x + 15.2 * S, y - 5.6 * S, 1.8 * S, 1.2 * S, C["CYAN"] if lamp > 0 else C["RED"])
    p.fill_rect(x + S, y - 1.6 * S, 2.5 * S, S, C["GOLD"])
    wheel(p, x + 3.5 * S, y)
    wheel(p, x + 9 * S, y)
    wheel(p, x + 14.5 * S, y)


def draw_police(w, p, x, y, lamp):
    C = w.C
    p.fill_rect(x, y - 3 * S, 12 * S, 3 * S, "#12182c")
    p.fill_rect(x + 5 * S, y - 4.2 * S, 4 * S, 1.6 * S, "#1a2744")
    p.fill_rect(x + 4.6 * S, y - 4.8 * S, 1.6 * S, S, C["RED"] if lamp > 0 else C["CYAN"])
    p.fill_rect(x + 6.6 * S, y - 4.8 * S, 1.6 * S, S, C["CYAN"] if lamp > 0 else C["RED"])
    p.fill_rect(x + 5.6 * S, y - 3.6 * S, 2.2 * S, S, "#8ea9c4")
    wheel(p, x + 2.5 * S, y)
    wheel(p, x + 9.5 * S, y)


def place_vehicle(p, x, y, draw):
    p.save()
    p.translate(x, y)
    p.scale(3, 3)
    p.translate(-x, -y)
    draw()
    p.restore()


def draw_crane_rig(w, p, x, y, mast_px, jib, cable, reach=None, dip=0.0):
    C = w.C
    if reach is None:
        reach = (10 + jib * 52) * S
    if mast_px < 1:
        return
    d = -1 if reach < 0 else 1
    p.fill_rect(x - 2 * S, y - mast_px, 5 * S, mast_px, "#9aabbf")
    if mast_px > 24 * S:
        p.fill_rect(x - 8 * S, y - mast_px - 4 * S, 16 * S, 10 * S, "#2a3148")
        p.fill_rect(x - 5 * S, y - mast_px - S, 5 * S, 4 * S, C["GOLD"])
    if jib > 0.02:
        p.line([(x, y - mast_px), (x + reach, y - mast_px + 2 * S + dip)], "#d5deea", 2 * S)
        p.line([(x, y - mast_px), (x - d * 16 * S * jib, y - mast_px + 4 * S)], "#d5deea", 2 * S)
        p.fill_rect(x - d * 22 * S * jib, y - mast_px - 2 * S, 8 * S, 8 * S, "#3f4860")
        if jib > 0.85 and cable > 2 * S:
            hx, hy = x + reach - d * 2 * S, y - mast_px + 2 * S + dip
            p.line([(hx, hy), (hx, hy + cable)], C["CYAN"], S)
            p.fill_rect(hx - 4 * S, hy + cable, 8 * S, 4 * S, C["ORANGE"])


def draw_crane(w, p, live):
    b = BUILDINGS[1]
    wx, wy, _g = fallen_pane(b)
    u = live.local / live.dur
    ground = street_y()
    fall = 0.0 if u < 0.06 else ease(span(u, 0.06, 0.2))
    px, py = wx + WIN_W / 2.0, wy + WIN_H / 2.0
    seat = ease(span(u, 0.48, 0.64))
    gone = ambulance_leave(live) > 0.04
    if u > 0.06 and seat < 1:
        p.fill_rect(wx - S, wy - S, WIN_W + 2 * S, WIN_H + 2 * S, "#0c101c")
        p.stroke_rect(wx + 0.5, wy + 0.5, WIN_W - 1, WIN_H - 1, "#24304c", S)
    if u > 0.06 and not gone:
        gy = ground - 2 * S if fall >= 1 else py + fall * fall * (ground - py)
        glass_pane(w, p, px, gy, fall * 1.15)
    walk = ease(span(u, 0, 0.16))
    mx = b.x - 8 * S + walk * (px - (b.x - 8 * S))
    squash = ease(span(fall, 0.72, 1))
    if u < 0.46:
        p.save()
        p.translate(px if fall >= 1 else mx, ground)
        p.scale(1 + squash * 0.7, max(0.16, 1 - squash * 0.84))
        figure(p, 0, 0, 0.84, "#d7c4a8", 0 if fall >= 1 else live.local * 10, 0.25, "#8d5a3c", "" if fall >= 1 else "#1a120c")
        p.restore()
    mast = ease(span(u, 0.28, 0.4)) if u < 0.72 else 1 - ease(span(u, 0.78, 0.94))
    jib = ease(span(u, 0.36, 0.46)) if u < 0.7 else 1 - ease(span(u, 0.76, 0.9))
    crane_x = b.x + 6 * S
    reach = max(18 * S, px - crane_x)
    mast_px = 36 * S * mast
    cab = b.y - mast_px
    retract = ease(span(u, 0.66, 0.76))
    holding = jib > 0.85 and seat < 1 and u < 0.66
    if holding:
        cable = max(6 * S, (cab + 8 * S + seat * (py - cab - 8 * S)) - cab)
    elif jib > 0.85 and retract < 1 and u >= 0.64:
        cable = (1 - retract) * max(6 * S, py - cab)
    else:
        cable = 0
    draw_crane_rig(w, p, crane_x, b.y, mast_px, jib, cable, reach)
    if holding and cable > 2 * S:
        glass_pane(w, p, crane_x + reach, cab + cable, (1 - seat) * 0.35)


def draw_wash(w, p, live):
    C = w.C
    b = BUILDINGS[0]
    u = live.local / live.dur
    rig = ease(span(u, 0.02, 0.14)) if u < 0.82 else 1 - ease(span(u, 0.86, 0.98))
    down = ease(span(u, 0.16, 0.4))
    up = ease(span(u, 0.58, 0.82))
    travel = down * (1 - up)
    if rig < 0.02:
        return
    top = b.y + 8 * S
    y = top + travel * (b.h - 56 * S)
    drop = (y - b.y) * rig
    p.line([(b.x + 12 * S, b.y + 4 * S), (b.x + 12 * S, b.y + 4 * S + drop)], "#8ea9c4", S)
    p.line([(b.x + b.w - 12 * S, b.y + 4 * S), (b.x + b.w - 12 * S, b.y + 4 * S + drop)], "#8ea9c4", S)
    py = b.y + 4 * S + drop
    p.fill_rect(b.x + 8 * S, py, b.w - 16 * S, 4 * S, "#d5deea")
    p.fill_rect(b.x + 10 * S, py - 8 * S, b.w - 20 * S, 8 * S, "#3f4860")
    p.fill_rect(b.x + 12 * S, py - 6 * S, 4 * S, 3 * S, C["CYAN"])
    if rig > 0.45:
        walking = (0.16 < u < 0.42) or (0.58 < u < 0.82)
        figure(p, b.x + b.w * 0.62, py, 0.72, "#e7eef8", live.local * 8 if walking else 0, 0.8 if 0.42 < u < 0.58 else 0.15)


def flame(w, p, x, base, h, lean):
    C = w.C
    for colr, k in ((C["RED"], 1.0), (C["ORANGE"], 0.72), (C["GOLD"], 0.46), ("#fff6d0", 0.22)):
        p.fill_poly([(x - (3 + k * 5) * S, base), (x + lean * k, base - h * k), (x + (3 + k * 5) * S, base)], colr)


def draw_burn(w, p, live):
    b = BUILDINGS[2]
    u = live.local / live.dur
    grow = ease(span(u, 0.05, 0.5))
    spray = ease(span(u, 0.64, 0.86))
    life = grow * (1 - spray)
    if life <= 0.01:
        return
    for i in range(6):
        local = clamp01(life * 1.4 - i * 0.1)
        if local <= 0:
            continue
        x = b.x + (i + 0.5) * b.w / 6.0
        h = (20 + (i % 3) * 14) * S * local
        lean = math.sin(live.local * 6 + i * 1.3) * 4 * S
        flame(w, p, x, b.y + S, h, lean)
    a = 0.25 + life * 0.3
    for i in range(3):
        q = (u * 0.55 + i * 0.28) % 1
        p.fill_ellipse(b.x + b.w * 0.3 + q * b.w * 0.55, b.y - (18 + q * 26 + i * 8) * S, (10 + q * 10) * S, 5 * S, "#d9b4f0", a)


def emerge(w, p, b, x, k, coat, step, arm):
    feet = b.y + S + (1 - k) * 20.8 * S
    p.save()
    if k < 0.98:
        p.clip_rect(b.x - 4 * S, SY0, b.x + b.w + 4 * S, SY0 + max(0, b.y - SY0))
    figure(p, x, feet, 0.84, coat, step, arm)
    p.restore()


def draw_pass(w, p, live):
    C = w.C
    b = BUILDINGS[3]
    u = live.local / live.dur
    if u > 0.58:
        return
    c1, c2 = ease(span(u, 0, 0.18)), ease(span(u, 0.08, 0.26))
    walk = ease(span(u, 0.26, 0.42))
    fall = span(u, 0.46, 0.58)
    hx1, hx2 = b.x + b.w * 0.3, b.x + b.w * 0.7
    x1 = hx1 + walk * (b.x + b.w * 0.55 - hx1)
    x2 = hx2 + walk * (b.x + b.w * 0.28 - hx2)
    drop = fall * fall * (street_y() - b.y)
    if fall > 0:
        figure(p, x1, b.y + S + drop, 0.84, "#e7eef8", 0, 1.15)
        figure(p, x2, b.y + S + drop, 0.84, C["ORANGE"], 0, 1.15)
        return
    stepping = 0 < walk < 1
    emerge(w, p, b, x1, max(c1, walk), "#e7eef8", live.local * 8 if stepping else 0, 0.2)
    if u > 0.08:
        emerge(w, p, b, x2, max(c2, walk), C["ORANGE"], live.local * 8 + 1 if stepping else 0, 0.15)


def head_burst(w, p, x, y, t):
    q = clamp01(t)
    p.fill_circle(x, y, (2 + q * 4) * S, "#fff6d0", 1 - q)
    for i in range(7):
        a = i / 7.0 * math.pi * 2 + q
        d = (3 + q * 10) * S
        p.fill_circle(x + math.cos(a) * d, y + math.sin(a) * d * 0.65, (1.4 + (1 - q)) * S, w.C["RED"], 1 - q)


def draw_hold(w, p, live):
    b = BUILDINGS[1]
    u = live.local / live.dur
    c1, c2 = ease(span(u, 0, 0.2)), ease(span(u, 0.1, 0.3))
    xh, xc = b.x + b.w * 0.32, b.x + b.w * 0.68
    shot_h, shot_c = 0.48, 0.56

    def body(x, coat, arm, at, up):
        if u < at:
            if up > 0:
                emerge(w, p, b, x, up, coat, 0, arm)
            return
        down = ease(span(u, at + 0.03, at + 0.16))
        if down >= 1 and u > at + 0.22:
            return
        feet = b.y + S
        p.save()
        p.translate(x, feet)
        p.rotate(down * 1.4)
        figure(p, 0, 0, 0.84, coat, 0, 0.2, "#f4f7fb", "", False)
        p.restore()
        burst = span(u, at, at + 0.08)
        if 0 < burst < 1:
            head_burst(w, p, x, feet - 18 * S, burst)

    body(xh, "#e7eef8", -1.15, shot_h, c1)
    if u > 0.1:
        body(xc, "#3a1020", 0.35, shot_c, c2)
    if shot_h <= u < 0.92:
        fade = 1 if u < 0.74 else 1 - ease(span(u, 0.74, 0.9))
        stain(w, p, xh, b.y + 2 * S, 9 * S, 3.2 * S, fade)
        if u >= shot_c:
            stain(w, p, xc, b.y + 2 * S, 9 * S, 3.2 * S, fade)


def draw_hold_heli(w, p, live):
    u = live.local / live.dur
    if u < 0.34 or u > 0.8:
        return
    b = BUILDINGS[1]
    k = span(u, 0.34, 0.78)
    x = -36 * S + k * (BOX[2] + 80 * S)
    y = max(SY0 + 8 * S, b.y - 40 * S)
    head_y = b.y + S - 18 * S
    p.fill_rect(x, y, 24 * S, 8 * S, "#d5deea")
    p.fill_rect(x + 4 * S, y + 2 * S, 8 * S, 4 * S, "#1b2262")
    p.fill_rect(x - 16 * S, y + 3 * S, 16 * S, 3 * S, "#8ea9c4")
    spin = live.local * 16
    p.line([(x + 10 * S - math.cos(spin) * 18 * S, y), (x + 10 * S + math.cos(spin) * 18 * S, y)], "#f4f7fb", 2 * S)
    for at, tx in ((0.48, b.x + b.w * 0.32), (0.56, b.x + b.w * 0.68)):
        if at <= u <= at + 0.05:
            p.line([(x + 12 * S, y + 6 * S), (tx, head_y)], "#fff6b0", S)


def boom(w, p, x, y, q):
    C = w.C
    t = clamp01(q)
    r = (6 + t * 22) * S
    p.fill_circle(x, y, r, C["RED"], 1 - t)
    p.fill_circle(x, y, r * 0.62, C["ORANGE"], 1 - t)
    p.fill_circle(x, y, r * 0.28, "#fff6d0", 1 - t)
    for i in range(6):
        a = i / 6.0 * math.pi * 2
        p.line([(x + math.cos(a) * r * 0.3, y + math.sin(a) * r * 0.3), (x + math.cos(a) * r * 1.15, y + math.sin(a) * r * 0.7)], C["GOLD"], S, 1 - t * 0.5)


def draw_scaffold(w, p, b, top):
    base = b.y + b.h
    if base - top < 6 * S:
        return
    left, right = b.x - 10 * S, b.x + b.w + 4 * S
    for xx in (left, left + 5 * S, right, right + 5 * S):
        p.line([(xx, base), (xx, top)], "#d5deea", S)
    step = 18 * S
    y = base
    while y >= top:
        p.line([(left, y), (right + 5 * S, y)], "#d5deea", S)
        p.line([(left, y), (left + 5 * S, y - step * 0.5)], "#d5deea", S)
        p.line([(right, y), (right + 5 * S, y - step * 0.5)], "#d5deea", S)
        y -= step
    y = base - step
    while y >= top:
        p.fill_rect(b.x - 8 * S, y, b.w + 16 * S, 2 * S, "#8ea9c4")
        y -= step


def draw_lift(w, p, live):
    C = w.C
    b = BUILDINGS[0]
    cut = building_cut(live)
    if not cut:
        return
    u = live.local / live.dur
    top = b.y + b.h * (1 - cut[1])
    if 0.02 <= u < 0.34:
        n = 5
        slot = (0.34 - 0.02) / n
        i = min(n - 1, int(span(u, 0.02, 0.34) * n))
        local = (u - 0.02 - i * slot) / slot
        if local < 0.55:
            boom(w, p, b.x + b.w * 0.5, top, local / 0.55)
            for k in range(4):
                fall = local * (0.4 + k * 0.15)
                p.fill_rect(b.x + (k + 0.5) * b.w / 4, top + fall * b.h * 0.35, 3 * S, 2 * S, "#3a1020" if k % 2 else "#8ea9c4")
    if 0.3 < u < 0.55:
        a = 1 if u < 0.36 else 1 - ease(span(u, 0.4, 0.54))
        p.fill_ellipse(b.x + b.w * 0.5, b.y + b.h - S, b.w * 0.42, 4 * S, "#3a4258", a)
    if 0.36 < u < 0.92:
        home = BUILDINGS[1]
        mast = ease(span(u, 0.36, 0.44)) if u < 0.74 else 1 - ease(span(u, 0.82, 0.92))
        jib = min(1.0, mast * 2)
        slew = ease(span(u, 0.44, 0.56)) * (1 - ease(span(u, 0.7, 0.82)))
        angle = slew * math.pi
        crane_x = home.x + 6 * S
        length = max(28 * S, crane_x - (b.x + b.w * 0.4))
        reach = math.cos(angle) * length
        dip = math.sin(angle) * 8 * S
        mast_px = 36 * S * mast
        working = slew > 0.82
        bob = math.sin(live.local * 3) * 4 * S
        cable = max(4 * S, top - (home.y - mast_px) + bob) if working else 0
        draw_crane_rig(w, p, crane_x, home.y, mast_px, jib, cable, reach, dip)
    if u > 0.42:
        built = b.y + b.h * (1 - cut[1])
        strip = ease(span(u, 0.72, 0.98))
        scaffold_top = built - 8 * S if u < 0.7 else b.y + b.h * strip
        draw_scaffold(w, p, b, scaffold_top)
        step = live.local * 9
        if u < 0.72:
            inn = ease(span(u, 0.42, 0.5))
            deck = built + S
            shift = (1 - inn) * -30 * S
            figure(p, b.x + b.w * 0.3 + shift, deck, 0.7, "#d7c4a8", step, 0.4)
            figure(p, b.x + b.w * 0.62 + shift, deck, 0.7, C["ORANGE"], step + 1, -0.2)
            figure(p, b.x - 16 * S + inn * 20 * S, b.y + b.h - S, 0.7, "#e7eef8", step, 0.15)
        elif strip < 0.92:
            figure(p, b.x - 8 * S, scaffold_top + 6 * S, 0.7, "#d7c4a8", step, 0.5)
            figure(p, b.x + b.w + 2 * S, scaffold_top + 6 * S, 0.7, C["ORANGE"], step + 1, -0.3)


def draw_ship(w, p, live):
    C = w.C
    u = live.local / live.dur
    x = BOX[2] + 70 * S - u * (BOX[2] + 160 * S)
    y = SY0 + 13 * S
    p.save()
    p.translate(x, y)
    p.scale(-1, 1)
    hull = Painter.arc_pts(0, 0, 34 * S, 12 * S, 0, 2 * math.pi, 32)[:-1]
    p.fill_poly(hull, "#1a2238")
    p.line(hull, C["EDGE"], S, closed=True)
    p.fill_rect(-14 * S, -2 * S, 28 * S, 3 * S, C["MAG"])
    for i in range(-2, 3):
        p.fill_rect(i * 8 * S - S, -7 * S, 2 * S, 4 * S, "#c3d6e6")
    p.fill_poly([(-26 * S, -2 * S), (-38 * S, -10 * S), (-32 * S, 6 * S)], C["RED"])
    p.fill_rect(-10 * S, 10 * S, 22 * S, 8 * S, "#0e1324")
    p.fill_rect(-6 * S, 12 * S, 4 * S, 3 * S, C["GOLD"])
    p.fill_rect(S, 12 * S, 4 * S, 3 * S, C["CYAN"])
    p.line([(-4 * S, 10 * S), (-6 * S, 4 * S)], "#8ea9c4", S)
    p.line([(6 * S, 10 * S), (8 * S, 4 * S)], "#8ea9c4", S)
    p.restore()


def draw_cone(w, p, live):
    C = w.C
    u = live.local / live.dur
    x = -40 * S + u * (BOX[2] + 80 * S)
    y = SY0 + 9 * S
    beam = ease(span(u, 0.18, 0.32)) if u < 0.72 else 1 - ease(span(u, 0.72, 0.86))
    b = BUILDINGS[2]
    aim = b.x + 8 * S + ease(span(u, 0.32, 0.72)) * (b.w - 16 * S)
    if beam > 0.02:
        p.fill_poly([(x + 10 * S, y + 8 * S), (aim - 16 * S, b.y + 4 * S), (aim + 16 * S, b.y + 4 * S)], "#fff6b0", 0.28 * beam)
    p.fill_rect(x, y, 22 * S, 8 * S, "#d5deea")
    p.fill_rect(x + 4 * S, y + 2 * S, 8 * S, 4 * S, "#1b2262")
    p.fill_rect(x - 16 * S, y + 3 * S, 16 * S, 3 * S, "#8ea9c4")
    p.fill_rect(x - 18 * S, y + S, 3 * S, 6 * S, C["RED"])
    spin = live.local * 14
    p.line([(x + 10 * S - math.cos(spin) * 20 * S, y - math.sin(spin) * 3 * S), (x + 10 * S + math.cos(spin) * 20 * S, y + math.sin(spin) * 3 * S)],
           "#f4f7fb", 2 * S)
    p.line([(x + 10 * S - math.sin(spin) * 16 * S, y - 2 * S), (x + 10 * S + math.sin(spin) * 16 * S, y - 2 * S)], "#f4f7fb", 2 * S)


def draw_gate(w, p, u, drop):
    C = w.C
    ang = -1.15 + drop * 1.15
    x, y = 52 * S, 444 * S
    p.fill_rect(x - 14 * S, y - 6 * S, 28 * S, 8 * S, "#12182c")
    p.fill_rect(x - 3 * S, y - 46 * S, 7 * S, 42 * S, "#8ea9c4")
    p.fill_rect(x - 3 * S, y - 46 * S, 2 * S, 42 * S, "#eef6fb")
    p.fill_rect(x - 9 * S, y - 52 * S, 18 * S, 12 * S, "#2a3148")
    p.fill_rect(x - 6 * S, y - 49 * S, 5 * S, 4 * S, C["RED"] if drop > 0.85 else "#3a1020")
    p.fill_rect(x + S, y - 49 * S, 5 * S, 4 * S, "#3a1020" if drop > 0.85 else C["GOLD"])
    p.fill_rect(x + 70 * S, y - 20 * S, 5 * S, 20 * S, "#8ea9c4")
    p.fill_rect(x + 64 * S, y - 4 * S, 16 * S, 5 * S, "#12182c")
    p.save()
    p.translate(x, y - 40 * S)
    p.rotate(ang)
    p.fill_poly([(-2 * S, -4 * S), (-16 * S, -7 * S), (-16 * S, 7 * S), (-2 * S, 4 * S)], "#3f4860")
    i = 0
    while i < 68 * S:
        p.fill_rect(i, -3 * S, 8 * S, 6 * S, C["RED"] if int(i / (8 * S)) % 2 == 0 else "#f4f7fb")
        i += 8 * S
    p.fill_rect(66 * S, -5 * S, 7 * S, 10 * S, C["RED"] if drop > 0.9 else C["GOLD"])
    p.restore()
    p.fill_circle(x, y - 40 * S, 3.5 * S, "#0d1030")
    if u < 0:
        return
    tx, ty = rail_spot(w)
    if u < 0.46:
        k = span(u, 0.08, 0.46)
        fx = -10 * S + (tx + 10 * S) * k
        fy = y - 2 * S + (ty - (y - 2 * S)) * k
        figure(p, fx, fy, 1.2, "#d7c4a8", u * 78, 0.55, "#8d5a3c", "#1a120c")


def draw_marks(w, p, live):
    p.save()
    p.clip_rect(*BOX)
    u = live.local / live.dur
    if live.id == "pass" and u >= 0.54:
        b = BUILDINGS[3]
        clear = ease(span(u, 0.74, 0.88))
        stain(w, p, b.x + b.w * 0.35, HZ + 3.5 * S, 8 * S, 1.1 * S, 1 - clear)
        stain(w, p, b.x + b.w * 0.7, HZ + 3.5 * S, 7 * S, S, 1 - clear)
    elif live.id == "crane" and 0.2 <= u < 0.52:
        wx, _wy, _g = fallen_pane(BUILDINGS[1])
        stain(w, p, wx + WIN_W / 2.0, HZ + 3.5 * S, 9 * S, 1.2 * S, 1 - ease(span(u, 0.38, 0.5)))
    elif live.id == "cross" and u >= 0.46:
        tx, ty = rail_spot(w)
        stain(w, p, tx, ty, 14 * S, 4 * S, 1 - ease(span(u, 0.62, 0.98)))
    p.restore()


def draw_street(w, p, live):
    u = live.local / live.dur
    lamp = math.sin(live.local * 14)
    curb = street_y()
    if live.id == "crane" and u > 0.24:
        b = BUILDINGS[1]
        wx, _wy, _g = fallen_pane(b)
        inn = ease(span(u, 0.24, 0.36))
        leaving = ambulance_leave(live)
        if inn > 0 and leaving < 1:
            park, start, end = wx + 16 * S, -80 * S, BOX[2] + 30 * S
            xx = start + inn * (park - start) + leaving * (end - park)
            place_vehicle(p, xx, curb, lambda: draw_ambulance(w, p, xx, curb, lamp))
    elif live.id == "pass" and u > 0.6:
        b = BUILDINGS[3]
        inn, out = ease(span(u, 0.6, 0.74)), ease(span(u, 0.88, 0.99))
        park, start, end = b.x - 4 * S, -80 * S, BOX[2] + 24 * S
        xx = start + inn * (park - start) + out * (end - park)
        place_vehicle(p, xx, curb, lambda: draw_ambulance(w, p, xx, curb, lamp))
    elif live.id == "burn" and u > 0.48:
        b = BUILDINGS[2]
        inn = ease(span(u, 0.48, 0.62))
        leaving = leave_when_clear(live, 0.9)
        if inn > 0 and leaving < 1:
            park, start, end = b.x + 4 * S, -90 * S, BOX[2] + 30 * S
            xx = start + inn * (park - start) + leaving * (end - park)
            place_vehicle(p, xx, curb, lambda: draw_fire_truck(w, p, xx, curb, lamp))
            spray = ease(span(u, 0.62, 0.7)) * (1 - ease(span(u, 0.84, 0.9))) * (1 - leaving)
            if spray > 0.02:                                       # the hose: a quadratic curve, sampled
                ax, ay = xx + 4 * S, curb - 14 * S
                cx, cy = b.x + b.w * 0.15, b.y + b.h * 0.45
                ex, ey = b.x + b.w * 0.5, b.y + S
                pts = [((1 - t) ** 2 * ax + 2 * (1 - t) * t * cx + t * t * ex, (1 - t) ** 2 * ay + 2 * (1 - t) * t * cy + t * t * ey)
                       for t in (i / 14.0 for i in range(15))]
                p.line(pts, "#b9ecff", 3 * S, 0.9 * spray)
    elif live.id == "hold" and u > 0.16:
        b = BUILDINGS[1]
        lamp = math.sin(live.local * 8)
        inn = ease(span(u, 0.16, 0.4))
        leaving = leave_when_clear(live, 0.78)
        if inn > 0 and leaving < 1:
            for i, park in enumerate((b.x, b.x + 40 * S, b.x + 80 * S)):
                start, end = -100 * S - i * 48 * S, BOX[2] + 20 * S + i * 24 * S
                px = start + inn * (park - start) + leaving * (end - park)
                place_vehicle(p, px, curb, lambda px=px: draw_police(w, p, px, curb, lamp))


CITY = {"crane": draw_crane, "wash": draw_wash, "burn": draw_burn, "pass": draw_pass, "hold": draw_hold, "lift": draw_lift}
