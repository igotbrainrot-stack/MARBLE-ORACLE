"""oracle_train -- a real (small) 3-D train for the TRANSMISSION scene.  Pure python; Tk only for the polygons.

The camera stands beside a straight track.  The rails, the sleepers and every polygon of the train go through the SAME
perspective projection, so the train is genuinely riding the rails: it starts as a speck at the vanishing point, its
nose swells and its flank swings past, car after car, until the tail has gone by.  Nothing is a pre-drawn picture.

Optional in every sense: the host imports this in a try/except and falls back to the old flat cars.
World units are metres: X right, Y up, Z away from the camera.
"""
import random

NL, CL, NCARS = 12.0, 25.0, 5          # nose length, car length, cars between the two noses
LTOT = 2 * NL + NCARS * CL
HW = 1.7                                # half width of the body
V = 78.0                                # train speed, m/s
Z0 = 420.0                              # where the nose starts (a speck near the horizon)
ZCLIP = 5.0                             # nearer than this is cut off

BASE = dict(body="#eef6fb", bodyM="#c3d6e6", bodyL="#ffffff", bodyD="#8ea9c4", blue="#1f63d6", blueD="#123c93", blueL="#5da4ff",
            win="#26327e", winHi="#5f78d8", glass="#1b2262", glassHi="#8ea2ff", skirt="#0d1030", grey="#7d8797", greyD="#3f4860",
            line="#16214f", shadow="#05030f", lamp="#fff6b0", glow="#8cf6ff")

NS = (0.0, 0.08, 0.2, 0.38, 0.6, 0.8, 1.0)


def _ytop(n):
    return 1.75 + 1.85 * n ** 0.75


def _ybot(n):
    return 0.55 - 0.20 * n


def _hw(n):
    return 0.50 + (HW - 0.50) * n ** 0.6


def clip_rect(pts, x0, y0, x1, y1):
    """Sutherland-Hodgman against an axis-aligned rectangle."""
    for axis, lim, keep_ge in ((0, x0, True), (0, x1, False), (1, y0, True), (1, y1, False)):
        if not pts:
            return pts
        out = []
        prev = pts[-1]
        for cur in pts:
            pin = (prev[axis] >= lim) if keep_ge else (prev[axis] <= lim)
            cin = (cur[axis] >= lim) if keep_ge else (cur[axis] <= lim)
            if cin != pin:
                t = (lim - prev[axis]) / float(cur[axis] - prev[axis])
                out.append((prev[0] + (cur[0] - prev[0]) * t, prev[1] + (cur[1] - prev[1]) * t))
            if cin:
                out.append(cur)
            prev = cur
        pts = out
    return pts


def _clip_line(a, b, x0, y0, x1, y1):
    """Liang-Barsky: the part of segment a-b inside the rectangle, or None."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, a[0] - x0), (dx, x1 - a[0]), (-dy, a[1] - y0), (dy, y1 - a[1])):
        if p == 0:
            if q < 0:
                return None
            continue
        t = q / float(p)
        if p < 0:
            if t > t1:
                return None
            t0 = max(t0, t)
        else:
            if t < t0:
                return None
            t1 = min(t1, t)
    return [(a[0] + dx * t0, a[1] + dy * t0), (a[0] + dx * t1, a[1] + dy * t1)]


def clip_near(pts):
    """Cut a 3-D polygon at the near plane z = ZCLIP."""
    out = []
    prev = pts[-1]
    for cur in pts:
        pin, cin = prev[2] >= ZCLIP, cur[2] >= ZCLIP
        if cin != pin:
            t = (ZCLIP - prev[2]) / (cur[2] - prev[2])
            out.append((prev[0] + (cur[0] - prev[0]) * t, prev[1] + (cur[1] - prev[1]) * t, ZCLIP))
        if cin:
            out.append(cur)
        prev = cur
    return out


class Rig:
    """The camera: eye height h, horizon row hz, vanishing column vx, focal length f (px at z = 1), track centre c0."""
    H = 2.2
    C0 = 9.0                # the track runs to the right of the camera, so we see the train's left flank

    def __init__(self, hz, vx, sy1, zbottom=14.0):
        self.hz, self.vx, self.sy1 = hz, vx, sy1
        self.f = max(60.0, (sy1 - hz)) * zbottom / self.H        # the rails reach the bottom of the scene at z = zbottom
        self.zb = zbottom

    def proj(self, X, Y, Z):
        k = self.f / Z
        return (self.vx + X * k, self.hz - (Y - self.H) * k)


class Part:
    __slots__ = ("v", "key", "outline", "stipple", "n", "car", "lod")

    def __init__(self, v, key, outline=False, stipple="", n=None, car=-1, lod=0):
        self.v, self.key, self.outline, self.stipple, self.n, self.car, self.lod = v, key, outline, stipple, n, car, lod


def _model():
    """The train in its own coordinates: X across (track centre = 0), Y up, dz = metres behind the nose tip.
    Returned far -> near, which is the painter's order for a camera in front of the train."""
    parts = []
    # the shadow on the ballast, cast a little toward the camera side (drawn first: it is on the ground)
    parts.append(Part([(-2.6, 0.01, -1.0), (1.9, 0.01, -1.0), (1.9, 0.01, LTOT + 1.0), (-2.6, 0.01, LTOT + 1.0)], "shadow", stipple="gray50"))

    def quad(x, y0, y1, za, zb, key, **kw):
        parts.append(Part([(x, y0, za), (x, y1, za), (x, y1, zb), (x, y0, zb)], key, n=(1, 0, 0), **kw))

    def nose(zn, sgn, head):
        """zn(n) -> dz along the train for sample n; sgn = +1 when dz grows with n (the head), -1 for the tail."""
        # right flank facets, from the body end (n = 1) toward the tip
        for i in range(len(NS) - 1, 0, -1):
            a, b = NS[i - 1], NS[i]
            za, zb = zn(a), zn(b)
            slope = (_hw(b) - _hw(a)) / abs(zb - za)
            nrm = (1.0, 0.0, -sgn * slope)
            xa, xb = _hw(a), _hw(b)
            P = lambda x, y, z: (x, y, z)
            parts.append(Part([P(xa, _ybot(a), za), P(xa, _ytop(a), za), P(xb, _ytop(b), zb), P(xb, _ybot(b), zb)], "body", n=nrm))
            # blue band + pale line follow the belly line
            parts.append(Part([P(xa, _ybot(a) + 0.42, za), P(xa, _ybot(a) + 1.02, za), P(xb, _ybot(b) + 1.02, zb), P(xb, _ybot(b) + 0.42, zb)],
                              "blue", n=nrm))
            parts.append(Part([P(xa, _ybot(a) + 1.02, za), P(xa, _ybot(a) + 1.10, za), P(xb, _ybot(b) + 1.10, zb), P(xb, _ybot(b) + 1.02, zb)],
                              "blueL", n=nrm))
        # the top of the nose, sloping down to the tip
        for i in range(len(NS) - 1, 0, -1):
            a, b = NS[i - 1], NS[i]
            za, zb = zn(a), zn(b)
            slope = (_ytop(b) - _ytop(a)) / abs(zb - za)
            nrm = (0.0, 1.0, -sgn * slope)
            parts.append(Part([(-_hw(a), _ytop(a), za), (_hw(a), _ytop(a), za), (_hw(b), _ytop(b), zb), (-_hw(b), _ytop(b), zb)],
                              "bodyL", n=nrm))
            if head and 0.19 < a < 0.99:                          # windscreen: dark glass with two pale reflections
                w = 0.66
                lift = 0.012
                parts.append(Part([(-w * _hw(a), _ytop(a) + lift, za), (w * _hw(a), _ytop(a) + lift, za),
                                   (w * _hw(b), _ytop(b) + lift, zb), (-w * _hw(b), _ytop(b) + lift, zb)], "glass", outline=True, n=nrm))
                parts.append(Part([(0.05 * _hw(a), _ytop(a) + 2 * lift, za), (0.32 * _hw(a), _ytop(a) + 2 * lift, za),
                                   (0.32 * _hw(b), _ytop(b) + 2 * lift, zb), (0.05 * _hw(b), _ytop(b) + 2 * lift, zb)], "glassHi", stipple="gray50", n=nrm))
        if head:                                                  # the tip: a dark cone with the lamps
            parts.append(Part([(-_hw(0), _ybot(0), 0.0), (_hw(0), _ybot(0), 0.0), (_hw(0), _ytop(0), 0.0), (-_hw(0), _ytop(0), 0.0)],
                              "greyD", outline=True, n=(0, 0, -1)))
            parts.append(Part([(-_hw(0) * .8, _ybot(0) + 0.06, -0.02), (_hw(0) * .8, _ybot(0) + 0.06, -0.02),
                               (_hw(0) * .8, _ybot(0) + 0.30, -0.02), (-_hw(0) * .8, _ybot(0) + 0.30, -0.02)], "blue", n=(0, 0, -1)))

    # ---- tail nose (far end), then the cars from the last to the first, then the head nose
    nose(lambda n: LTOT - n * NL, -1, False)
    for k in range(NCARS - 1, -1, -1):
        za, zb = NL + k * CL, NL + (k + 1) * CL
        X = HW
        quad(X, 0.35, 3.60, za, zb, "body", car=k)
        quad(X, 3.36, 3.60, za, zb, "bodyM", car=k)                     # roof shoulder
        quad(X, 0.35, 0.78, za, zb, "skirt", car=k)
        quad(X, 0.78, 1.55, za, zb, "blue", car=k)
        quad(X, 1.55, 1.64, za, zb, "blueD", car=k)
        quad(X, 2.88, 2.98, za, zb, "blueL", car=k)
        quad(X, 2.00, 2.76, za + 0.4, zb - 0.4, "win", lod=0, car=k)     # far: one ribbon
        # near: separate windows and door seams
        for j in range(12):
            wa = za + 2.6 + j * 1.75
            quad(X, 2.00, 2.76, wa, wa + 1.25, "win", lod=1, car=k)
            quad(X, 2.50, 2.76, wa, wa + 1.25, "winHi", lod=1, car=k)
        for dz in (0.5, 22.2):
            quad(X, 0.80, 3.0, za + dz, za + dz + 1.7, "bodyM", lod=1, car=k)
            quad(X, 0.9, 2.9, za + dz + 0.25, za + dz + 0.85, "bodyD", lod=1, car=k)
            quad(X, 0.9, 2.9, za + dz + 0.9, za + dz + 1.5, "bodyD", lod=1, car=k)
        for dz in (4.6, 20.4):                                          # bogies
            quad(X - 0.25, 0.08, 0.62, za + dz - 1.4, za + dz + 1.4, "greyD", car=k)
            quad(X - 0.25, 0.08, 0.30, za + dz - 1.4, za + dz + 1.4, "line", car=k)
        quad(X + 0.001, 0.4, 3.4, za - 0.2, za + 0.2, "skirt", car=k)  # the joint between cars
    nose(lambda n: n * NL, +1, True)
    for pt in parts:                                     # built as the right flank; mirror it for a camera left of the track
        pt.v = [(-x, y, z) for x, y, z in pt.v]
        if pt.n is not None:
            pt.n = (-pt.n[0], pt.n[1], pt.n[2])
    return parts


class Train3D:
    POOL = 330

    def __init__(self, canvas, box, hz, vx, sy1, mix, fog, ground, tags=("content", "train"), zbottom=14.0):
        self.c = canvas
        self.box = box                      # the scene rectangle: everything is clipped to it
        self.rig = Rig(hz, vx, sy1, zbottom)
        self.mix, self.fog = mix, fog
        self.tags = tags
        self.rng = random.Random(5)
        self.parts = _model()
        self.track_items = self._track(ground)          # rails first: the train is created after, so it rides on top of them
        self.cols = {}
        self.slots = []                     # [item, fill, outline, stipple] per pooled polygon
        self.shown = 0
        self.zf = None
        for _ in range(self.POOL):
            it = canvas.create_polygon(0, 0, 0, 0, 0, 0, fill="", outline="", state="hidden", tags=tags)
            self.slots.append([it, "", "", ""])
        # lamps: two bright ovals with a soft halo each, plus the light on the rails ahead
        self.lamps = [canvas.create_oval(0, 0, 0, 0, fill=BASE["lamp"], outline="", state="hidden", tags=tags) for _ in range(2)]
        self.halos = [canvas.create_oval(0, 0, 0, 0, fill=BASE["glow"], outline="", stipple="gray25", state="hidden", tags=tags) for _ in range(2)]
        self._poles()                                   # telegraph poles beside the track, in front of the train

    def _poles(self):
        """A row of poles with two cross-arms on the camera's side of the track, receding to the vanishing point."""
        c, r = self.c, self.rig
        x0, y0, x1, y1 = self.box
        col = self.mix("#2a2148", self.fog, 0.15)
        px = r.C0 - 4.6
        z = 15.0
        while z < 520.0:
            k = r.f / z
            cx = r.vx + px * k
            w = max(1.0, 0.24 * k)
            top, bot = r.hz - (7.6 - r.H) * k, r.hz + r.H * k
            if x0 < cx < x1 and bot > y0 and top < y1:
                ya, yb = max(y0, top), min(y1, bot)
                c.create_rectangle(cx - w / 2, ya, cx + w / 2, yb, fill=col, outline="", tags=self.tags)
                for hy, ln in ((7.1, 1.5), (6.2, 1.1)):
                    ay = r.hz - (hy - r.H) * k
                    if y0 < ay < y1:
                        c.create_rectangle(max(x0, cx - ln * k), ay, min(x1, cx + ln * k), ay + max(1.0, 0.16 * k), fill=col, outline="", tags=self.tags)
            z *= 1.32

    # ------------------------------------------------------------------ static track (same camera as the train)
    def _track(self, ground):
        c, r = self.c, self.rig
        x0, y0, x1, y1 = self.box
        C0 = r.C0
        zn, zfar = r.zb, 2500.0

        def P(X, Z):
            return r.proj(X, 0.0, Z)

        ball = [P(C0 - 2.3, zn), P(C0 + 2.3, zn), P(C0 + 2.3, zfar), P(C0 - 2.3, zfar)]
        ball = clip_rect(ball, x0, y0, x1, y1)
        if len(ball) >= 3:
            c.create_polygon([v for p in ball for v in p], fill=self.mix(ground, "#6b78b4", 0.62), outline="", tags="content")
        # sleepers: one every 0.65 m of track, drawn only when >= 2.4 px above the last one (they bunch up toward the horizon)
        last, z = 1e9, zn
        while z < 900.0:
            a, b = P(C0 - 1.6, z), P(C0 + 1.6, z)
            if last - a[1] >= 2.4 and y0 <= a[1] <= y1:
                xa, xb = max(a[0], x0), min(b[0], x1)
                if xb > xa:
                    c.create_line(xa, a[1], xb, a[1], fill=self.mix(ground, "#d9b4f0", 0.78), width=max(1, int(4 * zn / z + 0.7)), tags="content")
                last = a[1]
            elif last > 1e8:
                last = a[1] + 3
            z += 0.65
        for sg in (-1, 1):                                      # the two rails, each with a bright top edge
            for off, col, wd in ((sg * 0.717, "#8fa0e8", 3), (sg * 0.717 - sg * 0.03, "#f2f6ff", 1)):
                seg = _clip_line(P(C0 + off, zn), P(C0 + off, zfar), x0, y0, x1, y1)
                if seg:
                    c.create_line(seg[0][0], seg[0][1], seg[1][0], seg[1][1], fill=col, width=wd, tags="content")
        return []

    # ------------------------------------------------------------------ per frame
    def color(self, key, z):
        b = int(min(15, max(0.0, z / 40.0)))              # distance haze: 16 buckets
        k = (key, b)
        v = self.cols.get(k)
        if v is None:
            v = self.mix(BASE[key], self.fog, min(0.75, (b / 15.0) ** 1.3 * 0.8))
            self.cols[k] = v
        return v

    def hide(self):
        if self.shown or self.zf is not None:
            for s in self.slots[:max(self.shown, 1)]:
                self.c.itemconfigure(s[0], state="hidden")
            for it in self.lamps + self.halos:
                self.c.itemconfigure(it, state="hidden")
        self.shown, self.zf = 0, None

    def update(self, ph, run):
        """ph = seconds into the pass; run = its length.  Outside the pass the train is hidden."""
        if ph < 0 or ph >= run:
            self.hide()
            return
        zf = Z0 - V * ph
        self.zf = zf
        r, c = self.rig, self.c
        x0, y0, x1, y1 = self.box
        C0, f, vx, hz, H = r.C0, r.f, r.vx, r.hz, r.H
        near = lambda car: zf + NL + car * CL < 75.0
        # rumble: a pixel or two once it is close
        jy = 0.0
        if zf < 120:
            jy = self.rng.choice((-1, 0, 0, 1)) * min(2.0, 0.6 + (120 - zf) / 60.0)
        used = 0
        slots = self.slots
        out = []

        for pt in self.parts:
            if pt.lod and not near(pt.car):
                continue
            if pt.car >= 0 and not pt.lod and near(pt.car) and pt.key == "win":
                continue                                    # the ribbon gives way to separate windows up close
            z0 = zf + pt.v[0][2]
            if z0 - 0 > Z0 + LTOT:
                continue
            if pt.n is not None:                           # facing test: the polygon must face the camera
                v0 = pt.v[0]
                nx, ny, nz = pt.n
                if nx * (0 - (C0 + v0[0])) + ny * (H - v0[1]) + nz * (0 - (zf + v0[2])) <= 0:
                    continue
            p3 = [(C0 + v[0], v[1], zf + v[2]) for v in pt.v]
            zmin = min(p[2] for p in p3)
            zmax = max(p[2] for p in p3)
            if zmax < ZCLIP:
                continue
            if zmin < ZCLIP:
                p3 = clip_near(p3)
                if len(p3) < 3:
                    continue
            s2 = [(vx + X * f / Z, hz - (Y - H) * f / Z + jy) for X, Y, Z in p3]
            xs = [p[0] for p in s2]
            if max(xs) < x0 or min(xs) > x1:
                continue
            s2 = clip_rect(s2, x0, y0, x1, y1)
            if len(s2) < 3:
                continue
            zc = (zmin + zmax) * 0.5
            hgt = max(p[1] for p in s2) - min(p[1] for p in s2)
            out.append((s2, self.color(pt.key, zc), self.color("line", zc) if (pt.outline and hgt > 7) else "", pt.stipple))
            used += 1
            if used >= self.POOL:
                break
        for i, (s2, fill, outline, stip) in enumerate(out):
            s = slots[i]
            c.coords(s[0], *[v for p in s2 for v in p])
            if s[1] != fill or s[2] != outline or s[3] != stip:
                c.itemconfigure(s[0], fill=fill, outline=outline, stipple=stip, state="normal")
                s[1], s[2], s[3] = fill, outline, stip
            elif i >= self.shown:
                c.itemconfigure(s[0], state="normal")
        for i in range(len(out), self.shown):
            c.itemconfigure(slots[i][0], state="hidden")
        self.shown = len(out)
        # lamps at the tip (only while the nose is on screen)
        for j, sg in enumerate((-1, 1)):
            X, Y, Z = C0 + sg * 0.32, 1.12, zf - 0.03
            if Z >= ZCLIP:
                k = f / Z
                px, py = vx + X * k, hz - (Y - H) * k + jy
                rr = max(1.4, 0.16 * k)
                gr = rr * 2.6
                if x0 < px < x1 and y0 < py < y1:
                    c.coords(self.lamps[j], px - rr, py - rr, px + rr, py + rr)
                    c.coords(self.halos[j], px - gr, py - gr, px + gr, py + gr)
                    c.itemconfigure(self.lamps[j], state="normal")
                    c.itemconfigure(self.halos[j], state="normal")
                    continue
            c.itemconfigure(self.lamps[j], state="hidden")
            c.itemconfigure(self.halos[j], state="hidden")
