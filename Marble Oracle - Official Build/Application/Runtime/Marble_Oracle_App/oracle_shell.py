"""One page shell for every Marble Oracle workspace.

Before 0.4.9.5 each workspace drew its own frame: side rails of 225, 240 and
312 px (and none at all on PASSPHRASE), titles from 15 to 23 pt in three
colours, buttons at 10 or 11 pt with four different paddings, and the HOME
button in a different corner on every tab. This module is the single source
for those choices, so the tabs line up when you switch between them:

    ┌──────────── rail ────────────┬──────────────── main ─────────────────┐
    │ WORDMARK          (brand)    │ PAGE TITLE                    [chip]  │
    │ TAGLINE           (group)    │ One-line description          (sub)   │
    │                              │                                       │
    │ GROUP LABEL                  │  page content                         │
    │  NAV ITEM                    │                                       │
    │  NAV ITEM                    │                                       │
    │                              │                                       │
    │ [ HOME ]                     │ status line                  (status) │
    │ VERSION · LOCAL              │                                       │
    └──────────────────────────────┴───────────────────────────────────────┘

The type scale follows Oggcultist's (body 12 pt; labels 10 pt bold; card
titles 14 pt bold), which the other workspaces already took their colours
from. Sizes are Tk points; Tk scales them with the display.
"""
from __future__ import annotations

import tkinter as tk

from marble_uberata import FAMILY
from oggcultist_design_system import COLOR as C
from oracle_design import HOME_LABEL
from oracle_ogg_texture import frame as ogl_frame, label as ogl_label

# ---- type scale (points) ----------------------------------------------------
TYPE = {
    'brand': (18, 'bold'),       # wordmark at the top of the rail
    'page_title': (20, 'bold'),  # the title of the page in the main area
    'subtitle': (11, 'normal'),  # one line under the page title
    'section': (14, 'bold'),     # card and section headings
    'group': (10, 'bold'),       # rail group labels and column headings (capitals)
    'nav': (13, 'bold'),         # rail navigation items
    'button': (11, 'bold'),      # every push button
    'body': (11, 'normal'),
    'body_bold': (11, 'bold'),
    'small': (10, 'normal'),     # captions, hints
    'status': (10, 'normal'),    # the status line at the foot of the page
}

# ---- layout (pixels) --------------------------------------------------------
RAIL_WIDTH = 240          # navigation rails (EIDOLITH, PASSPHRASE, TOUCH TYPE)
RAIL_NARROW = 188         # the same rail below NARROW_WIDTH
LIST_RAIL_WIDTH = 312     # AUGURSPEX: its rail is a 23-row market list, not navigation
NARROW_WIDTH = 850        # workspace width below which rails narrow
SHORT_HEIGHT = 540        # main-area height below which the page subtitle is hidden
COLLAPSE_WIDTH = 800      # a collapsible rail (extras only, no navigation) steps aside below this
RAIL_PADX = 16
RAIL_TOP = 14
MAIN_PADX = 20
HEADER_PADY = (14, 10)
BUTTON_PAD = (14, 7)
NAV_PADY = 8              # rail item padding; NAV_PADY_SHORT in short windows
NAV_PADY_SHORT = 3


def _descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from _descendants(child)


def brand_font(canvas_width):
    """The brand type, a step smaller when a drawn logo must fit a narrowed rail."""
    size, weight = TYPE['brand']
    return (FAMILY, size if canvas_width >= RAIL_WIDTH - 2 * RAIL_PADX else size - 4, weight)


def font(role):
    size, weight = TYPE[role]
    return (FAMILY, size, weight)


def shown(text):
    """Capitals in Classic; sentence case in Dark and Light (oracle_appearance)."""
    import oracle_appearance
    return oracle_appearance.display(text)


def _modern():
    import oracle_appearance
    return oracle_appearance.modern()


def label(parent, text='', role='body', colour='text', **kwargs):
    """A textured label in the shell's type scale and colour roles."""
    return ogl_label(parent, text=shown(text), fg=C[colour], font=font(role), **kwargs)


def button(parent, text, command, *, primary=False, width=None, padx=None, pady=None):
    """The suite's push button: one bright primary, quiet boxed secondaries (Dark / Light: no box, just the fill)."""
    if _modern():
        try:
            ground = parent.cget('bg')
        except tk.TclError:
            ground = C['canvas']
        return tk.Button(parent, text=shown(text), command=command, cursor='hand2', relief='flat', bd=0,
                         padx=BUTTON_PAD[0] if padx is None else padx,
                         pady=BUTTON_PAD[1] if pady is None else pady, width=width, font=font('button'),
                         bg=C['accent'] if primary else C['control'],
                         fg=C['text_on_accent'] if primary else C['text'],
                         activebackground=C['accent_deep'] if primary else C['hover'],
                         activeforeground=C['text_on_accent'] if primary else C['text'],
                         highlightthickness=2, highlightbackground=ground, highlightcolor=C['focus'])
    return tk.Button(parent, text=text, command=command, cursor='hand2', relief='flat', bd=0,
                     padx=BUTTON_PAD[0] if padx is None else padx,
                     pady=BUTTON_PAD[1] if pady is None else pady, width=width,
                     font=font('button'),
                     bg=C['accent'] if primary else C['control'],
                     fg=C['text_on_accent'] if primary else C['text'],
                     activebackground=C['accent_deep'] if primary else C['hover'],
                     activeforeground=C['text_on_accent'] if primary else C['text'],
                     highlightthickness=2,
                     highlightbackground=C['accent'] if primary else C['control_line'],
                     highlightcolor=C['focus'])   # 2 px cream ring on keyboard focus


def nav_button(parent, text, command):
    """A rail item: flat on the rail, outlined in the accent when it is the current page."""
    btn = tk.Button(parent, text=shown(text), command=command, cursor='hand2', relief='flat', bd=0,
                    padx=12, pady=NAV_PADY, anchor='w', justify='left', font=font('nav'),
                    bg=C['sidebar'], fg=C['text'], activebackground=C['hover'],
                    activeforeground=C['text_bright'], highlightthickness=2,
                    highlightbackground=C['sidebar'], highlightcolor=C['focus'])
    btn._shell_nav = True
    btn.pack(fill='x', pady=2)
    return btn


def set_nav_current(btn, current):
    """Current page: amber-tinted fill and amber text, no outline. The outline is
    kept for keyboard focus (cream), so the two can never be confused."""
    btn.configure(bg=C['accent_soft'] if current else C['sidebar'],
                  fg=C['text_bright'] if current else C['text'],
                  activebackground=C['accent_soft'] if current else C['hover'],
                  highlightbackground=C['accent_soft'] if current else C['sidebar'])


class Shell:
    """Rail + vertical rule + main area inside `parent` (packed to fill it).

    Attributes: rail, main. Helpers place the standard parts in them.
    """

    def __init__(self, parent, *, rail_width=RAIL_WIDTH, narrow_width=RAIL_NARROW, collapsible=False):
        """`collapsible`: the rail holds only extras (no navigation), so in a very
        narrow workspace it may step aside; HOME stays in the suite's tab bar."""
        self.rail_width = rail_width
        self.narrow_width = narrow_width
        self.collapsible = collapsible
        self.collapsed = False
        self._wrapped = []
        self._brand_title = None
        self._logo = None
        self._short = False
        self._short_hidden = []      # (widget, pack options): the tagline and version line
        self.root = ogl_frame(parent, bg=C['sidebar'])
        self.root.pack(fill='both', expand=True)
        # A plain Tk frame holds the width: some Linux ttk themes collapse a
        # textured frame to its image element's size.
        self.rail_shell = tk.Frame(self.root, bg=C['sidebar'], width=rail_width, highlightthickness=0)
        self.rail_shell.pack(side='left', fill='y')
        self.rail_shell.pack_propagate(False)
        self.rail = ogl_frame(self.rail_shell, bg=C['sidebar'])
        self.rail.pack(fill='both', expand=True)
        self.rule = tk.Frame(self.root, bg=C['line'], width=1)
        self.rule.pack(side='left', fill='y')
        self.main = ogl_frame(self.root, bg=C['canvas'])
        self.main.pack(side='left', fill='both', expand=True)
        self._rail_bottom = None
        self._subtitle = None
        self._subtitle_shown = True
        self.main.bind('<Configure>', self._fit_height, add='+')
        self.root.bind('<Configure>', self._fit_width, add='+')

    def _fit_width(self, event):
        """Below NARROW_WIDTH every rail narrows the same way, giving the page the room."""
        if event.widget is not self.root or event.width <= 1:
            return
        collapse = self.collapsible and event.width < COLLAPSE_WIDTH
        if collapse != self.collapsed:
            self.collapsed = collapse
            if collapse:
                self.rail_shell.pack_forget()
                self.rule.pack_forget()
            else:
                self.rail_shell.pack(side='left', fill='y', before=self.main)
                self.rule.pack(side='left', fill='y', before=self.main)
        self.set_rail_width(self.narrow_width if event.width < NARROW_WIDTH else self.rail_width)

    def _fit_height(self, event):
        """In a short window the page description and the rail's spacing give their height to the content."""
        if event.widget is not self.main or event.height <= 1:
            return
        short = event.height < SHORT_HEIGHT
        if short != self._short:
            self._short = short
            for widget in _descendants(self.rail):
                if getattr(widget, '_shell_nav', False):
                    widget.configure(pady=NAV_PADY_SHORT if short else NAV_PADY)
            # The tagline and version line are the first to go, the same on every tab.
            for widget, options in self._short_hidden:
                try:
                    if short:
                        widget.pack_forget()
                    else:
                        widget.pack(**options)
                except tk.TclError:
                    pass
        if self._subtitle is None or (not short) == self._subtitle_shown:
            return
        self._subtitle_shown = not short
        if self._subtitle_shown:
            self._subtitle.pack(fill='x', pady=(2, 0))
        else:
            self._subtitle.pack_forget()

    def set_rail_width(self, width):
        if int(self.rail_shell.cget('width')) == int(width):
            return
        self.rail_shell.configure(width=width)
        narrow = width < self.rail_width
        if self._logo is not None:
            canvas, draw = self._logo
            canvas.configure(width=width - 2 * RAIL_PADX)
            canvas.delete('all')
            draw(canvas)
        if self._brand_title is not None:
            size, weight = TYPE['brand']
            self._brand_title.configure(font=(FAMILY, size - 4 if narrow else size, weight))
        for lab in self._wrapped:
            try:
                lab.configure(wraplength=width - 2 * RAIL_PADX)
            except tk.TclError:
                pass

    def rail_text(self, text, role='small', colour='text_2'):
        """A paragraph in the rail that re-wraps when the rail narrows."""
        lab = label(self.rail, text, role, colour, justify='left',
                    wraplength=int(self.rail_shell.cget('width')) - 2 * RAIL_PADX)
        lab.pack(anchor='w', fill='x', padx=RAIL_PADX)
        self._wrapped.append(lab)
        return lab

    # ---- rail -----------------------------------------------------------
    def brand(self, name, tagline='', logo=None):
        """Wordmark and tagline. `logo(canvas)` may draw a mark beside the name."""
        top = ogl_frame(self.rail, bg=C['sidebar'])
        top.pack(fill='x', padx=RAIL_PADX, pady=(RAIL_TOP, 0))
        if logo is not None:
            canvas = tk.Canvas(top, width=self.rail_width - 2 * RAIL_PADX, height=40,
                               bg=C['sidebar'], highlightthickness=0, bd=0)
            canvas.pack(anchor='w')
            logo(canvas)
            self._logo = (canvas, logo)
            title = None
        else:
            title = label(top, name, 'brand', 'text_bright')
            title.pack(anchor='w')
            self._brand_title = title
        sub = label(top, tagline, 'group', 'text_3') if tagline else None
        if sub is not None:
            sub.pack(anchor='w', pady=(4, 0))
            self._short_hidden.append((sub, dict(anchor='w', pady=(4, 0))))
        return title, sub

    def group(self, text, parent=None, top=18):
        lab = label(parent or self.rail, text, 'group', 'text_3')
        lab.pack(anchor='w', fill='x', padx=RAIL_PADX, pady=(top, 6))
        return lab

    def nav_group(self, parent=None):
        box = ogl_frame(parent or self.rail, bg=C['sidebar'])
        box.pack(fill='x', padx=RAIL_PADX - 4)
        return box

    def rail_bottom(self):
        """The area fixed to the foot of the rail (packed before anything that expands)."""
        if self._rail_bottom is None:
            self._rail_bottom = ogl_frame(self.rail, bg=C['sidebar'])
            self._rail_bottom.pack(side='bottom', fill='x', padx=RAIL_PADX, pady=(8, 14))
        return self._rail_bottom

    def home(self, on_home, version_text=''):
        """HOME and the version line, always at the foot of the rail."""
        bottom = self.rail_bottom()
        btn = button(bottom, HOME_LABEL, on_home)
        btn.pack(fill='x')
        version = None
        if version_text:
            version = label(bottom, version_text, 'small', 'text_3')
            version.pack(anchor='w', pady=(8, 0))
            self._short_hidden.append((version, dict(anchor='w', pady=(8, 0))))
        return btn, version

    # ---- main -----------------------------------------------------------
    def header(self, title, subtitle='', parent=None):
        """Page title, optional subtitle, and a right-hand slot (returned) for a chip or actions."""
        head = ogl_frame(parent or self.main, bg=C['canvas'])
        head.pack(fill='x', padx=MAIN_PADX, pady=HEADER_PADY)
        row = ogl_frame(head, bg=C['canvas'])
        row.pack(fill='x')
        right = ogl_frame(row, bg=C['canvas'])
        right.pack(side='right', anchor='n')
        title_label = label(row, title, 'page_title', 'text_bright', anchor='w')
        title_label.pack(side='left', fill='x', expand=True)
        sub = label(head, subtitle, 'subtitle', 'text_2', anchor='w', justify='left') if subtitle is not None else None
        if sub is not None:
            # One line that fits the page: shortened with "…" (full text on
            # hover) instead of running off the right edge (0.4.9.7).
            from oracle_widgets import ellipsize
            ellipsize(sub)
            sub.pack(fill='x', pady=(2, 0))
            if parent is None:
                self._subtitle = sub
        return title_label, sub, right

    def status(self, parent=None, **kwargs):
        """The status line at the foot of the main area (packed from the bottom first)."""
        foot = ogl_frame(parent or self.main, bg=C['canvas'])
        foot.pack(side='bottom', fill='x', padx=MAIN_PADX, pady=(0, 10))
        line = label(foot, '', 'status', 'text_2', anchor='w', justify='left', **kwargs)
        line.pack(fill='x')
        return line


def chip(parent, text, *, accent=True):
    """A small state badge (READY, RUNNING, ~44 BITS)."""
    return ogl_label(parent, text=text, bg=C['accent_soft'] if accent else C['raised'],
                     fg=C['accent'] if accent else C['text_2'], font=font('group'), padx=12, pady=4)
