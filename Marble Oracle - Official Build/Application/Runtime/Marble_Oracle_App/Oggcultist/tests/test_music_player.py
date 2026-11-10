"""Local music player: metadata, playlist durability, and non-writing subprocess control."""
from __future__ import annotations

import io
import os
import subprocess
import threading
from pathlib import Path

import pytest
from mutagen.flac import FLAC

from oggcultist.player import (FFplayTransport, PlaylistStore, PlayerError, Song,
                               read_song, scan_music_library)
from test_audit import flac, BASE, needs_ffmpeg
import setup_ffmpeg


@needs_ffmpeg
def test_tagged_track_artist_and_duration(tmp_path):
    p = tmp_path / 'Disc' / 'One.flac'
    flac(p, **{**BASE, 'artist': 'Track Performer', 'albumartist': 'Album Performer',
               'title': 'Finale', 'album': 'The Record', 'tracknumber': '3/12', 'discnumber': '2'})
    before = p.read_bytes()
    song = read_song(p)
    assert (song.artist, song.title, song.album, song.track, song.disc) == (
        'Album Performer', 'Finale', 'The Record', 3, 2)
    assert song.duration > 0 and p.read_bytes() == before


@needs_ffmpeg
def test_untagged_audio_still_listed_and_source_preserved(tmp_path):
    p = tmp_path / 'Misc' / 'Agartha - Signal.flac'
    flac(p, **{**BASE, 'title': '', 'album': '', 'artist': '', 'albumartist': ''})
    before = p.read_bytes()
    songs, errors = scan_music_library(tmp_path)
    assert len(songs) == 1 and not errors
    assert songs[0].artist == 'Unknown Artist'
    assert songs[0].title == 'Agartha - Signal'
    assert songs[0].album == 'Misc'
    assert p.read_bytes() == before


@needs_ffmpeg
def test_organised_folder_artist_fallback(tmp_path):
    p = tmp_path / 'Agartha' / 'Unknown Year - Agartha Remixes' / '01 - Domino.flac'
    flac(p, **{**BASE, 'title': 'Domino', 'albumartist': '', 'artist': ''})
    song = read_song(p)
    assert song.artist == 'Agartha'


@needs_ffmpeg
def test_library_skips_internal_state_and_symlink(tmp_path):
    flac(tmp_path / 'Music' / 'Song.flac', **BASE)
    flac(tmp_path / '.oggcultist' / 'hidden.flac', **BASE)
    (tmp_path / 'linked.flac').symlink_to(tmp_path / 'Music' / 'Song.flac')
    songs, errors = scan_music_library(tmp_path)
    assert len(songs) == 1 and not errors


def test_playlist_create_save_load_remove_and_delete(tmp_path):
    path = tmp_path / 'state' / 'playlists.json'
    store = PlaylistStore(path)
    store.create('Favourites')
    assert store.add('Favourites', [Path('one.opus'), Path('two.opus'), Path('one.opus')]) == 2
    assert store.add('Favourites', [Path('one.opus')]) == 0
    saved = PlaylistStore(path)
    assert saved.playlists['Favourites'] == ['one.opus', 'two.opus']
    assert saved.remove('Favourites', [Path('one.opus')]) == 1
    assert PlaylistStore(path).playlists['Favourites'] == ['two.opus']
    saved.delete('Favourites')
    assert PlaylistStore(path).playlists == {}


def test_corrupt_playlist_file_is_not_overwritten(tmp_path):
    path = tmp_path / 'playlists.json'
    path.write_text('{ broken')
    with pytest.raises(ValueError, match='Could not read playlists'):
        PlaylistStore(path)
    assert path.read_text() == '{ broken'


def test_playlist_duplicate_names_are_refused(tmp_path):
    store = PlaylistStore(tmp_path / 'playlists.json')
    store.create('Late Night')
    with pytest.raises(ValueError):
        store.create('late night')
    assert store.playlists == {'Late Night': []}


class FakeProcess:
    def __init__(self):
        self.finished = False
        self.returncode = 0
        self.killed = False
    def poll(self):
        return self.returncode if self.finished else None
    def terminate(self):
        self.finished = True
    def wait(self, timeout=None):
        return self.returncode
    def kill(self):
        self.killed = True
        self.finished = True


def test_transport_play_pause_seek_resume_volume_stop_read_only(tmp_path):
    path = tmp_path / 'audio.opus'
    path.write_bytes(b'not parsed by fake player')
    before = path.read_bytes()
    calls = []
    now = [10.0]
    def spawn(cmd, **kwargs):
        calls.append((cmd, kwargs))
        return FakeProcess()
    tr = FFplayTransport(finder=lambda: 'C:/ffplay.exe', spawner=spawn, clock=lambda: now[0])
    song = Song(path, 'A', 'B', 'C', duration=60)
    tr.play(song)
    assert tr.playing and tr.current_position() == 0
    assert calls[-1][0][-2:] == ['-i', str(path)]
    assert calls[-1][1]['stdin'] is subprocess.DEVNULL
    now[0] = 15.0
    tr.pause()
    assert tr.paused and abs(tr.current_position() - 5) < .01
    tr.seek(23)
    tr.resume()
    assert '-ss' in calls[-1][0] and '23.000' in calls[-1][0]
    now[0] = 18.0
    tr.set_volume(51)
    assert calls[-1][0][calls[-1][0].index('-volume')+1] == '51'
    tr.stop()
    assert tr.song is None and not tr.playing
    assert path.read_bytes() == before


def test_transport_avoids_nonexistent_or_player_missing(tmp_path):
    p = tmp_path / 'absent.opus'
    tr = FFplayTransport(finder=lambda: None)
    with pytest.raises(PlayerError, match='FFplay is not installed'):
        tr.play(Song(p,'X','Y','Z'))
    tr.finder = lambda: 'ffplay'
    with pytest.raises(PlayerError, match='no longer exists'):
        tr.play(Song(p,'X','Y','Z'))


def test_transport_notifies_natural_end_only_once(tmp_path):
    p = tmp_path / 'a.opus'
    p.write_bytes(b'test')
    fake = FakeProcess()
    tr = FFplayTransport(finder=lambda: 'ffplay', spawner=lambda *args, **kwargs: fake)
    tr.play(Song(p,'A','B','C'))
    fake.finished = True
    assert tr.poll_end()
    assert not tr.poll_end()


def test_optional_ffplay_extraction_does_not_replace_existing_ffmpeg(tmp_path):
    import zipfile
    raw = io.BytesIO()
    with zipfile.ZipFile(raw, 'w') as zf:
        zf.writestr('ffmpeg-package/bin/ffplay.exe', b'player')
        zf.writestr('ffmpeg-package/bin/ffmpeg.exe', b'other')
    target = tmp_path / 'bin'
    target.mkdir()
    (target / 'ffmpeg.exe').write_bytes(b'important-existing')
    setup_ffmpeg.install_windows(raw.getvalue(), target, filenames=('ffplay.exe',))
    assert (target / 'ffplay.exe').read_bytes() == b'player'
    assert (target / 'ffmpeg.exe').read_bytes() == b'important-existing'


def test_fresh_windows_setup_gets_optional_ffplay_from_verified_archive(tmp_path):
    import hashlib
    import zipfile
    raw = io.BytesIO()
    with zipfile.ZipFile(raw, 'w') as zf:
        for executable in ('ffmpeg.exe', 'ffprobe.exe', 'ffplay.exe'):
            zf.writestr(f'ffmpeg-package/bin/{executable}', executable.encode())
    archive = raw.getvalue()
    def opener(request, timeout=90):
        if request.full_url.endswith('.sha256'):
            return io.BytesIO(hashlib.sha256(archive).hexdigest().encode())
        return io.BytesIO(archive)
    env = {'LOCALAPPDATA': str(tmp_path), 'PATH': ''}
    target = setup_ffmpeg.local_bin('win32', env)
    assert setup_ffmpeg.ensure_ffmpeg(platform='win32', env=env,
                  input_fn=lambda _: 'y', print_fn=lambda _msg: None,
                  check_fn=lambda _platform: (target/'ffmpeg.exe').exists() and (target/'ffprobe.exe').exists(),
                  opener=opener)
    assert (target/'ffplay.exe').read_bytes() == b'ffplay.exe'
