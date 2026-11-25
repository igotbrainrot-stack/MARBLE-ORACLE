"""Small Tk behaviours every workspace shares, so none of them clips its controls.

* flow(container, children)   a toolbar whose buttons wrap to a second row when
                              the window is too narrow, instead of running off
                              the right edge;
* wrap_to_parent(widget)      explanatory text that wraps to the width it is
                              given, instead of being cut mid-sentence;
* install_interaction_defaults(root)
                              one hover, keyboard-focus and disabled look for
                              every control in the window;
* tooltip(widget, text)       the full text of anything that had to be shortened.

Both are driven by the container's real width, so they hold at any window
size and font scaling. The arithmetic lives in oracle_design.flow_layout.
"""
from __future__ import annotations

import tkinter as tk

from oracle_design import COLOR, WrapSettler, flow_layout, hover_tint


def flow(container, children, gap_x=7, gap_y=6):
    """Lay `children` (already created inside `container`) out as a wrapping row.

    The container must not also pack or grid children of its own. Returns the
    function that re-flows, for callers that change a child's size later.
    """
    children = list(children)
    state = {'signature': None}

    def reflow(_event=None):
        try:
            width = container.winfo_width()
            if width <= 1:                                   # not laid out yet: assume one row
                width = sum(child.winfo_reqwidth() + gap_x for child in children)
            sizes = [(child.winfo_reqwidth(), child.winfo_reqheight()) for child in children]
        except tk.TclError:                                  # the workspace is closing
            return
        positions, height = flow_layout(sizes, width, gap_x, gap_y)
        signature = (tuple(positions), height)
        if signature == state['signature']:
            return
        state['signature'] = signature
        for child, (x, y) in zip(children, positions):
            child.place(x=x, y=y)
        container.configure(height=max(1, height))

    container.bind('<Configure>', reflow, add='+')
    for child in children:
        child.bind('<Configure>', reflow, add='+')
    reflow()
    return reflow


def wrap_to_parent(widget, margin=0, minimum=120):
    """Keep `widget`'s text wrapped to its parent's width (less `margin`).

    The width is chosen by oracle_design.WrapSettler, so a container whose own
    width depends on this text cannot bounce between two widths for ever.
    """
    parent = widget.master
    settler = WrapSettler()

    def rewrap(_event=None):
        try:
            if parent.winfo_width() <= 1:                    # not laid out yet
                return
            width = settler.next(max(minimum, parent.winfo_width() - margin))
            if width is not None:
                widget.configure(wraplength=width, justify='left')
        except tk.TclError:                                  # the workspace is closing
            pass

    parent.bind('<Configure>', rewrap, add='+')
    return widget


def install_interaction_defaults(root):
    """One hover, focus and disabled treatment for every control in the window.

    * Hover: a button under the pointer lightens slightly (oracle_design.hover_tint).
      Tk only does this by itself on Linux; on Windows buttons gave no feedback.
    * Keyboard focus: the control that has focus gets an accent outline. The
      default outline was black on near-black, so Tab moved an invisible focus.
    * Disabled: disabled captions use the suite's tertiary text colour.

    Installed once per window; controls that set these options themselves keep
    their own. Safe to call again.
    """
    if getattr(root, '_oracle_interaction_defaults', False):
        return
    root._oracle_interaction_defaults = True
    accent, muted = COLOR['focus'], COLOR['text_3']
    for pattern in ('*Button.highlightColor', '*Entry.highlightColor', '*Listbox.highlightColor',
                    '*Text.highlightColor', '*Checkbutton.highlightColor', '*Menubutton.highlightColor',
                    '*Scale.highlightColor'):
        root.option_add(pattern, accent, 'startupFile')
    root.option_add('*Button.disabledForeground', muted, 'startupFile')

    def enter(event):
        button = event.widget
        try:
            if str(button.cget('state')) == 'disabled':
                return
            resting = str(button.cget('bg'))
            hovered = hover_tint(resting)
            if hovered != resting:
                button._oracle_hover = (resting, hovered)
                button.configure(bg=hovered)
        except (tk.TclError, AttributeError):
            pass

    def leave(event):
        button = event.widget
        try:
            resting, hovered = getattr(button, '_oracle_hover', (None, None))
            button._oracle_hover = (None, None)
            # Restore only what hover itself set: a click may have changed the colour meanwhile.
            if resting and str(button.cget('bg')).upper() == str(hovered).upper():
                button.configure(bg=resting)
        except (tk.TclError, AttributeError):
            pass

    root.bind_class('Button', '<Enter>', enter, add='+')
    root.bind_class('Button', '<Leave>', leave, add='+')


def tooltip(widget, text, delay_ms=450):
    """Show `text` in a small panel beside the pointer while it rests on `widget`.

    `text` is a string or a function of the pointer event returning one; an
    empty result shows nothing, so a caller can offer a tip only when its
    caption had to be shortened. The panel never takes focus and goes away on
    leave, click, key press or when the widget is destroyed.
    """
    state = {'after': None, 'panel': None, 'shown': None}

    def resolve(event):
        try:
            return (text(event) if callable(text) else text) or ''
        except Exception:
            return ''

    def hide(_event=None):
        if state['after'] is not None:
            try:
                widget.after_cancel(state['after'])
            except tk.TclError:
                pass
            state['after'] = None
        if state['panel'] is not None:
            try:
                state['panel'].destroy()
            except tk.TclError:
                pass
            state['panel'] = None
        state['shown'] = None

    def show(message, x, y):
        state['after'] = None
        try:
            panel = tk.Toplevel(widget)
            panel.wm_overrideredirect(True)
            panel.configure(bg=COLOR['control_line'])
            tk.Label(panel, text=message, justify='left', wraplength=420, bg=COLOR['raised'], fg=COLOR['text'],
                     font=widget.cget('font') if 'font' in widget.keys() else None, padx=8, pady=5).pack(padx=1, pady=1)
            panel.update_idletasks()
            x = max(0, min(x + 14, widget.winfo_screenwidth() - panel.winfo_reqwidth() - 4))
            y = max(0, min(y + 18, widget.winfo_screenheight() - panel.winfo_reqheight() - 4))
            panel.wm_geometry(f'+{x}+{y}')
            state['panel'], state['shown'] = panel, message
        except tk.TclError:
            hide()

    def moved(event):
        message = resolve(event)
        if message == state['shown']:
            return
        hide()
        if message:
            state['after'] = widget.after(delay_ms, lambda: show(message, event.x_root, event.y_root))

    widget.bind('<Enter>', moved, add='+')
    widget.bind('<Motion>', moved, add='+')
    for sequence in ('<Leave>', '<ButtonPress>', '<KeyPress>', '<Destroy>'):
        widget.bind(sequence, hide, add='+')
    return widget


def ellipsize(label, margin=0):
    """Keep `label` on one line: its text is shortened with "…" to the width it has.

    The full text is kept, shown on hover when it had to be shortened, and the
    label refits when its width or its text changes. Later calls to
    `label.configure(text=…)` set the full text, so callers need not know.
    """
    from tkinter import font as tkfont
    measure = tkfont.Font(font=label.cget('font')).measure
    original_configure = label.configure
    label._full_text = str(label.cget('text'))

    def fitted(text, width):
        if width <= 1 or measure(text) <= width:
            return text
        cut = text
        while len(cut) > 1 and measure(cut.rstrip() + '…') > width:
            cut = cut[:-1]
        return cut.rstrip() + '…'

    def refit(_event=None):
        try:
            width = label.winfo_width() - margin
            text = fitted(label._full_text, width)
            if str(label.cget('text')) != text:
                original_configure(text=text)
        except tk.TclError:                       # the workspace is closing
            pass

    def configure(cnf=None, **kw):
        if cnf is None and not kw:
            return original_configure()           # a query: all options, unchanged behaviour
        if isinstance(cnf, str):
            return original_configure(cnf)        # a query for one option
        if isinstance(cnf, dict) and 'text' in cnf:
            cnf = dict(cnf)
            label._full_text = str(cnf.pop('text'))
        if 'text' in kw:
            label._full_text = str(kw.pop('text'))
        result = original_configure(cnf, **kw) if (cnf or kw) else None
        refit()
        return result

    label.configure = label.config = configure
    label.bind('<Configure>', refit, add='+')
    tooltip(label, lambda _e: label._full_text if str(label.cget('text')) != label._full_text else '')
    refit()
    return label


class SlimScrollbar(tk.Canvas):
    """A thin, dark scrollbar in the suite's colours; a drop-in for tk.Scrollbar.

    Tk's own scrollbar is a grey bar with arrow buttons from another decade.
    This one is a 10 px track with a thumb that appears only when there is
    something to scroll, lightens under the pointer and turns amber while
    dragged. Click the track to move a page; the mouse wheel over it scrolls.
    It speaks the same protocol as tk.Scrollbar: pass `command=widget.yview`
    (or xview) and give the widget `yscrollcommand=bar.set`.
    """
    MIN_THUMB = 28

    def __init__(self, master, orient='vertical', command=None, width=10, **kwargs):
        try:
            background = kwargs.pop('bg', None) or kwargs.pop('background', None) or master.cget('bg')
        except (tk.TclError, AttributeError):
            background = COLOR['canvas']
        self._vertical = str(orient).startswith('v')
        # Ask for almost nothing along its length (a Tk canvas otherwise asks for ~270 px
        # and squeezes what it scrolls); it is stretched to fit with fill='y' / 'x'.
        size = {'width': width, 'height': 24} if self._vertical else {'height': width, 'width': 24}
        super().__init__(master, bg=background, highlightthickness=0, bd=0, cursor='arrow', **size, **kwargs)
        self._command = command
        self._first, self._last = 0.0, 1.0
        self._hover = self._drag = False
        self._grab = 0.0
        self._thumb = None
        self.bind('<Configure>', lambda _e: self._draw(), add='+')
        self.bind('<Enter>', lambda _e: self._set_hover(True), add='+')
        self.bind('<Leave>', lambda _e: self._set_hover(False), add='+')
        self.bind('<ButtonPress-1>', self._press, add='+')
        self.bind('<B1-Motion>', self._motion, add='+')
        self.bind('<ButtonRelease-1>', self._release, add='+')
        for sequence in ('<MouseWheel>', '<Button-4>', '<Button-5>'):
            self.bind(sequence, self._wheel, add='+')

    # -- the tk.Scrollbar protocol ------------------------------------------
    def set(self, first, last):
        self._first, self._last = max(0.0, float(first)), min(1.0, float(last))
        self._draw()

    def get(self):
        return self._first, self._last

    def configure(self, cnf=None, **kwargs):
        if isinstance(cnf, dict):
            kwargs = {**cnf, **kwargs}
            cnf = None
        if 'command' in kwargs:
            self._command = kwargs.pop('command')
        kwargs.pop('orient', None)
        kwargs.pop('troughcolor', None)
        if cnf is None and not kwargs:
            return None
        return super().configure(cnf, **kwargs)

    config = configure

    # -- drawing ------------------------------------------------------------
    def _length(self):
        return max(1, self.winfo_height() if self._vertical else self.winfo_width())

    def _span(self):
        length = self._length()
        start = self._first * length
        end = max(start + self.MIN_THUMB, self._last * length) if self._last - self._first < 1 else length
        if end > length:
            start, end = max(0, length - (end - start)), length
        return start, end

    def _draw(self):
        self.delete('thumb')
        self._thumb = None
        if self._first <= 0.0 and self._last >= 1.0:
            return                                    # nothing to scroll: a quiet track
        start, end = self._span()
        colour = COLOR['accent'] if self._drag else (COLOR['text_3'] if self._hover else COLOR['control_line'])
        thickness = self.winfo_width() if self._vertical else self.winfo_height()
        inset = 2 if self._hover or self._drag else 3
        if self._vertical:
            box = (inset, start + 2, thickness - inset, end - 2)
        else:
            box = (start + 2, inset, end - 2, thickness - inset)
        self._thumb = self.create_rectangle(*box, fill=colour, outline=colour, tags='thumb')

    def _set_hover(self, on):
        self._hover = on
        self._draw()

    # -- input --------------------------------------------------------------
    def _position(self, event):
        return event.y if self._vertical else event.x

    def _press(self, event):
        if self._command is None or (self._first <= 0.0 and self._last >= 1.0):
            return
        start, end = self._span()
        at = self._position(event)
        if start <= at <= end:
            self._drag = True
            self._grab = at - start
            self._draw()
        else:
            self._command('scroll', -1 if at < start else 1, 'pages')

    def _motion(self, event):
        if not self._drag or self._command is None:
            return
        length = self._length()
        self._command('moveto', max(0.0, min(1.0, (self._position(event) - self._grab) / length)))

    def _release(self, _event):
        if self._drag:
            self._drag = False
            self._draw()

    def _wheel(self, event):
        if self._command is None:
            return
        up = getattr(event, 'num', None) == 4 or getattr(event, 'delta', 0) > 0
        self._command('scroll', -3 if up else 3, 'units')


_CHEVRONS = {}
# Images whose Tk has gone are kept here instead of being freed: Python may run
# an image's destructor on a worker thread, which Tk refuses with
# "main thread is not in main loop". They are a few bytes each.
_RETIRED_IMAGES = []


def _chevron(widget, colour):
    """A small downward chevron image (cached per window and colour)."""
    # Keyed by the Tk instance, not the window name: a later Tk() reuses the
    # name "." but not the images of an interpreter that has gone.
    key = (widget.tk.interpaddr(), colour)
    image = _CHEVRONS.get(key)
    try:
        alive = image is not None and str(image) in widget.tk.splitlist(widget.tk.call('image', 'names'))
    except tk.TclError:
        alive = False
    if not alive:
        if image is not None:
            _RETIRED_IMAGES.append(image)
        image = tk.PhotoImage(master=widget, width=11, height=7)
        points = [(x, y) for y in range(5) for x in (y, y + 1, 9 - y, 10 - y)]
        for x, y in points:
            image.put(colour, to=(x, y + 1))
        _CHEVRONS[key] = image
    return image


def style_dropdown(menu_button, *, bg=None, fg=None, hover=None, line=None, font=None, menu_bg=None):
    """One look for every dropdown (tk.OptionMenu) in the suite.

    Replaces Tk's Motif indicator bar with a drawn chevron on the right, gives
    the button a 1 px outline that turns into the cream focus ring on keyboard
    focus, and styles the pop-up list to match. Colours default to the suite
    tokens; AUGURSPEX passes its GRADE palette instead.
    """
    bg = bg or COLOR['control']
    fg = fg or COLOR['text']
    hover = hover or COLOR['hover']
    line = line or COLOR['control_line']
    options = dict(bg=bg, fg=fg, activebackground=hover, activeforeground=fg, relief='flat', bd=0,
                   indicatoron=False, anchor='w', padx=10, pady=4, highlightthickness=1,
                   highlightbackground=line, highlightcolor=COLOR['focus'], takefocus=True,
                   image=_chevron(menu_button, COLOR['text_2']), compound='right', cursor='hand2')
    if font is not None:
        options['font'] = font
    menu_button.configure(**options)
    menu = menu_button['menu']
    menu_options = dict(bg=menu_bg or COLOR['raised'], fg=fg, activebackground=COLOR['accent_soft'],
                        activeforeground=COLOR['text_bright'], relief='flat', bd=1, activeborderwidth=0)
    if font is not None:
        menu_options['font'] = font
    menu.configure(**menu_options)
    # Space or Enter on a focused dropdown opens it, as a button would.
    def open_menu(_event=None):
        try:
            x = menu_button.winfo_rootx()
            y = menu_button.winfo_rooty() + menu_button.winfo_height()
            menu.tk_popup(x, y)
        finally:
            try:
                menu.grab_release()
            except tk.TclError:
                pass
        return 'break'
    menu_button.bind('<space>', open_menu, add='+')
    menu_button.bind('<Return>', open_menu, add='+')

    # A dropdown that sizes to its text keeps the chevron straight after it.
    # One stretched across a column gets the chevron pinned to its right edge
    # instead, where people look for it.
    chevron = options['image']
    pin = tk.Label(menu_button, image=chevron, bg=bg, bd=0, cursor='hand2')
    pin.bind('<Button-1>', open_menu, add='+')
    state = {'stretched': None}

    def fit(_event=None):
        try:
            stretched = menu_button.winfo_width() > menu_button.winfo_reqwidth() + 8
            if stretched == state['stretched']:
                return
            state['stretched'] = stretched
            if stretched:
                menu_button.configure(image='', compound='none')
                pin.place(relx=1.0, rely=0.5, x=-10, anchor='e')
            else:
                pin.place_forget()
                menu_button.configure(image=chevron, compound='right')
        except tk.TclError:
            pass

    def shade(active):
        try:
            pin.configure(bg=menu_button.cget('activebackground' if active else 'bg'))
        except tk.TclError:
            pass

    menu_button.bind('<Configure>', fit, add='+')
    menu_button.bind('<Enter>', lambda _e: shade(True), add='+')
    menu_button.bind('<Leave>', lambda _e: shade(False), add='+')
    return menu_button


# ---- rounded controls (0.5.3, Dark / Light) ------------------------------------------------------
_ROUND_IMAGES = {}       # (interp, w, h, r, fill, ground, ring, ring_w) -> PhotoImage, kept for the process


def _hex(colour, widget=None):
    """(r, g, b) 0..255 for '#rrggbb', '#rgb' or, given a widget, any colour name Tk knows."""
    text = str(colour).strip()
    digits = text.lstrip('#')
    try:
        if text.startswith('#') and len(digits) == 6:
            return tuple(int(digits[i:i + 2], 16) for i in (0, 2, 4))
        if text.startswith('#') and len(digits) == 3:
            return tuple(int(c * 2, 16) for c in digits)
    except ValueError:
        pass
    if widget is not None:
        return tuple(v // 257 for v in widget.winfo_rgb(text))
    raise ValueError(f'not a colour: {colour!r}')


def rounded_photo(widget, w, h, radius, fill, ground, ring=None, ring_width=2):
    """An anti-aliased rounded rectangle, `fill` on `ground`, with an optional inner `ring` (the focus ring)."""
    w, h = max(2, int(w)), max(2, int(h))
    r = max(0, min(int(radius), w // 2, h // 2))
    key = (widget.tk.interpaddr(), w, h, r, str(fill).upper(), str(ground).upper(), ring and str(ring).upper(),
           ring_width)
    image = _ROUND_IMAGES.get(key)
    if image is not None:
        return image
    fc, gc = _hex(fill, widget), _hex(ground, widget)
    rc = _hex(ring, widget) if ring else None

    def coverage(x, y, inset):
        """Share (0..1) of pixel (x, y) inside the rounded rectangle inset by `inset` px (4 samples)."""
        rr = max(0.0, r - inset)
        x0, y0, x1, y1 = inset, inset, w - inset, h - inset
        inside = 0
        for sx, sy in ((0.25, 0.25), (0.75, 0.25), (0.25, 0.75), (0.75, 0.75)):
            px, py = x + sx, y + sy
            if not (x0 <= px <= x1 and y0 <= py <= y1):
                continue
            cx = min(max(px, x0 + rr), x1 - rr)
            cy = min(max(py, y0 + rr), y1 - rr)
            if (px - cx) ** 2 + (py - cy) ** 2 <= rr * rr:
                inside += 1
        return inside / 4.0

    def blend(a, b, t):
        return tuple(round(a[i] * (1 - t) + b[i] * t) for i in range(3))

    # The shape is mirror-symmetric and straight between the corners, so a pixel's colour depends only on
    # its distance from the nearest edge on each axis (or "in the middle"): work out that small table once.
    corner = min(max(r + 2, ring_width + 2), w // 2, h // 2)

    def colour_at(x, y):
        outer = coverage(x, y, 0)
        colour = blend(gc, fc, outer)
        if rc is not None:
            colour = blend(colour, rc, max(0.0, outer - coverage(x, y, ring_width)))
        return '#%02x%02x%02x' % colour

    # Index `corner` on either axis stands for every pixel between the two corner bands.
    table = [[colour_at(fx, fy) for fx in range(corner + 1)] for fy in range(corner + 1)]

    def row_for(fy):
        cells = table[fy]
        left = cells[:corner]
        middle = max(0, w - 2 * corner)
        return '{' + ' '.join(left + [cells[corner]] * middle + left[::-1]) + '}'

    band = [row_for(fy) for fy in range(corner)]
    rows = band + [row_for(corner)] * (h - 2 * corner) + band[::-1]
    image = tk.PhotoImage(master=widget, width=w, height=h)
    image.put(' '.join(rows), to=(0, 0))
    _ROUND_IMAGES[key] = image
    return image


class RoundButton(tk.Button):
    """A tk.Button with rounded corners: its face is an anti-aliased rounded image, its text drawn by Tk on top.

    It keeps the whole Button interface (command, invoke, state, keyboard, textvariable), and the colour
    options mean what they always did: configure(bg=...) recolours the face, cget('bg') returns it. The face
    redraws on hover (the suite's shared hover sets bg), press, focus and when disabled, and stretches when a
    geometry manager gives the button more room than it asks for. Text anchored left ('w') stays left.
    """

    _OWN = ('bg', 'background', 'fg', 'foreground', 'activebackground', 'activeforeground', 'text', 'font',
            'width', 'padx', 'pady', 'state', 'anchor', 'highlightbackground', 'highlightcolor',
            'highlightthickness', 'disabledforeground', 'radius', 'ground')

    def __init__(self, master=None, radius=8, ground=None, **kw):
        try:
            parent_bg = master.cget('bg')
        except (tk.TclError, AttributeError):
            parent_bg = COLOR['canvas']
        self._o = {'bg': kw.pop('bg', kw.pop('background', COLOR['control'])),
                   'fg': kw.pop('fg', kw.pop('foreground', COLOR['text'])),
                   'activebackground': kw.pop('activebackground', None),
                   'activeforeground': kw.pop('activeforeground', None),
                   'text': kw.pop('text', ''), 'font': kw.pop('font', 'TkDefaultFont'),
                   'width': kw.pop('width', 0) or 0, 'padx': kw.pop('padx', 12), 'pady': kw.pop('pady', 6),
                   'state': kw.pop('state', 'normal'), 'anchor': kw.pop('anchor', 'center'),
                   'highlightbackground': kw.pop('highlightbackground', parent_bg),
                   'highlightcolor': kw.pop('highlightcolor', COLOR['focus']),
                   'highlightthickness': kw.pop('highlightthickness', 2),
                   'disabledforeground': kw.pop('disabledforeground', COLOR['text_3']),
                   'radius': radius, 'ground': ground or parent_bg}
        kw.pop('relief', None)
        kw.pop('bd', None)
        kw.pop('borderwidth', None)
        kw.pop('justify', None)
        super().__init__(master, relief='flat', bd=0, highlightthickness=0, compound='center', padx=0, pady=0,
                         **kw)
        self._pressed = self._focused = False
        self._size = None
        self.bind('<ButtonPress-1>', lambda _e: self._press(True), add='+')
        self.bind('<ButtonRelease-1>', lambda _e: self._press(False), add='+')
        self.bind('<FocusIn>', lambda _e: self._focus(True), add='+')
        self.bind('<FocusOut>', lambda _e: self._focus(False), add='+')
        self.bind('<Configure>', self._resized, add='+')
        self._render()

    # -- options
    def configure(self, cnf=None, **kw):
        if cnf:
            kw = {**cnf, **kw}
        if not kw:
            return super().configure()
        mine = {k: kw.pop(k) for k in list(kw) if k in self._OWN}
        if 'background' in mine:
            mine['bg'] = mine.pop('background')
        if 'foreground' in mine:
            mine['fg'] = mine.pop('foreground')
        self._o.update(mine)
        result = super().configure(**kw) if kw else None
        if mine:
            self._render()
        return result

    config = configure

    def cget(self, key):
        key = {'background': 'bg', 'foreground': 'fg'}.get(key, key)
        if key in self._o:
            return self._o[key]
        return super().cget(key)

    __getitem__ = cget

    def __setitem__(self, key, value):
        self.configure(**{key: value})

    # -- states
    def _press(self, down):
        if str(self._o['state']) != 'disabled':
            self._pressed = down
            self._render()

    def _focus(self, on):
        self._focused = on
        self._render()

    def _resized(self, event):
        ex, ey = self._inset()
        face = (event.width - ex, event.height - ey)     # the room given, less Tk's own inset
        natural = self._natural()
        if (max(natural[0], face[0]), max(natural[1], face[1])) != self._size:
            self._render(stretch=face)

    # -- drawing
    def _font(self):
        from tkinter import font as tkfont
        try:
            return tkfont.Font(root=self, font=self._o['font'])
        except tk.TclError:
            return tkfont.nametofont('TkDefaultFont')

    def _natural(self):
        font = self._font()
        lines = str(self._o['text']).split('\n') or ['']
        text_w = max(font.measure(line) for line in lines)
        if self._o['width']:
            text_w = max(text_w, int(self._o['width']) * font.measure('0'))
        return (text_w + 2 * int(self._o['padx']) + 2, font.metrics('linespace') * len(lines) + 2 * int(self._o['pady']))

    def _render(self, stretch=None):
        o = self._o
        disabled = str(o['state']) == 'disabled'
        natural = w, h = self._natural()
        if stretch is None and self._size is not None:
            stretch = self._size
        if stretch:
            w, h = max(w, stretch[0]), max(h, stretch[1])
        fill = o['bg']
        if disabled:
            fill = _mix(o['bg'], o['ground'], 0.45, self)
        elif self._pressed:
            fill = _mix(o['activebackground'] or o['bg'], '#000000', 0.12, self)
        ring = o['highlightcolor'] if (self._focused and int(o['highlightthickness'] or 0) > 0) else None
        image = rounded_photo(self, w, h, o['radius'], fill, o['ground'], ring=ring)
        fg = o['disabledforeground'] if disabled else o['fg']
        text = str(o['text'])
        if o['anchor'] in ('w', 'nw', 'sw') and '\n' not in text:
            # Text is centred on the face; trailing spaces move it to the left edge (less padx).
            font = self._font()
            room = w - 2 * int(o['padx'])
            space = max(1, font.measure(' '))
            text = text + ' ' * max(0, int((room - font.measure(text)) / space))
        self._size = (w, h)
        super().configure(image=image, text=text, fg=fg, font=o['font'], bg=o['ground'],
                          activebackground=o['ground'], activeforeground=o['activeforeground'] or fg,
                          disabledforeground=o['disabledforeground'], state=o['state'],
                          width=natural[0], height=natural[1])
        # The button asks for its natural size whatever its face's size, so a face stretched to fill a grid
        # cell never feeds back into the layout (shared columns would otherwise keep resizing each other).
        self._image = image

    def _inset(self):
        """Pixels Tk adds round an image button's face (measured once: 1 px a side on X11)."""
        inset = getattr(self, '_inset_px', None)
        if inset is None:
            try:
                inset = (max(0, self.winfo_reqwidth() - int(super().cget('width'))),
                         max(0, self.winfo_reqheight() - int(super().cget('height'))))
            except (tk.TclError, ValueError):
                inset = (0, 0)
            self._inset_px = inset
        return inset


def _mix(a, b, t, widget=None):
    ca, cb = _hex(a, widget), _hex(b, widget)
    return '#%02X%02X%02X' % tuple(round(ca[i] * (1 - t) + cb[i] * t) for i in range(3))


def empty_hint(listbox, text, *, fg=None):
    """A quiet line centred in `listbox` while it has no rows ("No files yet. Use Open or Folder.") (0.5.4).

    An empty list read as a broken or unfinished panel. The hint is a label placed over the list; it is shown
    and hidden as rows are inserted and deleted (the list's own insert/delete are wrapped), and it passes
    clicks through to the list underneath."""
    hint = tk.Label(listbox, text=text, bg=listbox.cget('bg'), fg=fg or listbox.cget('fg'),
                    font=listbox.cget('font'), justify='center', wraplength=260)
    try:
        import oracle_appearance
        palette = oracle_appearance.palette()
        if fg is None and palette is not None:
            hint.configure(fg=palette['dim'])
    except Exception:
        pass
    hint._marble_round_skip = True

    def refresh(*_args):
        try:
            if listbox.size() == 0:
                hint.configure(wraplength=max(120, listbox.winfo_width() - 40))
                hint.place(relx=0.5, rely=0.5, anchor='center')
            else:
                hint.place_forget()
        except tk.TclError:
            pass
    insert, delete = listbox.insert, listbox.delete

    def wrapped_insert(*args, **kwargs):
        result = insert(*args, **kwargs)
        refresh()
        return result

    def wrapped_delete(*args, **kwargs):
        result = delete(*args, **kwargs)
        refresh()
        return result
    listbox.insert, listbox.delete = wrapped_insert, wrapped_delete
    hint.bind('<Button-1>', lambda _e: listbox.focus_set())
    listbox.bind('<Configure>', refresh, add='+')
    listbox.after_idle(refresh)
    listbox._empty_hint = hint
    return hint


class FlatSlider(tk.Canvas):
    """A modern horizontal slider for Dark and Light (0.5.4), standing in for tk.Scale.

    A rounded track, the filled part in the accent and a round thumb; click anywhere to jump there, drag to
    follow, arrow keys and the wheel to nudge. It keeps the parts of tk.Scale's interface the suite uses:
    from_/to, variable, command (called with the value as text, as tk.Scale does), get(), set(), cget() and
    configure() for from/to, and callers' own <ButtonPress-1>/<ButtonRelease-1> bindings (added with '+').
    """

    def __init__(self, master, from_=0.0, to=100.0, variable=None, command=None, length=160, *,
                 ground=None, track=None, fill=None, thumb=None, focus=None, resolution=1.0, height=20):
        super().__init__(master, width=length, height=height, highlightthickness=0, bd=0, takefocus=1,
                         cursor='hand2', bg=ground or master.cget('bg'))
        self._from, self._to, self._resolution = float(from_), float(to), float(resolution) or 1.0
        self.variable = variable if variable is not None else tk.DoubleVar(master=self, value=self._from)
        self.command = command
        self.colours = dict(track=track or '#48484A', fill=fill or '#FF9F0A', thumb=thumb or '#FFFFFF',
                            focus=focus or fill or '#FF9F0A')
        self._focus = False
        self._trace = self.variable.trace_add('write', lambda *_: self.redraw())
        self.bind('<ButtonPress-1>', self._pointer)
        self.bind('<B1-Motion>', self._pointer)
        self.bind('<Configure>', lambda _e: self.redraw())
        for key, step in (('<Left>', -1), ('<Down>', -1), ('<Right>', 1), ('<Up>', 1), ('<Button-5>', -1),
                          ('<Button-4>', 1)):
            self.bind(key, lambda _e, s=step: self._nudge(s))
        self.bind('<MouseWheel>', lambda e: self._nudge(1 if e.delta > 0 else -1))
        self.bind('<FocusIn>', lambda _e: self._set_focus(True))
        self.bind('<FocusOut>', lambda _e: self._set_focus(False))
        self.bind('<Destroy>', self._destroyed, add='+')

    # -- tk.Scale's interface
    def get(self):
        try:
            return float(self.variable.get())
        except (tk.TclError, ValueError):
            return self._from

    def set(self, value):
        low, high = sorted((self._from, self._to))
        value = max(low, min(high, float(value)))
        self.variable.set(int(round(value)) if isinstance(self.variable, tk.IntVar) else value)

    def cget(self, key):
        if key in ('from', 'from_'):
            return self._from
        if key == 'to':
            return self._to
        return super().cget(key)

    def configure(self, cnf=None, **kw):
        for key in ('from_', 'from'):
            if key in kw:
                self._from = float(kw.pop(key))
        if 'to' in kw:
            self._to = float(kw.pop('to'))
        if 'command' in kw:
            self.command = kw.pop('command')
        result = super().configure(cnf, **kw) if (cnf or kw) else None
        self.redraw()
        return result
    config = configure

    # -- behaviour
    def _value_at(self, x):
        pad = self._pad()
        span = max(1, self.winfo_width() - 2 * pad)
        t = min(1.0, max(0.0, (x - pad) / span))
        value = self._from + (self._to - self._from) * t
        return round(value / self._resolution) * self._resolution

    def _changed(self, value):
        self.set(value)
        if self.command is not None:
            self.command(str(self.get()))

    def _pointer(self, event):
        self.focus_set()
        self._changed(self._value_at(event.x))

    def _nudge(self, step):
        span = abs(self._to - self._from) or 1
        self._changed(self.get() + step * max(self._resolution, span / 50) * (1 if self._to >= self._from else -1))

    def _set_focus(self, on):
        self._focus = on
        self.redraw()

    def _destroyed(self, event):
        if event.widget is self:
            try:
                self.variable.trace_remove('write', self._trace)
            except (tk.TclError, ValueError):
                pass

    def _pad(self):
        return max(6, int(self.winfo_height()) // 2)

    def redraw(self):
        try:
            w, h = max(2, self.winfo_width()), max(2, self.winfo_height())
        except tk.TclError:
            return
        self.delete('all')
        pad, mid = self._pad(), h / 2
        span = (self._to - self._from) or 1
        t = min(1.0, max(0.0, (self.get() - self._from) / span))
        x = pad + (w - 2 * pad) * t
        c = self.colours
        self.create_line(pad, mid, w - pad, mid, fill=c['track'], width=4, capstyle='round')
        if x > pad:
            self.create_line(pad, mid, x, mid, fill=c['fill'], width=4, capstyle='round')
        r = 6
        if self._focus:
            self.create_oval(x - r - 3, mid - r - 3, x + r + 3, mid + r + 3, outline=c['focus'], width=2)
        self.create_oval(x - r, mid - r, x + r, mid + r, fill=c['thumb'], outline=c['track'])


_CHECK_IMAGES = {}


def check_images(widget, size, *, ground, box, line, accent, tick):
    """(off, on) PhotoImages for a modern check box (0.5.4): a rounded square, outlined when off and filled
    with the accent and a tick when on. Anti-aliased, pure Python, cached per colour set."""
    key = (widget.tk.interpaddr(), size, ground, box, line, accent, tick)
    if key in _CHECK_IMAGES:
        return _CHECK_IMAGES[key]
    g, b, l, a, t = (_hex(c, widget) for c in (ground, box, line, accent, tick))
    r = size * 0.28
    points = ((0.26, 0.52), (0.43, 0.69), (0.75, 0.33))       # the tick, as fractions of the box

    def inside(px, py, inset):
        x0, y0, x1, y1 = inset, inset, size - inset, size - inset
        rr = max(0.0, r - inset)
        if not (x0 <= px <= x1 and y0 <= py <= y1):
            return False
        cx, cy = min(max(px, x0 + rr), x1 - rr), min(max(py, y0 + rr), y1 - rr)
        return (px - cx) ** 2 + (py - cy) ** 2 <= rr * rr

    def near_tick(px, py):
        width = max(1.2, size * 0.085)
        for (ax, ay), (bx, by) in zip(points, points[1:]):
            ax, ay, bx, by = ax * size, ay * size, bx * size, by * size
            dx, dy = bx - ax, by - ay
            u = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
            if (px - ax - u * dx) ** 2 + (py - ay - u * dy) ** 2 <= width * width:
                return True
        return False

    def build(on):
        rows = []
        for y in range(size):
            row = []
            for x in range(size):
                acc = [0.0, 0.0, 0.0]
                for sx, sy in ((0.25, 0.25), (0.75, 0.25), (0.25, 0.75), (0.75, 0.75)):
                    px, py = x + sx, y + sy
                    if not inside(px, py, 0):
                        colour = g
                    elif on:
                        colour = t if near_tick(px, py) else a
                    elif inside(px, py, 1.5):
                        colour = b
                    else:
                        colour = l
                    for i in range(3):
                        acc[i] += colour[i] / 4
                row.append('#%02x%02x%02x' % tuple(round(v) for v in acc))
            rows.append('{' + ' '.join(row) + '}')
        image = tk.PhotoImage(master=widget, width=size, height=size)
        image.put(' '.join(rows), to=(0, 0))
        return image
    _CHECK_IMAGES[key] = images = (build(False), build(True))
    return images


def modern_check(widget):
    """Turn a tk.Checkbutton into a modern check box (Dark/Light): a drawn box beside the text in place of
    Tk's small square indicator. Behaviour, variable and command are unchanged."""
    try:
        import oracle_appearance
        palette = oracle_appearance.palette()
        if palette is None and oracle_appearance.modern():
            # A window outside the suite's own (the setup window): the chosen look's palette.
            from overcast.theme import palette as overcast_palette
            palette = overcast_palette(*oracle_appearance.chosen())
        if palette is None:
            return False
        bg = widget.cget('bg')
        # Measured with a Tcl call, not a Font object (whose deletion on a worker thread can hang Tk).
        linespace = int(widget.tk.call('font', 'metrics', widget.cget('font'), '-linespace'))
        size = max(14, min(20, int(linespace * 0.8)))
        off, on = check_images(widget, size, ground=bg, box=palette['field'], line=palette['faint'],
                               accent=palette['accent'], tick=palette['on_accent'])
        widget.configure(image=off, selectimage=on, compound='left', indicatoron=False, relief='flat',
                         offrelief='flat', overrelief='flat', bd=0, selectcolor=bg, activebackground=bg,
                         padx=2)
        widget._marble_check = (off, on)
        text = widget.cget('text')
        if text and not text.startswith(' '):
            widget.configure(text='  ' + text)
        return True
    except (tk.TclError, AttributeError, ValueError):
        return False


def scroll_with_wheel(area, canvas):
    """The mouse wheel scrolls `canvas` while the pointer is anywhere over `area` (0.5.4).

    A scrolled settings column could only be moved by its slim scroll bar, so settings below the fold looked
    missing. A binding tag of its own is added to every widget in the area (re-checked whenever the pointer
    enters, so widgets made later join in), so no application-wide binding is touched; lists and text boxes
    keep scrolling themselves first."""
    tag = f'MarbleWheel{id(area)}'

    def wheel(event):
        if getattr(event, 'num', None) == 4:
            step = -1
        elif getattr(event, 'num', None) == 5:
            step = 1
        else:
            step = -1 if event.delta > 0 else 1
        first, last = canvas.yview()
        if first > 0.0 or last < 1.0:
            canvas.yview_scroll(step * 2, 'units')

    def tag_all(_event=None):
        stack = [area]
        while stack:
            widget = stack.pop()
            try:
                tags = widget.bindtags()
                if tag not in tags and widget.winfo_class() not in ('Listbox', 'Text'):
                    widget.bindtags(tags + (tag,))
                stack.extend(widget.winfo_children())
            except tk.TclError:
                pass
    for sequence in ('<MouseWheel>', '<Button-4>', '<Button-5>'):
        area.bind_class(tag, sequence, wheel)
    area.bind('<Enter>', tag_all, add='+')
    area.after_idle(tag_all)
