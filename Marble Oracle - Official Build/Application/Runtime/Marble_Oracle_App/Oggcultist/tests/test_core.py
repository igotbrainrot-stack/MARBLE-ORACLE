from pathlib import Path
import base64
import hashlib
import shutil
import subprocess
import threading
import pytest
from mutagen.flac import FLAC, Picture
from mutagen.oggopus import OggOpus
from oggcultist.artwork import ArtworkStore, draw_cover, preferred_ink
from oggcultist.core import (plan, process, safe_component, scan, target_path, validate_folders, _copy_without_reencode)
from oggcultist.metadata import Track
from oggcultist.musicbrainz import MusicBrainz


def make_track(path, albumartist='An Album Artist', album='Test Album', year='1988', title='One',
               n=1, artist='An Album Artist feat. A Guest', disc=1):
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(['ffmpeg','-loglevel','error','-f','lavfi','-i','sine=frequency=500:duration=1.2',
                    '-c:a','flac','-y',str(path)],check=True)
    obj=FLAC(path)
    obj['album']=[album]
    obj['albumartist']=[albumartist]
    obj['artist']=[artist]
    obj['title']=[title]
    obj['date']=['2020-10-15']
    obj['originaldate']=[year+'-02-01']
    obj['tracknumber']=[str(n)]
    obj['discnumber']=[str(disc)]
    obj['genre']=['Test genre']
    obj.save()
    return path


def test_portable_filenames_and_paths(tmp_path):
    t=Track(source=tmp_path/'dummy.mp3',size=1,title='A:B?C',albumartist='Composer / Orchestra',
            album='Demo: A',year='1996',track=2,disc=1)
    p=target_path(t,tmp_path/'Music')
    assert p.name == '02 - A-B-C.opus'
    assert 'Composer - Orchestra' in str(p)
    assert safe_component('CON')=='_CON'
    assert '..' not in str(safe_component('../../oops'))
    assert target_path(t,tmp_path/'Music',True).name=='01-02 - A-B-C.opus'
    with pytest.raises(ValueError):validate_folders(tmp_path,tmp_path/'child')


def test_group_inference_and_no_feature_folders(tmp_path):
    a=Track(source=tmp_path/'set'/'one.flac',size=10,album='Group',title='First',artist='Star feat. Guest',year='1998',track=1,disc=1)
    b=Track(source=tmp_path/'set'/'two.flac',size=10,album='Group',title='Second',artist='Star featuring Other',year='1998',track=2,disc=1)
    plan([a,b],tmp_path/'out')
    assert a.status==b.status=='Ready'
    assert a.albumartist==b.albumartist=='Star'
    assert 'Star/1998 - Group' in str(a.target)
    assert 'Guest' not in str(a.target)
    assert a.artist=='Star feat. Guest'


def test_ambiguous_artists_review(tmp_path):
    a=Track(source=tmp_path/'set'/'a.flac',size=10,album='Group',artist='Singer A',year='2021',track=1)
    b=Track(source=tmp_path/'set'/'b.flac',size=10,album='Group',artist='Singer B',year='2021',track=2)
    plan([a,b],tmp_path/'out')
    assert a.status==b.status=='Review'
    assert a.target is None
    assert 'Missing album artist' in a.issues


def test_multidisc(tmp_path):
    a=Track(source=tmp_path/'set'/'a.flac',size=10,album='Disc set',albumartist='Composer',year='2001',title='Opening',track=1,disc=1)
    b=Track(source=tmp_path/'set'/'b.flac',size=10,album='Disc set',albumartist='Composer',year='2001',title='Closing',track=1,disc=2)
    plan([a,b],tmp_path/'Music')
    assert a.target.name=='01-01 - Opening.opus'
    assert b.target.name=='02-01 - Closing.opus'


def test_colour_unique_and_persistent(tmp_path):
    store=ArtworkStore(tmp_path)
    colours=[store.colour_for(f'album-{i}') for i in range(250)]
    assert len(colours)==len(set(colours))
    assert store.colour_for('album-1')==colours[1]
    image=store.cover_for('album-1','Title','Artist','1967')
    assert image[:8]==b'\x89PNG\r\n\x1a\n'
    store.close()
    reopened=ArtworkStore(tmp_path)
    assert reopened.colour_for('album-1')==colours[1]
    reopened.close()


def test_confident_musicbrainz_does_not_guess():
    base={'album':'Same','albumartist':'A Singer','year':'1970','score':98,'match':100,'reliable':True}
    assert MusicBrainz.confident([base]) is base
    assert MusicBrainz.confident([base,{**base,'score':95}]) is None
    assert MusicBrainz.confident([{**base,'year':''}]) is None
    assert MusicBrainz.confident([{**base,'reliable':False}]) is None


@pytest.mark.skipif(not shutil.which('ffmpeg') or not shutil.which('ffprobe'),reason='FFmpeg missing')
def test_full_conversion_and_non_destructive_rerun(tmp_path):
    source=tmp_path/'originals'
    output=tmp_path/'Music'
    path=make_track(source/'artist'/'One.flac')
    before_sha=hashlib.sha256(path.read_bytes()).hexdigest()
    before_stat=path.stat().st_mtime_ns
    tracks,errs=scan(source)
    assert not errs
    assert len(tracks)==1
    assert tracks[0].year=='1988'
    result=process(tracks,output,threading.Event())
    assert result['converted']==1, result
    final=output/'An Album Artist'/'1988 - Test Album'/'01 - One.opus'
    assert final.is_file()
    ogg=OggOpus(final)
    assert ogg.get('albumartist')==['An Album Artist']
    assert ogg.get('artist')==['An Album Artist feat. A Guest']
    assert ogg.get('originalyear')==['1988']
    assert ogg.get('genre')==['Test genre']
    assert ogg.get('oggcultist_target_bitrate')==['96000']
    assert ogg.get('oggcultist_vbr')==['on']
    picture=Picture(base64.b64decode(ogg['metadata_block_picture'][0]))
    assert picture.mime=='image/png' and picture.width==600 and picture.height==600
    assert hashlib.sha256(path.read_bytes()).hexdigest()==before_sha
    assert path.stat().st_mtime_ns==before_stat
    first_output=final.read_bytes()
    again=process(tracks,output,threading.Event())
    assert again['converted']==0
    assert final.read_bytes()==first_output
    assert not list(final.parent.glob('*.part'))
    assert (output/'.oggcultist'/'library.sqlite3').is_file()
    assert list((output/'.oggcultist'/'reports').glob('*.csv'))


@pytest.mark.skipif(not shutil.which('ffmpeg') or not shutil.which('ffprobe'),reason='FFmpeg missing')
def test_duplicate_collision_and_never_overwrite(tmp_path):
    source=tmp_path/'source'
    p=make_track(source/'album'/'one.flac')
    (source/'album'/'other.flac').write_bytes(p.read_bytes())
    tracks,errs=scan(source)
    plan(tracks,tmp_path/'out')
    assert {t.status for t in tracks}=={'Duplicate'}
    assert all('Identical source bytes' in t.note for t in tracks)
    tracks=tracks[:1]
    dest=tmp_path/'out'
    target=dest/'An Album Artist'/'1988 - Test Album'/'01 - One.opus'
    target.parent.mkdir(parents=True)
    target.write_text('something precious')
    result=process(tracks,dest,threading.Event())
    assert result['converted']==0
    assert target.read_text()=='something precious'
    assert tracks[0].status=='Collision'


@pytest.mark.skipif(not shutil.which('ffmpeg') or not shutil.which('ffprobe'),reason='FFmpeg missing')
def test_existing_oggcultist_opus_stream_copy(tmp_path):
    source=tmp_path/'s'
    out=tmp_path/'o'
    make_track(source/'a.flac')
    original,_=scan(source)
    assert process(original,out,threading.Event())['converted']==1
    result_file=next(out.glob('**/*.opus'))
    assert _copy_without_reencode(Track.from_path(result_file))
    # Original converted files may be passed as input to a new destination.
    new_dest=tmp_path/'second'
    recs,_=scan(out)
    processed=process(recs,new_dest,threading.Event())
    assert processed['converted']==1
    assert processed['results'][0]['audio_copied'] is True


def test_compilation_classification(tmp_path):
    a=Track(source=tmp_path/'collection'/'1.flac',size=5,album='Mixtape',title='One',artist='Artist One',year='2010',track=1,disc=1,compilation=True)
    b=Track(source=tmp_path/'collection'/'2.flac',size=6,album='Mixtape',title='Two',artist='Artist Two',year='2010',track=2,disc=1,compilation=True)
    plan([a,b],tmp_path/'Music')
    assert a.albumartist==b.albumartist=='Various Artists'
    assert a.target.parts[-3]=='Various Artists'
    assert a.status==b.status=='Ready'


def test_duplicate_in_same_album_with_different_titles(tmp_path):
    from oggcultist.core import plan
    source=tmp_path/'s'
    source.mkdir()
    (source/'a.flac').write_bytes(b'original audio input file')
    (source/'b.flac').write_bytes(b'original audio input file')
    a=Track(source=source/'a.flac',size=25,album='Recording',albumartist='Singer',title='Alternate title',year='2002',track=1,disc=1)
    b=Track(source=source/'b.flac',size=25,album='Recording',albumartist='Singer',title='Different title',year='2002',track=2,disc=1)
    plan([a,b],tmp_path/'Music')
    assert a.status==b.status=='Duplicate'
    assert a.target!=b.target
    assert a.duplicate_group==b.duplicate_group


def test_musicbrainz_credit_joins_artists():
    from oggcultist.musicbrainz import artist_credit
    sample=[{'name':'Artist One','joinphrase':' & ','artist':{'name':'Artist One'}},
            {'name':'Artist Two','artist':{'name':'Artist Two'}}]
    assert artist_credit(sample)=='Artist One & Artist Two'


def test_conflicting_compilation_not_silently_reassigned(tmp_path):
    a=Track(source=tmp_path/'album'/'a.flac',size=6,album='Compilation',albumartist='Curator',artist='Act One',title='A',year='2000',track=1,disc=1,compilation=True)
    b=Track(source=tmp_path/'album'/'b.flac',size=7,album='Compilation',albumartist='Curator',artist='Act Two',title='B',year='2000',track=2,disc=1,compilation=True)
    plan([a,b],tmp_path/'out')
    assert a.status==b.status=='Review'
    assert any('compilation conflicts' in issue for issue in a.issues)


def test_title_missing_gets_flagged(tmp_path):
    t=Track(source=tmp_path/'01 - Unknown.flac',size=8,album='Album',albumartist='Artist',year='2000',title='01 - Unknown',unverified_title=True,track=1,disc=1)
    plan([t],tmp_path/'out')
    assert t.status=='Review'
