"""Oggcultist 2.0.6 as a *real* Marble Oracle tab, not an external launcher.

Oggcultist keeps its original seven pages and now-playing bar, but hosts the
same UI as a Tk Frame rather than a second Tk root. The instance remains
mounted (and can keep playing) when HOME or PASSPHRASE is selected.
"""
from __future__ import annotations

from pathlib import Path
import os
import subprocess
import sys
import tkinter as tk

from marble_uberata import FAMILY
from oggcultist_design_system import COLOR

HERE = Path(__file__).resolve().parent
OGG_MAIN = HERE / 'Oggcultist' / 'launch.py'
OGG_ROOT = OGG_MAIN.parent


class OggcultistPanel(tk.Frame):
    def __init__(self, master, on_home, start_automatically=False, existing_process=None):
        super().__init__(master, background=COLOR['canvas'], bd=0, highlightthickness=0)
        self.on_home = on_home
        self.process = None                 # backwards-compatible attribute; no subprocess by default
        self.ogg_app = None
        self.status = tk.StringVar(master=self, value='')

        bar = tk.Frame(self, bg=COLOR['sidebar'], padx=10, pady=7)
        bar.pack(side='top', fill='x')
        tk.Label(bar, text='OGGCULTIST 2.0.6', bg=COLOR['sidebar'], fg=COLOR['text'],
                 font=(FAMILY, 12, 'bold')).pack(side='left', padx=(6, 0))
        tk.Button(bar, text='BACK TO HOME', command=on_home,
                  font=(FAMILY, 11, 'bold'), padx=14, pady=5,
                  bg=COLOR['control'], fg=COLOR['text'],
                  activebackground=COLOR['raised'], activeforeground=COLOR['text'],
                  relief='flat', bd=0, cursor='hand2').pack(side='right')

        # The inner UI owns no separate Tk root, no separate OS window and no
        # duplicate media library. All pages remain the original 2.0.6 pages.
        try:
            if not OGG_MAIN.is_file():
                raise FileNotFoundError('Oggcultist 2.0.6 program files are missing.')
            if str(OGG_ROOT) not in sys.path:
                sys.path.insert(0, str(OGG_ROOT))
            from oggcultist.gui.app import OggcultistEmbeddedApp
            self.ogg_app = OggcultistEmbeddedApp(self)
            self.ogg_app.pack(fill='both', expand=True)
            self.status.set('Oggcultist is running inside Marble Oracle.')
        except Exception as exc:
            self.status.set('Embedded Oggcultist could not start: ' + str(exc))
            holder = tk.Frame(self, bg=COLOR['raised'], padx=22, pady=22)
            holder.pack(fill='both', expand=True)
            tk.Label(holder, text='OGGCULTIST STARTUP ERROR',
                     bg=COLOR['raised'], fg=COLOR['text'],
                     font=(FAMILY, 16, 'bold')).pack(anchor='w')
            tk.Label(holder, textvariable=self.status,
                     wraplength=690, justify='left', bg=COLOR['raised'],
                     fg=COLOR['text_2'], font=(FAMILY, 11)).pack(anchor='w', pady=(12, 20))
            tk.Button(holder, text='OPEN STANDALONE OGGCULTIST',
                      command=self.launch, font=(FAMILY, 11),
                      bg=COLOR['accent'], fg=COLOR['canvas'],
                      relief='flat').pack(anchor='w')

    def launch(self):
        """Only the failure recovery path uses an external application."""
        try:
            flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            self.process = subprocess.Popen(
                [sys.executable, str(OGG_MAIN)], cwd=str(OGG_ROOT),
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, creationflags=flags,
                close_fds=True)
            self.status.set('Standalone Oggcultist launched as a recovery option.')
        except Exception as exc:
            self.status.set('Could not launch Oggcultist: ' + str(exc))

    def shutdown(self):
        """Stop media cleanly when the user exits the whole suite."""
        if self.ogg_app is None or not self.ogg_app.winfo_exists():
            return True
        if self.ogg_app.converter.busy:
            self.ogg_app.show_converter()
            from tkinter import messagebox
            messagebox.showinfo('Conversion in progress',
                                'A conversion is still running. Cancel or finish it before quitting Marble Oracle.',
                                parent=self.ogg_app)
            return False
        self.ogg_app._on_close()
        return True


class EmbeddedOggcultist:
    def __init__(self, canvas, on_home, start_automatically=False, existing_process=None):
        self.canvas = canvas
        self.frame = OggcultistPanel(canvas, on_home=on_home,
                                     start_automatically=start_automatically,
                                     existing_process=existing_process)
        self.window = canvas.create_window(0, 0, anchor='nw', window=self.frame,
                                           tags=('oggwin', 'oggcultist-tab'))
        self._box = None

    def layout(self, box):
        self._box = box
        if not self.canvas.type(self.window):
            self.window = self.canvas.create_window(0, 0, anchor='nw', window=self.frame,
                                                   tags=('oggwin', 'oggcultist-tab'))
        x0, y0, x1, y1 = box
        self.canvas.coords(self.window, x0, y0)
        self.canvas.itemconfigure(self.window, width=max(100, x1-x0), height=max(100, y1-y0), state='normal')
        self.canvas.tag_raise(self.window)

    def restore(self):
        if self._box is not None:
            self.layout(self._box)

    def clear(self):
        """Hide, do not destroy. Playback, scans and conversions must continue."""
        if self.canvas.type(self.window):
            self.canvas.itemconfigure(self.window, state='hidden')

    def shutdown(self):
        return self.frame.shutdown()

    def key(self, keysym, char=''):
        if keysym.lower() in ('escape', 'esc'):
            return 'close'
        return None
