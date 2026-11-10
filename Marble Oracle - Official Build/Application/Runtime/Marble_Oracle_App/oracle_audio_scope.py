"""Windows default-speaker WASAPI loopback for two CRT instruments.

No microphone capture and no simulated activity: a daemon captures output, Tk
reads immutable snapshots; device changes and WASAPI failures reconnect.
"""
from __future__ import annotations
import os
import threading

SAMPLE_RATE = 48000
SILENT_WAVE = (0.,) * 48
SILENT_BANDS = (0.,) * 20


def analyse(samples, np, samplerate=SAMPLE_RATE):
    """Return true waveform and logarithmic FFT levels without fake activity."""
    samples = np.asarray(samples, dtype=np.float32)
    if samples.ndim == 2:
        samples = samples.mean(axis=1)
    if samples.size < 64:
        return SILENT_WAVE, SILENT_BANDS
    samples = np.nan_to_num(samples, nan=0., posinf=0., neginf=0.)
    latest = samples[-min(samples.size, round(samplerate * .042)):]
    wav = np.interp(np.linspace(0, len(latest)-1, 48),
                    np.arange(len(latest)), latest)
    wav = np.clip(wav * 1.8, -1., 1.)
    n = min(4096, len(samples))
    taper = np.hanning(n)
    spectrum = np.abs(np.fft.rfft(samples[-n:] * taper)) / max(1., taper.sum() * .5)
    freqs = np.fft.rfftfreq(n, d=1. / samplerate)
    edges = np.geomspace(70, min(16000, samplerate * .46), 21)
    bands = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        values = spectrum[(freqs >= lo) & (freqs < hi)]
        peak = float(values.max()) if values.size else 0.
        bands.append(min(1., max(0., peak) ** .55 * 3.3))
    return tuple(float(v) for v in wav), tuple(bands)


def select_speaker_loopback(sc):
    """Never confuse an ordinary microphone with an output loopback."""
    speaker = sc.default_speaker()
    if speaker is None:
        raise RuntimeError('No default speaker found')
    sid = str(speaker.id)
    try:
        mic = sc.get_microphone(id=sid, include_loopback=True)
        if mic is not None and getattr(mic, 'isloopback', False):
            return speaker, mic
    except (LookupError, ValueError, RuntimeError):
        pass
    candidates = [m for m in sc.all_microphones(include_loopback=True)
                  if getattr(m, 'isloopback', False)]
    for mic in candidates:
        if str(mic.id) == sid:
            return speaker, mic
    named = [m for m in candidates if
             str(getattr(m, 'name', '')).casefold() ==
             str(getattr(speaker, 'name', '')).casefold()]
    if len(named) == 1:
        return speaker, named[0]
    raise RuntimeError('No matching WASAPI speaker loopback; microphone capture refused')


class SystemAudioScope:
    def __init__(self, retry_seconds=3):
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None
        self._wave = SILENT_WAVE
        self._bands = SILENT_BANDS
        self.status = 'OFF'
        self.error = ''
        self.device_name = ''
        self.frames_received = 0
        self.retry_seconds = retry_seconds

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name='CRT-WASAPI-loopback', daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=.5)
        self._publish('OFF')

    def snapshot(self):
        with self._lock:
            return self._wave, self._bands, self.status

    def diagnostics(self):
        with self._lock:
            return dict(status=self.status, device=self.device_name,
                        error=self.error, frames=self.frames_received)

    def _publish(self, status, wave=None, bands=None, error='', device=None):
        with self._lock:
            self.status = status
            self.error = error
            if device is not None:
                self.device_name = device
            self._wave = SILENT_WAVE if wave is None else tuple(wave)
            self._bands = SILENT_BANDS if bands is None else tuple(bands)

    def _capture_once(self, sc, np):
        speaker, mic = select_speaker_loopback(sc)
        self._publish('CONNECTING', device=str(getattr(speaker, 'name', speaker.id)))
        previous = SILENT_BANDS
        with mic.recorder(samplerate=SAMPLE_RATE, blocksize=4096) as recorder:
            count = 0
            while not self._stop.is_set():
                chunk = recorder.record(numframes=1024)
                wave, bands = analyse(chunk, np)
                previous = tuple(max(new, old * .78) for new, old in zip(bands, previous))
                self._publish('LIVE', wave=wave, bands=previous)
                with self._lock:
                    self.frames_received += 1
                count += 1
                if count % 80 == 0:
                    active = sc.default_speaker()
                    if active is None or str(active.id) != str(speaker.id):
                        raise RuntimeError('Default speaker changed')

    def _run(self):
        if os.name != 'nt':
            self._publish('WINDOWS ONLY')
            return
        try:
            import numpy as np
            import soundcard as sc
        except (ImportError, OSError) as exc:
            self._publish('OFF', error=f'Missing audio dependency: {exc}')
            return
        while not self._stop.is_set():
            try:
                self._capture_once(sc, np)
            except Exception as exc:
                self._publish('RECONNECT', error=str(exc))
                self._stop.wait(self.retry_seconds)
        self._publish('OFF')
