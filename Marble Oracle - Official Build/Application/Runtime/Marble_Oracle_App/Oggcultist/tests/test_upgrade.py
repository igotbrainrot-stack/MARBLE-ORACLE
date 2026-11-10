"""Safe-upgrade and integrity regressions for Oggcultist v1.1."""
from __future__ import annotations
import os
import sqlite3
import threading
from pathlib import Path
import pytest
from mutagen.oggopus import OggOpus
from oggcultist.artwork import ArtworkStore
from oggcultist.core import plan, process, scan
from test_audit import flac, BASE


def test_old_database_is_backed_up_before_migration(tmp_path):
    state = tmp_path / 'music' / '.oggcultist'
    state.mkdir(parents=True)
    db = state / 'library.sqlite3'
    conn = sqlite3.connect(db)
    conn.execute('CREATE TABLE covers (album_key TEXT PRIMARY KEY, colour TEXT NOT NULL UNIQUE)')
    conn.execute('CREATE TABLE completed (source TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, output TEXT NOT NULL, output_size INTEGER, created TEXT DEFAULT CURRENT_TIMESTAMP)')
    conn.execute("INSERT INTO covers VALUES ('album:original', 'AABBCC')")
    conn.commit()
    conn.close()
    store = ArtworkStore(tmp_path / 'music')
    try:
        assert store.colour_for('album:original') == 'AABBCC'
        columns = {r[1] for r in store.db.execute('PRAGMA table_info(completed)')}
        assert {'source_sha256', 'metadata_signature', 'output_sha256', 'output_mtime_ns'} <= columns
    finally: store.close()
    backups = list(state.glob('library.sqlite3.bak-*'))
    assert len(backups) == 1
    before = backups[0].read_bytes()
    store = ArtworkStore(tmp_path / 'music')
    store.close()
    assert backups[0].read_bytes() == before
    assert len(list(state.glob('library.sqlite3.bak-*'))) == 1


def test_new_database_creates_no_unneeded_backup(tmp_path):
    store = ArtworkStore(tmp_path / 'Music')
    store.close()
    assert not list((tmp_path / 'Music' / '.oggcultist').glob('*.bak-*'))


@pytest.mark.skipif(not __import__('shutil').which('ffmpeg'), reason='FFmpeg missing')
def test_output_same_size_tampering_rejected(tmp_path):
    flac(tmp_path / 'src' / 'Album' / '01.flac', title='A', tracknumber='1', **BASE)
    tracks, _ = scan(tmp_path / 'src')
    assert process(tracks, tmp_path / 'out', threading.Event())['converted'] == 1
    output = next((tmp_path / 'out').rglob('*.opus'))
    old_time = output.stat().st_mtime_ns
    with output.open('r+b') as stream:
        stream.seek(-20, 2)
        item = stream.read(1)
        stream.seek(-20, 2)
        stream.write(bytes([item[0] ^ 1]))
    # Ensure timestamp differs (some filesystems have coarse time precision).
    os.utime(output, ns=(output.stat().st_atime_ns, old_time + 2_000_000_000))
    store = ArtworkStore(tmp_path / 'out')
    try: plan(tracks, tmp_path / 'out', store)
    finally: store.close()
    assert tracks[0].status == 'Review'
    assert 'modified' in tracks[0].note.lower()
    assert output.exists()


@pytest.mark.skipif(not __import__('shutil').which('ffmpeg'), reason='FFmpeg missing')
def test_manually_changed_metadata_requires_review_not_overwrite(tmp_path):
    flac(tmp_path / 'src' / 'Album' / '01.flac', title='A', tracknumber='1', **BASE)
    tracks, _ = scan(tmp_path / 'src')
    assert process(tracks, tmp_path / 'out', threading.Event())['converted'] == 1
    output = next((tmp_path / 'out').rglob('*.opus'))
    original_data = output.read_bytes()
    tracks[0].set_tag('genre', 'Classical')
    store = ArtworkStore(tmp_path / 'out')
    try: plan(tracks, tmp_path / 'out', store)
    finally: store.close()
    assert tracks[0].status == 'Review'
    assert 'outdated' in tracks[0].note.lower()
    assert output.read_bytes() == original_data
