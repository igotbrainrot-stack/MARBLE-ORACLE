"""oracle_skin.py -- build 1031: the modern skin (stdlib + tkinter only).  Rounded panels on soft drop shadows, lit header bands with a
neon rule, glass title and menu bars, inset wells for the ticker and status, pill buttons, a glowing knob.

Every piece is drawn here at run time as a small anti-aliased RGBA picture (signed distances, oracle_assets.rgba_png) and cut 9-slice
(panels, shadows) or 3-slice (bars, wells, pills): Tk only places and tiles them, so nothing is stretched or pixelated at any size, and a
resize costs a few thousand Python pixels, not a screenful.  The pictures are cached by their colours and scale.

SkinMixin is the Scene side.  Any failure (an old Tk without PNG alpha, say) turns the skin off and the Scene draws the flat 1030 look,
which --flat also asks for."""
import base64
import math
import random

from oggcultist_design_system import COLOR as OGG_EMBER

from oracle_assets import rgba_png




def _rgb(c):
    return (int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16))


def _mix(a, b, t):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


def hexmix(a, b, t):
    """'#rrggbb' between a and b (t = 0 .. 1)."""
    return "#%02x%02x%02x" % tuple(int(round(v)) for v in _mix(_rgb(a), _rgb(b), t))


def _rr(x, y, x0, y0, x1, y1, r):
    """Signed distance from (x, y) to the rounded rectangle (x0, y0, x1, y1) with corner radius r: negative inside."""
    qx = abs(x - (x0 + x1) * .5) - ((x1 - x0) * .5 - r)
    qy = abs(y - (y0 + y1) * .5) - ((y1 - y0) * .5 - r)
    return math.hypot(max(qx, 0.), max(qy, 0.)) + min(max(qx, qy), 0.) - r


def _cov(d):
    """Pixel coverage of an edge at signed distance d (one pixel of anti-aliasing)."""
    return 0. if d >= .5 else 1. if d <= -.5 else .5 - d


def _fall(d, reach):
    """A soft shadow's strength at distance d outside its shape (1 inside, about gone at `reach`)."""
    return 1. if d <= 0 else math.exp(-(d / (0.42 * reach)) ** 2)


def _over(dst, rgb, a):
    """Composite a straight-alpha colour over a premultiplied [r, g, b, a] pixel, in place."""
    if a <= 0:
        return
    k = 1 - a
    dst[0] = rgb[0] * a + dst[0] * k
    dst[1] = rgb[1] * a + dst[1] * k
    dst[2] = rgb[2] * a + dst[2] * k
    dst[3] = a + dst[3] * k


def raster(w, h, paint, under=None):
    """A w x h picture: paint(px, py, pixel) composites into a premultiplied [r, g, b, a] pixel (px, py = the pixel's centre).
    `under`: an opaque colour to start from.  Tk draws a picture with any part-transparent pixel by reading the screen back and blending,
    which is slow under the moving CRT static, so every large piece is made opaque over the colour it will sit on."""
    base = [float(v) for v in _rgb(under)] + [1.] if under else [0., 0., 0., 0.]
    rows = []
    for y in range(h):
        row = []
        for x in range(w):
            p = list(base)
            paint(x + .5, y + .5, p)
            row.append(p)
        rows.append(row)
    return rows


def png(rows, x=0, y=0, w=None, h=None):
    """The (x, y, w, h) part of a raster as PNG bytes (straight alpha)."""
    w = len(rows[0]) - x if w is None else w
    h = len(rows) - y if h is None else h
    out = []
    for row in rows[y:y + h]:
        buf = bytearray()
        for p in row[x:x + w]:
            a = p[3]
            if a <= 0.002:
                buf += b"\x00\x00\x00\x00"
            else:
                buf += bytes((min(255, int(p[0] / a + .5)), min(255, int(p[1] / a + .5)), min(255, int(p[2] / a + .5)), min(255, int(a * 255 + .5))))
        out.append(bytes(buf))
    return rgba_png(w, h, out)


def nine(rows, C):
    """Cut a (2C + 1)-square raster into corners and one-pixel edge profiles."""
    return dict(tl=png(rows, 0, 0, C, C), tr=png(rows, C + 1, 0, C, C), bl=png(rows, 0, C + 1, C, C), br=png(rows, C + 1, C + 1, C, C),
                top=png(rows, C, 0, 1, C), bottom=png(rows, C, C + 1, 1, C), left=png(rows, 0, C, C, 1), right=png(rows, C + 1, C, C, 1),
                C=C)


def three(rows, C):
    """Cut a (2C + 1)-wide raster into a left cap, a one-pixel middle column and a right cap."""
    h = len(rows)
    return dict(left=png(rows, 0, 0, C, h), mid=png(rows, C, 0, 1, h), right=png(rows, C + 1, 0, C, h), C=C, h=h)


_CACHE = {}


def cached(fn):
    def wrap(*a):
        key = (fn.__name__,) + a
        if key not in _CACHE:
            if len(_CACHE) > 400:                        # many resizes: start again rather than grow
                _CACHE.clear()
            _CACHE[key] = fn(*a)
        return _CACHE[key]
    wrap.__name__ = fn.__name__
    return wrap


@cached
def warm_grain(fill, size=256):
    """Return Oggcultist's own pre-rendered grain+stain PNG tile unchanged.

    Each PNG was baked by the bundled Oggcultist 2.0.6 textures.grain
    function, with exactly the same palette and strength as its ttk theme.
    The previous approximated noise/wave code is intentionally removed.
    """
    from oracle_ogg_texture import png_bytes, role_of
    return png_bytes(role_of(fill, 'card'))


def px(v, k, lo=1):
    return max(lo, int(round(v * k)))


# ------------------------------------------------------------------ the pieces
@cached
def card(k, fill, border, shade=0.55, radius=10, reach=12, drop=3, rim=None, rim_a=0.0, under=None):
    """A panel: dict(shadow=nine, body=nine, fill, R, S).  On a near-black ground a shadow alone barely shows, so an optional rim light (a faint glow
    of the accent just outside the edge) goes with it.  With `under` (the ground's colour) the body set is the whole thing, shadow included, and opaque."""
    R, S, off, bw = px(radius, k, 3), px(reach, k, 3), px(drop, k), px(1, k)
    C = S + R
    n = 2 * C + 1
    f, e = _rgb(fill), _rgb(border)
    box = (S, S, n - S, n - S)

    g = _rgb(rim) if rim else None

    def sh(x, y, p):
        _over(p, (0, 0, 0), shade * _fall(_rr(x, y - off, box[0], box[1], box[2], box[3], R), S))
        if g is not None:
            d = _rr(x, y, box[0], box[1], box[2], box[3], R)
            if d > -.5:
                _over(p, g, rim_a * _fall(d, S * 0.55))

    def body(x, y, p):
        d = _rr(x, y, box[0], box[1], box[2], box[3], R)
        c = _cov(d)
        if c:
            _over(p, _mix(e, f, _cov(d + bw)), c)
    if under:
        def both(x, y, p):
            sh(x, y, p)
            body(x, y, p)
        return dict(shadow=None, body=nine(raster(n, n, both, under), C), fill=fill, R=R, S=S)
    return dict(shadow=nine(raster(n, n, sh), C), body=nine(raster(n, n, body), C), fill=fill, R=R, S=S)


@cached
def header(k, h, top, bottom, radius=10):
    """A panel's header band (h px tall, rounded at the top only, lit along its top edge): three-slice."""
    R = px(radius - 1, k, 2)
    n = 2 * R + 1
    t, b = _rgb(top), _rgb(bottom)
    hi = px(1.5, k)

    def paint(x, y, p):
        c = _cov(_rr(x, y, 0, 0, n, h + 2 * R, R))
        if c:
            col = _mix(t, b, min(1., y / float(h)))
            if y < hi:
                col = _mix(col, (255, 255, 255), 0.22)
            _over(p, col, c)
    return three(raster(n, h, paint), R)


@cached
def bar(k, h, top, bottom, radius=0, border=None, glow=None, glow_a=0.0, inset=0.0, reach=6, sheen=0.0, under=None):
    """A pill, well or bar (h px tall, any width): a vertical gradient, an optional border, an outer glow (buttons) or an inner shadow
    along the top (wells).  Three-slice; the glow margin G is outside the pill on every side (dict 'G')."""
    R = min(px(radius, k, 0), h // 2)
    G = px(reach, k) if glow else 0
    C = G + max(R, 1)
    n, H = 2 * C + 1, h + 2 * G
    t, b = _rgb(top), _rgb(bottom)
    e = _rgb(border) if border else None
    g = _rgb(glow) if glow else None
    bw = px(1, k)
    box = (G, G, n - G, G + h)
    ish = px(3, k)

    def paint(x, y, p):
        d = _rr(x, y, box[0], box[1], box[2], box[3], R) if R else max(box[0] - x, x - box[2], box[1] - y, y - box[3])
        if g is not None and d > -.5:
            _over(p, g, glow_a * _fall(d, G))
        c = _cov(d)
        if not c:
            return
        v = min(1., max(0., (y - G) / float(h)))
        col = _mix(t, b, v)
        if inset:                                           # a well: darker toward its top edge
            col = _mix(col, (0, 0, 0), inset * max(0., 1 - (y - G) / float(ish)))
        if sheen and y - G < h * .5:
            col = _mix(col, (255, 255, 255), sheen * (1 - (y - G) / (h * .5)))
        if e is not None:
            col = _mix(e, col, _cov(d + bw))
        _over(p, col, c)
    out = three(raster(n, H, paint, under), C)
    out["G"] = G
    return out


@cached
def rule(w, a_rgb, b_rgb, a0=0.85, a1=0.0, h=1, under=None):
    """A neon rule w px long: colour a -> b, fading out to the right (opaque over `under`)."""
    A, B = _rgb(a_rgb), _rgb(b_rgb)
    row = []
    for x in range(w):
        t = x / float(max(1, w - 1))
        a = a0 + (a1 - a0) * (t ** 0.7)
        row.append(list(_mix(A, B, min(1., t * 1.6))) + [a])
    if under:
        U = _rgb(under)
        row = [list(_mix(U, p[:3], p[3])) + [1.] for p in row]
    rows = [[[p[0] * p[3], p[1] * p[3], p[2] * p[3], p[3]] for p in row] for _ in range(h)]
    return png(rows)


@cached
def sheen(h, a0=0.05, under="#000000"):
    """A one-pixel column: white fading to nothing over `under`, the light falling down a panel under its header (opaque)."""
    U = _rgb(under)
    rows = []
    for y in range(h):
        a = a0 * (1 - y / float(max(1, h))) ** 2
        rows.append([list(_mix(U, (255, 255, 255), a)) + [1.]])
    return png(rows)


@cached
def dot(d, top, bottom, glow=None, glow_a=0.6, reach=0, radius=None, w=None):
    """A small lit shape: a rounded bar or disc d px tall (w wide, default d), a top -> bottom gradient, a highlight, an optional glow."""
    w = d if w is None else w
    r = d / 2.0 if radius is None else radius
    G = reach
    W, H = w + 2 * G, d + 2 * G
    t, b = _rgb(top), _rgb(bottom)
    g = _rgb(glow) if glow else None

    def paint(x, y, p):
        dd = _rr(x, y, G, G, G + w, G + d, min(r, w / 2.0, d / 2.0))
        if g is not None and dd > -.5:
            _over(p, g, glow_a * _fall(dd, G))
        c = _cov(dd)
        if c:
            v = min(1., max(0., (y - G) / float(d)))
            col = _mix(t, b, v)
            col = _mix(col, (255, 255, 255), 0.35 * max(0., 1 - v * 2.5))
            _over(p, col, c)
    return png(raster(W, H, paint))


# ------------------------------------------------------------------ the Scene side
class SkinMixin:
    """Places the skin's pieces on the Scene canvas (self.c), at self.k, in the theme's colours (self.col)."""

    def skin_on(self):
        return not getattr(self, "o", {}).get("flat") and getattr(self, "skin_ok", True)

    def skin_reset(self):
        """build(): drop the per-size tiles of the last layout (the cached pieces stay)."""
        self.skin_tmp = []
        if len(getattr(self, "skin_ph", {})) > 300:
            self.skin_ph = {}

    def photo(self, data):
        import tkinter
        cache = self.__dict__.setdefault("skin_ph", {})
        im = cache.get(data)
        if im is None:
            im = cache[data] = tkinter.PhotoImage(master=self.c, data=base64.b64encode(data))
        return im

    def tiled(self, data, w, h):
        """A w x h picture repeating the piece (a one-pixel profile along an edge)."""
        import tkinter
        src = self.photo(data)
        if (src.width(), src.height()) == (w, h):
            return src
        big = tkinter.PhotoImage(master=self.c, width=w, height=h)
        self.c.tk.call(str(big), "copy", str(src), "-to", 0, 0, w, h)
        self.__dict__.setdefault("skin_tmp", []).append(big)
        return big

    def put(self, data, x, y, tags, anchor="nw", w=None, h=None):
        im = self.photo(data) if w is None else self.tiled(data, max(1, int(w)), max(1, int(h)))
        return self.c.create_image(int(x), int(y), image=im, anchor=anchor, tags=tags)

    def put_nine(self, art, box, tags, fill=None, out=0):
        """A nine-slice set round box; its corners reach `out` px outside the box (a shadow's reach)."""
        x0, y0, x1, y1 = [int(v) for v in box]
        C = art["C"]
        ins = C - out                                          # how far each corner reaches inside the box
        ax0, ay0, ax1, ay1 = x0 - out, y0 - out, x1 + out - C, y1 + out - C
        iw, ih = (x1 - ins) - (x0 + ins), (y1 - ins) - (y0 + ins)
        ids = [self.put(art["tl"], ax0, ay0, tags), self.put(art["tr"], ax1, ay0, tags),
               self.put(art["bl"], ax0, ay1, tags), self.put(art["br"], ax1, ay1, tags)]
        if iw > 0:
            ids += [self.put(art["top"], x0 + ins, ay0, tags, w=iw, h=C), self.put(art["bottom"], x0 + ins, ay1, tags, w=iw, h=C)]
        if ih > 0:
            ids += [self.put(art["left"], ax0, y0 + ins, tags, w=C, h=ih), self.put(art["right"], ax1, y0 + ins, tags, w=C, h=ih)]
        if fill and iw > 0 and ih > 0:
            ids.append(self.c.create_rectangle(x0 + ins, y0 + ins, x1 - ins, y1 - ins, fill=fill, outline="", tags=tags))
        return ids

    def put_three(self, art, x0, y0, x1, tags):
        """A three-slice set from x0 to x1 with its top at y0 (any glow margin reaches outside that)."""
        G, C = art.get("G", 0), art["C"]
        x0, x1 = int(x0), int(x1)
        ax0, ay0, ax1 = x0 - G, int(y0) - G, x1 + G - C
        ids = [self.put(art["left"], ax0, ay0, tags), self.put(art["right"], ax1, ay0, tags)]
        if ax1 > ax0 + C:
            ids.append(self.put(art["mid"], ax0 + C, ay0, tags, w=ax1 - ax0 - C, h=art["h"]))
        return ids

    # -------------------------------------------------------------- the composed parts
    def skin_card(self, box, tags="content", shade_tag="pshade", fill=None, border=None, radius=14, reach=18, drop=6, shade=0.6, rim_a=0.0):
        under = getattr(self, "ground", lambda: self.col("bg"))()          # 1036: in FLOAT the corners blend into the see-through ground
        art = card(self.k, fill or self.skin_fill(), border or self.skin_border(), shade, radius, reach, drop, self.col("cyan"), rim_a, under)
        self.put_nine(art["body"], box, (tags, shade_tag) if isinstance(tags, str) else tuple(tags) + (shade_tag,), fill=art["fill"], out=art["S"])
        return art

    def skin_fill(self):
        if getattr(self, "look", lambda: None)() == "CLEAR":           # 1038: CLEAR's panels are the see-through ground; their edges and text stay
            return self.ground()
        return hexmix(self.col("panel"), self.col("edge"), 0.20)

    def skin_border(self):
        return hexmix(self.skin_fill(), "#ffffff", 0.10)             # 1033: a neutral hairline, not a tinted frame

    def skin_panel(self, box, hh, title, right):
        """The modern panel().  1033, a 2020s app card: one flat surface on a soft shadow, a hairline edge, a rounder corner; the title is a
        quiet label in the UI face beside a small accent dot, over a hairline that stops short of the edges (no header band, rule or sheen)."""
        k, c = self.k, self.c
        x0, y0, x1, y1 = box
        clean = getattr(self, "clean", lambda: False)()
        look = getattr(self, "look", lambda: None)()
        if look in ("PANES", "GLASS", "OLED"):                               # Flat Oggcultist-style inset cards.
            # HOME panel bodies share Oggcultist's actual sidebar surface.
            # Previously only the gutter was this dark; panels stayed raised.
            fill = OGG_EMBER['sidebar']
            c.create_rectangle(x0, y0, x1, y1, fill=fill, outline=self.col("edge"), width=max(1, round(k)), tags="content")
            if x1-x0 > 4 and y1-y0 > 4:
                # Grain is INSIDE each panel and BELOW its content (never above
                # the white ASCII statues or the Tarot/Rune display).
                self.put(warm_grain(fill), x0+1, y0+1, "content",
                         w=max(1,int(x1-x0-2)), h=max(1,int(y1-y0-2)))
                c.create_rectangle(x0, y0, x1, y1, fill="", outline=self.col("edge"), tags="content")
            art = {"fill": fill}
        elif look in ("FLOAT", "HAZE", "CLEAR"):                     # 1036: a floating panel with no shadow (nothing to cast it on)
            edge = hexmix(self.col("panel"), "#ffffff", 0.16) if look == "CLEAR" else hexmix(self.skin_fill(), "#ffffff", 0.08)
            art = self.skin_card(box, radius=12, reach=2, drop=0, shade=0.0, border=edge)
        else:
            art = self.skin_card(box, radius=12, reach=14, drop=4, shade=0.35) if clean else self.skin_card(box)
        # Apply the same grain/mottle treatment to all panel bodies so every
        # section carries the Oggcultist-style surface, not just the main tabs.
        if look not in ("PANES", "GLASS", "OLED") and x1-x0 > 4 and y1-y0 > 4 and art.get("fill"):
            self.put(warm_grain(OGG_EMBER['sidebar']), x0+1, y0+1, "content",
                     w=max(1, int(x1-x0-2)), h=max(1, int(y1-y0-2)))
        acc, fill = self.col("cyan"), art["fill"]
        if clean:                                                    # 1034: the clean look: the title alone, small and secondary
            c.create_rectangle(x0 + px(9,k), y0 + hh//2 - px(5,k),
                               x0 + px(12,k), y0 + hh//2 + px(5,k),
                               fill=OGG_EMBER['accent'], outline="", tags="content")
            tid = self.T(x0 + px(19, k), y0 + hh // 2 + 1, title, 11, "txt", "w", bold=True, mono=False)
        else:
            d = px(7, k, 4)
            self.put(dot(d, acc, acc, None, 0.0, 0), x0 + px(15, k), y0 + hh // 2 + 1, "content", "center")
            tid = self.T(x0 + px(24, k), y0 + hh // 2 + 1, title, 12, hexmix(self.col("txt"), self.col("dim"), 0.15), "w", bold=True, mono=False)
        rid = self.T(x1 - px(14, k), y0 + hh // 2 + 1, right, 11, "dim", "e", mono=False) if right else None
        ins = px(12, k)
        c.create_line(x0 + ins, y0 + hh, x1 - ins, y0 + hh, fill=self.col("edge"), tags="content")
        return tid, rid

    def skin_tile(self, box, tags, radius=10, lift=0.035):
        """A raised tile inside a panel (a ticker row): a little lighter than the panel, a faint hairline, no shadow."""
        fill = hexmix(self.skin_fill(), "#ffffff", lift)
        art = card(self.k, fill, hexmix(fill, "#ffffff", 0.05), 0.0, radius, 2, 0, None, 0.0, self.skin_fill())
        ids = self.put_nine(art["body"], box, tags, fill=art["fill"], out=art["S"])
        x0, y0, x1, y1 = map(int, box)
        if x1-x0 > 4 and y1-y0 > 4:
            self.put(warm_grain(OGG_EMBER['raised']), x0+1, y0+1, tags,
                     w=max(1, int(x1-x0-2)), h=max(1, int(y1-y0-2)))
        return ids

    def skin_well(self, box, tags, radius=8, border=None, glow_a=0.0, under=None):
        """A field set into a surface (ticker, status, a reading, the plaque).  1033: flat and a shade darker, a hairline edge (an accent edge
        is muted; only a strong accent, the chosen card, keeps a soft glow)."""
        x0, y0, x1, y1 = [int(v) for v in box]
        base = OGG_EMBER['sunken'] if getattr(self, 'clean', lambda: False)() else hexmix(self.col("bg"), self.col("panel"), 0.55)
        edge = hexmix(border, base, 0.45) if border else OGG_EMBER['line_strong'] if getattr(self, 'clean', lambda: False)() else hexmix(base, "#ffffff", 0.07)
        glow = border if glow_a >= 0.3 else None
        art = bar(self.k, y1 - y0, base, base, radius, edge, glow, glow_a * 0.6 if glow else 0.0, 0.0, 6, 0.0,
                  self.skin_fill() if under is None else (under or None))
        ids = self.put_three(art, x0, y0, x1, tags)
        # Same actual Oggcultist dark table-field tile beneath content.
        if x1-x0 > 8 and y1-y0 > 8:
            from oracle_ogg_texture import png_bytes
            self.put(png_bytes('sunken'), x0+3, y0+3, tags,
                     w=max(1, x1-x0-6), h=max(1, y1-y0-6))
        return ids

    def skin_button(self, box, tags, accent=None, radius=None):
        """A pill button.  1033: a solid accent fill (a primary button), no border or glow; its label goes in the ground colour."""
        x0, y0, x1, y1 = [int(v) for v in box]
        acc = accent or self.col("cyan")
        fill = self.skin_fill()
        h = y1 - y0
        art = bar(self.k, h, acc, hexmix(acc, "#000000", 0.08), h / 2.0 / self.k if radius is None else radius,
                  None, None, 0.0, 0.0, 5, 0.0, fill)
        return self.put_three(art, x0, y0, x1, tags)

    def skin_outline(self, box, tags, accent=None, radius=None, fill=None, under=None):
        """1035: an outlined button: the panel's fill inside a 1 px accent outline, fully rounded unless `radius` (the modern outline look)."""
        x0, y0, x1, y1 = [int(v) for v in box]
        acc = accent or self.col("cyan")
        fill = fill or self.skin_fill()
        h = y1 - y0
        art = bar(self.k, h, fill, fill, h / 2.0 / self.k if radius is None else radius, acc, None, 0.0, 0.0, 5, 0.0,
                  fill if under is None else (under or None))
        return self.put_three(art, x0, y0, x1, tags)

    def skin_dialog(self, box, tags, fill=None, border=None, radius=14):
        """1035: a floating dialog (application message): a rounded card with a hairline outline on a wide soft shadow, drawn over anything
        (its corners and shadow are part-transparent, so it is kept to things that open now and then)."""
        fill = fill or self.skin_fill()
        art = card(self.k, fill, border or hexmix(fill, "#ffffff", 0.12), 0.65, radius, 22, 8, None, 0.0, None)
        S = art["S"]
        ids = self.put_nine(art["shadow"], box, tags, out=S)
        ids += self.put_nine(art["body"], box, tags, fill=fill, out=S)
        return ids

    def skin_chip(self, item, colour, tag, extra=()):
        """1032: a pill behind a short status text (OFFLINE, AUD SIM, PLATE 5/14, a market's move) that follows the text: redrawn only when the
        text or its place changes, under the text, tinted by `colour`."""
        c = self.c
        seen = self.__dict__.setdefault("skin_chips", {})
        try:
            text, bb = c.itemcget(item, "text"), c.bbox(item)
        except Exception:
            return
        key = (text, tuple(bb or ()), colour)
        if seen.get(tag) == key and c.find_withtag(tag):
            return
        seen[tag] = key
        c.delete(tag)
        if not self.skin_on() or not text.strip() or not bb:
            return
        try:
            k = self.k
            fill = self.skin_fill()
            x0, y0, x1, y1 = bb
            h = (y1 - y0) + px(3, k)
            cy = (y0 + y1) // 2
            padx = px(7, k)
            tint = hexmix(fill, colour, 0.17)                           # 1033: a flat tinted badge
            art = bar(k, h, tint, tint, h / 2.0 / k, None, None, 0.0, 0.0, 6, 0.0)
            for i in self.put_three(art, x0 - padx, cy - h // 2, x1 + padx, ("content", tag) + tuple(extra)):
                c.tag_lower(i, item)
        except Exception:
            c.delete(tag)
