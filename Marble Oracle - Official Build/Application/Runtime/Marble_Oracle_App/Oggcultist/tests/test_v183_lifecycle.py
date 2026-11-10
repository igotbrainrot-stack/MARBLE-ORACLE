"""v1.8.3: no FFplay/FFmpeg is left running after Oggcultist closes, however it closes."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest

from oggcultist.player import FFplayTransport, Song
from oggcultist.player.stream import StreamTransport
from oggcultist.services.tools import tie_to_app

needs_tools = pytest.mark.skipif(not (shutil.which('ffmpeg') and shutil.which('ffplay')), reason='needs FFmpeg/FFplay')
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def song(tmp_path, monkeypatch):
    monkeypatch.setenv('SDL_AUDIODRIVER', 'dummy')
    path = tmp_path / 'lifecycle-unique-name.flac'
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'sine=f=300:d=30', '-c:a', 'flac', str(path)],
                   check=True)
    return Song(path, 'x', 'a', 'b', duration=30)


def _helpers_for(token: str) -> list[str]:
    """FFplay/FFmpeg processes that are ours: their command line mentions ``token``."""
    found = []
    for entry in Path('/proc').iterdir():
        if not entry.name.isdigit():
            continue
        try:
            cmd = (entry / 'cmdline').read_bytes().replace(b'\0', b' ').decode('utf-8', 'replace')
        except OSError:
            continue
        if token in cmd and ('ffplay' in cmd or 'ffmpeg' in cmd):
            found.append(cmd)
    return found


def _sink_children(token: str) -> list[str]:
    """Our FFplay output processes read from a pipe; find them by the raw-input arguments."""
    return [c for c in _helpers_for('pipe:0') if 'ffplay' in c and token in c] if token else []


def _wait(condition, timeout=5.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if condition():
            return True
        time.sleep(0.05)
    return False


def test_ffplay_sink_is_told_to_exit_when_its_input_ends():
    calls = []
    tr = StreamTransport(spawner=lambda cmd, **kw: calls.append(cmd) or (_ for _ in ()).throw(OSError('x')))
    with pytest.raises(Exception):
        tr._start_session('ffplay')
    assert '-autoexit' in calls[0]


def test_tie_to_app_is_harmless_off_windows():
    marker = object()
    assert tie_to_app(marker, platform='linux') is marker


@needs_tools
@pytest.mark.skipif(not Path('/proc').is_dir(), reason='needs /proc')
def test_shutdown_while_playing_leaves_no_helper_processes(song):
    tr = StreamTransport()
    tr.play(song)
    assert _wait(lambda: tr.current_position() > 0.2)
    sink_pid = tr._session.sink.pid
    assert _helpers_for(str(song.path))                         # the decoder is running
    tr.shutdown()                                               # what closing the window does
    left = _helpers_for(str(song.path))
    assert not left, left
    assert not Path(f'/proc/{sink_pid}').exists() or 'zombie' in Path(f'/proc/{sink_pid}/status').read_text().lower()


@needs_tools
@pytest.mark.skipif(not Path('/proc').is_dir(), reason='needs /proc')
def test_closing_right_after_stop_still_ends_the_fading_ffplay(song):
    tr = StreamTransport()
    tr.play(song)
    assert _wait(lambda: tr.current_position() > 0.2)
    sink = tr._session.sink
    tr.stop()                                                   # fades out, would close a moment later...
    tr.shutdown()                                               # ...but the app closes now
    assert _wait(lambda: sink.poll() is not None, 2)


@needs_tools
@pytest.mark.skipif(not Path('/proc').is_dir(), reason='needs /proc')
def test_helpers_end_even_if_oggcultist_is_killed(song, tmp_path):
    """Oggcultist dies without any clean-up (crash / killed): FFplay and FFmpeg must not linger."""
    script = tmp_path / 'player.py'
    script.write_text(textwrap.dedent(f'''
        import os, sys, time
        sys.path.insert(0, {str(ROOT)!r})
        from pathlib import Path
        from oggcultist.player import Song
        from oggcultist.player.stream import StreamTransport
        tr = StreamTransport()
        tr.play(Song(Path({str(song.path)!r}), 'x', 'a', 'b', duration=30))
        time.sleep(1.5)
        print(tr._session.sink.pid, flush=True)
        os._exit(0)                      # no shutdown, no atexit: like a crash
    '''))
    out = subprocess.run([sys.executable, str(script)], capture_output=True, text=True, timeout=30,
                         env=dict(os.environ, SDL_AUDIODRIVER='dummy'))
    sink_pid = int(out.stdout.split()[0])

    def gone():
        status = Path(f'/proc/{sink_pid}/status')
        return not status.exists() or 'zombie' in status.read_text().lower()
    assert _wait(gone, 5), 'FFplay was left running after Oggcultist died: ' + out.stderr[-300:]
    assert _wait(lambda: not _helpers_for(str(song.path)), 5), _helpers_for(str(song.path))


@needs_tools
@pytest.mark.skipif(not Path('/proc').is_dir(), reason='needs /proc')
def test_fallback_transport_shutdown_stops_ffplay(song):
    tr = FFplayTransport()
    tr.play(song)
    assert _wait(lambda: tr._current and tr._current.audio_clock is not None)
    process = tr._current.process
    tr.shutdown()
    assert process.poll() is not None
