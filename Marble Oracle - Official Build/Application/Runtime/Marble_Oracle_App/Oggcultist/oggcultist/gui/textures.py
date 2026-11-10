"""Procedural film-grain textures for the Tk theme (Pillow only, generated at start-up).

Per-pixel noise has no visible structure, so the tiles repeat seamlessly and two
widgets whose tiles start at different offsets still look like one surface.
Everything is deterministic (fixed seeds), so screenshots are reproducible.

Grain strength follows brightness: full strength on dark surfaces, fading to about
a third on bright ones (the amber buttons), so labels drawn on them stay clean.
Dark surfaces also get a very faint, low-frequency light mottle (seamlessly tiling).
Tk draws all text on top of these images in solid colour; no texture touches glyphs.
"""
from __future__ import annotations

import math
import random
from functools import lru_cache

from PIL import Image, ImageChops, ImageDraw, ImageFilter

TILE = 256
GRAIN = 0.5         # overall grain strength (1.0 = the original v1.7.1 look; v1.8.5 halves it)
MOTTLE = 4          # peak lift in 8-bit levels, dark areas only (was 8)


def _rgb(colour: str) -> tuple[int, int, int]:
    colour = colour.lstrip('#')
    return tuple(int(colour[i:i + 2], 16) for i in (0, 2, 4))


@lru_cache(maxsize=16)
def _raw_noise(size: tuple[int, int], seed: int, clump: float) -> Image.Image:
    # randbytes is uniform and fast (one C call); scaling its spread to ~0.62 gives
    # roughly the same visible strength as Gaussian noise with sigma 46.
    noise = Image.frombytes('L', size, random.Random(seed).randbytes(size[0] * size[1]))
    noise = noise.point(lambda v: int(128 + (v - 128) * 0.62))
    return noise.filter(ImageFilter.GaussianBlur(clump)) if clump else noise


def _noise(size: tuple[int, int], seed: int, amount: float, clump: float = 0.55) -> Image.Image:
    """Grey noise centred on 128; ``clump`` softens it into film-like grain."""
    return _raw_noise(size, seed % 4, clump).point(lambda v: int(128 + (v - 128) * amount))


def _ramp(lo: int, hi: int, at_lo: int, at_hi: int):
    """Lookup table: at_lo below ``lo``, at_hi above ``hi``, linear in between (0..255 weights)."""
    return [at_lo if v <= lo else at_hi if v >= hi else int(at_lo + (at_hi - at_lo) * (v - lo) / (hi - lo))
            for v in range(256)]


_GRAIN_WEIGHT = _ramp(70, 190, 255, 80)     # dark: full grain; bright: ~30 %
_MOTTLE_WEIGHT = _ramp(40, 95, 255, 0)      # mottle only on the dark surfaces


@lru_cache(maxsize=8)
def _mottle(size: tuple[int, int], seed: int, cells: int = 5) -> Image.Image:
    """Soft light splotches (0 = none, 255 = full lift) that tile seamlessly.

    A small random grid is repeated 3×3, enlarged smoothly and the middle copy cropped,
    so the result wraps at its own edges.
    """
    w, h = size
    rng = random.Random(1000 + seed)
    grid = Image.frombytes('L', (cells, cells), bytes(rng.randrange(256) for _ in range(cells * cells)))
    tiled = Image.new('L', (cells * 3, cells * 3))
    for i in range(3):
        for j in range(3):
            tiled.paste(grid, (i * cells, j * cells))
    big = tiled.resize((w * 3, h * 3), Image.BICUBIC)
    big = big.filter(ImageFilter.GaussianBlur(max(w, h) / cells / 3)).crop((w, h, w * 2, h * 2))
    # keep only the upper part of the field: isolated light patches, mostly nothing
    return big.point(lambda v: max(0, v - 105) * 255 // 150)


def _finish(body: Image.Image, seed: int, amount: float, mottle: bool = True) -> Image.Image:
    """Add brightness-aware grain (and the dark-area mottle) to an RGB image."""
    size = body.size
    luma = body.convert('L')
    noise = _noise(size, seed, amount * GRAIN)
    weight = luma.point(_GRAIN_WEIGHT)
    up = ImageChops.multiply(noise.point(lambda v: max(0, v - 128)), weight)
    down = ImageChops.multiply(noise.point(lambda v: max(0, 128 - v)), weight)
    if mottle and MOTTLE:
        lift = ImageChops.multiply(_mottle(size, seed % 3), luma.point(_MOTTLE_WEIGHT))
        up = ImageChops.add(up, lift.point(lambda v: v * MOTTLE // 255))
    body = ImageChops.add(body, Image.merge('RGB', (up,) * 3))
    return ImageChops.subtract(body, Image.merge('RGB', (down,) * 3))


def grain(base: str, size: tuple[int, int] = (TILE, TILE), amount: float = 0.20, seed: int = 7,
          mottle: bool = True) -> Image.Image:
    """A flat colour with film grain (and, if dark, a faint mottle) on top."""
    return _finish(Image.new('RGB', size, _rgb(base)), seed, amount, mottle)


def _mix(a: tuple, b: tuple, f: float) -> tuple:
    return tuple(int(a[i] + (b[i] - a[i]) * f) for i in range(3))


def _edge_shaded(size, top: str, bottom: str, edge: int) -> Image.Image:
    """Flat middle (safe for ttk tiling) with shading only in the top/bottom ``edge`` rows.

    ttk tiles the centre of an image element, so a full-height gradient would band;
    keeping the shading inside the untiled border rows gives depth without seams.
    """
    w, h = size
    t, b = _rgb(top), _rgb(bottom)
    mid = _mix(t, b, 0.5)
    column = Image.new('RGB', (1, h), mid)
    for y in range(min(edge, h)):
        f = y / max(1, edge)
        column.putpixel((0, y), _mix(t, mid, f))
        column.putpixel((0, h - 1 - y), _mix(b, mid, f))
    return column.resize((w, h))


SMOOTH = 4    # edges and borders are drawn at higher resolution, then scaled down
# v1.9.6: a 38-degree chamfer profile, measured from the flat surface.
# The 2-pixel nominal edge rise gives a ~2.56-pixel-wide light/shadow band.
# This is a pixel-rendered visual approximation of a physical 38-degree bevel.
BEVEL_ANGLE_DEGREES = 38.0
BEVEL_EDGE_DEPTH_PX = 2.0


def bevel_run_px() -> float:
    """Horizontal run of the bevel from its nominal rise and requested slope angle."""
    return BEVEL_EDGE_DEPTH_PX / math.tan(math.radians(BEVEL_ANGLE_DEGREES))


@lru_cache(maxsize=64)
def _round_mask(size: tuple[int, int], radius: float, inset: float = 0.0) -> Image.Image:
    """An anti-aliased rounded-rectangle mask (0..255), optionally inset by ``inset`` px."""
    w, h = size
    big = Image.new('L', (w * SMOOTH, h * SMOOTH), 0)
    k = SMOOTH
    box = [inset * k, inset * k, (w - inset) * k - 1, (h - inset) * k - 1]
    if box[2] > box[0] and box[3] > box[1]:
        ImageDraw.Draw(big).rounded_rectangle(box, radius=max(0.0, radius - inset) * k, fill=255)
    return big.resize((w, h), Image.BOX)       # exact coverage: smooth corners, solid edges


@lru_cache(maxsize=64)
def _bevel_masks(size: tuple[int, int], radius: float, inset: float) -> tuple[Image.Image, Image.Image]:
    """Antialiased 38° sloping rim with top/left light and bottom/right shadow.

    A single 1-pixel ring looked too rounded. A run derived from tan(38°)
    has a defined shoulder and fades towards the flat interior. The body
    beyond that run is untouched. Shape masking keeps the bevel inside the
    border even at the tighter v1.9.6 corners.
    """
    w, h = size
    run = bevel_run_px()
    layers = max(1, int(math.ceil(run)))
    # Composite concentric fractional-pixel strips with decreasing intensity.
    edge = Image.new('L', size, 0)
    for i in range(layers):
        step = min(1.0, run - i)
        if step <= 0:
            break
        ring = ImageChops.subtract(_round_mask(size, radius, inset + i),
                                   _round_mask(size, radius, inset + i + step))
        weight = max(0.0, 1.0 - ((i + step / 2) / run) * 0.70)
        ring = ring.point(lambda v, gain=weight: round(v * gain))
        edge = ImageChops.add(edge, ring)
    split = Image.new('L', size)
    split.putdata([0 if x / max(1, w - 1) + y / max(1, h - 1) > 1 else 255
                   for y in range(h) for x in range(w)])
    split = split.filter(ImageFilter.BoxBlur(1))
    return ImageChops.multiply(edge, split), ImageChops.multiply(edge, ImageChops.invert(split))


def bevel(image: Image.Image, radius: float, strength: float, inset: float = 0.0) -> Image.Image:
    """v1.9.6: a 38-degree chamfer-like bevel: light along the top and left, shade along the
    bottom and right (``strength`` > 0, raised), or the other way round (``strength`` < 0, sunken)."""
    if not strength:
        return image
    top_left, bottom_right = _bevel_masks(image.size, radius, inset)
    light = Image.new('RGB', image.size, (255, 244, 225))
    dark = Image.new('RGB', image.size, (0, 0, 0))
    first, second = (light, dark) if strength > 0 else (dark, light)
    amount = abs(strength)
    out = image.copy()
    out.paste(Image.blend(image, first, min(1.0, amount)), (0, 0), top_left)
    out.paste(Image.blend(image, second, min(1.0, amount * 1.4)), (0, 0), bottom_right)
    return out


def _rounded(body: Image.Image, behind: Image.Image, radius: float, outline: str | None,
             width: float = 1.0, bevel_strength: float = 0.0) -> Image.Image:
    """Put ``body`` on ``behind`` with smooth rounded corners and a smooth ``outline`` border.

    ``bevel_strength`` (v1.9.0) adds a soft bevel just inside the border.
    """
    out = behind.copy()
    outer = _round_mask(body.size, radius)
    if bevel_strength:
        body = bevel(body, radius, bevel_strength, inset=width if outline else 0.0)
    if outline:
        out.paste(Image.new('RGB', body.size, _rgb(outline)), (0, 0), outer)
        out.paste(body, (0, 0), _round_mask(body.size, radius, inset=width))
    else:
        out.paste(body, (0, 0), outer)
    return out


def surface(size: tuple[int, int], top: str, bottom: str, *, behind: str, radius: int = 2,
            outline: str | None = None, highlight: str | None = None, amount: float = 0.20,
            seed: int = 11, bar: str | None = None, edge: int = 7, bevel: float = 0.0) -> Image.Image:
    """A rounded, gradient, grained panel composited onto ``behind`` (no transparency).

    ``highlight`` draws a 1 px top sheen; ``bar`` draws a 3 px accent strip on the left.
    """
    w, h = size
    body = _finish(_edge_shaded(size, top, bottom, edge), seed, amount, mottle=False)
    if highlight:
        ImageDraw.Draw(body).line([(radius, 1), (w - radius - 1, 1)], fill=_rgb(highlight))
    if bar:
        ImageDraw.Draw(body).rectangle([0, 0, 2, h - 1], fill=_rgb(bar))
    return _rounded(body, grain(behind, size, seed=seed + 1, mottle=False), radius, outline,
                    bevel_strength=bevel)


def _stop_colour(stops: tuple[str, ...], f: float) -> tuple:
    """Colour at position f (0..1) along evenly spaced gradient stops."""
    rgbs = [_rgb(c) for c in stops]
    if len(rgbs) == 1:
        return rgbs[0]
    pos = max(0.0, min(1.0, f)) * (len(rgbs) - 1)
    i = min(int(pos), len(rgbs) - 2)
    return _mix(rgbs[i], rgbs[i + 1], pos - i)


# v1.8.9: the gradient drift. An animated gradient shows a window SPAN long of its stops;
# ``shift`` (0..1) slides that window from the top of the gradient (amber) to the bottom (red).
SPAN = 0.6


def drift(f: float, shift: float | None) -> float:
    """Where position ``f`` (0..1) samples the gradient when shifted by ``shift`` (None: no drift)."""
    if shift is None:
        return f
    return SPAN * f + (1.0 - SPAN) * max(0.0, min(1.0, shift))


def gradient(size: tuple[int, int], stops: tuple[str, ...], *, behind: str, radius: int = 2,
             outline: str | None = None, sheen: str | None = None, amount: float = 0.22,
             seed: int = 21, vertical: bool = True, shift: float | None = None,
             bevel: float = 0.0) -> Image.Image:
    """Full-size multi-stop gradient with grain (rendered at the exact size it is shown).

    ``shift`` (v1.8.9) renders one frame of the slow drift; None is the full, still gradient.
    """
    w, h = size
    if vertical:
        strip = Image.new('RGB', (1, h))
        for y in range(h):
            strip.putpixel((0, y), _stop_colour(stops, drift(y / max(1, h - 1), shift)))
    else:
        strip = Image.new('RGB', (w, 1))
        for x in range(w):
            strip.putpixel((x, 0), _stop_colour(stops, drift(x / max(1, w - 1), shift)))
    body = strip.resize((w, h))
    body = _finish(body, seed, amount, mottle=False)
    if sheen:
        ImageDraw.Draw(body).line([(radius, 1), (w - radius - 1, 1)], fill=_rgb(sheen))
    if radius <= 0 and not outline and not bevel:
        return body
    return _rounded(body, grain(behind, size, seed=seed + 1, mottle=False), max(0, radius), outline,
                    bevel_strength=bevel)


def rounded_picture(image: Image.Image, behind: str, radius: float = 2.5, bevel_strength: float = 0.14,
                    amount: float = 0.18) -> Image.Image:
    """v1.9.0: a picture (an album cover) with slightly rounded, bevelled corners on a grained panel."""
    image = image.convert('RGB')
    return _rounded(image, grain(behind, image.size, amount=amount, seed=9, mottle=False), radius, None,
                    bevel_strength=bevel_strength)
