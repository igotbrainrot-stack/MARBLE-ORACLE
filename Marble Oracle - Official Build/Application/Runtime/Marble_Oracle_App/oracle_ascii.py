"""MARBLE ARCHIVE fallback: five statues raycast to ASCII in pure Python (math only; no numpy, no z-buffer).

Used by marble_oracle.Statue only when data/marble_archive.zip is missing or unreadable; the zip, when it loads, is the
real statue set.  One ray per cell of a 44 x 30 grid, 36 frames per turn.  The glyph's index in RAMP is the marble
colour the host paints it in (Statue.runs), so a hit is never a space and everything written is on the ramp.

Geometry.  The camera sits at (0, 0, DIST) looking toward -Z; +X is screen-right, +Y is up, row 0 is the top row.
Cells are tall, so the ray fan is squeezed vertically: (H * SY) / (W * SX) == 0.50 keeps a sphere round on the panel.
Yaw turns the statue about +Y; it is applied to the ray (world -> object), never to the primitives.

    render(key, frame, nframes=FRAMES) -> str     H lines of W characters; KeyError for an unknown key
    PLATES / NAMES                                the five keys in panel order and their panel names
"""
import math

W, H, FRAMES = 44, 30, 36
SX = 0.50
SY = (0.50 * W * SX) / H          # (H * SY) / (W * SX) == 0.50: the aspect lock
DIST = 2.35
T_MIN = 0.05
RAMP = " .,:;-=+*#%@"
TOP = len(RAMP) - 1               # 11: '@'
DARK = 0.08                       # at or below this Lambert value a hit is written as '.' (ramp index 1)


def _norm(v):
    """Unit vector along v; ValueError for the zero vector (a degenerate primitive, never silently accepted)."""
    n = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])
    if n == 0.0:
        raise ValueError("oracle_ascii: zero-length vector")
    return (v[0] / n, v[1] / n, v[2] / n)


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


LIGHT = _norm((-0.55, 0.72, 0.42))


# ---- primitives: hit(origin, direction) -> (t, outward unit normal) or None ---------------------------------------
class Sphere:
    """Sphere at `centre` with radius `radius`; `bump` raises the ramp index of its hits (kept within the ramp)."""

    def __init__(self, centre, radius, bump=0):
        if radius <= 0:
            raise ValueError("Sphere radius must be positive")
        self.c, self.r, self.bump = tuple(map(float, centre)), float(radius), int(bump)

    def hit(self, o, d):
        oc = _sub(o, self.c)
        a = _dot(d, d)
        b = 2.0 * _dot(oc, d)
        c = _dot(oc, oc) - self.r * self.r
        disc = b * b - 4.0 * a * c
        if disc < 0.0:
            return None
        s = math.sqrt(disc)
        for t in ((-b - s) / (2.0 * a), (-b + s) / (2.0 * a)):   # smallest root first
            if t > T_MIN:
                p = (o[0] + d[0] * t, o[1] + d[1] * t, o[2] + d[2] * t)
                n = _norm(_sub(p, self.c))
                if _dot(n, d) > 0.0:                               # seen from inside: the surface faces the ray
                    n = (-n[0], -n[1], -n[2])
                return t, n
        return None


class Capsule:
    """Segment a-b swept by `radius` (Inigo Quilez's capsule test: body, then the nearer end cap)."""

    def __init__(self, a, b, radius, bump=0):
        if radius <= 0:
            raise ValueError("Capsule radius must be positive")
        self.a, self.b = tuple(map(float, a)), tuple(map(float, b))
        self.r, self.bump = float(radius), int(bump)
        self.caps = (Sphere(self.a, self.r), Sphere(self.b, self.r))

    def hit(self, o, d):
        ba = _sub(self.b, self.a)
        oa = _sub(o, self.a)
        baba, bard, baoa = _dot(ba, ba), _dot(ba, d), _dot(ba, oa)
        rdoa, oaoa, dd = _dot(d, oa), _dot(oa, oa), _dot(d, d)
        best = None
        if baba > 0.0:
            a = baba * dd - bard * bard
            b = baba * rdoa - baoa * bard                          # NOT doubled: the quadratic is a t^2 + 2 b t + c
            c = baba * oaoa - baoa * baoa - self.r * self.r * baba
            h = b * b - a * c
            if a != 0.0 and h >= 0.0:
                for t in ((-b - math.sqrt(h)) / a, (-b + math.sqrt(h)) / a):
                    y = baoa + t * bard
                    if t > T_MIN and 0.0 < y < baba:                # the axial coordinate lies on the segment
                        p = (o[0] + d[0] * t, o[1] + d[1] * t, o[2] + d[2] * t)
                        k = y / baba
                        q = (self.a[0] + ba[0] * k, self.a[1] + ba[1] * k, self.a[2] + ba[2] * k)
                        n = _norm(_sub(p, q))
                        if _dot(n, d) > 0.0:
                            n = (-n[0], -n[1], -n[2])
                        best = (t, n)
                        break
        for cap in self.caps:
            h2 = cap.hit(o, d)
            if h2 and (best is None or h2[0] < best[0]):
                best = h2
        return best


class Box:
    """Box of half-extents `half` about `centre`, its local axes given by `axes` (three unit vectors; default: world
    axes).  Slab test; a ray that starts inside the box misses it."""

    def __init__(self, centre, half, axes=None, bump=0):
        if min(half) <= 0:
            raise ValueError("Box half-extents must be positive")
        self.c, self.h, self.bump = tuple(map(float, centre)), tuple(map(float, half)), int(bump)
        self.ax = tuple(_norm(v) for v in (axes or ((1, 0, 0), (0, 1, 0), (0, 0, 1))))

    @classmethod
    def span(cls, lo, hi, bump=0):
        """Axis-aligned box from corner lo to corner hi."""
        return cls(tuple((a + b) / 2.0 for a, b in zip(lo, hi)), tuple(abs(b - a) / 2.0 for a, b in zip(lo, hi)), bump=bump)

    @classmethod
    def plate(cls, centre, normal, radius, thick, bump=0):
        """A flat square slab (a disc, a wing): `normal` is its thin axis, `radius` its half-width, `thick` half-depth."""
        n = _norm(normal)
        u = _cross(n, (0.0, 0.0, 1.0)) if abs(n[2]) < 0.9 else _cross(n, (1.0, 0.0, 0.0))
        u = _norm(u)
        w = _cross(n, u)
        return cls(centre, (radius, thick, radius), axes=(u, n, w), bump=bump)

    def hit(self, o, d):
        oc = _sub(o, self.c)
        tn, tf, nn = -1e30, 1e30, None
        for ax, half in zip(self.ax, self.h):
            oo, dd = _dot(oc, ax), _dot(d, ax)
            if abs(dd) < 1e-12:
                if abs(oo) > half:
                    return None
                continue
            t1, t2 = (-half - oo) / dd, (half - oo) / dd
            sign = -1.0
            if t1 > t2:
                t1, t2, sign = t2, t1, 1.0
            if t1 > tn:
                tn, nn = t1, (ax[0] * sign, ax[1] * sign, ax[2] * sign)
            tf = min(tf, t2)
            if tn > tf:
                return None
        if nn is None or tn <= T_MIN:                              # behind the ray, or the ray starts inside
            return None
        return tn, nn


# ---- the statues ---------------------------------------------------------------------------------------------------
def _scaled(parts, k):
    """The same statue at k times the size (coordinates and radii); used to fit a silhouette without touching the camera."""
    out = []
    for p in parts:
        if isinstance(p, Sphere):
            out.append(Sphere(tuple(v * k for v in p.c), p.r * k, p.bump))
        elif isinstance(p, Capsule):
            out.append(Capsule(tuple(v * k for v in p.a), tuple(v * k for v in p.b), p.r * k, p.bump))
        else:
            out.append(Box(tuple(v * k for v in p.c), tuple(v * k for v in p.h), p.ax, p.bump))
    return out


def _discobolus():
    """Myron's discus thrower: hips square to the camera, chest twisted, throwing arm swung back and up with the disc
    (a thin slab, its face tilted to the back so it catches the light as the turn brings it round)."""
    C, S = Capsule, Sphere
    return [
        Box.span((-0.75, -2.45, -0.6), (0.75, -2.2, 0.6)),        # plinth
        C((-0.14, -2.15, 0.35), (-0.18, -1.05, 0.2), 0.16),        # left shin, forward
        C((-0.18, -1.05, 0.2), (-0.16, 0.05, 0.0), 0.2),           # left thigh
        C((0.16, -2.15, -0.35), (0.2, -1.05, -0.2), 0.15),         # right shin, trailing
        C((0.2, -1.05, -0.2), (0.16, 0.05, 0.0), 0.19),            # right thigh
        C((-0.2, 0.05, 0.0), (0.2, 0.05, 0.0), 0.24),              # hips, square to us
        C((0.0, 0.1, 0.0), (0.08, 0.95, -0.05), 0.3),              # torso, twisting
        C((-0.32, 1.02, 0.08), (0.42, 1.08, -0.18), 0.15),         # shoulders, turned
        C((0.14, 1.2, 0.0), (0.16, 1.38, 0.05), 0.11),             # neck
        S((0.2, 1.58, 0.12), 0.24),                                # head, looking back over the disc arm
        C((0.42, 1.08, -0.18), (0.52, 1.2, -0.55), 0.09),          # throwing arm, swung back at shoulder height
        C((0.52, 1.2, -0.55), (0.58, 1.28, -0.82), 0.08),
        Box.plate((0.6, 1.3, -1.02), (0.0, 0.7, -0.72), 0.3, 0.04, bump=1),     # the disc
        C((-0.32, 1.02, 0.08), (-0.22, 0.45, 0.4), 0.09),          # free arm across the body
        C((-0.22, 0.45, 0.4), (0.05, 0.05, 0.42), 0.08),
    ]


def _venus():
    """Venus de Milo: contrapposto, drapery wider than the chest, head turned to -X, both arms broken at the shoulder."""
    C, S = Capsule, Sphere
    return [
        Box.span((-0.8, -2.45, -0.55), (0.8, -2.2, 0.55)),          # plinth
        C((-0.45, 0.25, 0.0), (-0.62, -2.15, 0.05), 0.32),          # drapery, left fall
        C((0.42, 0.3, 0.0), (0.58, -2.15, -0.05), 0.32),            # drapery, right fall
        C((0.0, 0.2, 0.12), (0.05, -2.1, 0.18), 0.42),              # drapery, front mass
        C((-0.36, 0.34, 0.0), (0.38, 0.46, 0.0), 0.3),              # hips, tilted (contrapposto)
        C((0.02, 0.5, 0.0), (-0.04, 1.3, 0.0), 0.3),                # torso
        C((-0.36, 1.32, 0.0), (0.36, 1.38, 0.0), 0.16),             # shoulders
        S((-0.46, 1.28, 0.0), 0.15),                                # stump of the left arm
        S((0.46, 1.33, 0.0), 0.15),                                 # stump of the right arm
        C((-0.02, 1.45, 0.0), (-0.07, 1.7, 0.02), 0.12),            # neck
        S((-0.12, 1.95, 0.04), 0.25),                               # head, turned to -X
        S((-0.1, 2.12, -0.12), 0.15),                               # the knot of hair
    ]


def _victory():
    """Winged Victory of Samothrace: no head (a neck stump), two wings raised behind with a gap on the centreline,
    drapery blown back, standing on the prow of a ship."""
    C = Capsule
    return [
        Box.span((-0.95, -2.45, -0.9), (0.95, -1.95, 0.75)),        # the prow
        Box.span((-0.35, -1.95, 0.35), (0.35, -1.75, 0.85)),         # the prow's beak
        C((0.0, -1.8, 0.1), (0.0, 0.35, 0.05), 0.42),               # skirt
        C((-0.3, 0.1, -0.15), (-0.4, -1.7, -0.7), 0.24),            # drapery blown to -Z
        C((0.3, 0.1, -0.15), (0.42, -1.7, -0.75), 0.24),
        C((0.0, 0.35, 0.0), (0.0, 1.25, 0.0), 0.33),                # torso
        C((-0.34, 1.25, 0.0), (0.34, 1.25, 0.0), 0.15),             # shoulders
        C((0.0, 1.35, 0.0), (0.0, 1.5, 0.0), 0.13),                 # the neck stump
        Box((-0.72, 1.85, -0.45), (0.36, 0.75, 0.07), axes=((0.83, 0.56, 0.0), (-0.56, 0.83, 0.0), (0.0, 0.0, 1.0))),
        Box((0.72, 1.85, -0.45), (0.36, 0.75, 0.07), axes=((0.83, -0.56, 0.0), (0.56, 0.83, 0.0), (0.0, 0.0, 1.0))),
    ]


def _laocoon():
    """Laocoon and his sons: three bodies, the priest in the middle and tallest, two serpents (thicker than any arm)
    looped across all three."""
    C, S = Capsule, Sphere
    parts = [Box.span((-1.75, -2.45, -0.55), (1.75, -2.15, 0.55))]            # the altar plinth
    for x, top, s in ((-1.2, 0.55, 0.78), (0.0, 1.45, 1.0), (1.2, 0.35, 0.74)):  # sons, priest, son
        base = -2.15
        hip = base + (top - base) * 0.45
        chest = base + (top - base) * 0.78
        parts += [
            C((x - 0.12 * s, base, 0.05), (x - 0.1 * s, hip, 0.0), 0.13 * s),    # legs
            C((x + 0.12 * s, base, -0.05), (x + 0.1 * s, hip, 0.0), 0.13 * s),
            C((x, hip, 0.0), (x, chest, 0.0), 0.24 * s),                          # body
            S((x + 0.05 * s, top, 0.02), 0.2 * s),                                # head
            C((x - 0.28 * s, chest, 0.0), (x - 0.5 * s, top + 0.1, 0.1), 0.07),   # arms thrown up
            C((x + 0.28 * s, chest, 0.0), (x + 0.5 * s, chest - 0.35, 0.15), 0.07),
        ]
    snake_a = [(-1.65, -1.6, 0.3), (-1.2, -0.9, 0.35), (-0.6, -0.3, 0.3), (0.0, 0.2, 0.35), (0.55, 0.75, 0.3),
               (0.35, 1.2, 0.2)]
    snake_b = [(1.7, -1.7, 0.25), (1.2, -1.2, 0.35), (0.6, -1.0, 0.3), (0.0, -0.6, 0.35), (-0.6, 0.0, 0.3),
               (-1.2, 0.3, 0.25), (-1.45, 0.75, 0.15)]
    for chain in (snake_a, snake_b):
        for p, q in zip(chain, chain[1:]):
            parts.append(C(p, q, 0.1))
    return parts


class _Oracle:
    """Emblem, not a claimed antique: one stone eye, radius 0.95, looking out along +Z at yaw 0."""
    parts = [Sphere((0.0, 0.0, 0.0), 0.95)]


def _oracle_glyph(p, lam):
    """Pupil '@', iris '#', sclera '%' on the +Z face of the eye (object space point p); else None (plain stone)."""
    c = p[2] / 0.95
    if c > 0.975:
        return TOP
    if c > 0.9:
        return TOP - 2
    if c > 0.76:
        return TOP - 1
    return None


def _full(f, n):
    return 2.0 * math.pi * f / n


def _swing(amp):
    return lambda f, n: amp * math.sin(2.0 * math.pi * f / n)


# key -> (panel name, parts builder, yaw(frame, nframes), scale)
_TABLE = {
    "DISCOBOLUS": ("DISCOBOLUS", _discobolus, _full, 1.0),
    "VENUS": ("VENUS DE MILO", _venus, _swing(0.55), 1.0),
    "VICTORY": ("WINGED VICTORY", _victory, _swing(0.45), 1.0),
    "LAOCOON": ("LAOCOON", _laocoon, _swing(0.35), 1.0),
    "ORACLE": ("ORACLE", lambda: list(_Oracle.parts), _full, 1.0),
}
PLATES = ["DISCOBOLUS", "VENUS", "VICTORY", "LAOCOON", "ORACLE"]
NAMES = [_TABLE[k][0] for k in PLATES]
_PARTS = {}


def _parts(key):
    if key not in _PARTS:
        name, build, yaw, k = _TABLE[key]
        _PARTS[key] = _scaled(build(), k) if k != 1.0 else build()
    return _PARTS[key]


def _bound(parts):
    """A sphere about the origin that holds every part: rays that miss it skip the per-part tests."""
    r = 0.0
    for p in parts:
        if isinstance(p, Sphere):
            r = max(r, math.sqrt(_dot(p.c, p.c)) + p.r)
        elif isinstance(p, Capsule):
            r = max(r, math.sqrt(_dot(p.a, p.a)) + p.r, math.sqrt(_dot(p.b, p.b)) + p.r)
        else:
            r = max(r, math.sqrt(_dot(p.c, p.c)) + math.sqrt(_dot(p.h, p.h)))
    return Sphere((0.0, 0.0, 0.0), r + 1e-6)


def render(key, frame, nframes=FRAMES):
    """Frame `frame` (taken modulo nframes) of plate `key` as H lines of W characters from RAMP.
    KeyError for an unknown key; ValueError for nframes < 1 or a non-integer frame."""
    if key not in _TABLE:
        raise KeyError(key)
    if not isinstance(nframes, int) or nframes < 1:
        raise ValueError("nframes must be a positive int")
    if isinstance(frame, bool) or not isinstance(frame, int):
        raise ValueError("frame must be an int")
    parts = _parts(key)
    bound = _bound(parts)
    a = _TABLE[key][2](frame % nframes, nframes)
    ca, sa = math.cos(a), math.sin(a)
    # world -> object:  x' = x cos a - z sin a,  z' = x sin a + z cos a
    o = (-DIST * sa, 0.0, DIST * ca)
    is_oracle = key == "ORACLE"
    rows = []
    for j in range(H):
        ny = (H / 2.0 - (j + 0.5)) / (H * SY)
        line = []
        for i in range(W):
            nx = ((i + 0.5) - W / 2.0) / (W * SX)
            d = (nx * ca + sa, ny, nx * sa - ca)                     # (nx, ny, -1) rotated into the object
            if bound.hit(o, d) is None and _dot(_sub(o, bound.c), _sub(o, bound.c)) > bound.r * bound.r:
                line.append(" ")
                continue
            best, part = None, None
            for p in parts:
                h = p.hit(o, d)
                if h and (best is None or h[0] < best[0]):
                    best, part = h, p
            if best is None:
                line.append(" ")
                continue
            t, n = best
            nw = (n[0] * ca + n[2] * sa, n[1], -n[0] * sa + n[2] * ca)   # object -> world normal
            lam = _dot(nw, LIGHT)
            if lam <= DARK:
                idx = 1
            else:
                idx = 1 + int(round(lam * (TOP - 1)))
                idx += part.bump
                if is_oracle:
                    lift = max(0.0, lam)
                    if lift ** 8 > 0.35:                              # a glint on the stone (the ORACLE only)
                        idx += 2
            if is_oracle:
                p = (o[0] + d[0] * t, o[1] + d[1] * t, o[2] + d[2] * t)
                g = _oracle_glyph(p, lam)
                if g is not None:
                    idx = g
            line.append(RAMP[max(1, min(TOP, idx))])
        rows.append("".join(line))
    return "\n".join(rows)


if __name__ == "__main__":                                           # preview: python oracle_ascii.py [KEY] [FRAME]
    import sys
    keys = sys.argv[1:2] or PLATES
    fr = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    for k in keys:
        print(k)
        print(render(k, fr))
