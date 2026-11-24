"""A faint pumice-stone surface for the Dark and Light appearances (0.5.2).

Pure Python (no Pillow): one seamless relief tile is computed once, then tinted to each surface colour and
encoded as PNG with oracle_assets.rgba_png. The relief has three layers, all of which wrap at the tile's edges
so tiling shows no seams:

* pores: clustered and scattered vesicles stretched along one flow direction, with ragged edges, many
  micro-pores; each is darker inside, a little lighter on the wall that faces the light (top left) and has a
  faint raised rim;
* a slow mottle in two octaves, so large areas are not perfectly even;
* a fine grain.

The relief is measured in 8-bit levels and kept faint: most pixels move by one or two levels, the deepest pores
by about six. STRENGTH scales it (0 is flat).
"""
from __future__ import annotations

import math
import random
from functools import lru_cache

SIZE = 256                 # tile size in pixels (a seamless square)
STRENGTH = 1.0             # 1.0: faint. Light surfaces get a little more, so the pores read on white
SEED = 1931


def _value_noise(rnd, size, g):
    """Wrapped, smoothly interpolated value noise on a g x g lattice: a list of size*size floats in -1..1."""
    lattice = [[rnd.uniform(-1.0, 1.0) for _ in range(g)] for _ in range(g)]
    cell = size / g
    out = [0.0] * (size * size)

    def smooth(t):
        return t * t * (3 - 2 * t)
    for y in range(size):
        gy, fy = divmod(y / cell, 1)
        gy, sy = int(gy), smooth(fy)
        r0, r1 = lattice[gy % g], lattice[(gy + 1) % g]
        for x in range(size):
            gx, fx = divmod(x / cell, 1)
            gx, sx = int(gx), smooth(fx)
            a, b, c, d = r0[gx % g], r0[(gx + 1) % g], r1[gx % g], r1[(gx + 1) % g]
            top, bottom = a + (b - a) * sx, c + (d - c) * sx
            out[y * size + x] = top + (bottom - top) * sy
    return out


@lru_cache(maxsize=4)
def relief(size=SIZE, seed=SEED):
    """The tile's height map: a tuple of size*size floats in 8-bit levels (negative is darker)."""
    rnd = random.Random(seed)
    n = size * size
    # Slow mottle in two octaves (5 and 13 cells across, so neither lines up with the tile or the other).
    coarse, fine = _value_noise(rnd, size, 5), _value_noise(rnd, size, 13)
    h = [0.9 * a + 0.45 * b + rnd.gauss(0.0, 0.7) for a, b in zip(coarse, fine)]   # plus a fine grain
    flow = math.radians(rnd.uniform(-30, -10))     # pumice vesicles are stretched along the flow

    def pore(cx, cy, radius, depth):
        aspect = rnd.uniform(1.15, 1.9) if radius > 0.9 else rnd.uniform(1.0, 1.5)
        angle = flow + rnd.gauss(0.0, 0.3)
        ca, sa = math.cos(angle), math.sin(angle)
        rx, ry = radius * aspect, radius / math.sqrt(aspect)
        wobble = [rnd.uniform(-0.18, 0.18) for _ in range(5)]   # a ragged edge
        reach = int(rx * 1.5) + 2
        for oy in range(-reach, reach + 1):
            for ox in range(-reach, reach + 1):
                px, py = int(cx) + ox, int(cy) + oy
                vx, vy = px + 0.5 - cx, py + 0.5 - cy
                u, v = (vx * ca + vy * sa) / rx, (-vx * sa + vy * ca) / ry
                theta = math.atan2(v, u)
                edge = 1.0 + sum(w * math.sin((k + 2) * theta + k) for k, w in enumerate(wobble))
                d = math.hypot(u, v) / edge
                i = (py % size) * size + (px % size)
                if d < 1.0:
                    # Darker inside; the inner wall facing the light (top left) is the lower-right one: lighter.
                    lit = max(0.0, (vx + vy) / (1.414 * max(rx, ry)))
                    h[i] += -depth * (1.0 - d * d) ** 0.7 + depth * 0.35 * lit
                elif d < 1.45:
                    h[i] += depth * 0.14 * (1.0 - (d - 1.0) / 0.45)

    # Clusters of pores, as vesicles gather in the stone, and scattered ones between them.
    for _ in range(18):
        ccx, ccy, spread = rnd.uniform(0, size), rnd.uniform(0, size), rnd.uniform(6, 22)
        for _ in range(rnd.randint(4, 14)):
            radius = 0.8 + (rnd.random() ** 2.0) * 3.4
            pore(ccx + rnd.gauss(0, spread), ccy + rnd.gauss(0, spread), radius, 1.6 + radius * 1.1)
    for _ in range(n // 260):
        radius = 0.6 + (rnd.random() ** 3.0) * 2.4
        pore(rnd.uniform(0, size), rnd.uniform(0, size), radius, 1.2 + radius * 1.0)
    for _ in range(n // 90):                              # micro-pores
        pore(rnd.uniform(0, size), rnd.uniform(0, size), rnd.uniform(0.35, 0.7), rnd.uniform(0.8, 1.8))
    return tuple(h)


def _rgb(colour):
    colour = colour.lstrip('#')
    return tuple(int(colour[i:i + 2], 16) for i in (0, 2, 4))


def _luminance(rgb):
    r, g, b = (v / 255.0 for v in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


@lru_cache(maxsize=2)
def _levels(size, strength):
    """The relief rounded to whole levels, as one flat tuple of ints."""
    return tuple(round(v * strength) for v in relief(size))


def _encode(size, levels, pixel):
    """PNG bytes for a size x size tile; pixel(level) gives the 4 bytes for a level (looked up once each)."""
    from oracle_assets import rgba_png
    table = {}
    rows = []
    for y in range(size):
        row = levels[y * size:(y + 1) * size]
        rows.append(b''.join(table[v] if v in table else table.setdefault(v, pixel(v)) for v in row))
    return rgba_png(size, size, rows)


@lru_cache(maxsize=64)
def tile_png(colour, strength=None, size=SIZE):
    """PNG bytes of the pumice tile on `colour` (#RRGGBB)."""
    base = _rgb(colour)
    k = STRENGTH if strength is None else strength
    if _luminance(base) > 0.6:
        k *= 1.25                       # pores read less on light surfaces
    return _encode(size, _levels(size, round(k, 3)),
                   lambda v: bytes((max(0, min(255, base[0] + v)), max(0, min(255, base[1] + v)),
                                    max(0, min(255, base[2] + v)), 255)))


@lru_cache(maxsize=8)
def offset_png(size=SIZE, strength=None):
    """The relief alone as a grey tile centred on level 128 (for blending onto Pillow artwork)."""
    k = STRENGTH if strength is None else strength
    return _encode(size, _levels(size, round(k, 3)), lambda v: bytes((128 + v,) * 3 + (255,)))


@lru_cache(maxsize=64)
def corner_png(radius, outside, corner):
    """A radius x radius square: `outside` beyond a rounded corner, transparent inside it (anti-aliased).
    corner: 'tl', 'tr', 'bl' or 'br'. Laid over a textured card, it rounds the card's corner."""
    from oracle_assets import rgba_png
    r = max(1, int(radius))
    col = _rgb(outside)
    rows = []
    for y in range(r):
        row = bytearray()
        for x in range(r):
            # Distance from the arc's centre, which sits at the inner corner of this square.
            cx = r if corner in ('tl', 'bl') else 0
            cy = r if corner in ('tl', 'tr') else 0
            cover = 0.0
            for sy in (0.25, 0.75):
                for sx in (0.25, 0.75):
                    if math.hypot(x + sx - cx, y + sy - cy) > r:
                        cover += 0.25
            row += bytes((col[0], col[1], col[2], round(255 * cover)))
        rows.append(bytes(row))
    return rgba_png(r, r, rows)


@lru_cache(maxsize=32)
def rounded_tile_png(colour, radius=10, strength=None, size=SIZE):
    """A nine-slice card image (0.5.3): one whole tile in the middle, `radius` px of the same texture round it
    (wrapped, so ttk's repeating of the middle and the edges stays seamless), and rounded, anti-aliased corners
    left transparent (ttk shows the style's background there: the surface the card sits on)."""
    from oracle_assets import rgba_png
    base = _rgb(colour)
    k = STRENGTH if strength is None else strength
    if _luminance(base) > 0.6:
        k *= 1.25
    levels = _levels(size, round(k, 3))
    r = max(0, min(int(radius), size))
    full = size + 2 * r
    table = {}

    def pixel(v):
        if v not in table:
            table[v] = bytes((max(0, min(255, base[0] + v)), max(0, min(255, base[1] + v)),
                              max(0, min(255, base[2] + v)), 255))
        return table[v]

    # Alpha of the r x r top-left corner square (mirrored for the other three), 4 samples a pixel.
    corner = [[sum((x + sx - r) ** 2 + (y + sy - r) ** 2 <= r * r
                   for sx, sy in ((0.25, 0.25), (0.75, 0.25), (0.25, 0.75), (0.75, 0.75))) * 255 // 4
               for x in range(r)] for y in range(r)]

    rows = []
    for y in range(full):
        ty = (y - r) % size
        line = levels[ty * size:(ty + 1) * size]
        wrapped = (line[size - r:] + line + line[:r]) if r else line
        row = bytearray(b''.join(pixel(v) for v in wrapped))
        cy = y if y < r else (full - 1 - y if y >= full - r else None)
        if cy is not None:
            for x in range(r):
                a = corner[cy][x]
                row[x * 4 + 3] = a
                row[(full - 1 - x) * 4 + 3] = a
        rows.append(bytes(row))
    return rgba_png(full, full, rows)
