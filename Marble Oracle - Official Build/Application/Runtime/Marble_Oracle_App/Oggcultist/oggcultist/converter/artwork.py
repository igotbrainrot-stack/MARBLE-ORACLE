"""Persistent, unique-color, minimal album covers with Vorbis-compatible embedding."""
from __future__ import annotations
import base64
import io
import secrets
import datetime
import hashlib
import shutil
import tempfile
import time
import sqlite3
import sys
from urllib.parse import quote
from functools import lru_cache
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from mutagen.flac import Picture


def find_serif_font() -> str:
    """The cover font: Uberata Clear v3.0; fallback only for unsupported writing systems.

    Text the chosen font can't draw (e.g. Japanese, Arabic) still falls back line by line
    through ``_serif_for_text``.
    """
    try:
        from ..fonts import font_file
        bundled = font_file()          # Uberata Clear only; existing covers are left unchanged
        if bundled is not None:
            return str(bundled)
    except Exception:  # noqa: BLE001
        pass
    candidates = []
    if sys.platform == 'win32':
        candidates += [Path('C:/Windows/Fonts/times.ttf'), Path('C:/Windows/Fonts/timesbd.ttf')]
    candidates += [
        Path('/usr/share/fonts/truetype/msttcorefonts/Times_New_Roman.ttf'),
        Path('/usr/share/fonts/truetype/msttcorefonts/times.ttf'),
        Path('/usr/share/fonts/truetype/liberation2/LiberationSerif-Regular.ttf'),
        Path('/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf'),
        Path('/Library/Fonts/Times New Roman.ttf'),
    ]
    for f in candidates:
        if f.is_file(): return str(f)
    # PIL can resolve family fonts installed under other directories.
    for name in ('Times New Roman.ttf', 'times.ttf', 'LiberationSerif-Regular.ttf', 'DejaVuSerif.ttf'):
        try:
            ImageFont.truetype(name, 40)
            return name
        except OSError: continue
    raise RuntimeError('No serif font available: install Times New Roman or Liberation Serif')


def preferred_ink(rgb: tuple[int,int,int]) -> tuple[int,int,int]:
    def lum(c: int) -> float:
        v = c / 255
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    light = sum(k*lum(v) for k,v in zip((0.2126,0.7152,0.0722), rgb))
    return (0,0,0) if (light+0.05)/0.05 >= 1.05/(light+0.05) else (255,255,255)


@lru_cache(maxsize=2048)
def _font_has_text(font_name: str, label: str) -> bool:
    """Test actual glyph outlines, not just whether a font file loads."""
    try:
        font = ImageFont.truetype(font_name, 40)
        missing = bytes(font.getmask('\U0010FFFD'))
        for ch in label:
            if ch.isspace(): continue
            mask = font.getmask(ch)
            if not mask.getbbox() or bytes(mask) == missing:
                return False
        return True
    except (OSError, ValueError):
        return False


def _serif_for_text(label: str, preferred: str) -> str:
    """Select a serif with glyphs for the *whole* line; never print blank text."""
    paths = [
        preferred,
        '/usr/share/fonts/truetype/noto/NotoSerif-Regular.ttf',
        '/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf',
        '/usr/share/fonts/truetype/noto/NotoSerifThai-Regular.ttf',
        '/usr/share/fonts/truetype/noto/NotoSerifDevanagari-Regular.ttf',
        '/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc',
        '/usr/share/fonts/truetype/noto/NotoSerifCJK-Regular.ttc',
        'C:/Windows/Fonts/simsun.ttc',
        'C:/Windows/Fonts/mingliu.ttc',
        'C:/Windows/Fonts/batang.ttc',
        'C:/Windows/Fonts/msmincho.ttc',
        'C:/Windows/Fonts/yumin.ttf',
        'C:/Windows/Fonts/angsa.ttf',
        'C:/Windows/Fonts/mangal.ttf',
        'C:/Windows/Fonts/trado.ttf',
        '/System/Library/Fonts/Hiragino Sans GB.ttc',
    ]
    for path in paths:
        if _font_has_text(path, label): return path
    raise RuntimeError('No installed serif font has all the required glyphs for album/artist text. '
                       'Install Noto Serif fonts for this writing system.')


def _preferred_cover_font(label: str, preferred: str, *, role: str) -> str:
    """Use Uberata Clear for every generated cover line when it supports the text."""
    if _font_has_text(preferred, label):
        return preferred
    return _serif_for_text(label, preferred)


def _fit_cover_label(draw: ImageDraw.ImageDraw, label: str, font_file: str, start: int, max_width: int) -> tuple[str, ImageFont.FreeTypeFont, tuple[int, int, int, int]]:
    for size in range(start, 17, -1):
        font = ImageFont.truetype(font_file, size)
        bbox = draw.textbbox((0, 0), label, font=font)
        if bbox[2] - bbox[0] <= max_width:
            return label, font, bbox
    font = ImageFont.truetype(font_file, 18)
    suffix = '...'
    if not _font_has_text(font_file, suffix):
        raise RuntimeError('Cover font cannot render a truncation suffix')
    left, right = 0, len(label)
    while left < right:
        mid = (left + right + 1) // 2
        candidate = label[:mid].rstrip() + suffix
        bbox = draw.textbbox((0, 0), candidate, font=font)
        if bbox[2] - bbox[0] <= max_width:
            left = mid
        else:
            right = mid - 1
    label = label[:left].rstrip() + suffix
    bbox = draw.textbbox((0, 0), label, font=font)
    return label, font, bbox


def draw_cover(album: str, albumartist: str, year: str, colour: str, font_path: str | None = None,
               *, lines: list[str] | None = None, ink: str | None = None) -> bytes:
    """A 600 × 600 PNG: solid ``colour`` with balanced Oggcultist typography."""
    rgb = tuple(bytes.fromhex(colour.lstrip('#')))
    if len(rgb) != 3:
        raise ValueError('Expected six-digit RGB colour')
    im = Image.new('RGB', (600, 600), rgb)
    draw = ImageDraw.Draw(im)
    if ink and ink.lower() != 'auto':
        ink_rgb = tuple(bytes.fromhex(ink.lstrip('#')))
        if len(ink_rgb) != 3:
            raise ValueError('Expected six-digit RGB text colour')
        ink = ink_rgb
    else:
        ink = preferred_ink(rgb)
    font_path = font_path or find_serif_font()
    if lines is None:
        lines = [album or 'Unknown Album', albumartist or 'Unknown Album Artist', year or 'Year Unknown']

    line_specs = [('title', 96, 516), ('meta', 40, 500), ('meta', 34, 340)]
    prepared = []
    for (role, start_size, max_width), raw in zip(line_specs, list(lines)[:3]):
        if not raw or not raw.strip():
            continue
        label = raw.strip()
        font_file = _preferred_cover_font(label, font_path, role=role)
        prepared.append(_fit_cover_label(draw, label, font_file, start_size, max_width))
    # All lines left empty in the cover editor: a plain colour cover, as the editor promises.
    gaps = [26 if idx == 0 else 18 for idx in range(max(0, len(prepared) - 1))]
    total_h = sum((bbox[3] - bbox[1]) for _, _, bbox in prepared) + sum(gaps)
    y = max(56, (600 - total_h) / 2)
    for idx, (label, font, bbox) in enumerate(prepared):
        width, height = bbox[2] - bbox[0], bbox[3] - bbox[1]
        x = (600 - width) / 2 - bbox[0]
        draw.text((x, y - bbox[1]), label, font=font, fill=ink)
        y += height + (gaps[idx] if idx < len(gaps) else 0)
    output = io.BytesIO()
    im.save(output, format='PNG', optimize=True)
    return output.getvalue()


def picture_comment(png: bytes) -> str:
    pic = Picture()
    pic.type = 3
    pic.mime = 'image/png'
    pic.desc = 'Front cover'
    pic.width = 600
    pic.height = 600
    pic.depth = 24
    pic.colors = 0
    pic.data = png
    return base64.b64encode(pic.write()).decode('ascii')


def _sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


class ArtworkStore:
    def __init__(self, output: Path, read_only: bool = False):
        self.root = output.resolve()
        self.state = output / '.oggcultist'
        self.db_path = self.state / 'library.sqlite3'
        existing_db = self.db_path.is_file()
        self.read_only = read_only
        self.cover_warnings: dict[str, str] = {}
        self._inspected_folders: set[str] = set()
        self._owned_colours: dict[str, list[str]] = {}
        self._completed_paths: dict[str, list[tuple[int, int | None, str | None]]] | None = None
        if read_only:
            # The *entire preview* runs against a private, mutable in-memory copy.
            # No directory, database, backup, WAL/SHM or migration is written to
            # the destination (including a genuine v1.0 database).
            self.db = sqlite3.connect(':memory:')
            if self.db_path.is_file():
                # immutable=1 is strictly non-writing, but intentionally ignores
                # SQLite WAL/hot-journal recovery. For a journalled database, copy
                # the files to a *temporary* writable location, let SQLite recover
                # the copy, then backup the consistent view into memory. Never
                # create -shm or alter timestamps beside the user's original DB.
                journal_files = [self.db_path.with_name(self.db_path.name + suffix)
                                 for suffix in ('-wal', '-journal')]
                if any(path.is_file() for path in journal_files):
                    # A writer may append to -wal or checkpoint it while the
                    # files are being copied. Copying DB and WAL at different
                    # instants can produce an older or inconsistent snapshot.
                    # Verify source file versions before/after the whole copy;
                    # retry if ANY sidecar or the main database changed.
                    candidates = [self.db_path, *journal_files]
                    def versions():
                        versions_found = []
                        for file in candidates:
                            try:
                                st = file.stat()
                                versions_found.append((st.st_size, st.st_mtime_ns, st.st_ctime_ns, st.st_ino))
                            except FileNotFoundError:
                                versions_found.append(None)
                        return tuple(versions_found)

                    deadline = time.monotonic() + 15
                    while True:
                        try:
                            before = versions()
                            with tempfile.TemporaryDirectory(prefix='oggcultist-preview-') as temp:
                                copy = Path(temp) / self.db_path.name
                                shutil.copyfile(self.db_path, copy)
                                for journal in journal_files:
                                    if journal.is_file():
                                        shutil.copyfile(journal, Path(temp) / journal.name)
                                if versions() == before:
                                    source = sqlite3.connect(copy)
                                    try:
                                        source.backup(self.db)
                                        break
                                    finally:
                                        source.close()
                        except (FileNotFoundError, sqlite3.DatabaseError, OSError):
                            # File vanished during WAL checkpoint or a transient
                            # copy could not be recovered. Retry a fresh copy.
                            pass
                        if time.monotonic() >= deadline:
                            raise RuntimeError('Music library database is changing too quickly for '
                                               'a consistent read-only preview; please retry.')
                        time.sleep(0.01)
                else:
                    uri = 'file:' + quote(str(self.db_path.resolve()), safe='/') + '?mode=ro&immutable=1'
                    source = sqlite3.connect(uri, uri=True)
                    try:
                        source.backup(self.db)
                    finally:
                        source.close()
        else:
            self.state.mkdir(parents=True, exist_ok=True)
            self.db = sqlite3.connect(self.db_path)
        self.db.execute('PRAGMA busy_timeout=5000')
        self.db.execute('CREATE TABLE IF NOT EXISTS covers (album_key TEXT PRIMARY KEY, colour TEXT NOT NULL UNIQUE)')
        self.db.execute('CREATE TABLE IF NOT EXISTS completed (source TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, output TEXT NOT NULL, output_size INTEGER, created TEXT DEFAULT CURRENT_TIMESTAMP, source_sha256 TEXT, metadata_signature TEXT, output_sha256 TEXT, output_mtime_ns INTEGER)')
        self.db.commit()
        additions = {'source_sha256': 'TEXT', 'metadata_signature': 'TEXT',
                     'output_sha256': 'TEXT', 'output_mtime_ns': 'INTEGER'}
        # Back up an old database before altering it. Race-safe schema changes
        # require inspecting the columns again *inside* a write transaction.
        prior = {row[1] for row in self.db.execute('PRAGMA table_info(completed)')}
        audit_table_exists = self.db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='folder_artwork_audit'"
        ).fetchone() is not None
        if not read_only and existing_db and (
            any(name not in prior for name in additions) or not audit_table_exists
        ):
            backup = self.db_path.with_name('library.sqlite3.bak-' +
                                            datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
            with sqlite3.connect(backup) as destination:
                self.db.backup(destination)
        try:
            self.db.execute('BEGIN IMMEDIATE')
            columns = {row[1] for row in self.db.execute('PRAGMA table_info(completed)')}
            for name, kind in additions.items():
                if name not in columns:
                    self.db.execute(f'ALTER TABLE completed ADD COLUMN {name} {kind}')
            self.db.execute('CREATE INDEX IF NOT EXISTS ix_completed_content ON completed(source_sha256, metadata_signature)')
            self.db.execute('CREATE TABLE IF NOT EXISTS folder_covers (folder TEXT PRIMARY KEY, album_key TEXT NOT NULL)')
            self.db.execute('CREATE TABLE IF NOT EXISTS folder_artwork_audit ('
                            'folder TEXT PRIMARY KEY, signature TEXT NOT NULL, warning TEXT NOT NULL)')
            # v1.8: text and text colour chosen in the album art editor (colour stays in covers)
            self.db.execute('CREATE TABLE IF NOT EXISTS cover_designs ('
                            'album_key TEXT PRIMARY KEY, lines TEXT NOT NULL, ink TEXT NOT NULL)')
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise
        self.cache: dict[tuple[str,str,str,str],bytes] = {}

    @staticmethod
    def _album_png_colour(path: Path) -> str:
        """Read only the cover colour; no whole-file hash or ownership decision."""
        from mutagen.oggopus import OggOpus
        tags = OggOpus(path)
        picture = Picture(base64.b64decode(tags.get('metadata_block_picture', [])[0]))
        with Image.open(io.BytesIO(picture.data)) as im:
            return ''.join(f'{n:02X}' for n in im.convert('RGB').getpixel((0, 0)))

    @staticmethod
    def _folder_inventory(folder: Path) -> tuple[str, list[Path]]:
        """A cheap signature; changes when output names, sizes or mtimes change.

        It controls only the non-destructive *warning* cache, never ownership or
        completed-output verification (which perform their own integrity checks).
        """
        entries = sorted(folder.glob('*.opus')) if folder.is_dir() else []
        h = hashlib.sha256()
        for path in entries:
            try:
                stat = path.stat()
                h.update(repr((path.name, stat.st_size, stat.st_mtime_ns)).encode('utf-8', 'surrogatepass'))
                h.update(b'\0')
            except OSError:
                # A file disappearing during a scan must invalidate the warning
                # cache, rather than trusting a stale audit record.
                h.update(repr((path.name, 'unavailable')).encode('utf-8', 'surrogatepass'))
        return h.hexdigest(), entries

    def _refresh_cover_warning(self, folder: Path, folder_name: str,
                               seen: list[str] | None = None) -> None:
        """Recheck mixed artwork only when the directory inventory changed.

        Previously bound albums must never be SHA-256 hashed just to check
        their artwork; a one-time legacy colour-recovery scan is different.
        """
        signature, entries = self._folder_inventory(folder)
        row = self.db.execute('SELECT signature,warning FROM folder_artwork_audit WHERE folder=?',
                              (folder_name,)).fetchone()
        if row is not None and row[0] == signature:
            warning = row[1]
        else:
            if seen is None:
                seen = []
                for path in entries:
                    try:
                        seen.append(self._album_png_colour(path))
                    except Exception:
                        # Invalid output is handled by the normal completion-ledger
                        # check; it must never block a non-destructive preview.
                        continue
            count = len(set(seen))
            warning = (f'Existing outputs in this album carry {count} different artwork colours; '
                       'no existing audio was changed') if count > 1 else ''
            with self.db:
                self.db.execute('INSERT INTO folder_artwork_audit(folder,signature,warning) VALUES(?,?,?) '
                                'ON CONFLICT(folder) DO UPDATE SET signature=excluded.signature, '
                                'warning=excluded.warning', (folder_name, signature, warning))
        if warning:
            self.cover_warnings[folder_name] = warning
        else:
            self.cover_warnings.pop(folder_name, None)

    def _folder_colours(self, folder: Path, folder_name: str,
                        album: str, artist: str) -> tuple[list[str], list[str]]:
        """Return colours from all existing Opus files, then those owned by
        this folder's completion ledger. A stray copied track is *not* proof of
        the album's assigned colour.
        """
        seen: list[str] = []
        owned_ordered: list[tuple[int, str]] = []
        if self._completed_paths is None:
            try:
                rows = self.db.execute('SELECT output, output_size, output_sha256 '
                                       'FROM completed ORDER BY created, rowid').fetchall()
            except sqlite3.OperationalError:
                rows = []
            self._completed_paths = {}
            for index, (stored, size, sha256) in enumerate(rows):
                stored_path = Path(stored)
                if stored_path.is_absolute():
                    # Pre-v1.1 ledger destinations were absolute; the stable
                    # trailing album artist/album/track components are enough.
                    parts = stored_path.parts
                    if len(parts) >= 3:
                        stored_path = Path(*parts[-3:])
                self._completed_paths.setdefault(stored_path.as_posix().casefold(), []).append(
                    (index, size, sha256))
        owned_paths = self._completed_paths
        for opus in sorted(folder.glob('*.opus')) if folder.is_dir() else []:
            try:
                from mutagen.oggopus import OggOpus
                tags = OggOpus(opus)
                pic_value = tags.get('metadata_block_picture', [])[0]
                picture = Picture(base64.b64decode(pic_value))
                with Image.open(io.BytesIO(picture.data)) as im:
                    colour = ''.join(f'{n:02X}' for n in im.convert('RGB').getpixel((0, 0)))
                seen.append(colour)
                relative = opus.resolve().relative_to(self.root).as_posix().casefold()
                for index, recorded_size, recorded_sha in owned_paths.get(relative, []):
                    # A ledger *path* is not proof of identity: users or sync tools
                    # can replace a file at that same path. Require matching size,
                    # plus the output hash if the ledger version recorded one.
                    if recorded_size is None or opus.stat().st_size != recorded_size:
                        continue
                    if recorded_sha:
                        if _sha256_path(opus) != recorded_sha:
                            continue
                    else:
                        # v1.0 rows have no output hash. At least establish that
                        # the embedded album and album-artist tags belong here,
                        # rather than trusting a stray replacement's artwork.
                        def single_tag(key: str) -> str:
                            values = tags.get(key, [])
                            return values[0].strip().casefold() if values else ''
                        if (single_tag('album') != album.strip().casefold() or
                                single_tag('albumartist') != artist.strip().casefold()):
                            continue
                    owned_ordered.append((index, colour))
                    break
            except Exception:
                # A corrupt or foreign output is classified by plan(), never
                # allowed to crash artwork lookup or establish identity.
                continue
        return seen, [colour for _, colour in sorted(owned_ordered)]

    def folder_warning(self, folder: Path) -> str:
        name = folder.resolve().relative_to(self.root).as_posix().casefold()
        return self.cover_warnings.get(name, '')

    def folder_cover_key(self, folder: Path, candidate_keys: list[str],
                         album: str, artist: str, year: str) -> str:
        """Lock one colour to the destination album directory across future scans.

        Existing cover bytes win over changing MusicBrainz tags, v1.0/v1.1 key
        formats, and partial scans. This does not alter any existing music file.
        """
        folder_name = folder.resolve().relative_to(self.root).as_posix().casefold()
        # A persistent folder binding settles the artwork identity. Do NOT
        # inspect/hash every finished track to establish it again on reruns.
        row = self.db.execute('SELECT album_key FROM folder_covers WHERE folder=?',
                              (folder_name,)).fetchone()
        if row:
            self._refresh_cover_warning(folder, folder_name)
            return row[0]
        if folder_name not in self._inspected_folders:
            self._inspected_folders.add(folder_name)
            seen, self._owned_colours[folder_name] = self._folder_colours(folder, folder_name, album, artist)
            self._refresh_cover_warning(folder, folder_name, seen)
        candidates = list(dict.fromkeys(k for k in candidate_keys if k))
        chosen = None
        # Only completed tracks belonging to *this folder* may establish its
        # inherited cover colour. An untracked copy from another album cannot.
        for colour in self._owned_colours.get(folder_name, []):
            match = self.db.execute('SELECT album_key FROM covers WHERE colour=?',
                                    (colour,)).fetchone()
            if match:
                chosen = match[0]
                break
        if chosen is None:
            for key in candidates:
                if self.db.execute('SELECT 1 FROM covers WHERE album_key=?', (key,)).fetchone():
                    chosen = key
                    break
        if chosen is None:
            chosen = candidates[-1] if candidates else 'folder:' + folder_name
        # The same colour may not be assigned to two different output album
        # folders. A copied/ambiguous album is assigned a fresh unique key.
        taken = self.db.execute('SELECT folder FROM folder_covers WHERE album_key=?',
                                 (chosen,)).fetchone()
        if taken and taken[0] != folder_name:
            chosen = 'folder:' + folder_name
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO folder_covers(folder,album_key) VALUES(?,?)',
                            (folder_name,chosen))
        return self.db.execute('SELECT album_key FROM folder_covers WHERE folder=?',
                               (folder_name,)).fetchone()[0]

    def colour_for(self, album_key: str) -> str:
        row = self.db.execute('SELECT colour FROM covers WHERE album_key=?', (album_key,)).fetchone()
        if row: return row[0]
        for _ in range(1000):
            candidate = secrets.token_hex(3).upper()
            try:
                with self.db:
                    self.db.execute('INSERT INTO covers(album_key,colour) VALUES(?,?)', (album_key,candidate))
                return candidate
            except sqlite3.IntegrityError:
                row = self.db.execute('SELECT colour FROM covers WHERE album_key=?',(album_key,)).fetchone()
                if row: return row[0]
        raise RuntimeError('Unable to find unused 24-bit cover colour')

    def design_for(self, album_key: str) -> tuple[list[str] | None, str]:
        """Text lines and ink saved by the album art editor: (None, 'auto') if never edited."""
        try:
            row = self.db.execute('SELECT lines, ink FROM cover_designs WHERE album_key=?',
                                  (album_key,)).fetchone()
        except sqlite3.OperationalError:
            row = None
        if not row:
            return None, 'auto'
        import json
        try:
            lines = [str(x) for x in json.loads(row[0])][:3]
        except (ValueError, TypeError):
            lines = None
        return lines, row[1] or 'auto'

    def existing_cover(self, folder: Path, album_key: str) -> bytes | None:
        """The cover already used in this album folder, so new songs match the old ones.

        Only an Oggcultist-generated cover counts: a 600 × 600 PNG whose flat background is
        this album's colour. Changing the cover font or sizes (v1.8.6) must not give one
        album two different looks; the Album Art page restyles a whole album on request.
        """
        cache = self.__dict__.setdefault('_existing_covers', {})
        key = (str(folder).casefold(), album_key)
        if key in cache:
            return cache[key]
        found = None
        if folder.is_dir():
            from mutagen.oggopus import OggOpus
            colour = self.colour_for(album_key)
            for path in sorted(folder.glob('*.opus')):
                try:
                    values = OggOpus(path).get('metadata_block_picture', [])
                    if len(values) != 1:
                        continue
                    picture = Picture(base64.b64decode(values[0]))
                    if picture.mime != 'image/png':
                        continue
                    with Image.open(io.BytesIO(picture.data)) as im:
                        rgb = im.convert('RGB')
                        flat = len({rgb.getpixel(p) for p in ((0, 0), (599, 0), (0, 599), (599, 599))}) == 1
                        if im.size == (600, 600) and flat and \
                                ''.join(f'{n:02X}' for n in rgb.getpixel((0, 0))) == colour:
                            found = picture.data
                            break
                except Exception:  # noqa: BLE001 - unreadable sibling: just don't reuse it
                    continue
        cache[key] = found
        return found

    def remember_cover(self, folder: Path, album_key: str, data: bytes) -> None:
        """After publishing a song, its cover is the album's cover for the rest of the run."""
        self.__dict__.setdefault('_existing_covers', {})[(str(folder).casefold(), album_key)] = data

    def cover_for(self, album_key: str, album: str, artist: str, year: str) -> bytes:
        lines, ink = self.design_for(album_key)
        k = (album_key, album, artist, year, tuple(lines) if lines is not None else None, ink)
        if k not in self.cache:
            self.cache[k] = draw_cover(album, artist, year, self.colour_for(album_key), lines=lines, ink=ink)
        return self.cache[k]

    def _relative_output(self, output: str) -> str:
        return Path(output).resolve().relative_to(self.root).as_posix()

    def _adopt_moved_source(self, source: str, fingerprint: str, output: str,
                            source_path: Path, metadata_signature: str) -> bool:
        """Rebind a ledger entry after a source mount changes, only if uniquely
        content-identical and still mapped to this exact output. Never overwrite.
        """
        if not Path(output).is_file(): return False
        relative = self._relative_output(output)
        rows = self.db.execute(
            'SELECT source,output,source_sha256,metadata_signature,output_size,'
            'output_sha256,output_mtime_ns FROM completed WHERE metadata_signature=?',
            (metadata_signature,)).fetchall()
        matches = []
        for row in rows:
            old_source, old_output, src_sha, meta, size, dst_sha, dst_mtime = row
            if not src_sha or size is None: continue
            same = (Path(old_output).as_posix() == relative if not Path(old_output).is_absolute()
                    else Path(old_output).parts[-3:] == Path(output).parts[-3:])
            if same: matches.append(row)
        if len(matches) != 1: return False
        old_source, old_output, src_sha, meta, size, dst_sha, dst_mtime = matches[0]
        stat = Path(output).stat()
        if stat.st_size != size: return False
        try:
            if dst_sha and _sha256_path(Path(output)) != dst_sha: return False
            if _sha256_path(source_path) != src_sha: return False
        except OSError:
            return False
        try:
            with self.db:
                self.db.execute('UPDATE completed SET source=?,fingerprint=?,output=?,output_mtime_ns=? '
                                'WHERE source=?', (source,fingerprint,relative,stat.st_mtime_ns,old_source))
        except sqlite3.IntegrityError:
            return False
        return True

    def output_state(self, source: str, fingerprint: str, output: str, source_path: Path,
                     metadata_signature: str) -> str:
        """Return done/changed/outdated/foreign; never authorize an overwrite."""
        row = self.db.execute(
            'SELECT fingerprint,output,output_size,source_sha256,metadata_signature,'
            'output_sha256,output_mtime_ns FROM completed WHERE source=?', (source,)).fetchone()
        if row is None:
            if self._adopt_moved_source(source, fingerprint, output, source_path, metadata_signature):
                return 'done'
            return 'foreign' 
        old_fp, old_output, old_size, old_sha, old_metadata, old_output_sha, old_mtime = row
        path = Path(output)
        if not path.is_file(): return 'changed'
        relative = self._relative_output(output)
        if Path(old_output).is_absolute():
            # Legacy pre-migration entries retain absolute paths. Accept a moved
            # library if its trailing Album Artist/Year - Album/Title are identical.
            old_parts = Path(old_output).parts
            same_target = len(old_parts) >= 3 and old_parts[-3:] == path.parts[-3:]
        else:
            same_target = Path(old_output).as_posix() == relative
        if not same_target: return 'foreign'
        output_stat = path.stat()
        if old_size is None or output_stat.st_size != old_size: return 'changed'
        if old_output_sha and output_stat.st_mtime_ns != old_mtime:
            h = hashlib.sha256()
            try:
                with path.open('rb') as stream:
                    for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                        h.update(chunk)
            except OSError:
                return 'changed'
            if h.hexdigest() != old_output_sha: return 'changed'
            with self.db:
                self.db.execute('UPDATE completed SET output_mtime_ns=? WHERE source=?',
                                (output_stat.st_mtime_ns, source))
        try:
            from mutagen.oggopus import OggOpus
            if not OggOpus(path).get('oggcultist_target_bitrate'): return 'changed'
        except Exception:
            return 'changed'
        if old_fp == fingerprint and (old_metadata is None or old_metadata == metadata_signature):
            return 'done'
        if not old_sha or old_metadata != metadata_signature:
            return 'outdated'
        sha = hashlib.sha256()
        try:
            with source_path.open('rb') as f:
                for chunk in iter(lambda: f.read(1024 * 1024), b''):
                    sha.update(chunk)
        except OSError:
            return 'outdated'
        if sha.hexdigest() != old_sha: return 'outdated'
        # Content and metadata match despite a timestamp-only change.
        with self.db:
            self.db.execute('UPDATE completed SET fingerprint=?,output=? WHERE source=?',
                            (fingerprint, relative, source))
        return 'done'

    def completed(self, source: str, fingerprint: str, output: str) -> bool:
        # Public compatibility helper, kept strict for external callers.
        row = self.db.execute('SELECT fingerprint,output,output_size FROM completed WHERE source=?',
                              (source,)).fetchone()
        if row is None: return False
        try:
            relative = self._relative_output(output)
            return (row[0] == fingerprint and
                    (row[1] == relative or Path(row[1]).resolve() == Path(output).resolve()) and
                    Path(output).is_file() and Path(output).stat().st_size == row[2])
        except (ValueError, OSError):
            return False

    def mark_complete(self, source: str, fingerprint: str, output: str, size: int,
                      source_sha256: str = '', metadata_signature: str = '') -> None:
        relative = self._relative_output(output)
        digest = hashlib.sha256()
        with Path(output).open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(chunk)
        output_mtime_ns = Path(output).stat().st_mtime_ns
        with self.db:
            self.db.execute('INSERT OR REPLACE INTO completed'
                            '(source,fingerprint,output,output_size,source_sha256,metadata_signature,'
                            'output_sha256,output_mtime_ns) VALUES(?,?,?,?,?,?,?,?)',
                            (source,fingerprint,relative,size,source_sha256,metadata_signature,
                             digest.hexdigest(),output_mtime_ns))

    def close(self) -> None: self.db.close()
