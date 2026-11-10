"""Album art editor: change the colour and text of the covers Oggcultist generated.

Only covers that Oggcultist drew itself, inside files it converted, are ever changed:

- the library must have Oggcultist's database (``.oggcultist/library.sqlite3``);
- the album folder must be one the converter bound a cover to (``folder_covers``);
- each file must be in the completion ledger with matching size (and checksum, when
  recorded), and its embedded cover must be the album's generated solid-colour cover.

Anything else (real cover photos, files from elsewhere, edited files) is listed as
skipped and left alone. For each eligible file the cover is replaced on a temporary
copy, and the copy is checked before it replaces the original:

- the decoded audio is bit-identical (FFmpeg MD5 of the decoded stream);
- every other tag is unchanged;
- the new cover is a valid 600 × 600 PNG.

Then the ledger is updated with the new size and checksum, so the converter still
recognises the file as its own finished output.

The new design is saved first; if anything stops part-way, applying again finishes
the job (files that already carry the new cover are skipped). Original source music
is never involved.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import random
import re
import sqlite3
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from mutagen.flac import Picture

from ..services.tools import no_window_kwargs
from .artwork import draw_cover, picture_comment

DB_RELATIVE = Path('.oggcultist') / 'library.sqlite3'
HEX = re.compile(r'^#?[0-9A-Fa-f]{6}$')


class CoverEditError(RuntimeError):
    pass


def normalise_colour(value: str) -> str:
    value = (value or '').strip()
    if not HEX.match(value):
        raise CoverEditError(f'"{value}" is not a colour. Use six hex digits, like #C0392B.')
    return value.lstrip('#').upper()


@dataclass
class CoverDesign:
    colour: str                      # 'RRGGBB'
    lines: list[str]                 # up to three lines of text; blank lines are left out
    ink: str = 'auto'                # 'auto' (black or white for contrast) or 'RRGGBB'

    def png(self, album: str = '', artist: str = '', year: str = '') -> bytes:
        try:
            return draw_cover(album, artist, year, self.colour, lines=self.lines, ink=self.ink)
        except ValueError as exc:
            raise CoverEditError(str(exc)) from exc
        except RuntimeError as exc:
            from .artwork import _font_has_text, find_serif_font
            font = find_serif_font()
            missing = sorted({ch for line in self.lines for ch in line
                              if not ch.isspace() and not _font_has_text(font, ch)})
            shown = ' '.join(missing[:8]) if missing else ''
            raise CoverEditError('The cover font can\'t draw ' + (f'these characters: {shown}. ' if shown else
                                 'some of this text. ') + 'Remove them, or install Noto Serif fonts.') from exc


@dataclass
class EditableAlbum:
    folder: Path
    folder_name: str                 # the converter's key: relative path, case-folded
    album_key: str
    album: str
    artist: str
    year: str
    design: CoverDesign
    customised: bool                 # text or ink was changed in the editor before
    file_count: int

    @property
    def label(self) -> str:
        return f'{self.album} — {self.artist}'

    def default_lines(self) -> list[str]:
        return [self.album or 'Unknown Album', self.artist or 'Unknown Album Artist', self.year or 'Unknown Year']


@dataclass
class ApplyPlan:
    album: EditableAlbum
    design: CoverDesign
    eligible: list[Path] = field(default_factory=list)
    already: list[Path] = field(default_factory=list)          # already carry the new cover
    skipped: list[tuple[Path, str]] = field(default_factory=list)
    colour_note: str = ''                                      # e.g. colour nudged to stay unique


@dataclass
class ApplyResult:
    updated: list[Path] = field(default_factory=list)
    already: list[Path] = field(default_factory=list)
    skipped: list[tuple[Path, str]] = field(default_factory=list)
    failed: list[tuple[Path, str]] = field(default_factory=list)


# ---------------------------------------------------------------------------- helpers
def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def _embedded_picture(path: Path):
    from mutagen.oggopus import OggOpus
    values = OggOpus(path).get('metadata_block_picture', [])
    if len(values) != 1:
        return None
    return Picture(base64.b64decode(values[0]))


def _picture_colour(picture) -> str | None:
    """The colour of a generated cover (solid background), or None if it isn't one."""
    from PIL import Image
    try:
        if picture.mime != 'image/png':
            return None
        with Image.open(io.BytesIO(picture.data)) as im:
            if im.size != (600, 600):
                return None
            rgb = im.convert('RGB')
            corners = {rgb.getpixel(p) for p in ((0, 0), (599, 0), (0, 599), (599, 599), (300, 4))}
            if len(corners) != 1:
                return None          # not a flat generated background: treat as real artwork
            return ''.join(f'{n:02X}' for n in corners.pop())
    except Exception:
        return None


def _tags_without_picture(path: Path) -> dict:
    from mutagen.oggopus import OggOpus
    tags = OggOpus(path).tags or {}
    return {k.lower(): list(v) for k, v in tags.items() if k.lower() != 'metadata_block_picture'}


def _audio_md5(path: Path) -> str:
    result = subprocess.run(['ffmpeg', '-hide_banner', '-nostdin', '-v', 'error', '-i', str(path),
                             '-map', '0:a:0', '-f', 'md5', '-'], capture_output=True, text=True,
                            timeout=600, **no_window_kwargs())
    if result.returncode or 'MD5=' not in result.stdout:
        raise CoverEditError('Could not decode the audio to verify it: ' + (result.stderr or '')[-300:])
    return result.stdout.strip().split('MD5=')[-1]


# ---------------------------------------------------------------------------- the editor
class CoverEditor:
    """Lists editable albums in one Oggcultist library and applies new cover designs."""

    def __init__(self, library: Path):
        self.root = Path(library).resolve()
        self.db_path = self.root / DB_RELATIVE

    @property
    def available(self) -> bool:
        return self.db_path.is_file()

    def _connect(self) -> sqlite3.Connection:
        if not self.available:
            raise CoverEditError('This folder has no Oggcultist library database. Covers can only be '
                                 'edited in a library made by Oggcultist\'s converter.')
        db = sqlite3.connect(self.db_path, timeout=10)
        db.execute('PRAGMA busy_timeout=5000')
        db.execute('CREATE TABLE IF NOT EXISTS cover_designs ('
                   'album_key TEXT PRIMARY KEY, lines TEXT NOT NULL, ink TEXT NOT NULL)')
        return db

    def _folders(self) -> dict[str, Path]:
        """Album folders (Artist/Album) by their case-folded relative path."""
        found = {}
        for artist in sorted(p for p in self.root.iterdir() if p.is_dir() and not p.name.startswith('.')):
            for album in sorted(p for p in artist.iterdir() if p.is_dir()):
                found[album.relative_to(self.root).as_posix().casefold()] = album
        return found

    # ------------------------------------------------------------------ listing
    def albums(self) -> list[EditableAlbum]:
        if not self.available:
            return []
        from mutagen.oggopus import OggOpus
        db = self._connect()
        try:
            bindings = db.execute('SELECT folder, album_key FROM folder_covers').fetchall()
            colours = dict(db.execute('SELECT album_key, colour FROM covers').fetchall())
            designs = {k: (lines, ink) for k, lines, ink in
                       db.execute('SELECT album_key, lines, ink FROM cover_designs').fetchall()}
        finally:
            db.close()
        folders = self._folders()
        result = []
        for folder_name, album_key in bindings:
            folder = folders.get(folder_name)
            if folder is None or album_key not in colours:
                continue
            files = sorted(folder.glob('*.opus'))
            if not files:
                continue
            album = artist = year = ''
            for path in files:
                try:
                    tags = OggOpus(path)
                except Exception:
                    continue
                first = lambda key: (tags.get(key) or [''])[0]
                album, artist = first('album'), first('albumartist') or first('artist')
                year = first('originalyear') or first('date')[:4]
                break
            entry = EditableAlbum(folder, folder_name, album_key, album or folder.name, artist or folder.parent.name,
                                  year, CoverDesign(colours[album_key], []), album_key in designs, len(files))
            if album_key in designs:
                lines, ink = designs[album_key]
                try:
                    entry.design.lines = [str(x) for x in json.loads(lines)][:3]
                except (ValueError, TypeError):
                    entry.design.lines = entry.default_lines()
                entry.design.ink = ink or 'auto'
            else:
                entry.design.lines = entry.default_lines()
            result.append(entry)
        result.sort(key=lambda a: (a.album.casefold(), a.artist.casefold()))
        return result

    # ------------------------------------------------------------------ colours
    def colour_owner(self, colour: str, except_key: str = '') -> str | None:
        """The album key already using ``colour``, if any (colours are unique per album)."""
        db = self._connect()
        try:
            row = db.execute('SELECT album_key FROM covers WHERE colour=? AND album_key<>?',
                             (normalise_colour(colour), except_key)).fetchone()
        finally:
            db.close()
        return row[0] if row else None

    def owner_label(self, album_key: str | None) -> str:
        """A readable name ('Artist / Year - Album') for an album key, or ''."""
        if not album_key:
            return ''
        db = self._connect()
        try:
            row = db.execute('SELECT folder FROM folder_covers WHERE album_key=?', (album_key,)).fetchone()
        finally:
            db.close()
        if not row:
            return 'another album'
        folder = self._folders().get(row[0])
        return folder.relative_to(self.root).as_posix().replace('/', ' / ') if folder else row[0]

    def free_colour(self, colour: str, except_key: str = '') -> str:
        """``colour`` if unused, else the closest unused shade (differs by one step per channel)."""
        colour = normalise_colour(colour)
        db = self._connect()
        try:
            taken = {c for (c,) in db.execute('SELECT colour FROM covers WHERE album_key<>?', (except_key,))}
        finally:
            db.close()
        if colour not in taken:
            return colour
        r, g, b = (int(colour[i:i + 2], 16) for i in (0, 2, 4))
        for distance in range(1, 6):
            for dr in range(-distance, distance + 1):
                for dg in range(-distance, distance + 1):
                    for db_ in range(-distance, distance + 1):
                        if max(abs(dr), abs(dg), abs(db_)) != distance:
                            continue
                        candidate = (r + dr, g + dg, b + db_)
                        if all(0 <= c <= 255 for c in candidate):
                            hex_value = ''.join(f'{c:02X}' for c in candidate)
                            if hex_value not in taken:
                                return hex_value
        raise CoverEditError('No free colour close to that one; please choose another.')

    def random_colour(self, except_key: str = '') -> str:
        rng = random.SystemRandom()
        for _ in range(1000):
            colour = f'{rng.randrange(1 << 24):06X}'
            try:
                return self.free_colour(colour, except_key)
            except CoverEditError:
                continue
        raise CoverEditError('Could not find an unused colour.')

    # ------------------------------------------------------------------ planning
    def _ledger(self, db) -> dict[str, list[tuple[str, int | None, str | None]]]:
        rows = db.execute('SELECT source, output, output_size, output_sha256 FROM completed').fetchall()
        ledger: dict[str, list] = {}
        for source, stored, size, sha in rows:
            stored_path = Path(stored)
            if stored_path.is_absolute() and len(stored_path.parts) >= 3:
                stored_path = Path(*stored_path.parts[-3:])     # legacy absolute ledger rows
            ledger.setdefault(stored_path.as_posix().casefold(), []).append((source, size, sha))
        return ledger

    def _owner_row(self, ledger, path: Path, album: EditableAlbum):
        """The ledger row proving Oggcultist produced this exact file, or None."""
        relative = path.resolve().relative_to(self.root).as_posix().casefold()
        size = path.stat().st_size
        for source, recorded_size, recorded_sha in ledger.get(relative, []):
            if recorded_size is None or size != recorded_size:
                continue
            if recorded_sha:
                if _sha256(path) != recorded_sha:
                    continue
            else:
                from mutagen.oggopus import OggOpus
                tags = OggOpus(path)
                if ((tags.get('album') or [''])[0].casefold() != album.album.casefold()):
                    continue
            return source
        return None

    def plan(self, album: EditableAlbum, design: CoverDesign) -> ApplyPlan:
        """Check every file in the album; nothing is changed."""
        design = CoverDesign(normalise_colour(design.colour), [l.strip() for l in design.lines][:3],
                             'auto' if design.ink in ('', 'auto', None) else normalise_colour(design.ink))
        result = ApplyPlan(album, design)
        free = self.free_colour(design.colour, album.album_key)
        if free != design.colour:
            owner = self.owner_label(self.colour_owner(design.colour, album.album_key)) or 'another album'
            result.colour_note = (f'#{design.colour} is already the cover colour of {owner}; '
                                  f'the nearly identical #{free} will be used so every album stays unique.')
            design.colour = free
        new_png = design.png(album.album, album.artist, album.year)
        db = self._connect()
        try:
            ledger = self._ledger(db)
        finally:
            db.close()
        for path in sorted(album.folder.glob('*.opus')):
            try:
                picture = _embedded_picture(path)
            except Exception:
                result.skipped.append((path, 'could not be read'))
                continue
            if picture is None:
                result.skipped.append((path, 'has no single embedded cover'))
                continue
            if picture.data == new_png:
                result.already.append(path)
                continue
            colour = _picture_colour(picture)
            if colour not in (album.design.colour, design.colour):
                result.skipped.append((path, 'its cover is not this album\'s generated cover (left as it is)'))
                continue
            try:
                owner = self._owner_row(ledger, path, album)
            except OSError as exc:
                result.skipped.append((path, f'could not be checked: {exc}'))
                continue
            if owner is None:
                result.skipped.append((path, 'not recorded as an Oggcultist output, or changed since'))
                continue
            result.eligible.append(path)
        return result

    # ------------------------------------------------------------------ applying
    def save_design(self, album: EditableAlbum, design: CoverDesign) -> None:
        db = self._connect()
        try:
            with db:
                db.execute('UPDATE covers SET colour=? WHERE album_key=?', (design.colour, album.album_key))
                default = design.lines == album.default_lines() and design.ink == 'auto'
                if default:
                    db.execute('DELETE FROM cover_designs WHERE album_key=?', (album.album_key,))
                else:
                    db.execute('INSERT INTO cover_designs(album_key, lines, ink) VALUES(?,?,?) '
                               'ON CONFLICT(album_key) DO UPDATE SET lines=excluded.lines, ink=excluded.ink',
                               (album.album_key, json.dumps(design.lines), design.ink))
        except sqlite3.IntegrityError as exc:
            raise CoverEditError('That colour was just taken by another album; please apply again.') from exc
        finally:
            db.close()

    def apply(self, plan: ApplyPlan, progress: Callable[[int, int, Path], None] = lambda *_: None,
              cancel: Callable[[], bool] = lambda: False) -> ApplyResult:
        album, design = plan.album, plan.design
        result = ApplyResult(already=list(plan.already), skipped=list(plan.skipped))
        self.save_design(album, design)          # first, so an interrupted run can be resumed
        new_png = design.png(album.album, album.artist, album.year)
        comment = picture_comment(new_png)
        db = self._connect()
        try:
            ledger = self._ledger(db)
            for number, path in enumerate(plan.eligible, 1):
                if cancel():
                    result.skipped.append((path, 'stopped before this file'))
                    continue
                progress(number, len(plan.eligible), path)
                try:
                    source = self._owner_row(ledger, path, album)       # re-check right before changing it
                    if source is None:
                        raise CoverEditError('changed since it was checked')
                    self._replace_cover(path, comment, new_png)
                    stat = path.stat()
                    with db:
                        db.execute('UPDATE completed SET output_size=?, output_sha256=?, output_mtime_ns=? '
                                   'WHERE source=?', (stat.st_size, _sha256(path), stat.st_mtime_ns, source))
                    result.updated.append(path)
                except PermissionError:
                    result.failed.append((path, 'in use by another program (is it playing?); not changed'))
                except (CoverEditError, OSError, subprocess.SubprocessError) as exc:
                    result.failed.append((path, f'{exc}; not changed'))
        finally:
            db.close()
        album.design = design
        return result

    @staticmethod
    def _replace_cover(path: Path, comment: str, new_png: bytes) -> None:
        from mutagen.oggopus import OggOpus
        from PIL import Image
        before = path.stat()
        original_tags = _tags_without_picture(path)
        original_audio = _audio_md5(path)
        fd, name = tempfile.mkstemp(prefix='.oggcultist-art-', suffix='.opus', dir=path.parent)
        temp = Path(name)
        try:
            with os.fdopen(fd, 'wb') as out, path.open('rb') as src:
                for chunk in iter(lambda: src.read(1024 * 1024), b''):
                    out.write(chunk)
            ogg = OggOpus(temp)
            ogg['metadata_block_picture'] = [comment]
            ogg.save()
            # verify the copy before it replaces anything
            if _tags_without_picture(temp) != original_tags:
                raise CoverEditError('other tags changed unexpectedly')
            picture = _embedded_picture(temp)
            if picture is None or picture.data != new_png:
                raise CoverEditError('new cover did not verify')
            with Image.open(io.BytesIO(picture.data)) as im:
                im.verify()
            if _audio_md5(temp) != original_audio:
                raise CoverEditError('audio did not verify as identical')
            with temp.open('r+b') as handle:
                os.fsync(handle.fileno())
            now = path.stat()
            if (now.st_size, now.st_mtime_ns) != (before.st_size, before.st_mtime_ns):
                raise CoverEditError('file changed while it was being updated')
            os.replace(temp, path)
        finally:
            temp.unlink(missing_ok=True)
