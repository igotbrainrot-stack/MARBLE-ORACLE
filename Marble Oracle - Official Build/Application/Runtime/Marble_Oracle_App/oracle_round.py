"""Rounded corners for the suite's plain Tk widgets in Dark and Light (0.5.3).

Tk cannot round a widget. Buttons are RoundButtons and textured cards are rounded images (oracle_widgets,
oracle_ogg_texture); everything else with a visible edge (entry fields, lists, text boxes, dropdowns,
bordered panels, small badges) gets four corner pieces laid over its corners. Each piece is a tiny
anti-aliased picture: the surface behind outside the curve, the widget's border on the curve, its fill inside.

install(root) watches for such widgets as they are first shown (class bindings on <Map>), so widgets made later
(rebuilt charts, new rows) are rounded too. A light check every half second redraws the pieces of any widget
whose colours changed (keyboard focus, a toggle). Subtrees marked `_marble_no_round = True` (OVERCAST and
Oggcultist, which draw their own rounded artwork) are left alone.
"""
from __future__ import annotations

import tkinter as tk

import oracle_appearance

CLASSES = ('Entry', 'Listbox', 'Text', 'Spinbox', 'Menubutton', 'Label', 'Frame', 'Button', 'Canvas', 'TLabel')
RADIUS = {'Entry': 6, 'Listbox': 7, 'Text': 7, 'Spinbox': 6, 'Menubutton': 7, 'Label': 6, 'TLabel': 6,
          'Frame': 9, 'Button': 7, 'Canvas': 9}
POLL_MS = 500
_IMAGES = {}
_TRACKED = []        # [widget, pieces, signature]


def _hex(colour, widget=None):
    colour = str(colour)
    if not colour.startswith('#') and widget is not None:
        try:
            r, g, b = widget.winfo_rgb(colour)
            return (r // 256, g // 256, b // 256)
        except tk.TclError:
            return (0, 0, 0)
    colour = colour.lstrip('#')
    if len(colour) == 3:
        colour = ''.join(c * 2 for c in colour)
    return tuple(int(colour[i:i + 2], 16) for i in (0, 2, 4))


def corner_image(master, r, corner, outside, border, fill, thickness):
    """An r x r corner piece: `outside` beyond the curve, a `thickness` px `border` on it, `fill` inside."""
    key = (master.tk.interpaddr(), r, corner, outside, border, fill, thickness)
    image = _IMAGES.get(key)
    if image is not None:
        return image
    out, ring, inside = _hex(outside, master), _hex(border, master), _hex(fill, master)
    cx = r if corner in ('nw', 'sw') else 0
    cy = r if corner in ('nw', 'ne') else 0
    rows = []
    for y in range(r):
        row = []
        for x in range(r):
            a_out = a_ring = 0
            for sx, sy in ((0.25, 0.25), (0.75, 0.25), (0.25, 0.75), (0.75, 0.75)):
                d = ((x + sx - cx) ** 2 + (y + sy - cy) ** 2) ** 0.5
                if d > r:
                    a_out += 1
                elif d > r - thickness:
                    a_ring += 1
            a_in = 4 - a_out - a_ring
            colour = tuple(round((out[i] * a_out + ring[i] * a_ring + inside[i] * a_in) / 4) for i in range(3))
            row.append('#%02x%02x%02x' % colour)
        rows.append('{' + ' '.join(row) + '}')
    image = tk.PhotoImage(master=master, width=r, height=r)
    image.put(' '.join(rows), to=(0, 0))
    _IMAGES[key] = image
    return image


def _excluded(widget):
    while widget is not None:
        if getattr(widget, '_marble_no_round', False):
            return True
        widget = getattr(widget, 'master', None)
    return False


def _option(widget, name, default=None):
    try:
        return widget.cget(name)
    except (tk.TclError, AttributeError):
        return default


def _edge_pad(widget):
    import re
    padx = _option(widget, 'padx', None)
    if padx is None:                         # ttk: padding, a Tcl list such as "12 4"
        try:
            padx = widget.tk.call(widget._w, 'cget', '-padding')
        except tk.TclError:
            padx = 0
    numbers = re.findall(r'\d+(?:\.\d+)?', str(padx))
    return int(float(numbers[0])) if numbers else 0


def _signature(widget):
    """(radius, outside, border, fill, thickness) for the widget now, or None when it should not be rounded."""
    from oracle_ogg_texture import surface_colour
    kind = widget.winfo_class()
    if kind not in RADIUS or getattr(widget, '_marble_round_skip', False):
        return None
    from oracle_widgets import RoundButton, SlimScrollbar
    if isinstance(widget, (RoundButton, SlimScrollbar)):
        return None
    ground = surface_colour(widget.master, None)
    fill = surface_colour(widget, None)
    if ground is None or fill is None:
        return None
    thickness = int(_option(widget, 'highlightthickness', 0) or 0)
    has_focus = False
    try:
        has_focus = widget.focus_get() is widget
    except (tk.TclError, KeyError):
        pass
    border = _option(widget, 'highlightcolor' if has_focus else 'highlightbackground', fill) if thickness else fill
    differs = str(fill).upper() != str(ground).upper()
    edged = thickness > 0 and str(border).upper() != str(ground).upper()
    if kind in ('Frame', 'Canvas') and not edged:
        return None                          # plain containers keep their square edges
    if kind in ('Label', 'TLabel') and not (differs or edged):
        return None
    if kind in ('Label', 'Button') and widget.winfo_height() > 56:
        return None                          # badges and chips, not large areas
    if kind in ('Label', 'TLabel', 'Button') and str(_option(widget, 'anchor', 'center')) != 'center' \
            and _option(widget, 'text', '') and _edge_pad(widget) < 4:
        return None                          # text aligned to an edge would be covered by a corner
    if not (differs or edged):
        return None
    radius = RADIUS[kind]
    if min(widget.winfo_width(), widget.winfo_height()) < 2 * radius + 2:
        radius = max(3, min(widget.winfo_width(), widget.winfo_height()) // 2 - 1)
        if radius < 3:
            return None
    return (radius, str(ground), str(border), str(fill), min(thickness, 2))


def _apply(entry):
    widget, pieces, old = entry
    try:
        if not widget.winfo_exists() or not widget.winfo_ismapped():
            return
        sig = _signature(widget)
    except tk.TclError:
        return
    if sig == old:
        return
    entry[2] = sig
    if sig is None:
        for piece in pieces.values():
            piece.place_forget()
        return
    r, outside, border, fill, thickness = sig
    for corner, (relx, rely) in (('nw', (0, 0)), ('ne', (1, 0)), ('sw', (0, 1)), ('se', (1, 1))):
        piece = pieces.get(corner)
        if piece is None:
            piece = pieces[corner] = tk.Label(widget.master, bd=0, highlightthickness=0, padx=0, pady=0)
            piece._marble_round_skip = True
        piece.configure(image=corner_image(widget, r, corner, outside, border, fill, thickness), bg=outside)
        # bordermode outside: over the widget's own border, not inside it.
        piece.place(in_=widget, relx=relx, rely=rely, anchor=corner, bordermode='outside')
        piece.lift(widget)


def consider(widget):
    if not oracle_appearance.modern() or getattr(widget, '_marble_round_entry', None) is not None:
        return
    if getattr(widget, '_marble_round_skip', False) or _excluded(widget):
        return
    entry = [widget, {}, None]
    widget._marble_round_entry = entry
    _TRACKED.append(entry)
    widget.bind('<Destroy>', lambda _e, en=entry: _forget(en), add='+')
    widget.bind('<FocusIn>', lambda _e, en=entry: _apply(en), add='+')
    widget.bind('<FocusOut>', lambda _e, en=entry: _apply(en), add='+')
    widget.bind('<Configure>', lambda _e, en=entry: _apply(en), add='+')
    widget.after_idle(lambda en=entry: _apply(en))


def _forget(entry):
    if entry in _TRACKED:
        _TRACKED.remove(entry)
    for piece in entry[1].values():
        try:
            piece.destroy()
        except tk.TclError:
            pass


def _poll(root):
    for entry in list(_TRACKED):
        try:
            _apply(entry)
        except Exception:
            pass
    try:
        root._marble_round_after = root.after(POLL_MS, _poll, root)
    except tk.TclError:
        pass


def _stop(event, root):
    if event.widget is root:
        try:
            root.after_cancel(root._marble_round_after)
        except (tk.TclError, AttributeError, ValueError):
            pass


def install(root):
    """Round eligible widgets in this window as they appear (Dark and Light only)."""
    if not oracle_appearance.modern() or getattr(root, '_marble_round', False):
        return
    root._marble_round = True
    for kind in CLASSES:
        root.bind_class(kind, '<Map>', lambda e: consider(e.widget), add='+')
    root._marble_round_after = root.after(POLL_MS, _poll, root)
    root.bind('<Destroy>', lambda e: _stop(e, root), add='+')
