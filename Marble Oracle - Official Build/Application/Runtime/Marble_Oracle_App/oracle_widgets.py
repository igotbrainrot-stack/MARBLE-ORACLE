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
