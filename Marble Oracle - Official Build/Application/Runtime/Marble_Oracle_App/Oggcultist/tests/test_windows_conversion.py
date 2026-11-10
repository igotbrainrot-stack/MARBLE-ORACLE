"""Windows release regression: a read-only fsync causes EBADF on Windows.

The Oggcultist v1.5.2 user report showed 174 failures with this exact error.
The staging file must be opened with write access before os.fsync, and the
program must still never overwrite an existing destination.
"""
import errno
import os
import shutil
import subprocess
import threading
from pathlib import Path

import pytest

import oggcultist.core as core
from oggcultist.core import publish_no_overwrite, process, scan
from test_audit import flac, BASE


@pytest.mark.skipif(os.name == 'nt', reason='Windows tests the native CRT directly; simulated check uses POSIX fcntl')
def test_windows_style_fsync_rejects_readonly_staging_descriptor(tmp_path, monkeypatch):
    import fcntl

    stage = tmp_path / 'staged.opus'
    dest = tmp_path / 'final.opus'
    stage.write_bytes(b'good file')
    sync = os.fsync
    checked = []

    def windows_style_fsync(fd):
        mode = fcntl.fcntl(fd, fcntl.F_GETFL) & os.O_ACCMODE
        if mode == os.O_RDONLY:
            raise OSError(errno.EBADF, 'Bad file descriptor (simulated Windows _commit on read-only handle)')
        checked.append(fd)
        sync(fd)

    monkeypatch.setattr(core.os, 'fsync', windows_style_fsync)
    publish_no_overwrite(stage, dest)
    assert checked, 'staged file must be synchronized using a writable descriptor'
    assert dest.read_bytes() == b'good file'
    assert not stage.exists()


@pytest.mark.skipif(not (shutil.which('ffmpeg') and shutil.which('ffprobe')),
                    reason='FFmpeg and FFprobe required')
@pytest.mark.parametrize('source_type', ['flac', 'mp3'])
def test_actual_conversion_with_windows_style_readonly_fsync_rejection(tmp_path, monkeypatch, source_type):
    """End-to-end: simulate _commit failing on read-only fd, verify tags/output."""
    if os.name != 'nt':
        import fcntl
        sync = os.fsync
        def windows_style_fsync(fd):
            if (fcntl.fcntl(fd, fcntl.F_GETFL) & os.O_ACCMODE) == os.O_RDONLY:
                raise OSError(errno.EBADF, 'Bad file descriptor (Windows CRT simulation)')
            return sync(fd)
        monkeypatch.setattr(core.os, 'fsync', windows_style_fsync)

    if source_type == 'flac':
        source = flac(tmp_path / 'music' / 'Album' / '01.flac', title='Track', tracknumber='1', **BASE)
    else:
        from mutagen.easyid3 import EasyID3
        source = tmp_path / 'music' / 'Album' / '01.mp3'
        source.parent.mkdir(parents=True)
        subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-f', 'lavfi',
                        '-i', 'sine=frequency=440:duration=1', '-c:a', 'libmp3lame', '-y',
                        str(source)], check=True)
        tags = EasyID3(source)
        tags.update({'title': 'Track', 'album': 'Album', 'albumartist': 'Band',
                     'artist': 'Band', 'date': '1975', 'originaldate': '1975',
                     'tracknumber': '1'})
        tags.save()
    before = source.read_bytes()
    tracks, problems = scan(tmp_path / 'music')
    assert not problems
    output = tmp_path / 'opus'
    summary = process(tracks, output, threading.Event())
    assert summary['converted'] == 1, summary
    assert summary['errors'] == 0
    from mutagen.oggopus import OggOpus
    trackout = next(output.rglob('*.opus'))
    tags = OggOpus(trackout)
    assert tags['albumartist'] == ['Band']
    assert tags['tracknumber'] == ['1']
    assert source.read_bytes() == before
    assert not list(output.rglob('.oggcultist-*.opus'))


def test_atomic_publication_keeps_existing_file(tmp_path):
    staged, target = tmp_path / 'stage.opus', tmp_path / 'done.opus'
    staged.write_bytes(b'new')
    target.write_bytes(b'old')
    with pytest.raises((RuntimeError, FileExistsError)):
        publish_no_overwrite(staged, target)
    assert staged.read_bytes() == b'new'
    assert target.read_bytes() == b'old'
