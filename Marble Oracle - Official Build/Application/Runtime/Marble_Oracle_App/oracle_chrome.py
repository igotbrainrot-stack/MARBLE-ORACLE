"""oracle_chrome.py -- the frame around Marble_Oracle (stdlib + tkinter only): colour themes, the CRT sheets
(scanlines + static, tiled by Tk from one-period PNGs), the Windows-98 window chrome with its menu-row tabs and the
ornamental plastic monitor case (bezel, buttons, power LED).  ChromeMixin holds
the Scene methods that draw and animate them; Scene inherits it, so every call site is unchanged.  Split out of
marble_oracle.py (build 0929); behaviour unchanged."""
import base64
import math
import os
import random
import time

from oracle_assets import open_zip, rgba_png, state_dir
from oracle_photo_bezel import PhotoBezelMixin
from oggcultist_design_system import COLOR as OGG_EMBER


DECK_TAB_OFF, DECK_TAB_ON = "#c6ff3a", "#eaff9a"  # ARCHIVE DECK tab fill (0991): flat mint card
DK_TAB_OFF, DK_TAB_ON = "#ffe14a", "#fff3a0"            # DICEKEY tab fill (0991): flat yellow card
LD_TAB_OFF, LD_TAB_ON = "#ff7a6b", "#ffb3a8"            # 1045 LIAR'S DICE tab fill: flat red card
TAB_INK = "#3df0ff"                                     # chrome lettering on the three night tabs
TAB_EDGE = "#ff2d8a"                                    # magenta edge
TAB_SLOPE = 0.275                                     # tab side slant per px of height
TAB_GAP = 10                                          # space between menu-row tabs (reference px)
TAB_MIN_PX = 7                                        # labels shrink to fit a small tab, never below this
THEMES = {
    "ONE": dict(bg="#06060d", panel="#0a0c18", edge="#17415a", edge2="#0f2233", cyan="#19e6ff",
                mag="#ff2bd6", gold="#ffd23f", lime="#7cff6b", txt="#c9d4e8", dim="#5d6d8a",
                red="#ff4d5e", orange="#ff8a2a", marble="#b9c7d6", sun1="#ffd23f", sun2="#ff2bd6"),
    "TWO": dict(bg="#0d0606", panel="#150a0a", edge="#5a2a17", edge2="#331a0f", cyan="#ffb347",
                mag="#ff3d81", gold="#ffe45c", lime="#b6ff5c", txt="#efd9c9", dim="#8a6a5d",
                red="#ff4d3d", orange="#ff8a2a", marble="#d8c7b9", sun1="#ffe45c", sun2="#ff3d81",
                ramp=("#3a2a26", "#fffaf2")),
    # build 0940: four more schemes for the VIEW presets.  Every one keeps lime = up and red = down (the markets)
    "PHOSPHOR": dict(bg="#020a04", panel="#041208", edge="#1d5a2c", edge2="#0e2e16", cyan="#39ff6a",
                     mag="#b8ff3a", gold="#d9ff7a", lime="#7dff9e", txt="#a8f0b4", dim="#4f8a5c",
                     red="#ff5a4a", orange="#e0c040", marble="#9fe0ae", sun1="#d9ff7a", sun2="#39ff6a",
                     ramp=("#062a10", "#d8ffe0")),
    "AMBER": dict(bg="#0c0700", panel="#140c02", edge="#5a3a0c", edge2="#2e1d06", cyan="#ffb000",
                  mag="#ff7a1a", gold="#ffd98a", lime="#d8ff5c", txt="#f2d6a2", dim="#9a7a4a",
                  red="#ff4a3a", orange="#ff8a2a", marble="#e8cfa0", sun1="#ffd98a", sun2="#ff7a1a",
                  ramp=("#2a1600", "#fff0cc")),
    "ARCTIC": dict(bg="#04080e", panel="#08121e", edge="#2a5c80", edge2="#14304a", cyan="#8fe3ff",
                   mag="#6fa8ff", gold="#e6f4ff", lime="#7cf0c8", txt="#d6e6f5", dim="#6a88a4",
                   red="#ff6a7a", orange="#ffb070", marble="#cfe0ee", sun1="#e6f4ff", sun2="#6fa8ff",
                   ramp=("#0e2438", "#f4fbff")),
    "ORCHID": dict(bg="#0a0410", panel="#120820", edge="#4a2a70", edge2="#26143c", cyan="#d58bff",
                   mag="#ff5ab8", gold="#ffd1f0", lime="#9dffb0", txt="#e6d6f2", dim="#86769c",
                   red="#ff5a6a", orange="#ffa05a", marble="#dccdea", sun1="#ffd1f0", sun2="#ff5ab8",
                   ramp=("#24103a", "#fbf0ff")),
}
# 1034: the clean look's two schemes, neutral and quiet; the token names are the same, so every panel keeps its meaning (lime = up, red = down).
THEMES["GRAPHITE"] = dict(bg="#0f1012", panel="#17181b", edge="#2a2c31", edge2="#1d1e22", cyan="#8ab4f8", mag="#c58af9", gold="#e8c47a",
                          lime="#81c995", txt="#e8eaed", dim="#9aa0a6", red="#f28b82", orange="#fcad70", marble="#c9ccd1",
                          sun1="#e8c47a", sun2="#c58af9", ramp=("#2a2c31", "#f1f3f4"))
THEMES["SLATE"] = dict(bg="#0d1117", panel="#161b22", edge="#30363d", edge2="#21262d", cyan="#58a6ff", mag="#bc8cff", gold="#e3b341",
                       lime="#3fb950", txt="#e6edf3", dim="#8b949e", red="#f85149", orange="#f0883e", marble="#c9d1d9",
                       sun1="#e3b341", sun2="#bc8cff", ramp=("#21262d", "#f0f6fc"))
# 1050: a third clean scheme with the retro accents: GRAPHITE's quiet surfaces, NIGHT GAS's neon (cyan, magenta, gold, lime).
THEMES["NEON"] = dict(THEMES["GRAPHITE"], cyan="#19e6ff", mag="#ff2bd6", gold="#ffd23f", lime="#7cff6b", red="#ff4d5e", orange="#ff8a2a",
                      sun1="#ffd23f", sun2="#ff2bd6")
# Oggcultist 2.0.4 Ember colours, with restrained semantic accents.
# The original market-direction colours remain green/red so chart meaning is unchanged.
THEMES["EMBER"] = dict(
    # Share Oggcultist's colour roles instead of gradually diverging copies.
    bg=OGG_EMBER['canvas'], panel=OGG_EMBER['raised'],
    edge=OGG_EMBER['line'], edge2=OGG_EMBER['control'],
    cyan=OGG_EMBER['accent'], mag=OGG_EMBER['text_2'],
    gold='#F2C38B', lime=OGG_EMBER['done'],
    txt=OGG_EMBER['text'], dim=OGG_EMBER['text_2'],
    red=OGG_EMBER['failed'], orange=OGG_EMBER['accent'],
    marble=OGG_EMBER['text_bright'], sun1=OGG_EMBER['accent'],
    sun2=OGG_EMBER['control_line'],
    ramp=(OGG_EMBER['sunken_alt'], OGG_EMBER['text_bright'])
)

THEME_NAMES = {"EMBER": "EMBER", "GRAPHITE": "GRAPHITE", "SLATE": "SLATE", "NEON": "NEON", "ONE": "NIGHT GAS", "TWO": "LOW FIRE", "PHOSPHOR": "GREEN HOUR", "AMBER": "OLD HEAT", "ARCTIC": "COLD ROOM",
               "ORCHID": "LATE PURPLE"}


# 1030: the case is pre-rendered, anti-aliased artwork (data/bezel.zip), baked at these scales; the margins snap to one of them so every
# piece is shown at its own pixel size (never stretched, never pixelated).  The vector case below stays as the fallback.
BEZEL_STEPS = (0.4375, 0.5, 0.625, 0.75, 0.875, 1.0, 1.125, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0)


def bezel_step(s):
    """The largest baked scale not above s (the smallest one below that)."""
    return max([k for k in BEZEL_STEPS if k <= s + 1e-9] or [BEZEL_STEPS[0]])


def bezel_geometry(k):
    """Every size of the case at scale k, in pixels (the bake tool and the program share it).  l t r b: the margins.  R: the recess wall,
    G: the gasket, rc: the tube's corner radius, S: the glass shadow, C: how far a corner piece reaches into the screen."""
    def px(v, lo=1):
        return max(lo, int(round(v * k)))
    g = dict(k=k, l=px(52), t=px(46), r=px(52), b=max(52, px(104)), R=px(13, 5), G=px(2.5, 2), rc=px(11, 4), ro=px(8, 3), bev=px(4, 2),   # 1066: thicker (was 36 32 36 84)
             S=px(7, 3), shx=px(1.5, 1), shy=px(3.5, 1), rr=max(7, px(12)), lr=px(4, 3), vw=px(4, 3), vstep=int(7 * k + 3))
    g["C"] = max(g["rc"], g["S"] + g["shy"]) + 2
    g["pr"] = int(g["rr"] * 1.35)
    g["wr"] = max(6, int(g["rr"] * 0.9))                  # 1062: the window keys (min, window, close) on the chin
    g["vh"] = max(8, int(g["b"] * 0.34))
    g["pw"], g["ph"] = px(330), max(10, int(g["vh"] * 1.2))
    return g


def bezel_plan(W, H, g):
    """Where the case pieces go, in inner coordinates (the screen is 0..W x 0..H): [(piece, x, y, w, h)].  The four corners are shown as
    they are; top / bottom / left / right are one-pixel profiles tiled along the edge."""
    l, t, r, b, C = g["l"], g["t"], g["r"], g["b"], g["C"]
    return [("tl", -l, -t, l + C, t + C), ("tr", W - C, -t, r + C, t + C), ("bl", -l, H - C, l + C, b + C), ("br", W - C, H - C, r + C, b + C),
            ("top", C, -t, W - 2 * C, t + C), ("bot", C, H - C, W - 2 * C, b + C), ("left", -l, C, l + C, H - 2 * C), ("right", W - C, C, r + C, H - 2 * C)]


def bezel_chin(W, H, g):
    """Centres on the chin: vents (x0), badge, the four buttons, the LED and the three window keys, all on one line cy.
    1062: the window keys (min, window, close) take POWER's place at the right; the LED sits before them.  1063: five buttons (PASS)."""
    cy = H + g["G"] + g["R"] + (g["b"] - g["G"] - g["R"]) // 2
    rr, wr = g["rr"], g["wr"]
    wins = [int(W * 0.955) - (2 - i) * int(wr * 5.2) for i in range(3)]
    return dict(cy=cy, vx=int(W * 0.035), plate=int(W * 0.30), btns=[int(W * 0.52) + i * int(rr * 4.6) for i in range(5)],
                wins=wins, lx=wins[0] - wr - int(30 * g["k"]))


_BEZEL_ZIP = []                                       # [zipfile or None], opened once


def bezel_zip():
    if not _BEZEL_ZIP:
        try:
            _BEZEL_ZIP.append(open_zip("bezel.zip"))
        except Exception:
            _BEZEL_ZIP.append(None)
    return _BEZEL_ZIP[0]


_NOISE_TILES = {}


def noise_tile_png(seed=1, tile=(199, 211)):
    """The CRT grain: a small random tile (EVERY pixel a faint grey, alpha 2..16, so Tk has no ragged transparent regions to track), as its own PNG (Tk tiles
    it across the sheet: Scene._tiled).  Kept in state_dir()/cache/ after the first run (it is the same tile every time: a fixed seed)."""
    k = (seed, tile)
    path = os.path.join(state_dir(), "cache", "noise_%d_%dx%d.v1.png" % (seed, tile[0], tile[1]))
    if k not in _NOISE_TILES:
        try:
            with open(path, "rb") as f:
                data = f.read()
            if data.startswith(b"\x89PNG"):
                _NOISE_TILES[k] = data
        except OSError:
            pass
    if k not in _NOISE_TILES:
        rnd = random.Random(seed)
        tw, th = tile
        trows = []
        for _ in range(th):
            buf = bytearray(tw * 4)
            for x in range(tw):
                v = 255 if rnd.random() < 0.5 else 0
                buf[x * 4:x * 4 + 4] = bytes((v, v, v, rnd.randint(2, 16)))
            trows.append(bytes(buf))
        _NOISE_TILES[k] = rgba_png(tw, th, trows)
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path + ".tmp", "wb") as f:
                f.write(_NOISE_TILES[k])
            os.replace(path + ".tmp", path)
        except OSError:
            pass
    return _NOISE_TILES[k]


def scan_tile_png(a=34, period=3):
    """The scanlines: one period (one dark row every `period` rows, transparent between).  Tk tiles it across the window."""
    return rgba_png(1, period, [bytes((0, 0, 0, a)) if y % period == period - 1 else bytes(4) for y in range(period)])


def hexrgb(c):
    return int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16)


def mix(a, b, t):
    ra, ga, ba = hexrgb(a)
    rb, gb, bb = hexrgb(b)
    return "#%02x%02x%02x" % (int(ra + (rb - ra) * t), int(ga + (gb - ga) * t), int(ba + (bb - ba) * t))


def _lum(c):
    def ch(v):
        v /= 255.0
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = hexrgb(c)
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def tab_ink(fill, dark="#111111", light="#ffffff"):
    """The label colour for a tab filled with `fill`: whichever of near-black and white reads better on it (the 0993 tabs are bright flat fields: a fixed ink cannot
    suit mint, yellow, blue and pink at once, and a blue tab's two states need different inks)."""
    def contrast(a, b):
        hi, lo = sorted((_lum(a), _lum(b)), reverse=True)
        return (hi + 0.05) / (lo + 0.05)
    return dark if contrast(dark, fill) >= contrast(light, fill) else light


class ChromeMixin(PhotoBezelMixin):
    """Scene's frame: bezel, CRT, window chrome, wordmark (see the module docstring)."""

    def case_on(self):
        """1062: the monitor case is round the screen (then its chin holds the menu keys and the window keys)."""
        return getattr(self, "mg", (0, 0, 0, 0)) != (0, 0, 0, 0)

    def _bezel(self):
        """1030: the case is the baked, anti-aliased artwork when data/bezel.zip is there and Tk takes it; else the drawn case below."""
        self.bz_imgs = []
        # Reset old animation handles on every rebuild. A transient resize or
        # explicit self-test resize may render the vector fallback instead.
        self.photo_animate = None
        self.dial_hot = []
        self.bz_dials = []
        if self.mg != (0, 0, 0, 0):
            try:
                from oracle_photo_bezel import photo_zip
                locked = photo_zip() is not None
                if self._bezel_photo():
                    return
                if not locked and self._bezel_art():
                    return
            except Exception:
                self.c.delete("bezel")
                self.bz_imgs = []
        self._bezel_vector()

    def _bezel_art(self):
        """The baked case: four corners and four tiled one-pixel profiles round the screen, then the chin sprites (vents, badge, the four
        buttons, the LED and POWER, each button an up and a down picture, the LED eight glow levels).  The labels stay Tk text (smooth)."""
        z = bezel_zip()
        if z is None:
            return False
        import tkinter
        l, t, r, b = self.mg
        k = next((k for k in BEZEL_STEPS if bezel_geometry(k)["l"] == l and bezel_geometry(k)["b"] == b), None)
        if k is None:
            return False
        g, key = bezel_geometry(k), "k%04d" % int(round(k * 1000))
        c, W, H, tg = self.c, self.W, self.H, "bezel"
        self.bz_btns, self.bz_led = [], None

        def pic(name):
            im = tkinter.PhotoImage(master=c, data=base64.b64encode(z.read("%s/%s.png" % (key, name))))
            self.bz_imgs.append(im)
            return im
        def placed(name, w, h):
            im = pic(name)
            if (im.width(), im.height()) != (w, h):              # a profile: Tk tiles it along the edge
                big = tkinter.PhotoImage(master=c, width=w, height=h)
                c.tk.call(str(big), "copy", str(im), "-to", 0, 0, w, h)
                self.bz_imgs.append(big)
                im = big
            return im
        plan = [p for p in bezel_plan(W, H, g) if p[3] > 0 and p[4] > 0]
        for name, x, y, w, h in plan:
            c.create_image(x, y, image=placed(name, w, h), anchor="nw", tags=tg)
        self._bezel_neon(z, key, g, plan, placed, pic)
        ch = bezel_chin(W, H, g)
        cy, ink = ch["cy"], self.BZ_INK
        c.create_image(ch["vx"], cy, image=pic("vent"), anchor="w", tags=tg)
        c.create_image(ch["plate"], cy, image=pic("plate"), anchor="center", tags=tg)
        self.T(ch["plate"], cy, "Marble_Oracle", 12, ink, "center", tg, True, True)
        well_y = cy - 3
        ups, downs = pic("btn0"), pic("btn1")
        labs = sorted([(x, l) for (l, _n), x in zip(self.BZ_BTNS, ch["btns"])] + [(x, l) for (l, _n), x in zip(self.BZ_WIN, ch["wins"])] + [(ch["lx"], "LIT")])
        self.bz_lab_font = self.font(10, True, False)
        try:                                                      # 1032: on a small window the labels shrink until neighbours clear by 6 px
            px = max(10, int(round(10 * self.k * 1.15)))         # the size self.font(10) would give, then down to 7 px (below font()'s floor)
            while True:
                f = self.tkfont.Font(family=self.ui_family, size=-px, weight="bold")
                if px <= 7 or all((f.measure(la) + f.measure(lb)) / 2.0 + 6 <= xb - xa for (xa, la), (xb, lb) in zip(labs, labs[1:])):
                    break
                px -= 1
            self.bz_lab_font = f
        except Exception:
            pass
        for (lab, name), cx in zip(self.BZ_BTNS, ch["btns"]):
            self._bz_art_button(cx, well_y, g["rr"], name, lab, ups, downs, ink)
        for (lab, name), cx, gl in zip(self.BZ_WIN, ch["wins"], ("min", "max", "cls")):      # 1062: the window keys
            self._bz_art_button(cx, well_y, g["wr"], name, lab, pic(gl + "0"), pic(gl + "1"), ink)
        levels = [pic("led%d" % i) for i in range(8)]
        led = c.create_image(ch["lx"], well_y, image=levels[0], anchor="center", tags=tg)
        c.create_text(ch["lx"], well_y + g["lr"] + 13, text="LIT", font=self.bz_lab_font, fill=ink, tags=tg)
        self.bz_led = ("art", led, levels)
        self.bz_last_led = -1
        return True

    def _bz_art_button(self, cx, cy, rr, name, lab, up, down, ink):
        c, g = self.c, "bezel"
        face = c.create_image(cx, cy, image=up, anchor="center", tags=g)
        c.create_text(cx, cy + rr + 10, text=lab, font=self.bz_lab_font, fill=ink, tags=g)
        self.bz_btns.append(dict(cx=cx, cy=cy, r=rr, face=face, hi=None, art=(up, down), name=name, down=False, until=0.0, extra=[]))
        self.hot.append((cx - rr, cy - rr, cx + rr, cy + rr, name))

    NEON_LEVELS = 5
    SPARKS = 6
    SPARK_LAP = 7.0                                        # seconds for the light to run once round the groove
    STRIKE = 1.6                                           # seconds the neon flickers before it holds

    def _bezel_neon(self, z, key, g, plan, placed, pic):
        """1064: the neon trims are their own baked layer (NEON_LEVELS brightnesses of the eight pieces); _bezel_tick strikes them on the
        first time the case is shown, then lets them breathe, and runs a spark round the groove.  An older bezel.zip simply has none."""
        self.bz_neon, self.bz_spark = None, None
        names = set(z.namelist())
        if "%s/n0_tl.png" % key not in names:
            return
        items = []
        for name, x, y, w, h in plan:
            levels = [placed("n%d_%s" % (lv, name), w, h) for lv in range(self.NEON_LEVELS)]
            items.append((self.c.create_image(x, y, image=levels[0], anchor="nw", tags="bezel"), levels))
        self.bz_neon = dict(items=items, last=-1, t0=getattr(self, "bz_struck", None))
        if "%s/spark0.png" % key in names:
            l, t, r, b = self.mg
            gp = max(2.5, 3.2 * g["k"])                    # the groove, as bake_bezel cuts it: gp inside the case's outer edge
            box = (-l + gp, -t + gp, self.W + r - gp, self.H + b - gp)
            pics = [pic("spark%d" % i) for i in range(self.SPARKS)]
            dots = [self.c.create_image(-999, -999, image=p, anchor="center", tags="bezel") for p in reversed(pics)]
            self.bz_spark = dict(box=box, rad=max(0.0, g["ro"] - gp), dots=list(reversed(dots)), gap=max(5.0, 8.0 * g["k"]))
        self._bezel_detail(names, key, g, pic)

    LAMPS = 17
    SEGS = 14

    def _bezel_detail(self, names, key, g, pic):
        """1066 (the owner: "make the crt boarder thicker and more dense with detail and animation"): rivets and etched legends on the face, a
        scanner of LAMPS lamps on the brow, a level meter of SEGS segments on each side, and a magenta spark that runs the lip line the other
        way.  Each part needs its sprites in bezel.zip; without them that part is left out."""
        self.bz_chase = self.bz_vu = self.bz_mspark = None
        c, k, W, H = self.c, g["k"], self.W, self.H
        l, t, r, b = self.mg
        have = lambda n: "%s/%s.png" % (key, n) in names
        rail = 18.25 * k                                    # the ribbed band's middle, from the case's outer edge
        lamp_gap, seg_gap = 12 * k, 5 * k
        if have("rivet"):
            riv, rx = pic("rivet"), 26 * k               # down both sides (the brow has its legends and the scanner)
            vspan = seg_gap * (self.SEGS + 2) / 2.0
            y = 40 * k
            while y < H - 30 * k:
                if abs(y - H / 2.0) > vspan:
                    for xx in (-l + rx, W + r - rx):
                        c.create_image(xx, y, image=riv, anchor="center", tags="bezel")
                y += 90 * k
        try:                                                # etched legends on the brow, either side of the scanner
            ink = mix(self.BZ_INK, self.BZ_BEIGE, 0.45)
            self.T(int(70 * k), -t + rail, "Marble_Oracle", 8, ink, "w", "bezel", True, True)
            self.T(W - int(70 * k), -t + rail, "SER 1066-OX  \u00b7  240V ~ 50HZ  \u00b7  HV 25KV", 8, ink, "e", "bezel", True, True)
        except Exception:
            pass
        if all(have("lamp%d" % i) for i in range(4)):
            pics = [pic("lamp%d" % i) for i in range(4)]
            x0 = W / 2.0 - lamp_gap * (self.LAMPS - 1) / 2.0
            items = [c.create_image(x0 + i * lamp_gap, -t + rail, image=pics[0], anchor="center", tags="bezel") for i in range(self.LAMPS)]
            self.bz_chase = dict(items=items, pics=pics, last=[0] * self.LAMPS)
        if all(have("seg%d" % i) for i in range(3)):
            pics = [pic("seg%d" % i) for i in range(3)]
            y0 = H / 2.0 + seg_gap * (self.SEGS - 1) / 2.0     # segment 0 at the bottom
            cols = [[c.create_image(xx, y0 - i * seg_gap, image=pics[0], anchor="center", tags="bezel") for i in range(self.SEGS)]
                    for xx in (-l + rail, W + r - rail)]
            self.bz_vu = dict(cols=cols, pics=pics, val=[0.0, 0.0], aim=[0.5, 0.5], last=[[0] * self.SEGS for _ in cols], next=0.0)
        if all(have("mspark%d" % i) for i in range(self.SPARKS)):
            d = g["G"] + g["R"] * 0.92                      # the lip line, as bake_bezel draws it: d outside the tube's rounded rect
            pics = [pic("mspark%d" % i) for i in range(self.SPARKS)]
            dots = [c.create_image(-999, -999, image=p, anchor="center", tags="bezel") for p in reversed(pics)]
            self.bz_mspark = dict(box=(-d, -d, W + d, H + d), rad=g["rc"] + d, dots=list(reversed(dots)), gap=max(5.0, 8.0 * k))

    def _detail_tick(self, now, a):
        """1066: the scanner sweeps, the meters dance, the magenta spark runs the lip the other way (a: seconds since the neon held)."""
        ch = self.bz_chase
        if ch:
            pos = (0.5 + 0.5 * math.sin(a * 2.4)) * (self.LAMPS - 1)
            for i, item in enumerate(ch["items"]):
                q = max(0, 3 - int(abs(i - pos) * 1.5))
                if q != ch["last"][i]:
                    ch["last"][i] = q
                    self.c.itemconfigure(item, image=ch["pics"][q])
        vu = self.bz_vu
        if vu and now >= vu["next"]:
            vu["next"] = now + 0.07
            for j, col in enumerate(vu["cols"]):
                if self.rng.random() < 0.18:
                    vu["aim"][j] = self.rng.random() ** 0.7
                vu["val"][j] += (vu["aim"][j] - vu["val"][j]) * 0.45
                lit = int(round(vu["val"][j] * self.SEGS))
                for i, item in enumerate(col):
                    q = 0 if i >= lit else (2 if i >= self.SEGS - 3 else 1)
                    if q != vu["last"][j][i]:
                        vu["last"][j][i] = q
                        self.c.itemconfigure(item, image=vu["pics"][q])
        ms = self.bz_mspark
        if ms:
            x0, y0, x1, y1 = ms["box"]
            head = -a / (self.SPARK_LAP * 1.3) * 2 * (x1 - x0 + y1 - y0)
            for i, dot in enumerate(ms["dots"]):
                self.c.coords(dot, *self.groove_point(ms["box"], ms["rad"], head + i * ms["gap"]))

    @staticmethod
    def groove_point(box, rad, s):
        """The point at arc length s (wrapping) along a rounded rectangle, clockwise from the top-left end of the top edge."""
        x0, y0, x1, y1 = box
        w, h = x1 - x0 - 2 * rad, y1 - y0 - 2 * rad
        q = math.pi * rad / 2.0
        segs = (w, q, h, q, w, q, h, q)
        s %= sum(segs)
        for i, n in enumerate(segs):
            if s <= n or i == 7:
                f = s / n if n else 0.0
                if i == 0:
                    return x0 + rad + f * w, y0
                if i == 2:
                    return x1, y0 + rad + f * h
                if i == 4:
                    return x1 - rad - f * w, y1
                if i == 6:
                    return x0, y1 - rad - f * h
                cx, cy, a0 = {1: (x1 - rad, y0 + rad, -90), 3: (x1 - rad, y1 - rad, 0),
                              5: (x0 + rad, y1 - rad, 90), 7: (x0 + rad, y0 + rad, 180)}[i]
                a = math.radians(a0 + 90 * f)
                return cx + rad * math.cos(a), cy + rad * math.sin(a)
            s -= n

    def _neon_level(self, now):
        """0..NEON_LEVELS-1: a tube striking (dark, stutters, full) for STRIKE seconds, then a slow breath near full."""
        n = self.bz_neon
        if n["t0"] is None:
            n["t0"] = self.bz_struck = now
        a = now - n["t0"]
        top = self.NEON_LEVELS - 1
        if a < self.STRIKE:
            on = (0.10, 0.22, 0.30, 0.55, 0.62, 0.95, 1.10, 1.25)
            lit = sum(1 for e in on if a >= e) % 2 == 1 or a >= 1.25
            return top if lit and a >= 0.10 else (1 if a > 0.5 else 0)
        return int(round(top - 2 + 2 * (0.5 + 0.5 * math.sin((a - self.STRIKE) * 1.4))))     # breathes between top-2 and top

    def _bezel_vector(self):
        """Beige plastic monitor case round the Win98 window: recessed screen lip, chin with four
        round buttons, a power button and a green LED.  Drawn in inner coordinates (outside 0..W, 0..H)."""
        self.bz_btns, self.bz_led = [], None
        l, t, r, b = self.mg
        if not (l or t or r or b):
            return
        c, W, H = self.c, self.W, self.H
        BE, HI, LO, DK = self.BZ_BEIGE, self.BZ_HI, self.BZ_LO, self.BZ_DK
        g = "bezel"
        X0, Y0, X1, Y1 = -l, -t, W + r, H + b
        e = max(6, int(min(l, t) * 0.85))
        # the case is a FRAME, never a full rectangle, so it can sit above the screen and clip sprites.
        # 1030: moulded plastic lit from above -- a soft top-to-bottom shade in bands (was flat beige with random grain streaks)
        top, bot = mix(BE, HI, .55), mix(BE, LO, .55)
        n = 28
        for i in range(n):
            ya, yb = Y0 + (Y1 - Y0) * i // n, Y0 + (Y1 - Y0) * (i + 1) // n
            f = (i + .5) / n
            fill = mix(top, BE, f * 2) if f < .5 else mix(BE, bot, (f - .5) * 2)
            if ya < -e:
                c.create_rectangle(X0, ya, X1, min(yb, -e), fill=fill, outline="", tags=g)
            if yb > -e and ya < H + e:
                c.create_rectangle(X0, max(ya, -e), -e, min(yb, H + e), fill=fill, outline="", tags=g)
                c.create_rectangle(W + e, max(ya, -e), X1, min(yb, H + e), fill=fill, outline="", tags=g)
            if yb > H + e:
                c.create_rectangle(X0, max(ya, H + e), X1, yb, fill=fill, outline="", tags=g)
        # case edge bevel, and the moulding's parting line as an engraved groove
        c.create_line(X0, Y1 - 1, X0, Y0, X1 - 1, Y0, fill=HI, width=2, tags=g)
        c.create_line(X0 + 1, Y1 - 1, X1 - 1, Y1 - 1, X1 - 1, Y0 + 1, fill=DK, width=2, tags=g)
        c.create_rectangle(X0 + 5, Y0 + 5, X1 - 5, Y1 - 5, outline=LO, tags=g)
        c.create_rectangle(X0 + 6, Y0 + 6, X1 - 4, Y1 - 4, outline="#19d9ff", tags=g)        # 1062: the groove is a cyan neon trim
        # recessed screen opening: a graded chamfer (shade on the top and left walls, light on the bottom and right) down to a dark gasket
        k = 6
        for i in range(k):
            o0, o1 = e - e * i // k, e - e * (i + 1) // k
            u = i / float(k - 1)
            self._lip(-o0, -o0, W + o0, H + o0, -o1, -o1, W + o1, H + o1, mix("#0b0c0f", "#1a1c21", u), mix("#3a3f48", "#23262c", u))
        c.create_rectangle(-2, -2, W + 2, H + 2, outline="#15140f", width=3, tags=g)
        # the tube's rounded corners: four small fillets in the gasket colour over the screen's corners
        rc = max(5, int(e * .6))
        for cx, cy, sx_, sy_ in ((0, 0, 1, 1), (W, 0, -1, 1), (0, H, 1, -1), (W, H, -1, -1)):
            pts = [cx, cy, cx + sx_ * rc, cy]
            for j in range(1, 8):
                a = math.pi / 2 * j / 8
                pts += [cx + sx_ * (rc - rc * math.sin(a)), cy + sy_ * (rc - rc * math.cos(a))]
            pts += [cx, cy + sy_ * rc]
            c.create_polygon(*pts, fill="#15140f", outline="", tags=g)
        # ---- chin
        cy = H + e + (b - e - 6) / 2.0
        s = max(0.5, min(self.sx, self.sy))
        # vent slots
        vx = int(W * 0.035)
        vh = max(8, int(b * 0.34))
        for i in range(9):
            x = vx + i * int(7 * s + 3)
            c.create_rectangle(x, cy - vh / 2.0, x + max(3, int(4 * s)), cy + vh / 2.0, fill=DK, outline="", tags=g)
            c.create_line(x + 1 + max(3, int(4 * s)), cy - vh / 2.0, x + 1 + max(3, int(4 * s)), cy + vh / 2.0, fill=HI, tags=g)
        # etched plate
        px0, py0, px1, py1 = int(W * 0.20), cy - vh * 0.6, int(W * 0.50), cy + vh * 0.6
        c.create_rectangle(px0, py0, px1, py1, fill=mix(BE, LO, .30), outline=LO, tags=g)
        c.create_line(px0, py1, px1, py1, px1, py0, fill=HI, tags=g)
        self.T((px0 + px1) / 2, (py0 + py1) / 2, "Marble_Oracle", 12, self.BZ_INK, "center", g, True, True)
        # the round buttons (1063: five)
        rr = max(7, int(12 * s))
        bx0 = int(W * 0.52)                            # 1063: as the baked chin, room for PASS
        step = int(rr * 4.6)
        well_y = cy - 3
        for i, (lab, name) in enumerate(self.BZ_BTNS):
            cx = bx0 + i * step
            self._bz_button(cx, well_y, rr, name, lab, i)
        # 1062: the window keys (min, window, close) where POWER was, the LED before them
        wr = max(6, int(rr * 0.9))
        wins = [int(W * 0.955) - (2 - i) * int(wr * 5.2) for i in range(3)]
        for (lab, name), cx in zip(self.BZ_WIN, wins):
            self._bz_button(cx, well_y, wr, name, lab, 0)
            gl, ink_ = max(3, int(wr * 0.4)), ("#ff4d55" if name == "bz9" else "#19d9ff")
            if name == "bz7":
                c.create_line(cx - gl, well_y, cx + gl, well_y, fill=ink_, width=2, tags=g)
            elif name == "bz8":
                c.create_rectangle(cx - gl, well_y - gl, cx + gl, well_y + gl, outline=ink_, width=2, tags=g)
            else:
                c.create_line(cx - gl, well_y - gl, cx + gl, well_y + gl, fill=ink_, width=2, tags=g)
                c.create_line(cx - gl, well_y + gl, cx + gl, well_y - gl, fill=ink_, width=2, tags=g)
        lx = wins[0] - wr - int(30 * s)
        lr = max(3, int(4 * s))
        c.create_oval(lx - lr - 4, well_y - lr - 4, lx + lr + 4, well_y + lr + 4, fill=DK, outline=HI, tags=g)
        glow = c.create_oval(lx - lr - 2, well_y - lr - 2, lx + lr + 2, well_y + lr + 2, fill="#1a5a26", outline="", tags=g)
        core = c.create_oval(lx - lr, well_y - lr, lx + lr, well_y + lr, fill="#28c845", outline="#0c3a14", tags=g)
        spec = c.create_oval(lx - lr * .6, well_y - lr * .7, lx - lr * .05, well_y - lr * .15, fill="#d8ffe0", outline="", tags=g)
        c.create_text(lx, well_y + lr + 13, text="LIT", font=self.font(10, True, False), fill=self.BZ_INK, tags=g)
        self.bz_led = (glow, core, spec, BE)
        self.bz_last_led = -1
        for i in range(3):                                   # resize grip, bottom-right corner of the case
            o = 7 + i * 6
            c.create_line(X1 - 6, Y1 - o, X1 - o, Y1 - 6, fill=DK, tags=g)
            c.create_line(X1 - 6, Y1 - o - 1, X1 - o - 1, Y1 - 6, fill=HI, tags=g)

    def _lip(self, ox0, oy0, ox1, oy1, ix0, iy0, ix1, iy1, dark, light):
        c, g = self.c, "bezel"
        c.create_polygon(ox0, oy0, ox1, oy0, ix1, iy0, ix0, iy0, fill=dark, outline="", tags=g)
        c.create_polygon(ox0, oy0, ix0, iy0, ix0, iy1, ox0, oy1, fill=dark, outline="", tags=g)
        c.create_polygon(ox1, oy0, ox1, oy1, ix1, iy1, ix1, iy0, fill=light, outline="", tags=g)
        c.create_polygon(ox0, oy1, ix0, iy1, ix1, iy1, ox1, oy1, fill=light, outline="", tags=g)

    def _bz_button(self, cx, cy, rr, name, lab, i):
        c, g = self.c, "bezel"
        c.create_oval(cx - rr - 3, cy - rr - 3, cx + rr + 3, cy + rr + 3, fill=self.BZ_DK, outline="#19d9ff", tags=g)     # 1062: a lit well
        face = c.create_oval(cx - rr, cy - rr, cx + rr, cy + rr, fill="#353942", outline=self.BZ_DK, width=2, tags=g)
        hi = c.create_arc(cx - rr + 3, cy - rr + 3, cx + rr - 3, cy + rr - 3, start=110, extent=90, style="arc",
                          outline="#5c6370", width=2, tags=g)
        c.create_text(cx, cy + rr + 10, text=lab, font=self.font(10, True, False), fill=self.BZ_INK, tags=g)
        self.bz_btns.append(dict(cx=cx, cy=cy, r=rr, face=face, hi=hi, name=name, down=False, until=0.0, extra=[]))
        self.hot.append((cx - rr, cy - rr, cx + rr, cy + rr, name))

    def _bz_set(self, b, down):
        if b["down"] == down and not b.get("frames"):
            return
        b["down"] = down
        c = self.c
        if 'photo_overlay' in b:
            frames = b.get("frames") or []
            if frames:
                if down:
                    b["release"] = False
                    b["fi"] = 0
                    c.itemconfigure(b["photo_overlay"], image=frames[0], state="normal")
                else:
                    b["release"] = True
                return
            c.itemconfigure(b['photo_overlay'], image=b['art'][1 if down else 0], state='normal' if down else 'hidden')
            return
        if b.get("art"):                                    # 1030: the baked button swaps to its pressed picture
            c.itemconfigure(b["face"], image=b["art"][1 if down else 0])
            return
        d = 1 if down else -1
        c.move(b["face"], d, d)
        c.move(b["hi"], d, d)
        c.itemconfigure(b["face"], fill="#22252b" if down else "#353942")
        c.itemconfigure(b["hi"], state="hidden" if down else "normal")

    def bz_press(self, name, secs=0.22):
        for b in self.bz_btns:
            if b["name"] == name:
                self._bz_set(b, True)
                b["until"] = time.time() + secs

    def _bezel_tick(self, now):
        self._photo_tick(now)
        tick_press = getattr(self, "_tick_press", None)
        if tick_press:
            tick_press(now)
        tick_dials = getattr(self, "_tick_dials", None)
        if tick_dials:
            tick_dials()
        if not self.bz_btns:
            return
        for b in self.bz_btns:
            if b["down"] and now >= b["until"]:
                self._bz_set(b, False)
        neon = getattr(self, "bz_neon", None)
        if neon:                                              # 1064: the neon strikes, then breathes
            q = self._neon_level(now)
            if q != neon["last"]:
                neon["last"] = q
                for item, levels in neon["items"]:
                    self.c.itemconfigure(item, image=levels[q])
        sp = getattr(self, "bz_spark", None)
        if sp and neon and now - neon["t0"] >= self.STRIKE:   # and a spark runs round the groove
            x0, y0, x1, y1 = sp["box"]
            lap = 2 * (x1 - x0 + y1 - y0)
            head = (now - neon["t0"] - self.STRIKE) / self.SPARK_LAP * lap
            for i, dot in enumerate(sp["dots"]):
                self.c.coords(dot, *self.groove_point(sp["box"], sp["rad"], head - i * sp["gap"]))
        if neon and now - neon["t0"] >= self.STRIKE:
            self._detail_tick(now, now - neon["t0"] - self.STRIKE)
        if self.bz_led:
            v = 0.5 + 0.5 * math.sin(now * 2.2)
            if self.bz_flick > 0:
                self.bz_flick -= 1
                v *= 0.35
            elif self.rng.random() < 0.012:
                self.bz_flick = self.rng.randint(1, 3)
            if self.bz_led[0] == "art":                       # 1030: eight baked glow levels
                q = min(7, int(v * 8))
                if q != self.bz_last_led:
                    self.bz_last_led = q
                    self.c.itemconfigure(self.bz_led[1], image=self.bz_led[2][q])
                return
            glow, core, spec, BE = self.bz_led
            q = int(v * 15)
            if q != self.bz_last_led:
                self.bz_last_led = q
                v = q / 15.0
                self.c.itemconfigure(core, fill=mix("#0f4a1a", "#6dff7a", v))
                self.c.itemconfigure(glow, fill=mix("#5f6a48", "#3dff5a", v * 0.75))
                self.c.itemconfigure(spec, state="normal" if v > .35 else "hidden")

    def _chrome(self):
        """Windows-98 window frame around the dark instrument panels."""
        c, r = self.c, self.rect
        W, H = self.W, self.H
        G = "#c0c0c0"
        skin = self.skin_on()
        if skin:
            try:                                           # 1031: glass title and menu bars, wells for the ticker and status (oracle_skin)
                return self._chrome_skin()
            except Exception:
                self.skin_ok = False
                c.delete("chrome")
                self.hot = [h for h in self.hot if h[4] not in ("quit", "full", "min", "next", "word", "deal", "view")]
        # outer frame strips (left / right), bevelled like a 98 window
        self.bevel((0, 0, W, H), True, None)
        c.create_rectangle(2, 2, 6, H - 2, fill=G, outline="", tags="chrome")
        c.create_rectangle(W - 6, 2, W - 2, H - 2, fill=G, outline="", tags="chrome")
        # ---- title bar: navy -> light-blue gradient
        x0, y0, x1, y1 = r["title"]
        ty0, ty1 = y0 + 3, y1 - 1
        n = 48
        for i in range(n):
            xa, xb = 3 + (W - 6) * i // n, 3 + (W - 6) * (i + 1) // n
            c.create_rectangle(xa, ty0, xb + 1, ty1, fill=mix("#000080", "#1084d0", i / float(n - 1)), outline="", tags="chrome")
        th = ty1 - ty0
        c.create_rectangle(8, ty0 + 3, 8 + th - 6, ty1 - 3, fill="#ffffff", outline="#000000", tags="chrome")
        self.T(8 + (th - 6) / 2, (ty0 + ty1) / 2, "M", 11, "#000080", "center", "chrome", True, False)
        bw, bh = int(th * 1.05), th - 5
        bx = W - 8 - bw
        for kind, act in (("x", "quit"), ("max", "full"), ("min", "min")):
            b = (bx, ty0 + 2, bx + bw, ty0 + 2 + bh)
            self.bevel(b, True)
            cx_, cy_ = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
            if kind == "x":
                c.create_line(cx_ - 4, cy_ - 4, cx_ + 4, cy_ + 4, fill="#000000", width=2, tags="chrome")
                c.create_line(cx_ - 4, cy_ + 4, cx_ + 4, cy_ - 4, fill="#000000", width=2, tags="chrome")
            elif kind == "max":
                c.create_rectangle(cx_ - 5, cy_ - 5, cx_ + 5, cy_ + 5, outline="#000000", fill="", tags="chrome")
                c.create_line(cx_ - 5, cy_ - 4, cx_ + 5, cy_ - 4, fill="#000000", width=2, tags="chrome")
            else:
                c.create_line(cx_ - 4, cy_ + 4, cx_ + 4, cy_ + 4, fill="#000000", width=2, tags="chrome")
            self.hot.append((b[0], b[1], b[2], b[3], act))
            bx -= bw + (6 if kind == "max" else 1)
        # ---- menu row (grey), greyed key hints on the right
        mx0, my0, mx1, my1 = r["menu"]
        self.B((3, my0, W - 3, my1 + 1), G, None, "chrome")
        c.create_line(3, my1, W - 3, my1, fill="#808080", tags="chrome")
        # The menu row is dedicated to the three workspace tabs; the four
        # instrument actions now live at the bottoms of their own panels.
        self._primary_tabs(mx0 + int(12 * self.sx))
        # sunken frame around the dark content area
        self.bevel((4, my1 + 2, W - 4, r["status"][1] - 2), False, None)
        # ---- status area: sunken ticker field, HOLD + status fields
        sx0, sy0, sx1, sy1 = r["status"]
        self.B((3, sy0, W - 3, H - 3), G, None, "chrome")
        # No market/news runner: one footer status field remains for brief messages.
        ry0, ry1 = sy0 + 4, H - 8
        ry = (ry0 + ry1) / 2
        self.bevel((8, ry0, W - 8, ry1), False, G)
        self.tick_id = self.T(8, ry, "", 12, "#404040", "w", "chrome")
        self.hold_id = self.T(8, ry, "", 12, "#404040", "w", "chrome")
        self.stat_id = self.T(W / 2, ry, "", 12, "#404040", "center", "chrome", False, False)
        self.tick_n, self.tick_full = 0, ""

    def _primary_tabs(self, x):
        """Six persistent workspace tabs in the header, including CRT modes.

        Keep all navigation within the previous menu row. Layout presets and
        the independent panels do not move when switching tabs.
        """
        from oracle_skin import hexmix
        c = self.c
        _, y0, x1, y1 = self.rect["menu"]
        tabs = (("HOME", "tab_home"), ("OGGCULTIST", "tab_oggcultist"),
                ("EIDOLITH", "tab_eidolith"), ("AUGURSPEX", "tab_augurspex"),
                ("PASSPHRASE", "tab_passphrase"), ("TOUCH TYPE", "tab_touch_type"))
        if self.case_on():
            # The physical CRT's nixie module protrudes over the inner glass
            # at the extreme upper left. Keep HOME visible inside the aperture.
            x += max(52, round(70 * self.k))
        gap = max(3, round(6 * self.k))
        pad = max(6, round(12 * self.k))
        h = min(max(22, round(28 * self.k)), max(20, y1 - y0 - 4))
        font = self.font(12, True, False)
        widths = [font.measure(label) + 2 * pad for label, _ in tabs]
        available = max(165, x1 - x - max(85, round(116 * self.k)))
        scale = min(1.0, max(0.5, (available - (len(tabs)-1) * gap) / sum(widths)))
        widths = [max(52, int(w * scale)) for w in widths]
        y = int((y0 + y1 - h) / 2)
        self.nav_tabs = {}
        for idx, ((label, action), w) in enumerate(zip(tabs, widths)):
            x0 = int(x)
            x2 = x0 + w
            panel = c.create_rectangle(x0, y, x2, y + h,
                                       fill=OGG_EMBER['raised'], outline=OGG_EMBER['line_strong'],
                                       width=1, tags="chrome")
            # A smaller font is chosen for tight CRT aperture scales.
            fs = min(12, max(8, round(12 * scale)))
            if font.measure(label) * fs / 12.0 > w - 8:
                label = {"PASSPHRASE": "PASS", "OGGCULTIST": "OGG", "TOUCH TYPE": "TYPE", "EIDOLITH": "EIDO", "AUGURSPEX": "AUGUR"}.get(label, label)
            tid = self.T((x0+x2)/2, y + h/2, label, fs, "txt", "center", "chrome", True, False)
            self.hot.append((x0, y0, x2, y1, action))
            self.nav_tabs[action] = (panel, tid)
            x = x2 + gap
        self._update_primary_tab_state()

    def _update_primary_tab_state(self):
        active = "tab_passphrase" if getattr(self, "dk", None) is not None else (
            "tab_oggcultist" if getattr(self, "ogg", None) is not None else (
            "tab_touch_type" if getattr(self, "touch", None) is not None else (
            "tab_eidolith" if getattr(self, "eido", None) is not None else (
            "tab_augurspex" if getattr(self, "aug", None) is not None else "tab_home"))))
        for action, pair in getattr(self, "nav_tabs", {}).items():
            on = action == active
            try:
                self.c.itemconfigure(pair[0], fill=OGG_EMBER['accent'] if on else OGG_EMBER['raised'],
                                     outline=OGG_EMBER['accent'] if on else OGG_EMBER['line_strong'])
                self.c.itemconfigure(pair[1], fill=OGG_EMBER['text_on_accent'] if on else OGG_EMBER['text'])
            except Exception:
                pass

    def _tab_strip(self, menu_end, hint_ink):
        """The menu row's right side: the passphrase tab strip from menu_end, the key hints at the far right.
        Every tab is the same size: the largest step of the tab size ladder that fits the row, every tab at the same slant."""
        c = self.c
        mx0, my0, mx1, my1 = self.rect["menu"]
        lx = mx1 - int(12 * self.sx)
        h1 = self.T(lx, my0 + (my1 - my0) * 0.30, "SPACE next  ENTER speak  N word  T deal", 11, hint_ink, "e", "chrome", False, False)
        hints = (["K passphrase"] if self.dk_mod else []) + ["F size", "ESC quit"]
        h2 = self.T(lx, my0 + (my1 - my0) * 0.72, "  ".join(hints), 11, hint_ink, "e", "chrome", False, False)
        self.deck_tab = self.dk_tab = self.ld_tab = None
        strip = ["dk"] if self.dk_mod else []
        gap = max(6, int(TAB_GAP * self.sx))
        tx = menu_end + gap
        tw, th = self._tab_size(len(strip), my1 - my0 - int(5 * self.sy), lx - tx, gap)
        if len(strip) > 1 and tx + len(strip) * tw + (len(strip) - 1) * gap > lx:          # still too wide even squeezed: close the gaps up (never below 3 px)
            gap = max(3, (lx - tx - len(strip) * tw) // (len(strip) - 1))
        if tx + len(strip) * (tw + gap) > min(c.bbox(h1)[0], c.bbox(h2)[0]):     # the key hints give way to the strip
            c.delete(h1)
            c.delete(h2)
        self.tab_size = (tw, th)
        draw = {"dk": self._dk_tab}
        for name in strip:
            draw[name](my1, tx, tw, th)
            tx += tw + gap

    def _tab_strip_clean(self, x, hints_too=True):
        """1046: the clean look's tabs are one segmented control.  1047: PASSPHRASE sits on the home bench, so there the bar is
        only the passphrase control.  An open tool is the filled segment and the word stays, so a second click returns to the dashboard.  The 90s tab art stays in --retro."""
        from oracle_skin import bar, hexmix, px
        c, k = self.c, self.k
        mx0, my0, mx1, my1 = self.rect["menu"]
        mid = (my0 + my1) / 2.0
        lx = mx1 - int(12 * self.sx)
        home = False  # Passphrase is an actual tab now
        hints = ["SPACE next", "ENTER speak", "N word", "T deal"] + \
                (["K roll" if home else "K passphrase"] if self.dk_mod else []) + ["ESC quit"]
        self.deck_tab = self.dk_tab = self.ld_tab = None
        f = self.font(12, True, False)
        pad = px(12, k)
        items = [] if home or self.case_on() else ([("dk", "PASSPHRASE", "dk")] if self.dk_mod else [])      # PASS in the case
        words, widths = [], []
        for key, label, act in items:
            word = label
            w_ = f.measure(word) + 2 * pad
            words.append(word)
            widths.append(w_)
        ch = min(px(28, k), max(18, int(my1 - my0) - px(8, k)))
        cy0 = int((my0 + my1) / 2.0 - ch / 2.0)
        top = getattr(self, "menu_bg", self.col("bg"))
        grp = hexmix(top, "#000000", 0.18)
        if items:
            self.put_three(bar(k, ch, grp, grp, 8, hexmix(grp, "#ffffff", 0.08), None, 0.0, 0.0, 6, 0.0, top), x, cy0, x + sum(widths), "chrome")
        for i, ((key, label, act), word, w_) in enumerate(zip(items, words, widths)):
            if i:
                c.create_line(x, cy0 + px(6, k), x, cy0 + ch - px(6, k), fill=hexmix(grp, "#ffffff", 0.12), tags="chrome")
            on = key == "dk" and self.dk is not None
            mark = c.create_rectangle(x + px(2, k), cy0 + px(2, k), x + w_ - px(2, k), cy0 + ch - px(2, k),
                                      fill=self.col("cyan"), outline="", state="normal" if on else "hidden", tags="chrome")
            txt = self.T(x + w_ / 2.0, mid, word, 12, "bg" if on else "txt", "center", "chrome", True, False)
            rec = dict(poly=None, line=mark, txt=txt, label=word, motion=None, mark=None)
            if key == "dk":
                self.dk_tab = rec
            self.hot.append((x, my0, x + w_, my1, act))
            x += w_
        tw = self.font(11, False, False)
        line1, line2 = "  ".join(hints[:5]), "  ".join(hints[5:])
        if hints_too and not self.case_on() and max(tw.measure(line1), tw.measure(line2)) + px(16, k) < lx - mx1 * 0.6:
            self.T(lx, my0 + (my1 - my0) * 0.32, line1, 11, "dim", "e", "chrome", False, False)
            self.T(lx, my0 + (my1 - my0) * 0.70, line2, 11, "dim", "e", "chrome", False, False)


    def clean_tab_state(self, t, on, label):
        """1046: the open segment is filled; the word stays the tool's name, and a second click returns to the dashboard."""
        try:
            self.c.itemconfigure(t["line"], state="normal" if on else "hidden")
        except Exception:
            self.c.itemconfigure(t["line"], fill=self.col("cyan") if on else getattr(self, "menu_bg", self.col("bg")))
        self.c.itemconfigure(t["txt"], text=label, fill=self.col("bg") if on else self.col("txt"))

    def _nav_group(self, x, my0, my1, top, look_too):
        """The menu words in one rounded segmented group on `top`, from x; returns where it ends.  1036: Look (A) in the clean look."""
        from oracle_skin import bar, hexmix, px
        c, k = self.c, self.k
        ch = px(28, k)
        cy0 = (my0 + my1) // 2 - ch // 2
        pad, f = px(12, k), self.font(14, False, False)
        items = (("Wire", "next"), ("Tongue", "word"), ("Cut", "deal"), ("Grade", "view")) + ((("Look", "look"),) if look_too else ())
        gw = sum(f.measure(l) + 2 * pad for l, _ in items)
        grp = hexmix(top, self.col("bg"), 0.55)
        self.put_three(bar(k, ch, grp, grp, 8, hexmix(grp, "#ffffff", 0.07), None, 0.0, 0.0, 6, 0.0, top), x, cy0, x + gw, "chrome")
        for i, (label, act) in enumerate(items):
            w_ = f.measure(label) + 2 * pad
            if i:
                c.create_line(x, cy0 + px(7, k), x, cy0 + ch - px(7, k), fill=hexmix(grp, "#ffffff", 0.10), tags="chrome")
            self.T(x + pad, (my0 + my1) / 2, label, 14, "txt", "w", "chrome", False, False)
            self.hot.append((x, my0, x + w_, my1, act))
            x += w_
        return x

    def _win_glyphs(self, x1, y0, y1, ink):
        """Close, maximise and minimise as bare glyphs (no boxes), right to left from x1, full height; their hot spots quit / full / min."""
        from oracle_skin import px
        c, k = self.c, self.k
        bw = int((y1 - y0) * 1.2)
        bx = x1 - bw
        lw = max(1, px(1, k))
        for kind, act in (("x", "quit"), ("max", "full"), ("min", "min")):
            cx_, cy_ = bx + bw / 2.0, (y0 + y1) / 2.0
            g = px(5, k)
            if kind == "x":
                c.create_line(cx_ - g, cy_ - g, cx_ + g, cy_ + g, fill=ink, width=lw, tags="chrome")
                c.create_line(cx_ - g, cy_ + g, cx_ + g, cy_ - g, fill=ink, width=lw, tags="chrome")
            elif kind == "max":
                c.create_rectangle(cx_ - g, cy_ - g, cx_ + g, cy_ + g, outline=ink, width=lw, tags="chrome")
            else:
                c.create_line(cx_ - g, cy_, cx_ + g, cy_, fill=ink, width=lw, tags="chrome")
            self.hot.append((bx, y0, bx + bw, y1, act))
            bx -= bw
        return bx + bw

    def _chrome_integrated(self):
        """1036, the integrated looks (FLOAT / PANES / GLASS): no window.  One header row holds the app mark, the menu, the tabs and the window
        glyphs; one footer row holds HOLD, the headlines and the status.  In PANES and GLASS they sit on the ground, edge to edge, and the panels'
        hairlines are the only borders (with one round the whole window); in FLOAT the header and footer are bars of their own, like the panels,
        and the ground between them is see-through (Scene.ground)."""
        from oracle_skin import bar, dot, hexmix, px
        c, r, k = self.c, self.rect, self.k
        W, H = self.W, self.H
        bg, acc, mag = self.col("bg"), self.col("cyan"), self.col("mag")
        float_ = self.floating()
        fill = self.skin_fill()
        surf = fill if float_ else bg
        hair = hexmix(self.col("panel"), "#ffffff", 0.16) if self.look() == "CLEAR" else hexmix(fill, "#ffffff", 0.08)
        # The embedded Oggcultist uses a near-black navigation surface and a
        # warmer raised player bar. Match both without moving the Oracle tabs.
        header_surf = OGG_EMBER['sidebar'] if self.clean() else surf
        footer_surf = OGG_EMBER['raised'] if self.clean() else surf
        self.menu_bg = header_surf
        hx0, hy0, hx1, hy1 = r["menu"]
        sx0, sy0, sx1, sy1 = r["status"]
        if float_:
            for b in ((hx0, hy0, hx1, hy1), (sx0, sy0, sx1, sy1)):
                self.put_three(bar(k, b[3] - b[1], surf, surf, 10, hair, None, 0.0, 0.0, 6, 0.0, self.ground()), b[0], b[1], b[2], "chrome")
        else:
            c.create_rectangle(0, 0, W, hy1, fill=header_surf, outline="", tags="chrome")
            c.create_rectangle(0, sy0, W, H, fill=footer_surf, outline="", tags="chrome")
            c.create_line(0, hy1, W, hy1, fill=OGG_EMBER['line'], tags="chrome")
            c.create_line(0, sy0, W, sy0, fill=OGG_EMBER['line_strong'], tags="chrome")
            c.create_rectangle(0, 0, W - 1, H - 1, outline=hair, tags=("chrome", "winedge"))
        # ---- header and menu
        cy = (hy0 + hy1) / 2.0
        x = hx0 + px(14, k)
        self._primary_tabs(x)
        if not self.case_on():
            self._win_glyphs(hx1 - px(4, k), hy0, hy1, self.col("txt"))
        # ---- footer: one line.  HOLD and the live/voice stamp are not drawn (1046); the ids stay.  1050: the marquee is back, teletype, dim;
        # a message takes the line while it is up.
        fy = (sy0 + sy1) / 2.0
        self.hold_id = self.T(sx0 + px(14, k), fy, "", 13, "txt", "w", "chrome", True)
        self.stat_id = self.T(sx0 + px(14, k), fy, "", 12, "txt", "w", "chrome", False, False)
        self.mono_w = max(1.0, self.font(12, False, True).measure("M"))
        self.tick_n = max(10, int((sx1 - sx0 - px(28, k)) / self.mono_w))
        self.tick_id = self.T(sx0 + px(14, k), fy, "", 12, "dim", "w", "chrome", False, True)
        self.tick_full = ""

    def _chrome_skin(self):
        """1031: the modern frame.  1033, a 2020s app header: the title bar and the menu row are one flat surface with a hairline under it; the app
        badge, the title in the UI face, Windows-11 style window glyphs with no boxes; the menu words share one rounded segmented group; the same
        tab strip.  The ticker, HOLD and status sit in flat wells on a flat footer.  Same hot spots and ids as the 98 frame."""
        if getattr(self, "integrated", lambda: False)():
            return self._chrome_integrated()
        from oracle_skin import bar, dot, hexmix, px
        c, r, k = self.c, self.rect, self.k
        W, H = self.W, self.H
        bg, edge, edge2, acc, mag = self.col("bg"), self.col("edge"), self.col("edge2"), self.col("cyan"), self.col("mag")
        clean = self.clean()
        top = hexmix(bg, self.col("panel"), 0.5) if clean else hexmix(bg, edge, 0.32)     # 1034: the clean header is the window's own ground
        hair = hexmix(top, "#ffffff", 0.07)
        self.menu_bg = top
        # ---- title bar
        x0, y0, x1, y1 = r["title"]
        th = y1 - y0
        mx0, my0, mx1, my1 = r["menu"]
        c.create_rectangle(0, 0, W, my1, fill=top, outline="", tags="chrome")
        ic = th - px(11, k)
        self.put(dot(ic, acc, mag, None, 0.0, 0, px(5, k)), px(10, k) + ic // 2, th // 2, "chrome", "center")
        self.T(px(10, k) + ic / 2.0, th / 2.0, "M", 11, bg, "center", "chrome", True, False)
        bw, bh = int(th * 1.35), th
        bx = W - bw
        lw = max(1, px(1, k))
        for kind, act in () if self.case_on() else (("x", "quit"), ("max", "full"), ("min", "min")):      # 1062: in the case, its chin keys
            b = (bx, 0, bx + bw, bh)
            cx_, cy_ = (b[0] + b[2]) / 2.0, (b[1] + b[3]) / 2.0
            g, ink = px(5, k), self.col("txt")
            if kind == "x":
                c.create_line(cx_ - g, cy_ - g, cx_ + g, cy_ + g, fill=ink, width=lw, tags="chrome")
                c.create_line(cx_ - g, cy_ + g, cx_ + g, cy_ - g, fill=ink, width=lw, tags="chrome")
            elif kind == "max":
                c.create_rectangle(cx_ - g, cy_ - g, cx_ + g, cy_ + g, outline=ink, width=lw, tags="chrome")
            else:
                c.create_line(cx_ - g, cy_, cx_ + g, cy_, fill=ink, width=lw, tags="chrome")
            self.hot.append((b[0], b[1], b[2], b[3], act))
            bx -= bw
        # ---- menu row: the menu words in one segmented group, then the tab strip
        c.create_line(0, my1, W, my1, fill=hair, tags="chrome")
        x = mx0 + int(12 * self.sx)
        self._primary_tabs(x)
        # ---- status: the ticker, HOLD and the status line in wells
        sx0, sy0, sx1, sy1 = r["status"]
        under = hexmix(bg, edge2, 0.40)
        c.create_rectangle(0, sy0, W, H, fill=under, outline="", tags="chrome")
        c.create_line(0, sy0, W, sy0, fill=hexmix(under, "#ffffff", 0.07), tags="chrome")
        m = px(10, k)
        # Only a temporary status message is shown; the scrolling ticker is gone.
        sb = (m, sy0 + px(5, k), W - m, H - px(6, k))
        self.skin_well(sb, "chrome", under=under)
        ry = (sb[1] + sb[3]) / 2
        self.tick_id = self.T(m, ry, "", 12, "dim", "w", "chrome")
        self.hold_id = self.T(m, ry, "", 12, "dim", "w", "chrome")
        self.stat_id = self.T((sb[0] + sb[2]) / 2, ry, "", 12, "dim", "center", "chrome", False, False)
        self.tick_n, self.tick_full = 0, ""

    def _crt(self):
        """CRT layer: fine scanlines plus a little static.  It covers the WHOLE Windows-98 window (frame, title bar,
        menu row, status bar included) and stops at the ornamental plastic case, which sits above it."""
        import tkinter as tk
        W, H, c = self.W, self.H, self.c
        self.crt_items = []
        self.crt_noise_id = None
        if not self.o.get("crt", True) or getattr(self, "crt_off", False):
            return
        self.crt_box = (0, 0, W, H)
        pad = 48
        try:
            if getattr(self, "crt_size", None) != (W, H) or not getattr(self, "crt_imgs", None):
                # Tk tiles a one-period PNG across the sheet (the full-sheet builders went in 1020; they had no caller since this landed)
                # instead of Python building and zlib-packing ~5 MB per sheet (most of a cold start and of every resize)
                self.crt_imgs = [self._tiled(scan_tile_png(20), W, H+3)]
                self.noise_imgs = [self._tiled(noise_tile_png(sd), W + pad, H + pad) for sd in (11, 23, 37)]
                self.crt_size = (W, H)
        except Exception:
            self.crt_imgs = None
            return
        self.crt_pad = pad
        self.crt_main = c.create_image(0, 0, image=self.crt_imgs[0], anchor="nw", tags="crt")
        self.crt_noise_id = c.create_image(0, 0, image=self.noise_imgs[0], anchor="nw", tags="crt")

    def _tiled(self, png, w, h):
        """A w x h photo filled by repeating the PNG from (0, 0): pixel (x, y) = tile(x % tw, y % th)."""
        import tkinter as tk
        tile = tk.PhotoImage(master=self.c, data=base64.b64encode(png))
        img = tk.PhotoImage(master=self.c, width=w, height=h)
        self.c.tk.call(str(img), "copy", str(tile), "-to", 0, 0, w, h, "-compositingrule", "set")
        return img

    def _glass_overlay(self):
        """1068: real-alpha CRT curvature/shadow cues inside the aperture.

        The generated photo case always stays on top. Only build photos when
        bezel is present, and preserve those photos on the Scene instance so
        Tk does not garbage-collect them. This never replaces/warps text.
        """
        self.glass_ids, self.glass_imgs = None, []
        if not self.case_on() or self.W < 100 or self.H < 100:
            return
        try:
            import tkinter as tk
            from oracle_glass import edge_png, barrel_png, sweep_png, silhouette_png, curved_screen_png, scan_beam_png, convex_glass_png
            def im(data):
                img = tk.PhotoImage(master=self.c, data=base64.b64encode(data))
                self.glass_imgs.append(img)
                return img
            # A 32px neutral falloff along the inside perimeter. These are
            # distinct alpha layers and do not block normal mouse events.
            sh = 32
            left = self._tiled(edge_png(True, sh), sh, self.H)
            right0 = im(edge_png(True, sh, True))
            right = tk.PhotoImage(master=self.c, width=sh, height=self.H)
            self.c.tk.call(str(right), "copy", str(right0), "-to", 0, 0, sh, self.H, "-compositingrule", "set")
            top = self._tiled(edge_png(False, sh), self.W, sh)
            bottom0 = im(edge_png(False, sh, True))
            bottom = tk.PhotoImage(master=self.c, width=self.W, height=sh)
            self.c.tk.call(str(bottom), "copy", str(bottom0), "-to", 0, 0, self.W, sh, "-compositingrule", "set")
            self.glass_imgs += [left, right, top, bottom]
            c=self.c
            c.create_image(0,0,image=left,anchor="nw",tags="glare")
            c.create_image(self.W,0,image=right,anchor="ne",tags="glare")
            c.create_image(0,0,image=top,anchor="nw",tags="glare")
            c.create_image(0,self.H,image=bottom,anchor="sw",tags="glare")
            barrel=im(barrel_png(self.W,self.H,1.62))
            c.create_image(0,0,image=barrel,anchor="nw",tags="glare")
            dome=im(convex_glass_png(self.W,self.H))
            c.create_image(0,0,image=dome,anchor="nw",tags="glare")
            # Draw a mathematically bowed inner aperture.  This is important:
            # the program must not look like a flat rectangular UI behind
            # a rounded photographic bezel.
            curve=im(curved_screen_png(self.W,self.H))
            c.create_image(0,0,image=curve,anchor="nw",tags="glare")
            sweep=im(sweep_png(260,max(280,int(self.H*.98))))
            reflection=c.create_image(-300,self.H*.03,image=sweep,anchor="nw",tags="glare")
            second=im(sweep_png(156,max(210,int(self.H*.80))))
            secondary=c.create_image(-240,self.H*.13,image=second,anchor="nw",tags="glare")
            beam=im(scan_beam_png(self.W,108))
            rolling=c.create_image(0,-100,image=beam,anchor="nw",tags="glare")
            silhouette=im(silhouette_png())
            person=c.create_image(self.W*.80,self.H*.40,image=silhouette,anchor="center",state="hidden",tags="glare")
            self.glass_ids=(reflection,secondary,rolling,person)
        except Exception:
            self.c.delete("glare")
            self.glass_ids, self.glass_imgs = None, []

    def _glass_tick(self,now):
        ids=getattr(self,"glass_ids",None)
        if not ids:return
        elapsed=max(0,now-getattr(self,"t0",now))
        # Two reflections drift at different speeds, to suggest actual curved
        # glass catching light rather than a single flat stripe.
        sweep_x=-300+(elapsed%18.0)/18.0*(self.W+620)
        self.c.coords(ids[0],sweep_x,self.H*.03+math.sin(elapsed*.42)*11)
        second_x=self.W+220-((elapsed+6)%27.0)/27.0*(self.W+470)
        self.c.coords(ids[1],second_x,self.H*.12+math.sin(elapsed*.26+1.6)*14)
        # Slow rolling phosphor refresh beam, not frame-synchronous flashing.
        scan_y=-125+(elapsed%8.9)/8.9*(self.H+260)
        self.c.coords(ids[2],0,scan_y)
        visible=94.8<(elapsed%97.0)<96.0
        self.c.itemconfigure(ids[3],state="normal" if visible else "hidden")

    def _crt_tick(self, now, dt):
        """Static: every third frame the noise sheet swaps and jumps to a new offset (it is larger than the window).
        Frame-based: 10 Hz at the default 30 fps."""
        if not getattr(self, "crt_imgs", None) or not self.crt_noise_id:
            return
        if self.frame_no % 4 == 0:
            rng = self.rng
            self.c.itemconfigure(self.crt_noise_id, image=rng.choice(self.noise_imgs))
            self.c.coords(self.crt_noise_id, -rng.randint(0, 9), -rng.randint(0, 9))
        # Slowly roll one scanline phase every few frames. Existing scanline
        # sheet is opaque only on thin horizontal rows (never over the bezel).
        if getattr(self,'crt_main',None):
            phase=int(now*1.8)%3
            if phase!=getattr(self,'_crt_phase',None):
                self._crt_phase=phase
                self.c.coords(self.crt_main,0,phase-2)

