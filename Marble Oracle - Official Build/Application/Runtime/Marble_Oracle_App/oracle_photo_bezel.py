"""Marble_Oracle photographic CRT bezel helpers.

One undistorted photographic frame is used at runtime. The dashboard always
fits inside the true transparent aperture, and any extra bezel animation is
added as lightweight canvas overlays at coordinates derived from the original
source art.
"""
from __future__ import annotations

import base64
import os
import math
import datetime
import zipfile
from pathlib import Path
import struct
import zlib
from oracle_assets import open_zip

SOURCE_W, SOURCE_H = 1448, 1086
# Exact transparent opening in the approved photographic master frame.
APERTURE = (194, 124, 1254, 823)
PHOTO_STEPS = (0.625, 0.75, 0.875, 1.0, 1.125, 1.25, 1.5, 1.75, 2.0)
PHOTO_ZIP = []
V2_ZIP = []


def v2_active():
    return os.environ.get("MARBLE_ORACLE_CRT_V2", "") == "1"

# stock is the restored housing. patina is the same housing with a light rust.
BEZEL_THEMES = ("stock", "patina")


def photo_frame_stem(theme):
    """Which baked photograph to load. Anything unknown stays on the stock frame."""
    return "frame_patina" if theme == "patina" else "frame"


def _png_rgba(data):
    """Decode a non-interlaced 8-bit RGBA PNG. Stdlib only."""
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a png")
    pos, w, h, idat = 8, None, None, []
    while pos + 8 <= len(data):
        n = struct.unpack(">I", data[pos:pos + 4])[0]
        kind = data[pos + 4:pos + 8]
        chunk = data[pos + 8:pos + 8 + n]
        if kind == b"IHDR":
            w, h, bit, color = struct.unpack(">IIBB", chunk[:10])
            if bit != 8 or color != 6:
                raise ValueError("png must be 8-bit rgba")
        elif kind == b"IDAT":
            idat.append(chunk)
        elif kind == b"IEND":
            break
        pos += 12 + n
    raw = zlib.decompress(b"".join(idat))
    stride = w * 4
    rows, i, prev = [], 0, bytearray(stride)
    for _y in range(h):
        filt = raw[i]
        i += 1
        row = bytearray(raw[i:i + stride])
        i += stride
        if filt == 1:
            for x in range(stride):
                left = row[x - 4] if x >= 4 else 0
                row[x] = (row[x] + left) & 255
        elif filt == 2:
            for x in range(stride):
                row[x] = (row[x] + prev[x]) & 255
        elif filt == 3:
            for x in range(stride):
                left = row[x - 4] if x >= 4 else 0
                row[x] = (row[x] + ((left + prev[x]) // 2)) & 255
        elif filt == 4:
            for x in range(stride):
                a = row[x - 4] if x >= 4 else 0
                b = prev[x]
                c = prev[x - 4] if x >= 4 else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pr = a if pa <= pb and pa <= pc else (b if pb <= pc else c)
                row[x] = (row[x] + pr) & 255
        elif filt != 0:
            raise ValueError("bad png filter")
        prev = row
        rows.append(row)
    return w, h, rows


def _png_bytes(w, h, rows):
    raw = b"".join(b"\x00" + bytes(r) for r in rows)

    def chunk(kind, body):
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 6))
            + chunk(b"IEND", b""))


def fit_frame_png(data, tw, th):
    """Scale the photographic frame to the current window. Uniform, keeps alpha."""
    tw, th = int(tw), int(th)
    if tw < 8 or th < 8:
        return data
    try:
        from PIL import Image
        from io import BytesIO
        im = Image.open(BytesIO(data)).convert("RGBA")
        if im.size == (tw, th):
            return data
        im = im.resize((tw, th), Image.LANCZOS)
        buf = BytesIO()
        im.save(buf, "PNG")
        return buf.getvalue()
    except Exception:
        pass
    w, h, rows = _png_rgba(data)
    if (w, h) == (tw, th):
        return data
    out = []
    for y in range(th):
        y0 = y * h // th
        y1 = max(y0 + 1, (y + 1) * h // th)
        row = bytearray(tw * 4)
        for x in range(tw):
            x0 = x * w // tw
            x1 = max(x0 + 1, (x + 1) * w // tw)
            acc = [0, 0, 0, 0]
            n = 0
            for yy in range(y0, y1):
                src = rows[yy]
                for xx in range(x0, x1):
                    i = xx * 4
                    acc[0] += src[i]
                    acc[1] += src[i + 1]
                    acc[2] += src[i + 2]
                    acc[3] += src[i + 3]
                    n += 1
            o = x * 4
            row[o] = acc[0] // n
            row[o + 1] = acc[1] // n
            row[o + 2] = acc[2] // n
            row[o + 3] = acc[3] // n
        out.append(row)
    return _png_bytes(tw, th, out)


class _V2SingleFrame:
    """Read-only archive interface for the standalone V2 PNG.

    Developer checkouts retain frame.zip for rebuild/verification. A lean
    Windows package can omit that duplicate 2 MB archive without disabling
    V2 geometry, launcher detection, or legacy bezel selection.
    """
    def __init__(self, path):
        self.filename = str(path)
        self._path = path

    def namelist(self):
        return ['k1000/frame.png']

    def read(self, name):
        if name != 'k1000/frame.png':
            raise KeyError(name)
        return self._path.read_bytes()


def photo_zip():
    if v2_active():
        if not V2_ZIP:
            base = Path(__file__).resolve().parent / 'data' / 'crt_v2'
            try:
                V2_ZIP.append(zipfile.ZipFile(base / 'frame.zip'))
            except (OSError, zipfile.BadZipFile):
                # The runtime includes the same lossless PNG once, not twice.
                image = base / 'frame.png'
                V2_ZIP.append(_V2SingleFrame(image) if image.is_file() else None)
        return V2_ZIP[0]
    if not PHOTO_ZIP:
        try:
            PHOTO_ZIP.append(open_zip('photo_bezel_locked.zip'))
        except Exception:
            PHOTO_ZIP.append(None)
    return PHOTO_ZIP[0]


def photo_step(scale):
    """Scale near a baked step, allowing half-pixel image-size rounding.

    For example 1086x814 *is* the k=.75 frame, even though 814/1086
    is slightly below .75. A strict floating-point comparison previously
    selected k=.625 and forced the vector fallback at k=.75 and other sizes.
    """
    return max((k for k in PHOTO_STEPS if k <= scale + 0.00055),
               default=PHOTO_STEPS[0])


def photo_scale_for_size(width, height):
    """Return a scale only for an EXACT baked frame size."""
    return next((k for k in PHOTO_STEPS
                 if (photo_geometry(k)['outer_w'], photo_geometry(k)['outer_h']) ==
                 (round(width), round(height))), None)


def photo_geometry(k):
    """Window, aperture and margins from a single uniformly scaled image."""
    if k not in PHOTO_STEPS:
        raise ValueError('Only verified uniform photo scales are permitted')
    x0, y0, x1, y1 = ((369,223,1077,817) if v2_active() else APERTURE)
    outer_w, outer_h = round(SOURCE_W * k), round(SOURCE_H * k)
    l, t = round(x0 * k), round(y0 * k)
    r, b = round((SOURCE_W - x1) * k), round((SOURCE_H - y1) * k)
    return dict(k=k, l=l, t=t, r=r, b=b,
                outer_w=outer_w, outer_h=outer_h,
                aperture_w=outer_w - l - r, aperture_h=outer_h - t - b)


def photo_fit_size(available_width, available_height):
    """Largest approved frame that fits without stretching, including rounding."""
    fitting = [k for k in PHOTO_STEPS if
               photo_geometry(k)['outer_w'] <= available_width and
               photo_geometry(k)['outer_h'] <= available_height]
    k = max(fitting) if fitting else PHOTO_STEPS[0]
    g = photo_geometry(k)
    return g['outer_w'], g['outer_h']


def _blend_hex(dim: str, bright: str, q: float) -> str:
    q = max(0.0, min(1.0, float(q)))
    da = [int(dim[i:i + 2], 16) for i in (1, 3, 5)]
    ba = [int(bright[i:i + 2], 16) for i in (1, 3, 5)]
    vals = [round(d + (b - d) * q) for d, b in zip(da, ba)]
    return '#%02x%02x%02x' % tuple(vals)


def _soft_glow_png(rx, ry, color, opacity):
    """Generate an alpha-feathered illumination sprite, never a drawn square.

    A tiny PNG is generated once per glow palette/scale and cached by Tk. It
    applies lighting to the original photographic pixel art; no opaque painted
    rectangle or pixel tile is ever laid across the source border.
    """
    rx, ry = max(2, int(round(rx))), max(2, int(round(ry)))
    width, height = rx * 2 + 1, ry * 2 + 1
    rgb = bytes(int(color[i:i + 2], 16) for i in (1, 3, 5))
    raw = bytearray()
    for y in range(height):
        raw.append(0)  # PNG filter None
        for x in range(width):
            d = ((x-rx) / float(rx)) ** 2 + ((y-ry) / float(ry)) ** 2
            # Very smooth bloom fading to true transparency at every edge.
            fade = (max(0., 1. - d) ** 3) if d < 1 else 0.
            alpha = round(min(255, opacity * fade))
            raw.extend(rgb)
            raw.append(alpha)

    def chunk(name, contents):
        return (struct.pack('>I', len(contents)) + name + contents +
                struct.pack('>I', zlib.crc32(name + contents) & 0xffffffff))

    png = (b'\x89PNG\r\n\x1a\n' +
           chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0)) +
           chunk(b'IDAT', zlib.compress(bytes(raw), level=5)) +
           chunk(b'IEND', b''))
    return base64.b64encode(png)


def _crosshair_px(image):
    """Centre of the photographed radar, in pixels of the frame as displayed.

    The sweep has to start on that dot. A fixed source coordinate drifts
    whenever the frame is scaled to a window that is not an exact step.
    Pillow only: the Windows build does not ship numpy.
    """
    w, h = image.size
    x0, x1 = int(w * 0.88), min(w - 1, int(w * 0.995))
    y0, y1 = int(h * 0.11), min(h - 1, int(h * 0.205))
    if x1 - x0 < 8 or y1 - y0 < 8:
        return None
    crop = image.convert("RGB").crop((x0, y0, x1, y1))
    pix = crop.load()
    cw, ch = crop.size
    sx = sy = n = 0
    minx, maxx = cw, 0
    for y in range(ch):
        for x in range(cw):
            r, g, b = pix[x, y]
            if g > 150 and g > r + 25 and g > b:
                sx += x
                sy += y
                n += 1
                if x < minx:
                    minx = x
                if x > maxx:
                    maxx = x
    if n < 40:
        return None
    return (int(round(sx / float(n) + x0)), int(round(sy / float(n) + y0)),
            max(8.0, (maxx - minx) * 0.46))


def _quiet_chin_glow(image):
    """Drop the neon rim on the chin keys. The metal and the legends stay.

    The photographic masters paint a purple line along the top of every
    chin button. That is the glow under the keys. It is recolored to the
    grey of the cap, in place, and nothing outside that band is touched.
    """
    image = image.convert("RGBA")
    pix = image.load()
    w, h = image.size
    y0, y1 = int(h * 0.828), int(h * 0.862)
    x0, x1 = int(w * 0.20), int(w * 0.84)
    for y in range(max(0, y0), min(h, y1)):
        for x in range(max(0, x0), min(w, x1)):
            r, g, b, a = pix[x, y]
            if a and b > g + 8 and r > g + 4:
                m = (r + g) // 2
                pix[x, y] = (m, (g + m) // 2, (g * 3 + m) // 4, a)
    return image


# Chin keys, in the same order as BZ_BTNS + BZ_WIN. Source pixels of the
# 1448x1086 master: centre, then half width and half height of the cap.
_CHIN = (
    (403.25, 952.0, 44.0, 48.0),
    (511.75, 952.0, 43.0, 48.0),
    (617.5, 952.0, 42.0, 48.0),
    (719.5, 952.0, 40.0, 48.0),
    (820.0, 952.0, 40.0, 48.0),
    (932.0, 952.0, 31.0, 46.0),
    (1005.5, 952.0, 31.0, 46.0),
    (1080.0, 952.0, 31.0, 46.0),
)
# Six rotary knobs used to sit on the cheeks. Seam keeps only the left
# volume knob. The right knob and the four small knobs are gone.
_DIALS = (
    ("dial:vol", 85.0, 318.0, 39.0),
)
# The volume needle only travels the upper half: 9 o'clock, over the top,
# to 3 o'clock. A lamp sits every 10 degrees on that arc.
VOL_LO = -90.0
VOL_HI = 90.0
VOL_SWEEP = 180.0
VOL_LAMPS = tuple(range(-90, 91, 20))
VOL_RING = 54.0


def vol_angle(vol):
    """Needle angle for a volume in 0..1. -90 is off, +90 is full."""
    vol = 0.0 if vol < 0.0 else 1.0 if vol > 1.0 else vol
    return VOL_LO + vol * VOL_SWEEP


def vol_level(angle):
    """Volume in 0..1 for a needle angle, clamped to the upper half."""
    if angle < VOL_LO:
        angle = VOL_LO
    elif angle > VOL_HI:
        angle = VOL_HI
    return (angle - VOL_LO) / VOL_SWEEP


# The flat of the knob, inside the knurled skirt. The skirt and the orange
# ring stay in the photograph and do not turn.
DIAL_FACE = 30.5


def dial_face_image(diameter):
    """A round cap drawn straight on.

    The shading is a function of distance from the centre only, so the cap
    can sit still while the needle turns. Nothing here is a side light.
    """
    from PIL import Image, ImageDraw
    d = max(16, int(diameter))
    im = Image.new("RGBA", (d, d), (0, 0, 0, 0))
    px = im.load()
    c = (d - 1) / 2.0
    rad = c - 1.0
    for y in range(d):
        for x in range(d):
            dx, dy = x - c, y - c
            r = math.hypot(dx, dy)
            if r > rad:
                continue
            u = r / rad
            base = 28 + 22 * (1.0 - u) ** 1.4
            groove = 7.0 * math.sin(u * 46.0 * math.pi) * (0.35 + 0.65 * u)
            ring = 10.0 if 0.78 < u < 0.90 else (-8.0 if u >= 0.90 else 0.0)
            v = max(0.0, min(255.0, base + groove + ring))
            px[x, y] = (int(v * 1.02), int(v), int(v * 0.94), 255)
    dr = ImageDraw.Draw(im)
    bore = d * 0.06
    dr.ellipse((c - bore, c - bore, c + bore, c + bore), fill=(12, 12, 14, 255))
    return im


def dial_needle_image(diameter):
    """The pointer only. This is the piece that turns with the volume."""
    from PIL import Image, ImageDraw
    d = max(16, int(diameter))
    im = Image.new("RGBA", (d, d), (0, 0, 0, 0))
    c = (d - 1) / 2.0
    rad = c - 1.0
    tip = c - rad * 0.86
    width = max(3, d // 22)
    dr = ImageDraw.Draw(im)
    dr.line((c, c, c, tip), fill=(255, 214, 150, 255), width=width)
    dot = max(3.0, d * 0.07)
    dr.ellipse((c - dot, tip - dot, c + dot, tip + dot), fill=(255, 150, 30, 255))
    return im


def button_cap_mask(crop):
    """The raised key only. The well under it, and the screen lip, stay put."""
    from PIL import Image, ImageDraw
    w, h = crop.size
    if w < 8 or h < 8:
        return Image.new("L", (w, h), 0)
    lum = crop.convert("L")
    px = lum.load()
    cx, cy = w // 2, h // 2

    def walk(x, y, dx, dy):
        while 0 <= x + dx < w and 0 <= y + dy < h and px[x + dx, y + dy] >= 14:
            x += dx
            y += dy
        return x, y

    left, _ = walk(cx, cy, -1, 0)
    right, _ = walk(cx, cy, 1, 0)
    _, top = walk(cx, max(0, cy - 8), 0, -1)
    _, bot = walk(cx, min(h - 1, cy + 8), 0, 1)

    def bevel(x, y, dx, dy):
        steps = 0
        while steps < 8 and 0 <= x + dx < w and 0 <= y + dy < h and px[x + dx, y + dy] > 60:
            x += dx
            y += dy
            steps += 1
        return x, y

    left, _ = bevel(left, cy, -1, 0)
    right, _ = bevel(right, cy, 1, 0)
    _, top = bevel(cx, top, 0, -1)
    _, bot = bevel(cx, bot, 0, 1)
    if right - left < 8 or bot - top < 8:
        return Image.new("L", (w, h), 0)
    mask = Image.new("L", (w, h), 0)
    rad = max(6, int(min(right - left, bot - top) * 0.18))
    ImageDraw.Draw(mask).rounded_rectangle((left, top, right, bot), radius=rad, fill=255)
    return mask


def dial_light_image(diameter):
    """Studio glint. Drawn once and never rotated, so the light stays put."""
    from PIL import Image, ImageDraw, ImageFilter
    d = max(16, int(diameter))
    im = Image.new("RGBA", (d, d), (0, 0, 0, 0))
    ImageDraw.Draw(im).ellipse((d * 0.18, d * 0.12, d * 0.62, d * 0.48), fill=(255, 244, 220, 70))
    return im.filter(ImageFilter.GaussianBlur(max(1, d * 0.06)))


# Blank keys for sections that do not exist yet. Source pixels of the
# 1448x1086 master: centre, then half width and half height of the cap.
_SPARE = (
    ("bz11", 58.0, 564.0, 24.0, 26.0),
    ("bz12", 114.0, 564.0, 24.0, 26.0),
    ("bz13", 1363.0, 258.0, 34.0, 26.0),
    ("bz14", 1363.0, 342.0, 34.0, 22.0),
    ("bz15", 1334.0, 562.0, 20.0, 24.0),
    ("bz16", 1390.0, 562.0, 20.0, 24.0),
)


class PhotoBezelMixin:
    def _src(self, g, x, y):
        sx, sy = getattr(self, "_frame_scale", (g["k"], g["k"]))
        return x * sx - self.mg[0], y * sy - self.mg[1]

    def _bezel_photo(self):
        if v2_active():
            from oracle_crt_v2 import install
            return install(self)
        z = photo_zip()
        if z is None:
            return False
        import tkinter as tk
        # Scale implied by the margins the window was actually given.
        k = next((s for s in PHOTO_STEPS if photo_geometry(s)["l"] == self.mg[0]
                  and photo_geometry(s)["t"] == self.mg[1]), None)
        if k is None:
            k = photo_step(min((self.W + self.mg[0] + self.mg[2]) / float(SOURCE_W),
                               (self.H + self.mg[1] + self.mg[3]) / float(SOURCE_H)))
        g = photo_geometry(k)
        master_key = None
        # Exact baked frame first, otherwise the largest master we shipped.
        # Patina is a second photograph of the same housing. If that file is
        # missing, the stock frame is used so an older zip still opens.
        stem = photo_frame_stem(getattr(self, "bezel_theme", "stock"))
        names = z.namelist()
        exact = "k%04d/%s.png" % (round(k * 1000), stem)
        if exact in names:
            master_key = exact
        else:
            for step in reversed(PHOTO_STEPS):
                cand = "k%04d/%s.png" % (round(step * 1000), stem)
                if cand in names:
                    master_key = cand
                    break
            if master_key is None and stem != "frame":
                for step in reversed(PHOTO_STEPS):
                    cand = "k%04d/frame.png" % round(step * 1000)
                    if cand in names:
                        master_key = cand
                        break
        if master_key is None:
            return False
        self._dedicated_photo_seats = 'metadata/seats_v2.json' in names
        raw = z.read(master_key)
        tw = self.mg[0] + self.W + self.mg[2]
        th = self.mg[1] + self.H + self.mg[3]
        raw = fit_frame_png(raw, tw, th)
        self._frame_scale = (tw / float(SOURCE_W), th / float(SOURCE_H))
        self._radar_hit = None
        self._frame_im = None
        try:
            from PIL import Image
            from io import BytesIO
            frame = _quiet_chin_glow(Image.open(BytesIO(raw)))
            self._frame_im = frame
            self._radar_hit = _crosshair_px(frame)
            buf = BytesIO()
            frame.save(buf, "PNG")
            raw = buf.getvalue()
        except Exception:
            self._frame_im = None
            self._radar_hit = None
        import tempfile, os
        fd, tmp = tempfile.mkstemp(suffix=".png")
        os.write(fd, raw)
        os.close(fd)
        try:
            image = tk.PhotoImage(master=self.c, file=tmp)
        finally:
            try:
                os.unlink(tmp)
            except Exception:
                pass
        self.bz_imgs.append(image)
        c = self.c
        c.create_image(-self.mg[0], -self.mg[1], image=image, anchor="nw", tags="bezel")
        try:
            self._bezel_photo_rest(g, c, k)
        except Exception:
            pass
        # Chin keys and the six dials. The press and the spin are photographs
        # of the same caps, shifted or rotated. No glow is drawn under them.
        self.bz_btns = []
        self.dial_hot = []
        self.bz_dials = []
        sx, sy = self._frame_scale
        try:
            for (label, action), (bx, by, hw, hh) in zip(
                    list(self.BZ_BTNS) + list(self.BZ_WIN), _CHIN):
                cx, cy = self._src(g, bx, by)
                half_w, half_h = hw * sx, hh * sy
                frames = self._press_frames(bx, by, hw, hh)
                if not frames:
                    continue
                ox, oy = self._src(g, bx - hw, by - hh)
                overlay = c.create_image(ox, oy, image=frames[0], anchor="nw",
                                         state="hidden", tags="bezel")
                self.bz_btns.append(dict(name=action, down=False, until=0.0,
                                         photo_overlay=overlay, frames=frames,
                                         art=(frames[0], frames[-1]), fi=-1))
                self.hot.append((cx - half_w, cy - half_h, cx + half_w, cy + half_h, action))
            for action, bx, by, hw, hh in _SPARE:
                frames = self._press_frames(bx, by, hw, hh)
                if not frames:
                    continue
                ox, oy = self._src(g, bx - hw, by - hh)
                overlay = c.create_image(ox, oy, image=frames[0], anchor="nw",
                                         state="hidden", tags="bezel")
                self.bz_btns.append(dict(name=action, down=False, until=0.0,
                                         photo_overlay=overlay, frames=frames,
                                         art=(frames[0], frames[-1]), fi=-1))
                cx, cy = self._src(g, bx, by)
                half_w, half_h = hw * sx, hh * sy
                self.hot.append((cx - half_w, cy - half_h, cx + half_w, cy + half_h, action))
            self._install_dials(g, c)
        except Exception:
            pass
        self._frame_im = None
        return True
    def _bezel_photo_rest(self, g, c, k):
        self.bz_led = self.bz_neon = self.bz_spark = None
        self.bz_chase = self.bz_vu = self.bz_mspark = None
        # Light sprites for the scanner, the radar pip and the instrument
        # lamps only. The chin keys and the dials are not lit from here.
        self._bezel_glow_cache = {}
        self._bezel_glow_scale = getattr(self, "_frame_scale", (k, k))[0]
        self._photo_instruments(g)
        return True

    def _glow_sprites(self, purpose, color, rx, ry, peak=70):
        import tkinter as tk
        k = self._bezel_glow_scale
        key = (purpose, color, round(rx * k), round(ry * k), peak)
        cache = self._bezel_glow_cache
        if key not in cache:
            # Up to six pre-composited photographic glows. Runtime changes
            # only image pointers: no Canvas pixel squares or new frames.
            imgs = []
            for level in range(7):
                opacity = round(peak * level / 6)
                image = tk.PhotoImage(master=self.c,
                         data=_soft_glow_png(rx * k, ry * k, color, opacity))
                self.bz_imgs.append(image)
                imgs.append(image)
            cache[key] = imgs
        return cache[key]

    def _photo_instruments(self, g):
        import tkinter as tk
        c, k = self.c, g['k']
        a = {'start': None, 'lamps': [], 'meters': [], 'lights': [], 'waves': [], 'clock': [], 'time': None, 'audio_frame': -1}
        self.photo_animate = a

        def lamp(x, y, palette, purpose, rx, ry, peak=70, speed=1., phase=0.):
            pics = self._glow_sprites(purpose, palette, rx, ry, peak=peak)
            cx, cy = self._src(g, x, y)
            item = c.create_image(cx, cy, image=pics[0], anchor='center', tags='bezel')
            return dict(item=item, images=pics, speed=speed, phase=phase,
                        last=-1)

        # Quench: the brow scanner is a dark grate. No cyan chase is drawn on it.

        # The radar scope left with the right-hand knob. Nothing sweeps there.
        a['radar'] = None

        a['meters'] = []

        # Four glass nixie tubes fill the orange scope. The photograph under
        # them is covered so the waveform does not show through the glass.
        from oracle_nixie import NixieState, nixie_frames, bay_back_png, bay_mesh_png, plate_png
        a['nixie'] = NixieState()
        a['clock'] = []
        a['nixie_frames'] = {}
        # The opening is flush with the left edge of the case and rounds
        # toward the screen on the right. Tubes sit in the straight part.
        bay = (26.0, 128.0, 190.0, 210.0)
        cut_frac = 368.0 / 444.0
        visible_h = (bay[3] - bay[1]) - 8.0
        tw_src, th_src, gap = 36.0, visible_h / cut_frac, 4.0
        row = tw_src * 4 + gap * 3
        origin = bay[0] + ((bay[2] - bay[0]) - row) / 2.0
        cy = bay[1] + 4.0 + th_src / 2.0
        bw = max(8, round((bay[2] - bay[0]) * k))
        bh = max(8, round((bay[3] - bay[1]) * k))
        back = bay_back_png(bw, bh, (0.7, 0.7, 0.7, 0.7))
        if back:
            img = tk.PhotoImage(master=c, data=base64.b64encode(back))
            self.bz_imgs.append(img)
            a['wire_item'] = c.create_image(*self._src(g, bay[0], bay[1]), image=img, anchor='nw', tags='bezel')
            a['wire_bank'] = {}
            a['wire_key'] = None
            a['wire_size'] = (bw, bh)
        tw, th = max(8, round(tw_src * k)), max(16, round(th_src * k))
        for d in range(10):
            frames = []
            for raw in nixie_frames(str(d), tw, th, steps=9):
                photo = tk.PhotoImage(master=c, data=base64.b64encode(raw))
                self.bz_imgs.append(photo)
                frames.append(photo)
            if frames:
                a['nixie_frames'][str(d)] = frames
        blank = (a['nixie_frames'].get('0') or [None])[-1]
        for i in range(4):
            sx = origin + tw_src / 2.0 + i * (tw_src + gap)
            x, y = self._src(g, sx, cy)
            digit = c.create_image(x, y, image=blank, anchor='center', tags='bezel') if blank else None
            a['clock'].append(dict(digit=digit, x=x, y=y, last=None, level=None))
        mesh = bay_mesh_png(bw, bh)
        if mesh:
            img = tk.PhotoImage(master=c, data=base64.b64encode(mesh))
            self.bz_imgs.append(img)
            c.create_image(*self._src(g, bay[0], bay[1]), image=img, anchor='nw', tags='bezel')

        # Left scope is the speaker. The right glass is the CPU and GPU readout.
        scopes = (
            ('wave', (36, 458, 136, 518), 44, 128, 486, 22, '#58f89c'),
        )
        for name, plate, x0, x1, y, half, color in scopes:
            pw = max(8, round((plate[2] - plate[0]) * k))
            ph = max(8, round((plate[3] - plate[1]) * k))
            raw = plate_png(pw, ph, (1, 8, 4, 255))
            if raw and not getattr(self, '_dedicated_photo_seats', False):
                img = tk.PhotoImage(master=c, data=base64.b64encode(raw))
                self.bz_imgs.append(img)
                px, py = self._src(g, plate[0], plate[1])
                c.create_image(px, py, image=img, anchor='nw', tags='bezel')
            item = c.create_line(*self._src(g, x0, y), *self._src(g, x1, y),
                                 fill=color, width=max(1, round(1.6 * k)),
                                 smooth=False, capstyle='round', tags='bezel')
            a['waves'].append(dict(name=name, x0=x0, x1=x1, y=y, amp=half,
                                   item=item, hist=[0.35] * 48))

        # Right glass: CPU and GPU temperature, then usage.
        glass_r = (1316, 460, 1410, 508)
        gw = glass_r[2] - glass_r[0]
        gh = glass_r[3] - glass_r[1]
        gp = plate_png(max(8, round(gw * k)), max(8, round(gh * k)), (2, 8, 4, 255))
        if gp and not getattr(self, '_dedicated_photo_seats', False):
            img = tk.PhotoImage(master=c, data=base64.b64encode(gp))
            self.bz_imgs.append(img)
            px, py = self._src(g, glass_r[0], glass_r[1])
            c.create_image(px, py, image=img, anchor='nw', tags='bezel')
        lab_px = max(7, round(gh * 0.22 * k))
        num_px = max(8, round(gh * 0.30 * k))
        font_l = ('Uberata Clear', lab_px, 'bold')
        font_n = ('Uberata Clear', num_px, 'bold')
        col_x = (glass_r[0] + gw * 0.27, glass_r[0] + gw * 0.73)
        row_y = (glass_r[1] + gh * 0.20, glass_r[1] + gh * 0.50, glass_r[1] + gh * 0.80)
        a['readout'] = {}
        for key, sx, sy, font, fill, text in (
                ('cpu_l', col_x[0], row_y[0], font_l, '#8fbfa0', 'CPU'),
                ('gpu_l', col_x[1], row_y[0], font_l, '#e0c080', 'GPU'),
                ('cpu_t', col_x[0], row_y[1], font_n, '#e8fff2', '--'),
                ('gpu_t', col_x[1], row_y[1], font_n, '#ffe7b8', '--'),
                ('cpu_p', col_x[0], row_y[2], font_n, '#b8ffd2', '--'),
                ('gpu_p', col_x[1], row_y[2], font_n, '#ffd48a', '--'),
        ):
            x, y = self._src(g, sx, sy)
            a['readout'][key] = c.create_text(x, y, text=text, anchor='center',
                                              fill=fill, font=font, tags='bezel')
        for item in a['readout'].values():
            c.tag_raise(item)

        def mix(t):
            if t < 0.5:
                u = t / 0.5
                rgb = (int(48 + 207 * u), int(255 - 35 * u), int(72 - 40 * u))
            else:
                u = (t - 0.5) / 0.5
                rgb = (255, int(220 - 184 * u), int(32 - 10 * u))
            return '#%02x%02x%02x' % rgb

        slots = ((796, 803), (784, 791), (772, 779), (759, 766),
                 (746, 753), (734, 741), (722, 729), (710, 717), (698, 705))
        colors = [mix(i / 8.0) for i in range(9)]
        a['bars'] = {'colors': colors, 'cpu': [], 'gpu': []}

        def stack(name, x0, x1):
            for i, (y0, y1) in enumerate(slots):
                ax, ay = self._src(g, x0, y0)
                bx, by = self._src(g, x1, y1)
                off = self._flat(bx - ax, by - ay, '#0c120e')
                item = c.create_image(ax, ay, image=off, anchor='nw', tags='bezel')
                a['bars'][name].append(dict(item=item, off=off, on=colors[i],
                                            w=max(1, bx - ax), h=max(1, by - ay), cur=off))

        stack('cpu', 79, 96)
        stack('gpu', 1351, 1368)

        # Quench: the side indicator lamps are bare plate metal. Nothing is lit there.

        self.photo_animate = a

    def _ring_points(self):
        # Just outside the metal opening, so the spark rides the lip.
        x0, y0, x1, y1 = APERTURE
        box = (x0 - 12, y0 - 10, x1 + 12, y1 + 8)
        rad = 88
        x0, y0, x1, y1 = box
        w = x1 - x0 - 2 * rad
        h = y1 - y0 - 2 * rad
        perim = 2 * (w + h) + 2 * math.pi * rad
        return [self.groove_point(box, rad, perim * i / 36.0) for i in range(36)]

    def _lip_points(self):
        return [(280 + i * (880 / 19.0), 888) for i in range(20)]

    def _chase_chain(self, g, points, color, purpose, rx, ry, peak=80):
        pics = self._glow_sprites(purpose, color, rx, ry, peak=peak)
        items = []
        for x, y in points:
            cx, cy = self._src(g, x, y)
            items.append(self.c.create_image(cx, cy, image=pics[0], anchor='center', tags='bezel'))
        return dict(items=items, images=pics, last=[-1] * len(items))

    def _chase(self, chain, elapsed, speed, closed=True):
        if not chain or not chain['items']:
            return
        c = self.c
        n = len(chain['items'])
        pos = (elapsed * speed) % n
        for i, item in enumerate(chain['items']):
            d = abs(i - pos)
            if closed:
                d = min(d, n - d)
            q = max(0.0, 1.0 - d / 3.2)
            level = max(0, min(6, round(q * 6)))
            if level != chain['last'][i]:
                c.itemconfigure(item, image=chain['images'][level])
                chain['last'][i] = level

    def _photo_tick(self, now):
        if v2_active():
            from oracle_crt_v2 import tick
            return tick(self, now)
        a = getattr(self, 'photo_animate', None)
        if not a:
            return
        if a['start'] is None:
            a['start'] = now
        elapsed = now - a['start']
        c = self.c
        k = getattr(self, "_frame_scale", (1.0, 1.0))[0]
        sy = getattr(self, "_frame_scale", (k, k))[1]

        # Scanner bulbs used to chase here. Quench leaves that grate dark.
        if a['lamps']:
            lamp_pos = (elapsed * 4.6) % len(a['lamps'])
            for i, glow in enumerate(a['lamps']):
                d = min(abs(i - lamp_pos), len(a['lamps']) - abs(i - lamp_pos))
                q = max(0., 1. - d / 3.0)
                level = max(0, min(6, round(q * 6)))
                if level != glow['last']:
                    c.itemconfigure(glow['item'], image=glow['images'][level])
                    glow['last'] = level

        # Radar sweep removed. The cheek where it sat is blank keys now.
        nix = a.get('nixie')
        frames = a.get('nixie_frames') or {}
        if nix and frames:
            now = datetime.datetime.now()
            nix.update(now, 1.0 / 30.0)
            for i, tube in enumerate(a['clock']):
                ch = nix.digits[i]
                bank = frames.get(ch) or []
                if not bank or not tube.get('digit'):
                    continue
                glow = nix.glow(i, now)
                level = int(round((glow - 0.72) / 0.28 * (len(bank) - 1)))
                level = max(0, min(len(bank) - 1, level))
                if ch != tube.get('last') or level != tube.get('level'):
                    c.itemconfigure(tube['digit'], image=bank[level])
                    tube['last'] = ch
                    tube['level'] = level
            wire_item = a.get('wire_item')
            if wire_item:
                key = tuple(max(0, min(4, int(round((nix.glow(i, now) - 0.72) / 0.28 * 4))))
                            for i in range(4))
                if key != a.get('wire_key'):
                    bank = a.setdefault('wire_bank', {})
                    img = bank.get(key)
                    if img is None:
                        import tkinter as tk
                        from oracle_nixie import bay_back_png
                        bw, bh = a['wire_size']
                        raw = bay_back_png(bw, bh, tuple(v / 4.0 for v in key))
                        img = tk.PhotoImage(master=c, data=base64.b64encode(raw))
                        self.bz_imgs.append(img)
                        bank[key] = img
                    c.itemconfigure(wire_item, image=img)
                    a['wire_key'] = key

        frame = int(elapsed * 15)
        if frame != a['audio_frame']:
            a['audio_frame'] = frame
            audio = getattr(getattr(self, 'host', None), 'system_audio', None)
            samples, bands, status = (audio.snapshot() if audio else
                                      ((0.0,) * 48, (0.0,) * 20, 'OFF'))
            l, t = self.mg[0], self.mg[1]
            try:
                from oracle_sysmetrics import cpu_percent, cpu_temp_c, gpu_temp_c, gpu_util
                cpu = cpu_percent()
                cpu_c = cpu_temp_c()
                gpu_c = gpu_temp_c()
                gpu_u = gpu_util()
            except Exception:
                cpu = cpu_c = gpu_c = gpu_u = None
            energy = sum(abs(v) for v in samples)
            for w in a['waves']:
                pts = []
                if w['name'] == 'wave':
                    # Genuine captured speaker output only. Missing audio or
                    # quiet PC means a stationary trace, never fabricated sound.
                    values = samples if status == 'LIVE' else (0.0,) * 48
                    for n, v in enumerate(values):
                        sx = w['x0'] + (w['x1'] - w['x0']) * n / max(1, len(values) - 1)
                        pts.extend((sx * k - l, (w['y'] - v * w['amp']) * sy - t))
                if len(pts) >= 4:
                    c.coords(w['item'], *pts)

            def pct(v):
                return '--' if v is None else '%d%%' % round(v * 100)

            def deg(v):
                return '--' if v is None else '%d\u00b0' % round(v)

            rows = a.get('readout') or {}
            if rows:
                c.itemconfigure(rows['cpu_t'], text=deg(cpu_c))
                c.itemconfigure(rows['gpu_t'], text=deg(gpu_c))
                c.itemconfigure(rows['cpu_p'], text=pct(cpu))
                c.itemconfigure(rows['gpu_p'], text=pct(gpu_u))

            bars = a.get('bars')
            if bars:
                colors = bars['colors']
                nseg = len(colors)
                # The top lit segment breathes so a steady reading still moves.
                breath = 0.5 + 0.5 * math.sin(elapsed * 8.0)

                def paint(name, value):
                    lit = 0 if value is None else max(0, min(nseg, int(round((value or 0) * nseg))))
                    # No synthetic sensor readings on unavailable hardware.
                    if value is None:
                        lit = 0
                    for i, seg in enumerate(bars[name]):
                        if i < lit:
                            color = colors[i]
                            if i == lit - 1 and breath > 0.65:
                                color = '#f4ffe8'
                        else:
                            color = '#070a08'
                        img = seg['off'] if color == '#070a08' else self._flat(seg['w'], seg['h'], color)
                        if img is not seg.get('cur'):
                            c.itemconfigure(seg['item'], image=img)
                            seg['cur'] = img

                paint('cpu', cpu)
                paint('gpu', gpu_u)

        # Indicator lights and decorative buttons: no pixel-art cubes.
        for glow in a['lights']:
            q = .20 + .80 * (.5 + .5 * math.sin(
                elapsed * glow['speed'] * 2 + glow['phase'] * math.tau))
            level = max(0, min(6, round(q * 6)))
            if level != glow['last']:
                c.itemconfigure(glow['item'], image=glow['images'][level])
                glow['last'] = level

    def _flat(self, w, h, color):
        import tkinter as tk
        w, h = max(1, int(round(w))), max(1, int(round(h)))
        cache = getattr(self, '_flat_cache', None)
        if cache is None:
            cache = self._flat_cache = {}
        key = (w, h, color)
        if key in cache:
            return cache[key]
        rgb = [int(color[i:i + 2], 16) for i in (1, 3, 5)]
        row = bytearray(rgb + [255]) * w
        image = tk.PhotoImage(master=self.c, data=base64.b64encode(_png_bytes(w, h, [row] * h)))
        self.bz_imgs.append(image)
        cache[key] = image
        return image

    def _photo_from_pil(self, im):
        import tkinter as tk
        from io import BytesIO
        buf = BytesIO()
        im.save(buf, 'PNG')
        image = tk.PhotoImage(master=self.c, data=base64.b64encode(buf.getvalue()))
        self.bz_imgs.append(image)
        return image

    def _press_frames(self, cx, cy, hw, hh):
        """Four pictures of one push-button. The whole cap sinks toward its centre.

        A vertical slide left the sides of the key where they were, which is
        how a switch looks. A push-button moves as one piece.
        """
        im = getattr(self, '_frame_im', None)
        if im is None:
            return []
        from PIL import Image, ImageEnhance, ImageChops, ImageDraw
        sx, sy = self._frame_scale
        x0 = max(0, int(round((cx - hw) * sx)))
        y0 = max(0, int(round((cy - hh) * sy)))
        x1 = min(im.size[0], int(round((cx + hw) * sx)))
        y1 = min(im.size[1], int(round((cy + hh) * sy)))
        if x1 - x0 < 6 or y1 - y0 < 6:
            return []
        crop = im.crop((x0, y0, x1, y1)).convert('RGBA')
        mask = button_cap_mask(crop)
        w, h = crop.size
        frames = []
        # Same size on every frame. Shrinking the cap showed the real key behind it.
        for step in range(4):
            body = ImageEnhance.Brightness(crop).enhance(1.0 - 0.018 * step)
            body.putalpha(mask)
            if step:
                band = Image.new('RGBA', (w, h), (0, 0, 0, 0))
                ImageDraw.Draw(band).rectangle((0, 0, w, 1 + step), fill=(0, 0, 0, 50 + 16 * step))
                band.putalpha(ImageChops.multiply(band.getchannel('A'), mask))
                body = Image.alpha_composite(body, band)
            frames.append(self._photo_from_pil(body))
        return frames

    def _knob_frames(self, cx, cy, rad):
        """Needle positions. The cap and the glint are separate and do not turn."""
        from PIL import Image
        sx, sy = self._frame_scale
        rr = max(8, int(round(rad * (sx + sy) / 2.0)))
        self._dial_face = self._photo_from_pil(dial_face_image(rr * 2))
        self._dial_light = self._photo_from_pil(dial_light_image(rr * 2))
        needle = dial_needle_image(rr * 2)
        frames = []
        for i in range(36):
            rot = needle.rotate(-i * 10.0, resample=Image.BICUBIC, expand=False,
                                fillcolor=(0, 0, 0, 0))
            frames.append(self._photo_from_pil(rot))
        return frames

    def _install_dials(self, g, c):
        self.bz_dials = []
        self.vol_lamps = []
        self.dial_hot = []
        sx, sy = self._frame_scale
        for name, bx, by, rad in _DIALS:
            frames = self._knob_frames(bx, by, DIAL_FACE)
            if not frames:
                continue
            cx, cy = self._src(g, bx, by)
            hit = rad * (sx + sy) / 2.0 * 1.7
            vol = 0.8
            voice = getattr(self, 'voice', None)
            if voice is not None:
                try:
                    vol = max(0.0, min(1.0, float(voice.vol)))
                except Exception:
                    vol = 0.8
            angle = vol_angle(vol) if name == 'dial:vol' else 0.0
            idx = int(round(angle / 10.0)) % len(frames)
            face = getattr(self, '_dial_face', None)
            if face is not None:
                c.create_image(cx, cy, image=face, anchor='center', tags='bezel')
            light = getattr(self, '_dial_light', None)
            if light is not None:
                c.create_image(cx, cy, image=light, anchor='center', tags='bezel')
            item = c.create_image(cx, cy, image=frames[idx], anchor='center', tags='bezel')
            c.tag_raise(item)
            self.dial_hot.append((cx - hit, cy - hit, cx + hit, cy + hit, name))
            self.bz_dials.append(dict(name=name, item=item, frames=frames, cx=cx, cy=cy,
                                      angle=angle, target=angle, fi=idx))
            if name == 'dial:vol':
                self._install_vol_lamps(g, c, bx, by, angle)

    def _tick_press(self, now):
        for b in getattr(self, 'bz_btns', []) or []:
            frames = b.get('frames')
            if not frames:
                continue
            if b.get('down'):
                if now - b.get('step_at', 0.0) < 0.05:
                    continue
                fi = 0 if b.get('fi', -1) < 0 else min(len(frames) - 1, b['fi'] + 1)
                b['step_at'] = now
            elif b.get('release'):
                if now - b.get('step_at', 0.0) < 0.04:
                    continue
                b['step_at'] = now
                fi = b.get('fi', 0) - 1
                if fi < 0:
                    try:
                        self.c.itemconfigure(b['photo_overlay'], state='hidden')
                    except Exception:
                        pass
                    b['fi'] = -1
                    b['release'] = False
                    continue
            else:
                continue
            if fi != b.get('fi'):
                try:
                    self.c.itemconfigure(b['photo_overlay'], image=frames[fi], state='normal')
                except Exception:
                    pass
                b['fi'] = fi

    def _tick_dials(self):
        if v2_active():
            from oracle_crt_v2 import tick_dial
            return tick_dial(self)
        dragging = getattr(self, 'dragging', None)
        voice = getattr(self, 'voice', None)
        for d in getattr(self, 'bz_dials', []) or []:
            if d['name'] == 'dial:vol' and dragging != 'dial:vol' and voice is not None:
                try:
                    d['target'] = vol_angle(float(voice.vol))
                except Exception:
                    pass
            delta = d['target'] - d['angle']
            if delta > 180.0:
                delta -= 360.0
            elif delta < -180.0:
                delta += 360.0
            if abs(delta) < 0.35:
                d['angle'] = d['target']
            else:
                d['angle'] = d['angle'] + max(-12.0, min(12.0, delta))
            idx = int(round(d['angle'] / 10.0)) % len(d['frames'])
            if idx != d.get('fi'):
                try:
                    self.c.itemconfigure(d['item'], image=d['frames'][idx])
                except Exception:
                    pass
                d['fi'] = idx
        self._tick_vol_lamps()

    def _vol_led(self, on, k):
        """A small round lamp. Shared by every mark on the volume arc."""
        from PIL import Image, ImageDraw, ImageFilter
        d = max(16, int(round(13 * k)))
        im = Image.new('RGBA', (d, d), (0, 0, 0, 0))
        if on:
            glow = Image.new('RGBA', (d, d), (0, 0, 0, 0))
            ImageDraw.Draw(glow).ellipse((1, 1, d - 2, d - 2), fill=(50, 255, 120, 210))
            im = Image.alpha_composite(im, glow.filter(ImageFilter.GaussianBlur(max(1, d // 6))))
            core = d // 4
            ImageDraw.Draw(im).ellipse((core, core, d - 1 - core, d - 1 - core), fill=(230, 255, 230, 255))
        else:
            m = d // 5
            dr = ImageDraw.Draw(im)
            dr.ellipse((m, m, d - 1 - m, d - 1 - m), fill=(18, 28, 20, 255))
            dr.ellipse((m, m, d - 1 - m, d - 1 - m), outline=(70, 90, 72, 255))
        return self._photo_from_pil(im)

    def _install_vol_lamps(self, g, c, bx, by, angle):
        k = (self._frame_scale[0] + self._frame_scale[1]) / 2.0
        on, off = self._vol_led(True, k), self._vol_led(False, k)
        self.vol_lamps = []
        for lamp_angle in VOL_LAMPS:
            rad = math.radians(lamp_angle)
            x, y = self._src(g, bx + math.sin(rad) * VOL_RING, by - math.cos(rad) * VOL_RING)
            lit = angle + 0.5 >= lamp_angle
            img = on if lit else off
            item = c.create_image(x, y, image=img, anchor='center', tags='bezel')
            c.tag_raise(item)
            self.vol_lamps.append(dict(angle=lamp_angle, item=item, on=on, off=off, cur=img))

    def _tick_vol_lamps(self):
        lamps = getattr(self, 'vol_lamps', None)
        if not lamps:
            return
        dial = self._dial_by('dial:vol')
        if not dial:
            return
        angle = dial['angle']
        for lamp in lamps:
            img = lamp['on'] if angle + 0.5 >= lamp['angle'] else lamp['off']
            if img is not lamp.get('cur'):
                try:
                    self.c.itemconfigure(lamp['item'], image=img)
                except Exception:
                    pass
                lamp['cur'] = img

    def _dial_by(self, name):
        for d in getattr(self, 'bz_dials', []) or []:
            if d['name'] == name:
                return d
        return None

    def _dial_down(self, name, x, y):
        d = self._dial_by(name)
        if not d:
            return
        d['grab'] = math.degrees(math.atan2(y - d['cy'], x - d['cx']))
        d['base'] = d['target']
        d['base_vol'] = getattr(getattr(self, 'voice', None), 'vol', 0.8)
        d['moved'] = 0.0

    def _dial_drag(self, name, x, y):
        d = self._dial_by(name)
        if not d or 'grab' not in d:
            return
        ang = math.degrees(math.atan2(y - d['cy'], x - d['cx']))
        delta = ang - d['grab']
        if delta > 180.0:
            delta -= 360.0
        elif delta < -180.0:
            delta += 360.0
        d['moved'] = max(d.get('moved', 0.0), abs(delta))
        if name == 'dial:vol':
            d['target'] = max(VOL_LO, min(VOL_HI, d['base'] + delta))
            voice = getattr(self, 'voice', None)
            if voice is not None:
                voice.vol = vol_level(d['target'])
                draw = getattr(self, '_vol_draw', None)
                if draw:
                    try:
                        draw()
                    except Exception:
                        pass
        else:
            d['target'] = d['base'] + delta

    def _dial_up(self, name):
        """A click that did not turn the knob advances one detent."""
        d = self._dial_by(name)
        if not d:
            return
        if d.get('moved', 0.0) < 6.0:
            step = 20.0 if name == 'dial:vol' else 18.0
            d['target'] = d['angle'] + step
            if name == 'dial:vol':
                d['target'] = max(VOL_LO, min(VOL_HI, d['target']))
                voice = getattr(self, 'voice', None)
                if voice is not None:
                    voice.vol = vol_level(d['target'])
                    draw = getattr(self, '_vol_draw', None)
                    if draw:
                        try:
                            draw()
                        except Exception:
                            pass

