"""oracle_audio.py -- Marble_Oracle's sound (stdlib only).

    AudioBackend        the one place that talks to the sound device: Windows winsound, else a paplay / aplay /
                        afplay child.  play_once(path) (a one-shot, replacing any other), stop_once(), play_blocking(path).
                        Host effects (Sfx) and the lexicon voices (VoiceBank) go through it.  (play_loop / stop_loop had no
                        caller and were deleted in 1020.)
    Sfx                 one-shot sound effects, fire-and-forget
    VoiceBank, synth_wav, respell   the LEXICON voices: recorded clips from latin_voices.zip, else a formant synth.  Since 0955
                        respell comes from oracle_latin (a real classical / ecclesiastical respelling); the old toy one below
                        is the fallback when that file is missing or raises.
Split out of marble_oracle.py (build 0929); behaviour unchanged."""
import os
import random
import math
import struct
import sys
import threading
import time

import oracle_assets
from oracle_assets import state_dir

# 1023: the LEXICON voice is louder and lower.  VOICE_GAIN multiplies the volume slider (each clip is held just under full scale, so a loud clip
# is raised as far as it can go without clipping).  VOICE_PITCH < 1 plays the clip at that fraction of its sample rate: lower, and slower by the
# same amount (tape slowed down; 0.85 is about 2.8 semitones down).  1.0 and 1.0 give the old voice.
# 1060 (the owner: "make the latin voice volume higher by default and add a volume slider"): the slider's top is gain 4.0 (was 2.0) and it
# starts at VOICE_VOL 0.8, as before: about 5.5 dB louder by default (median of the recorded clips), up to about 7.5 dB at the top.  Past a
# clip's own ceiling a soft knee (VOICE_KNEE of VOICE_PEAK) rounds off the peaks instead of turning the whole clip down (the 1023 cap held the
# loudest clips back), so louder is really louder and still never clips.
VOICE_GAIN = 4.0
VOICE_VOL = 0.8
VOICE_PITCH = 0.85
VOICE_PEAK = 31000                                   # of 32767: the loudest a boosted sample may go
VOICE_KNEE = 0.6


def _zip(name):
    return oracle_assets.open_zip(name)


def _respell_toy(lemma, ecclesiastical):
    """Rough ASCII respelling (a toy, not IPA): classical vs ecclesiastical.  Kept as the fallback for respell()."""
    w = lemma.lower()
    out = []
    i = 0
    while i < len(w):
        c = w[i]
        nx = w[i + 1] if i + 1 < len(w) else ""
        n2 = w[i + 2] if i + 2 < len(w) else ""
        if w[i:i + 2] in ("ae", "oe"):
            out.append("e" if ecclesiastical else ("eye" if w[i:i + 2] == "ae" else "oy")); i += 2; continue
        if c == "c":
            out.append("ch" if ecclesiastical and (nx in "eiy" or w[i + 1:i + 3] in ("ae", "oe")) else "k")
        elif c == "s" and nx == "c" and ecclesiastical and n2 in "ei":
            out.append("sh"); i += 2; continue
        elif c == "g" and ecclesiastical and nx in "ei":
            out.append("j")
        elif c == "t" and nx == "i" and ecclesiastical and n2 in "aeiou":
            out.append("ts")
        elif c == "v":
            out.append("v" if ecclesiastical else "w")
        elif c == "j":
            out.append("y")
        elif c == "u" and not ecclesiastical and nx == "":
            out.append("oo")
        else:
            out.append(c)
        i += 1
    return "".join(out)


try:
    import oracle_latin as _latin
except Exception:                                    # optional: without it the toy respelling above speaks
    _latin = None


def respell(lemma, ecclesiastical):
    """ASCII respelling for synth_wav (never IPA: the synth only knows eye, oy, ch, sh, ts and single letters).  oracle_latin's
    when it has one, else the toy's; a failure in oracle_latin is never the voice's failure."""
    if _latin is not None:
        try:
            out = _latin.respell(lemma, ecclesiastical)
            if out:
                return out
        except Exception:
            pass
    return _respell_toy(lemma, ecclesiastical)


_VOW = {"a": (800, 1300), "e": (550, 1800), "i": (300, 2200), "o": (500, 900), "u": (320, 800), "y": (300, 2100)}
_SON = {"m": (250, 1000), "n": (280, 1500), "l": (350, 1100), "r": (400, 1300), "w": (300, 700),
        "v": (300, 1200), "b": (250, 900), "d": (280, 1600), "g": (280, 1300), "z": (300, 1800), "j": (300, 2000)}


_NOI = {"s": 6000, "f": 4500, "h": 2000, "k": 2500, "t": 4000, "p": 1500, "c": 2500, "x": 4500, "q": 2500,
        "sh": 3500, "ch": 3500, "ts": 5000}


def synth_wav(spell, vol=0.8, rate=16000):
    """Tiny formant synthesiser (stdlib): speaks a respelling when no recorded voice bank exists.
    Deliberately robotic; recorded latin_voices.zip always wins."""
    import io
    import wave
    rnd = random.Random(1)
    toks, i = [], 0
    while i < len(spell):
        for t in ("eye", "oy", "ch", "sh", "ts"):
            if spell.startswith(t, i):
                toks.append(t); i += len(t); break
        else:
            toks.append(spell[i]); i += 1
    out = []
    ph = 0.0
    n_v = max(1, sum(1 for t in toks if t in ("eye", "oy") or t[0] in _VOW))
    vi = 0
    z1 = z2 = y1 = y2 = 0.0
    for t in toks:
        if t == "eye":
            segs = [(_VOW["a"], .16), (_VOW["i"], .12)]
        elif t == "oy":
            segs = [(_VOW["o"], .16), (_VOW["i"], .12)]
        elif t in _VOW:
            segs = [(_VOW[t], .15)]
        elif t in _SON:
            segs = [(_SON[t], .08)]
        elif t in _NOI:
            segs = [(_NOI[t], .07 if t not in "ptkc" else .05)]
        else:
            continue
        for tgt, dur in segs:
            voiced = isinstance(tgt, tuple)
            vowel = t in _VOW or t in ("eye", "oy")
            if vowel:
                vi += 1
            n = int(dur * rate)
            f0 = 125 - 25 * (vi / float(n_v))
            for k in range(n):
                env = min(1.0, k / (0.012 * rate), (n - k) / (0.012 * rate))
                if voiced:
                    ph += f0 / rate
                    ph -= int(ph)
                    x = (ph * 2 - 1) * (1.0 if vowel else 0.45)
                    r1, r2 = 0.985, 0.985
                    f1, f2 = tgt
                    c1, c2 = 2 * r1 * math.cos(2 * math.pi * f1 / rate), 2 * r2 * math.cos(2 * math.pi * f2 / rate)
                    y = (1 - r1) * x + c1 * y1 - r1 * r1 * y2
                    y2, y1 = y1, y
                    w = (1 - r2) * y + c2 * z1 - r2 * r2 * z2
                    z2, z1 = z1, w
                    v = w * 7.0
                else:
                    v = (rnd.random() * 2 - 1) * 0.28 * (0.5 + tgt / 12000.0)
                    if t in "ptkc" and k > n // 3:
                        v *= 0.3
                out.append(max(-1.0, min(1.0, v * env)) * vol)
        if t not in _VOW and t not in ("eye", "oy"):
            out += [0.0] * int(0.012 * rate)
    out += [0.0] * int(0.08 * rate)
    import array
    a = array.array("h", [int(v * 26000) for v in out])
    if sys.byteorder == "big":
        a.byteswap()
    b = io.BytesIO()
    with wave.open(b, "wb") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(rate)
        wf.writeframes(a.tobytes())
    return b.getvalue()


class VoiceBank:
    """latin_voices.zip -> '<lemma>_c.wav' / '<lemma>_e.wav'.  Silent when zip/backend absent.  Since 0962 a loose folder wins over the zip:
    data/voices/<lemma>_c.wav (searched like every asset: $MARBLE_ORACLE_ASSETS, then data/, then the program folder), so a clip can be replaced
    by dropping a WAV there.  A loose clip is never "recorded" (that is SOURCES.txt's job, in the zip)."""
    def __init__(self):
        self.z = _zip("latin_voices.zip")
        self.loose = {}                             # '<lemma>_c.wav' -> a path in a voices/ folder
        for root in oracle_assets.roots():
            d = os.path.join(root, "voices")
            try:
                for n in sorted(os.listdir(d)):
                    if n.lower().endswith(".wav") and os.path.isfile(os.path.join(d, n)):
                        self.loose.setdefault(n.lower(), os.path.join(d, n))        # the first folder found wins
            except OSError:
                pass
        self.members = {}                           # '<lemma>_c.wav' -> zip member ('<lemma>_c.wav', or the packed '.pcmz')
        if self.z:
            try:
                import lzma  # noqa: F401  (packed clips need it; without it they count as absent: synth voice)
                packed = True
            except ImportError:
                packed = False
            for n in self.z.namelist():
                if packed and n.lower().endswith(".pcmz"):
                    self.members.setdefault(n[:-5] + ".wav", n)
            for n in self.z.namelist():
                if n.lower().endswith(".wav"):
                    self.members[n] = n
        self.names = (set(n for n in self.z.namelist() if not n.lower().endswith(".pcmz")) | set(self.members) if self.z else set()) | set(self.loose)
        self.vol = VOICE_VOL
        self.busy = False
        self.human = set()                          # clips that are recordings of a person (SOURCES.txt), else synthetic
        try:
            if self.z and "SOURCES.txt" in self.names:
                self.human = set(l.strip() for l in self.z.read("SOURCES.txt").decode("utf-8", "replace").splitlines() if l.strip())
        except Exception:
            pass

    def has(self, lemma, ecc):
        return ("%s_%s.wav" % (lemma.lower(), "e" if ecc else "c")) in self.names

    def recorded(self, lemma, ecc):
        return ("%s_%s.wav" % (lemma.lower(), "e" if ecc else "c")) in self.human

    def _wav(self, lemma, ecc):
        n = "%s_%s.wav" % (lemma.lower(), "e" if ecc else "c")
        if n in self.loose:
            try:
                with open(self.loose[n], "rb") as f:
                    return self._voice(f.read(), self.vol)
            except OSError:
                pass                                         # unreadable: fall through to the zip, then the synth
        if n in self.members:
            data = self.z.read(self.members[n])
            if self.members[n] != n:
                data = oracle_assets.unpack_pcmz(data)       # packed clip: back to the exact WAV (a few ms)
            return self._voice(data, self.vol)
        return self._voice(synth_wav(respell(lemma, ecc), 1.0), self.vol)      # no recording: built-in formant synth (full scale; _voice sets the level)

    def play(self, lemma, ecc):
        """One pronunciation (True = ecclesiastical) on a throwaway thread."""
        return self.speak(lemma, "e" if ecc else "c")

    def speak(self, lemma, mode="both"):
        """mode 'c' / 'e' / 'both' (classical, a beat, ecclesiastical, as in 3.8).  The clip plays on a
        throwaway thread so the animation never stalls; a second request while one is playing is ignored."""
        if self.busy or self.vol <= 0.001:
            return False
        seq = {"c": (False,), "e": (True,), "both": (False, True)}.get(mode, (False, True))
        try:
            clips = [self._wav(lemma, e) for e in seq]
        except Exception:
            return False

        def run():
            try:
                for i, data in enumerate(clips):
                    path = os.path.join(state_dir(), "voice%d.wav" % i)
                    with open(path, "wb") as f:
                        f.write(data)
                    self._play(path)
                    if i + 1 < len(clips):
                        time.sleep(0.28)
            except Exception:
                pass
            finally:
                self.busy = False
        self.busy = True
        try:
            threading.Thread(target=run, daemon=True).start()
        except Exception:
            self.busy = False
            return False
        return True

    @staticmethod
    def _voice(wav, vol, gain=None, pitch=None):
        """16-bit PCM WAV at `vol` x VOICE_GAIN (held under VOICE_PEAK by a soft knee since 1060), with its sample rate lowered to VOICE_PITCH of itself (1023: was _scale,
        which could only turn a clip down).  Anything that is not plain 16-bit PCM with its "fmt " chunk first plays as it is."""
        import array
        gain = VOICE_GAIN if gain is None else gain
        pitch = VOICE_PITCH if pitch is None else pitch
        i = wav.find(b"data")
        if i < 0 or wav[12:16] != b"fmt " or wav[20:22] != b"\x01\x00" or wav[34:36] != b"\x10\x00":
            return wav
        n = struct.unpack("<I", wav[i + 4:i + 8])[0]
        a = array.array("h")
        a.frombytes(wav[i + 8:i + 8 + n - (n % 2)])
        if sys.byteorder == "big":
            a.byteswap()
        peak = max(map(abs, a)) if a else 0
        g = vol * gain
        if peak and peak * g > VOICE_PEAK:                # 1060: a soft knee over the loud part only, never clipped (was: the whole clip turned down)
            knee = VOICE_KNEE * VOICE_PEAK
            room = VOICE_PEAK - knee

            def soft(s):
                y = s * g
                m = abs(y)
                if m <= knee:
                    return int(y)
                m = knee + room * math.tanh((m - knee) / room)
                return int(m if y > 0 else -m)
            a = array.array("h", [soft(s) for s in a])
        elif abs(g - 1.0) > 0.001:
            a = array.array("h", [int(s * g) for s in a])
        if sys.byteorder == "big":
            a.byteswap()
        head = wav[:i + 8]
        if abs(pitch - 1.0) > 0.001:
            rate, align = struct.unpack("<I", head[24:28])[0], struct.unpack("<H", head[32:34])[0]
            new = max(4000, int(round(rate * pitch)))
            head = head[:24] + struct.pack("<II", new, new * align) + head[32:]
        return head + a.tobytes() + wav[i + 8 + len(a) * 2:]

    @staticmethod
    def _play(path):
        BACKEND.play_blocking(path)


class AudioBackend:
    """The one place that talks to the sound device.

    Windows has ONE winsound channel: a one-shot or a blocking clip replaces whatever was playing.
    Elsewhere every sound is its own paplay / aplay / afplay child.

    nt / winsound / popen / which can be injected (tests); by default they are the real ones.
    There is no music loop. play_loop was removed in 1020, and the restart-the-loop path (which could no longer run) in 1021."""

    def __init__(self, nt=None, winsound=None, popen=None, which=None, run=None):
        self.nt = (os.name == "nt") if nt is None else nt
        self._ws, self._popen, self._which, self._run = winsound, popen, which, run
        self.proc = None                 # the current one-shot child (not Windows)

    # -- plumbing -------------------------------------------------------------------------------------------------
    def _winsound(self):
        if self._ws is None:
            import winsound
            self._ws = winsound
        return self._ws

    def _cmd(self):
        import shutil
        which = self._which or shutil.which
        return next((c for c in ("paplay", "aplay", "afplay") if which(c)), None)

    def _spawn(self, argv):
        import subprocess
        return (self._popen or subprocess.Popen)(argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # -- one-shots --------------------------------------------------------------------------------------------------
    def play_once(self, path):
        """Fire and forget; replaces the previous one-shot."""
        self.stop_once()
        try:
            if self.nt:
                ws = self._winsound()
                ws.PlaySound(path, ws.SND_FILENAME | ws.SND_ASYNC)
                return True
            cmd = self._cmd()
            if not cmd:
                return False
            self.proc = self._spawn([cmd, path])
            return True
        except Exception:
            return False

    def stop_once(self, resume=True):
        """Cut the one-shot short (a stopped sound).  `resume` is accepted and ignored: nothing is waiting to be restarted."""
        try:
            if self.nt:
                ws = self._winsound()
                ws.PlaySound(None, ws.SND_PURGE)
            elif self.proc is not None and self.proc.poll() is None:
                self.proc.terminate()
        except Exception:
            pass
        self.proc = None

    def play_blocking(self, path):
        """Play and wait (the lexicon voices, on their own thread)."""
        try:
            if self.nt:
                ws = self._winsound()
                ws.PlaySound(path, ws.SND_FILENAME)
                return True
            cmd = self._cmd()
            if not cmd:
                return False
            import subprocess
            (self._run or subprocess.run)([cmd, path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20)
            return True
        except Exception:
            return False


BACKEND = AudioBackend()


class Sfx:
    """One-shot sound effect, fire-and-forget (through the shared AudioBackend)."""
    backend = BACKEND

    @classmethod
    def play(cls, path):
        return cls.backend.play_once(path)

    @classmethod
    def stop(cls):
        cls.backend.stop_once()
