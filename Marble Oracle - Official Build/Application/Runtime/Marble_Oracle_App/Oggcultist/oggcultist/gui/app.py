"""The Oggcultist desktop window: one window, player first, converter one click away.

Layout::

    ┌──────────┬─────────────────────────────────────────────┐
    │ Sidebar  │  search · status                            │
    │ Library  ├─────────────────────────────────────────────┤
    │ Artists  │                                             │
    │ Albums   │     current page (Library ... Converter)      │
    │ Playlists│                                             │
    │──────────│                                             │
    │ Converter│                                             │
    ├──────────┴─────────────────────────────────────────────┤
    │ now playing: cover · title · ⏮ ▶ ⏭ ■ · seek · volume   │
    └────────────────────────────────────────────────────────┘

Playback lives in :class:`PlayerController`, outside every page, so switching
to the converter (or converting) never interrupts music.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk

from .. import __version__, paths
from ..player import PlaylistStore, Song, scan_music_library
from .converter_view import ConverterPage
from .art_view import CoverArtPage
from .settings_view import SettingsPage
from .now_playing import NowPlayingBar
from .player_view import AlbumsPage, ArtistsPage, LibraryPage, PlayerController, PlaylistsPage
from .theme import GRADIENT, PALETTE, apply_theme, set_heading_font, set_body_font, enable_dpi_awareness
from . import brand, line_icons
from .widgets import GradientRule
from . import design_system as ds
from .native_folders import choose_directory

PAGES = (('library', 'Library'), ('artists', 'Artists'), ('albums', 'Albums'), ('playlists', 'Playlists'))
CONVERTER = ('converter', 'Converter')
ART = ('art', 'Album Art')
SETTINGS = ('settings', 'Settings')
UNSEARCHABLE = ('converter', 'settings')     # pages where the search box is switched off
SIDEBAR_WIDTH = ds.SIDEBAR_WIDTH          # deliberate navigation-to-content ratio


def settings_file() -> Path:
    return paths.settings_file()


def load_settings() -> dict:
    try:
        data = json.loads(settings_file().read_text('utf-8'))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_settings(data: dict) -> None:
    """Atomic write that keeps keys written by other versions."""
    path = settings_file()
    merged = load_settings()
    merged.update(data)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix='.settings-', suffix='.json', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(merged, f, indent=2, ensure_ascii=False)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


class _OggcultistUI:
    """Shared desktop and embedded UI; the latter lives in Marble Oracle's tab."""

    def __init__(self, startup_message: str = '', *, master=None, embedded: bool = False):
        self._embedded = embedded
        enable_dpi_awareness()
        from .. import fonts as app_fonts
        app_fonts.register_private_fonts()          # before Tk starts, so Tk can see the font
        if embedded:
            super().__init__(master, background=PALETTE['bg'])
        else:
            super().__init__(className='Oggcultist')
            self.title('Oggcultist')
        self.settings = load_settings()
        # 1.9.x font choices (heading_font / body_font) may still be in the file: they are ignored.
        self._fonts_ok = app_fonts.ensure_ui_fonts_loaded(self)
        if not embedded:
            self.geometry(self.settings.get('geometry') or '{}x{}'.format(*ds.DEFAULT_WINDOW))
            self.minsize(*ds.MIN_WINDOW)
        self.fonts = apply_theme(self)
        if not embedded:
            self._set_icon()

        self.library_folder = tk.StringVar(value=self.settings.get('library') or self.settings.get('output')
                                           or self.settings.get('input') or '')
        self.search = tk.StringVar()
        self.status = tk.StringVar(value=startup_message or 'Welcome to Oggcultist.')
        self.volume = tk.IntVar(value=int(self.settings.get('volume', 80)))
        self.songs: list[Song] = []
        self.by_path: dict[str, Song] = {}
        self.scanning = False
        self.closed = False
        self._search_job = None
        self._status_job = None
        self._events: list = []
        self._lock = threading.Lock()
        try:
            self.playlists: PlaylistStore | None = PlaylistStore()
            self.playlists_error = ''
        except ValueError as exc:
            self.playlists = None
            self.playlists_error = str(exc)
        self.player = PlayerController(self)

        self._build()
        self.set_animations(bool(self.settings.get('animations', True)))   # v1.8.9: drift + button motion
        if not embedded:
            try:                               # dark title bar and border on Windows
                from .window_frame import follow_new_windows
                follow_new_windows(self, caption=PALETTE['sidebar'], text=PALETTE['text'], border='#2A211C')
            except Exception:  # noqa: BLE001 - cosmetic only
                pass
        self.media = None
        if self.settings.get('media_keys', True):       # headset / keyboard media buttons
            try:
                from .media_keys import MediaControls
                self.media = MediaControls(self).start()
            except Exception:  # noqa: BLE001 - media buttons are optional, never block start-up
                self.media = None
        self.search.trace_add('write', lambda *_: self._debounced_search())
        self._bind_keys()
        if not embedded:
            self.protocol('WM_DELETE_WINDOW', self._on_close)
        self.show_page(self.settings.get('page') if self.settings.get('page') in dict(PAGES) else 'library')
        if not self._fonts_ok:
            self.notify('Bundled Uberata Clear is missing or could not be loaded. Please extract a fresh Oggcultist ZIP.', sticky=True)
        if self.playlists_error:
            self.notify('Playlists could not be loaded and were left unchanged: ' + self.playlists_error, sticky=True)
        self._timer = self.after(200, self._tick)
        if self.library_folder.get() and Path(self.library_folder.get()).is_dir():
            self.after(150, self.rescan_library)

    # ------------------------------------------------------------------ building
    def _set_icon(self) -> None:
        self._icons = brand.window_icons(self)   # keep references alive
        if self._icons:
            try:
                self.iconphoto(True, *self._icons)
            except tk.TclError:
                pass

    def _build(self) -> None:
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        self._build_sidebar()

        main = ttk.Frame(self)
        main.grid(row=0, column=1, sticky='nsew')
        main.columnconfigure(0, weight=1)
        main.rowconfigure(1, weight=1)
        topbar = ttk.Frame(main, padding=(ds.TOPBAR_MARGIN, ds.SPACE['l'], ds.TOPBAR_MARGIN, ds.SPACE['xs']))
        topbar.grid(row=0, column=0, sticky='ew')
        topbar.columnconfigure(0, weight=1, minsize=280)
        topbar.columnconfigure(1, weight=1)

        search_zone = ttk.Frame(topbar)
        search_zone.grid(row=0, column=0, sticky='ew', padx=(0, 18))
        search_zone.columnconfigure(0, weight=1)
        self.search_entry = ttk.Entry(search_zone, textvariable=self.search, width=40, style='Search.TEntry')
        self.search_entry.grid(row=0, column=0, sticky='ew')
        self._search_icon = line_icons.photo(self, 'search', 18, ds.COLOR['text_3'])
        if self._search_icon is not None:
            ttk.Label(search_zone, image=self._search_icon, style='Field.TLabel').place(
                in_=self.search_entry, x=10, rely=0.5, anchor='w')
        # placeholder: a label over the empty field (never put into the search text itself)
        self._search_placeholder = ttk.Label(search_zone, text='Search your music', style='Placeholder.TLabel')
        self._search_hint = ttk.Label(search_zone, text='Ctrl+F', style='Status.TLabel')
        self._search_hint.grid(row=0, column=1, sticky='w', padx=(12, 0))
        self._search_placeholder.bind('<Button-1>', lambda _e: self.search_entry.focus_set())
        for sequence in ('<FocusIn>', '<FocusOut>'):
            self.search_entry.bind(sequence, lambda _e: self._update_placeholder(), add='+')
        self.search.trace_add('write', lambda *_: self._update_placeholder())
        self.after_idle(self._update_placeholder)

        status_zone = ttk.Frame(topbar)
        status_zone.grid(row=0, column=1, sticky='ew')
        status_zone.columnconfigure(0, weight=1)
        # a fixed character width: a long message is cut short instead of squeezing the search field
        self.status_label = ttk.Label(status_zone, textvariable=self.status, style='Status.TLabel', anchor='e', width=46)
        self.status_label.grid(row=0, column=0, sticky='e')
        topbar.bind('<Configure>', self._topbar_resized, add='+')

        self.content = ttk.Frame(main)
        self.content.grid(row=1, column=0, sticky='nsew')
        self.content.rowconfigure(0, weight=1)
        self.content.columnconfigure(0, weight=1)
        self.pages = {
            'library': LibraryPage(self.content, self),
            'artists': ArtistsPage(self.content, self),
            'albums': AlbumsPage(self.content, self),
            'playlists': PlaylistsPage(self.content, self),
            'converter': ConverterPage(self.content, self),
            'art': CoverArtPage(self.content, self),
            'settings': SettingsPage(self.content, self),
        }
        for page in self.pages.values():
            page.grid(row=0, column=0, sticky='nsew')
        self.converter = self.pages['converter']

        GradientRule(self, GRADIENT).grid(row=1, column=0, columnspan=2, sticky='ew')
        self.now = NowPlayingBar(self, self)
        self.now.grid(row=2, column=0, columnspan=2, sticky='ew')
        self.current_page = 'library'

    def _bind_keys(self) -> None:
        self.bind_all('<Control-f>', lambda _e: self.focus_search())
        self.bind_all('<Control-F>', lambda _e: self.focus_search())
        self.search_entry.bind('<Escape>', lambda _e: (self.search.set(''), self.pages[self.current_page].focus_content()))
        self.search_entry.bind('<Return>', lambda _e: self.pages[self.current_page].focus_content())
        self.search_entry.bind('<Down>', lambda _e: self.pages[self.current_page].focus_content())
        for number, (key, _label) in enumerate((*PAGES, CONVERTER, ART, SETTINGS), start=1):
            self.bind_all(f'<Control-Key-{number}>', lambda _e, k=key: self.show_page(k))
        self.bind_all('<space>', self._space)
        self.bind_all('<Control-Right>', lambda _e: self._unless_typing(self.player.next))
        self.bind_all('<Control-Left>', lambda _e: self._unless_typing(self.player.previous))
        for key in ('<Control-s>', '<Control-S>'):
            self.bind_all(key, lambda _e: self._unless_typing(self.player.toggle_shuffle))
        for key in ('<Control-r>', '<Control-R>'):
            self.bind_all(key, lambda _e: self._unless_typing(self.player.cycle_repeat))

    def _typing(self) -> bool:
        widget = self.focus_get()
        return isinstance(widget, (tk.Entry, ttk.Entry, tk.Text, ttk.Combobox, tk.Spinbox))

    def _unless_typing(self, action) -> str | None:
        if self._typing():
            return None
        action()
        return 'break'

    def _space(self, event) -> str | None:
        if self._typing() or isinstance(event.widget, (ttk.Button, tk.Button, ttk.Checkbutton, ttk.Menubutton)):
            return None
        self.player.toggle()
        return 'break'

    # ------------------------------------------------------------------ navigation
    def _topbar_resized(self, event) -> None:
        """Hide low-priority helper text first on narrower windows."""
        searchable = getattr(self, 'current_page', 'library') not in UNSEARCHABLE
        wanted = 'Ctrl+F' if searchable and self.winfo_width() >= ds.COMPACT_BREAKPOINT else ''
        if self._search_hint.cget('text') != wanted:
            self._search_hint.configure(text=wanted)

    def _update_placeholder(self) -> None:
        entry = self.search_entry
        show = (not self.search.get() and self.focus_get() is not entry
                and str(entry.cget('state')) != 'disabled')
        if show:
            self._search_placeholder.place(in_=entry, x=36 if self._search_icon else 12, rely=0.5, anchor='w')
        else:
            self._search_placeholder.place_forget()

    # ------------------------------------------------------------------ sidebar
    def _build_sidebar(self) -> None:
        """Brand, two labelled groups of icon + text items, Settings and the version at the bottom."""
        sidebar = ttk.Frame(self, style='Sidebar.TFrame', padding=(0, ds.SPACE['l'], 0, ds.SPACE['l']),
                            width=SIDEBAR_WIDTH)
        self._sidebar = sidebar
        sidebar.grid(row=0, column=0, sticky='nsw')
        sidebar.grid_propagate(False)
        sidebar.pack_propagate(False)
        self._brand_image = brand.sidebar_lockup(self, max_width=SIDEBAR_WIDTH - 2 * ds.SPACE['l'] - 4)
        self._brand_symbol = brand.sidebar_symbol(self, height=34)
        options = dict(image=self._brand_image, compound='image') if self._brand_image is not None else {}
        self.brand_label = ttk.Label(sidebar, text='Oggcultist', style='Brand.TLabel',
                                     padding=(ds.SPACE['l'] + 4, 4, 0, ds.SPACE['xl']), **options)
        self.brand_label.pack(anchor='w')
        self._group_labels = []

        def group(text, first=False):
            label = ttk.Label(sidebar, text=text.upper(), style='SidebarLabel.TLabel',
                              padding=(ds.SPACE['xl'] - 4, 0 if first else ds.SPACE['l'], 0, ds.SPACE['s']))
            label.pack(anchor='w', fill='x')
            self._group_labels.append(label)

        self.nav: dict[str, ttk.Button] = {}
        self._nav_icons: dict[str, tuple] = {}
        self._nav_text: dict[str, str] = {}

        def item(key, label, **pack):
            icons = (line_icons.stateful(self, key, ds.NAV_ICON, ds.COLOR['sidebar_icon'], active=ds.COLOR['text_bright']),
                     line_icons.stateful(self, key, ds.NAV_ICON, ds.COLOR['accent']))
            self._nav_icons[key] = icons
            self._nav_text[key] = label
            extra = dict(image=icons[0], compound='left') if icons[0] else {}
            button = ttk.Button(sidebar, text=label, style='Nav.TButton', width=0,
                                command=lambda k=key: self.show_page(k), **extra)
            button.pack(fill='x', padx=ds.SPACE['s'], pady=1, **pack)
            self.nav[key] = button

        group('Your music', first=True)
        for key, label in PAGES:
            item(key, label)
        group('Workspace')
        for key, label in (CONVERTER, ART):
            item(key, label)
        self.converter_badge = ttk.Label(sidebar, text='', style='SidebarMuted.TLabel',
                                         padding=(ds.SPACE['xl'] + 26, 2, 0, 0))
        self.converter_badge.pack(anchor='w')
        self.version_label = ttk.Label(sidebar, text=f'{__version__} · OGG', style='SidebarMuted.TLabel',
                                       padding=(ds.SPACE['xl'] - 4, ds.SPACE['s'], 0, 0))
        self.version_label.pack(side='bottom', anchor='w')
        item(*SETTINGS, side='bottom')
        self.compact = False
        self._fit_sidebar_titles()
        self.bind('<Configure>', self._window_resized, add='+')

    def _window_resized(self, event) -> None:
        if event.widget is self and not getattr(self, '_compact_check', None):
            # decide from the settled size: Tk can report a stale width in the event itself
            self._compact_check = self.after_idle(self._check_compact)

    def _check_compact(self) -> None:
        self._compact_check = None
        width = self.winfo_width()
        if width > 1:
            self.set_compact(width < ds.COMPACT_BREAKPOINT)

    def set_compact(self, compact: bool) -> None:
        """Below the breakpoint the sidebar becomes a 64 px icon rail; tooltips are the page titles."""
        if compact == self.compact:
            return
        self.compact = compact
        self._sidebar.configure(width=ds.SIDEBAR_COMPACT_WIDTH if compact else SIDEBAR_WIDTH)
        if compact:
            if self._brand_symbol is not None:
                self.brand_label.configure(image=self._brand_symbol, compound='image', padding=(0, 4, 0, ds.SPACE['xl']))
            self.brand_label.pack_configure(anchor='center')
            for label in self._group_labels:
                label.configure(text='', padding=(0, ds.SPACE['s'], 0, 0))
            self.version_label.configure(text='')
            self.converter_badge.configure(padding=(ds.SPACE['m'], 2, 0, 0))
        else:
            options = dict(image=self._brand_image, compound='image') if self._brand_image is not None else dict(image='')
            self.brand_label.configure(padding=(ds.SPACE['l'] + 4, 4, 0, ds.SPACE['xl']), **options)
            self.brand_label.pack_configure(anchor='w')
            for label, text, first in zip(self._group_labels, ('Your music', 'Workspace'), (True, False)):
                label.configure(text=text.upper(),
                                padding=(ds.SPACE['xl'] - 4, 0 if first else ds.SPACE['l'], 0, ds.SPACE['s']))
            self.version_label.configure(text=f'{__version__} · OGG')
            self.converter_badge.configure(padding=(ds.SPACE['xl'] + 26, 2, 0, 0))
        for key, button in self.nav.items():
            if compact and self._nav_icons[key][0]:
                button.configure(text='', compound='image', style=self._nav_style(key, compact=True))
            else:
                button.configure(text=self._nav_text[key], compound='left', style=self._nav_style(key))

    def _nav_style(self, key: str, compact: bool | None = None) -> str:
        compact = self.compact if compact is None else compact
        on = key == getattr(self, 'current_page', None)
        return ('NavActive' if on else 'Nav') + ('Rail' if compact else '') + '.TButton'

    def _fit_sidebar_titles(self) -> int:
        """Largest uniform sidebar size (up to the token) at which every item fits the rail."""
        width = int(self._sidebar.cget('width'))
        nav_font = self.fonts['nav']
        body_points = abs(int(self.fonts['body'].actual('size')))
        chosen = ds.MIN_POINTS
        for points in range(ds.sidebar_font_points(body_points), ds.MIN_POINTS - 1, -1):
            nav_font.configure(size=points)
            self.update_idletasks()
            if all(button.winfo_reqwidth() <= width - 2 * ds.SPACE['s'] for button in self.nav.values()):
                chosen = points
                break
        nav_font.configure(size=chosen)
        self._nav_title_size = chosen
        return chosen

    def show_page(self, key: str) -> None:
        if key not in self.pages:
            return
        self.current_page = key
        for name, button in self.nav.items():
            button.configure(style=self._nav_style(name))
            icons = self._nav_icons.get(name)
            if icons and icons[0]:
                button.configure(image=icons[1] if name == key else icons[0])
        page = self.pages[key]
        page.tkraise()
        searchable = key not in UNSEARCHABLE
        self.search_entry.configure(state='normal' if searchable else 'disabled')
        self._search_hint.configure(text='Ctrl+F' if searchable and self.winfo_width() >= ds.COMPACT_BREAKPOINT else '')
        self._update_placeholder()
        if key != 'converter':
            page.refresh()

    def show_converter(self) -> None:
        self.show_page('converter')

    def show_player(self) -> None:
        self.show_page('library')

    def focus_search(self) -> str:
        if self.current_page in UNSEARCHABLE:
            self.show_page('library')
        self.search_entry.focus_set()
        self.search_entry.select_range(0, 'end')
        return 'break'

    def search_query(self) -> str:
        return self.search.get().strip().casefold()

    def _debounced_search(self) -> None:
        if self._search_job is not None:
            self.after_cancel(self._search_job)
        self._search_job = self.after(180, self._apply_search)

    def _apply_search(self) -> None:
        self._search_job = None
        page = self.pages.get(self.current_page)
        if page is not None and self.current_page != 'converter':
            page.refresh()

    def refresh_player_pages(self) -> None:
        if self.current_page != 'converter':
            self.pages[self.current_page].refresh()

    # ------------------------------------------------------------------ status
    def notify(self, message: str, sticky: bool = False) -> None:
        """Show a short message in the status line instead of an interrupting dialog."""
        self.status.set(message)
        if self._status_job is not None:
            self.after_cancel(self._status_job)
            self._status_job = None
        if not sticky:
            self._status_job = self.after(9000, lambda: self.status.set(''))

    def converter_busy_changed(self, busy: bool) -> None:
        self.converter_badge.configure(text='● working...' if busy else '')

    # ------------------------------------------------------------------ settings
    def change_heading_font(self, choice: object = None) -> str:
        """1.9.x API: 2.0 has a single heading face. Returns the family in use."""
        return set_heading_font(self, choice)

    def change_body_font(self, choice: object = None) -> str:
        """1.9.x API: 2.0 has a single text face. Returns the family in use."""
        return set_body_font(self, choice)

    def set_animations(self, enabled: bool) -> None:
        """Turn the gradient drift and the button hover/press motion on or off (v1.8.9)."""
        anim = getattr(self, '_og_anim', None)
        motion = getattr(self, '_og_motion', None)
        if anim is not None:
            anim.set_enabled(enabled)
            if enabled:
                anim.start()
        if motion is not None:
            motion.set_enabled(enabled)

    def update_settings(self, **values) -> None:
        self.settings.update(values)
        try:
            save_settings(values)
        except OSError as exc:
            self.notify(f'Could not save settings: {exc}')

    # ------------------------------------------------------------------ library
    def choose_library(self) -> None:
        folder = choose_directory(parent=self, mustexist=True, title='Choose music library folder',
                                  initialdir=self.library_folder.get() or str(Path.home()))
        if folder:
            self.library_folder.set(folder)
            self.update_settings(library=folder)
            self.rescan_library()

    def rescan_library(self) -> None:
        if self.scanning:
            return
        folder = Path(self.library_folder.get()).expanduser()
        if not folder.is_dir():
            self.notify('That music folder no longer exists. Choose another one.')
            return
        self.scanning = True
        self.pages['library'].rescan_btn.configure(state='disabled')
        self.refresh_player_pages()
        self.notify('Reading library...', sticky=True)

        def job():
            try:
                result = scan_music_library(folder, lambda: self.closed)
                self._post(('scanned', result))
            except Exception as exc:
                self._post(('scan_error', str(exc)))
        threading.Thread(target=job, daemon=True).start()

    def _post(self, event) -> None:
        with self._lock:
            self._events.append(event)

    def _library_loaded(self, result) -> None:
        songs, errors = result
        self.songs = songs
        self.by_path = {str(s.path): s for s in songs}
        self.scanning = False
        self.pages['library'].rescan_btn.configure(state='normal')
        self.refresh_player_pages()
        unreadable = f' ({len(errors)} unreadable files skipped)' if errors else ''
        self.notify(f'Loaded {len(songs)} songs{unreadable}.')

    # ------------------------------------------------------------------ playlists
    def playlists_changed(self) -> None:
        self.refresh_player_pages()

    def create_playlist(self, name: str) -> str | None:
        if self.playlists is None:
            self.notify('Playlists are unavailable: ' + self.playlists_error, sticky=True)
            return None
        try:
            self.playlists.create(name)
        except (ValueError, OSError) as exc:
            self.notify(f'Could not create playlist: {exc}')
            return None
        name = name.strip()
        self.notify(f'Created playlist {name}.')
        self.playlists_changed()
        return name

    def add_to_playlist(self, name: str, songs: list[Song]) -> None:
        if self.playlists is None or not songs:
            self.notify('Select one or more songs first.' if not songs else 'Playlists are unavailable.')
            return
        try:
            count = self.playlists.add(name, [s.path for s in songs])
        except (OSError, KeyError) as exc:
            self.notify(f'Could not save playlist: {exc}')
            return
        skipped = len(songs) - count
        self.notify(f'Added {count} song(s) to {name}' + (f' ({skipped} already there).' if skipped else '.'))
        self.playlists_changed()

    def new_playlist_from(self, songs: list[Song]) -> None:
        if not songs:
            self.notify('Select one or more songs first.')
            return
        name = simpledialog.askstring('New playlist', 'Name for the new playlist:', parent=self)
        if name is None:
            return
        created = self.create_playlist(name)
        if created:
            self.add_to_playlist(created, songs)

    def fill_playlist_menu(self, menu: tk.Menu, songs_fn) -> None:
        menu.delete(0, 'end')
        names = sorted(self.playlists.playlists, key=str.casefold) if self.playlists else []
        for name in names:
            menu.add_command(label=name, command=lambda n=name: self.add_to_playlist(n, songs_fn()))
        if names:
            menu.add_separator()
        menu.add_command(label='New playlist...', command=lambda: self.new_playlist_from(songs_fn()))

    # ------------------------------------------------------------------ playback hooks
    def play_current_selection(self) -> None:
        page = self.pages.get(self.current_page)
        if hasattr(page, 'play_selected'):
            page.play_selected()

    def on_song_changed(self, old_path: str | None, song: Song | None) -> None:
        new_path = str(song.path) if song else None
        for page in self.pages.values():
            if hasattr(page, 'mark_playing'):
                page.mark_playing(old_path, new_path)
        self.now.show(song)
        self.publish_media_state()
        if not self._embedded:
            if song is not None:
                self.title(f'{song.title} — {song.display_artist} · Oggcultist')
            else:
                self.title('Oggcultist')

    def on_play_state(self) -> None:
        self.now.update_play_state()
        self.publish_media_state()

    def publish_media_state(self) -> None:
        if getattr(self, 'media', None) is not None:
            try:
                self.media.publish()
            except Exception:  # noqa: BLE001
                pass

    def offer_ffplay(self, song: Song) -> None:
        if sys.platform != 'win32':
            self.now.notice('Playback unavailable', 'FFplay is missing — install it with: sudo apt install ffmpeg')
            self.notify('The music player needs FFplay. On Linux Mint/Ubuntu: sudo apt install ffmpeg', sticky=True)
            return
        if not messagebox.askyesno(
                'Install audio player',
                'FFplay is needed to play music. Install it in your Oggcultist user folder?\n\n'
                'The download comes from the FFmpeg Windows build at gyan.dev and is SHA-256 verified.\n'
                'No administrator access is needed.', parent=self):
            self.notify('Playback needs FFplay. You can still browse music and use the converter.')
            return
        self.notify('Downloading and verifying FFplay...', sticky=True)
        self.now.play_btn.configure(state='disabled')

        def work():
            try:
                from ..services.ffmpeg_setup import download_verified_archive, install_windows, local_bin
                archive = download_verified_archive()
                install_windows(archive, local_bin('win32'), filenames=('ffplay.exe',))
                paths.prepend_to_path(local_bin('win32'))
                self._post(('ffplay_installed', song))
            except Exception as exc:
                self._post(('ffplay_error', str(exc)))
        threading.Thread(target=work, daemon=True).start()

    # ------------------------------------------------------------------ main loop
    def _tick(self) -> None:
        if self.closed:
            return
        with self._lock:
            events, self._events = self._events, []
        for kind, data in events:
            if kind == 'scanned':
                self._library_loaded(data)
            elif kind == 'scan_error':
                self.scanning = False
                self.pages['library'].rescan_btn.configure(state='normal')
                self.refresh_player_pages()
                self.notify('Could not read the music folder: ' + data, sticky=True)
            elif kind == 'ffplay_installed':
                self.now.play_btn.configure(state='normal')
                self.notify('FFplay installed. Starting playback...')
                if self.player.queue:
                    self.player._start()
            elif kind == 'ffplay_error':
                self.now.play_btn.configure(state='normal')
                self.notify('FFplay installation failed: ' + data, sticky=True)
        self._check_compact()                  # catches a first size that arrived before the window mapped
        self.player.tick()
        self.now.update_position()
        self.now.update_play_state()
        self._timer = self.after(200, self._tick)

    def _on_close(self) -> None:
        if self.converter.busy:
            self.show_converter()
            messagebox.showinfo('Conversion in progress',
                                'A conversion is running. Press Cancel, wait for it to stop safely, then close Oggcultist.',
                                parent=self)
            return
        self.closed = True
        try:
            self.after_cancel(self._timer)
        except (tk.TclError, ValueError):
            pass
        self.player.shutdown()
        if getattr(self, '_og_anim', None) is not None:
            self._og_anim.stop()
        if getattr(self, 'media', None) is not None:
            self.media.stop()
        try:
            self.converter.persist()
            self.update_settings(volume=int(self.volume.get()), library=self.library_folder.get(),
                                 page=self.current_page if self.current_page != 'converter' else 'library',
                                 geometry=(self.settings.get('geometry') if self._embedded else
                                           self.geometry() if self.state() == 'normal' else self.settings.get('geometry')))
        except tk.TclError:
            pass
        self.destroy()


class OggcultistApp(_OggcultistUI, tk.Tk):
    """Original standalone Oggcultist 2.0.6, unchanged from the user's perspective."""


class OggcultistEmbeddedApp(_OggcultistUI, tk.Frame):
    """Real Oggcultist UI hosted inside Marble Oracle, sharing its Tk interpreter."""

    def __init__(self, master, startup_message: str = ''):
        super().__init__(startup_message, master=master, embedded=True)

    def deiconify(self):
        """Media key callbacks raise the parent window when in the suite."""
        self.winfo_toplevel().deiconify()

    def state(self):
        """Animation scheduler respects both the suite window and tab visibility."""
        if not self.winfo_ismapped():
            return 'withdrawn'
        return self.winfo_toplevel().state()

    def bind_all(self, sequence, func, add=None):
        """Oggcultist shortcuts act only while focus is inside this tab."""
        def only_here(event):
            target = event.widget
            while target is not None:
                if target is self:
                    return func(event)
                target = getattr(target, 'master', None)
            return None
        return super().bind_all(sequence, only_here, add=add)


def main(startup_message: str = '') -> None:
    try:
        OggcultistApp(startup_message=startup_message).mainloop()
    except tk.TclError as exc:
        raise SystemExit('Desktop display unavailable. Run with --cli on a headless system. ' + str(exc)) from exc
