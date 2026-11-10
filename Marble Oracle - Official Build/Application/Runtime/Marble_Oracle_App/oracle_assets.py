"""oracle_assets.py -- the small shared kernel of Marble_Oracle and its plug-ins (stdlib only).

    state_dir()                 %LOCALAPPDATA%\\MarbleOracle, else $XDG_STATE_HOME/marbleoracle (MARBLE_ORACLE_STATE overrides)
    asset(name, here)           data/<name>, then beside the program (MARBLE_ORACLE_ASSETS is searched first)
    load_json / save_json       small state files in state_dir(), written atomically
    join_parts(name, here)      rebuild an asset zip shipped as name.part00, .part01 ... (older downloads)
    open_zip(name, here)        an asset zip, from its pieces when needed; None when absent
    audio_path(name, here)      a playable PCM WAV for data/<name>: the .wav itself, else its packed .pcmz inflated once
                                into state_dir()/cache/ (winsound and paplay/aplay only play plain PCM WAV files)
    unpack_pcmz(data) -> bytes  .pcmz -> the exact WAV bytes it was packed from (tools/pack_audio.py writes them)
    rgba_png(w, h, rows)        RGBA rows -> PNG bytes

.pcmz ("PCM, predicted and LZMA-packed") is lossless: the samples of each channel are replaced by their 1st/2nd/3rd
order differences (modulo 2^16), a second channel by its difference from the first, the low and high bytes stored as
two planes, and the lot LZMA-compressed.  Decoding is two or three itertools.accumulate passes (C speed).  If this
Python has no lzma module the packed sounds are treated as absent (music silent, voices synthesised), like any
missing optional asset.
"""
import array
import io
import itertools
import json
import os
import struct
import sys
import tempfile
import wave
import zipfile
import zlib

HERE = os.path.dirname(os.path.abspath(sys.argv[0] if getattr(sys, "frozen", False) else __file__))
PCMZ_MAGIC = b"PCMZ1\n"
PART_RE = r"^(.*?)%s\.part(\d{2,3})$"          # a big asset shipped in pieces: [anything]name.part00, .part01, ...


def state_dir():
    p = os.environ.get("Marble_Oracle_STATE") or os.environ.get("MARBLE_ORACLE_STATE")
    if not p:
        if os.name == "nt":
            p = os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "Marble_Oracle")
        else:
            p = os.path.join(os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state"), "Marble_Oracle")
    try:
        os.makedirs(p, exist_ok=True)
    except OSError:
        pass
    return p


def roots(here=None):
    here = here or HERE
    out = [os.environ["MARBLE_ORACLE_ASSETS"]] if os.environ.get("MARBLE_ORACLE_ASSETS") else []
    return out + [os.path.join(here, "data"), here]


def asset(name, here=None):
    """data/<name> first, then beside the script (flat folders still work).  MARBLE_ORACLE_ASSETS is searched first."""
    for r in roots(here):
        p = os.path.join(r, name)
        if os.path.isfile(p):
            return p
    return None


def load_json(name, default):
    try:
        with open(os.path.join(state_dir(), name), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(name, obj):
    """Atomically persist settings without sharing a fixed temporary filename.

    Concurrent saves must not overwrite one another's temporary files. A
    write failure keeps the last valid configuration rather than truncating it.
    The calling API and settings format remain unchanged.
    """
    temp_path = None
    try:
        folder = state_dir()
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=folder,
                                         prefix="." + os.path.basename(name) + ".",
                                         suffix=".tmp", delete=False) as stream:
            temp_path = stream.name
            json.dump(obj, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_path, os.path.join(folder, name))
    except (OSError, TypeError, ValueError):
        # Preserve legacy non-raising behaviour for callers writing optional
        # preference snapshots. A prior configuration is not damaged.
        pass
    finally:
        if temp_path is not None:
            try:
                os.unlink(temp_path)
            except FileNotFoundError:
                pass
            except OSError:
                pass


def join_parts(name, here=None):
    """Rebuild data/<name> from its numbered pieces lying in an asset folder (a download too big to send whole arrives
    as name.part00, name.part01 ..., often with a build prefix).  The newest complete set wins; the joined file is
    written beside its pieces only if it opens as a zip.  The pieces are left where they are.  -> path or None.
    Kept for folders unpacked from builds before 0928; nothing ships in pieces any more."""
    import re
    rx = re.compile(PART_RE % re.escape(name), re.I)
    for root in roots(here):
        try:
            names = os.listdir(root)
        except OSError:
            continue
        sets = {}
        for n in names:
            mt = rx.match(n)
            if mt:
                sets.setdefault(mt.group(1), []).append((int(mt.group(2)), os.path.join(root, n)))
        if not sets:
            continue
        good = []
        for prefix, parts in sets.items():
            parts.sort()
            if [i for i, _ in parts] == list(range(len(parts))):          # 00, 01, ... with no gap
                good.append((max(os.path.getmtime(p) for _, p in parts), parts))
        for _, parts in sorted(good, reverse=True):
            dst = os.path.join(root, name)
            tmp = dst + ".joining"
            try:
                with open(tmp, "wb") as out:
                    for _, p in parts:
                        with open(p, "rb") as f:
                            while True:
                                chunk = f.read(1 << 20)
                                if not chunk:
                                    break
                                out.write(chunk)
                with zipfile.ZipFile(tmp) as z:
                    z.namelist()
                os.replace(tmp, dst)
                return dst
            except Exception:
                try:
                    os.remove(tmp)
                except OSError:
                    pass
    return None


def open_zip(name, here=None):
    """An asset zip: data/<name>, or rebuilt from its pieces when it is missing or does not open."""
    p = asset(name, here)
    if p:
        try:
            return zipfile.ZipFile(p)
        except Exception:
            p = None                                   # damaged (a bad hand join): try the pieces
    p = join_parts(name, here)
    if not p:
        return None
    try:
        return zipfile.ZipFile(p)
    except Exception:
        return None


def rgba_png(w, h, rows):
    """rows: iterable of bytes (w*4 each) -> PNG bytes (stdlib only)."""
    raw = b"".join(b"\x00" + r for r in rows)

    def chunk(t, d):
        c = struct.pack(">I", len(d)) + t + d
        return c + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 3)) + chunk(b"IEND", b""))


# --------------------------------------------------------------------------- packed PCM
def _undiff(vals, order):
    for _ in range(order):
        vals = itertools.accumulate(vals)
    return array.array("H", map((0xFFFF).__and__, vals))          # streamed: no million-element list in between


def unpack_pcmz(data):
    """.pcmz bytes -> the exact WAV bytes they were packed from.  Raises on anything malformed (or no lzma)."""
    import lzma
    if not data.startswith(PCMZ_MAGIC):
        raise ValueError("not a pcmz")
    o = len(PCMZ_MAGIC)
    ch, width, rate, frames, order, planes, joint = struct.unpack("<BBIIBBB", data[o:o + 13])
    if width != 2 or not 1 <= ch <= 2 or order > 3:
        raise ValueError("unsupported pcmz")
    raw = lzma.decompress(data[o + 13:])
    if len(raw) != frames * ch * 2:
        raise ValueError("pcmz length")
    if planes:
        n = len(raw) // 2
        b = bytearray(len(raw))
        b[0::2] = raw[:n]
        b[1::2] = raw[n:]
        raw = bytes(b)
    res = array.array("H")
    res.frombytes(raw)
    if sys.byteorder == "big":
        res.byteswap()
    chans = [_undiff(res[c * frames:(c + 1) * frames], order) for c in range(ch)]
    if ch == 2 and joint:                              # second channel was stored as its difference from the first
        chans[1] = array.array("H", map((0xFFFF).__and__, map(int.__add__, chans[0], chans[1])))
    if ch == 1:
        pcm = chans[0]
    else:
        pcm = array.array("H", bytes(frames * ch * 2))
        for c in range(ch):
            pcm[c::ch] = chans[c]
    if sys.byteorder == "big":
        pcm.byteswap()
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setnchannels(ch)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm.tobytes())
    return out.getvalue()


def _cache_name(stem, packed):
    """Versioned by the packed file's own checksum, so a rebaked sound never plays a stale inflate."""
    return "%s.%08x.wav" % (stem, zlib.crc32(packed) & 0xFFFFFFFF)


def audio_path(name, here=None):
    """data/<name> (a .wav) if it is there; else data/<stem>.pcmz, inflated once into state_dir()/cache/ (atomic
    write, reused on every later play).  None when neither exists or the packed file cannot be read."""
    p = asset(name, here)
    if p:
        return p
    stem = os.path.splitext(name)[0]
    src = asset(stem + ".pcmz", here)
    if not src:
        return None
    try:
        with open(src, "rb") as f:
            packed = f.read()
        cache = os.path.join(state_dir(), "cache")
        dst = os.path.join(cache, _cache_name(stem, packed))
        if os.path.isfile(dst):
            return dst
        wav = unpack_pcmz(packed)
        os.makedirs(cache, exist_ok=True)
        import threading
        tmp = dst + ".tmp%d_%d" % (os.getpid(), threading.get_ident())
        with open(tmp, "wb") as f:
            f.write(wav)
        os.replace(tmp, dst)
        for old in os.listdir(cache):                  # an older inflate of the same sound
            if old.startswith(stem + ".") and old.endswith(".wav") and old != os.path.basename(dst):
                try:
                    os.remove(os.path.join(cache, old))
                except OSError:
                    pass
        return dst
    except Exception:
        return None


def warm_audio(names, here=None):
    """Inflate packed sounds on a background thread, so the first play does not wait for it."""
    import threading

    def run():
        for n in names:
            audio_path(n, here)
    t = threading.Thread(target=run, daemon=True)
    t.start()
    return t
