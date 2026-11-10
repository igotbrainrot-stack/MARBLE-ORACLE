"""Third independent audit pass: Oggcultist v1.2.0 (added 2026-11-04).

Conventions as before: plain tests = verified behaviour; xfail(strict=True) = confirmed defect
(ID in CODE_REVIEW_v1.2.md). History tests need the unmodified v1.0 and v1.1 source trees:
set OGGCULTIST_V10 and OGGCULTIST_V11 to the folders containing their launch.py, otherwise they skip.
"""
from __future__ import annotations
import base64
import hashlib
import io
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path

import pytest
from mutagen.flac import Picture
from mutagen.oggopus import OggOpus
from PIL import Image

from oggcultist.artwork import ArtworkStore, draw_cover, _serif_for_text, _font_has_text, find_serif_font
from oggcultist.core import plan, process, scan
from test_audit import flac, BASE, needs_ffmpeg

V10, V11 = os.environ.get('OGGCULTIST_V10', ''), os.environ.get('OGGCULTIST_V11', '')
ROOT = Path(__file__).resolve().parents[1]
has = lambda v: bool(v) and (Path(v) / 'launch.py').is_file()
needs_history = pytest.mark.skipif(not (has(V10) and has(V11)), reason='Set OGGCULTIST_V10 and OGGCULTIST_V11')


def run_cli(tree: str | Path, src: Path, out: Path, run=True) -> subprocess.CompletedProcess:
    args = [sys.executable, str(Path(tree) / 'launch.py'), '--cli', '--input', str(src), '--output', str(out)]
    return subprocess.run(args + (['--run'] if run else []), cwd=str(tree), capture_output=True, text=True)


def cover_colour(p: Path) -> str:
    data = Picture(base64.b64decode(OggOpus(p)['metadata_block_picture'][0])).data
    with Image.open(io.BytesIO(data)) as im:
        return '%02X%02X%02X' % im.convert('RGB').getpixel((0, 0))


def colours_by_folder(out: Path) -> dict[Path, set[str]]:
    result: dict[Path, set[str]] = {}
    for p in out.rglob('*.opus'):
        result.setdefault(p.parent, set()).add(cover_colour(p))
    return result


def album(src: Path, name: str, n: int, start=1, **extra):
    for i in range(start, start + n):
        flac(src / name / f'{i:02}.flac', title=f'{name} {i}', tracknumber=str(i),
             **{**BASE, 'album': name, **extra})


# --------------------------------------------------------------------------- colour identity
@needs_ffmpeg
@needs_history
def test_mixed_v10_v11_v12_history_with_fragmented_scans(tmp_path):
    """Albums started under v1.0 and v1.1, then finished by v1.2 one album folder at a time."""
    src, out = tmp_path / 'src', tmp_path / 'out'
    rid = 'aaaaaaaa-1111-2222-3333-444444444444'
    album(src, 'Alpha', 1); album(src, 'Bravo', 1, releasetype='album')
    assert run_cli(V10, src, out).returncode == 0              # v1.0: Alpha 1, Bravo 1
    album(src, 'Bravo', 1, start=2, releasetype='album'); album(src, 'Charlie', 1, musicbrainz_albumid=rid)
    assert run_cli(V11, src, out).returncode == 0              # v1.1: Bravo 2 (hits old F1), Charlie 1
    before = {p: cover_colour(p) for p in out.rglob('*.opus')}
    first_colour = {}
    for p in sorted(before, key=lambda q: q.stat().st_mtime_ns):
        first_colour.setdefault(p.parent, before[p])
    album(src, 'Alpha', 1, start=2); album(src, 'Charlie', 1, start=2)   # Charlie 2 has no MBID
    album(src, 'Delta', 2)
    for folder in sorted(p for p in src.iterdir() if p.is_dir()):  # v1.2: fragmented, one album per scan
        tracks, _ = scan(folder)
        process(tracks, out, threading.Event())
    after = {p: cover_colour(p) for p in out.rglob('*.opus')}
    new = {p: c for p, c in after.items() if p not in before}
    assert len(after) == 8 and len(new) == 4
    for p, c in new.items():                       # v1.2 continues the album's *original* colour
        first_colour.setdefault(p.parent, c)
        assert c == first_colour[p.parent], (p, c, first_colour[p.parent])
    assert len(set(first_colour.values())) == len(first_colour)   # never shared between albums
    # Bravo carries the pre-existing v1.1 split (F1); v1.2 neither repairs nor reports it (G4).
    bravo = {c for p, c in after.items() if p.parent.name == '1975 - Bravo'}
    assert len(bravo) == 2


@needs_ffmpeg
def test_two_processes_converting_same_library_concurrently(tmp_path):
    src, out = tmp_path / 'src', tmp_path / 'out'
    for name in ('One', 'Two', 'Three'):
        album(src, name, 3)
    procs = [subprocess.Popen([sys.executable, str(ROOT / 'launch.py'), '--cli', '--input', str(src),
                               '--output', str(out), '--run'], cwd=str(ROOT),
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True) for _ in range(2)]
    logs = [p.communicate(timeout=600)[0] for p in procs]
    assert 'Traceback' not in ''.join(logs), logs
    outputs = sorted(out.rglob('*.opus'))
    assert len(outputs) == 9
    assert not list(out.rglob('.oggcultist-*'))                       # no staging debris
    by_folder = colours_by_folder(out)
    assert all(len(c) == 1 for c in by_folder.values())
    assert len({next(iter(c)) for c in by_folder.values()}) == 3
    tracks, _ = scan(src)
    store = ArtworkStore(out)
    try: plan(tracks, out, store)
    finally: store.close()
    assert {t.status for t in tracks} == {'Done'}                     # ledger consistent afterwards


# --------------------------------------------------------------------------- dry-run side effects
@needs_ffmpeg
def test_G1_dry_run_does_not_modify_destination_state(tmp_path):
    src, out = tmp_path / 'src', tmp_path / 'out'
    album(src, 'One', 1)
    assert run_cli(ROOT, src, out).returncode == 0
    album(src, 'Two', 1)                                               # new album, previewed only
    db = out / '.oggcultist' / 'library.sqlite3'
    before = hashlib.sha256(db.read_bytes()).hexdigest()
    r = run_cli(ROOT, src, out, run=False)
    assert 'DRY RUN' in r.stdout
    assert hashlib.sha256(db.read_bytes()).hexdigest() == before


# --------------------------------------------------------------------------- cover glyphs
def test_G2_elided_label_uses_supported_suffix(monkeypatch):
    # The old audit asked the *untruncated* font to include U+2026.
    # The fix instead chooses an ASCII suffix when U+2026 is absent.
    from PIL import ImageDraw
    import oggcultist.artwork as artwork
    old = artwork._font_has_text
    seen = []
    original_text = ImageDraw.ImageDraw.text
    monkeypatch.setattr(artwork, '_font_has_text', lambda name, text: False if text == '…' else old(name, text))
    def record(drawer, xy, text, *args, **kwargs):
        seen.append(text)
        return original_text(drawer, xy, text, *args, **kwargs)
    monkeypatch.setattr(ImageDraw.ImageDraw, 'text', record)
    png = draw_cover('Very long album title ' * 28, 'Artist', '1995', 'FFFFFF')
    assert png.startswith(b'\x89PNG')
    assert seen and seen[0].endswith('...') and '…' not in seen[0]


def test_script_font_tests_need_fonts_installed():
    """Documents G3: the shipped other-script tests fail (not skip) when Noto script fonts are absent."""
    missing = [s for s in ('أغنية', 'เพลง', 'हिंदी')
               if not any(_font_has_text(f, s) for f in (
                   '/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf',
                   '/usr/share/fonts/truetype/noto/NotoSerifThai-Regular.ttf',
                   '/usr/share/fonts/truetype/noto/NotoSerifDevanagari-Regular.ttf'))]
    if missing:
        pytest.skip(f'script fonts absent for {missing}: shipped test_F7_other_scripts_* will FAIL here')
