"""Three-Rune Seeing for Marble Oracle.

The active 12-frame animations come from the matched-stone archive; original
image archives remain bundled for provenance and fallback. The interpretive
keyword associations are for reflective use, not historical authentication.
"""
import base64
from collections import OrderedDict
import tkinter as tk
import json
import math
import os
import secrets
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
POSITIONS = ("Past", "Present", "Possible Future")
# Source artwork numbering is NOT canonical Futhark sequence.
# ID 16 is especially stylised; its provisional Perthro binding warrants artist confirmation.
SPEC = [
    (1, 'Ansuz', 'ᚨ', 'communication', 'insight'),
    (2, 'Uruz', 'ᚢ', 'strength', 'endurance'),
    (3, 'Thurisaz', 'ᚦ', 'boundaries', 'disruption'),
    (4, 'Fehu', 'ᚠ', 'resources', 'exchange'),
    (5, 'Raidho', 'ᚱ', 'journey', 'rhythm'),
    (6, 'Kenaz', 'ᚲ', 'clarity', 'craft'),
    (7, 'Gebo', 'ᚷ', 'gift', 'reciprocity'),
    (8, 'Wunjo', 'ᚹ', 'joy', 'harmony'),
    (9, 'Hagalaz', 'ᚺ', 'disruption', 'change'),
    (10, 'Nauthiz', 'ᚾ', 'need', 'constraint'),
    (11, 'Isa', 'ᛁ', 'stillness', 'delay'),
    (12, 'Algiz', 'ᛉ', 'protection', 'alertness'),
    (13, 'Sowilo', 'ᛊ', 'vitality', 'success'),
    (14, 'Tiwaz', 'ᛏ', 'integrity', 'sacrifice'),
    (15, 'Berkano', 'ᛒ', 'growth', 'nurture'),
    (16, 'Perthro', 'ᛈ', 'uncertainty', 'hidden factors'),
    (17, 'Jera', 'ᛃ', 'cycles', 'harvest'),
    (18, 'Eihwaz', 'ᛇ', 'resilience', 'transition'),
    (19, 'Ehwaz', 'ᛖ', 'cooperation', 'momentum'),
    (20, 'Mannaz', 'ᛗ', 'self', 'community'),
    (21, 'Laguz', 'ᛚ', 'intuition', 'flow'),
    (22, 'Ingwaz', 'ᛜ', 'potential', 'gestation'),
    (23, 'Dagaz', 'ᛞ', 'breakthrough', 'dawn'),
    (24, 'Othala', 'ᛟ', 'heritage', 'belonging'),
]
RUNES = [dict(file=n, name=name, glyph=glyph, keywords=(a,b),
              imageFront=f'{n:02}.png', imageBack=f'{n:02}-blank.png')
         for n,name,glyph,a,b in SPEC]
assert len(RUNES) == len(set(r['name'] for r in RUNES)) == 24
RUNE_BY_NAME = {r['name'].lower(): r for r in RUNES}


class RuneDeck:
    def __init__(self):
        self.runes = RUNES
        self.zip_path = os.path.join(HERE, 'data', 'runes.zip')
        self._cache = {}
        # Bounded decoded-image cache: repeated draws must not retain every
        # rune/size/frame ever viewed in the lifetime of the application.
        # Visible frames are separately referenced by the Scene and Labels.
        self._flip_cache = OrderedDict()
        self._flip_cache_limit = 144
        # Re-reading a frame must not re-parse a 2,900-entry ZIP central
        # directory on every flip tick or every window resize.
        self._frame_archives = {}
        self._strip_cache = {}  # Decoded source strips, independent of displayed frame size
        self.flip_zip_path = os.path.join(HERE, 'data', 'rune_flip_strips.zip')
        self.native_zip_path = os.path.join(HERE, 'data', 'rune_native_frames.zip')
        self._native_assets = os.path.isfile(self.native_zip_path)
        # Generated from one shared rough-cut stone. Every back, face, and
        # intermediate flip is derived from exactly the same alpha silhouette.
        self.consistent_zip_path = os.path.join(HERE, 'data', 'rune_consistent_flips.zip')
        self._consistent_assets = os.path.isfile(self.consistent_zip_path)
        self.flip_duration_ms = 115
        self.flip_frames = 8
        # Use true blank stone backs for the opening frames so no rune symbol
        # leaks through before the flip reveal begins.
        self.blank_frame_cutoff = 3
        self._flip_names = {}
        if os.path.isfile(self.flip_zip_path):
            with zipfile.ZipFile(self.flip_zip_path) as anim:
                manifest = json.loads(anim.read('manifest.json'))
                self.flip_duration_ms = max(145, int(manifest.get('recommended_frame_duration_ms', 115)))
                self.flip_frames = int(manifest.get('frame_count_per_rune', 8))
                for entry in manifest['runes']:
                    if entry['strip'] not in anim.namelist():
                        raise ValueError('Rune animation missing: ' + entry['strip'])
                    self._flip_names[entry['rune'].lower()] = entry['strip']
        if self._consistent_assets:
            with zipfile.ZipFile(self.consistent_zip_path) as generated:
                manifest = json.loads(generated.read('manifest.json'))
                self.flip_frames = int(manifest['frame_count_per_rune'])
                self.flip_duration_ms = int(manifest['recommended_frame_duration_ms'])
                self.blank_frame_cutoff = 0  # same real rock shown from first frame
                assert self.flip_frames == 12 and len(manifest['runes']) == 24
        self._rng = secrets.SystemRandom()
        with zipfile.ZipFile(self.zip_path) as archive:
            names = set(archive.namelist())
        for rune in RUNES:
            if rune['imageFront'] not in names or rune['imageBack'] not in names:
                raise ValueError('Rune art missing: ' + rune['name'])

    def draw(self):
        return self._rng.sample(self.runes, 3)

    def close(self):
        """Release ZIP handles when the app is shutting down."""
        for archive in self._frame_archives.values():
            archive.close()
        self._frame_archives.clear()

    def __del__(self):
        # No Tk operations here; just release any open ZIP descriptors.
        try:
            self.close()
        except Exception:
            pass

    @staticmethod
    def _tk_png(master, raw):
        """Load PNG natively via Tk 8.6. No Pillow or ImageTk required."""
        return tk.PhotoImage(master=master, data=base64.b64encode(raw), format="png")

    def image_for(self, master, filename, size):
        """Fallback original 96px stones, also Pillow-free."""
        size = max(1, int(size))
        key = (filename, max(1, math.ceil(96 / size)))
        if key not in self._cache:
            with zipfile.ZipFile(self.zip_path) as archive:
                raw = archive.read(filename)
            img = self._tk_png(master, raw)
            if key[1] > 1:
                img = img.subsample(key[1])
            self._cache[key] = img
        return self._cache[key]

    NATIVE_SIZES = (24, 32, 40, 48, 56, 64, 72, 80, 88, 96, 104, 112,
                    120, 128, 144, 160, 176, 192)

    def _blank_back_for_name(self, name):
        entry = RUNE_BY_NAME.get(name.lower())
        if not entry:
            raise KeyError('Unknown rune: ' + name)
        return entry['imageBack']

    def _frame_image(self, master, archive_path, filename, key, budget):
        if key not in self._flip_cache:
            archive = self._frame_archives.get(archive_path)
            if archive is None:
                archive = zipfile.ZipFile(archive_path)
                self._frame_archives[archive_path] = archive
            raw = archive.read(filename)
            image = self._tk_png(master, raw)
            if image.width() > budget or image.height() > budget:
                sx = max(1, (image.width() + budget - 1) // budget)
                sy = max(1, (image.height() + budget - 1) // budget)
                image = image.subsample(max(sx, sy))
            self._flip_cache[key] = image
            if len(self._flip_cache) > self._flip_cache_limit:
                self._flip_cache.popitem(last=False)
        else:
            # Keep recently-used frames, particularly the currently playing
            # three-stone animation, available without another PNG decode.
            self._flip_cache.move_to_end(key)
        return self._flip_cache[key]

    def _frame_size(self, requested):
        # Return a size guaranteed to fit; never round a small budget UP.
        # The panel supplies a verified safe bounding box, so subtracting an
        # extra five pixels only forces a smaller sprite (sometimes an entire
        # size rung).  The PNG itself has its own transparent edge margin.
        budget = max(1, int(requested))
        size = max((p for p in self.NATIVE_SIZES if p <= budget), default=24)
        return budget, size

    def blank_frame(self, master, size):
        """The SAME back image as the flip's first frame, even before a draw."""
        budget, px = self._frame_size(size)
        if self._consistent_assets:
            return self._frame_image(master, self.consistent_zip_path,
                   f'{px}/blank.png', ('blank', px, budget if budget < px else None), budget)
        return self.image_for(master, '01-blank.png', budget)

    def flip_frame(self, master, rune_name, frame, size):
        """Tk-only matched 12-frame axis flip; zero runtime Pillow dependency.

        Frame 0 is the exact same stone as the initial back and frame 11 has
        the same rock texture and outline with a carved rune. Frames 1..5
        narrow the back to an edge; frames 6..11 widen the front with no
        prematurely exposed glyph.
        """
        name = rune_name.lower()
        name = {'berkano': 'berkana'}.get(name, name)
        frame = max(0, min(self.flip_frames - 1, int(frame)))
        budget, px = self._frame_size(size)
        key = (name, frame, px, budget if budget < px else None)
        if self._consistent_assets:
            return self._frame_image(master, self.consistent_zip_path,
                       f'{px}/{rune_name.lower()}/{frame:02}.png', key, budget)
        if frame < self.blank_frame_cutoff:
            return self.image_for(master, self._blank_back_for_name(rune_name), budget)
        if not self._native_assets:
            raise FileNotFoundError('Rune animation archive missing: ' + self.native_zip_path)
        return self._frame_image(master, self.native_zip_path,
                   f'{px}/{name}/{frame:02}.png', key, budget)

    def interpret(self, rune, position):
        key = ', '.join(rune['keywords'])
        if position == 0:
            return (f"PAST / {rune['name']}: {key}. Consider where these themes have "
                    "appeared before and what you may carry forward from them.")
        if position == 1:
            return (f"PRESENT / {rune['name']}: {key}. Notice whether these ideas "
                    "describe a choice, circumstance, or feeling in your life now.")
        return (f"POSSIBLE FUTURE / {rune['name']}: {key}. Explore how these "
                "themes might develop if the present direction continues; this is not a prediction.")

    def synthesis(self, runes):
        a,b,c = [r['name'] for r in runes]
        return (f"Together: {a} suggests context, {b} the current focus, and {c} "
                "a possible direction. Use the reading for reflection, not certainty.")
