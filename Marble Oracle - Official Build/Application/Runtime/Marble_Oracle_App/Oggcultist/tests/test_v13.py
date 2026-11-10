"""Oggcultist v1.3 audit remediation: preview safety and legacy artwork."""
import hashlib
import os
import shutil
import sqlite3
import subprocess
import sys
import threading
from pathlib import Path
import pytest
from PIL import Image
from mutagen.flac import Picture
from mutagen.oggopus import OggOpus
import base64
import io
from oggcultist.artwork import ArtworkStore
from oggcultist.core import plan, process, scan
from test_audit import flac, BASE, sha

ROOT = Path(__file__).resolve().parents[1]
needs_ffmpeg = pytest.mark.skipif(not shutil.which('ffmpeg'), reason='FFmpeg missing')

def cli(src, dest, run=False):
    args = [sys.executable, str(ROOT / 'launch.py'), '--cli', '--input', str(src), '--output', str(dest)]
    if run: args += ['--run']
    return subprocess.run(args, cwd=ROOT, capture_output=True, text=True)


def cover_colour(path):
    pic = Picture(base64.b64decode(OggOpus(path)['metadata_block_picture'][0]))
    with Image.open(io.BytesIO(pic.data)) as im:
        return '%02X%02X%02X' % im.convert('RGB').getpixel((0, 0))


def test_preview_new_destination_creates_no_directory(tmp_path):
    src = tmp_path / 'src'
    flac(src / 'Album' / '01.flac', title='T', tracknumber='1', **BASE)
    output = tmp_path / 'out'
    r = cli(src, output)
    assert r.returncode == 0, r.stderr
    assert not output.exists()


@needs_ffmpeg
def test_preview_does_not_change_existing_library_db_or_files(tmp_path):
    src, out = tmp_path / 'src', tmp_path / 'out'
    flac(src / 'Album' / '01.flac', title='T', tracknumber='1', **BASE)
    assert cli(src, out, run=True).returncode == 0
    flac(src / 'Another' / '01.flac', title='N', tracknumber='1', **{**BASE, 'album':'Another'})
    db = out / '.oggcultist' / 'library.sqlite3'
    before = (sha(db), db.stat().st_mtime_ns)
    files = {p: sha(p) for p in out.rglob('*.opus')}
    assert cli(src, out).returncode == 0
    assert (sha(db), db.stat().st_mtime_ns) == before
    assert {p: sha(p) for p in out.rglob('*.opus')} == files


def test_v10_schema_preview_does_not_migrate_or_backup(tmp_path):
    src, out = tmp_path / 'src', tmp_path / 'out'
    flac(src / 'Album' / '01.flac', title='T', tracknumber='1', **BASE)
    state = out / '.oggcultist'
    state.mkdir(parents=True)
    db = state / 'library.sqlite3'
    conn = sqlite3.connect(db)
    conn.execute('CREATE TABLE covers (album_key TEXT PRIMARY KEY, colour TEXT NOT NULL UNIQUE)')
    conn.execute('CREATE TABLE completed (source TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, output TEXT NOT NULL, output_size INTEGER, created TEXT DEFAULT CURRENT_TIMESTAMP)')
    conn.commit();conn.close()
    before = (sha(db), db.stat().st_mtime_ns)
    r = cli(src, out)
    assert r.returncode == 0, r.stderr
    assert before == (sha(db), db.stat().st_mtime_ns)
    assert not list(state.glob('*.bak-*'))
    conn = sqlite3.connect(db)
    try: assert 'source_sha256' not in {x[1] for x in conn.execute('PRAGMA table_info(completed)')}
    finally: conn.close()


@needs_ffmpeg
def test_mixed_legacy_covers_reported_without_rewriting(tmp_path):
    src, out = tmp_path / 'src', tmp_path / 'out'
    for n in (1,2):
        flac(src / 'Album' / f'{n:02}.flac', title=f'T{n}', tracknumber=str(n), **BASE)
    tracks, _ = scan(src)
    assert process(tracks, out, threading.Event())['converted'] == 2
    outputs = sorted(out.rglob('*.opus'))
    track1, track2 = outputs
    # Simulate a bug in v1.1: another existing (valid) artwork colour.
    store = ArtworkStore(out)
    try:
        png = store.cover_for('synthetic:legacy-2', 'Album', 'Band', '1975')
    finally: store.close()
    from oggcultist.artwork import picture_comment
    song2 = OggOpus(track2)
    song2['metadata_block_picture'] = [picture_comment(png)]
    song2.save()
    before = {p: sha(p) for p in outputs}
    refreshed, _ = scan(src)
    store = ArtworkStore(out)
    try:
        plan(refreshed, out, store)
        assert any('different artwork colours' in t.note for t in refreshed)
        assert store.cover_warnings
    finally: store.close()
    assert {p: sha(p) for p in outputs} == before
    summary = process(refreshed, out, threading.Event())
    assert summary['cover_warnings']
    assert {p: sha(p) for p in outputs} == before


@needs_ffmpeg
def test_untracked_foreign_copy_does_not_define_album_cover(tmp_path):
    src, out = tmp_path / 'src', tmp_path / 'out'
    flac(src / 'Album A' / '01.flac', title='T1', tracknumber='1', **{**BASE, 'album': 'Album A'})
    assert cli(src, out, run=True).returncode == 0
    a = next(out.rglob('*.opus'))
    a_colour = cover_colour(a)
    flac(src / 'Album B' / '01.flac', title='T2', tracknumber='1', **{**BASE, 'album': 'Album B'})
    b_folder = a.parent.parent / '1975 - Album B'
    b_folder.mkdir(parents=True)
    copied = b_folder / '98 - Copied from A.opus'
    shutil.copyfile(a, copied)
    tracks, _ = scan(src)
    store = ArtworkStore(out)
    try:
        plan(tracks, out, store)
        track_b = next(t for t in tracks if t.album=='Album B')
        b_colour = store.colour_for(track_b.cover_key)
        assert b_colour != a_colour
    finally: store.close()
    assert cover_colour(copied) == a_colour
