"""Smooth playback engine: FFmpeg decodes, Oggcultist sets the volume, one FFplay plays.

FFplay can only set its volume when it starts, so changing volume by restarting it is
never perfectly smooth. Here the audio goes through Oggcultist instead:

    FFmpeg (decode song → 48 kHz stereo PCM) → Oggcultist (volume, ramped) → FFplay (sound out)

- **Volume** is applied to the samples as they pass through, ramping between levels, so
  dragging the slider changes the loudness continuously with no restarts. It is heard
  about ``AHEAD`` seconds later (0.2 s), the small buffer kept ahead of the speakers.
- **Seek, track change and fast-forward** start a new FFmpeg decoder (about 40 ms);
  the one FFplay keeps playing, so there is no device restart and no gap. The audio
  already buffered (≤ 0.2 s) finishes first.
- **Back-to-back songs** are joined in the same stream, so repeat-one and the next song
  follow without a gap.
- **Pause** stops both processes at once; resume starts again at the exact position.
- The **position** comes from FFplay's own clock (``-stats``) mapped back through the
  segments written, so it matches what is heard.

``FFplayTransport`` (one FFplay per song) remains as the fallback when FFmpeg is missing.
"""
from __future__ import annotations

import struct
import subprocess
import sys
import threading
import time
from array import array

from ..services.tools import find_tool, no_window_kwargs, tie_to_app
from .library import Song
from .transport import FFplayTransport, PlayerError, find_ffplay

RATE = 48000
CHANNELS = 2
FRAME_BYTES = 2 * CHANNELS            # s16le stereo
CHUNK_FRAMES = 960                    # 20 ms per write
AHEAD = 0.20                          # seconds kept buffered ahead of the speakers
GAIN_STEP = 0.12                      # largest gain change per 20 ms chunk (full sweep ≈ 170 ms)
END_EARLY = 0.15                      # report a song's end this long before it is heard, so the
                                      # next one can be joined on without a gap


def find_ffmpeg() -> str | None:
    return find_tool('ffmpeg')


def volume_gain(volume: int | float) -> float:
    """Slider 0–100 → amplitude. Squared, so equal slider steps sound like equal steps."""
    v = max(0.0, min(100.0, float(volume))) / 100.0
    return v * v


def apply_gain(data: bytes, start: float, end: float) -> bytes:
    """Scale s16le samples, ramping linearly from ``start`` to ``end`` across the chunk."""
    if start == end == 1.0:
        return data
    if start == end == 0.0:
        return bytes(len(data))
    samples = array('h')
    samples.frombytes(data[:len(data) - len(data) % 2])
    if sys.byteorder == 'big':
        samples.byteswap()
    frames = max(1, len(samples) // CHANNELS)
    if start == end:
        out = array('h', [int(x * start) for x in samples])
    else:
        step = (end - start) / frames
        out = array('h', [int(x * (start + step * (i // CHANNELS))) for i, x in enumerate(samples)])
    if sys.byteorder == 'big':
        out.byteswap()
    return out.tobytes()


_LAYOUT_OPTION: dict[str, list[str]] = {}


def channel_option(ffplay: str) -> list[str]:
    """How this FFplay is told the input is stereo: '-ch_layout stereo' (FFmpeg 5.1+) or '-ac 2'."""
    if ffplay not in _LAYOUT_OPTION:
        option = ['-ch_layout', 'stereo']
        try:
            result = subprocess.run([ffplay, '-hide_banner', '-h', 'demuxer=s16le'], capture_output=True,
                                    text=True, timeout=10, stdin=subprocess.DEVNULL, **no_window_kwargs())
            text = result.stdout + result.stderr
            if 'ch_layout' not in text and 'channels' in text:
                option = ['-ac', str(CHANNELS)]
        except (OSError, subprocess.SubprocessError):
            pass
        _LAYOUT_OPTION[ffplay] = option
    return _LAYOUT_OPTION[ffplay]


def wav_header() -> bytes:
    """A streaming WAV header (unknown length): no version-specific raw-audio options needed."""
    return (b'RIFF' + struct.pack('<I', 0xFFFFFFFF) + b'WAVE' + b'fmt ' +
            struct.pack('<IHHIIHH', 16, 1, CHANNELS, RATE, RATE * FRAME_BYTES, FRAME_BYTES, 16) +
            b'data' + struct.pack('<I', 0xFFFFFFFF))


class _Segment:
    """A stretch of the output stream that came from one song, from one start point."""

    def __init__(self, start_frame: int, song: Song, offset: float, speed: float):
        self.start_frame = start_frame
        self.song = song
        self.offset = offset
        self.speed = speed
        self.end_frame: int | None = None      # set when the decoder reached the end
        self.returncode: int | None = None
        self.error = ''
        self.reported = False

    def time_at(self, frame: int) -> float:
        return self.offset + (frame - self.start_frame) / RATE * self.speed


class _Session:
    """One FFplay output process and the pump thread feeding it."""

    def __init__(self):
        self.sink = None
        self.written = 0                        # frames written to the sink
        self.clock: float | None = None         # FFplay's clock: seconds of the stream played
        self.clock_at = 0.0
        self.segments: list[_Segment] = []
        self.decoder = None
        self.switch = None                      # (decoder, segment) waiting to take over
        self.stopped = False
        self.sink_errors: list[str] = []
        self.gain = None                        # gain applied to the last chunk
        self.held = b''                         # last 20 ms, kept back so a switch can fade it out
        self.fade_in = False                    # next chunk starts a new stretch: fade it in
        self.pausing = False                    # pause asked: fade out and stop feeding
        self.pause_frame: int | None = None     # where the faded-out stream ends
        self.faded = threading.Event()


class StreamTransport:
    """Same interface as FFplayTransport; volume changes are live and smooth."""

    live_volume = True

    def __init__(self, finder=find_ffplay, ffmpeg_finder=find_ffmpeg, spawner=subprocess.Popen,
                 clock=time.monotonic):
        self.finder = finder
        self.ffmpeg_finder = ffmpeg_finder
        self.spawner = spawner
        self.clock = clock
        self._lock = threading.RLock()
        self._session: _Session | None = None
        self.song: Song | None = None
        self.position = 0.0
        self.paused = False
        self.volume = 80
        self.speed = 1.0
        self.last_returncode: int | None = None
        self.last_error = ''
        self.startup_latency = 0.0
        self.tap = None                         # tests: called with every chunk sent to FFplay
        self._closing: list[_Session] = []      # faded-out sessions still finishing their buffer

    # ------------------------------------------------------------------ processes
    def _spawn_sink(self, executable: str):
        # -autoexit: FFplay ends as soon as its input pipe closes, so it can never be left
        # running in the background, even if Oggcultist itself crashes.
        command = [executable, '-nodisp', '-autoexit', '-hide_banner', '-loglevel', 'error', '-stats',
                   '-fflags', 'nobuffer', '-probesize', '32', '-analyzeduration', '0', '-volume', '100',
                   '-f', 's16le', '-ar', str(RATE), *channel_option(executable), '-i', 'pipe:0']
        return tie_to_app(self.spawner(command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                       stderr=subprocess.PIPE, **no_window_kwargs()))

    def _spawn_decoder(self, executable: str, song: Song, offset: float, speed: float):
        command = [executable, '-nostdin', '-hide_banner', '-v', 'error']
        if offset:
            command += ['-ss', f'{offset:.3f}']
        command += ['-i', str(song.path), '-map', '0:a:0', '-vn']
        if speed != 1.0:
            command += ['-af', FFplayTransport.tempo_filter(speed)]
        command += ['-f', 's16le', '-ar', str(RATE), '-ac', str(CHANNELS), '-']
        return tie_to_app(self.spawner(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, **no_window_kwargs()))

    def _start_session(self, ffplay: str) -> _Session:
        session = _Session()
        try:
            session.sink = self._spawn_sink(ffplay)
        except OSError as exc:
            raise PlayerError(f'Could not start FFplay: {exc}') from exc
        threading.Thread(target=self._read_sink, args=(session,), daemon=True, name='ffplay-out').start()
        threading.Thread(target=self._pump, args=(session,), daemon=True, name='audio-pump').start()
        return session

    def _end_session(self, session: _Session | None) -> None:
        if session is None:
            return
        with self._lock:
            session.stopped = True
            processes = [session.decoder, session.sink] + ([session.switch[0]] if session.switch else [])
            session.switch = None
        for process in processes:
            if process is not None and process.poll() is None:
                try:
                    process.kill()
                except OSError:
                    pass
        for process in processes:
            if process is not None:
                try:
                    process.wait(timeout=3)
                except (subprocess.TimeoutExpired, OSError):
                    pass

    # ------------------------------------------------------------------ threads
    def _read_sink(self, session: _Session) -> None:
        pipe = session.sink.stderr
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
                    line = raw.decode('utf-8', 'replace').strip()
                    if not line:
                        continue
                    try:
                        value = float(line.split()[0])
                    except ValueError:
                        session.sink_errors = (session.sink_errors + [line])[-3:]
                        continue
                    if value == value:
                        with self._lock:
                            session.clock, session.clock_at = value, self.clock()
        except (OSError, ValueError):
            pass

    def _played(self, session: _Session) -> int:
        """Frames heard so far (FFplay's clock, extrapolated, never past what was written)."""
        if session.clock is None:
            return 0
        frames = (session.clock + max(0.0, self.clock() - session.clock_at)) * RATE
        return int(min(session.written, max(0.0, frames)))

    def _write(self, session: _Session, data: bytes) -> bool:
        if not data:
            return True
        try:
            session.sink.stdin.write(data)
            session.sink.stdin.flush()
        except (OSError, ValueError):
            with self._lock:
                if not session.stopped:
                    session.sink_errors = (session.sink_errors + ['audio output stopped'])[-3:]
            return False
        if self.tap is not None:
            self.tap(data)
        with self._lock:
            session.written += len(data) // FRAME_BYTES
        return True

    def _pump(self, session: _Session) -> None:
        """Move audio from the current decoder to FFplay, applying volume, ≤ AHEAD seconds early.

        The last chunk is held back one step, so that when the decoder is switched (seek, new
        song, speed) the old audio can fade out over 20 ms while the new fades in: no click.
        """
        chunk_bytes = CHUNK_FRAMES * FRAME_BYTES
        while True:
            fade_out = b''
            with self._lock:
                if session.stopped:
                    return
                if session.pausing:
                    held, session.held = session.held, b''
            if session.pausing:
                self._write(session, apply_gain(held, 1.0, 0.0))     # end on silence: no click
                with self._lock:
                    session.pause_frame = session.written
                session.faded.set()
                return
            with self._lock:
                if session.switch is not None:
                    session.decoder, segment = session.switch
                    session.switch = None
                    fade_out, session.held = session.held, b''
                    session.fade_in = True
                    pending_segment = segment
                else:
                    pending_segment = None
            if fade_out:
                if not self._write(session, apply_gain(fade_out, 1.0, 0.0)):
                    return
            if pending_segment is not None:
                with self._lock:
                    pending_segment.start_frame = session.written
                    session.segments.append(pending_segment)
                    del session.segments[:-8]
            with self._lock:
                decoder = session.decoder
                segment = session.segments[-1] if session.segments else None
                ahead = session.written - self._played(session)
            if decoder is None or segment is None:
                time.sleep(0.005)
                continue
            if ahead > AHEAD * RATE:
                time.sleep(0.004)
                continue
            try:
                data = decoder.stdout.read(chunk_bytes)
            except (OSError, ValueError):
                data = b''
            with self._lock:
                if session.stopped:
                    return
                if session.decoder is not decoder or session.switch is not None:
                    continue                    # replaced while reading: drop this chunk
                if not data:
                    held, session.held = session.held, b''
                else:
                    target = volume_gain(self.volume)
                    start = target if session.gain is None else session.gain
                    end = start + max(-GAIN_STEP, min(GAIN_STEP, target - start))
                    session.gain = end
                    fade_in, session.fade_in = session.fade_in, False
            if not data:
                # the song (or this stretch of it) is finished: its real ending is written as is
                if not self._write(session, held):
                    return
                try:
                    code = decoder.wait(timeout=3)
                    errors = decoder.stderr.read().decode('utf-8', 'replace').strip() if decoder.stderr else ''
                except (subprocess.TimeoutExpired, OSError, ValueError):
                    code, errors = -1, ''
                with self._lock:
                    if session.decoder is decoder:
                        segment.returncode = code
                        segment.error = errors.splitlines()[-1] if errors else ''
                        segment.end_frame = session.written
                        session.decoder = None
                continue
            data = data[:len(data) - len(data) % FRAME_BYTES]
            out = apply_gain(data, start, end)
            if fade_in:
                out = apply_gain(out, 0.0, 1.0)
            with self._lock:
                held, session.held = session.held, out
            if not self._write(session, held):
                return

    # ------------------------------------------------------------------ state
    @staticmethod
    def playing_session(session: _Session) -> bool:
        return (not session.stopped and session.sink is not None and session.sink.poll() is None
                and session.decoder is not None or (session.segments and session.segments[-1].end_frame is None))

    @property
    def playing(self) -> bool:
        with self._lock:
            session = self._session
            return (session is not None and not session.stopped and not self.paused and self.song is not None
                    and session.sink is not None and session.sink.poll() is None)

    def current_position(self) -> float:
        with self._lock:
            session, song = self._session, self.song
            if self.paused or session is None or song is None:
                position = self.position
            elif session.switch is not None:
                position = session.switch[1].offset     # a seek or new song is starting: show its start
            elif not session.segments:
                position = self.position
            else:
                played = self._played(session)
                latest = session.segments[-1]
                if played < latest.start_frame:
                    position = latest.offset             # still hearing the previous stretch
                else:
                    position = latest.time_at(played)
        if song and song.duration > 0:
            return max(0.0, min(position, song.duration))
        return max(0.0, position)

    # ------------------------------------------------------------------ controls
    def play(self, song: Song, offset: float = 0.0, speed: float = 1.0) -> None:
        ffplay, ffmpeg = self.finder(), self.ffmpeg_finder()
        if not ffplay:
            raise PlayerError('FFplay is not installed. Install the optional FFplay playback component.')
        if not ffmpeg:
            raise PlayerError('FFmpeg is not installed.')
        if not song.path.is_file():
            raise PlayerError(f'Audio file no longer exists: {song.path}')
        if song.duration:
            offset = min(max(0.0, offset), max(0.0, song.duration - 0.1))
        else:
            offset = max(0.0, offset)
        with self._lock:
            session = self._session
            alive = (session is not None and not session.stopped and session.sink is not None
                     and session.sink.poll() is None)
        if not alive:
            self._end_session(session)
            session = self._start_session(ffplay)
        try:
            decoder = self._spawn_decoder(ffmpeg, song, offset, speed)
        except OSError as exc:
            raise PlayerError(f'Could not start FFmpeg: {exc}') from exc
        with self._lock:
            old = [session.decoder] + ([session.switch[0]] if session.switch else [])
            session.switch = (decoder, _Segment(0, song, offset, speed))
            self._session = session
            self.song, self.paused, self.speed = song, False, speed
            self.position = offset
            self.last_returncode, self.last_error = None, ''
        for process in old:                      # unblock the pump if it is waiting on the old decoder
            if process is not None and process.poll() is None:
                try:
                    process.kill()
                except OSError:
                    pass

    def stop(self) -> None:
        with self._lock:
            session, self._session = self._session, None
        if session is not None and self.playing_session(session):
            self._fade_and_end(session)              # fades out; closes when the buffer has played
        else:
            self._end_session(session)
        self.song, self.position, self.paused, self.speed = None, 0.0, False, 1.0
        self.last_returncode = None

    def _time_at(self, session: _Session, frame: int) -> float | None:
        for segment in reversed(session.segments):
            if segment.start_frame <= frame:
                return segment.time_at(frame)
        return None

    def _fade_and_end(self, session: _Session) -> int | None:
        """Fade the stream out, let the buffered audio play, then close; returns the last frame."""
        with self._lock:
            session.pausing = True
        if not session.faded.wait(0.3):
            self._end_session(session)              # pump stuck: stop at once instead
            return None
        with self._lock:
            remaining = max(0, session.written - self._played(session)) / RATE
            decoders = [session.decoder] + ([session.switch[0]] if session.switch else [])
            session.decoder = session.switch = None
        for decoder in decoders:                    # nothing more is read; only FFplay finishes
            if decoder is not None and decoder.poll() is None:
                try:
                    decoder.kill()
                    decoder.wait(timeout=3)
                except (OSError, subprocess.TimeoutExpired):
                    pass
        with self._lock:
            self._closing = [s for s in self._closing if not s.stopped] + [session]
        timer = threading.Timer(remaining + 0.05, self._end_session, args=(session,))
        timer.daemon = True
        timer.start()
        return session.pause_frame

    def pause(self) -> None:
        """Fade out (20 ms) and stop; resume continues exactly where the sound ended."""
        if not self.playing:
            return
        position = self.current_position()
        with self._lock:
            session, self._session = self._session, None
        end = self._fade_and_end(session)
        if end is not None and session.switch is None:
            heard = self._time_at(session, end)
            if heard is not None:
                position = heard
        if self.song and self.song.duration:
            position = min(position, self.song.duration)
        self.position, self.paused, self.speed = position, True, 1.0

    def resume(self) -> None:
        if self.song is not None and self.paused:
            self.play(self.song, self.position)

    def seek(self, seconds: float) -> None:
        if not self.song:
            return
        if self.paused:
            duration = self.song.duration
            self.position = max(0.0, min(seconds, duration)) if duration else max(0.0, seconds)
        else:
            self.play(self.song, seconds, self.speed)

    def set_volume(self, value: int) -> None:
        """Takes effect on the next 20 ms of audio, ramped; no restart."""
        self.volume = max(0, min(100, int(value)))

    def set_speed(self, speed: float) -> None:
        if not self.playing or self.song is None or speed == self.speed:
            return
        self.play(self.song, self.current_position(), speed)

    def poll_end(self) -> bool:
        """One-shot: True when the current song has (nearly) finished or playback failed."""
        with self._lock:
            session = self._session
            if session is None or self.song is None or self.paused:
                return False
            if session.sink is not None and session.sink.poll() is not None and not session.stopped:
                self.last_returncode = session.sink.poll() or 1
                self.last_error = '; '.join(session.sink_errors) or 'the audio output stopped'
                finished = True
            else:
                if session.switch is not None or not session.segments:
                    return False
                segment = session.segments[-1]
                if segment.end_frame is None or segment.reported:
                    return False
                if segment.returncode not in (0, None) and segment.start_frame == segment.end_frame:
                    self.last_returncode, self.last_error = segment.returncode, segment.error
                elif self._played(session) < segment.end_frame - END_EARLY * RATE:
                    return False
                else:
                    self.last_returncode, self.last_error = 0, ''
                segment.reported = True
                finished = False
            self.song, self.position, self.speed = None, 0.0, 1.0
        if finished:
            code, error = self.last_returncode, self.last_error
            self.stop()
            self.last_returncode, self.last_error = code, error
        return True

    def shutdown(self) -> None:
        """Closing Oggcultist: end every FFplay/FFmpeg now and wait until they are gone."""
        with self._lock:
            sessions = [self._session] + self._closing
            self._session, self._closing = None, []
        for session in sessions:
            self._end_session(session)
        self.song, self.position, self.paused, self.speed = None, 0.0, False, 1.0
