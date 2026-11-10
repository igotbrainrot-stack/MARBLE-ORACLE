"""Settings page (2.0 "Ember"): cards for Appearance, Playback, Fonts, Music folder and About.

Saving the fonts copies them, with their licences and a short "HOW TO INSTALL.txt", into a
new folder the user picks (``fonts.export_fonts``); an existing folder is never overwritten.
Nothing is installed by Oggcultist itself: installing stays the user's choice, through
Windows' own right-click "Install".
"""
from __future__ import annotations

import os
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from tkinter import font as tkfont
from typing import TYPE_CHECKING

from .. import __version__
from .. import fonts as app_fonts
from . import design_system as ds
from .native_folders import choose_directory

if TYPE_CHECKING:  # pragma: no cover
    from .app import OggcultistApp

SAMPLE = 'Uberata Clear  Übergröße  123'
TWO_COLUMNS_FROM = 840            # viewport width (px) at which the cards sit in two columns


def open_folder(path: Path) -> bool:
    """Show a folder in the system file manager. Returns False if that wasn't possible."""
    try:
        if sys.platform == 'win32':
            os.startfile(str(path))  # noqa: S606 - opens Explorer on a folder the user chose
        elif sys.platform == 'darwin':
            subprocess.Popen(['open', str(path)])
        else:
            subprocess.Popen(['xdg-open', str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except (OSError, AttributeError):
        return False


def default_save_folder() -> Path:
    downloads = Path.home() / 'Downloads'
    return downloads if downloads.is_dir() else Path.home()


class SettingsPage(ttk.Frame):
    def __init__(self, parent, app: 'OggcultistApp'):
        m = ds.CONTENT_MARGIN
        super().__init__(parent, padding=(m, 4, m - 12, ds.SPACE['l']))
        self.app = app
        self.saved_folder: Path | None = None
        self._sample_fonts: list[tkfont.Font] = []
        self._wrapping: list[ttk.Label] = []

        ttk.Label(self, text='Settings', style='Title.TLabel').pack(anchor='w')
        ttk.Label(self, text='Appearance, playback, fonts and your music folder',
                  style='Muted.TLabel').pack(anchor='w', pady=(0, ds.SPACE['l']))

        # A scrolling viewport, so every card stays reachable at 960×600.
        viewport = ttk.Frame(self)
        viewport.pack(fill='both', expand=True)
        self.scroll_canvas = tk.Canvas(viewport, highlightthickness=0, borderwidth=0,
                                       background=ds.COLOR['canvas'])
        self.scroll_canvas.pack(side='left', fill='both', expand=True)
        self.scrollbar = ttk.Scrollbar(viewport, orient='vertical', command=self.scroll_canvas.yview)
        self.scrollbar.pack(side='right', fill='y', padx=(4, 0))
        self.scroll_canvas.configure(yscrollcommand=self.scrollbar.set)
        main = ttk.Frame(self.scroll_canvas)
        self._scroll_content = main
        self._scroll_window = self.scroll_canvas.create_window((0, 0), anchor='nw', window=main)
        main.bind('<Configure>', self._scroll_region_changed, add='+')
        self.scroll_canvas.bind('<Configure>', self._settings_viewport_changed, add='+')
        self.scroll_canvas.bind('<Enter>', self._scroll_enter, add='+')
        self.scroll_canvas.bind('<Leave>', self._scroll_leave, add='+')
        self._scroll_active = False
        self._single_settings_column = None

        self.cards: dict[str, ttk.Frame] = {}
        # two stacks of cards; in a narrow window the right stack moves under the left one
        self._columns = (ttk.Frame(main), ttk.Frame(main))
        self._settings_left, self._settings_right = self._columns
        self._build_appearance(self._columns[0])
        self._build_playback(self._columns[0])
        self._build_about(self._columns[0])
        self._build_fonts(self._columns[1])
        self._build_folder(self._columns[1])
        for card in self.cards.values():
            card.pack(fill='x', pady=(0, ds.SPACE['l']))
        self._layout_cards(single=False)

    # ------------------------------------------------------------------ cards
    def _card(self, parent, key: str, title: str) -> ttk.Frame:
        card = ttk.Frame(parent, style='Card.TFrame', padding=ds.SPACE['l'])
        ttk.Label(card, text=title, style='CardTitle.TLabel').pack(anchor='w', pady=(0, ds.SPACE['s']))
        self.cards[key] = card
        return card

    def _note(self, parent, text: str = '', **kw) -> ttk.Label:
        label = ttk.Label(parent, text=text, style='CardMuted.TLabel', wraplength=360, justify='left', **kw)
        self._wrapping.append(label)
        return label

    def _row(self, parent) -> ttk.Frame:
        tk.Frame(parent, height=1, background=ds.COLOR['line']).pack(fill='x', pady=(ds.SPACE['s'], 0))
        row = ttk.Frame(parent, style='CardInner.TFrame', padding=(0, ds.SPACE['s'], 0, 0))
        row.pack(fill='x')
        return row

    def _build_appearance(self, parent) -> None:
        card = self._card(parent, 'appearance', 'Appearance')
        row = self._row(card)
        self.animations = tk.BooleanVar(value=bool(self.app.settings.get('animations', True)))
        ttk.Checkbutton(row, text='Animations', variable=self.animations, style='Card.TCheckbutton',
                        command=self._animations_changed).pack(anchor='w')
        self._note(row, 'The amber gradient drifts slowly, and buttons fade on hover and sink when pressed. '
                        'Switch off for a completely still interface.').pack(anchor='w', padx=(24, 0))

    def _build_playback(self, parent) -> None:
        card = self._card(parent, 'playback', 'Playback')
        row = self._row(card)
        self.media_keys = tk.BooleanVar(value=bool(self.app.settings.get('media_keys', True)))
        ttk.Checkbutton(row, text='Headset and keyboard media buttons', variable=self.media_keys,
                        style='Card.TCheckbutton', command=self._media_keys_changed).pack(anchor='w')
        self._note(row, 'Takes effect the next time Oggcultist starts.').pack(anchor='w', padx=(24, 0))

    def _build_fonts(self, parent) -> None:
        card = self._card(parent, 'fonts', 'Fonts')
        families = set(tkfont.families(self))
        body_points = abs(int(tkfont.nametofont('OgBody', root=self).actual('size')))
        self.font_rows: dict[str, ttk.Label] = {}
        self.font_export_buttons: dict[str, ttk.Button] = {}
        for info in app_fonts.FONTS:
            row = self._row(card)
            row.columnconfigure(0, weight=1)
            ttk.Label(row, text=info.title, style='CardMuted.TLabel').grid(row=0, column=0, sticky='w')
            button = ttk.Button(row, text='Save...', style='Ghost.TButton',
                                command=lambda k=info.key: self.save_fonts(font_key=k))
            button.grid(row=0, column=1, rowspan=2, sticky='e', padx=(ds.SPACE['s'], 0))
            self.font_export_buttons[info.key] = button
            if info.family in families:
                sample = tkfont.Font(root=self, family=info.family,
                                     size=body_points + 2,
                                     weight='bold' if info.style == 'Bold' else 'normal')
                self._sample_fonts.append(sample)
                label = ttk.Label(row, text=SAMPLE, font=sample, style='Card.TLabel')
            else:
                label = ttk.Label(row, text='Could not be loaded here; the file is still included.',
                                  style='CardMuted.TLabel')
            label.grid(row=1, column=0, sticky='w')
            self.font_rows[info.filename] = label
        actions = self._row(card)
        self.save_btn = ttk.Button(actions, text='Export fonts...', style='Accent.TButton', command=self.save_fonts)
        self.save_btn.pack(side='left')
        self.open_btn = ttk.Button(actions, text='Open folder', style='Ghost.TButton', command=self.open_saved,
                                   state='disabled')
        self.open_btn.pack(side='left', padx=(ds.SPACE['s'], 0))
        self._note(card, 'Saves Uberata Clear with its licence into a new folder. To use it in other programs, '
                         'right-click the TTF and choose Install. Oggcultist never '
                         'installs or downloads fonts.').pack(anchor='w', pady=(ds.SPACE['s'], 0))
        self.saved_text = tk.StringVar(value='')
        self._saved_label = self._note(card, textvariable=self.saved_text)   # packed once something is saved

    def _build_folder(self, parent) -> None:
        card = self._card(parent, 'folder', 'Music folder')
        row = self._row(card)
        self.folder_label = ttk.Label(row, textvariable=self.app.library_folder, style='Card.TLabel',
                                      wraplength=360, justify='left')
        self._wrapping.append(self.folder_label)
        self.folder_label.pack(anchor='w')
        buttons = ttk.Frame(card, style='CardInner.TFrame', padding=(0, ds.SPACE['s'], 0, 0))
        buttons.pack(fill='x')
        ttk.Button(buttons, text='Change folder...', command=self.app.choose_library).pack(side='left')
        ttk.Button(buttons, text='Rescan', style='Ghost.TButton',
                   command=self.app.rescan_library).pack(side='left', padx=(ds.SPACE['s'], 0))

    def _build_about(self, parent) -> None:
        card = self._card(parent, 'about', 'About')
        row = self._row(card)
        ttk.Label(row, text='Oggcultist', style='CardDisplay.TLabel').pack(anchor='w')
        self._note(row, f'Version {__version__} “Ember”. A local-first music player and FLAC to Opus '
                        'converter. Your original audio files are never changed.').pack(anchor='w')

    def _layout_cards(self, single: bool) -> None:
        main = self._scroll_content
        left, right = self._columns
        left.grid_forget()
        right.grid_forget()
        gap = ds.SPACE['l']
        if single:
            main.columnconfigure(0, weight=1, uniform='')
            main.columnconfigure(1, weight=0, uniform='')
            left.grid(row=0, column=0, sticky='new')
            right.grid(row=1, column=0, sticky='new')
        else:
            main.columnconfigure(0, weight=1, uniform='settings')
            main.columnconfigure(1, weight=1, uniform='settings')
            left.grid(row=0, column=0, sticky='new', padx=(0, gap // 2))
            right.grid(row=0, column=1, sticky='new', padx=(gap // 2, 0))

    # ------------------------------------------------------------------ responsive viewport
    def _scroll_region_changed(self, _event=None) -> None:
        self.scroll_canvas.configure(scrollregion=self.scroll_canvas.bbox('all'))

    def _settings_viewport_changed(self, event) -> None:
        self.scroll_canvas.itemconfigure(self._scroll_window, width=max(1, event.width))
        single = event.width < TWO_COLUMNS_FROM
        if single != self._single_settings_column:
            self._single_settings_column = single
            self._layout_cards(single)
        self.after_idle(self._settings_wrap_labels)

    def _settings_wrap_labels(self) -> None:
        for label in self._wrapping:
            try:
                width = label.master.winfo_width() - label.winfo_x() - ds.SPACE['xs']
                label.configure(wraplength=max(160, width))
            except tk.TclError:
                pass

    def _scroll_enter(self, _event=None) -> None:
        self._scroll_active = True
        self.bind_all('<MouseWheel>', self._settings_mousewheel, add='+')
        self.bind_all('<Button-4>', self._settings_wheel_up, add='+')
        self.bind_all('<Button-5>', self._settings_wheel_down, add='+')

    def _scroll_leave(self, _event=None) -> None:
        self._scroll_active = False
        self.unbind_all('<MouseWheel>')
        self.unbind_all('<Button-4>')
        self.unbind_all('<Button-5>')

    def _settings_mousewheel(self, event) -> None:
        if self._scroll_active:
            self.scroll_canvas.yview_scroll(-int(event.delta / 120) if event.delta else 0, 'units')

    def _settings_wheel_up(self, _event) -> None:
        if self._scroll_active:
            self.scroll_canvas.yview_scroll(-1, 'units')

    def _settings_wheel_down(self, _event) -> None:
        if self._scroll_active:
            self.scroll_canvas.yview_scroll(1, 'units')

    # ------------------------------------------------------------------ page interface
    def refresh(self) -> None:
        pass

    def focus_content(self) -> None:
        self.save_btn.focus_set()

    # ------------------------------------------------------------------ actions
    def save_fonts(self, parent: Path | str | None = None, font_key: str | None = None) -> Path | None:
        """Copy the fonts into a new folder. ``parent`` skips the folder dialog (tests)."""
        if parent is None:
            chosen = choose_directory(parent=self, title='Save Uberata Clear in...',
                                             initialdir=str(default_save_folder()), mustexist=True)
            if not chosen:
                return None
            parent = chosen
        try:
            folder = app_fonts.export_fonts(parent, font_key=font_key)
        except (OSError, ValueError) as exc:
            messagebox.showerror('Fonts not saved', f'The font files could not be saved:\n\n{exc}', parent=self)
            return None
        self.saved_folder = folder
        self.open_btn.configure(state='normal')
        count = 1 if font_key else sum(app_fonts.resource(x.filename) is not None for x in app_fonts.FONTS)
        self.saved_text.set(f'Saved {count} font{"s" if count != 1 else ""} and licences in:\n{folder}')
        if not self._saved_label.winfo_ismapped():
            self._saved_label.pack(anchor='w', pady=(ds.SPACE['s'], 0))
        self.app.notify(f'Fonts saved in {folder}')
        return folder

    def open_saved(self) -> None:
        if self.saved_folder is not None and not open_folder(self.saved_folder):
            self.app.notify(f'Open this folder yourself: {self.saved_folder}')

    def _animations_changed(self) -> None:
        enabled = bool(self.animations.get())
        self.app.update_settings(animations=enabled)
        self.app.set_animations(enabled)

    def _media_keys_changed(self) -> None:
        self.app.update_settings(media_keys=bool(self.media_keys.get()))
