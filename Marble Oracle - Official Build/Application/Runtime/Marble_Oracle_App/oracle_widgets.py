"""Small Tk behaviours every workspace shares, so none of them clips its controls.

* flow(container, children)   a toolbar whose buttons wrap to a second row when
                              the window is too narrow, instead of running off
                              the right edge;
* wrap_to_parent(widget)      explanatory text that wraps to the width it is
                              given, instead of being cut mid-sentence.

Both are driven by the container's real width, so they hold at any window
size and font scaling. The arithmetic lives in oracle_design.flow_layout.
"""
from __future__ import annotations

import tkinter as tk

from oracle_design import WrapSettler, flow_layout


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
