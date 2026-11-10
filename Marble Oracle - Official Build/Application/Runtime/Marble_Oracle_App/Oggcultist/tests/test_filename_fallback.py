"""Untagged YouTube MP3 filename fallback: transparent, no guessed artist/year."""
from __future__ import annotations
import hashlib
import shutil
import subprocess
import threading
from pathlib import Path
import pytest
from mutagen.oggopus import OggOpus
from mutagen.flac import Picture
import base64
from oggcultist.core import scan, plan, process, target_path
from oggcultist.metadata import filename_remix_credit, Track

NAMES = [
    'Better Off Alone x Clarity x Unlock It x Alone - Agartha Remix',
    'Domino - Agartha Remix',
    'Down Under - Agartha Remix',
    'Feel So Close - Calvin Harris - Agartha Remix',
    'Hava Nagila - Agartha Remix',
    'Hot n Cold - Agartha Remix',
    "L'amour toujours x clear them out! - Agartha Remix",
    'The Days - Agartha Remix',
]

@pytest.mark.parametrize('name', NAMES)
def test_reported_suffixes_identify_one_remixer(name):
    assert filename_remix_credit(name) == ('Agartha', name)

@pytest.mark.parametrize('name', [
    'Song without tags', 'Unknown Song - Live', 'Song - Original Remix',
    'Song - Ariana Grande', 'Official Audio', 'Song - 320kbps',
])
def test_uncertain_filenames_not_guessed(name):
    assert filename_remix_credit(name) is None

def test_parenthetical_and_youtube_wrapper():
    assert filename_remix_credit('My Song (Agartha Remix)') == ('Agartha', 'My Song (Agartha Remix)')
    assert filename_remix_credit('My Song [Agartha Remix]') == ('Agartha', 'My Song [Agartha Remix]')
    assert filename_remix_credit('My Song - Agartha Remix [Official Audio]') == ('Agartha', 'My Song - Agartha Remix')

@pytest.mark.skipif(not shutil.which('ffmpeg') or not shutil.which('ffprobe'), reason='FFmpeg needed')
def test_eight_unlabelled_mp3s_convert_safely(tmp_path):
    src=tmp_path/'src'/'YouTube remixes'
    out=tmp_path/'out'
    src.mkdir(parents=True)
    original={}
    for i,name in enumerate(NAMES):
        p=src/(name+'.mp3')
        subprocess.run(['ffmpeg','-loglevel','error','-f','lavfi','-i',
                        f'sine=frequency={400+i*10}:duration=0.25', '-map_metadata','-1',
                        '-c:a','libmp3lame','-q:a','7','-y',str(p)],check=True)
        original[p]=(hashlib.sha256(p.read_bytes()).hexdigest(),p.stat().st_mtime_ns)
    tracks, errs=scan(tmp_path/'src')
    assert len(tracks)==8 and not errs
    plan(tracks,out)
    assert {t.status for t in tracks}=={'Ready'}, [(t.source,t.issues) for t in tracks]
    assert {t.albumartist for t in tracks}=={'Agartha'}
    assert {t.album for t in tracks}=={'Agartha Remixes'}
    assert {t.year for t in tracks}=={''}
    assert {t.artist for t in tracks}=={''}
    assert sorted(t.track for t in tracks)==list(range(1,9))
    assert {t.target.parent.relative_to(out).as_posix() for t in tracks}=={'Agartha/Unknown Year - Agartha Remixes'}
    assert all('Filename suffix' in t.note for t in tracks)
    r=process(tracks,out,threading.Event())
    assert r['converted']==8 and r['errors']==0, r
    assert r['not_processed']==0
    files=sorted(out.rglob('*.opus'))
    assert len(files)==8
    for p in files:
        ogg=OggOpus(p)
        assert ogg['albumartist']==['Agartha']
        assert ogg['album']==['Agartha Remixes']
        assert ogg['remixer']==['Agartha']
        assert ogg['oggcultist_metadata_source']==['filename_remix_suffix']
        assert 'originaldate' not in ogg and 'originalyear' not in ogg
        assert 'artist' not in ogg
        pic=Picture(base64.b64decode(ogg['metadata_block_picture'][0]))
        assert (pic.width,pic.height)==(600,600)
    for p, (digest, mtime) in original.items():
        assert hashlib.sha256(p.read_bytes()).hexdigest()==digest and p.stat().st_mtime_ns==mtime
    r2=process(tracks,out,threading.Event())
    assert r2['converted']==0 and r2['already_done']==8, r2

@pytest.mark.skipif(not shutil.which('ffmpeg'), reason='FFmpeg needed')
def test_untagged_unrecognised_remains_review_and_tagged_title_is_not_reinterpreted(tmp_path):
    from mutagen.mp3 import MP3
    src=tmp_path/'src';src.mkdir()
    paths=[src/'Mystery - Live.mp3',src/'Known Song - Agartha Remix.mp3']
    for p in paths:
        subprocess.run(['ffmpeg','-loglevel','error','-f','lavfi','-i','sine=d=0.2','-c:a','libmp3lame','-y',str(p)],check=True)
    from mutagen.id3 import ID3, TIT2, TALB, TPE2, TPE1, TRCK, TDRC
    tags=ID3(paths[1]);tags.add(TIT2(encoding=3,text='Actual title'));tags.add(TALB(encoding=3,text='Official Album'))
    tags.add(TPE2(encoding=3,text='Official Group'));tags.add(TPE1(encoding=3,text='Original Singer'))
    tags.add(TRCK(encoding=3,text='1'));tags.add(TDRC(encoding=3,text='2001'));tags.save(paths[1])
    tracks,_=scan(src);plan(tracks,tmp_path/'out')
    byname={t.source.name:t for t in tracks}
    assert byname['Mystery - Live.mp3'].status=='Review'
    t=byname['Known Song - Agartha Remix.mp3']
    assert t.status=='Ready' and t.albumartist=='Official Group' and t.title=='Actual title'
    assert not t.filename_inferred


def test_provisional_collection_never_auto_musicbrainz_matches(tmp_path):
    from oggcultist.musicbrainz import MusicBrainz
    t=Track(source=tmp_path/'Domino - Agartha Remix.mp3',size=1,
            title='Domino - Agartha Remix', album='Agartha Remixes',albumartist='Agartha',
            filename_inferred=True)
    assert MusicBrainz.auto_lookup_safe([t]) is False
