"""Reusable widgets shared by the player and converter screens."""
from __future__ import annotations

import sys
import tkinter as tk
from tkinter import ttk
from typing import Callable, Iterable, Sequence

from .selection import bind_track_selection
from .theme import PALETTE


class TrackTable(ttk.Frame):
    """A Treeview with a slim scrollbar, standard multi-selection and an empty-state hint.

    ``columns`` is a sequence of ``(key, heading, width, stretch, anchor)``.
    Ctrl+A, Ctrl+click, Shift+click and Ctrl+Shift+click are bound by
    :func:`bind_track_selection`; double-click / Enter call ``on_activate``.
    """

    def __init__(self, parent, columns: Sequence[tuple], *, empty_text: str = '',
                 on_activate: Callable[[], None] | None = None,
                 on_context: Callable[[tk.Event], None] | None = None,
                 horizontal_scroll: bool = False, style: str = 'Treeview'):
        super().__init__(parent)          # v1.9.0: the table draws its own rounded field
        keys = [c[0] for c in columns]
        self.tree = ttk.Treeview(self, columns=keys, show='headings', selectmode='extended', style=style)
        for key, heading, width, stretch, anchor in columns:
            self.tree.heading(key, text=heading.upper(), anchor=anchor)   # 2.0: label style
            self.tree.column(key, width=width, minwidth=min(width, 40), stretch=stretch, anchor=anchor)
        yscroll = ttk.Scrollbar(self, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=yscroll.set)
        self.tree.grid(row=0, column=0, sticky='nsew')
        yscroll.grid(row=0, column=1, sticky='ns')
        if horizontal_scroll:
            xscroll = ttk.Scrollbar(self, orient='horizontal', command=self.tree.xview)
            self.tree.configure(xscrollcommand=xscroll.set)
            xscroll.grid(row=1, column=0, sticky='ew')
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.tree.tag_configure('odd', background=PALETTE['row_alt'])
        self.tree.tag_configure('playing', foreground=PALETTE['accent'], font='OgListBold')
        bind_track_selection(self.tree)
        self._empty = tk.Label(self, text=empty_text, justify='center', font='OgBody',
                               background=PALETTE['table'], foreground=PALETTE['muted'])
        self._on_activate = on_activate
        if on_activate is not None:
            self.tree.bind('<Double-1>', self._double_click)
            self.tree.bind('<Return>', lambda _e: (on_activate(), 'break')[1])
        if on_context is not None:
            # Right-click; macOS Tk reports the secondary button as Button-2.
            buttons = ('<Button-3>', '<Button-2>') if sys.platform == 'darwin' else ('<Button-3>',)
            for button in buttons:
                self.tree.bind(button, lambda event: self._context(event, on_context))
            for key in ('<Shift-F10>', '<KeyPress-App>', '<KeyPress-Menu>'):
                try:  # Context-menu key: 'App' on Windows, 'Menu' on X11.
                    self.tree.bind(key, lambda event: self._context(event, on_context))
                except tk.TclError:
                    pass

    def _double_click(self, event) -> str | None:
        if self.tree.identify_region(event.x, event.y) in ('heading', 'separator'):
            return None
        if self.tree.identify_row(event.y) and self._on_activate is not None:
            self._on_activate()
            return 'break'
        return None

    def _context(self, event, callback) -> str:
        from_keyboard = str(getattr(event, 'type', '')) in ('2', 'KeyPress')
        row = '' if from_keyboard else self.tree.identify_row(event.y)
        if row and row not in self.tree.selection():
            self.tree.selection_set((row,))
            self.tree.focus(row)
        callback(event)
        return 'break'

    def set_empty_text(self, text: str) -> None:
        self._empty.configure(text=text)
        self._update_empty()

    def _update_empty(self) -> None:
        if self.tree.get_children('') or not self._empty.cget('text'):
            self._empty.place_forget()
        else:
            self._empty.place(relx=0.5, rely=0.45, anchor='center')

    def set_rows(self, rows: Iterable[tuple[str, tuple, tuple]]) -> None:
        """Replace all rows: iterable of (iid, values, tags). Keeps the selection where possible."""
        previous = set(self.tree.selection())
        self.tree.delete(*self.tree.get_children(''))
        keep = []
        for index, (iid, values, tags) in enumerate(rows):
            self.tree.insert('', 'end', iid=iid, values=values,
                             tags=tuple(tags) + (('odd',) if index % 2 else ()))
            if iid in previous:
                keep.append(iid)
        if keep:
            self.tree.selection_set(keep)
        self._update_empty()

    def selection(self) -> tuple[str, ...]:
        return self.tree.selection()


class Chip(ttk.Label):
    """A clickable, grained status counter: '●  Ready  12'. Active filter = 'selected' state."""

    def __init__(self, parent, label: str, colour: str, command: Callable[[], None] | None = None):
        style = f'{label.replace(" ", "")}.Chip.TLabel'
        ttk.Style(parent).configure(style, foreground=colour)
        super().__init__(parent, text='', style=style, cursor='hand2' if command else '')
        self.label = label
        self.colour = colour
        self.compact = False
        if command is not None:
            self.bind('<Button-1>', lambda _e: command())
            self.bind('<Enter>', lambda _e: self.state(['active']))
            self.bind('<Leave>', lambda _e: self.state(['!active']))

    def set(self, count: int, active: bool = False) -> None:
        short = {'Completed': 'Done', 'Needs review': 'Review', 'Skipped': 'Skip'}
        name = short.get(self.label, self.label) if self.compact else self.label
        self.configure(text=f'●  {name}  {count}')
        self.state(['selected'] if active else ['!selected'])


class GradientRule(tk.Canvas):
    """A thin horizontal amber → reddish-orange line that redraws to its width."""

    def __init__(self, parent, stops: tuple[str, ...], height: int = 2):
        super().__init__(parent, height=height, highlightthickness=0, borderwidth=0, background=stops[-1])
        self._stops = stops
        self._shift = 0.0                     # v1.8.9: follows the gradient drift
        self._cells: list[tuple[int, int]] = []
        self.bind('<Configure>', self._draw)
        anim = getattr(self.winfo_toplevel(), '_og_anim', None)
        if anim is not None:
            anim.on_frame(self.set_shift)

    def _colour(self, f: float) -> str:
        from .textures import _stop_colour, drift
        return '#%02X%02X%02X' % _stop_colour(self._stops, drift(f, self._shift))

    def _draw(self, event=None) -> None:
        self.delete('all')
        width = max(1, self.winfo_width())
        height = int(self.cget('height'))
        step = max(1, width // 256)
        self._cells = []
        for x in range(0, width, step):
            item = self.create_rectangle(x, 0, x + step, height, fill=self._colour(x / max(1, width - 1)), width=0)
            self._cells.append((item, x))

    def set_shift(self, shift: float) -> None:
        """Recolour the existing strips for a new drift position (no redraw of the shapes)."""
        self._shift = shift
        width = max(1, self.winfo_width())
        for item, x in self._cells:
            self.itemconfigure(item, fill=self._colour(x / max(1, width - 1)))


def section_label(parent, text: str, card: bool = False) -> ttk.Label:
    return ttk.Label(parent, text=text.upper(), style='CardSection.TLabel' if card else 'Section.TLabel')


class Swatch(tk.Label):
    """v1.9.0: a clickable colour swatch with rounded, bevelled corners.

    Takes the same calls as the square tk.Button it replaces: ``configure(background=...)``
    shows a new colour, ``configure(state='disabled')`` dims it and ignores clicks.
    """

    SIZE = (34, 26)

    def __init__(self, parent, command: Callable[[], None] | None = None, behind: str | None = None):
        self._behind = behind or PALETTE['bg']
        super().__init__(parent, background=self._behind, borderwidth=0, highlightthickness=0, cursor='hand2')
        self._command = command
        self._colour = '#808080'
        self._enabled = True
        self._photo = None
        self.bind('<Button-1>', lambda _e: self._command() if (self._enabled and self._command) else None)
        self._render()

    def _render(self) -> None:
        try:
            from PIL import ImageTk
            from . import textures
            fill = self._colour if self._enabled else '#4A3E36'
            image = textures.surface(self.SIZE, fill, fill, behind=self._behind, radius=2, outline=PALETTE['button_border'],
                                     edge=0, amount=0.0, bevel=0.20)
            self._photo = ImageTk.PhotoImage(image, master=self)
            super().configure(image=self._photo)
        except Exception:  # noqa: BLE001 - no Pillow: a plain coloured label
            super().configure(background=self._colour, width=3)

    def configure(self, cnf=None, **kw):
        changed = False
        for key in ('background', 'bg'):
            if key in kw:
                self._colour = kw.pop(key); changed = True
        kw.pop('activebackground', None)
        if 'state' in kw:
            self._enabled = str(kw.pop('state')) != 'disabled'
            super().configure(cursor='hand2' if self._enabled else '')
            changed = True
        if 'command' in kw:
            self._command = kw.pop('command')
        result = super().configure(cnf, **kw) if (cnf or kw) else None
        if changed:
            self._render()
        return result

    config = configure
