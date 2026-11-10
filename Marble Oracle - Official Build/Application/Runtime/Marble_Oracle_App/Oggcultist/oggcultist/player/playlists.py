"""Named, ordered playlists stored atomically outside the music library.

File format (unchanged since v1.5, so older playlists load as-is)::

    {"format": 1, "playlists": {"Name": ["/absolute/path.opus", ...]}}
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from .. import paths


def playlist_file() -> Path:
    return paths.playlist_file()


class PlaylistStore:
    def __init__(self, path: Path | None = None):
        self.path = path or playlist_file()
        self.playlists: dict[str, list[str]] = {}
        if self.path.exists():
            try:
                raw = json.loads(self.path.read_text(encoding='utf-8'))
                if not isinstance(raw, dict) or raw.get('format') != 1 or not isinstance(raw.get('playlists'), dict):
                    raise ValueError('Unexpected playlist format')
                for name, entries in raw['playlists'].items():
                    if not isinstance(name, str) or not isinstance(entries, list) or any(not isinstance(v, str) for v in entries):
                        raise ValueError('Invalid playlist entry')
                    self.playlists[name] = list(dict.fromkeys(entries))
            except (OSError, UnicodeError, ValueError) as exc:
                raise ValueError(f'Could not read playlists at {self.path}: {exc}') from exc

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = json.dumps({'format': 1, 'playlists': self.playlists}, ensure_ascii=False, indent=2)
        fd, temp_path = tempfile.mkstemp(prefix='.playlists-', suffix='.json', dir=str(self.path.parent))
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_path, self.path)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    @staticmethod
    def _clean_name(name: str) -> str:
        name = name.strip()
        if not name or len(name) > 100:
            raise ValueError('Choose a playlist name between 1 and 100 characters.')
        return name

    def create(self, name: str) -> None:
        name = self._clean_name(name)
        if any(existing.casefold() == name.casefold() for existing in self.playlists):
            raise ValueError('A playlist with that name already exists.')
        self.playlists[name] = []
        self.save()

    def rename(self, old: str, new: str) -> str:
        new = self._clean_name(new)
        if old not in self.playlists:
            raise ValueError('That playlist no longer exists.')
        if new != old and any(n.casefold() == new.casefold() for n in self.playlists if n != old):
            raise ValueError('A playlist with that name already exists.')
        # Rebuild to keep insertion order stable for the renamed entry.
        self.playlists = {(new if n == old else n): v for n, v in self.playlists.items()}
        self.save()
        return new

    def delete(self, name: str) -> None:
        if name in self.playlists:
            del self.playlists[name]
            self.save()

    def add(self, name: str, paths: list[Path]) -> int:
        existing = self.playlists[name]
        count = 0
        for path in paths:
            key = str(path)
            if key not in existing:
                existing.append(key)
                count += 1
        if count:
            self.save()
        return count

    def remove(self, name: str, paths: list[Path]) -> int:
        entries = self.playlists[name]
        chosen = {str(p) for p in paths}
        count = len(entries) - len([p for p in entries if p not in chosen])
        if count:
            self.playlists[name] = [p for p in entries if p not in chosen]
            self.save()
        return count

    def move(self, name: str, paths: list[Path], delta: int) -> bool:
        """Move the chosen entries up (delta < 0) or down (delta > 0) as a block."""
        entries = self.playlists[name]
        chosen = {str(p) for p in paths}
        indices = [i for i, p in enumerate(entries) if p in chosen]
        if not indices or delta == 0:
            return False
        if (delta < 0 and indices[0] == 0) or (delta > 0 and indices[-1] == len(entries) - 1):
            return False
        moving = [entries[i] for i in indices]
        rest = [p for p in entries if p not in chosen]
        insert_at = max(0, min(len(rest), indices[0] + delta))
        self.playlists[name] = rest[:insert_at] + moving + rest[insert_at:]
        self.save()
        return True
