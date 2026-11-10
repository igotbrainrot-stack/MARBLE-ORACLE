"""v1.8.1: smooth playback engine (FFmpeg decodes → Oggcultist applies volume → one FFplay).

The real-process tests use FFmpeg/FFplay with SDL's dummy audio driver, which consumes
audio in real time, and capture exactly what is sent to FFplay to check it is smooth.
"""
from __future__ import annotations

import math
import shutil
import subprocess
import time
from array import array
from pathlib import Path

import pytest

from oggcultist.player import Song
from oggcultist.player.stream import RATE, StreamTransport, apply_gain, volume_gain

needs_tools = pytest.mark.skipif(not (shutil.which('ffmpeg') and shutil.which('ffplay')),
                                 reason='needs FFmpeg with FFplay')


def _samples(data: bytes) -> array:
    a = array('h')
    a.frombytes(data[:len(data) // 2 * 2])
    return a


def test_volume_curve_is_smooth_and_bounded():
    assert volume_gain(0) == 0 and volume_gain(100) == 1 and volume_gain(150) == 1
    assert volume_gain(50) == pytest.approx(0.25)
    values = [volume_gain(v) for v in range(101)]
    assert values == sorted(values)


def test_apply_gain_constant_ramp_and_silence():
    data = array('h', [10000, -10000] * 100).tobytes()
    assert apply_gain(data, 1.0, 1.0) == data
    assert set(_samples(apply_gain(data, 0.0, 0.0))) == {0}
    assert set(_samples(apply_gain(data, 0.5, 0.5))) == {5000, -5000}
    ramp = _samples(apply_gain(data, 1.0, 0.0))[0::2]
    assert ramp[0] == 10000 and ramp[-1] < 200
    assert all(a >= b for a, b in zip(ramp, ramp[1:]))       # a steady ramp, never a jump


@pytest.fixture
def sine(tmp_path, monkeypatch):
    monkeypatch.setenv('SDL_AUDIODRIVER', 'dummy')
    path = tmp_path / 'sine.flac'
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'sine=f=330:d=12', '-c:a', 'flac', str(path)],
                   check=True)
    return Song(path, 'sine', 'x', 'y', duration=12)


def _wait(condition, timeout=5.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if condition():
            return True
        time.sleep(0.01)
    return False


@needs_tools
def test_volume_moves_smoothly_while_dragged_with_no_restart(sine):
    tr = StreamTransport()
    out = bytearray()
    tr.tap = out.extend
    try:
        tr.play(sine)
        assert _wait(lambda: tr.current_position() > 0.3)
        sink = tr._session.sink
        for v in list(range(80, 9, -2)) + list(range(10, 101, 3)):      # a fast slider drag
            tr.set_volume(v)
            time.sleep(0.02)
        time.sleep(0.5)
        assert tr._session.sink is sink and sink.poll() is None          # the same FFplay throughout
    finally:
        tr.stop()
    left = _samples(bytes(out))[0::2]
    peak = max(abs(x) for x in left)
    natural = 2 * math.pi * 330 / RATE * peak                             # steepest step of a clean sine
    assert max(abs(b - a) for a, b in zip(left, left[1:])) <= natural * 1.15     # no clicks or jumps
    envelope = [max(abs(x) for x in left[i:i + 960]) for i in range(0, len(left) - 960, 960)]
    low = min(envelope[10:])
    assert low < peak * 0.05                                              # it really got quiet...
    assert envelope[-1] == pytest.approx(peak, rel=0.05)                  # ...and back to full


@needs_tools
def test_seek_pause_resume_and_fast_forward_positions(sine):
    tr = StreamTransport()
    out = bytearray()
    tr.tap = out.extend
    try:
        tr.play(sine)
        assert _wait(lambda: tr.current_position() > 0.2)
        sink = tr._session.sink
        tr.seek(6.0)
        assert tr.current_position() == pytest.approx(6.0, abs=0.05)
        time.sleep(0.6)
        assert 6.2 < tr.current_position() < 6.9
        assert tr._session.sink is sink                                    # seeking keeps the same FFplay
        tr.pause()
        paused_at = tr.position
        time.sleep(0.3)
        assert tr.current_position() == paused_at and not tr.playing
        tr.resume()
        assert _wait(lambda: tr.current_position() > paused_at + 0.1)
        assert tr.current_position() < paused_at + 0.6
        tr.set_speed(4.0)
        start = tr.current_position()
        time.sleep(1.0)
        moved = tr.current_position() - start
        assert 2.4 < moved < 4.8, moved                                    # about 4× (minus the 0.2 s buffer)
        tr.set_speed(1.0)
    finally:
        tr.stop()
    left = _samples(bytes(out))[0::2]
    natural = 2 * math.pi * 330 / RATE * max(abs(x) for x in left)
    assert max(abs(b - a) for a, b in zip(left, left[1:])) <= natural * 1.15   # seeks crossfade: no click


@needs_tools
def test_song_end_is_reported_once_and_next_song_joins_the_same_output(sine, tmp_path):
    short = tmp_path / 'short.flac'
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'sine=f=440:d=1', '-c:a', 'flac', str(short)],
                   check=True)
    song = Song(short, 'short', 'x', 'y', duration=1)
    tr = StreamTransport()
    try:
        tr.play(song)
        sink = tr._session.sink
        assert _wait(lambda: tr.poll_end(), 4)
        assert tr.last_returncode == 0 and not tr.poll_end()
        tr.play(song)                                                      # repeat one / next song
        assert tr._session.sink is sink                                     # joined on: no restart, no gap
        assert _wait(lambda: tr.current_position() > 0.3)
    finally:
        tr.stop()
    assert _wait(lambda: subprocess.run(['pgrep', '-f', str(short)], capture_output=True).returncode != 0, 2)
    assert _wait(lambda: tr._session is None, 1)


@needs_tools
def test_unplayable_file_reports_failure(tmp_path, monkeypatch):
    monkeypatch.setenv('SDL_AUDIODRIVER', 'dummy')
    bad = tmp_path / 'bad.opus'
    bad.write_bytes(b'not audio at all' * 100)
    tr = StreamTransport()
    try:
        tr.play(Song(bad, 'bad', 'x', 'y', duration=5))
        assert _wait(lambda: tr.poll_end(), 5)
        assert tr.last_returncode not in (0, None) and tr.last_error
    finally:
        tr.stop()
