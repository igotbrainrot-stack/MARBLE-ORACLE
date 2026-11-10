"""Music player screens: the playback controller and the library pages.

The now-playing bar lives in ``now_playing.py`` (split out in 2.0).
"""
from __future__ import annotations

import io
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk
from typing import TYPE_CHECKING, Callable

from ..player import (REPEAT_LABELS, REPEAT_MODES, FFplayTransport, PlayerError, PlayOrder, Song, album_of,
                      album_sort_key, embedded_picture, find_ffplay)
from . import design_system as ds
from .theme import PALETTE
from .widgets import TrackTable, section_label

if TYPE_CHECKING:  # pragma: no cover
    from .app import OggcultistApp

# Stretchable columns start narrow and grow to fill: Treeview never shrinks a
# column below its initial width, so generous widths would clip the last column.
SONG_COLUMNS = (
    ('pos', '', 40, False, 'center'),
    ('title', 'Title', 180, True, 'w'),
    ('artist', 'Artist', 120, True, 'w'),
    ('album', 'Album', 120, True, 'w'),
    ('time', 'Time', 64, False, 'e'),
)
PLAYING_MARK = '▶'


def duration_label(seconds: float) -> str:
    seconds = max(0, int(seconds))
    if seconds >= 3600:
        return f'{seconds // 3600}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}'
    return f'{seconds // 60}:{seconds % 60:02d}'


def shorten(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:max(1, limit - 1)].rstrip() + '...'


def fit_text(text: str, font, width: int, widget=None) -> str:
    """``text`` cut so that, drawn in ``font``, it fits in ``width`` pixels, ending in "...".

    A width of 1 or less means "not laid out yet": the text is returned whole.
    """
    if width <= 1:
        return text
    from tkinter import font as tkfont
    if isinstance(font, str):
        font = tkfont.nametofont(font, root=widget)
    if font.measure(text) <= width:
        return text
    low, high = 0, len(text)                  # longest prefix that fits with the "..."
    while low < high:
        middle = (low + high + 1) // 2
        if font.measure(text[:middle].rstrip() + '...') <= width:
            low = middle
        else:
            high = middle - 1
    return text[:low].rstrip() + '...' if low else '...'


def default_transport():
    """The smooth engine (FFmpeg → Oggcultist → FFplay) when FFmpeg is present, else FFplay alone."""
    from ..player.stream import StreamTransport, find_ffmpeg
    return StreamTransport() if find_ffmpeg() else FFplayTransport()


def click_to_set(scale, on_press=None, on_drag=None, on_release=None) -> None:
    """Clicking anywhere on a slider jumps straight there, and dragging follows the pointer.

    Tk's default only nudges the value a step at a time towards a click on the track.
    v1.9.0's :class:`~oggcultist.gui.sliders.GradientSlider` does this itself; it just takes
    the callbacks.
    """
    from .sliders import GradientSlider
    if isinstance(scale, GradientSlider):
        scale.on_press, scale.on_drag, scale.on_release = on_press, on_drag, on_release
        return
    def value_at(event) -> float:
        low, high = float(scale.cget('from')), float(scale.cget('to'))
        try:
            value = float(scale.get(event.x, event.y))
        except (tk.TclError, ValueError):
            width = max(1, scale.winfo_width())
            value = low + (high - low) * event.x / width
        return max(min(low, high), min(max(low, high), value))

    def press(event):
        scale.state(['pressed'])
        scale.set(value_at(event))
        if on_press:
            on_press()
        if on_drag:
            on_drag()
        return 'break'

    def drag(event):
        scale.set(value_at(event))
        if on_drag:
            on_drag()
        return 'break'

    def release(event):
        scale.state(['!pressed'])
        scale.set(value_at(event))
        if on_release:
            on_release()
        return 'break'

    scale.bind('<ButtonPress-1>', press)
    scale.bind('<B1-Motion>', drag)
    scale.bind('<ButtonRelease-1>', release)


# --------------------------------------------------------------------------- playback
class PlayerController:
    """Owns the FFplay transport and the play order. Independent of any page."""

    def __init__(self, app: 'OggcultistApp', transport: FFplayTransport | None = None):
        self.app = app
        self.transport = transport or default_transport()
        self.order = PlayOrder(album_lookup=self._album_tracks)
        settings = getattr(app, 'settings', {}) or {}
        self.order.set_shuffle(bool(settings.get('shuffle', False)))
        mode = settings.get('repeat', 'off')
        self.order.set_repeat(mode if mode in REPEAT_MODES else 'off')
        self._pending: Song | None = None

    # The queue as before, for callers that only need the list and position.
    @property
    def queue(self) -> list[Song]:
        return self.order.songs

    @property
    def index(self) -> int:
        return self.order.index

    @property
    def song(self) -> Song | None:
        return self.transport.song

    def current_path(self) -> str | None:
        return str(self.transport.song.path) if self.transport.song else None

    def _album_tracks(self, song: Song) -> list[Song]:
        key = album_of(song)
        return sorted((s for s in getattr(self.app, 'songs', []) if album_of(s) == key), key=album_sort_key)

    # ------------------------------------------------------------------ modes
    @property
    def shuffle(self) -> bool:
        return self.order.shuffle

    @property
    def repeat(self) -> str:
        return self.order.repeat

    def set_shuffle(self, on: bool) -> None:
        self.order.set_shuffle(on)
        self._modes_changed('Shuffle on' if on else 'Shuffle off')

    def toggle_shuffle(self) -> None:
        self.set_shuffle(not self.order.shuffle)

    def note_selected(self, song: Song | None) -> None:
        """The song the user last selected in a list (or started): what Loop Album locks onto."""
        if song is not None:
            self.last_selected = song

    def set_repeat(self, mode: str) -> None:
        playing = self.transport.song or self.order.current
        selected = getattr(self, 'last_selected', None)
        # Loop Album: the album of the last song selected; Loop One: the song playing
        anchor = (selected or playing) if mode == 'album' else (playing or selected)
        self.order.set_repeat(mode, anchor)
        message = REPEAT_LABELS[mode]
        if mode == 'album' and self.order.loop_album:
            message += f': only “{self.order.locked_album}” will play until you change this'
            if playing is not None and all(s.path != playing.path for s in self.order.loop_album):
                message += ' (it starts when this song ends)'
        elif mode == 'one' and self.order.loop_song is not None:
            message += f': “{self.order.loop_song.title}” repeats; ⏭ and ⏮ go back to its start'
        elif mode in ('album', 'one'):
            message += ': it locks onto the next song you play'
        self._modes_changed(message)

    def cycle_repeat(self) -> None:
        self.set_repeat(REPEAT_MODES[(REPEAT_MODES.index(self.order.repeat) + 1) % len(REPEAT_MODES)])

    def _modes_changed(self, message: str) -> None:
        self.app.update_settings(shuffle=self.order.shuffle, repeat=self.order.repeat)
        now = getattr(self.app, 'now', None)
        if now is not None:
            now.update_modes()
        if hasattr(self.app, 'publish_media_state'):
            self.app.publish_media_state()
        self.app.notify(message)

    # ------------------------------------------------------------------ playing
    def play_list(self, songs: list[Song], index: int = 0) -> None:
        if not songs:
            self.app.notify('Nothing to play here yet.')
            return
        self.order.load(songs, index)
        self.note_selected(self.order.current)
        self._start()

    def _start(self) -> None:
        song = self.order.current
        if song is None:
            return
        if not find_ffplay():
            self.app.offer_ffplay(song)
            return
        previous = self.current_path()
        try:
            self.transport.volume = int(self.app.volume.get())
            self.transport.play(song)
        except PlayerError as exc:
            self.app.notify(f'Could not play {song.path.name}: {exc}')
            self.app.on_song_changed(previous, None)
            return
        self.app.on_song_changed(previous, song)

    def toggle(self) -> None:
        if self.transport.playing:
            self.transport.pause()
            self.app.on_play_state()
        elif self.transport.paused and self.transport.song:
            try:
                self.transport.resume()
            except PlayerError as exc:
                self.app.notify(f'Cannot resume: {exc}')
            self.app.on_play_state()
        elif self.order.current is not None:
            self._start()
        else:
            self.app.play_current_selection()

    def stop(self) -> None:
        previous = self.current_path()
        self.transport.stop()
        self.app.on_song_changed(previous, None)

    def next(self) -> None:
        if self.order.next(manual=True) is not None:
            self._start()
        else:
            self.stop()
            self.app.notify('End of the play queue.')

    def _finished(self) -> None:
        """A song played to its end: follow shuffle and repeat."""
        if self.order.next(manual=False) is not None:
            self._start()
        else:
            self.stop()
            self.app.notify('End of the play queue.')

    def previous(self) -> None:
        if self.transport.song and self.transport.current_position() > 3:
            self.seek(0)
        elif self.order.previous() is not None:
            self._start()

    # ------------------------------------------------------------------ fast-forward
    FAST_FORWARD = (4.0, 8.0)       # first speed while held, then faster after a while

    @property
    def fast_forwarding(self) -> bool:
        return getattr(self.transport, 'speed', 1.0) > 1.0

    def start_fast_forward(self, level: int = 0) -> bool:
        """Play the current song sped up (audible) until stop_fast_forward()."""
        if not self.transport.playing or self.transport.song is None or self.transport.paused:
            return False
        speed = self.FAST_FORWARD[min(level, len(self.FAST_FORWARD) - 1)]
        try:
            self.transport.set_speed(speed)
        except PlayerError as exc:
            self.app.notify(f'Cannot fast-forward: {exc}')
            return False
        self.app.notify(f'⏩ Fast-forwarding at {speed:g}×', sticky=True)
        return True

    def stop_fast_forward(self) -> None:
        if not self.fast_forwarding:
            # e.g. the song ran out while held: just clear the fast-forward message
            status = getattr(self.app, 'status', None)
            if status is not None and '⏩' in status.get():
                self.app.notify('Normal speed')
            return
        try:
            self.transport.set_speed(1.0)
        except PlayerError as exc:
            self.app.notify(f'Cannot return to normal speed: {exc}')
            return
        self.app.notify('Normal speed')

    def seek(self, seconds: float) -> None:
        if not self.transport.song:
            return
        try:
            self.transport.seek(seconds)
        except PlayerError as exc:
            self.app.notify(f'Cannot seek: {exc}')

    def set_volume(self, value: int) -> None:
        try:
            self.transport.set_volume(value)
        except PlayerError as exc:
            self.app.notify(f'Cannot change volume: {exc}')

    VOLUME_STEP_MS = 120     # at most one FFplay restart per this interval while dragging

    def request_volume(self, value: int) -> None:
        if getattr(self.transport, 'live_volume', False):
            self.transport.set_volume(int(value))     # applied to the audio as it plays: smooth
            return
        self._request_volume_by_restart(value)

    def _request_volume_by_restart(self, value: int) -> None:
        """Follow the volume slider live. FFplay sets volume only at start-up, so each change
        starts a new FFplay (gap-free handoff); requests are paced so a drag never piles up
        restarts: the latest value wins, and a new one waits until the last has taken over."""
        self._volume_target = int(value)
        if getattr(self, '_volume_job', None) is None:
            self._volume_job = self.app.after(0, self._volume_step)

    def _volume_step(self) -> None:
        import time
        self._volume_job = None
        target = getattr(self, '_volume_target', None)
        if target is None:
            return
        transport = self.transport
        waited = time.monotonic() - getattr(self, '_volume_last', 0.)
        starting = getattr(transport, '_pending', None) is not None
        if starting or waited < self.VOLUME_STEP_MS / 1000:
            self._volume_job = self.app.after(40, self._volume_step)
            return
        self._volume_target = None
        if transport.volume != target:
            self._volume_last = time.monotonic()
            self.set_volume(target)

    def tick(self) -> None:
        if self.transport.poll_end():
            code = self.transport.last_returncode
            if code not in (None, 0):
                failed = self.order.current.path.name if self.order.current else 'this file'
                self.stop()
                detail = getattr(self.transport, 'last_error', '')
                self.app.notify(f'Playback of {failed} failed (FFplay exit code {code})'
                                + (f': {detail}' if detail else '.'))
            else:
                self._finished()

    def shutdown(self) -> None:
        stop_now = getattr(self.transport, 'shutdown', None)     # immediate, waits for the processes
        (stop_now or self.transport.stop)()


# --------------------------------------------------------------------------- now playing
# --------------------------------------------------------------------------- pages
class SongPage(ttk.Frame):
    """Common behaviour for pages that show a song table."""
    title = ''
    numbered = False

    def __init__(self, parent, app: 'OggcultistApp'):
        super().__init__(parent, padding=ds.PAGE_PADDING)
        self.app = app
        self.shown: list[Song] = []
        self.row_for_path: dict[str, str] = {}
        self.table: TrackTable | None = None

    # The page's song table must exist before these are used.
    def make_table(self, parent, empty_text: str) -> TrackTable:
        self.table = TrackTable(parent, SONG_COLUMNS, empty_text=empty_text,
                                on_activate=self.play_selected, on_context=self.context_menu)
        self.table.tree.bind('<<TreeviewSelect>>', lambda _e: self._note_selection(), add='+')
        return self.table

    def _note_selection(self) -> None:
        """Tell the player which song was selected last (the clicked row if several are)."""
        tree = self.table.tree
        chosen = tree.selection()
        focus = tree.focus()
        iid = focus if focus in chosen else (chosen[-1] if chosen else '')
        if iid.isdigit() and int(iid) < len(self.shown):
            self.app.player.note_selected(self.shown[int(iid)])

    def populate(self, songs: list[Song]) -> None:
        self.shown = list(songs)
        self.row_for_path = {}
        playing = self.app.player.current_path()
        rows = []
        for index, song in enumerate(self.shown):
            iid = str(index)
            key = str(song.path)
            self.row_for_path.setdefault(key, iid)
            is_playing = key == playing
            rows.append((iid, (self._mark(song, is_playing), song.title, song.display_artist, song.album,
                               duration_label(song.duration)), ('playing',) if is_playing else ()))
        self.table.set_rows(rows)

    def _mark(self, song: Song, playing: bool) -> str:
        if playing:
            return PLAYING_MARK
        return str(song.track) if self.numbered and song.track else ''

    def mark_playing(self, old: str | None, new: str | None) -> None:
        if self.table is None:
            return
        tree = self.table.tree
        for key, playing in ((old, False), (new, True)):
            iid = self.row_for_path.get(key or '')
            if iid and tree.exists(iid):
                song = self.shown[int(iid)]
                values = list(tree.item(iid, 'values'))
                values[0] = self._mark(song, playing)
                tags = [t for t in tree.item(iid, 'tags') if t != 'playing'] + (['playing'] if playing else [])
                tree.item(iid, values=values, tags=tags)

    def selected_songs(self) -> list[Song]:
        if self.table is None:
            return []
        return [self.shown[int(i)] for i in self.table.selection() if i.isdigit() and int(i) < len(self.shown)]

    def play_selected(self) -> None:
        if self.table is None:
            return
        chosen = self.table.selection()
        if not chosen:
            self.app.notify('Select a song first.')
            return
        selected = [int(i) for i in chosen if i.isdigit() and int(i) < len(self.shown)]
        if not selected:
            return
        if len(selected) > 1:
            self.app.player.play_list([self.shown[i] for i in sorted(selected)], 0)
        else:
            self.app.player.play_list(self.shown, selected[0])

    def play_all(self) -> None:
        self.app.player.play_list(self.shown, 0)

    def shuffle_all(self) -> None:
        """Turn shuffle on and play everything shown."""
        if not self.app.player.shuffle:
            self.app.player.set_shuffle(True)
        self.play_all()

    def context_menu(self, event) -> None:
        songs = self.selected_songs()
        if not songs:
            return
        menu = tk.Menu(self, tearoff=False)
        menu.add_command(label='Play', command=self.play_selected)
        add_menu = tk.Menu(menu, tearoff=False)
        self.app.fill_playlist_menu(add_menu, lambda: self.selected_songs())
        menu.add_cascade(label='Add to playlist', menu=add_menu)
        self.extra_context_items(menu)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def extra_context_items(self, menu: tk.Menu) -> None:
        pass

    def add_menu_button(self, parent) -> ttk.Menubutton:
        button = ttk.Menubutton(parent, text='Add to playlist', style='TButton')
        menu = tk.Menu(button, tearoff=False,
                       postcommand=lambda: self.app.fill_playlist_menu(menu, self.selected_songs))
        button.configure(menu=menu)
        return button

    def matches(self, song: Song, query: str) -> bool:
        return not query or query in f'{song.title} {song.display_artist} {song.artist} {song.album}'.casefold()

    def refresh(self) -> None:  # pragma: no cover - implemented by subclasses
        raise NotImplementedError

    def focus_content(self) -> None:
        if self.table is not None:
            self.table.tree.focus_set()


def header(page: ttk.Frame, title: str, subtitle_var: tk.StringVar | None = None) -> ttk.Frame:
    bar = ttk.Frame(page)
    bar.pack(fill='x', pady=(0, ds.SPACE['l']))
    titles = ttk.Frame(bar)
    titles.pack(side='left', fill='x', expand=True)
    ttk.Label(titles, text=title, style='Title.TLabel').pack(anchor='w')
    if subtitle_var is not None:
        ttk.Label(titles, textvariable=subtitle_var, style='Muted.TLabel').pack(anchor='w')
    actions = ttk.Frame(bar)
    actions.pack(side='right', anchor='s')
    return actions


class LibraryPage(SongPage):
    title = 'Library'

    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.subtitle = tk.StringVar(value='No music folder chosen yet')
        header(self, 'Library', self.subtitle)
        tools = ttk.Frame(self)
        tools.pack(fill='x', pady=(0, ds.SPACE['m']))
        self.play_all_btn = ttk.Button(tools, text='▶  Play all', style='Accent.TButton', command=self.play_all)
        self.play_all_btn.pack(side='left')
        self.shuffle_all_btn = ttk.Button(tools, text='Shuffle', command=self.shuffle_all)
        self.shuffle_all_btn.pack(side='left', padx=(ds.SPACE['s'], 0))
        self.add_menu_button(tools).pack(side='left', padx=(ds.SPACE['s'], 0))
        self.folder_btn = ttk.Button(tools, text='Choose music folder...', command=app.choose_library)
        self.folder_btn.pack(side='right')
        self.rescan_btn = ttk.Button(tools, text='Rescan', style='Ghost.TButton', command=app.rescan_library)
        self.rescan_btn.pack(side='right', padx=(0, ds.SPACE['s']))
        self.make_table(self, 'Your music library is empty.\n\nChoose a music folder above to see your tracks here.').pack(fill='both', expand=True)

    def refresh(self) -> None:
        query = self.app.search_query()
        songs = [s for s in self.app.songs if self.matches(s, query)]
        self.populate(songs)
        folder = self.app.library_folder.get()
        if self.app.scanning:
            self.subtitle.set(f'Reading {folder}...')
        elif folder:
            shown = f'{len(songs)} of {len(self.app.songs)}' if query else f'{len(self.app.songs)}'
            self.subtitle.set(f'{shown} songs  ·  {folder}')
        else:
            self.subtitle.set('No music folder chosen yet')
        # one primary action at a time: with no music, choosing a folder is the thing to do
        self.folder_btn.configure(style='TButton' if self.app.songs else 'Accent.TButton')
        for button in (self.play_all_btn, self.shuffle_all_btn):
            button.configure(state='normal' if songs else 'disabled')


# Artists, Albums and Playlists moved to collection_pages.py in 2.0; re-exported for callers.
from .collection_pages import AlbumsPage, ArtistsPage, PlaylistsPage, _ListAndSongsPage  # noqa: E402,F401
