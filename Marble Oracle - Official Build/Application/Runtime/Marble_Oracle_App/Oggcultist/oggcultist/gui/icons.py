"""Bold gradient transport icons (⏮ ⏭ ■) drawn with Pillow.

Tk can't colour text with a gradient, so these are images: solid shapes filled with the
amber → reddish-orange gradient, drawn 4× larger and scaled down for smooth edges. Each icon
has normal, hover, pressed and disabled images; ttk picks one by button state.
"""
from __future__ import annotations

import tkinter as tk
from functools import lru_cache

from . import textures

SUPER = 4          # supersampling factor
UNIT = 100         # shapes are designed on a 100 × 100 grid


def _shapes(name: str) -> list:
    """Polygons and rectangles on the 100-unit grid: ('poly', points) or ('rect', box, radius)."""
    if name == 'next':
        return [('poly', [(8, 16), (8, 84), (46, 50)]),
                ('poly', [(42, 16), (42, 84), (80, 50)]),
                ('rect', (80, 16, 93, 84), 4)]
    if name == 'previous':
        return [('rect', (7, 16, 20, 84), 4),
                ('poly', [(58, 16), (58, 84), (20, 50)]),
                ('poly', [(92, 16), (92, 84), (54, 50)])]
    if name == 'play':
        return [('poly', [(24, 12), (24, 88), (86, 50)])]
    if name == 'pause':
        return [('rect', (20, 14, 42, 86), 5), ('rect', (58, 14, 80, 86), 5)]
    if name == 'stop':
        return [('rect', (18, 18, 82, 82), 12)]
    raise ValueError(name)


OUTLINE = '#000000'
OUTLINE_PX = 1.5   # outline width at final size


@lru_cache(maxsize=32)
def _masks(name: str, size: int, outlined: bool):
    """The supersampled shape mask and (if outlined) outline ring; shared by every frame."""
    from PIL import Image, ImageDraw, ImageFilter
    big = size * SUPER
    # leave room inside the square for the outline
    margin = (OUTLINE_PX + 0.5) * SUPER if outlined else 0
    scale = (big - 2 * margin) / UNIT
    mask = Image.new('L', (big, big), 0)
    draw = ImageDraw.Draw(mask)
    for shape in _shapes(name):
        if shape[0] == 'poly':
            draw.polygon([(margin + x * scale, margin + y * scale) for x, y in shape[1]], fill=255)
        else:
            x0, y0, x1, y1 = (margin + v * scale for v in shape[1])
            draw.rounded_rectangle((x0, y0, x1, y1), radius=shape[2] * scale, fill=255)
    ring = None
    if outlined:
        grow = int(round(OUTLINE_PX * SUPER)) * 2 + 1
        ring = mask.filter(ImageFilter.MaxFilter(grow))
    return mask, ring


def render(name: str, size: int, stops: tuple[str, ...], outline: str | None = None,
           shift: float | None = None):
    """One icon as an RGBA Pillow image, ``size`` pixels square, optionally with an outline.

    ``shift`` (v1.8.9) renders one frame of the slow gradient drift (see ``textures.drift``).
    """
    from PIL import Image
    big = size * SUPER
    mask, ring = _masks(name, size, bool(outline))
    fill = Image.new('RGB', (1, big))
    for y in range(big):
        fill.putpixel((0, y), textures._stop_colour(stops, textures.drift(y / max(1, big - 1), shift)))
    icon = Image.new('RGBA', (big, big), (0, 0, 0, 0))
    if outline:
        icon.paste(Image.new('RGB', (big, big), textures._rgb(outline)), (0, 0), ring)
    icon.paste(fill.resize((big, big)), (0, 0), mask)
    return icon.resize((size, size), Image.LANCZOS)


def transport_icons(root: tk.Misc, size: int) -> dict[str, tuple] | None:
    """{'next'|'previous'|'stop': ttk image spec}, or None if Pillow is unavailable."""
    try:
        from PIL import ImageTk
        from .theme import GRADIENT, GRADIENT_DISABLED, GRADIENT_HOVER, GRADIENT_PRESSED
        keep = getattr(root, '_og_icons', None)
        if keep is None:
            keep = root._og_icons = []
        result = {}
        anim = getattr(root, '_og_anim', None) or getattr(root.winfo_toplevel(), '_og_anim', None)
        for name in ('previous', 'next', 'stop'):
            images = {}
            for state, stops in (('normal', GRADIENT), ('active', GRADIENT_HOVER),
                                 ('pressed', GRADIENT_PRESSED), ('disabled', GRADIENT_DISABLED)):
                drifts = state != 'disabled'
                images[state] = ImageTk.PhotoImage(render(name, size, stops, OUTLINE, 0.0 if drifts else None),
                                                   master=root)
                if drifts and anim is not None:      # v1.8.9: the icon gradient drifts too
                    anim.register(images[state], lambda shift, n=name, st=stops: render(n, size, st, OUTLINE, shift))
            keep.extend(images.values())
            # ttk uses the first state that matches, so the most specific come first.
            result[name] = (images['normal'], 'disabled', images['disabled'], 'pressed', images['pressed'],
                            'active', images['active'])
        # play / pause sit on the gradient button, so they are solid dark like its text
        from .theme import PALETTE
        for name in ('play', 'pause'):
            image = ImageTk.PhotoImage(render(name, max(10, round(size * 0.8)), (PALETTE['on_accent'],)),
                                       master=root)
            keep.append(image)
            result[name] = image
        return result
    except Exception:  # noqa: BLE001 - icons are cosmetic; the text symbols remain
        return None
