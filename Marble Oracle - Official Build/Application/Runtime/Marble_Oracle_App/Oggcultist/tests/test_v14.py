"""Regression coverage added after Claude's v1.3 follow-up audit."""
from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

from oggcultist.artwork import ArtworkStore


def _state_snapshot(root: Path) -> dict[str, tuple[bytes | None, int]]:
    """Capture on-disk bytes and mtimes (including SQLite journal sidecars)."""
    result = {}
    for p in sorted(root.rglob('*')):
        result[str(p.relative_to(root))] = (
            p.read_bytes() if p.is_file() else None, p.stat().st_mtime_ns
        )
    return result


def test_readonly_wal_snapshot_never_changes_original_db(tmp_path):
    root = tmp_path / 'dest'
    ArtworkStore(root).close()
    db = root / '.oggcultist' / 'library.sqlite3'
    conn = sqlite3.connect(db)
    conn.execute('PRAGMA journal_mode=WAL')
    conn.close()
    # Deliberately exit with os._exit so committed data remains in -wal.
    script = ("import sqlite3,os,sys; c=sqlite3.connect(sys.argv[1]); "
              "c.execute(\"INSERT INTO covers VALUES ('wal-test', '123456')\"); "
              "c.commit(); os._exit(0)")
    subprocess.run([sys.executable, '-c', script, str(db)], check=True)
    assert (db.parent / 'library.sqlite3-wal').stat().st_size > 0
    before = _state_snapshot(root)
    store = ArtworkStore(root, read_only=True)
    try:
        assert store.db.execute("SELECT colour FROM covers WHERE album_key='wal-test'").fetchone() == ('123456',)
    finally:
        store.close()
    assert _state_snapshot(root) == before


def test_readonly_journal_snapshot_does_not_touch_destination(tmp_path):
    root = tmp_path / 'dest'
    ArtworkStore(root).close()
    db = root / '.oggcultist' / 'library.sqlite3'
    # SQLite's hot journals are generated only after an interrupted transaction.
    # An empty stale journal suffices to test that the preview reads from a temp
    # copy and does not delete the original sidecar.
    journal = db.with_name(db.name + '-journal')
    journal.write_bytes(b'')
    before = _state_snapshot(root)
    store = ArtworkStore(root, read_only=True)
    try:
        assert store.db.execute('SELECT count(*) FROM completed').fetchone()[0] == 0
    finally:
        store.close()
    assert _state_snapshot(root) == before
