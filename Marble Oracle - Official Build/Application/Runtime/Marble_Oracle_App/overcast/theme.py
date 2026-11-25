"""OVERCAST visual system: Apple-inspired rounded, flat, quiet.

Everything visual lives here: palettes (dark / light), accent colours, fonts,
and anti-aliased rounded artwork for ttk image elements (nine-slice
stretching via ``-border``), the technique used by well-known modern ttk
themes. Artwork is rendered in pure Python (no Pillow at runtime) and
pre-blended onto each surface colour it sits on, so it looks identical on
every platform and Tk version (no reliance on alpha compositing).

Robustness: ``install()`` never raises. Each component is installed inside a
guard; if Tk rejects anything, that component falls back to flat colours and
the failure is recorded in ``Theme.warnings``. The app always starts.
"""
from __future__ import annotations

from functools import lru_cache

try:   # Artwork and palettes are pure Python and must import without Tk (tests, CLI).
    import tkinter as tk
    from tkinter import ttk, font as tkfont
except ImportError:  # pragma: no cover - exercised only where Tk is absent
    tk = ttk = tkfont = None

# ── Tokens ────────────────────────────────────────────────────────────────
PALETTES = {
    'dark': {'bg': '#1C1C1E', 'side': '#161618', 'card': '#2C2C2E', 'field': '#3A3A3C',
             'field_hover': '#48484A', 'line': '#38383A', 'ink': '#F5F5F7', 'dim': '#98989D',
             'faint': '#636366', 'red': '#FF453A', 'green': '#30D158', 'knob': '#FFFFFF',
             'track_off': '#48484A', 'shadow': '#0E0E10'},
    'light': {'bg': '#F2F2F7', 'side': '#EBEBF0', 'card': '#FFFFFF', 'field': '#E0E0E6',
              'field_hover': '#D4D4DB', 'line': '#D1D1D6', 'ink': '#1D1D1F', 'dim': '#606065',
              'faint': '#AEAEB2', 'red': '#E0352B', 'green': '#248A3D', 'knob': '#FFFFFF',
              'track_off': '#D1D1D6', 'shadow': '#D8D8DE'},
}
# accent, hover, text-on-accent for (dark, light)
ACCENTS = {
    'Amber': (('#FF9F0A', '#FFB340', '#1C1C1E'), ('#F08C00', '#FF9F0A', '#1D1D1F')),
    'Blue': (('#0A84FF', '#409CFF', '#FFFFFF'), ('#007AFF', '#3395FF', '#FFFFFF')),
    'Green': (('#30D158', '#5DE07C', '#1C1C1E'), ('#248A3D', '#2FA84D', '#FFFFFF')),
    'Graphite': (('#AEAEB2', '#C7C7CC', '#1C1C1E'), ('#6E6E73', '#8E8E93', '#FFFFFF')),
}
APPEARANCES = tuple(PALETTES)
# 1.1.3: looks a host can ask for but OVERCAST's own settings do not offer. 'classic' is Marble Oracle's
# Ember (warm browns and the orange accent), so OVERCAST inside the suite's Classic look matches it.
HOST_PALETTES = {
    'classic': {'bg': '#1D1714', 'side': '#130F0D', 'card': '#261F1B', 'field': '#2F2620',
                'field_hover': '#372A23', 'line': '#3A2E27', 'ink': '#F2E8DE', 'dim': '#B9A99B',
                'faint': '#85705F', 'red': '#FF6B57', 'green': '#7BD88F', 'knob': '#FFF4E6',
                'track_off': '#493B32', 'shadow': '#0E0A08'},
}
HOST_ACCENTS = {'classic': ('#FB8E22', '#FFA04A', '#2B1405')}
DEFAULT_APPEARANCE = 'dark'
DEFAULT_ACCENT = 'Amber'
FONT_PREFERENCE = ('SF Pro Text', 'SF Pro Display', 'Inter', 'Inter Variable', 'Adwaita Sans',
                   'Segoe UI Variable Text', 'Segoe UI', 'Cantarell', 'Noto Sans', 'Ubuntu',
                   'Helvetica Neue', 'Uberata Clear', 'DejaVu Sans')
MONO_PREFERENCE = ('SF Mono', 'JetBrains Mono', 'Cascadia Mono', 'Consolas', 'Noto Sans Mono',
                   'DejaVu Sans Mono')
SURFACES = ('bg', 'card', 'side')
_KEPT_IMAGES = []


def hex_rgb(c):
    c = c.lstrip('#')
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def rgb_hex(rgb):
    return '#%02X%02X%02X' % tuple(max(0, min(255, round(v))) for v in rgb)


def mix(a, b, t):
    """t of colour a over (1 - t) of colour b."""
    ra, rb = hex_rgb(a), hex_rgb(b)
    return rgb_hex(tuple(x * t + y * (1 - t) for x, y in zip(ra, rb)))


def luminance(colour):
    def chan(c):
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = hex_rgb(colour)
    return 0.2126 * chan(r) + 0.7152 * chan(g) + 0.0722 * chan(b)


def contrast(a, b):
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def readable(colour, backgrounds, minimum=4.5):
    """Darken (light UI) or lighten (dark UI) a colour until it reads as text (WCAG AA)."""
    darker = luminance(backgrounds[0]) > 0.5
    target = '#000000' if darker else '#FFFFFF'
    for step in range(0, 101, 4):
        candidate = mix(target, colour, step / 100)
        if all(contrast(candidate, bg) >= minimum for bg in backgrounds):
            return candidate
    return target


def palette(appearance=DEFAULT_APPEARANCE, accent=DEFAULT_ACCENT):
    appearance = appearance if appearance in PALETTES or appearance in HOST_PALETTES else DEFAULT_APPEARANCE
    accent = accent if accent in ACCENTS else DEFAULT_ACCENT
    if appearance in HOST_PALETTES:
        p = dict(HOST_PALETTES[appearance])
        a, hover, on = HOST_ACCENTS[appearance]
    else:
        p = dict(PALETTES[appearance])
        a, hover, on = ACCENTS[accent][0 if appearance == 'dark' else 1]
    select = mix(a, p['card'], 0.32)
    # Text colours must read (WCAG AA, 4.5:1) on every surface they are drawn on: the page, cards, the
    # sidebar and fields. The stock dim, green and red fell short on fields (and in Light on every
    # surface), so they are nudged just far enough, keeping their hue (1.1.3). Selected rows carry ink.
    surfaces = (p['bg'], p['card'], p['side'], p['field'])
    for name in ('dim', 'green', 'red'):
        p[name] = readable(p[name], surfaces)
    # Text on an accent button: the stock pairing where it reads, otherwise whichever of white and near
    # black reads best (Blue in Dark was 3.6:1).
    on = max((on, '#FFFFFF', '#1C1C1E'), key=lambda c: (contrast(c, a) >= 4.5 and c == on, contrast(c, a)))
    p.update({'accent': a, 'accent_hover': hover, 'on_accent': on,
              'select': select, 'select_side': mix(a, p['side'], 0.22),
              'accent_text': readable(a, surfaces),
              'appearance': appearance, 'accent_name': accent})
    return p


# ── Pure-Python anti-aliased artwork ──────────────────────────────────────
def _in_rrect(px, py, x0, y0, x1, y1, r):
    if px < x0 or px > x1 or py < y0 or py > y1:
        return False
    dx = max(x0 + r - px, 0.0, px - (x1 - r))
    dy = max(y0 + r - py, 0.0, py - (y1 - r))
    return dx * dx + dy * dy <= r * r


def _in_circle(px, py, cx, cy, rad):
    return (px - cx) ** 2 + (py - cy) ** 2 <= rad * rad


def _in_triangle(px, py, ax, ay, bx, by, cx, cy):
    def side(x0, y0, x1, y1):
        return (px - x1) * (y0 - y1) - (x0 - x1) * (py - y1)
    d1, d2, d3 = side(ax, ay, bx, by), side(bx, by, cx, cy), side(cx, cy, ax, ay)
    return not ((d1 < 0 or d2 < 0 or d3 < 0) and (d1 > 0 or d2 > 0 or d3 > 0))


def _inside(shape, px, py):
    if shape[0] == 'rrect':
        return _in_rrect(px, py, *shape[1:6])
    if shape[0] == 'tri':
        return _in_triangle(px, py, *shape[1:7])
    return _in_circle(px, py, *shape[1:4])


def render(width, height, shapes, background, ss=4):
    """Rasterise shapes (painted in order, last on top) over a solid background.

    shapes: ('rrect', x0, y0, x1, y1, radius, colour) or ('circle', cx, cy, r, colour),
    in pixel coordinates (edges, not centres). Returns rows of '#RRGGBB'.
    Pixels on a shape boundary average ss*ss sub-samples (anti-aliasing,
    pre-blended); pixels a 3x3 probe finds fully inside or outside every shape
    are filled directly (shapes are convex), which is ~10x faster.
    """
    bg = hex_rgb(background)
    cols = [(s, hex_rgb(s[-1])) for s in shapes]
    probes = (0.02, 0.5, 0.98)
    step = 1.0 / ss
    rows = []
    for y in range(height):
        row = []
        for x in range(width):
            solid = None
            for shape, rgb in reversed(cols):           # topmost shape first
                hits = sum(_inside(shape, x + a, y + b) for a in probes for b in probes)
                if hits == 9:
                    solid = rgb
                    break
                if hits:
                    solid = False                        # partial coverage: supersample
                    break
            if solid is None:
                row.append(rgb_hex(bg)); continue
            if solid is not False:
                row.append(rgb_hex(solid)); continue
            acc = [0.0, 0.0, 0.0]
            for j in range(ss):
                py = y + (j + 0.5) * step
                for i in range(ss):
                    px = x + (i + 0.5) * step
                    colour = bg
                    for shape, rgb in cols:
                        if _inside(shape, px, py):
                            colour = rgb
                    acc[0] += colour[0]; acc[1] += colour[1]; acc[2] += colour[2]
            n = ss * ss
            row.append(rgb_hex((acc[0] / n, acc[1] / n, acc[2] / n)))
        rows.append(row)
    return rows


@lru_cache(maxsize=512)
def rounded_tile(radius, fill, background, outline=None, size=None):
    """Square nine-slice tile: corners of `radius`, 1 px optional outline."""
    size = size or 2 * radius + 4
    shapes = []
    if outline:
        shapes.append(('rrect', 0, 0, size, size, radius, outline))
        shapes.append(('rrect', 1, 1, size - 1, size - 1, max(radius - 1, 0), fill))
    else:
        shapes.append(('rrect', 0, 0, size, size, radius, fill))
    return tuple(tuple(row) for row in render(size, size, shapes, background))


@lru_cache(maxsize=64)
def pill(width, height, fill, background, outline=None):
    r = height / 2
    shapes = [('rrect', 0, 0, width, height, r, outline or fill)]
    if outline:
        shapes.append(('rrect', 1, 1, width - 1, height - 1, r - 1, fill))
    return tuple(tuple(row) for row in render(width, height, shapes, background))


@lru_cache(maxsize=32)
def chevron(colour, background, width=18, height=16):
    """A small downward triangle centred in a box of the field colour (the dropdown arrow)."""
    cx, cy = width / 2 - 2, height / 2
    return tuple(tuple(row) for row in render(width, height, [('tri', cx - 4.5, cy - 2.5, cx + 4.5, cy - 2.5, cx, cy + 3, colour)],
                                              background))


def switch(on, p, background, width=40, height=24):
    return _switch(on, p['accent'] if on else p['track_off'], p['knob'], background, width, height)


@lru_cache(maxsize=32)
def _switch(on, track, knob, background, width, height):
    r = height / 2
    knob_x = width - r if on else r
    return tuple(tuple(row) for row in render(width, height, [('rrect', 0, 0, width, height, r, track),
                                                            ('circle', knob_x, r, r - 2.5, knob)], background))


def to_photo_data(rows):
    return ' '.join('{' + ' '.join(row) + '}' for row in rows)


# ── Fonts ─────────────────────────────────────────────────────────────────
def choose_font(widget, preference=FONT_PREFERENCE, fallback='TkDefaultFont'):
    try:
        families = set(tkfont.families(widget))
    except tk.TclError:
        return fallback
    for name in preference:
        if name in families:
            return name
    return fallback


class Theme:
    """Resolved palette, fonts and style names for one panel."""

    def __init__(self, appearance=DEFAULT_APPEARANCE, accent=DEFAULT_ACCENT, family=None):
        self.p = palette(appearance, accent)
        self.host_family = family          # 1.1.2: a host's interface face, used instead of choosing one
        self.appearance = self.p['appearance']
        self.accent = self.p['accent_name']
        self.family = 'TkDefaultFont'
        self.mono = 'TkFixedFont'
        self.images = {}
        self.warnings = []
        self.installed = set()

    # Fonts: Apple-like hierarchy.
    def f(self, size=11, weight='normal'):
        return (self.family, size, weight)

    @property
    def fonts(self):
        return {'title': self.f(22, 'bold'), 'headline': self.f(13, 'bold'), 'body': self.f(11),
                'callout': self.f(10), 'caption': self.f(9), 'section': self.f(9, 'bold'),
                'big': self.f(30, 'bold'), 'button': self.f(10, 'bold')}

    def surface_colour(self, surface):
        return self.p[{'bg': 'bg', 'card': 'card', 'side': 'side'}.get(surface, 'bg')]

    # Style name helpers (falls back gracefully if a variant was not installed).
    def button(self, kind='secondary', surface='bg'):
        return f'O.{kind}.{surface}.TButton'

    def entry(self, surface='bg'):
        return f'O.{surface}.TEntry'

    def combo(self, surface='bg'):
        return f'O.{surface}.TCombobox'

    def chip(self, surface='bg'):
        return f'O.chip.{surface}.TRadiobutton'

    # ── install ──
    def install(self, widget, *, standalone=False):
        root = widget.winfo_toplevel()
        self.family = choose_font(widget, (self.host_family,) + FONT_PREFERENCE) if self.host_family else choose_font(widget)
        self.mono = choose_font(widget, MONO_PREFERENCE, 'TkFixedFont')
        style = ttk.Style(widget)
        if standalone:
            self._guard('base-theme', lambda: style.theme_use('clam'))
            self._guard('option-db', lambda: self._options(root))
        self._guard('frames', lambda: self._frames(style))
        self._guard('fallback-colours', lambda: self._flat(style))
        for name, fn in (('buttons', self._buttons), ('fields', self._fields), ('chips', self._chips),
                         ('nav', self._nav), ('switch', self._switch), ('scrollbar', self._scrollbar),
                         ('cards', self._cards), ('menubutton', self._menubutton)):
            self._guard(name, lambda fn=fn: fn(style, root))
        self._guard('treeview', lambda: self._treeview(style))
        return self

    def _guard(self, name, fn):
        try:
            fn()
            self.installed.add(name)
        except (tk.TclError, TypeError, ValueError, AttributeError) as exc:
            self.warnings.append(f'{name}: {exc}')

    def _image(self, root, key, rows):
        if key not in self.images:
            img = tk.PhotoImage(master=root, width=len(rows[0]), height=len(rows))
            img.put(to_photo_data(rows), to=(0, 0))
            self.images[key] = img
            # Kept for the life of the process: if a destroyed panel's images were freed by garbage collection
            # running on a worker thread, Tk would refuse ("main thread is not in main loop").
            _KEPT_IMAGES.append(img)
        return self.images[key]

    def _element(self, style, name, *args, **kw):
        if name not in style.element_names():
            style.element_create(name, 'image', *args, **kw)

    def _options(self, root):
        p = self.p
        for pattern, value in (('*TCombobox*Listbox.background', p['card']),
                               ('*TCombobox*Listbox.foreground', p['ink']),
                               ('*TCombobox*Listbox.selectBackground', p['select']),
                               ('*TCombobox*Listbox.selectForeground', p['ink']),
                               ('*TCombobox*Listbox.font', self.f(11)),
                               ('*Menu.background', p['card']), ('*Menu.foreground', p['ink']),
                               ('*Menu.activeBackground', p['select']),
                               ('*Menu.activeForeground', p['ink']), ('*Menu.relief', 'flat'),
                               ('*Menu.font', self.f(11))):
            root.option_add(pattern, value)

    def _flat(self, style):
        """Colours that also make the plain (fallback) widgets look right."""
        p = self.p
        for surface in SURFACES:
            bg = self.surface_colour(surface)
            for kind in ('accent', 'secondary', 'plain', 'danger'):
                name = self.button(kind, surface)
                fg = p['on_accent'] if kind == 'accent' else (p['red'] if kind == 'danger' else
                                                             (p['accent_text'] if kind == 'plain' else p['ink']))
                fill = p['accent'] if kind == 'accent' else (bg if kind == 'plain' else p['field'])
                style.configure(name, background=fill, foreground=fg, font=self.fonts['button'],
                                padding=(14, 6), borderwidth=0, relief='flat', focuscolor=fill,
                                lightcolor=fill, darkcolor=fill, bordercolor=fill, anchor='center')
                style.map(name, foreground=[('disabled', p['faint'])],
                          background=[('pressed', p['field_hover']), ('active', p['field_hover'] if kind != 'accent' else p['accent_hover'])])
            for name in (self.entry(surface), self.combo(surface)):
                style.configure(name, fieldbackground=p['field'], foreground=p['ink'], background=bg,
                                insertcolor=p['ink'], bordercolor=p['field'], lightcolor=p['field'],
                                darkcolor=p['field'], arrowcolor=p['dim'], padding=(9, 5),
                                selectbackground=p['select'], selectforeground=p['ink'])
                style.map(name, fieldbackground=[('readonly', p['field'])], foreground=[('readonly', p['ink'])],
                          selectbackground=[('readonly', p['field'])], selectforeground=[('readonly', p['ink'])])
            style.configure(self.chip(surface), background=bg, foreground=p['dim'], font=self.f(10, 'bold'),
                            padding=(12, 4), indicatorrelief='flat', focuscolor=bg)
            style.map(self.chip(surface), foreground=[('selected', p['ink']), ('active', p['ink'])],
                      background=[('selected', p['field']), ('active', bg)])
        style.configure('O.nav.TRadiobutton', background=p['side'], foreground=p['ink'], font=self.f(11),
                        padding=(8, 3), anchor='w', focuscolor=p['side'])
        style.map('O.nav.TRadiobutton', background=[('selected', p['select_side']), ('active', p['side'])],
                  foreground=[('selected', p['ink'])])
        style.configure('O.switch.TCheckbutton', background=p['card'], foreground=p['ink'], font=self.f(11),
                        focuscolor=p['card'], indicatorbackground=p['field'], indicatorforeground=p['accent'])
        style.map('O.switch.TCheckbutton', background=[('active', p['card'])])
        style.configure('O.TMenubutton', background=p['field'], foreground=p['ink'], font=self.fonts['button'],
                        padding=(14, 6), arrowcolor=p['dim'], borderwidth=0, relief='flat')
        style.map('O.TMenubutton', background=[('active', p['field_hover'])])
        for orient in ('Vertical', 'Horizontal'):
            style.configure(f'O.{orient}.TScrollbar', troughcolor=p['card'], background=p['field_hover'],
                            bordercolor=p['card'], lightcolor=p['field_hover'], darkcolor=p['field_hover'],
                            arrowcolor=p['dim'], gripcount=0, width=10)

    def _frames(self, style):
        p = self.p
        style.configure('O.bg.TFrame', background=p['bg'])
        style.configure('O.side.TFrame', background=p['side'])
        style.configure('O.card.TFrame', background=p['card'])

    def _cards(self, style, root):
        p = self.p
        for surface in ('bg', 'side'):
            tile = self._image(root, f'card-{surface}', rounded_tile(14, p['card'], self.surface_colour(surface),
                                                                    outline=mix(p['line'], p['card'], 0.55)))
            self._element(style, f'O.cardbg.{surface}', tile, border=15, sticky='nsew')
            name = f'O.card.{surface}.TFrame'
            style.layout(name, [(f'O.cardbg.{surface}', {'sticky': 'nsew'})])
            style.configure(name, background=p['card'], padding=6)

    def _buttons(self, style, root):
        p = self.p
        for surface in SURFACES:
            bg = self.surface_colour(surface)
            for kind, normal, hover, pressed in (
                    ('accent', p['accent'], p['accent_hover'], mix(p['accent'], p['bg'], 0.8)),
                    ('secondary', p['field'], p['field_hover'], mix(p['field_hover'], p['bg'], 0.7)),
                    ('danger', p['field'], mix(p['red'], p['field'], 0.25), mix(p['red'], p['field'], 0.4)),
                    ('plain', bg, p['field'], p['field_hover'])):
                imgs = [self._image(root, f'btn-{kind}-{surface}-{state}', rounded_tile(7, colour, bg))
                        for state, colour in (('n', normal), ('h', hover), ('p', pressed),
                                              ('d', mix(normal, bg, 0.45)))]
                ring = p['ink'] if kind == 'accent' else p['accent']
                focus = self._image(root, f'btn-{kind}-{surface}-f', rounded_tile(7, normal, bg, outline=ring))
                element = f'O.btnbg.{kind}.{surface}'
                # Keyboard focus stays visible (accent ring), as on macOS.
                self._element(style, element, imgs[0], ('disabled', imgs[3]), ('pressed', imgs[2]),
                              ('active', imgs[1]), ('focus', focus), border=8, sticky='nsew')
                name = self.button(kind, surface)
                style.layout(name, [(element, {'sticky': 'nsew', 'children': [
                    ('Button.padding', {'sticky': 'nsew', 'children': [('Button.label', {'sticky': 'nsew'})]})]})])
                # The 8 px slice border already pads the label; real Tk adds `padding` on top of it.
                style.configure(name, background=bg, padding=(6, 0), width=0)

    def _fields(self, style, root):
        p = self.p
        for surface in SURFACES:
            bg = self.surface_colour(surface)
            normal = self._image(root, f'field-{surface}-n', rounded_tile(8, p['field'], bg))
            focus = self._image(root, f'field-{surface}-f', rounded_tile(8, p['field'], bg, outline=p['accent']))
            hover = self._image(root, f'field-{surface}-h', rounded_tile(8, p['field_hover'], bg))
            element = f'O.fieldbg.{surface}'
            self._element(style, element, normal, ('focus', focus), ('active', hover), border=8, sticky='nsew')
            arrow = f'O.chevron.{surface}'
            self._element(style, arrow, self._image(root, 'chev-n', chevron(p['dim'], p['field'])),
                          ('active', self._image(root, 'chev-h', chevron(p['ink'], p['field_hover']))), sticky='')
            style.layout(self.entry(surface), [(element, {'sticky': 'nsew', 'children': [
                ('Entry.padding', {'sticky': 'nsew', 'children': [('Entry.textarea', {'sticky': 'nsew'})]})]})])
            style.layout(self.combo(surface), [(element, {'sticky': 'nsew', 'children': [
                (arrow, {'side': 'right', 'sticky': ''}),
                ('Combobox.padding', {'sticky': 'nsew', 'children': [('Combobox.textarea', {'sticky': 'nsew'})]})]})])
            style.configure(self.combo(surface), padding=(4, 0, 0, 0))
            style.configure(self.entry(surface), padding=(4, 0))

    def _chips(self, style, root):
        p = self.p
        for surface in SURFACES:
            bg = self.surface_colour(surface)
            off = self._image(root, f'chip-{surface}-off', rounded_tile(7, bg, bg))
            hov = self._image(root, f'chip-{surface}-hov', rounded_tile(7, mix(p['field'], bg, 0.5), bg))
            on = self._image(root, f'chip-{surface}-on', rounded_tile(7, p['field_hover'], bg))
            element = f'O.chipbg.{surface}'
            self._element(style, element, off, ('selected', on), ('active', hov), border=7, sticky='nsew')
            style.layout(self.chip(surface), [(element, {'sticky': 'nsew', 'children': [
                ('Radiobutton.padding', {'sticky': 'nsew', 'children': [('Radiobutton.label', {'sticky': 'nsew'})]})]})])
            style.configure(self.chip(surface), anchor='center', padding=(6, 0))

    def _nav(self, style, root):
        p = self.p
        off = self._image(root, 'nav-off', rounded_tile(6, p['side'], p['side']))
        hov = self._image(root, 'nav-hov', rounded_tile(6, mix(p['field'], p['side'], 0.45), p['side']))
        on = self._image(root, 'nav-on', rounded_tile(6, p['select_side'], p['side']))
        self._element(style, 'O.navbg', off, ('selected', on), ('active', hov), border=6, sticky='nsew')
        style.layout('O.nav.TRadiobutton', [('O.navbg', {'sticky': 'nsew', 'children': [
            ('Radiobutton.padding', {'sticky': 'nsew', 'children': [('Radiobutton.label', {'sticky': 'nsew'})]})]})])

    def _switch(self, style, root):
        p = self.p
        off = self._image(root, 'switch-off', switch(False, p, p['card']))
        on = self._image(root, 'switch-on', switch(True, p, p['card']))
        dis = self._image(root, 'switch-dis', render(40, 24, [('rrect', 0, 0, 40, 24, 12, mix(p['track_off'], p['card'], 0.5))],
                                                     p['card']))
        self._element(style, 'O.switch.indicator', off, ('disabled', dis), ('selected', on), sticky='')
        style.layout('O.switch.TCheckbutton', [('O.switch.indicator', {'side': 'left', 'sticky': ''}),
                                               ('Checkbutton.padding', {'sticky': 'nsew', 'children': [
                                                   ('Checkbutton.label', {'sticky': 'nsew'})]})])
        style.configure('O.switch.TCheckbutton', padding=(10, 2))

    def _scrollbar(self, style, root):
        p = self.p
        trough = self._image(root, 'sb-trough', render(10, 10, [], p['card']))
        thumb = self._image(root, 'sb-thumb', render(10, 24, [('rrect', 2, 2, 8, 22, 3, p['field_hover'])], p['card']))
        thumb_h = self._image(root, 'sb-thumb-h', render(10, 24, [('rrect', 2, 2, 8, 22, 3, p['faint'])], p['card']))
        thumb_x = self._image(root, 'sb-thumb-x', render(24, 10, [('rrect', 2, 2, 22, 8, 3, p['field_hover'])], p['card']))
        thumb_xh = self._image(root, 'sb-thumb-xh', render(24, 10, [('rrect', 2, 2, 22, 8, 3, p['faint'])], p['card']))
        self._element(style, 'O.sb.trough', trough, border=2, sticky='nsew')
        self._element(style, 'O.sb.vthumb', thumb, ('active', thumb_h), ('pressed', thumb_h), border=(2, 6), sticky='nsew')
        self._element(style, 'O.sb.hthumb', thumb_x, ('active', thumb_xh), ('pressed', thumb_xh), border=(6, 2), sticky='nsew')
        style.layout('O.Vertical.TScrollbar', [('O.sb.trough', {'sticky': 'ns', 'children': [
            ('O.sb.vthumb', {'expand': '1', 'sticky': 'nsew'})]})])
        style.layout('O.Horizontal.TScrollbar', [('O.sb.trough', {'sticky': 'ew', 'children': [
            ('O.sb.hthumb', {'expand': '1', 'sticky': 'nsew'})]})])

    def _menubutton(self, style, root):
        p = self.p
        element = 'O.btnbg.secondary.bg'   # created by _buttons
        if element not in style.element_names():
            raise tk.TclError('button artwork unavailable')
        style.layout('O.TMenubutton', [(element, {'sticky': 'nsew', 'children': [
            ('Menubutton.padding', {'sticky': 'nsew', 'children': [('Menubutton.label', {'sticky': 'nsew'})]})]})])
        style.configure('O.TMenubutton', background=p['bg'], anchor='center', padding=(6, 0), width=0)

    def _treeview(self, style):
        p = self.p
        style.configure('O.Treeview', background=p['card'], fieldbackground=p['card'], foreground=p['ink'],
                        rowheight=30, borderwidth=0, relief='flat', font=self.f(11),
                        lightcolor=p['card'], darkcolor=p['card'], bordercolor=p['card'])
        style.map('O.Treeview', background=[('selected', p['select'])], foreground=[('selected', p['ink'])])
        style.configure('O.Treeview.Heading', background=p['card'], foreground=p['dim'], font=self.f(9, 'bold'),
                        relief='flat', borderwidth=0, padding=(8, 6), lightcolor=p['card'], darkcolor=p['card'],
                        bordercolor=p['card'])
        style.map('O.Treeview.Heading', background=[('active', p['field'])], foreground=[('active', p['ink'])])
        # Keep the field (it paints the empty area) but with no visible border.
        style.layout('O.Treeview', [('Treeview.field', {'sticky': 'nsew', 'border': '0', 'children': [
            ('Treeview.padding', {'sticky': 'nsew', 'children': [('Treeview.treearea', {'sticky': 'nsew'})]})]})])
