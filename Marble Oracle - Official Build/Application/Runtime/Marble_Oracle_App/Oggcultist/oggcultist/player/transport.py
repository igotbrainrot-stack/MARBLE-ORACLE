"""FFplay-backed audio transport: play, pause, resume, seek, volume, stop.

FFplay has no control channel, so seek, volume and track changes start a new FFplay
process. To avoid a silent gap while it opens the file and the audio device, the old
process keeps playing until the new one reports that its audio clock is running
(``-stats`` prints the clock about every 30 ms on stderr); only then is the old one
stopped. The same clock gives the real playback position, so pausing and resuming
no longer drift by the start-up delay. Pause is immediate. No extra Python audio
dependency is required.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import threading
import time

from .. import paths
from ..services.tools import tie_to_app
from .library import Song


class PlayerError(RuntimeError):
    pass



def find_ffplay() -> str | None:
    """FFplay from the configured PATH (bundled tools, private copy, system)."""
    exe = shutil.which('ffplay')
    if exe:
        return exe
    local = paths.private_tools_dir() / ('ffplay.exe' if sys.platform == 'win32' else 'ffplay')
    return str(local) if local.is_file() else None


class _Stream:
    """One FFplay child and what it reports about its own audio clock."""

    def __init__(self, process, song: Song, offset: float, spawned: float, speed: float = 1.0):
        self.process = process
        self.song = song
        self.offset = offset
        self.speed = speed                      # 1.0 normally; 4 or 8 while fast-forwarding
        self.spawned = spawned
        self.audio_clock: float | None = None   # seconds into the file, from FFplay
        self.clock_at = 0.0                     # our clock when audio_clock was read
        self.base = 0.0                         # file start-time offset, if any
        self.ready = threading.Event()
        self.errors: list[str] = []

    @property
    def alive(self) -> bool:
        return self.process.poll() is None

    @property
    def reports_clock(self) -> bool:
        return getattr(self.process, 'stderr', None) is not None


def _stop_process(process, wait: bool) -> None:
    if process is None or process.poll() is not None:
        return
    try:
        process.terminate()
    except OSError:
        return  # Child exited between poll() and terminate().
    if not wait:
        threading.Thread(target=_reap, args=(process,), daemon=True).start()
        return
    _reap(process)


def _reap(process) -> None:
    try:
        process.wait(timeout=2.5)
    except subprocess.TimeoutExpired:
        process.kill()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            pass


class FFplayTransport:
    """Play/pause/seek using managed FFplay child processes (no extra Python wheels)."""

    HANDOFF_TIMEOUT = 2.5   # seconds to wait for a new FFplay before switching anyway

    def __init__(self, finder=find_ffplay, spawner=subprocess.Popen, clock=time.monotonic):
        self.finder = finder
        self.spawner = spawner
        self.clock = clock
        self._lock = threading.RLock()
        self._current: _Stream | None = None
        self._pending: _Stream | None = None    # new FFplay warming up during a handoff
        self.song: Song | None = None
        self.position = 0.0
        self.started_at = 0.0
        self.paused = False
        self.volume = 80
        self.last_returncode: int | None = None
        self.startup_latency = 0.25             # measured; used to keep volume changes seamless
        self.last_error = ''
        self.speed = 1.0                        # playback speed (fast-forward while > 1)

    # ------------------------------------------------------------------ state
    @property
    def process(self):
        stream = self._current
        return stream.process if stream else None

    @property
    def playing(self) -> bool:
        with self._lock:
            return bool(self._current and self._current.alive) or bool(self._pending and self._pending.alive)

    def current_position(self) -> float:
        with self._lock:
            if self._pending is not None:
                position = self._pending.offset          # a seek is starting: show where it goes
            elif self.paused or self._current is None or not self._current.alive:
                position = self.position
            elif self._current.audio_clock is not None:
                # FFplay's clock runs in real time from the start point, even when the audio is
                # sped up, so song time = start + clock progress × speed.
                stream = self._current
                clock = stream.audio_clock - stream.base + max(0., self.clock() - stream.clock_at)
                position = stream.offset + (clock - stream.offset) * stream.speed
            else:
                speed = self._current.speed
                position = self.position + max(0., self.clock() - self.started_at) * speed
            song = self.song
        if song and song.duration > 0:
            return max(0., min(position, song.duration))
        return max(0., position)

    # ------------------------------------------------------------------ processes
    @staticmethod
    def tempo_filter(speed: float) -> str:
        """An atempo chain for ``speed``: stages of at most 2× work with every FFmpeg version."""
        stages = []
        while speed > 2.0 + 1e-9:
            stages.append('atempo=2')
            speed /= 2.0
        stages.append(f'atempo={speed:g}')
        return ','.join(stages)

    def _command(self, executable: str, song: Song, offset: float, speed: float = 1.0) -> list[str]:
        command = [executable, '-nodisp', '-autoexit', '-vn', '-hide_banner', '-loglevel', 'error', '-stats',
                   '-volume', str(max(0, min(100, self.volume)))]
        if speed != 1.0:
            command += ['-af', self.tempo_filter(speed)]
        if offset:
            command += ['-ss', f'{offset:.3f}']
        return command + ['-i', str(song.path)]

    def _spawn(self, song: Song, offset: float, speed: float = 1.0) -> _Stream:
        executable = self.finder()
        if not executable:
            raise PlayerError('FFplay is not installed. Install the optional FFplay playback component.')
        if not song.path.is_file():
            raise PlayerError(f'Audio file no longer exists: {song.path}')
        flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0) if sys.platform == 'win32' else 0
        try:
            process = tie_to_app(self.spawner(self._command(executable, song, offset, speed), stdin=subprocess.DEVNULL,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, creationflags=flags))
        except OSError as exc:
            raise PlayerError(f'Could not start FFplay: {exc}') from exc
        stream = _Stream(process, song, offset, self.clock(), speed)
        if stream.reports_clock:
            threading.Thread(target=self._read_clock, args=(stream,), daemon=True,
                             name='ffplay-clock').start()
        else:
            stream.ready.set()      # test doubles and unusual spawners: no clock, switch at once
        return stream

    def _read_clock(self, stream: _Stream) -> None:
        """Drain FFplay's stderr (it must never fill up) and track its audio clock."""
        pipe = stream.process.stderr
        read = getattr(pipe, 'read1', pipe.read)
        pending = b''
        try:
            while True:
                chunk = read(4096)
                if not chunk:
                    break
                pending += chunk
                *lines, pending = pending.replace(b'\r', b'\n').split(b'\n')
                for raw in lines:
                    self._clock_line(stream, raw.decode('utf-8', 'replace').strip())
        except (OSError, ValueError):
            pass
        finally:
            try:
                pipe.close()
            except OSError:
                pass
        # The process ended before ever reporting audio (bad file, no audio device...):
        # switch to it anyway so the normal end-of-track handling reports what happened.
        if not stream.ready.is_set():
            stream.ready.set()
            self._promote(stream)

    def _clock_line(self, stream: _Stream, line: str) -> None:
        if not line:
            return
        first = line.split()[0]
        try:
            value = float(first)
        except ValueError:
            if 'M-A' not in line and 'aq=' not in line:
                stream.errors = (stream.errors + [line])[-3:]
            return
        if value != value:      # nan: FFplay has not started its clock yet
            return
        now = self.clock()
        with self._lock:
            if stream.audio_clock is None and abs(value - stream.offset) > 2.0:
                stream.base = value - stream.offset      # file timestamps don't start at zero
            stream.audio_clock = value
            stream.clock_at = now
        if not stream.ready.is_set():
            stream.ready.set()
            self.startup_latency = 0.7 * self.startup_latency + 0.3 * min(2.0, max(0.02, now - stream.spawned))
            self._promote(stream)

    def _promote(self, stream: _Stream) -> None:
        """Make a warmed-up pending stream current and stop the old one."""
        with self._lock:
            if stream is not self._pending:
                return
            old, self._current, self._pending = self._current, stream, None
            self.position, self.started_at = stream.offset, stream.spawned
        if old is not None:
            _stop_process(old.process, wait=False)

    def _start(self, song: Song, offset: float, speed: float = 1.0) -> None:
        if song.duration:
            offset = min(max(0., offset), max(0., song.duration - 0.1))
        else:
            offset = max(0., offset)
        with self._lock:
            handoff = bool(self._current and self._current.alive and self._current.reports_clock
                           and not self.paused)
            stale_pending, self._pending = self._pending, None
        _stop_process(stale_pending.process if stale_pending else None, wait=False)
        if not handoff:
            with self._lock:
                old, self._current = self._current, None
            _stop_process(old.process if old else None, wait=True)
        try:
            stream = self._spawn(song, offset, speed)
        except PlayerError:
            if not handoff:
                self.song = None
            raise
        old = None
        with self._lock:
            self.song = song
            self.paused = False
            self.speed = speed
            self.last_returncode = None
            if handoff and not stream.ready.is_set():
                self._pending = stream          # the old FFplay keeps playing until this one is heard
            else:
                old = self._current if handoff else None
                self._current = stream
                self.position, self.started_at = offset, stream.spawned
        if old is not None:
            _stop_process(old.process, wait=False)

    def _stop_all(self) -> None:
        with self._lock:
            streams, self._current, self._pending = [self._pending, self._current], None, None
        for stream in streams:
            if stream is not None:
                _stop_process(stream.process, wait=True)

    # ------------------------------------------------------------------ controls
    def stop(self) -> None:
        self._stop_all()
        self.speed = 1.0
        self.song = None
        self.position = 0.
        self.paused = False
        self.last_returncode = None

    def play(self, song: Song, offset: float = 0., speed: float = 1.0) -> None:
        self._start(song, offset, speed)

    def set_speed(self, speed: float) -> None:
        """Change playback speed (fast-forward) without a gap, continuing from the current point."""
        if not self.playing or self.song is None or speed == self.speed:
            return
        # The old process keeps playing at its own speed while the new one starts up.
        ahead = self.startup_latency * self.speed if (self._current and self._current.reports_clock) else 0.
        self.play(self.song, self.current_position() + ahead, speed)

    def pause(self) -> None:
        if not self.playing:
            return
        position = self.current_position()
        self._stop_all()
        self.position = position
        self.paused = True
        self.speed = 1.0

    def resume(self) -> None:
        if self.song is not None and self.paused:
            self.play(self.song, self.position)

    def seek(self, seconds: float) -> None:
        if not self.song:
            return
        if self.paused:
            self.position = max(0., min(seconds, self.song.duration)) if self.song.duration else max(0., seconds)
        else:
            self.play(self.song, seconds, self.speed)

    def set_volume(self, value: int) -> None:
        self.volume = max(0, min(100, int(value)))
        # FFplay applies -volume at start-up. Start the new process slightly ahead, by the
        # measured start-up delay, so it picks up where the old one will be when it takes over.
        if self.playing and self.song is not None:
            ahead = self.startup_latency * self.speed if (self._current and self._current.reports_clock) else 0.
            self.play(self.song, self.current_position() + ahead, self.speed)

    def poll_end(self) -> bool:
        """One-shot notification that the track ended, irrespective of exit status."""
        with self._lock:
            pending = self._pending
            if pending is not None and self.clock() - pending.spawned > self.HANDOFF_TIMEOUT:
                pending.ready.set()
                stuck = True
            else:
                stuck = False
        if stuck:
            self._promote(pending)
        with self._lock:
            current = self._current
            if self._pending is not None:
                if current is not None and not current.alive:
                    # the old track ran out while the next one warms up: not an end of queue
                    pending = self._pending
                    pending.ready.set()
                else:
                    return False
            else:
                pending = None
        if pending is not None:
            self._promote(pending)
            return False
        if current is not None and not current.alive:
            with self._lock:
                self.last_returncode = current.process.poll()
                self.last_error = '; '.join(current.errors)
                self._current = None
                self.position = 0.
                self.song = None
                self.paused = False
                self.speed = 1.0
            return True
        return False

    def shutdown(self) -> None:
        """Closing Oggcultist: stop every FFplay now, including ones still being stopped."""
        self._stop_all()
