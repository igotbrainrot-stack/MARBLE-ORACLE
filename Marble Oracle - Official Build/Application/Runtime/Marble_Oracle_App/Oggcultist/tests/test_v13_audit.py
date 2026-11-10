"""Fourth independent audit pass: Oggcultist v1.3.0 (added 2026-11-04).

Conventions as before: plain tests = verified behaviour; xfail(strict=True) = confirmed defect
(ID in CODE_REVIEW_v1.3.md). History tests need OGGCULTIST_V10 / OGGCULTIST_V11 (folders
containing the original launch.py). The permission test needs root plus `runuser` and an
unprivileged `nobody` account; otherwise it skips.
"""
from __future__ import annotations
import base64
import io
import os
import shutil
import subprocess
import sys
import tempfile
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
needs_v10 = pytest.mark.skipif(not has(V10), reason='Set OGGCULTIST_V10')
needs_history = pytest.mark.skipif(not (has(V10) and has(V11)), reason='Set OGGCULTIST_V10 and OGGCULTIST_V11')
can_drop_privs = os.geteuid() == 0 and shutil.which('runuser') is not None and \
    subprocess.run(['id', 'nobody'], capture_output=True).returncode == 0
needs_nobody = pytest.mark.skipif(not can_drop_privs, reason='needs root + runuser + nobody')


def cli(tree, src, out, run=False, user=None):
    cmd = [sys.executable, str(Path(tree) / 'launch.py'), '--cli', '--input', str(src), '--output', str(out)]
    if run: cmd.append('--run')
    if user: cmd = ['runuser', '-u', user, '--'] + cmd
    return subprocess.run(cmd, cwd=str(tree), capture_output=True, text=True)


def snapshot(root: Path) -> dict[str, tuple[int, int, bytes]]:
    """Every file *and directory* below root: (size, mtime_ns, bytes-for-files)."""
    out = {}
    if not root.exists(): return out
    for p in sorted([root, *root.rglob('*')]):
        st = p.stat()
        out[str(p.relative_to(root))] = (st.st_size if p.is_file() else -1, st.st_mtime_ns,
                                         p.read_bytes() if p.is_file() else b'')
    return out


def colour(p: Path) -> str:
    data = Picture(base64.b64decode(OggOpus(p)['metadata_block_picture'][0])).data
    with Image.open(io.BytesIO(data)) as im:
        return '%02X%02X%02X' % im.convert('RGB').getpixel((0, 0))


def album(src: Path, name: str, n: int, start=1, **extra):
    for i in range(start, start + n):
        flac(src / name / f'{i:02}.flac', title=f'{name} {i}', tracknumber=str(i),
             **{**BASE, 'album': name, **extra})


# --------------------------------------------------------------------------- G1: dry run is side-effect free
@needs_ffmpeg
@needs_v10
def test_dry_run_on_real_v10_library_changes_no_byte_or_timestamp(tmp_path):
    src, out = tmp_path / 'src', tmp_path / 'out'
    album(src, 'One', 2)
    assert cli(V10, src, out, run=True).returncode == 0
    album(src, 'Two', 1)
    before = snapshot(out)
    r = cli(ROOT, src, out)
    assert r.returncode == 0 and 'DRY RUN' in r.stdout, r.stderr
    assert snapshot(out) == before                       # no backup, no -wal/-shm, no migration
    assert '[Done' in r.stdout                           # v1.0 completions still recognised in preview


@needs_ffmpeg
def test_dry_run_into_missing_destination_creates_nothing(tmp_path):
    album(tmp_path / 'src', 'One', 1)
    r = cli(ROOT, tmp_path / 'src', tmp_path / 'never-created')
    assert r.returncode == 0 and not (tmp_path / 'never-created').exists()


@needs_ffmpeg
@needs_nobody
def test_dry_run_as_unprivileged_user_on_unwritable_destination():
    base = Path(tempfile.mkdtemp(prefix='ogg-ro-'))
    try:
        os.chmod(base, 0o755)
        src, out = base / 'src', base / 'out'
        album(src, 'One', 1)
        assert cli(ROOT, src, out, run=True).returncode == 0          # root builds the library
        album(src, 'Two', 1)
        for p in [base, *base.rglob('*')]:
            os.chmod(p, 0o755 if p.is_dir() else 0o644)               # readable, NOT writable by nobody
        before = snapshot(out)
        r = cli(ROOT, src, out, user='nobody')
        assert r.returncode == 0, r.stdout + r.stderr
        assert '[Done' in r.stdout and '[Ready' in r.stdout
        assert snapshot(out) == before
    finally:
        shutil.rmtree(base, ignore_errors=True)


# --------------------------------------------------------------------------- G4: legacy split reported
@needs_ffmpeg
@needs_history
def test_v11_split_is_reported_in_preview_and_report(tmp_path):
    src, out = tmp_path / 'src', tmp_path / 'out'
    album(src, 'Bravo', 1, releasetype='album')
    assert cli(V10, src, out, run=True).returncode == 0
    album(src, 'Bravo', 1, start=2, releasetype='album')
    assert cli(V11, src, out, run=True).returncode == 0              # v1.1 writes the second colour
    assert len({colour(p) for p in out.rglob('*.opus')}) == 2
    album(src, 'Bravo', 1, start=3, releasetype='album')
    preview = cli(ROOT, src, out)
    assert 'different artwork colours' in preview.stdout
    tracks, _ = scan(src)
    summary = process(tracks, out, threading.Event())
    assert summary['converted'] == 1 and len(summary['cover_warnings']) == 1
    newest = next(p for p in out.rglob('03 - *.opus'))
    oldest = next(p for p in out.rglob('01 - *.opus'))
    assert colour(newest) == colour(oldest)                         # continues the *v1.0* colour


# --------------------------------------------------------------------------- G5: ownership rules
@needs_ffmpeg
@needs_v10
def test_foreign_copy_into_unbound_legacy_folder_cannot_claim_colour(tmp_path):
    src, out = tmp_path / 'src', tmp_path / 'out'
    album(src, 'Alpha', 1); album(src, 'Bravo', 1)
    assert cli(V10, src, out, run=True).returncode == 0
    a1 = next(out.rglob('*Alpha*/*.opus')); b1 = next(out.rglob('*Bravo*/*.opus'))
    alpha_c, bravo_c = colour(a1), colour(b1)
    shutil.copy(a1, b1.parent / 'Stray copy.opus')                  # untracked foreign copy
    album(src, 'Bravo', 1, start=2)
    tracks, _ = scan(src / 'Bravo')                                  # fragmented: Bravo bound first
    process(tracks, out, threading.Event())
    assert colour(next(out.rglob('*Bravo*/02 - *.opus'))) == bravo_c
    album(src, 'Alpha', 1, start=2)
    tracks, _ = scan(src / 'Alpha')
    process(tracks, out, threading.Event())
    assert colour(next(out.rglob('*Alpha*/02 - *.opus'))) == alpha_c


@needs_ffmpeg
@needs_v10
def test_H1_swapped_file_at_owned_path_cannot_claim_colour(tmp_path):
    src, out = tmp_path / 'src', tmp_path / 'out'
    album(src, 'Alpha', 1); album(src, 'Bravo', 1)
    assert cli(V10, src, out, run=True).returncode == 0
    a1 = next(out.rglob('*Alpha*/*.opus')); b1 = next(out.rglob('*Bravo*/*.opus'))
    alpha_c, bravo_c = colour(a1), colour(b1)
    # A user (or a sync tool) replaces Bravo's managed file with a copy of Alpha's track.
    b1.unlink(); shutil.copy(a1, b1)
    album(src, 'Bravo', 1, start=2)
    tracks, _ = scan(src / 'Bravo')
    process(tracks, out, threading.Event())
    new_bravo = colour(next(out.rglob('*Bravo*/02 - *.opus')))
    assert new_bravo != alpha_c, 'Bravo inherited Alpha\'s colour from a swapped file'
    album(src, 'Alpha', 1, start=2)
    tracks, _ = scan(src / 'Alpha')
    process(tracks, out, threading.Event())
    assert colour(next(out.rglob('*Alpha*/02 - *.opus'))) == alpha_c


# --------------------------------------------------------------------------- G2 with real fonts
def test_G2_real_arabic_elision_draws_only_covered_text(monkeypatch):
    label = 'ألبوم طويل جدا ' * 8
    try:
        font = _serif_for_text(label, find_serif_font())
    except RuntimeError:
        pytest.skip('No Arabic serif font installed')
    from PIL import ImageDraw
    drawn = []
    real = ImageDraw.ImageDraw.text
    monkeypatch.setattr(ImageDraw.ImageDraw, 'text', lambda d, xy, t, *a, **k: (drawn.append(t), real(d, xy, t, *a, **k))[1])
    draw_cover(label, 'X', '1999', 'F2E6C9')
    assert drawn[0] != label and _font_has_text(font, drawn[0]), (font, drawn[0][-5:])


# --------------------------------------------------------------------------- H2: immutable snapshot ignores WAL
@needs_ffmpeg
def test_H2_preview_sees_committed_wal_rows(tmp_path):
    import sqlite3
    src, out = tmp_path / 'src', tmp_path / 'out'
    album(src, 'One', 1)
    assert cli(ROOT, src, out, run=True).returncode == 0
    db = out / '.oggcultist' / 'library.sqlite3'
    c = sqlite3.connect(db); c.execute('PRAGMA journal_mode=WAL'); c.close()
    code = (f"import sqlite3,os; c=sqlite3.connect({str(db)!r}); "
            "c.execute(\"INSERT INTO covers VALUES('album:probe','123456')\"); c.commit(); os._exit(0)")
    subprocess.run([sys.executable, '-c', code], check=True)          # writer dies before checkpoint
    assert (db.parent / 'library.sqlite3-wal').stat().st_size > 0
    store = ArtworkStore(out, read_only=True)
    try:
        assert store.db.execute("SELECT count(*) FROM covers WHERE album_key='album:probe'").fetchone()[0] == 1
    finally:
        store.close()
