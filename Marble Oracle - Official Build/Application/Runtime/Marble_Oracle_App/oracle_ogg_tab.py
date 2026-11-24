"""Oggcultist 2.0.6 as a *real* Marble Oracle tab, not an external launcher.

Oggcultist keeps its original seven pages and now-playing bar, but hosts the
same UI as a Tk Frame rather than a second Tk root. The instance remains
mounted (and can keep playing) when HOME or PASSPHRASE is selected.
"""
from __future__ import annotations

from pathlib import Path
import os
import re
import subprocess
import sys
import tkinter as tk

from marble_uberata import FAMILY
from oggcultist_design_system import COLOR
from oracle_design import HOME_LABEL
import oracle_shell as shell

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

        # 0.4.9.5: no separate title bar. Oggcultist's own rail already shows
        # its name and version; HOME goes to the foot of that rail (see
        # _add_home), where it sits in every other workspace.
        self.home_button = None

        # The inner UI owns no separate Tk root, no separate OS window and no
        # duplicate media library. All pages remain the original 2.0.6 pages.
        try:
            if not OGG_MAIN.is_file():
                raise FileNotFoundError('Oggcultist 2.0.6 program files are missing.')
            if str(OGG_ROOT) not in sys.path:
                sys.path.insert(0, str(OGG_ROOT))
            import oracle_appearance                    # 0.5.1: Dark / Light retint its own tokens first
            oracle_appearance.retint_oggcultist()
            from oggcultist.gui.app import OggcultistEmbeddedApp
            self.ogg_app = OggcultistEmbeddedApp(self)
            self.ogg_app.pack(fill='both', expand=True)
            self._add_home(on_home)
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
                     fg=COLOR['text_2'], font=shell.font('body')).pack(anchor='w', pady=(12, 20))
            shell.button(holder, 'OPEN STANDALONE OGGCULTIST', self.launch, primary=True).pack(anchor='w')
            self.home_button = shell.button(holder, HOME_LABEL, on_home)
            self.home_button.pack(anchor='w', pady=(10, 0))

    def _add_home(self, on_home):
        """The suite HOME button at the foot of Oggcultist's rail, just above its version line."""
        app = self.ogg_app
        sidebar = getattr(app, '_sidebar', None)
        anchor = getattr(app, 'version_label', None)
        first = getattr(app, 'brand_label', None)
        if sidebar is None or anchor is None:
            return
        self.home_button = shell.button(sidebar, HOME_LABEL, on_home, padx=4)   # whole in the 64 px icon rail
        if first is not None:
            # Packed ahead of the rail's top items, so in a short window the
            # version line and HOME keep their place and the items above give
            # way (Tk's packer serves widgets in packing order).
            anchor.pack_configure(before=first)
        self.home_button.pack(side='bottom', fill='x', padx=6, pady=(8, 0), after=anchor)   # whole even in the icon rail
        # 0.4.9.8: Settings sits at the foot of the rail too, so it is served
        # with HOME and the version line, ahead of the items above. Before, it
        # was packed last: at 1280x720 HOME covered half of it, and at 900x580
        # it was not reachable at all.
        settings = getattr(app, 'nav', {}).get('settings')
        if settings is not None:
            settings.pack_configure(after=self.home_button)
        groups = getattr(app, '_group_labels', None) or []

        def numbers(value):
            return [int(float(n)) for n in re.findall(r'-?\d+(?:\.\d+)?', str(value))]

        def rail_needs():
            """Height every packed rail item asks for, padding included."""
            total = 0
            for child in sidebar.pack_slaves():
                pady = numbers(child.pack_info().get('pady', 0)) or [0]
                total += child.winfo_reqheight() + (sum(pady) if len(pady) > 1 else 2 * pady[0])
            padding = numbers(sidebar.cget('padding'))
            if len(padding) == 4:
                total += padding[1] + padding[3]
            return total

        def fit_logo():
            # 0.4.9.8: in the 64 px icon rail of a short window (900x580) the
            # items did not fit and Converter and Album Art were cut off. The
            # logo there repeats the OGGCULTIST tab directly above it, so it
            # gives way first; it returns as soon as there is room again.
            if first is None or not groups:
                return
            compact = bool(getattr(app, 'compact', False))
            shown = bool(first.winfo_manager())
            height = sidebar.winfo_height()
            if height <= 1:
                return
            if shown:
                # Oggcultist re-packs its logo when the rail changes width,
                # which would put it at the end; keep it at the top.
                slaves = sidebar.pack_slaves()
                if groups[0] in slaves and slaves.index(first) + 1 != slaves.index(groups[0]):
                    first.pack_configure(before=groups[0])
                if compact and rail_needs() > height:
                    first.pack_forget()
            else:
                first.pack(anchor='center' if compact else 'w', before=groups[0])
                sidebar.update_idletasks()
                if compact and rail_needs() > height:
                    first.pack_forget()

        def fit(_event=None):
            # Below 1100 px Oggcultist shrinks its rail to 64 px icons; HOME
            # keeps its word in the small label type there rather than being
            # cut off. (The suite font has no house symbol to use instead.)
            try:
                compact = bool(getattr(app, 'compact', False))
                if getattr(self.home_button, '_compact', None) != compact:
                    self.home_button._compact = compact
                    self.home_button.configure(font=shell.font('group' if compact else 'button'),
                                               padx=2 if compact else shell.BUTTON_PAD[0])
                    self.home_button.pack_configure(padx=6 if compact else shell.RAIL_PADX)
                fit_logo()
            except tk.TclError:
                pass
        sidebar.bind('<Configure>', fit, add='+')
        fit()

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
