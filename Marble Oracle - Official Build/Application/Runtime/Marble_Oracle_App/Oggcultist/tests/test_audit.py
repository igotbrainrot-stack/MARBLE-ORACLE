"""Independent audit regression tests for Oggcultist v1.0.0 (added 2026-11-04).

Tests that PASS document behaviour verified as correct/safe.
Tests marked xfail(strict=True) reproduce a confirmed defect from CODE_REVIEW.md
(finding ID in the reason). They will turn into hard failures (XPASS-strict) once the
defect is fixed, at which point the marker should be removed.

All audio is synthetic (FFmpeg lavfi sine); no network access is used (MusicBrainz is mocked).
"""
from __future__ import annotations
import base64
import errno
import hashlib
import io
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import threading
from pathlib import Path
from types import SimpleNamespace
from urllib.error import HTTPError, URLError

import pytest
from mutagen.flac import FLAC, Picture
from mutagen.oggopus import OggOpus

from oggcultist import core, musicbrainz
from oggcultist.artwork import ArtworkStore, draw_cover, find_serif_font
from oggcultist.core import plan, process, scan, publish_no_overwrite, safe_component
from oggcultist.metadata import Track
from oggcultist.musicbrainz import MusicBrainz, MetadataLookupError

HAVE_FFMPEG = bool(shutil.which('ffmpeg') and shutil.which('ffprobe'))
needs_ffmpeg = pytest.mark.skipif(not HAVE_FFMPEG, reason='FFmpeg missing')


def flac(path: Path, seconds=1.0, layout=None, **tags) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    cmd = ['ffmpeg', '-loglevel', 'error', '-f', 'lavfi', '-i', f'sine=frequency=440:duration={seconds}']
    if layout:
        cmd += ['-af', f'pan={layout}|' + '|'.join(f'c{i}=c0' for i in range(6))]
    subprocess.run(cmd + ['-c:a', 'flac', '-y', str(path)], check=True)
    f = FLAC(path)
    for k, v in tags.items():
        f[k] = v if isinstance(v, list) else [v]
    f.save()
    return path


BASE = dict(album='Album', albumartist='Band', artist='Band', originaldate='1975', date='1975')


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def pictures_of(path: Path) -> bytes:
    return Picture(base64.b64decode(OggOpus(path)['metadata_block_picture'][0])).data


# --------------------------------------------------------------------------- H1
def test_H1_multidisc_subfolders_use_consistent_naming(tmp_path):
    src = tmp_path / 'src' / 'Album'
    flac(src / 'CD1' / '01.flac', title='Opening', tracknumber='1', discnumber='1/2', **BASE)
    flac(src / 'CD2' / '01.flac', title='Closing', tracknumber='1', discnumber='2/2', **BASE)
    tracks, _ = scan(tmp_path / 'src')
    plan(tracks, tmp_path / 'out')
    names = sorted(t.target.name for t in tracks)
    # Contract: multi-disc albums use a disc+track prefix on *every* disc.
    assert names == ['01-01 - Opening.opus', '02-01 - Closing.opus'], names


def test_H1_untagged_disc_subfolders_require_review(tmp_path):
    src = tmp_path / 'src' / 'Album'
    flac(src / 'CD1' / '01.flac', title='Opening', tracknumber='1', **BASE)
    flac(src / 'CD2' / '01.flac', title='Closing', tracknumber='1', **BASE)
    tracks, _ = scan(tmp_path / 'src')
    plan(tracks, tmp_path / 'out')
    ready = [t for t in tracks if t.status == 'Ready']
    same_folder = {t.target.parent for t in ready}
    # Two "track 1, disc 1" files from one album must not both be silently Ready in one folder.
    assert not (len(ready) == 2 and len(same_folder) == 1), [t.target for t in ready]


def test_H1_disc_total_is_parsed_from_slash_notation(tmp_path):
    """Disc/track totals must be parsed from 1/2 and 3/12."""
    p = flac(tmp_path / 'a.flac', title='T', tracknumber='3/12', discnumber='1/2', **BASE)
    t = Track.from_path(p)
    assert (t.disc, t.disc_total, t.track, t.track_total) == (1, 2, 3, 12)


# --------------------------------------------------------------------------- H2
def test_H2_one_album_folder_gets_one_cover_key(tmp_path):
    a = Track(source=tmp_path / 'set' / 'a.flac', size=1, album='Album', albumartist='Band', year='1975',
              title='A', track=1, disc=1, release_type='Album')
    b = Track(source=tmp_path / 'set' / 'b.flac', size=2, album='Album', albumartist='Band', year='1975',
              title='B', track=2, disc=1)
    c = Track(source=tmp_path / 'set' / 'c.flac', size=3, album='Album', albumartist='Band', year='1975',
              title='C', track=3, disc=1, release_id='11111111-2222-3333-4444-555555555555')
    plan([a, b, c], tmp_path / 'out')
    assert {t.status for t in (a, b, c)} == {'Ready'}
    assert len({t.target.parent for t in (a, b, c)}) == 1
    assert len({t.album_key() for t in (a, b, c)}) == 1, [t.album_key() for t in (a, b, c)]


@needs_ffmpeg
def test_H2_embedded_covers_identical_within_album(tmp_path):
    src = tmp_path / 'src' / 'Album'
    flac(src / '01.flac', title='A', tracknumber='1', releasetype='album', **BASE)
    flac(src / '02.flac', title='B', tracknumber='2', **BASE)
    tracks, _ = scan(tmp_path / 'src')
    r = process(tracks, tmp_path / 'out', threading.Event())
    assert r['converted'] == 2
    outs = sorted((tmp_path / 'out').rglob('*.opus'))
    assert len({o.parent for o in outs}) == 1
    assert pictures_of(outs[0]) == pictures_of(outs[1])


# --------------------------------------------------------------------------- H3
def _mb_payload(groups):
    return json.dumps({'release-groups': groups}).encode()


def _group(gid, title, artist, score=100, date='1975-01-01', ptype='Album'):
    return {'id': gid, 'title': title, 'score': score, 'first-release-date': date, 'primary-type': ptype,
            'artist-credit': [{'name': artist, 'artist': {'name': artist}}]}


class FakeResponse(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *a): self.close()


@pytest.fixture
def mb_mock(monkeypatch):
    calls = []
    state = SimpleNamespace(payload=_mb_payload([]), exc=None, calls=calls)

    def urlopen(req, timeout=None):
        calls.append(req)
        if state.exc: raise state.exc
        return FakeResponse(state.payload)
    monkeypatch.setattr(musicbrainz.request, 'urlopen', urlopen)
    monkeypatch.setattr(musicbrainz.time, 'sleep', lambda s: None)
    return state


def test_H3_auto_lookup_keeps_existing_mbids(tmp_path, mb_mock, monkeypatch):
    import launch
    existing = 'aaaaaaaa-0000-0000-0000-000000000000'
    flac(tmp_path / 'src' / 'Album' / '01.flac', title='A', tracknumber='1',
         musicbrainz_releasegroupid=existing, **BASE)
    mb_mock.payload = _mb_payload([_group('bbbbbbbb-1111-1111-1111-111111111111', 'Album', 'Band', date='1974')])
    seen = {}
    real_plan = launch.plan
    monkeypatch.setattr(launch, 'plan', lambda tracks, d, s: (seen.setdefault('t', tracks), real_plan(tracks, d, s)))
    args = SimpleNamespace(input=str(tmp_path / 'src'), output=str(tmp_path / 'out'), run=False,
                           musicbrainz=True, contact_email='audit@example.org')
    assert launch.cli(args) == 0
    t = seen['t'][0]
    assert t.releasegroup_id == existing, 'source MBID was replaced by a text-search result'


def test_mb_query_and_headers(mb_mock):
    mb = MusicBrainz('audit@example.org')
    mb_mock.payload = _mb_payload([_group('x', 'Album', 'Band')])
    res = mb.search('Al"bum', 'Band')
    req = mb_mock.calls[0]
    from oggcultist import __version__
    assert f'Oggcultist/{__version__} (mailto:audit@example.org)' == req.get_header('User-agent')
    from urllib.parse import urlparse, parse_qs
    q = parse_qs(urlparse(req.full_url).query)['query'][0]
    # Correctly escape quoted text, without the former stray whitespace.
    assert q == 'releasegroup:"Al\\\"bum" AND artist:"Band"'
    assert res[0]['reliable'] and MusicBrainz.confident(res) is res[0]


def test_mb_zero_ambiguous_misleading_and_errors(mb_mock):
    mb = MusicBrainz('audit@example.org')
    assert mb.search('Album', 'Band') == []
    assert MusicBrainz.confident([]) is None
    mb_mock.payload = _mb_payload([_group('1', 'Album', 'Band'), _group('2', 'Album', 'Band', score=97, date='2010')])
    assert MusicBrainz.confident(mb.search('Album', 'Band')) is None          # ambiguous
    mb_mock.payload = _mb_payload([_group('1', 'Album (Live)', 'Band')])
    assert MusicBrainz.confident(mb.search('Album', 'Band')) is None          # misleading near-name
    mb_mock.payload = _mb_payload([_group('1', 'Album', 'Band Tribute Orchestra')])
    assert MusicBrainz.confident(mb.search('Album', 'Band')) is None          # different artist
    for exc in (URLError('timed out'), HTTPError('u', 503, 'Service Unavailable', {}, None), TimeoutError()):
        mb_mock.exc = exc
        with pytest.raises(MetadataLookupError):
            mb.search('Album', 'Band')
    with pytest.raises(MetadataLookupError):
        MusicBrainz('not-an-email')


# --------------------------------------------------------------------------- M-findings
@needs_ffmpeg
def test_M1_cancel_reports_unprocessed_tracks(tmp_path):
    src = tmp_path / 'src' / 'Album'
    for n in (1, 2, 3):
        flac(src / f'{n:02}.flac', title=f'T{n}', tracknumber=str(n), **BASE)
    tracks, _ = scan(tmp_path / 'src')
    cancel = threading.Event()

    def progress(name, i, total, f):
        if i == 2: cancel.set()
    r = process(tracks, tmp_path / 'out', cancel, progress)
    assert r['cancelled'] and r['converted'] == 1
    assert len(r['results']) == 3, r['results']
    assert r['not_processed'] == 2


@needs_ffmpeg
def test_cancel_mid_encode_leaves_no_files_and_source_intact(tmp_path):
    src = tmp_path / 'src' / 'Album'
    p = flac(src / '01.flac', seconds=30, title='Long', tracknumber='1', **BASE)
    before = (sha(p), p.stat().st_mtime_ns)
    tracks, _ = scan(tmp_path / 'src')
    cancel = threading.Event()

    def progress(name, i, total, f):
        if f > 0.05: cancel.set()
    r = process(tracks, tmp_path / 'out', cancel, progress)
    assert r['cancelled'] and r['converted'] == 0
    assert not [q for q in (tmp_path / 'out').rglob('*') if q.is_file() and '.oggcultist' not in q.parts]
    assert (sha(p), p.stat().st_mtime_ns) == before


@needs_ffmpeg
def test_M2_truncated_output_not_reported_done(tmp_path):
    flac(tmp_path / 'src' / 'A' / '01.flac', title='T', tracknumber='1', **BASE)
    tracks, _ = scan(tmp_path / 'src')
    assert process(tracks, tmp_path / 'out', threading.Event())['converted'] == 1
    out = next((tmp_path / 'out').rglob('*.opus'))
    with open(out, 'r+b') as f: f.truncate(100)
    store = ArtworkStore(tmp_path / 'out')
    try: plan(tracks, tmp_path / 'out', store)
    finally: store.close()
    assert tracks[0].status != 'Done'
    assert out.stat().st_size == 100  # and it must still not be overwritten silently


@needs_ffmpeg
def test_M3_mtime_only_change_is_not_a_collision(tmp_path):
    p = flac(tmp_path / 'src' / 'A' / '01.flac', title='T', tracknumber='1', **BASE)
    tracks, _ = scan(tmp_path / 'src')
    process(tracks, tmp_path / 'out', threading.Event())
    os.utime(p, ns=(p.stat().st_atime_ns, p.stat().st_mtime_ns + 10**9))
    tracks, _ = scan(tmp_path / 'src')
    r = process(tracks, tmp_path / 'out', threading.Event())
    assert tracks[0].status == 'Done', tracks[0].note


@needs_ffmpeg
def test_M3_moved_library_still_recognised(tmp_path):
    flac(tmp_path / 'src' / 'A' / '01.flac', title='T', tracknumber='1', **BASE)
    tracks, _ = scan(tmp_path / 'src')
    process(tracks, tmp_path / 'out', threading.Event())
    shutil.move(str(tmp_path / 'out'), str(tmp_path / 'moved'))
    tracks, _ = scan(tmp_path / 'src')
    process(tracks, tmp_path / 'moved', threading.Event())
    assert tracks[0].status == 'Done', tracks[0].note


@needs_ffmpeg
def test_M4_source_changed_during_conversion_not_marked_done(tmp_path):
    p = flac(tmp_path / 'src' / 'A' / '01.flac', seconds=10, title='T', tracknumber='1', **BASE)
    tracks, _ = scan(tmp_path / 'src')
    touched = []

    def progress(name, i, total, f):
        if 0 < f < 1 and not touched:
            os.utime(p, ns=(p.stat().st_atime_ns, p.stat().st_mtime_ns + 10**9)); touched.append(1)
    process(tracks, tmp_path / 'out', threading.Event(), progress)
    assert touched
    tracks, _ = scan(tmp_path / 'src')
    store = ArtworkStore(tmp_path / 'out')
    try: plan(tracks, tmp_path / 'out', store)
    finally: store.close()
    assert tracks[0].status != 'Done'


@needs_ffmpeg
def test_M5_multivalue_artist_preserved(tmp_path):
    tags = {**BASE, 'artist': ['Singer', 'Guest Rapper']}
    flac(tmp_path / 'src' / 'A' / '01.flac', title='T', tracknumber='1', **tags)
    tracks, _ = scan(tmp_path / 'src')
    assert process(tracks, tmp_path / 'out', threading.Event())['converted'] == 1
    out = next((tmp_path / 'out').rglob('*.opus'))
    assert OggOpus(out)['artist'] == ['Singer', 'Guest Rapper']


@needs_ffmpeg
def test_M6_originaldate_not_fabricated(tmp_path):
    tags = {k: v for k, v in BASE.items() if k != 'originaldate'}
    tags['date'] = '2010-05-01'
    flac(tmp_path / 'src' / 'A' / '01.flac', title='T', tracknumber='1', **tags)
    tracks, _ = scan(tmp_path / 'src')
    assert process(tracks, tmp_path / 'out', threading.Event())['converted'] == 1
    out = next((tmp_path / 'out').rglob('*.opus'))
    assert 'originaldate' not in OggOpus(out), OggOpus(out)['originaldate']
    assert 'originalyear' not in OggOpus(out), OggOpus(out)['originalyear']


def test_M7_filename_track_guess_needs_review(tmp_path):
    t = Track(source=tmp_path / 'A' / '1999 - Party.flac', size=1, album='Album', albumartist='Band',
              year='1982', title='1999', track=0, disc=1)
    plan([t], tmp_path / 'out')
    # A filename-derived number must at least be flagged for review, never silently Ready.
    assert t.status != 'Ready', (t.track, t.target)


@needs_ffmpeg
def test_M8_surround_side_layout_converts(tmp_path):
    flac(tmp_path / 'src' / 'A' / '01.flac', layout='5.1(side)', title='T', tracknumber='1', **BASE)
    tracks, _ = scan(tmp_path / 'src')
    r = process(tracks, tmp_path / 'out', threading.Event())
    assert r['converted'] == 1, r['results'][0]['message']


@needs_ffmpeg
def test_surround_back_layout_converts(tmp_path):
    flac(tmp_path / 'src' / 'A' / '01.flac', layout='5.1', title='T', tracknumber='1', **BASE)
    tracks, _ = scan(tmp_path / 'src')
    assert process(tracks, tmp_path / 'out', threading.Event())['converted'] == 1


@needs_ffmpeg
@pytest.mark.parametrize('ext,codec', [('wma', 'wmav2'), ('wv', 'wavpack')])
def test_M9_wma_wavpack_tags_read(tmp_path, ext, codec):
    import mutagen
    p = tmp_path / f'a.{ext}'
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-f', 'lavfi', '-i', 'sine=d=1', '-c:a', codec, str(p)], check=True)
    f = mutagen.File(p)
    if f.tags is None: f.add_tags()
    key = 'WM/AlbumTitle' if ext == 'wma' else 'Album'
    f[key] = 'Album'
    f['Title'] = 'Song'
    f.save()
    t = Track.from_path(p)
    assert (t.title, t.album) == ('Song', 'Album')


@needs_ffmpeg
def test_mp3_m4a_tags_and_mbids_read(tmp_path):
    from mutagen.easyid3 import EasyID3
    from mutagen.mp4 import MP4, MP4FreeForm
    rg = 'cccccccc-0000-0000-0000-000000000000'
    mp3 = tmp_path / 'a.mp3'
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-f', 'lavfi', '-i', 'sine=d=1', '-c:a', 'libmp3lame', str(mp3)], check=True)
    e = EasyID3(mp3)
    e.update({'title': 'Song', 'album': 'Album', 'albumartist': 'Band', 'tracknumber': '3/12',
              'discnumber': '1/2', 'musicbrainz_releasegroupid': rg, 'originaldate': '1975'})
    e.save()
    m4a = tmp_path / 'a.m4a'
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-f', 'lavfi', '-i', 'sine=d=1', '-c:a', 'aac', str(m4a)], check=True)
    m = MP4(m4a)
    m.update({'\xa9nam': ['Song'], '\xa9alb': ['Album'], 'aART': ['Band'], 'trkn': [(3, 12)], 'disk': [(1, 2)],
              '----:com.apple.iTunes:MusicBrainz Release Group Id': [MP4FreeForm(rg.encode())],
              '----:com.apple.iTunes:ORIGINALDATE': [MP4FreeForm(b'1975')]})
    m.save()
    for p in (mp3, m4a):
        t = Track.from_path(p)
        assert (t.title, t.album, t.albumartist, t.track, t.disc, t.releasegroup_id, t.year) == \
               ('Song', 'Album', 'Band', 3, 1, rg, '1975'), p.suffix


# --------------------------------------------------------------------------- safety paths that PASS
def test_publish_fallback_never_overwrites(tmp_path, monkeypatch):
    staged, target = tmp_path / 'staged', tmp_path / 'target'
    staged.write_bytes(b'new')
    target.write_bytes(b'precious')
    monkeypatch.setattr(core.os, 'link', lambda a, b: (_ for _ in ()).throw(OSError(errno.EPERM, 'no links')))
    with pytest.raises(FileExistsError):
        publish_no_overwrite(staged, target)
    assert target.read_bytes() == b'precious' and staged.exists()


def test_publish_link_path_refuses_existing(tmp_path):
    staged, target = tmp_path / 'staged', tmp_path / 'target'
    staged.write_bytes(b'new'); target.write_bytes(b'precious')
    with pytest.raises(RuntimeError):
        publish_no_overwrite(staged, target)
    assert target.read_bytes() == b'precious'


def test_publish_fallback_copy_error_removes_partial(tmp_path, monkeypatch):
    staged, target = tmp_path / 'staged', tmp_path / 'target'
    staged.write_bytes(b'x' * 10)
    monkeypatch.setattr(core.os, 'link', lambda a, b: (_ for _ in ()).throw(OSError(errno.EPERM, 'no links')))

    def bad_copy(src, dst, n):
        dst.write(b'partial'); raise OSError(errno.ENOSPC, 'No space left on device')
    monkeypatch.setattr(core.shutil, 'copyfileobj', bad_copy)
    with pytest.raises(OSError):
        publish_no_overwrite(staged, target)
    assert not target.exists() and staged.exists()


def test_L1_publish_fallback_interrupt_removes_partial(tmp_path, monkeypatch):
    staged, target = tmp_path / 'staged', tmp_path / 'target'
    staged.write_bytes(b'x' * 10)
    monkeypatch.setattr(core.os, 'link', lambda a, b: (_ for _ in ()).throw(OSError(errno.EPERM, 'no links')))

    def interrupted(src, dst, n):
        dst.write(b'partial'); raise KeyboardInterrupt
    monkeypatch.setattr(core.shutil, 'copyfileobj', interrupted)
    with pytest.raises(KeyboardInterrupt):
        publish_no_overwrite(staged, target)
    assert not target.exists()


@needs_ffmpeg
def test_corrupt_and_empty_sources_fail_safely(tmp_path):
    src = tmp_path / 'src' / 'A'
    good = flac(src / '01.flac', title='Good', tracknumber='1', **BASE)
    bad = src / '02.flac'
    data = bytearray(good.read_bytes())
    bad.write_bytes(bytes(data[:len(data) // 3]))  # truncated FLAC
    (src / '03.flac').write_bytes(b'')
    (src / '04.mp3').write_bytes(os.urandom(4000))
    before = {p: sha(p) for p in src.iterdir()}
    tracks, problems = scan(tmp_path / 'src')
    assert {Path(p).name for p, _ in problems} >= {'03.flac', '04.mp3'}
    r = process(tracks, tmp_path / 'out', threading.Event())
    assert r['converted'] >= 1
    outs = [q for q in (tmp_path / 'out').rglob('*') if q.is_file() and '.oggcultist' not in q.parts]
    assert all(q.suffix == '.opus' and not q.name.startswith('.oggcultist-') for q in outs)
    assert {p: sha(p) for p in src.iterdir()} == before


def test_ffmpeg_failure_leaves_no_temp(tmp_path, monkeypatch):
    p = tmp_path / 'src' / 'x.flac'
    p.parent.mkdir(parents=True); p.write_bytes(b'not audio')
    t = Track(source=p, size=9, album='A', albumartist='B', year='2000', title='T', track=1, disc=1, originaldate='2000')
    if not HAVE_FFMPEG: pytest.skip('FFmpeg missing')
    r = process([t], tmp_path / 'out', threading.Event())
    assert r['errors'] == 1
    assert not [q for q in (tmp_path / 'out').rglob('*.opus')]
    assert p.read_bytes() == b'not audio'


def test_corrupt_database_is_not_destroyed(tmp_path):
    state = tmp_path / 'out' / '.oggcultist'
    state.mkdir(parents=True)
    (state / 'library.sqlite3').write_bytes(b'garbage' * 200)
    with pytest.raises(sqlite3.DatabaseError):
        ArtworkStore(tmp_path / 'out')
    assert (state / 'library.sqlite3').read_bytes() == b'garbage' * 200


@pytest.mark.parametrize('raw,expected', [
    ('aux.txt', '_aux.txt'), ('Con', '_Con'), ('LPT1.', '_LPT1'), ('...', 'Unknown'),
    ('a\tb', 'a-b'), ('x' * 300, 'x' * 130), ('../..', '-'), ('Trailing. ', 'Trailing'),
])
def test_safe_component_cases(raw, expected):
    assert safe_component(raw) == expected


def test_case_only_and_truncation_collisions_are_detected(tmp_path):
    long_a, long_b = 'L' * 140 + 'a', 'L' * 140 + 'b'
    ts = [Track(source=tmp_path / 'A' / f'{i}.flac', size=i, album='Album', albumartist='Band', year='2000',
                title=title, track=1, disc=1, originaldate='2000')
          for i, title in enumerate(['Song', 'SONG', long_a, long_b])]
    ts[2].track = ts[3].track = 2
    plan(ts, tmp_path / 'out')
    assert [t.status for t in ts] == ['Collision'] * 4


def test_identical_bytes_in_different_albums_are_not_flagged(tmp_path):
    (tmp_path / 's').mkdir()
    for n in ('a', 'b'): (tmp_path / 's' / f'{n}.flac').write_bytes(b'same')
    a = Track(source=tmp_path / 's' / 'a.flac', size=4, album='One', albumartist='X', year='2000', title='T', track=1, disc=1)
    b = Track(source=tmp_path / 's' / 'b.flac', size=4, album='Two', albumartist='X', year='2000', title='T', track=1, disc=1)
    plan([a, b], tmp_path / 'out')
    # Documented limitation (handover lead 11): cross-album exact duplicates are both Ready.
    assert a.status == b.status == 'Ready'


# --------------------------------------------------------------------------- cover
def test_L2_long_cover_text_fits(tmp_path):
    # Measure the rendered pixels rather than the original string which is elided.
    from PIL import Image, ImageChops
    name = 'An Extremely Long Album Title ' * 8
    png = draw_cover(name, 'Artist', '1999', '336699')
    im = Image.open(io.BytesIO(png)).convert('RGB')
    bg = Image.new('RGB', im.size, (0x33,0x66,0x99))
    bbox = ImageChops.difference(im, bg).getbbox()
    assert bbox is not None
    assert 20 <= bbox[0] < bbox[2] <= 580, bbox


def test_japanese_cover_has_text(tmp_path):
    from PIL import Image, ImageChops
    a = Image.open(io.BytesIO(draw_cover('東京の音楽', '日本語の歌手', '1995', 'FFFFFF'))).convert('RGB')
    b = Image.open(io.BytesIO(draw_cover('A', 'B', '1995', 'FFFFFF'))).convert('RGB')
    assert ImageChops.difference(a, b).getbbox() is not None
    # Detect ink specifically in the top album title's region.
    title_box = a.crop((15, 175, 585, 298))
    assert ImageChops.difference(title_box, Image.new('RGB', title_box.size, 'white')).getbbox()


def test_cover_basic_contract():
    from PIL import Image
    im = Image.open(io.BytesIO(draw_cover('Album', 'Artist', '1975', 'FFFFFF'))).convert('RGB')
    assert im.size == (600, 600)
    colours = {c for _, c in im.getcolors(1_000_000)}
    assert (255, 255, 255) in colours and (0, 0, 0) in colours  # white bg -> black ink
    corners = {im.getpixel(p) for p in [(0, 0), (599, 0), (0, 599), (599, 599)]}
    assert corners == {(255, 255, 255)}
