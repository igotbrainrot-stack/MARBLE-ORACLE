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
