"""Optional lifecycle adapter matching Marble Oracle 0.4.9.9 workspace conventions.

NOT imported by the existing suite yet. A future integration commit can wire
this in explicitly without modifying any existing HOME, Oggcultist or EIDOLITH code.
"""
from __future__ import annotations

import tkinter as tk
from . import create_panel


class EmbeddedSignal:
    """Minimal Marble Oracle workspace lifecycle (layout/clear/shutdown/key).

    Use one instance per host overlay. No Tk root, no subprocess, no global
    keyboard bindings. Hosts can supply `on_event` to receive JSON-like events.
    """
    def __init__(self, parent: tk.Widget, on_home=None, *, state_dir=None, on_event=None):
        self.parent=parent
        self.on_home=on_home
        self.panel=create_panel(parent,state_dir=state_dir,on_event=on_event)
        self._stopped=False

    def layout(self, box=None):
        if self._stopped:return
        if box is None:
            self.panel.place(relx=0,rely=0,relwidth=1,relheight=1)
        else:
            x0,y0,x1,y1=box
            self.panel.place(x=x0,y=y0,width=max(1,x1-x0),height=max(1,y1-y0))
        self.panel.lift()

    def clear(self):
        if not self._stopped:self.panel.place_forget()

    def shutdown(self):
        if not self._stopped:
            self._stopped=True
            self.panel.destroy()
        return True

    def key(self,event):
        # Reserve Escape for the host shell, and avoid hijacking typing inputs.
        return False
