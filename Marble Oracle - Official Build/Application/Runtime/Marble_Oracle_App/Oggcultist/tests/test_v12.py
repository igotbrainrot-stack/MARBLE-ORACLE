"""Additional v1.2 integrity checks, independent of Claude's regression suite."""
import os
import shutil
import sqlite3
import threading
from pathlib import Path
import pytest
from oggcultist.artwork import ArtworkStore
from oggcultist.core import process, scan, plan
from test_audit import BASE, flac, sha

NEEDS_FFMPEG = pytest.mark.skipif(not (shutil.which('ffmpeg') and shutil.which('ffprobe')),
                                 reason='FFmpeg is required')


def test_different_album_folders_get_distinct_covers(tmp_path):
    from oggcultist.metadata import Track
    out = tmp_path / 'out'
    tracks = [Track(source=tmp_path / 'src' / album / '01.flac', size=10,
                    album=album, albumartist='Band', year='1975', originaldate='1975',
                    title='Song', disc=1, track=1) for album in ('First', 'Second')]
    store = ArtworkStore(out)
    try:
        plan(tracks, out, store)
        assert tracks[0].cover_key != tracks[1].cover_key
        colours = [store.colour_for(t.cover_key) for t in tracks]
        assert len(set(colours)) == 2
        plan(tracks, out, store)
        assert [store.colour_for(t.cover_key) for t in tracks] == colours
    finally:
        store.close()


@NEEDS_FFMPEG
def test_moved_source_with_changed_bytes_not_adopted(tmp_path):
    original = flac(tmp_path / 'src' / 'A' / '01.flac', title='Song', tracknumber='1', **BASE)
    tracks, _ = scan(tmp_path / 'src')
    assert process(tracks, tmp_path / 'out', threading.Event())['converted'] == 1
    before = sha(next((tmp_path / 'out').rglob('*.opus')))
    shutil.move(str(tmp_path / 'src'), str(tmp_path / 'src-new'))
    # Same tags, different signal: source content must not be implicitly adopted.
    new_path = tmp_path / 'src-new' / 'A' / '01.flac'
    flac(new_path, seconds=1.2, title='Song', tracknumber='1', **BASE)
    tracks, _ = scan(tmp_path / 'src-new')
    store = ArtworkStore(tmp_path / 'out')
    try:
        plan(tracks, tmp_path / 'out', store)
    finally:
        store.close()
    assert tracks[0].status == 'Collision'
    assert sha(next((tmp_path / 'out').rglob('*.opus'))) == before


@NEEDS_FFMPEG
def test_foreign_invalid_output_remains_collision(tmp_path):
    original = flac(tmp_path / 'src' / 'A' / '01.flac', title='Song', tracknumber='1', **BASE)
    tracks, _ = scan(tmp_path / 'src')
    plan(tracks, tmp_path / 'out')
    target = tracks[0].target
    target.parent.mkdir(parents=True)
    target.write_bytes(b'EXISTING FOREIGN FILE, DO NOT MODIFY')
    before = target.read_bytes()
    result = process(tracks, tmp_path / 'out', threading.Event())
    assert result['converted'] == 0
    assert target.read_bytes() == before
    assert original.is_file()


def test_missing_script_font_raises_instead_of_silent_text_loss(monkeypatch):
    from oggcultist import artwork
    monkeypatch.setattr(artwork, '_font_has_text', lambda font, label: False)
    with pytest.raises(RuntimeError, match='No installed serif font'):
        artwork._serif_for_text('أغنية', artwork.find_serif_font())


def test_musicbrainz_retries_only_transient_http_errors(monkeypatch):
    import io
    from urllib.error import HTTPError
    from oggcultist import musicbrainz
    from oggcultist.musicbrainz import MusicBrainz
    from test_audit import _group, _mb_payload
    attempts = []
    sleeps = []
    class Reply(io.BytesIO):
        def __enter__(self): return self
        def __exit__(self, *args): self.close()
    def get(req, timeout=12):
        attempts.append(1)
        if len(attempts) < 3:
            raise HTTPError(req.full_url, 503, 'Unavailable', {'Retry-After': '0'}, None)
        return Reply(_mb_payload([_group('one','Album','Band')]))
    monkeypatch.setattr(musicbrainz.request, 'urlopen', get)
    monkeypatch.setattr(musicbrainz.time, 'sleep', lambda seconds: sleeps.append(seconds))
    mb = MusicBrainz('audit@example.org')
    result = mb.search('Album','Band')
    assert len(attempts) == 3
    assert result[0]['album'] == 'Album'
    assert len(sleeps) >= 2
