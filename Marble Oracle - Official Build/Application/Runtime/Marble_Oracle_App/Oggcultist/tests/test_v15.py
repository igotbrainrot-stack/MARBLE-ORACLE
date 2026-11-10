"""v1.5 performance and warning-cache regressions (synthetic local audio only)."""
from __future__ import annotations
import shutil
import threading
from oggcultist import artwork
from oggcultist.artwork import ArtworkStore
from oggcultist.core import plan, process, scan
from test_audit import flac, BASE, needs_ffmpeg


@needs_ffmpeg
def test_finished_album_never_rehashes_on_replan(tmp_path, monkeypatch):
    source, out = tmp_path / 'src', tmp_path / 'out'
    for i in (1, 2):
        flac(source / 'Album' / f'{i:02}.flac', title=f'Song {i}', tracknumber=str(i), **BASE)
    ts, _ = scan(source)
    assert process(ts, out, threading.Event())['converted'] == 2
    calls = []
    original = artwork._sha256_path
    monkeypatch.setattr(artwork, '_sha256_path',
                        lambda path: (calls.append(path), original(path))[1])
    for _ in range(3):
        store = ArtworkStore(out)
        try:
            plan(ts, out, store)
            assert {t.status for t in ts} == {'Done'}
        finally: store.close()
    assert calls == []


@needs_ffmpeg
def test_legacy_unbound_album_recovers_once_then_reuses_binding(tmp_path, monkeypatch):
    source, out = tmp_path / 'src', tmp_path / 'out'
    flac(source / 'Album' / '01.flac', title='Song', tracknumber='1', **BASE)
    tracks, _ = scan(source)
    assert process(tracks, out, threading.Event())['converted'] == 1
    s = ArtworkStore(out)
    with s.db:
        s.db.execute('DELETE FROM folder_covers')  # simulate an upgraded legacy library
    s.close()
    hashed = []
    original = artwork._sha256_path
    monkeypatch.setattr(artwork, '_sha256_path',
                        lambda p: (hashed.append(p), original(p))[1])
    for i in range(2):
        s = ArtworkStore(out)
        try:
            plan(tracks, out, s)
            assert tracks[0].status == 'Done'
        finally: s.close()
        if i == 0: assert len(hashed) == 1  # one-time integrity proof for inheritance
    assert len(hashed) == 1


@needs_ffmpeg
def test_artwork_warning_is_cached_and_invalidated_without_rehash(tmp_path, monkeypatch):
    source, out = tmp_path / 'src', tmp_path / 'out'
    flac(source / 'Album A' / '01.flac', album='Album A', title='A', tracknumber='1', **{k:v for k,v in BASE.items() if k != 'album'})
    flac(source / 'Album B' / '01.flac', album='Album B', title='B', tracknumber='1', **{k:v for k,v in BASE.items() if k != 'album'})
    tracks, _ = scan(source)
    assert process(tracks, out, threading.Event())['converted'] == 2
    from pathlib import Path
    output_a = next(p for p in out.rglob('*.opus') if 'Album A' in p.parent.name)
    output_b = next(p for p in out.rglob('*.opus') if 'Album B' in p.parent.name)
    foreign = output_a.parent / 'Foreign copy.opus'
    readings = []
    original = ArtworkStore._album_png_colour
    monkeypatch.setattr(ArtworkStore, '_album_png_colour', staticmethod(lambda path: (readings.append(path), original(path))[1]))
    shutil.copyfile(output_b, foreign)
    for i in range(3):
        store = ArtworkStore(out, read_only=(i==0))
        try:
            plan(tracks, out, store)
            assert len(store.cover_warnings) == 1
            assert 'different artwork colours' in next(iter(store.cover_warnings.values()))
        finally: store.close()
        if i == 0: assert len(readings) >= 2
    # First preview is intentionally ephemeral; the write-mode pass persists the audit.
    before = len(readings)
    store = ArtworkStore(out)
    try:
        plan(tracks, out, store)
        assert len(store.cover_warnings) == 1
    finally: store.close()
    assert len(readings) == before  # cached across process/store instances
    foreign.unlink()
    store = ArtworkStore(out)
    try:
        plan(tracks, out, store)
        assert not store.cover_warnings
    finally: store.close()


def test_v14_schema_upgrade_is_backed_up_once(tmp_path):
    out = tmp_path / 'existing-library'
    store = ArtworkStore(out)
    with store.db:
        store.db.execute('DROP TABLE folder_artwork_audit')  # v1.4 schema
    store.close()
    assert not list((out / '.oggcultist').glob('*.bak-*'))
    store = ArtworkStore(out)
    try:
        assert store.db.execute("SELECT name FROM sqlite_master WHERE name='folder_artwork_audit'").fetchone()
    finally:
        store.close()
    backups = list((out / '.oggcultist').glob('library.sqlite3.bak-*'))
    assert len(backups) == 1
    ArtworkStore(out).close()
    assert list((out / '.oggcultist').glob('library.sqlite3.bak-*')) == backups
