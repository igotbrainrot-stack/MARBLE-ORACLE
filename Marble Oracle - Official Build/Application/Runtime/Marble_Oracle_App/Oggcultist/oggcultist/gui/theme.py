"""Oggcultist's warm dark film-grain theme (ttk 'clam' base + generated image elements).

Tk can only paint solid colours, so every textured surface is a ttk *image
element*: a grained tile (see textures.py) that ttk tiles across the widget.
Frames, labels, check buttons, buttons, navigation items and status chips use
these layouts. Treeview rows and text fields remain solid (a Tk limitation) and
use the deep ``table`` colour so they read as inset panels.
"""
from __future__ import annotations

import sys
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

from . import design_system as ds

C = ds.COLOR
# 1.9 palette names, now read from the Ember colour roles in design_system.
PALETTE = {
    'bg': C['canvas'], 'surface': C['raised'], 'table': C['sunken'], 'row_alt': C['sunken_alt'],
    'sidebar': C['sidebar'], 'sidebar_fg': C['sidebar_text'], 'sidebar_muted': C['sidebar_icon'],
    'sidebar_active': C['nav_current'], 'accent': C['accent'], 'accent_dark': C['accent_deep'],
    'accent_soft': C['accent_soft'], 'text': C['text'], 'muted': C['text_2'], 'faint': C['text_3'],
    'border': C['line_strong'], 'line': C['line'], 'hover': C['hover'], 'button': C['control'],
    'button_border': C['control_line'], 'on_accent': C['text_on_accent'],
    'ready': C['ready'], 'done': C['done'], 'review': C['review'], 'skipped': C['skipped'], 'failed': C['failed'],
}

BUTTON_BORDER = '#000000'      # every boxed button has a black border; focus uses the accent
RADIUS = ds.RADIUS['s'] - 2    # image corner radius (the bevel adds about 2 px of visual rounding)
BEVEL = ds.BEVEL['raised']
BEVEL_SOFT = ds.BEVEL['soft']
BEVEL_SUNKEN = ds.BEVEL['sunken']

GRADIENT = ds.ACCENT_GRADIENT
GRADIENT_HOVER = ds.ACCENT_GRADIENT_HOVER
GRADIENT_PRESSED = ds.ACCENT_GRADIENT_PRESSED
GRADIENT_DISABLED = ds.ACCENT_GRADIENT_DISABLED

FONT_NAMES = ('OgBody', 'OgBold', 'OgSmall', 'OgSmallBold', 'OgList', 'OgListBold', 'OgHeading', 'OgColumn', 'OgTitle', 'OgNav',
              'OgNowTitle', 'OgSymbol', 'OgBrand', 'OgLabel')
# All typographic roles use Uberata Clear v3.0; role-specific sizes/weights are retained.
HEADING_FONTS = ('OgTitle', 'OgNowTitle', 'OgBrand')


def enable_dpi_awareness() -> None:
    """Sharp text on high-DPI Windows displays (must run before the first Tk window)."""
    if sys.platform != 'win32':
        return
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            import ctypes
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def _font(root: tk.Misc, name: str, **options) -> tkfont.Font:
    try:
        existing = tkfont.nametofont(name, root=root)
        existing.configure(**options)
        return existing
    except tk.TclError:
        return tkfont.Font(root=root, name=name, **options)


def _classic_widget_colours(root: tk.Misc) -> None:
    """Dark defaults for classic Tk widgets (menus, list boxes, Tk-drawn dialogs)."""
    p = PALETTE
    for key, value in (('*Background', p['surface']), ('*Foreground', p['text']),
                       ('*activeBackground', p['accent_soft']), ('*activeForeground', p['text']),
                       ('*selectBackground', p['accent_soft']), ('*selectForeground', p['text']),
                       ('*insertBackground', p['text']), ('*highlightBackground', p['bg']),
                       ('*highlightColor', p['accent']), ('*troughColor', p['table']),
                       ('*disabledForeground', p['muted']), ('*Entry.Background', p['table']),
                       ('*Listbox.Background', p['table']), ('*Text.Background', p['table']),
                       ('*Menu.relief', 'flat'), ('*Menu.activeBorderWidth', 0)):
        root.option_add(key, value)


class _Textures:
    """Builds and keeps the PhotoImages alive for one Tk interpreter."""

    def __init__(self, root: tk.Misc):
        from PIL import ImageTk
        from . import textures as tx
        self.root = root
        self._tk = ImageTk
        self._tx = tx
        self.images: dict[str, object] = {}
        self.pil: dict[str, object] = {}

    def photo(self, key: str, image) -> object:
        self.images[key] = self._tk.PhotoImage(image, master=self.root)
        self.pil[str(self.images[key])] = image
        return self.images[key]

    def pil_of(self, photo) -> object:
        """The Pillow image a PhotoImage was made from (to blend hover steps from)."""
        return self.pil[str(photo)]

    def grain(self, key: str, base: str, amount: float = 0.20) -> object:
        return self.photo(key, self._tx.grain(base, amount=amount, seed=len(self.images)))

    def surface(self, key: str, top: str, bottom: str, behind: str, size=(64, 48), **kw) -> object:
        return self.photo(key, self._tx.surface(size, top, bottom, behind=behind, seed=len(self.images), **kw))


def _background_layout(element: str, inner: list) -> list:
    return [(element, {'sticky': 'nswe', 'children': inner})]


def _label_layout(element: str) -> list:
    return _background_layout(element, [('Label.padding', {'sticky': 'nswe', 'children': [
        ('Label.label', {'sticky': 'nswe'})]})])


def _button_layout(element: str) -> list:
    return [(element, {'sticky': 'nswe', 'children': [('Button.focus', {'sticky': 'nswe', 'children': [
        ('Button.padding', {'sticky': 'nswe', 'children': [('Button.label', {'sticky': 'nswe'})]})]})]})]


def _check_layout(element: str, indicator: str = 'Checkbutton.indicator') -> list:
    return _background_layout(element, [('Checkbutton.padding', {'sticky': 'nswe', 'children': [
        (indicator, {'side': 'left', 'sticky': ''}),
        ('Checkbutton.focus', {'side': 'left', 'sticky': 'w', 'children': [
            ('Checkbutton.label', {'sticky': 'nswe'})]})]})])


def apply_theme(root: tk.Misc, heading_choice: str = 'new', body_choice: str = 'new') -> dict[str, tkfont.Font]:
    """Configure fonts, colours and textured ttk styles. Call once per Tk root."""
    base = tkfont.nametofont('TkDefaultFont', root=root)
    system = base.actual('family')
    size = max(abs(int(base.actual('size'))) or ds.BODY_POINTS, ds.BODY_POINTS)
    # 2.0.4: Uberata Clear v3.0 is the sole application typeface.
    from .. import fonts as app_fonts
    available = set(tkfont.families(root))
    heading = app_fonts.HEADING_FAMILY if app_fonts.HEADING_FAMILY in available else system
    body = clear = app_fonts.BODY_FAMILY if app_fonts.BODY_FAMILY in available else system
    # Uberata ships one regular face; preserve role hierarchy through Tk's weight option.
    display_weight = 'normal'
    roles = {'TkDefaultFont': body, 'TkTextFont': clear, 'TkHeadingFont': body, 'TkMenuFont': body, 'TkFixedFont': body,
             'TkCaptionFont': body, 'TkSmallCaptionFont': body, 'TkIconFont': body, 'TkTooltipFont': body}
    for name, family in roles.items():
        try:
            tkfont.nametofont(name, root=root).configure(family=family, size=size)
        except tk.TclError:
            pass

    def role(name, tk_name, family=None, **extra):
        fam, _delta, weight, _use = ds.TYPE[name]
        family = family or (heading if fam == 'display' else body)
        weight = display_weight if fam == 'display' else weight
        return _font(root, tk_name, family=family, size=ds.points(name, size), weight=weight, **extra)

    fonts = {
        'body': role('body', 'OgBody'),
        'bold': role('body_bold', 'OgBold'),
        'small': role('small', 'OgSmall'),
        'small_bold': role('small_bold', 'OgSmallBold'),
        'list': role('body', 'OgList'),
        'list_bold': role('body_bold', 'OgListBold'),
        'heading': role('title', 'OgHeading'),          # card / section titles (text face, bold)
        'title': role('display_xl', 'OgTitle'),          # page titles
        'column': role('label', 'OgColumn'),             # table column headings
        'label': role('label', 'OgLabel'),               # sidebar group labels
        'nav': _font(root, 'OgNav', family=body, size=ds.sidebar_font_points(size)),
        'now_title': role('display_l', 'OgNowTitle'),
        'symbol': _font(root, 'OgSymbol', family=body, size=size + 4),
        'brand': role('brand', 'OgBrand'),
    }
    p = PALETTE
    s = ttk.Style(root)
    if 'clam' in s.theme_names():
        s.theme_use('clam')
    root.configure(background=p['bg'])
    _classic_widget_colours(root)
    root.option_add('*TCombobox*Listbox.font', fonts['list'])
    root.option_add('*Menu.font', fonts['body'])
    row_height = max(ds.ROW_HEIGHT, fonts['list'].metrics('linespace') + 12)

    t = _Textures(root)
    root._og_textures = t  # keep PhotoImages alive as long as the window

    # ---- grained backgrounds -------------------------------------------------
    for name, colour, amount in (('Og.page', p['bg'], 0.20), ('Og.card', p['surface'], 0.18),
                                 ('Og.side', p['sidebar'], 0.22)):
        s.element_create(name, 'image', t.grain(name, colour, amount), sticky='nswe', width=1, height=1)

    s.configure('.', background=p['bg'], foreground=p['text'], font=fonts['body'],
                bordercolor=p['border'], lightcolor=p['surface'], darkcolor=p['border'],
                troughcolor=p['table'], focuscolor=p['accent'], selectbackground=p['accent_soft'],
                selectforeground=p['text'], insertcolor=p['text'], fieldbackground=p['table'])
    # v1.9.0: cards are rounded and bevelled; CardInner.TFrame (a frame inside a card) and the
    # full-width player bar (Now.TFrame) stay flat
    s.element_create('Og.cardframe', 'image',
                     t.surface('cardframe', p['surface'], p['surface'], p['bg'], size=(256, 256), radius=RADIUS + 1,
                               amount=0.18, edge=0, bevel=BEVEL_SOFT),
                     border=10, sticky='nswe', width=1, height=1)
    for style, element in (('TFrame', 'Og.page'), ('Card.TFrame', 'Og.cardframe'), ('CardInner.TFrame', 'Og.card'),
                           ('Now.TFrame', 'Og.card'), ('Sidebar.TFrame', 'Og.side')):
        s.layout(style, [(element, {'sticky': 'nswe'})])
    s.configure('TFrame', background=p['bg'])
    s.configure('Card.TFrame', background=p['surface'])
    s.configure('CardInner.TFrame', background=p['surface'])
    s.configure('Now.TFrame', background=p['surface'])
    s.configure('Sidebar.TFrame', background=p['sidebar'])

    # ---- labels (grain behind the text so they blend into their panel) -------
    label_styles = {
        'TLabel': ('Og.page', {}),
        'Muted.TLabel': ('Og.page', {'foreground': p['muted']}),
        'Title.TLabel': ('Og.page', {'font': fonts['title']}),
        'Section.TLabel': ('Og.page', {'font': fonts['heading']}),     # 2.0: amber is kept for actions
        'Status.TLabel': ('Og.page', {'foreground': p['muted'], 'font': fonts['small']}),
        'Card.TLabel': ('Og.card', {}),
        'CardMuted.TLabel': ('Og.card', {'foreground': p['muted']}),
        'CardSection.TLabel': ('Og.card', {'font': fonts['heading']}),
        'NowTitle.TLabel': ('Og.card', {'font': fonts['now_title']}),
        'NowMuted.TLabel': ('Og.card', {'foreground': p['muted']}),
        'Brand.TLabel': ('Og.side', {'foreground': GRADIENT[1], 'font': fonts['brand']}),
        'SidebarMuted.TLabel': ('Og.side', {'foreground': p['faint'], 'font': fonts['small']}),
        'SidebarLabel.TLabel': ('Og.side', {'foreground': p['faint'], 'font': fonts['label']}),
        'CardTitle.TLabel': ('Og.card', {'font': fonts['heading']}),
        'CardDisplay.TLabel': ('Og.card', {'font': fonts['now_title']}),
        'Faint.TLabel': ('Og.page', {'foreground': p['faint'], 'font': fonts['small']}),
    }
    for style, (element, options) in label_styles.items():
        s.layout(style, _label_layout(element))
        s.configure(style, foreground=options.pop('foreground', p['text']), **options)

    for style, element in (('TCheckbutton', 'Og.page'), ('Card.TCheckbutton', 'Og.card')):
        s.layout(style, _check_layout(element))
        s.configure(style, foreground=p['text'], indicatorbackground=p['table'],
                    indicatorforeground=p['accent'], indicatormargin=(0, 0, 8, 0), padding=(0, 2))
        s.map(style, indicatorbackground=[('active', p['hover'])])

    # ---- buttons --------------------------------------------------------------
    # v1.8.9: every button style also gets in-between images for the hover fade (levels 1..3
    # between rest and hover) and a release flash, used by animation.ButtonMotion; gradient
    # images also get drift frames (animation.GradientAnimator).
    from PIL import Image
    from . import animation
    anim = root._og_anim = animation.GradientAnimator(root)
    motion = root._og_motion = animation.ButtonMotion(root)
    levels = animation.HOVER_LEVELS
    hover_elements: dict[str, dict] = {}       # element -> {'border': .., 'level images': ..}

    def blend(a, b, f):
        if a.size != b.size:                  # a flat grain tile behind a smaller hover panel
            a = a.crop((0, 0) + b.size)
        return Image.blend(a, b, f)

    def flash_of(image):
        return Image.blend(image, Image.new('RGB', image.size, (255, 236, 200)), 0.16)

    def hover_images(element, normal, active, pressed, disabled, border):
        """Static in-between images (photos) for a non-gradient button element."""
        rest, hot = t.pil_of(normal), t.pil_of(active)
        photos = {k: t.photo(f'{element}-h{k}', blend(rest, hot, k / (levels + 1))) for k in range(1, levels + 1)}
        photos['F'] = t.photo(f'{element}-hF', flash_of(blend(rest, hot, 1.0)))
        hover_elements[element] = {'border': border, 'images': photos, 'pressed': pressed, 'disabled': disabled}

    def button(element, normal, active, pressed, disabled, focus=None, border=7):
        states = [('disabled', disabled), ('pressed', pressed), ('active', active)]
        if focus is not None:
            states.append(('focus', focus))
        s.element_create(element, 'image', normal, *states, border=border, padding=2, sticky='nswe',
                         width=16, height=16)
        hover_images(element, normal, active, pressed, disabled, border)

    def raised(key, top, bottom, behind, outline, sheen, size=(64, 44), radius=RADIUS, **kw):
        kw.setdefault('bevel', BEVEL)                 # v1.9.0: soft bevel on every raised button
        return t.surface(key, top, bottom, behind, size=size, radius=radius, outline=outline, highlight=sheen, **kw)

    bg, card, side = p['bg'], p['surface'], p['sidebar']
    # v1.8.6: every boxed button has a black border (keyboard focus keeps the accent border)
    black = BUTTON_BORDER
    button('Og.Button',
           raised('btn', '#383029', '#29211C', bg, black, '#46382E'),
           raised('btn-a', '#4A3A2E', '#332821', bg, black, '#5D4939'),
           raised('btn-p', '#261F1B', '#30271F', bg, black, None),
           raised('btn-d', '#271F1B', '#231C18', bg, black, None),
           raised('btn-f', '#3A2F28', '#2B231E', bg, p['accent'], '#4A3C32'))
    ghost = raised('ghost', '#29211D', '#261E1A', bg, black, None)          # quiet, but boxed
    button('Og.Ghost', ghost,
           raised('ghost-a', '#30261F', '#2A211C', bg, black, None),
           raised('ghost-p', '#241D19', '#2A211C', bg, black, None), ghost,
           raised('ghost-f', '#211A16', '#211A16', bg, p['accent'], None))
    button('Og.Danger',
           raised('danger', '#33211E', '#281B19', bg, '#684038', None),
           raised('danger-a', '#51302B', '#38231F', bg, '#9F5148', None),
           raised('danger-p', '#261816', '#38241F', bg, '#A6534A', None),
           raised('danger-d', '#251F1D', '#241D1B', bg, black, None),
           raised('danger-f', '#33211E', '#281B19', bg, p['failed'], None))
    button('Og.Transport', t.grain('tr', card, 0.18),
           raised('tr-a', '#382D26', '#2F2620', card, '#4A3C32', None, radius=3),
           raised('tr-p', '#271F1A', '#2F2620', card, '#4A3C32', None, radius=3), t.grain('tr-d', card, 0.18),
           raised('tr-f', '#261F1B', '#261F1B', card, p['accent'], None, radius=3))
    nav = t.grain('nav', side, 0.22)
    # sidebar items: v1.9.0 rounds and bevels the hover/pressed/focus panels
    button('Og.Nav', nav,
           t.surface('nav-a', '#1E1714', '#1B1512', side, size=(64, 40), radius=RADIUS, bevel=BEVEL_SOFT),
           t.surface('nav-p', '#241B17', '#241B17', side, size=(64, 40), radius=RADIUS, bevel=BEVEL_SUNKEN),
           nav,
           t.surface('nav-f', '#19130F', '#19130F', side, size=(64, 40), radius=RADIUS, outline='#5A4536'),
           border=(6, 6, 6, 6))

    # Gradient (accent) styles are rendered at their exact natural height: ttk tiles
    # the middle of an image element, which would otherwise repeat the gradient.
    pad = (ds.BUTTON_HORIZONTAL, ds.BUTTON_VERTICAL)
    accent_styles = {
        'Accent.TButton': {'padding': pad, 'font': fonts['bold']},
        'Play.TButton': {'padding': (8, 1), 'font': fonts['symbol'], 'width': 3},
        'NavActive.TButton': {'padding': (ds.SIDEBAR_INSET, ds.NAV_VERTICAL_PAD), 'font': fonts['nav'], 'anchor': 'w', 'space': 10},
    }
    s.element_create('Og.Probe', 'image', t.grain('probe', bg), border=7, padding=2, sticky='nswe',
                     width=16, height=16)
    heights = {}
    for style, options in accent_styles.items():
        probe = 'Probe' + style
        s.layout(probe, _button_layout('Og.Probe'))
        s.configure(probe, focusthickness=0, **options)  # same as the real style below
        widget = ttk.Button(root, text='Ag ▶', style=probe)
        widget.update_idletasks()
        heights[style] = max(24, widget.winfo_reqheight())
        widget.destroy()

    def animated(key, factory):
        """A PhotoImage showing ``factory(shift)``: frame 0 now, the drift frames later."""
        photo = t.photo(key, factory(0.0))
        anim.register(photo, factory)
        return photo

    def exact(element, height, behind, radius, stops_and_outlines, side_border=10):
        cache: dict = {}

        def state(i, stops, outline, sheen):
            def render(shift):
                key = (i, shift)
                if key not in cache:
                    cache[key] = t._tx.gradient((96, height), stops, behind=behind, radius=radius,
                                                outline=outline, sheen=sheen, seed=31 + i, shift=shift,
                                                bevel=BEVEL)
                    if len(cache) > 64:
                        cache.pop(next(iter(cache)))
                return cache[key]
            return render

        renders = [state(i, *spec) for i, spec in enumerate(stops_and_outlines)]
        normal_r, active_r, pressed_r, disabled_r, focus_r = renders
        normal = animated(f'{element}-0', normal_r)
        active = animated(f'{element}-1', active_r)
        pressed = animated(f'{element}-2', pressed_r)
        disabled = t.photo(f'{element}-3', disabled_r(0.0))           # greyed: no drift
        focus = animated(f'{element}-4', focus_r)
        top = height // 2
        border = (side_border, top, side_border, height - top - 1)
        s.element_create(element, 'image', normal, ('disabled', disabled), ('pressed', pressed),
                         ('active', active), ('focus', focus), border=border, padding=2, sticky='nswe',
                         width=16, height=16)
        photos = {k: animated(f'{element}-h{k}', lambda shift, k=k: blend(normal_r(shift), active_r(shift),
                                                                            k / (levels + 1)))
                  for k in range(1, levels + 1)}
        photos['F'] = animated(f'{element}-hF', lambda shift: flash_of(active_r(shift)))
        hover_elements[element] = {'border': border, 'images': photos, 'pressed': pressed, 'disabled': disabled}

    states = [(GRADIENT, BUTTON_BORDER, '#FFE08A'), (GRADIENT_HOVER, BUTTON_BORDER, '#FFE9A6'),
              (GRADIENT_PRESSED, BUTTON_BORDER, None), (GRADIENT_DISABLED, BUTTON_BORDER, None),
              (GRADIENT, '#FFF1C9', '#FFE08A')]                          # focus: light border
    exact('Og.Accent', heights['Accent.TButton'], bg, 5, states)
    # the play button carries a black outline, like the other music controls
    play_states = [(stops, BUTTON_BORDER if i < 4 else outline, sheen)
                   for i, (stops, outline, sheen) in enumerate(states)]
    exact('Og.Play', heights['Play.TButton'], card, 10, play_states)
    # Active navigation item: warm tint with a gradient bar on the left edge (the bar drifts).
    nav_h = heights['NavActive.TButton']
    # v1.9.0: a rounded, bevelled panel with a rounded gradient pill near its left edge
    navon_base = t._tx.surface((64, nav_h), '#2C1F17', '#2A1D15', behind=side, radius=RADIUS, edge=0, seed=41,
                               bevel=BEVEL_SOFT)
    navon_focus_base = t._tx.surface((64, nav_h), '#2C1F17', '#2A1D15', behind=side, radius=RADIUS, edge=0,
                                     seed=41, outline='#8A5A34', bevel=BEVEL_SOFT)
    pill_h = max(8, nav_h - 14)

    def navon_render(base_image):
        def render(shift):
            image = base_image.copy()
            pill = t._tx.gradient((4, pill_h), GRADIENT, behind='#2C1F17', radius=2, seed=43, shift=shift)
            image.paste(pill, (4, (nav_h - pill_h) // 2))
            return image
        return render
    top = nav_h // 2
    s.element_create('Og.NavOn', 'image', animated('navon', navon_render(navon_base)),
                     ('focus', animated('navon-f', navon_render(navon_focus_base))),
                     border=(10, top, 6, nav_h - top - 1), padding=2, sticky='nswe', width=16, height=16)

    button_styles = (
            ('TButton', 'Og.Button', {'padding': pad}),
            ('Accent.TButton', 'Og.Accent', dict(accent_styles['Accent.TButton'], foreground=p['on_accent'])),
            ('Ghost.TButton', 'Og.Ghost', {'padding': (ds.BUTTON_HORIZONTAL, ds.BUTTON_VERTICAL)}),
            ('Danger.TButton', 'Og.Danger', {'padding': (ds.BUTTON_HORIZONTAL, ds.BUTTON_VERTICAL), 'foreground': '#EFB8AA'}),
            # gradient icons are images (gui/icons.py); the amber text is the fallback without Pillow
            ('Transport.TButton', 'Og.Transport', {'padding': (6, 1), 'font': fonts['symbol'], 'width': 3,
                                                   'foreground': GRADIENT[1]}),
            # shuffle / repeat toggles: muted when off, amber when on
            ('Mode.TButton', 'Og.Transport', {'padding': (6, 1), 'font': fonts['small_bold'], 'foreground': p['muted']}),
            ('ModeOn.TButton', 'Og.Transport', {'padding': (6, 1), 'font': fonts['small_bold'], 'foreground': p['accent'], 'space': 4}),
            ('Play.TButton', 'Og.Play', dict(accent_styles['Play.TButton'], foreground=p['on_accent'])),
            ('Nav.TButton', 'Og.Nav', {'padding': (ds.SIDEBAR_INSET, ds.NAV_VERTICAL_PAD), 'font': fonts['nav'], 'anchor': 'w', 'space': 10,
                                       'foreground': p['sidebar_fg']}),
            ('NavActive.TButton', 'Og.NavOn', dict(accent_styles['NavActive.TButton'], foreground=ds.COLOR['text_bright'])),
            ('NavRail.TButton', 'Og.Nav', {'padding': (0, ds.NAV_VERTICAL_PAD), 'font': fonts['nav'], 'anchor': 'center',
                                           'foreground': p['sidebar_fg']}),
            ('NavActiveRail.TButton', 'Og.NavOn', dict(accent_styles['NavActive.TButton'], anchor='center',
                                                        padding=(0, ds.NAV_VERTICAL_PAD), foreground=ds.COLOR['text_bright'])))
    s.configure('TButton', width=0)       # 2.0: buttons fit their label (clam reserves 11 characters)
    for style, element, options in button_styles:
        s.layout(style, _button_layout(element))
        options.setdefault('foreground', p['text'])
        s.configure(style, focusthickness=0, **options)
        s.map(style, foreground=[('disabled', PALETTE['faint'])] + ([('active', ds.COLOR['text_bright'])] if style.startswith('Nav.') or style.startswith('NavRail') else []))
    s.map('Accent.TButton', foreground=[('disabled', '#B09C8C')])
    s.map('Play.TButton', foreground=[('disabled', '#B09C8C')])

    # Press: the label sinks one pixel while the button is held down.
    for style, element, options in button_styles:
        padding = options.get('padding', 0)
        padding = (padding,) * 4 if isinstance(padding, int) else tuple(padding)
        if len(padding) == 2:
            padding = padding * 2
        elif len(padding) == 3:
            padding = padding + (padding[1],)
        left, top_pad, right, bottom = padding
        s.map(style, padding=[('pressed', (left, top_pad + 1, right, max(0, bottom - 1)))])

    # Hover fade and release flash: OgH1..3.<style> and OgHF.<style> (names inherit <style>'s options)
    for style, element, _options in button_styles:
        spec = hover_elements.get(element)
        if spec is None:
            continue
        for level, photo in spec['images'].items():
            name = f'{element}.h{level}'
            if name not in s.element_names():
                s.element_create(name, 'image', photo, ('disabled', spec['disabled']), ('pressed', spec['pressed']),
                                 border=spec['border'], padding=2, sticky='nswe', width=16, height=16)
            s.layout(animation.variant(level, style), _button_layout(name))
        motion.add_style(style)

    # ---- status chips (pill, grained; 'selected' state = active filter) -------
    chip = t.surface('chip', '#221B17', '#221B17', bg, size=(48, 28), radius=3, outline='#3F332B', bevel=BEVEL_SOFT)
    chip_on = t.surface('chip-on', '#4A2C18', '#3D2414', bg, size=(48, 28), radius=3, outline=p['accent'],
                        bevel=BEVEL_SOFT)
    chip_hover = t.surface('chip-h', '#2A211C', '#251D19', bg, size=(48, 28), radius=3, outline='#55453A',
                           bevel=BEVEL_SOFT)
    s.element_create('Og.Chip', 'image', chip, ('selected', chip_on), ('active', chip_hover),
                     border=12, padding=(4, 1), sticky='nswe', width=26, height=20)
    s.layout('Chip.TLabel', _label_layout('Og.Chip'))
    s.configure('Chip.TLabel', padding=(8, 2), font=fonts['small_bold'])

    # ---- fields: rounded, sunken (v1.9.0) -----------------------------------------
    def field(name, behind):
        fill, size = p['table'], (64, 32)
        normal = t.surface(f'{name}', fill, fill, behind, size=size, radius=RADIUS, outline=p['button_border'],
                           edge=0, amount=0.12, bevel=BEVEL_SUNKEN)
        hover = t.surface(f'{name}-a', fill, fill, behind, size=size, radius=RADIUS, outline='#5A4A3E',
                          edge=0, amount=0.12, bevel=BEVEL_SUNKEN)
        focus = t.surface(f'{name}-f', fill, fill, behind, size=size, radius=RADIUS, outline=p['accent'],
                          edge=0, amount=0.12, bevel=BEVEL_SUNKEN)
        disabled = t.surface(f'{name}-d', p['bg'], p['bg'], behind, size=size, radius=RADIUS, outline=p['border'],
                             edge=0, amount=0.12)
        s.element_create(name, 'image', normal, ('disabled', disabled), ('focus', focus), ('hover', hover),
                         border=7, padding=1, sticky='nswe', width=16, height=16)
    field('Og.Field', bg)
    field('Og.Field.card', card)
    for style, element in (('TEntry', 'Og.Field'), ('Card.TEntry', 'Og.Field.card')):
        s.layout(style, [(element, {'sticky': 'nswe', 'children': [
            ('Entry.padding', {'sticky': 'nswe', 'children': [('Entry.textarea', {'sticky': 'nswe'})]})]})])
        s.configure(style, fieldbackground=p['table'], foreground=p['text'], insertcolor=p['text'], padding=(8, 6))
        s.map(style, foreground=[('disabled', p['muted'])])
    # search: room on the left for the magnifier icon; icon and placeholder sit on the field colour
    s.layout('Search.TEntry', s.layout('TEntry'))
    s.configure('Search.TEntry', fieldbackground=p['table'], foreground=p['text'], insertcolor=p['text'],
                padding=(36, 7, 10, 7))
    s.map('Search.TEntry', foreground=[('disabled', p['faint'])])
    for style, colour in (('Field.TLabel', p['faint']), ('Placeholder.TLabel', p['faint'])):
        s.layout(style, [('Label.padding', {'sticky': 'nswe', 'children': [('Label.label', {'sticky': 'nswe'})]})])
        s.configure(style, background=p['table'], foreground=colour, padding=0, font=fonts['body'])
    s.layout('TCombobox', [('Og.Field', {'sticky': 'nswe', 'children': [
        ('Combobox.downarrow', {'side': 'right', 'sticky': 'ns'}),
        ('Combobox.padding', {'sticky': 'nswe', 'children': [('Combobox.textarea', {'sticky': 'nswe'})]})]})])
    # the arrow sits on the field: same colour, no box of its own
    s.configure('TCombobox', fieldbackground=p['table'], background=p['table'], foreground=p['text'],
                bordercolor=p['table'], lightcolor=p['table'], darkcolor=p['table'],
                arrowcolor=p['muted'], padding=(6, 4), arrowsize=12)
    s.map('TCombobox', fieldbackground=[('readonly', p['table'])], background=[('active', p['table'])],
          arrowcolor=[('active', p['text'])])

    # ---- check boxes: a small rounded, bevelled box with a tick (v1.9.0) ------------
    from PIL import ImageDraw as _Draw

    def check_image(key, fill, outline, tick, behind, bevel_strength):
        box = 16
        image = t._tx.surface((box, box), fill, fill, behind=behind, radius=1.5, outline=outline, edge=0,
                              amount=0.10, bevel=bevel_strength)
        if tick:
            big = image.resize((box * 4, box * 4))
            _Draw.Draw(big).line([(14, 33), (26, 45), (50, 19)], fill=t._tx._rgb(tick), width=7, joint='curve')
            image = big.resize((box, box), Image.LANCZOS)
        # the gap before the label is part of the image (on the panel's own grain)
        framed = t._tx.grain(behind, (box + 8, box), amount=0.20, seed=5, mottle=False)
        framed.paste(image, (0, 0))
        return t.photo(key, framed)

    for suffix, behind in (('', bg), ('.card', card)):
        off = check_image(f'check{suffix}', p['table'], '#5A4A3E', None, behind, BEVEL_SUNKEN)
        off_hover = check_image(f'check-a{suffix}', p['table'], p['accent'], None, behind, BEVEL_SUNKEN)
        on = check_image(f'check-on{suffix}', p['accent'], '#000000', p['on_accent'], behind, BEVEL)
        on_hover = check_image(f'check-on-a{suffix}', '#FDA629', '#000000', p['on_accent'], behind, BEVEL)
        disabled = check_image(f'check-d{suffix}', p['bg'], p['border'], None, behind, 0.0)
        s.element_create(f'Og.Check{suffix}', 'image', off, ('disabled', disabled),
                         ('selected', 'active', on_hover), ('selected', on), ('active', off_hover),
                         sticky='w', width=24, height=16)
    s.layout('TCheckbutton', _check_layout('Og.page', 'Og.Check'))
    s.layout('Card.TCheckbutton', _check_layout('Og.card', 'Og.Check.card'))

    # v1.9.0: the table sits in a rounded, sunken field
    table_field = t.surface('tablefield', p['table'], p['table'], bg, size=(64, 64), radius=RADIUS + 1,
                            outline=p['border'], edge=0, amount=0.10, bevel=BEVEL_SUNKEN)
    s.element_create('Og.TableField', 'image', table_field, border=8, padding=3, sticky='nswe', width=16, height=16)
    for style in ('Treeview', 'List.Treeview'):
        s.layout(style, [('Og.TableField', {'sticky': 'nswe', 'children': [
            ('Treeview.padding', {'sticky': 'nswe', 'children': [('Treeview.treearea', {'sticky': 'nswe'})]})]})])
    s.configure('Treeview', background=p['table'], fieldbackground=p['table'], foreground=p['text'],
                bordercolor=p['border'], lightcolor=p['table'], darkcolor=p['table'],
                rowheight=row_height, borderwidth=0, font=fonts['list'])
    s.map('Treeview', background=[('selected', p['accent_soft'])], foreground=[('selected', '#FFF4E6')])
    s.configure('Treeview.Heading', background=p['surface'], foreground=p['muted'], font=fonts['column'],
                bordercolor=p['surface'], lightcolor=p['surface'], darkcolor=p['surface'],
                relief='flat', padding=(8, 7))
    s.map('Treeview.Heading', background=[('active', p['hover'])], foreground=[('active', p['text'])])
    s.configure('List.Treeview', rowheight=row_height + 4)

    # v1.9.0: slim rounded, bevelled scrollbar thumbs on a page-coloured trough, no arrow buttons
    for orient in ('Vertical', 'Horizontal'):
        size = (10, 40) if orient == 'Vertical' else (40, 10)
        thumb = t.surface(f'thumb-{orient}', '#4A3C32', '#3E322A', bg, size=size, radius=2, edge=0, amount=0.10,
                          bevel=BEVEL_SOFT)
        thumb_hot = t.surface(f'thumb-a-{orient}', '#6A5646', '#5A4A3E', bg, size=size, radius=2, edge=0,
                              amount=0.10, bevel=BEVEL_SOFT)
        thumb_on = t.surface(f'thumb-p-{orient}', p['accent'], p['accent_dark'], bg, size=size, radius=2, edge=0,
                             amount=0.10, bevel=BEVEL_SOFT)
        border = (4, 6, 4, 6) if orient == 'Vertical' else (6, 4, 6, 4)
        s.element_create(f'Og{orient[0]}.thumb', 'image', thumb, ('pressed', thumb_on), ('active', thumb_hot),
                         border=border, sticky='nswe', width=size[0] if orient == 'Vertical' else 20,
                         height=size[1] if orient == 'Horizontal' else 20)
        sticky = 'ns' if orient == 'Vertical' else 'we'
        s.layout(f'{orient}.TScrollbar', [(f'{orient}.Scrollbar.trough', {'sticky': sticky, 'children': [
            (f'Og{orient[0]}.thumb', {'sticky': 'nswe'})]})])
        s.configure(f'{orient}.TScrollbar', troughcolor=p['bg'], bordercolor=p['bg'], lightcolor=p['bg'],
                    darkcolor=p['bg'], gripcount=0, relief='flat', arrowsize=10)
    s.configure('Horizontal.TScale', background=GRADIENT[1], troughcolor='#120E0C', bordercolor=p['surface'],
                lightcolor=GRADIENT[0], darkcolor=GRADIENT[2], sliderthickness=14, sliderlength=14)
    s.map('Horizontal.TScale', background=[('active', GRADIENT_HOVER[1])])
    s.configure('Horizontal.TProgressbar', troughcolor='#120E0C', background=GRADIENT[1],
                bordercolor=p['border'], lightcolor=GRADIENT[0], darkcolor=GRADIENT[2], thickness=8)
    s.configure('TPanedwindow', background=p['bg'])
    s.configure('Sash', sashthickness=6, gripcount=0, background=p['bg'])
    s.configure('TSeparator', background=p['border'])
    s.configure('TMenubutton', background=p['button'], foreground=p['text'])
    return fonts


def set_heading_font(root: tk.Misc, choice: object = None) -> str:
    """All heading roles use Uberata Clear; retained for compatibility."""
    from .. import fonts as app_fonts
    family = app_fonts.HEADING_FAMILY
    if family not in set(tkfont.families(root)):
        return tkfont.nametofont('OgTitle', root=root).actual('family')
    for name in HEADING_FONTS:
        try:
            tkfont.nametofont(name, root=root).configure(family=family, weight='normal')
        except tk.TclError:
            continue
    return family


def set_body_font(root: tk.Misc, choice: object = None) -> str:
    """1.9.x API. 2.0 has one text face; returns the family in use."""
    return tkfont.nametofont('OgBody', root=root).actual('family')
