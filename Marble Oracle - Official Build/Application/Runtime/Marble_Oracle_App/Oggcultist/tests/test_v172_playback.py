"""v1.7.2: gap-free seeking, volume changes and track changes (FFplay handoff).

The fake processes below report an audio clock on a real pipe, exactly like
``ffplay -stats``, so the handoff logic is tested without timing guesses. The last
test uses the real FFplay when it is installed.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import time

import pytest

from oggcultist.player import FFplayTransport, Song


class ClockProcess:
    """A stand-in FFplay whose stderr is a real pipe we can write status lines into."""

    instances: list['ClockProcess'] = []

    def __init__(self, command, **kwargs):
        self.command = command
        read_fd, self._write_fd = os.pipe()
        self.stderr = os.fdopen(read_fd, 'rb')
        self.code = None
        self.terminated = False
        ClockProcess.instances.append(self)

    def say(self, text: str) -> None:
        os.write(self._write_fd, text.encode())

    def clock(self, seconds: float) -> None:
        self.say(f'  {seconds:6.2f} M-A:  0.000 fd=   0 aq=   14KB vq=    0KB sq=    0B f=0/0   \r')

    def finish(self, code: int = 0) -> None:
        if self.code is None:
            self.code = code
            os.close(self._write_fd)

    def poll(self):
        return self.code

    def terminate(self):
        self.terminated = True
        self.finish(-15)

    kill = terminate

    def wait(self, timeout=None):
        return self.code


def _wait(condition, timeout=2.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if condition():
            return True
        time.sleep(0.005)
    return False


@pytest.fixture
def songs(tmp_path):
    made = []
    for name in ('one', 'two'):
        path = tmp_path / f'{name}.opus'
        path.write_bytes(b'fake audio')
        made.append(Song(path, name, 'Artist', 'Album', duration=60))
    return made


@pytest.fixture
def transport():
    ClockProcess.instances = []
    tr = FFplayTransport(finder=lambda: 'ffplay', spawner=ClockProcess)
    yield tr
    tr.stop()
    for process in ClockProcess.instances:
        process.finish()


def test_command_asks_ffplay_for_its_clock_and_keeps_input_last(transport, songs):
    transport.play(songs[0], 5)
    command = ClockProcess.instances[0].command
    assert '-stats' in command and command[-2:] == ['-i', str(songs[0].path)]
    assert command[command.index('-ss') + 1] == '5.000'


def test_seek_keeps_old_ffplay_playing_until_new_one_is_heard(transport, songs):
    transport.play(songs[0])
    first = ClockProcess.instances[0]
    first.clock(3.0)
    assert _wait(lambda: transport._current.audio_clock == 3.0)

    transport.seek(40)
    second = ClockProcess.instances[1]
    assert transport._pending is not None
    assert not first.terminated, 'old FFplay must keep playing during start-up (no silent gap)'
    assert transport.playing
    assert transport.current_position() == pytest.approx(40)   # the seek bar shows the target at once

    second.clock(40.02)
    assert _wait(lambda: first.terminated)
    assert transport._current.process is second and transport._pending is None
    assert transport.poll_end() is False


def test_position_follows_ffplay_clock_so_pause_resume_does_not_drift(transport, songs):
    transport.play(songs[0])
    process = ClockProcess.instances[0]
    process.clock(0.02)                 # FFplay's first report is where playback began
    process.clock(12.5)
    assert _wait(lambda: transport._current.audio_clock == 12.5)
    position = transport.current_position()
    assert 12.5 <= position < 12.8
    transport.pause()
    assert process.terminated and transport.paused
    assert transport.position == pytest.approx(position, abs=0.05)
    transport.resume()
    command = ClockProcess.instances[-1].command
    assert float(command[command.index('-ss') + 1]) == pytest.approx(position, abs=0.05)


def test_rapid_track_changes_only_keep_the_latest_starting_ffplay(transport, songs):
    transport.play(songs[0])
    playing = ClockProcess.instances[0]
    playing.clock(1.0)
    assert _wait(lambda: transport._current.audio_clock == 1.0)
    for i in range(4):
        transport.play(songs[i % 2])
    starters = ClockProcess.instances[1:]
    assert all(p.terminated for p in starters[:-1]), 'superseded starting FFplays are stopped'
    assert not playing.terminated and not starters[-1].terminated
    assert transport.song is songs[1]
    starters[-1].clock(0.0)
    assert _wait(lambda: playing.terminated)


def test_track_ending_during_a_handoff_does_not_skip_an_extra_song(transport, songs):
    transport.play(songs[0])
    old = ClockProcess.instances[0]
    old.clock(59.8)
    assert _wait(lambda: transport._current.audio_clock is not None)
    transport.play(songs[1])          # user pressed Next just as the song ended
    old.finish(0)
    assert transport.poll_end() is False
    assert transport._current.process is ClockProcess.instances[1]
    assert transport.song is songs[1]


def test_new_ffplay_failing_before_sound_is_reported_once(transport, songs):
    transport.play(songs[0])
    old = ClockProcess.instances[0]
    old.clock(2.0)
    assert _wait(lambda: transport._current.audio_clock is not None)
    transport.play(songs[1])
    broken = ClockProcess.instances[1]
    broken.say('Invalid data found when processing input\n')
    broken.finish(1)
    assert _wait(lambda: old.terminated)
    assert transport.poll_end() is True
    assert transport.last_returncode == 1
    assert 'Invalid data' in transport.last_error
    assert transport.poll_end() is False


def test_stuck_ffplay_is_switched_to_after_timeout(transport, songs):
    now = [100.0]
    transport.clock = lambda: now[0]
    transport.play(songs[0])
    ClockProcess.instances[0].clock(1.0)
    assert _wait(lambda: transport._current.audio_clock is not None)
    transport.seek(30)
    now[0] += transport.HANDOFF_TIMEOUT + 0.1
    assert transport.poll_end() is False
    assert transport._current.process is ClockProcess.instances[1]
    assert ClockProcess.instances[0].terminated


def test_volume_change_starts_new_ffplay_ahead_by_measured_startup(transport, songs):
    transport.play(songs[0])
    ClockProcess.instances[0].clock(0.02)
    ClockProcess.instances[0].clock(20.0)
    assert _wait(lambda: transport._current.audio_clock == 20.0)
    transport.startup_latency = 0.3
    transport.set_volume(35)
    command = ClockProcess.instances[1].command
    assert command[command.index('-volume') + 1] == '35'
    assert float(command[command.index('-ss') + 1]) == pytest.approx(20.3, abs=0.1)


def test_file_with_nonzero_start_time_reports_position_from_zero(transport, songs):
    transport.play(songs[0], 10)
    process = ClockProcess.instances[0]
    process.clock(1410.0)               # stream timestamps start at 1400 s
    process.clock(1415.0)
    assert _wait(lambda: transport._current.audio_clock == 1415.0)
    assert 15.0 <= transport.current_position() < 15.3


def test_status_flood_never_blocks_ffplay(transport, songs):
    transport.play(songs[0])
    process = ClockProcess.instances[0]
    line = '   1.00 M-A:  0.000 fd=   0 aq=   14KB vq=    0KB sq=    0B f=0/0   \r'
    for _ in range(4000):     # ~280 KB: far more than a pipe buffer; would block if not drained
        process.say(line)
    assert transport._current.audio_clock == pytest.approx(1.0)


@pytest.mark.skipif(not shutil.which('ffplay') or not shutil.which('ffmpeg'), reason='needs FFmpeg with FFplay')
def test_real_ffplay_seek_and_track_change_have_no_silent_gap(tmp_path, monkeypatch):
    monkeypatch.setenv('SDL_AUDIODRIVER', 'dummy')
    made = []
    for name in ('a', 'b'):
        path = tmp_path / f'{name}.opus'
        subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'sine=f=440:d=20', '-c:a', 'libopus',
                        str(path)], check=True)
        made.append(Song(path, name, 'x', 'y', duration=20))
    tr = FFplayTransport(finder=lambda: shutil.which('ffplay'))
    try:
        tr.play(made[0])
        assert _wait(lambda: tr._current and tr._current.audio_clock is not None, 5)
        for action in (lambda: tr.seek(9), lambda: tr.set_volume(40), lambda: tr.play(made[1])):
            action()
            end = time.monotonic() + 1.0
            while time.monotonic() < end:
                sounding = [s for s in (tr._current, tr._pending) if s and s.alive and s.audio_clock is not None]
                assert sounding, 'a moment with no FFplay producing audio'
                time.sleep(0.005)
            assert tr._pending is None
        assert tr.song is made[1] and tr.current_position() < 2.5
    finally:
        tr.stop()


# ---------------------------------------------------------------- v1.7.5 fast-forward (speed)
def test_tempo_filter_chains_stages_of_two():
    assert FFplayTransport.tempo_filter(4) == 'atempo=2,atempo=2'
    assert FFplayTransport.tempo_filter(8) == 'atempo=2,atempo=2,atempo=2'
    assert FFplayTransport.tempo_filter(1.5) == 'atempo=1.5'


def test_fast_forward_position_runs_at_speed_and_returns_seamlessly(transport, songs):
    now = [50.0]
    transport.clock = lambda: now[0]
    transport.play(songs[0], 10)
    first = ClockProcess.instances[0]
    first.clock(10.0)
    assert _wait(lambda: transport._current.audio_clock == 10.0)
    transport.startup_latency = 0.2
    transport.set_speed(4.0)
    fast = ClockProcess.instances[1]
    assert '-af' in fast.command and fast.command[fast.command.index('-af') + 1] == 'atempo=2,atempo=2'
    start = float(fast.command[fast.command.index('-ss') + 1])
    assert start == pytest.approx(10.2, abs=0.05)          # ahead by start-up delay × old speed (1×)
    assert not first.terminated
    fast.clock(start)
    assert _wait(lambda: first.terminated)
    fast.clock(start + 1.0)                                # one real second later...
    assert _wait(lambda: transport._current.audio_clock == pytest.approx(start + 1.0))
    now[0] = transport._current.clock_at
    assert transport.current_position() == pytest.approx(start + 4.0, abs=0.05)   # ...four song seconds
    transport.startup_latency = 0.2         # (it was re-measured when the 4× process started)
    transport.set_speed(1.0)
    normal = ClockProcess.instances[2]
    assert '-af' not in normal.command
    resumed = float(normal.command[normal.command.index('-ss') + 1])
    assert resumed == pytest.approx(start + 4.0 + 0.2 * 4.0, abs=0.1)   # old one runs at 4× meanwhile
    assert transport.speed == 1.0


def test_pause_and_stop_return_to_normal_speed(transport, songs):
    transport.play(songs[0])
    ClockProcess.instances[0].clock(0.0)
    assert _wait(lambda: transport._current.audio_clock is not None)
    transport.set_speed(4.0)
    transport.pause()
    assert transport.speed == 1.0
    transport.resume()
    assert '-af' not in ClockProcess.instances[-1].command


@pytest.mark.skipif(not shutil.which('ffplay') or not shutil.which('ffmpeg'), reason='needs FFmpeg with FFplay')
def test_real_ffplay_fast_forward_moves_four_times_faster_without_gap(tmp_path, monkeypatch):
    monkeypatch.setenv('SDL_AUDIODRIVER', 'dummy')
    path = tmp_path / 'long.opus'
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'sine=f=330:d=60', '-c:a', 'libopus', str(path)],
                   check=True)
    tr = FFplayTransport(finder=lambda: shutil.which('ffplay'))
    try:
        tr.play(Song(path, 'long', 'x', 'y', duration=60))
        assert _wait(lambda: tr._current and tr._current.audio_clock is not None, 5)
        tr.set_speed(4.0)
        assert _wait(lambda: tr._pending is None and tr._current.speed == 4.0, 5)
        start, t0 = tr.current_position(), time.monotonic()
        end = t0 + 1.5
        while time.monotonic() < end:
            assert tr._current.alive
            time.sleep(0.01)
        moved = tr.current_position() - start
        assert 4.0 * 1.5 * 0.8 < moved < 4.0 * 1.5 * 1.25, moved
        tr.set_speed(1.0)
        end = time.monotonic() + 1.0
        while time.monotonic() < end:
            assert [s for s in (tr._current, tr._pending) if s and s.alive and s.audio_clock is not None]
            time.sleep(0.005)
        assert tr._current.speed == 1.0
    finally:
        tr.stop()
