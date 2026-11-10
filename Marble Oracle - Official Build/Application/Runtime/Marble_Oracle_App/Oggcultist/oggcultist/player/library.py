"""Read-only music library scanning for the player.

The player never opens audio files for writing.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from mutagen import File as MutagenFile

AUDIO_EXTENSIONS = frozenset({'.opus', '.ogg', '.mp3', '.flac', '.m4a', '.aac', '.wav', '.aiff', '.wma', '.mp4'})


@dataclass(frozen=True)
class Song:
    path: Path
    title: str
    artist: str            # album artist: groups the Artists and Albums views
    album: str
    track: int = 0
    disc: int = 1
    duration: float = 0.0
    track_artist: str = ''  # per-track credit, including featured guests
    year: str = ''

    @property
    def display_artist(self) -> str:
        return self.track_artist or self.artist


def _first(tags, *keys) -> str:
    for key in keys:
        value = tags.get(key)
        if isinstance(value, (list, tuple)) and value:
            value = value[0]
        if value is not None and str(value).strip():
            return str(value).strip()
    return ''


def _number(raw: str, default: int) -> int:
    try:
        return int(raw.split('/')[0])
    except (ValueError, TypeError):
        return default


def read_song(path: Path) -> Song:
    """Read metadata only; never retag or open a source for writing."""
    tags = MutagenFile(str(path), easy=True)
    if tags is None:
        raise ValueError('Unrecognised audio format')
    title = _first(tags, 'title') or path.stem
    artist = _first(tags, 'albumartist', 'album artist', 'artist')
    album = _first(tags, 'album')
    if not artist and path.parent.parent != path.parent:
        # Oggcultist output: Album Artist / Year - Album / Track.opus.
        parent = path.parent.name
        if ' - ' in parent and len(parent.split(' - ', 1)[0]) >= 4:
            artist = path.parent.parent.name
    artist = artist or 'Unknown Artist'
    album = album or path.parent.name or 'Unknown Album'
    info = getattr(tags, 'info', None)
    duration = max(0.0, float(getattr(info, 'length', 0.0) or 0.0))
    year = (_first(tags, 'originaldate', 'date') or '')[:4]
    return Song(path=path, title=title, artist=artist, album=album,
                track=_number(_first(tags, 'tracknumber'), 0),
                disc=_number(_first(tags, 'discnumber'), 1), duration=duration,
                track_artist=_first(tags, 'artist'), year=year if year.isdigit() else '')


def scan_music_library(root: Path, cancelled: Callable[[], bool] | None = None) -> tuple[list[Song], list[str]]:
    """Recursively discover audio on a worker thread, without writing to root."""
    if not root.is_dir():
        raise ValueError('Choose an existing music folder.')
    songs: list[Song] = []
    errors: list[str] = []
    for parent, dirs, files in os.walk(root, followlinks=False):
        if cancelled and cancelled():
            break
        dirs[:] = [name for name in dirs if name != '.oggcultist' and not (Path(parent) / name).is_symlink()]
        for name in files:
            if cancelled and cancelled():
                break
            path = Path(parent) / name
            if path.suffix.lower() not in AUDIO_EXTENSIONS or path.is_symlink():
                continue
            try:
                songs.append(read_song(path))
            except (OSError, ValueError, TypeError, RuntimeError) as exc:
                errors.append(f'{path.name}: {exc}')
    songs.sort(key=lambda s: (s.artist.casefold(), s.album.casefold(), s.disc, s.track or 99999, s.title.casefold(), str(s.path)))
    return songs, errors


def embedded_picture(path: Path) -> bytes | None:
    """Return the first embedded cover image (Opus/Ogg, FLAC, MP3, M4A), read-only."""
    try:
        audio = MutagenFile(str(path))
    except Exception:
        return None
    if audio is None:
        return None
    try:
        pictures = getattr(audio, 'pictures', None)
        if pictures:
            return bytes(pictures[0].data)
        tags = audio.tags
        if tags is None:
            return None
        if hasattr(tags, 'getall'):  # ID3
            frames = tags.getall('APIC')
            return bytes(frames[0].data) if frames else None
        values = tags.get('metadata_block_picture') or tags.get('METADATA_BLOCK_PICTURE')
        if values:
            import base64
            from mutagen.flac import Picture
            return bytes(Picture(base64.b64decode(values[0])).data)
        covers = tags.get('covr')
        if covers:
            return bytes(covers[0])
    except Exception:
        return None
    return None
