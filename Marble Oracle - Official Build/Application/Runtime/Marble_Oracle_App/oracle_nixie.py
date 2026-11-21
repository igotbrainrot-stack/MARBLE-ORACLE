"""Four glass nixie tubes for the upper-left instrument.

Each tube is a dark glass envelope with a hexagonal anode mesh and one
wire cathode. The live cathode glows orange and flickers, the way a real
tube does. Drawn with Pillow and scaled down into the bezel.
"""
import datetime
import io
import math


def local_hhmm(now=None):
    """Return the OS local time as four digits, always zero-padded."""
    if now is None:
        now = datetime.datetime.now()
    return now.strftime("%H%M")


# Wire cathodes in a 100 x 150 box. The shapes follow a stacked nixie numeral,
# not a seven-segment digit.
_DIGITS = {
    "0": [[(50, 12), (22, 32), (14, 75), (22, 118), (50, 138), (78, 118), (86, 75), (78, 32), (50, 12)]],
    "1": [[(58, 22), (36, 14), (46, 24), (46, 132)], [(28, 138), (66, 138)]],
    "2": [[(20, 42), (24, 20), (50, 10), (80, 24), (84, 48), (70, 74), (24, 124), (16, 140), (86, 140)]],
    "3": [[(22, 26), (48, 10), (78, 24), (84, 48), (58, 74), (84, 100), (76, 126), (46, 142), (18, 122)]],
    "4": [[(72, 142), (72, 14), (16, 96), (90, 96)]],
    "5": [[(84, 14), (22, 14), (16, 56), (36, 48), (74, 64), (88, 94), (76, 126), (44, 144), (16, 116)]],
    "6": [[(78, 30), (50, 12), (22, 36), (14, 86), (24, 128), (50, 144), (78, 124), (86, 96), (60, 78), (28, 88), (16, 72)]],
    "7": [[(16, 14), (86, 14), (48, 68), (34, 142)]],
    "8": [[(50, 12), (20, 30), (16, 54), (34, 74), (66, 74), (84, 54), (80, 30), (50, 12)],
          [(34, 74), (16, 98), (22, 128), (50, 144), (80, 128), (86, 98), (66, 74)]],
    "9": [[(24, 124), (50, 144), (80, 118), (86, 68), (72, 30), (46, 12), (20, 32), (14, 58), (32, 78), (70, 70)]],
}


def plate_png(width, height, rgba):
    """Opaque plate that hides the photographed scope under an instrument."""
    try:
        from PIL import Image, ImageDraw
    except Exception:
        return None
    im = Image.new("RGBA", (max(1, int(width)), max(1, int(height))), (0, 0, 0, 0))
    ImageDraw.Draw(im, "RGBA").rounded_rectangle(
        [0, 0, im.width - 1, im.height - 1], radius=max(2, min(im.width, im.height) // 14), fill=rgba)
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


_PAIRS = {}


def _sprite_dir():
    from pathlib import Path
    return Path(__file__).resolve().parent / "data" / "nixie_wires"


def sprite_pair(digit):
    """The photographed dim and lit tube for one numeral. None if the art is missing."""
    digit = str(digit)
    if digit in _PAIRS:
        return _PAIRS[digit]
    try:
        from PIL import Image
    except Exception:
        return None
    folder = _sprite_dir()
    lit = folder / ("nixie_%s_lit.png" % digit)
    dim = folder / ("nixie_%s_dim.png" % digit)
    if not lit.is_file() or not dim.is_file():
        return None
    pair = (Image.open(dim).convert("RGBA"), Image.open(lit).convert("RGBA"))
    _PAIRS[digit] = pair
    return pair


def _legacy_nixie_frames(digit, width, height, steps=9):
    """One still photograph. Only the orange glow changes, from soft to full.

    The dim and lit pictures are not the same tube. Crossfading them made the
    glass and the wires crawl. The lit photograph stays put.
    """
    pair = sprite_pair(digit)
    if pair is None:
        return []
    from PIL import Image
    width, height = max(8, int(width)), max(8, int(height))
    lit = pair[1].resize((width, height), Image.Resampling.LANCZOS)
    px = lit.load()
    warm = []
    for y in range(height):
        for x in range(width):
            r, g, b, a = px[x, y]
            if a > 8 and r > 36 and r > g + 8 and r > b + 8:
                warm.append((x, y, r, g, b, a))
    frames = []
    steps = max(2, int(steps))
    lo, hi = 0.72, 1.0
    for i in range(steps):
        t = lo + (hi - lo) * (i / float(steps - 1))
        frame = lit.copy()
        fp = frame.load()
        for x, y, r, g, b, a in warm:
            fp[x, y] = (min(255, int(r * t)), min(255, int(g * t)), min(255, int(b * t)), a)
        # The leads fade out instead of ending in a cut line.
        cut = int(height * 368 / 444.0)
        fade = max(3, int(height * 0.07))
        for y in range(max(0, cut - fade), height):
            t = 0.0 if y >= cut else (cut - y) / float(fade)
            for x in range(width):
                r, g, b, a = fp[x, y]
                fp[x, y] = (r, g, b, int(a * t))
        buf = io.BytesIO()
        frame.save(buf, "PNG")
        frames.append(buf.getvalue())
    return frames


def nixie_frames(digit, width, height, steps=9):
    """Approved fixed-shell Nixie layers for both CRT V2 and legacy bezel.

    Shell, post, glass and leads are stationary; only the transparent digit
    is modulated. Retain _legacy_nixie_frames for explicit recovery only.
    """
    from layered_nixie_adapter import layered_nixie_frames
    return layered_nixie_frames(digit, width, height, steps=steps)


class NixieState:
    """Four digits. The glow is a slow breath, with a rare small dip."""

    def __init__(self):
        self.time = None
        self.digits = ["0", "0", "0", "0"]

    def update(self, now, dt):
        hhmm = local_hhmm(now)
        changed = hhmm != self.time
        if changed:
            self.time = hhmm
            self.digits = list(hhmm)
        return changed

    def glow(self, index, now):
        """0.72 to 1. Soft pulse. A short dip every twenty seconds or so."""
        t = now.timestamp()
        breath = 0.5 + 0.5 * math.sin(t * (2.0 * math.pi / 5.2) + index * 0.45)
        level = 0.86 + 0.14 * breath
        period = 19.0 + index * 4.5
        if (t + index * 3.1) % period < 0.12:
            level = 0.74
        return level


def _seat(im):
    """Feather the overlay into the recess. A hard edge reads as a clip."""
    from PIL import Image, ImageChops, ImageDraw, ImageFilter
    w, h = im.size
    radius = max(8, int(min(w, h) * 0.28))
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((1, 1, w - 2, h - 2), radius=radius, fill=255)
    blur = max(1.4, min(w, h) * 0.045)
    mask = mask.filter(ImageFilter.GaussianBlur(radius=blur))
    out = im.copy()
    out.putalpha(ImageChops.multiply(out.getchannel("A"), mask))
    return out


def bay_back_png(width, height, levels):
    """Copper traces behind the four tubes. Each trace follows that tube's glow."""
    from PIL import Image, ImageDraw
    width, height = max(8, int(width)), max(8, int(height))
    im = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im)

    def copper(amount):
        amount = max(0.0, min(1.0, amount))
        return (int(60 + 160 * amount), int(22 + 78 * amount),
                int(6 + 16 * amount), int(60 + 160 * amount))

    glow = [max(0.0, min(1.0, v)) for v in levels]
    bus = sum(glow) / float(len(glow) or 1)
    draw.line((3, height - 5, width - 4, height - 5), fill=copper(bus), width=max(1, height // 28))
    draw.line((5, 5, width - 6, 5), fill=copper(bus * 0.65), width=max(1, height // 40))
    span = width - 8
    gap = max(1, width // 80)
    tw = (span - 3 * gap) / 4.0
    for i, amount in enumerate(glow):
        cx = int(4 + tw / 2.0 + i * (tw + gap))
        draw.line((cx, 7, cx, height - 7), fill=copper(amount), width=max(1, width // 170))
        radius = max(1, width // 140)
        draw.ellipse((cx - radius, height - 9 - radius, cx + radius, height - 5 + radius),
                     fill=copper(min(1.0, amount + 0.15)))
        if i:
            left = glow[i - 1]
            gx = int(4 + i * (tw + gap) - gap / 2.0)
            draw.line((gx, 14, gx, height - 12), fill=copper(min(amount, left) * 0.85), width=1)
    buf = io.BytesIO()
    _seat(im).save(buf, "PNG")
    return buf.getvalue()


def bay_mesh_png(width, height):
    """A fine metal hex screen. Open enough that the numerals stay readable."""
    from PIL import Image, ImageDraw
    import math
    width, height = max(8, int(width)), max(8, int(height))
    im = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im)
    step = max(6, int(min(width, height) / 12))
    line = (186, 192, 200, 115)
    shade = (12, 14, 16, 90)
    y = step
    row = 0
    while y < height:
        x = step + (0 if row % 2 == 0 else step // 2)
        while x < width:
            pts = []
            for k in range(6):
                ang = math.pi / 6.0 + k * math.pi / 3.0
                pts.append((x + step * 0.48 * math.cos(ang), y + step * 0.48 * math.sin(ang)))
            draw.line(pts + [pts[0]], fill=shade, width=1)
            draw.line([(p[0] - 0.4, p[1] - 0.4) for p in pts] + [(pts[0][0] - 0.4, pts[0][1] - 0.4)],
                      fill=line, width=1)
            x += step
        y += int(step * 0.86)
        row += 1
    buf = io.BytesIO()
    _seat(im).save(buf, "PNG")
    return buf.getvalue()
