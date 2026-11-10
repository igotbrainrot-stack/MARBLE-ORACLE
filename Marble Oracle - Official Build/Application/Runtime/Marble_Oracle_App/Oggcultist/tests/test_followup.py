"""Follow-up audit of Oggcultist v1.1.0 (added 2026-11-04).

All previously confirmed failures are promoted to normal regression assertions
for the repaired Oggcultist v1.2 codebase.

Upgrade tests need the unmodified v1.0.0 source tree to build a genuine v1.0 library.
Point OGGCULTIST_V10 at it (the folder containing launch.py); otherwise they skip.
"""
from __future__ import annotations
import base64
import io
import os
import shutil
import sqlite3
import subprocess
import sys
import threading
from pathlib import Path

import pytest
from mutagen.flac import Picture
from mutagen.oggopus import OggOpus

from oggcultist.artwork import ArtworkStore, draw_cover
from oggcultist.core import plan, process, scan
from oggcultist.metadata import Track
from test_audit import flac, BASE, needs_ffmpeg, sha

V10 = os.environ.get('OGGCULTIST_V10', '')
needs_v10 = pytest.mark.skipif(not (V10 and (Path(V10) / 'launch.py').is_file()),
                               reason='Set OGGCULTIST_V10 to the v1.0.0 source folder')


def cover_bytes(path: Path) -> bytes:
    return Picture(base64.b64decode(OggOpus(path)['metadata_block_picture'][0])).data


def run_v10(src: Path, out: Path) -> None:
    subprocess.run([sys.executable, str(Path(V10) / 'launch.py'), '--cli', '--input', str(src),
                    '--output', str(out), '--run'], check=True, cwd=V10, capture_output=True)


def statuses(tracks):
    return {t.source.name: t.status for t in tracks}


def replan(src: Path, out: Path):
    tracks, _ = scan(src)
    store = ArtworkStore(out)
    try: plan(tracks, out, store)
    finally: store.close()
    return tracks


# --------------------------------------------------------------------------- upgrade from a real v1.0 library
@needs_ffmpeg
@needs_v10
def test_v10_library_upgrades_to_done_with_backup(tmp_path):
    src, out = tmp_path / 'src', tmp_path / 'out'
    for n in (1, 2):
        flac(src / 'Album' / f'{n:02}.flac', title=f'T{n}', tracknumber=str(n), **BASE)
    run_v10(src, out)
    outputs = {p: sha(p) for p in out.rglob('*.opus')}
    assert len(outputs) == 2
    tracks = replan(src, out)
    assert set(statuses(tracks).values()) == {'Done'}
    assert len(list((out / '.oggcultist').glob('library.sqlite3.bak-*'))) == 1
    assert {p: sha(p) for p in out.rglob('*.opus')} == outputs


@needs_ffmpeg
@needs_v10
def test_v10_library_moved_then_upgraded_is_recognised(tmp_path):
    src = tmp_path / 'src'
    flac(src / 'Album' / '01.flac', title='T', tracknumber='1', **BASE)
    run_v10(src, tmp_path / 'out')
    shutil.move(str(tmp_path / 'out'), str(tmp_path / 'moved'))
    assert statuses(replan(src, tmp_path / 'moved')) == {'01.flac': 'Done'}


@needs_ffmpeg
@needs_v10
def test_F1_album_started_in_v10_keeps_its_cover(tmp_path):
    src, out = tmp_path / 'src', tmp_path / 'out'
    flac(src / 'Album' / '01.flac', title='T1', tracknumber='1', **BASE)
    run_v10(src, out)                                   # v1.0 converts track 1
    flac(src / 'Album' / '02.flac', title='T2', tracknumber='2', **BASE)
    tracks, _ = scan(src)
    r = process(tracks, out, threading.Event())         # v1.1 adds track 2
    assert r['converted'] == 1
    a, b = sorted(out.rglob('*.opus'))
    assert cover_bytes(a) == cover_bytes(b)


# --------------------------------------------------------------------------- cover identity stability (v1.1 only)
@needs_ffmpeg
def test_F2_adding_untagged_track_later_keeps_cover(tmp_path):
    src, out = tmp_path / 'src', tmp_path / 'out'
    rid = '11111111-2222-3333-4444-555555555555'
    flac(src / 'Album' / '01.flac', title='T1', tracknumber='1', musicbrainz_albumid=rid, **BASE)
    flac(src / 'Album' / '02.flac', title='T2', tracknumber='2', musicbrainz_albumid=rid, **BASE)
    tracks, _ = scan(src)
    assert process(tracks, out, threading.Event())['converted'] == 2
    flac(src / 'Album' / '03.flac', title='T3', tracknumber='3', **BASE)     # bonus track, no MBID
    tracks, _ = scan(src)
    assert process(tracks, out, threading.Event())['converted'] == 1
    covers = {cover_bytes(p) for p in out.rglob('*.opus')}
    assert len(covers) == 1


def test_editions_with_conflicting_release_ids_require_review(tmp_path):
    a = Track(source=tmp_path / 'ed1' / 'a.flac', size=1, album='Album', albumartist='Band', year='1975',
              title='A', track=1, disc=1, originaldate='1975', release_id='r-one')
    b = Track(source=tmp_path / 'ed2' / 'b.flac', size=2, album='Album', albumartist='Band', year='1975',
              title='B', track=2, disc=1, originaldate='1975', release_id='r-two')
    plan([a, b], tmp_path / 'out')
    assert a.status == b.status == 'Review' and a.target is None


@pytest.mark.parametrize('folders', [('CD1', 'CD2'), ('Disc 1', 'Disc 2'), ('cd01', 'cd02'),
                                     ('Disc 1 - Early', 'Disc 2 - Late')])
def test_disc_folders_share_cover_and_prefix(tmp_path, folders):
    ts = [Track(source=tmp_path / 'Album' / f / '01.flac', size=i, album='Album', albumartist='Band',
                year='1975', originaldate='1975', title=f'T{i}', track=1, disc=i + 1)
          for i, f in enumerate(folders)]
    plan(ts, tmp_path / 'out')
    assert [t.status for t in ts] == ['Ready', 'Ready']
    assert [t.target.name for t in ts] == ['01-01 - T0.opus', '02-01 - T1.opus']
    assert ts[0].cover_key == ts[1].cover_key


def test_va_compilation_across_disc_folders(tmp_path):
    ts = [Track(source=tmp_path / 'Hits' / f'CD{d}' / f'{n}.flac', size=d * 10 + n, album='Hits',
                year='1990', originaldate='1990', title=f'S{d}{n}', artist=f'Act {d}{n}',
                track=n, disc=d, compilation=True)
          for d in (1, 2) for n in (1, 2)]
    plan(ts, tmp_path / 'out')
    assert {t.status for t in ts} == {'Ready'}
    assert {t.target.parts[-3] for t in ts} == {'Various Artists'}
    assert len({t.cover_key for t in ts}) == 1


# --------------------------------------------------------------------------- ledger portability
@needs_ffmpeg
def test_F3_moved_source_library_still_done(tmp_path):
    flac(tmp_path / 'src' / 'Album' / '01.flac', title='T', tracknumber='1', **BASE)
    tracks, _ = scan(tmp_path / 'src')
    process(tracks, tmp_path / 'out', threading.Event())
    shutil.move(str(tmp_path / 'src'), str(tmp_path / 'src-new-mount'))
    assert statuses(replan(tmp_path / 'src-new-mount', tmp_path / 'out')) == {'01.flac': 'Done'}


@needs_ffmpeg
def test_mtime_only_and_moved_output_are_done(tmp_path):
    p = flac(tmp_path / 'src' / 'A' / '01.flac', title='T', tracknumber='1', **BASE)
    tracks, _ = scan(tmp_path / 'src')
    process(tracks, tmp_path / 'out', threading.Event())
    os.utime(p, ns=(p.stat().st_atime_ns, p.stat().st_mtime_ns + 5 * 10**9))
    shutil.move(str(tmp_path / 'out'), str(tmp_path / 'moved'))
    assert statuses(replan(tmp_path / 'src', tmp_path / 'moved')) == {'01.flac': 'Done'}


def test_concurrent_migration_of_v10_database(tmp_path):
    errors = []
    for i in range(15):
        state = tmp_path / f'm{i}' / '.oggcultist'
        state.mkdir(parents=True)
        conn = sqlite3.connect(state / 'library.sqlite3')
        conn.execute('CREATE TABLE covers (album_key TEXT PRIMARY KEY, colour TEXT NOT NULL UNIQUE)')
        conn.execute('CREATE TABLE completed (source TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, output TEXT NOT NULL, output_size INTEGER, created TEXT DEFAULT CURRENT_TIMESTAMP)')
        conn.commit(); conn.close()
        barrier = threading.Barrier(2)

        def open_store():
            barrier.wait()
            try: ArtworkStore(tmp_path / f'm{i}').close()
            except Exception as exc: errors.append(repr(exc))
        threads = [threading.Thread(target=open_store) for _ in range(2)]
        for t in threads: t.start()
        for t in threads: t.join()
    assert not errors, errors


# --------------------------------------------------------------------------- tags
@needs_ffmpeg
def test_uppercase_ape_keys_recovered_by_easy_pass(tmp_path):
    """4-letter APE keys (DATE, ISRC) match the raw-ID3 skip regex but the easy pass restores them."""
    import mutagen
    p = tmp_path / 'a.wv'
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-f', 'lavfi', '-i', 'sine=d=1', '-c:a', 'wavpack', str(p)], check=True)
    f = mutagen.File(p)
    if f.tags is None: f.add_tags()
    f.update({'TITLE': 'Song', 'ALBUM': 'Album', 'DATE': '1975', 'ISRC': 'GBAAA7500001'})   # foobar2000 style
    f.save()
    t = Track.from_path(p)
    assert (t.title, t.album, t.year, t.tags.get('isrc')) == ('Song', 'Album', '1975', ['GBAAA7500001'])


@needs_ffmpeg
def test_F4_ape_multivalue_album_artist(tmp_path):
    import mutagen
    p = tmp_path / 'src' / 'Album' / '01.wv'
    p.parent.mkdir(parents=True)
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-f', 'lavfi', '-i', 'sine=d=1', '-c:a', 'wavpack', str(p)], check=True)
    f = mutagen.File(p)
    if f.tags is None: f.add_tags()
    f.update({'Title': 'Song', 'Album': 'Album', 'Album Artist': ['Duo One', 'Duo Two'],
              'Artist': ['Duo One', 'Duo Two'], 'Year': '1975', 'Track': '1'})
    f.save()
    tracks, _ = scan(tmp_path / 'src')
    assert tracks[0].tags.get('artist') == ['Duo One', 'Duo Two']
    assert '\x00' not in tracks[0].albumartist


def test_id3_raw_frames_no_longer_leak_but_mbids_kept(tmp_path):
    from mutagen.easyid3 import EasyID3
    p = tmp_path / 'a.mp3'
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-f', 'lavfi', '-i', 'sine=d=1', '-c:a', 'libmp3lame', str(p)], check=True)
    e = EasyID3(p)
    e.update({'title': 'Song', 'artistsort': 'Band, The', 'musicbrainz_trackid': 'trk-1', 'isrc': 'GB0000000001'})
    e.save()
    tags = Track.from_path(p).tags
    assert not {'tsse', 'tsop', 'ufid:http://musicbrainz.org'} & set(tags)
    assert tags['artistsort'] == ['Band, The'] and tags['musicbrainz_trackid'] == ['trk-1']
    assert tags['isrc'] == ['GB0000000001']


# --------------------------------------------------------------------------- covers
@pytest.mark.parametrize('label', ['東京の音楽', '서울의 노래', '北京之歌'])
def test_cjk_titles_render(label):
    from PIL import Image, ImageChops
    try:
        png = draw_cover(label, 'X', '1995', 'FFFFFF')
    except RuntimeError as exc:
        if 'No installed serif font' in str(exc):
            pytest.skip('Optional CJK serif font not installed')
        raise
    a = Image.open(io.BytesIO(png)).convert('RGB')
    top = a.crop((15, 150, 585, 300))
    assert ImageChops.difference(top, Image.new('RGB', top.size, 'white')).getbbox()


@pytest.mark.parametrize('label', ['أغنية عربية', 'เพลงไทย', 'हिंदी गीत', 'ＡＢＣ'])
def test_F7_other_scripts_render_real_glyphs(label):
    from PIL import ImageFont
    from oggcultist.artwork import _serif_for_text, find_serif_font
    try:
        font_file = _serif_for_text(label, find_serif_font())
    except RuntimeError as exc:
        if 'No installed serif font' in str(exc):
            pytest.skip(f'Optional writing-system font not installed: {label}')
        raise
    font = ImageFont.truetype(font_file, 40)
    notdef = font.getmask('\U0010FFFD').getbbox()   # what a missing glyph looks like in this font
    for ch in label.replace(' ', ''):
        box = font.getmask(ch).getbbox()
        assert box and bytes(font.getmask(ch)) != bytes(font.getmask('\U0010FFFD')), (label, ch)
