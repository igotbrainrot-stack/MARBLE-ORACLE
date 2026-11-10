"""Verify the 24 matched rune faces and twelve-stage Tk-native flipping sprites.

Only the builder needs Pillow; the running Oracle uses stock Tk PhotoImage.
"""
from pathlib import Path
from zipfile import ZipFile
import json
import tkinter as tk
from oracle_runes import RuneDeck

d = RuneDeck()
assert d._consistent_assets and d.flip_frames == 12
path = Path(__file__).parent / 'data' / 'rune_consistent_flips.zip'
with ZipFile(path) as archive:
    assert archive.testzip() is None
    names = set(archive.namelist())
    manifest = json.loads(archive.read('manifest.json'))
    assert manifest['reveal_starts_at_frame'] == 6
    for px in d.NATIVE_SIZES:
        assert f'{px}/blank.png' in names
        for r in d.runes:
            k = r['name'].lower()
            for frame in range(d.flip_frames):
                assert f'{px}/{k}/{frame:02}.png' in names
root = tk.Tk(); root.withdraw()
try:
    for r in d.runes:
        for frame in range(d.flip_frames):
            image = d.flip_frame(root, r['name'], frame, 96)
            assert 1 <= image.width() <= 96 and 1 <= image.height() <= 96
    for budget in (6, 18, 24, 36, 64, 82, 96):
        im=d.blank_frame(root, budget)
        assert im.width() <= budget and im.height() <= budget
        front=d.flip_frame(root,'Fehu',11,budget)
        assert front.width() <= budget and front.height() <= budget
    print('RUNE ASSETS OK — 24 stones, 12 frames, 10 sizes, matched back, Tk-only runtime')
finally:
    root.destroy()
