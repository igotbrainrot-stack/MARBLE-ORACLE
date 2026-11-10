"""oracle_media.py -- Marble_Oracle's pictures (stdlib + tkinter only): the tarot deck and its scans (TarotImages),
the MARBLE ARCHIVE plates (Statue).  Each one
degrades silently when its asset is missing.  Split out of marble_oracle.py (build 0929); behaviour unchanged."""
import base64
import json
import math
import os

import oracle_assets
from oracle_assets import asset


def _zip(name):
    return oracle_assets.open_zip(name)


MAJOR = [("THE FOOL", "beginnings", "recklessness"), ("THE MAGICIAN", "skill", "trickery"),
         ("THE HIGH PRIESTESS", "intuition", "secrets kept too long"), ("THE EMPRESS", "abundance", "smothering"),
         ("THE EMPEROR", "structure", "rigidity"), ("THE HIEROPHANT", "tradition", "dogma"),
         ("THE LOVERS", "choice", "misalignment"), ("THE CHARIOT", "momentum", "loss of control"),
         ("STRENGTH", "patience", "self-doubt"), ("THE HERMIT", "solitude", "isolation"),
         ("WHEEL OF FORTUNE", "cycles", "bad timing"), ("JUSTICE", "fairness", "evasion"),
         ("THE HANGED MAN", "surrender", "stalling"), ("DEATH", "endings", "clinging"),
         ("TEMPERANCE", "balance", "excess"), ("THE DEVIL", "appetite", "release"),
         ("THE TOWER", "upheaval", "delayed collapse"), ("THE STAR", "hope", "discouragement"),
         ("THE MOON", "illusion", "clarity returning"), ("THE SUN", "joy", "dimmed joy"),
         ("JUDGEMENT", "reckoning", "self-excuse"), ("THE WORLD", "completion", "loose ends")]


SUITS = [("WANDS", "drive"), ("CUPS", "feeling"), ("SWORDS", "argument"), ("PENTACLES", "money")]
RANKS = ["ACE", "TWO", "THREE", "FOUR", "FIVE", "SIX", "SEVEN", "EIGHT", "NINE", "TEN", "PAGE", "KNIGHT", "QUEEN", "KING"]


def tarot_card(i):
    """0..77 -> (name, upright, reversed, suit_index or -1)."""
    if i < 22:
        n, u, r = MAJOR[i]
        return n, u, r, -1
    s, r = divmod(i - 22, 14)
    su, th = SUITS[s]
    return "%s OF %s" % (RANKS[r], su), "%s, early" % th if r < 5 else "%s, matured" % th, "%s, blocked" % th, s


class TarotImages:
    """tarot_cards.zip: '<name>.png' (e.g. the_fool.png, ace_of_cups.png) or '<index>.png'."""
    def __init__(self):
        self.z = _zip("tarot_cards.zip")
        self.names = {}
        if self.z:
            files = {os.path.splitext(os.path.basename(n))[0].lower(): n for n in self.z.namelist() if n.lower().endswith(".png")}
            for i in range(78):
                key = tarot_card(i)[0].lower().replace(" ", "_")
                n = files.get(key) or files.get("%02d" % i) or files.get(str(i))
                if n:
                    self.names[i] = n
        self.cache = {}

    @staticmethod
    def _rot180(tk, im):
        """Rotate 180 deg.  Tk's negative-subsample flip is tried first and verified on the corner
        pixels; if this Tk build does not honour it, fall back to strip-by-strip copies."""
        import tkinter
        w, h = im.width(), im.height()
        out = tkinter.PhotoImage(master=tk, width=w, height=h)
        try:
            tk.tk.call(str(out), "copy", str(im), "-subsample", -1, -1)
            if out.width() == w and out.height() == h and out.get(0, 0) == im.get(w - 1, h - 1) and out.get(w - 1, h - 1) == im.get(0, 0):
                return out
        except Exception:
            pass
        col = tkinter.PhotoImage(master=tk, width=w, height=h)
        for x in range(w):                                # mirror left-right
            tk.tk.call(str(col), "copy", str(im), "-from", x, 0, x + 1, h, "-to", w - 1 - x, 0)
        out = tkinter.PhotoImage(master=tk, width=w, height=h)
        for y in range(h):                                # mirror top-bottom
            tk.tk.call(str(out), "copy", str(col), "-from", 0, y, w, y + 1, "-to", 0, h - 1 - y)
        return out

    def get(self, tk, i, mw, mh, rev=False):
        if i not in self.names:
            return None
        k = (i, mw, mh, rev)
        if k not in self.cache:
            try:
                import tkinter
                im = tkinter.PhotoImage(master=tk, data=base64.b64encode(self.z.read(self.names[i])))
                best = (1, max(1, math.ceil(max(im.width() / float(mw), im.height() / float(mh)))))
                for z in (1,):                          # integer subsample only: fractional ratios alias badly
                    for d in range(1, 13):
                        if im.width() * z <= mw * d and im.height() * z <= mh * d and z * best[1] > best[0] * d:
                            best = (z, d)
                z, d = best
                out = tkinter.PhotoImage(master=tk, width=max(1, im.width() // d), height=max(1, im.height() // d))
                tk.tk.call(str(out), "copy", str(im), "-subsample", d, d)
                im = out
                if rev:                                   # reversed card = turned upside down (rotated 180 degrees)
                    im = self._rot180(tk, im)
                self.cache[k] = im
            except Exception as e:
                self.err = repr(e)
                self.cache[k] = None
        return self.cache[k]


class Statue:
    """MARBLE ARCHIVE: pre-baked ASCII plates (data/marble_archive.zip, built by tools/sculpt.py).
    Without the zip, oracle_ascii raycasts five plates (Discobolus, Venus de Milo, Winged Victory, Laocoon, Oracle) at
    44x30, frame by frame on demand and cached; if even that module cannot be imported, a pure-python torus stands in.
    The zip always wins when it loads."""
    W, H = 44, 30                     # the fallback grid; real plates carry their own size

    def __init__(self):
        self.plates = []
        self.names = []
        self.ramps = []
        z = _zip("marble_archive.zip")
        try:
            if z:
                man = z.read("MANIFEST").decode("utf-8", "replace").split("\n")
                nf = int([m for m in man if m.startswith("frames")][0].split()[1])
                self.names = [m.split(None, 2)[2] for m in man if m.startswith("plate ")]
                pf, pr = {}, {}
                for m in man:
                    if m.startswith("pframes "):
                        _, i, n = m.split()
                        pf[int(i)] = int(n)
                    elif m.startswith("pramp "):
                        _, i, r = m.split(" ", 2)
                        pr[int(i)] = r
                have = set(z.namelist())
                for p in range(len(self.names)):
                    n = pf.get(p, nf)
                    missing = [k for k in range(n) if "p%d_%02d.txt" % (p, k) not in have]
                    if missing:
                        raise KeyError("p%d_%02d.txt" % (p, missing[0]))
                    self.plates.append([None] * n)                     # frames are read from the zip when first shown
                    self.ramps.append(pr.get(p, " .,:;-=+*#%@"))       # 3.8 plates: ' .:-=+*#%@'
        except Exception:
            self.plates, self.names, self.ramps = [], [], []
        self.credits = {}                 # plate -> "credit" line of the MANIFEST (the source cast), when the zip has one
        try:
            if self.plates:
                for m_ in z.read("MANIFEST").decode("utf-8", "replace").split("\n"):
                    if m_.startswith("credit "):
                        _, i, c = m_.split(" ", 2)
                        self.credits[int(i)] = c.strip()
        except Exception:
            self.credits = {}
        self.step = {}                    # plate -> downsample step the panel asked for (set_fit); 1 = as baked
        self._crop = {}                   # plate -> (x0, y0, x1, y1) content box of the whole turn
        self.z = z if self.plates else None
        self.fallback = not self.plates
        self._ray = None                  # the oracle_ascii module while its plates are shown
        self._runs = {}
        self._dims = {}
        if self.fallback:
            try:
                import oracle_ascii
                self._ray = oracle_ascii
                self.names = list(oracle_ascii.NAMES)
                self.plates = [[None] * oracle_ascii.FRAMES for _ in oracle_ascii.PLATES]
                self.ramps = [oracle_ascii.RAMP] * len(oracle_ascii.PLATES)
                for i in range(len(self.plates)):          # every raycast frame is the full grid: no need to render a turn to size it
                    self._dims[i] = (oracle_ascii.W, oracle_ascii.H)
            except Exception:
                self._ray = None
                self.names = ["TORUS (FALLBACK)"]
                self.plates = [[None] * 72]
                self.ramps = [" .,-~:;=!*#$@"]
        self.nf = len(self.plates[0])

    def _raw(self, plate, k):
        return self.z.read("p%d_%02d.txt" % (plate, k)).decode("ascii", "replace")

    def crop_box(self, plate):
        """(x0, y0, x1, y1) that holds every frame of this plate's turn: the blank margins a big mesh raster carries
        (4.1-0934 plates are 160x80 with the figure in the middle) are cut once, the same for every frame, so the
        figure never slides as it turns."""
        plate %= len(self.plates)
        if plate not in self._crop:
            x0, y0, x1, y1 = 10 ** 6, 10 ** 6, 0, 0
            for k in range(len(self.plates[plate])):
                for y, line in enumerate(self._raw(plate, k).split("\n")):
                    t = line.rstrip()
                    if t.strip():
                        x0, x1 = min(x0, len(t) - len(t.lstrip())), max(x1, len(t))
                        y0, y1 = min(y0, y), max(y1, y + 1)
            self._crop[plate] = (x0, y0, x1, y1) if x1 else (0, 0, 1, 1)
        return self._crop[plate]

    def set_fit(self, plate, max_cols, max_rows):
        """The panel can show at most max_cols x max_rows characters: pick the smallest whole downsample step that
        makes this plate's cropped turn fit (1 = as baked).  Returns the step."""
        plate %= len(self.plates)
        if self.z is None:
            return 1
        x0, y0, x1, y1 = self.crop_box(plate)
        stepx = -(-(x1 - x0) // max(1, max_cols))
        stepy = -(-(y1 - y0) // max(1, max_rows))
        st = max(1, stepx, stepy)
        if self.step.get(plate, 1) != st:
            self.step[plate] = st
            self.plates[plate] = [None] * len(self.plates[plate])
            self._dims.pop(plate, None)
            for key in [k for k in self._runs if k[0] == plate]:
                del self._runs[key]
        return st

    def _shrink(self, plate, text):
        """Crop to the turn's box, then (step > 1) average each step x step block on the ramp: a block's mean band
        over its lit cells, lit when at least a third of the block is."""
        x0, y0, x1, y1 = self.crop_box(plate)
        rows = [l[x0:x1].ljust(x1 - x0) for l in (text.split("\n") + [""] * y1)[y0:y1]]
        st = self.step.get(plate, 1)
        if st <= 1:
            return "\n".join(r.rstrip() for r in rows)
        ramp = self.ramps[plate]
        top = max(1, len(ramp) - 1)
        out = []
        for by in range(0, len(rows), st):
            line = []
            for bx in range(0, x1 - x0, st):
                vals = [ramp.find(rows[y][x]) for y in range(by, min(by + st, len(rows)))
                        for x in range(bx, min(bx + st, x1 - x0)) if rows[y][x] != " "]
                n = st * st
                if len(vals) * 3 < n:
                    line.append(" ")
                else:
                    v = sum(max(0, a) for a in vals) / len(vals)
                    line.append(ramp[min(top, max(1, int(round(v))))])
            out.append("".join(line).rstrip())
        return "\n".join(out)

    def frame(self, plate, k):
        pl = self.plates[plate % len(self.plates)]
        k %= len(pl)
        if pl[k] is None and self.z is not None:
            try:
                pl[k] = self._shrink(plate % len(self.plates), self._raw(plate % len(self.plates), k))
            except Exception:
                pl[k] = self._torus(k * 2 * math.pi / len(pl))
        if pl[k] is None:
            if self._ray is not None:
                try:
                    pl[k] = self._ray.render(self._ray.PLATES[plate % len(self.plates)], k, len(pl))
                except Exception:          # a broken plate must not take the panel down: show the torus for that frame
                    pl[k] = self._torus(k * 2 * math.pi / len(pl))
            else:
                pl[k] = self._torus(k * 2 * math.pi / len(pl))
        return pl[k]

    def dims(self, plate):
        """(columns, rows) of the whole turn: every frame shares one box, so the figure never breathes as it revolves."""
        plate %= len(self.plates)
        if plate not in self._dims:
            fr = [self.frame(plate, k) for k in range(len(self.plates[plate]))]
            self._dims[plate] = (max(len(l) for f in fr for l in f.split("\n")), max(len(f.split("\n")) for f in fr))
        return self._dims[plate]

    def runs(self, plate, k):
        """[(row, col, text, band 0..9)] -- the character ramp IS the luminance, so it doubles as the colour."""
        plate %= len(self.plates)
        k %= len(self.plates[plate])
        key = (plate, k)
        r = self._runs.get(key)
        if r is None:
            ramp = self.ramps[plate]
            top = float(max(1, len(ramp) - 1))
            r = []
            for row, line in enumerate(self.frame(plate, k).split("\n")):
                i = 0
                while i < len(line):
                    if line[i] == " ":
                        i += 1
                        continue
                    band = min(9, max(0, int(round(max(0, ramp.find(line[i])) * 9 / top))))
                    j = i
                    while j < len(line) and line[j] != " " and min(9, max(0, int(round(max(0, ramp.find(line[j])) * 9 / top)))) == band:
                        j += 1
                    r.append((row, i, line[i:j], band))
                    i = j
            if len(self._runs) > 400:
                self._runs.clear()
            self._runs[key] = r
        return r

    def _torus(self, a):
        W, H = self.W, self.H
        buf = [" "] * (W * H)
        zb = [0.0] * (W * H)
        ramp = ".,-~:;=!*#$@"
        ca, sa = math.cos(a), math.sin(a)
        cb, sb = math.cos(a * 0.5), math.sin(a * 0.5)
        t = 0.0
        while t < 6.283:
            ct, st = math.cos(t), math.sin(t)
            p = 0.0
            while p < 6.283:
                cp, sp = math.cos(p), math.sin(p)
                cx, cy = 2 + ct, st
                x = cx * (cb * cp + sa * sb * sp) - cy * ca * sb
                y = cx * (sb * cp - sa * cb * sp) + cy * ca * cb
                z = 5 + ca * cx * sp + cy * sa
                ooz = 1.0 / z
                xp = int(W / 2 + W * 0.4545 * ooz * x)
                yp = int(H / 2 - H * 0.3333 * ooz * y)
                L = cp * ct * sb - ca * ct * sp - sa * st + cb * (ca * st - ct * sa * sp)
                if 0 <= xp < W and 0 <= yp < H and ooz > zb[xp + W * yp]:
                    zb[xp + W * yp] = ooz
                    buf[xp + W * yp] = ramp[max(0, int(L * 8))] if L > 0 else "."
                p += 0.07
            t += 0.09
        return "\n".join("".join(buf[j * W:(j + 1) * W]).rstrip() for j in range(H))


