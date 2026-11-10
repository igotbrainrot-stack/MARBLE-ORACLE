"""Play order: the queue, shuffle, and repeat (off / all / album / one).

Pure Python (no Tk, no FFplay) so every rule can be tested directly.

- **Shuffle** plays every song in scope once, in random order, before any song repeats.
- **Repeat off**: stop after the last song.
- **Repeat all**: start the queue again (a fresh shuffle if shuffle is on).
- **Repeat album**: keep playing one album, all of its tracks from the library, in track
  order (or shuffled). The album is locked when repeat album is switched on: the GUI
  passes the last song the user selected (or started), and it stays that album whatever
  else you play, until repeat is changed.
- **Repeat one**: the song playing when repeat one is switched on is locked: when it ends
  it starts again, and Next / Previous also just return to its start. Nothing moves on to
  another song until repeat is changed.
- **Previous** goes back through the songs actually played, so it works with shuffle.
"""
from __future__ import annotations

import random
from typing import Callable

from .library import Song

REPEAT_MODES = ('off', 'all', 'album', 'one')
REPEAT_LABELS = {'off': 'Repeat off', 'all': 'Repeat all', 'album': 'Repeat album', 'one': 'Repeat this song'}


def album_of(song: Song) -> tuple[str, str]:
    return song.artist.casefold(), song.album.casefold()


def album_sort_key(song: Song):
    return song.disc, song.track or 99999, song.title.casefold()


class PlayOrder:
    def __init__(self, album_lookup: Callable[[Song], list[Song]] | None = None,
                 rng: random.Random | None = None):
        self.album_lookup = album_lookup
        self.rng = rng or random.Random()
        self.songs: list[Song] = []
        self.current: Song | None = None
        self.shuffle = False
        self.repeat = 'off'
        self.history: list[Song] = []
        self._played: set = set()       # songs already heard in this shuffle pass
        self.loop_song: Song | None = None          # locked by repeat one
        self.loop_album: list[Song] | None = None   # locked by repeat album

    # ------------------------------------------------------------------ setup
    def load(self, songs: list[Song], index: int = 0) -> Song | None:
        self.songs = list(songs)
        self.history = []
        self.current = self.songs[max(0, min(index, len(self.songs) - 1))] if self.songs else None
        self._played = {self.current.path} if self.current else set()
        self._lock_if_needed()
        return self.current

    @property
    def index(self) -> int:
        """Position of the current song in the queue, or -1."""
        if self.current is None:
            return -1
        for i, song in enumerate(self.songs):
            if song.path == self.current.path:
                return i
        return -1

    def set_shuffle(self, on: bool) -> None:
        self.shuffle = bool(on)
        self._played = {self.current.path} if self.current else set()

    def set_repeat(self, mode: str, anchor: Song | None = None) -> None:
        """Change repeat mode. Repeat one / album lock onto ``anchor`` (default: the current song)."""
        if mode not in REPEAT_MODES:
            raise ValueError(f'Unknown repeat mode: {mode}')
        if (mode == 'album') != (self.repeat == 'album'):
            self._played = {self.current.path} if self.current else set()
        self.repeat = mode
        self.loop_song = None
        self.loop_album = None
        self._lock_if_needed(anchor)

    def _lock_if_needed(self, anchor: Song | None = None) -> None:
        anchor = anchor or self.current
        if anchor is None:
            return                      # nothing playing yet: lock onto the first song that plays
        if self.repeat == 'one' and self.loop_song is None:
            self.loop_song = anchor
        elif self.repeat == 'album' and self.loop_album is None:
            if self.album_lookup is not None:
                album = list(self.album_lookup(anchor))
            else:
                album = sorted((s for s in self.songs if album_of(s) == album_of(anchor)), key=album_sort_key)
            if not any(s.path == anchor.path for s in album):
                album.append(anchor)
            self.loop_album = album

    @property
    def locked_album(self) -> str:
        return self.loop_album[0].album if self.loop_album else ''

    def cycle_repeat(self, anchor: Song | None = None) -> str:
        self.set_repeat(REPEAT_MODES[(REPEAT_MODES.index(self.repeat) + 1) % len(REPEAT_MODES)], anchor)
        return self.repeat

    # ------------------------------------------------------------------ scope
    def scope(self) -> list[Song]:
        """The songs the next choice is made from."""
        if self.repeat == 'album':
            self._lock_if_needed()
            if self.loop_album is not None:
                return self.loop_album
        return self.songs

    @staticmethod
    def _find(songs: list[Song], song: Song) -> int:
        for i, candidate in enumerate(songs):
            if candidate.path == song.path:
                return i
        return -1

    # ------------------------------------------------------------------ moving
    def next(self, manual: bool) -> Song | None:
        """The song to play after the current one; None means stop.

        ``manual`` is True for the Next button, False when a song finished by itself.
        """
        current = self.current
        if current is None:
            return None
        if self.repeat == 'one':
            # natural end, Next and Previous alike: back to the start of the locked song
            self._lock_if_needed()
            target = self.loop_song or current
            if target.path != current.path:
                self.history.append(current)
                self.current = target
                self._played.add(target.path)
            return target
        wrap = self.repeat in ('all', 'album')
        scope = self.scope()
        if not scope:
            return None
        if self.shuffle:
            choice = self._shuffle_pick(scope, wrap)
        else:
            i = self._find(scope, current)
            if i + 1 < len(scope):
                choice = scope[i + 1]
            elif wrap:
                choice = scope[0]
            else:
                choice = None
        if choice is not None:
            self.history.append(current)
            del self.history[:-200]
            self.current = choice
            self._played.add(choice.path)
        return choice

    def _shuffle_pick(self, scope: list[Song], wrap: bool) -> Song | None:
        current = self.current
        remaining = [s for s in scope if s.path not in self._played and s.path != current.path]
        if not remaining:
            if not wrap:
                return None
            # A new pass: every song is due again (including the one just heard, later on),
            # but the next pick is never the song that just played.
            self._played = set()
            remaining = [s for s in scope if s.path != current.path] or [current]
        return self.rng.choice(remaining)

    def previous(self) -> Song | None:
        """The song before the current one: the last one played, else the queue order."""
        current = self.current
        if current is None:
            return None
        if self.repeat == 'one':
            self._lock_if_needed()
            self.current = self.loop_song or current
            return self.current
        if self.history:
            choice = self.history.pop()
        else:
            scope = self.scope()
            i = self._find(scope, current)
            if i > 0:
                choice = scope[i - 1]
            elif self.repeat != 'off' and scope:
                choice = scope[-1]
            else:
                choice = scope[0] if scope else None
        if choice is not None:
            self.current = choice
            self._played.add(choice.path)
        return choice

    def jump(self, song: Song) -> None:
        """The user picked a song directly (e.g. double-click within the queue)."""
        if self.current is not None and self.current.path != song.path:
            self.history.append(self.current)
        self.current = song
        self._played.add(song.path)
        self._lock_if_needed()
