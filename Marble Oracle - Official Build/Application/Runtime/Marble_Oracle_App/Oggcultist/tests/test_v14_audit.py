"""Fifth independent audit pass: Oggcultist v1.4.0 (added 2026-11-04).

Conventions as before: plain tests = verified behaviour; xfail(strict=True) = confirmed defect
(ID in CODE_REVIEW_v1.4.md). History tests need OGGCULTIST_V10 (folder containing the original
v1.0 launch.py). The unprivileged test needs root + runuser + a `nobody` account.
"""
from __future__ import annotations
import hashlib
import os
import sqlite3
import subprocess
import sys
import threading
from pathlib import Path

import pytest

import oggcultist.artwork as artwork
from oggcultist.artwork import ArtworkStore
from oggcultist.core import plan, process, scan
from test_audit import flac, BASE, needs_ffmpeg
from test_v13_audit import album, cli, colour, needs_v10, needs_nobody, ROOT, V10


def sidecar_snapshot(folder: Path):
    return {p.name: (p.stat().st_size, p.stat().st_mtime_ns, hashlib.sha256(p.read_bytes()).hexdigest())
            for p in sorted(folder.iterdir())}


# --------------------------------------------------------------------------- J1: hashing cost
@needs_ffmpeg
def test_J1_plan_of_bound_library_does_not_rehash_outputs(tmp_path, monkeypatch):
    src, out = tmp_path / 'src', tmp_path / 'out'
    album(src, 'One', 3); album(src, 'Two', 3)
    tracks, _ = scan(src)
    assert process(tracks, out, threading.Event())['converted'] == 6   # folders are now bound
    hashed = []
    real = artwork._sha256_path
    monkeypatch.setattr(artwork, '_sha256_path', lambda p: (hashed.append(Path(p).name), real(p))[1])
    for read_only in (True, False):                                     # preview, then a --run style plan
        store = ArtworkStore(out, read_only=read_only)
        try: plan(tracks, out, store)
        finally: store.close()
    assert {t.status for t in tracks} == {'Done'}
    assert hashed == [], f'{len(hashed)} output hashes for an unchanged, already-bound library'


# --------------------------------------------------------------------------- H1 legitimate legacy
@needs_ffmpeg
@needs_v10
def test_v10_album_with_inferred_albumartist_keeps_colour(tmp_path):
    """Source has no ALBUMARTIST; v1.0 inferred and wrote one. The H1 tag check must still accept it."""
    src, out = tmp_path / 'src', tmp_path / 'out'
    tags = {k: v for k, v in BASE.items() if k != 'albumartist'}
    flac(src / 'Solo' / '01.flac', title='S1', tracknumber='1', **{**tags, 'album': 'Solo', 'artist': 'Singer feat. Guest'})
    assert cli(V10, src, out, run=True).returncode == 0
    first = colour(next(out.rglob('*.opus')))
    flac(src / 'Solo' / '02.flac', title='S2', tracknumber='2', **{**tags, 'album': 'Solo', 'artist': 'Singer'})
    tracks, _ = scan(src / 'Solo')
    assert process(tracks, out, threading.Event())['converted'] == 1
    assert {colour(p) for p in out.rglob('*.opus')} == {first}
    assert next(out.rglob('*.opus')).parent.parent.name == 'Singer'


# --------------------------------------------------------------------------- H2 stress
def test_preview_rolls_back_genuine_hot_journal_on_copy_only(tmp_path):
    ArtworkStore(tmp_path).close()
    db = tmp_path / '.oggcultist' / 'library.sqlite3'
    c = sqlite3.connect(db)
    c.executemany('INSERT INTO covers VALUES(?,?)', [(f'base{i}', f'{i:06X}') for i in range(2000)])
    c.commit(); c.close()
    code = (f"import sqlite3,os\nc=sqlite3.connect({str(db)!r}); c.execute('PRAGMA cache_size=1')\n"
            "c.execute('BEGIN'); c.execute('DELETE FROM covers')\n"
            "c.executemany('INSERT INTO covers VALUES(?,?)',[('junk'+str(i),'F'+format(i,'05X')) for i in range(3000)])\n"
            "os._exit(0)")                                               # dies mid-transaction, pages spilled
    subprocess.run([sys.executable, '-c', code], check=True)
    assert db.with_name(db.name + '-journal').stat().st_size > 0        # a real hot journal
    before = sidecar_snapshot(db.parent)
    store = ArtworkStore(tmp_path, read_only=True)
    try:
        base = store.db.execute("SELECT count(*) FROM covers WHERE album_key LIKE 'base%'").fetchone()[0]
        junk = store.db.execute("SELECT count(*) FROM covers WHERE album_key LIKE 'junk%'").fetchone()[0]
    finally: store.close()
    assert (base, junk) == (2000, 0)
    assert sidecar_snapshot(db.parent) == before


def test_previews_racing_live_wal_writer(tmp_path):
    ArtworkStore(tmp_path).close()
    db = tmp_path / '.oggcultist' / 'library.sqlite3'
    c = sqlite3.connect(db); c.execute('PRAGMA journal_mode=WAL'); c.close()
    writer = subprocess.Popen([sys.executable, '-c',
        f"import sqlite3\nc=sqlite3.connect({str(db)!r}); c.execute('PRAGMA wal_autocheckpoint=0')\n"
        "for i in range(2000):\n    c.execute('INSERT INTO covers VALUES(?,?)',('w'+str(i),format(i,'06X'))); c.commit()\n"])
    counts, errors = [], []
    while writer.poll() is None:
        try:
            s = ArtworkStore(tmp_path, read_only=True)
            counts.append(s.db.execute('SELECT count(*) FROM covers').fetchone()[0]); s.close()
        except Exception as exc:
            errors.append(repr(exc))
    assert writer.returncode == 0 and not errors, errors[:3]
    assert counts == sorted(counts)                                     # never goes backwards


@needs_nobody
def test_unprivileged_preview_of_wal_database_in_unwritable_folder():
    import shutil, tempfile
    root = Path(tempfile.mkdtemp(prefix='ogg-wal-ro-'))
    try:
        ArtworkStore(root).close()
        db = root / '.oggcultist' / 'library.sqlite3'
        c = sqlite3.connect(db); c.execute('PRAGMA journal_mode=WAL')
        c.execute("INSERT INTO covers VALUES('probe','ABCDEF')"); c.commit()
        subprocess.run([sys.executable, '-c', f"import sqlite3,os; c=sqlite3.connect({str(db)!r}); "
                        "c.execute(\"INSERT INTO covers VALUES('probe2','ABCDE0')\"); c.commit(); os._exit(0)"], check=True)
        # c stays open on purpose: closing would checkpoint and remove the -wal under test
        for p in [root, *root.rglob('*')]:
            os.chmod(p, 0o755 if p.is_dir() else 0o644)
        before = sidecar_snapshot(db.parent)
        r = subprocess.run(['runuser', '-u', 'nobody', '--', sys.executable, '-c',
                            f"import sys; sys.path.insert(0,{str(ROOT)!r}); from pathlib import Path; "
                            f"from oggcultist.artwork import ArtworkStore; s=ArtworkStore(Path({str(root)!r}),read_only=True); "
                            "print(s.db.execute(\"select count(*) from covers where album_key like 'probe%'\").fetchone()[0])"],
                           capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        assert r.stdout.strip() == '2'
        assert sidecar_snapshot(db.parent) == before
    finally:
        shutil.rmtree(root, ignore_errors=True)
