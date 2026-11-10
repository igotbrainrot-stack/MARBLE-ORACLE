"""Thin line icons for navigation and quiet controls (2.0 "Ember").

Drawn with Pillow on a 24-unit grid, supersampled 4× and scaled down, so they stay crisp at
16–24 px without an icon font. Each shape is a list of strokes:

* ``('line', [(x, y), ...])`` an open polyline, ``('poly', [...])`` a closed one
* ``('circle', (cx, cy, r))``, ``('rect', (x0, y0, x1, y1, radius))``
* ``('arc', (cx, cy, r, start, end))`` in degrees, clockwise from 3 o'clock (Pillow's convention)
* ``('dot', (cx, cy, r))`` a filled circle
"""
from __future__ import annotations

import tkinter as tk
from functools import lru_cache

SUPER = 4
GRID = 24.0
STROKE = 1.75

SHAPES: dict[str, list] = {
    'library': [('line', [(4, 5), (14, 5)]), ('line', [(4, 10), (14, 10)]), ('line', [(4, 15), (10, 15)]),
                ('line', [(18.5, 16), (18.5, 5), (21, 6.5)]), ('circle', (16, 16.5, 2.5))],
    'artists': [('circle', (12, 8, 4)), ('arc', (12, 22, 8, 200, 340))],
    'albums': [('rect', (3, 3, 17, 17, 2)), ('line', [(7, 21), (19, 21), (21, 19), (21, 7)]),
               ('circle', (10, 10, 2.5))],
    'playlists': [('line', [(4, 6), (20, 6)]), ('line', [(4, 12), (14, 12)]), ('line', [(4, 18), (11, 18)]),
                  ('poly', [(17, 14), (17, 20), (21.5, 17)])],
    'converter': [('arc', (12, 12, 8, 200, 320)), ('line', [(17, 4.5), (19.2, 7.6), (15.6, 8.4)]),
                  ('arc', (12, 12, 8, 20, 140)), ('line', [(7, 19.5), (4.8, 16.4), (8.4, 15.6)])],
    'art': [('rect', (3, 3, 21, 21, 2)), ('line', [(6, 17), (10.5, 12), (14, 15.5), (16, 13.5), (20, 17.5)]),
            ('circle', (9, 8, 1.6))],
    'settings': [('circle', (12, 12, 3.2)), ('line', [(12, 2.5), (12, 5.5)]), ('line', [(12, 18.5), (12, 21.5)]),
                 ('line', [(2.5, 12), (5.5, 12)]), ('line', [(18.5, 12), (21.5, 12)]),
                 ('line', [(5.3, 5.3), (7.4, 7.4)]), ('line', [(16.6, 16.6), (18.7, 18.7)]),
                 ('line', [(5.3, 18.7), (7.4, 16.6)]), ('line', [(16.6, 7.4), (18.7, 5.3)])],
    'search': [('circle', (11, 11, 6.5)), ('line', [(16, 16), (20.5, 20.5)])],
    'shuffle': [('line', [(3, 7), (6, 7), (9, 9), (13, 15), (16, 17), (20, 17)]),
                ('line', [(3, 17), (6, 17), (9, 15)]), ('line', [(13, 9), (16, 7), (20, 7)]),
                ('line', [(17.5, 4), (20.5, 7), (17.5, 10)]), ('line', [(17.5, 14), (20.5, 17), (17.5, 20)])],
    'repeat': [('line', [(4, 11), (4, 9), (7, 6), (20, 6)]), ('line', [(17, 3), (20, 6), (17, 9)]),
               ('line', [(20, 13), (20, 15), (17, 18), (4, 18)]), ('line', [(7, 21), (4, 18), (7, 15)])],
    'repeat_one': [('line', [(4, 11), (4, 9), (7, 6), (20, 6)]), ('line', [(17, 3), (20, 6), (17, 9)]),
                   ('line', [(20, 13), (20, 15), (17, 18), (4, 18)]), ('line', [(7, 21), (4, 18), (7, 15)]),
                   ('line', [(11, 10.5), (12.5, 9.5), (12.5, 14.5)])],
    'volume': [('poly', [(4, 9), (7, 9), (12, 5), (12, 19), (7, 15), (4, 15)]), ('arc', (13, 12, 4, 300, 60)),
               ('arc', (13, 12, 7.5, 305, 55))],
    'folder': [('line', [(3, 7), (3, 18), (5, 19.5), (19, 19.5), (21, 18), (21, 9.5), (19, 8), (11, 8),
                         (9, 5.5), (5, 5.5), (3, 7)])],
    'download': [('line', [(12, 4), (12, 15)]), ('line', [(7, 10.5), (12, 15.5), (17, 10.5)]),
                 ('line', [(5, 20), (19, 20)])],
    'plus': [('line', [(12, 5), (12, 19)]), ('line', [(5, 12), (19, 12)])],
    'more': [('dot', (5, 12, 1.8)), ('dot', (12, 12, 1.8)), ('dot', (19, 12, 1.8))],
    'note': [('line', [(9, 18), (9, 5), (19, 3), (19, 16)]), ('circle', (6.5, 18, 2.5)), ('circle', (16.5, 16, 2.5))],
}
NAV_ICONS = ('library', 'artists', 'albums', 'playlists', 'converter', 'art', 'settings')


def _rgb(colour: str) -> tuple[int, int, int]:
    colour = colour.lstrip('#')
    return tuple(int(colour[i:i + 2], 16) for i in (0, 2, 4))


@lru_cache(maxsize=256)
def render(name: str, size: int, colour: str, stroke: float = STROKE):
    """The icon as an RGBA Pillow image, ``size`` px square."""
    from PIL import Image, ImageDraw
    big = size * SUPER
    k = big / GRID
    width = max(1, round(stroke * k))
    mask = Image.new('L', (big, big), 0)
    draw = ImageDraw.Draw(mask)

    def pt(p):
        return (p[0] * k, p[1] * k)

    for kind, data in SHAPES[name]:
        if kind in ('line', 'poly'):
            points = [pt(p) for p in data] + ([pt(data[0])] if kind == 'poly' else [])
            draw.line(points, fill=255, width=width, joint='curve')
            for p in points:                                   # round caps
                r = width / 2
                draw.ellipse((p[0] - r, p[1] - r, p[0] + r, p[1] + r), fill=255)
        elif kind == 'circle':
            cx, cy, r = (v * k for v in data)
            draw.ellipse((cx - r, cy - r, cx + r, cy + r), outline=255, width=width)
        elif kind == 'dot':
            cx, cy, r = (v * k for v in data)
            draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=255)
        elif kind == 'rect':
            x0, y0, x1, y1, r = data
            draw.rounded_rectangle((x0 * k, y0 * k, x1 * k, y1 * k), radius=r * k, outline=255, width=width)
        elif kind == 'arc':
            cx, cy, r, start, end = data
            cx, cy, r = cx * k, cy * k, r * k
            draw.arc((cx - r, cy - r, cx + r, cy + r), start, end, fill=255, width=width)
        else:  # pragma: no cover - programming error
            raise ValueError(kind)
    small = mask.resize((size, size), Image.LANCZOS)
    icon = Image.new('RGBA', (size, size), _rgb(colour) + (0,))
    icon.putalpha(small)
    return icon


def photo(root: tk.Misc, name: str, size: int, colour: str):
    """A PhotoImage kept alive on the root window, or None without Pillow."""
    try:
        from PIL import ImageTk
        image = ImageTk.PhotoImage(render(name, size, colour), master=root)
    except Exception:  # noqa: BLE001 - icons are cosmetic; text labels remain
        return None
    keep = getattr(root, '_og_line_icons', None)
    if keep is None:
        keep = root._og_line_icons = []
    keep.append(image)
    return image


def stateful(root: tk.Misc, name: str, size: int, normal: str, active: str | None = None,
             disabled: str | None = None):
    """A ttk image spec: ``(normal, 'disabled', img, 'active', img)`` or None without Pillow."""
    base = photo(root, name, size, normal)
    if base is None:
        return None
    spec: list = [base]
    if disabled:
        spec += ['disabled', photo(root, name, size, disabled)]
    if active:
        spec += ['active', photo(root, name, size, active)]
    return tuple(spec)
