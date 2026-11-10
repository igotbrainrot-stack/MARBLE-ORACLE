"""Asset-level checks for rune flip silhouette and prereveal/visible separation.

Run from any directory: python3 Application/Tests/test_rune_consistency.py
Requires Pillow for test only, not at application runtime.
"""
from pathlib import Path
from io import BytesIO
from zipfile import ZipFile
import json
from PIL import Image, ImageChops

file=Path(__file__).resolve().parents[1]/'Runtime/Marble_Oracle_App/data/rune_consistent_flips.zip'
with ZipFile(file) as z:
    manifest=json.loads(z.read('manifest.json'))
    assert manifest['frame_count_per_rune']==12
    assert len(manifest['runes'])==24
    for size in manifest['sizes']:
        blank=Image.open(BytesIO(z.read(f'{size}/blank.png'))).convert('RGBA')
        assert blank.size==(size,size)
        bbox=blank.getchannel('A').getbbox()
        assert bbox and bbox[1]>=1 and bbox[3]<size
        for rune in manifest['runes']:
            name=rune['name'].lower()
            before=Image.open(BytesIO(z.read(f'{size}/{name}/00.png'))).convert('RGBA')
            after=Image.open(BytesIO(z.read(f'{size}/{name}/11.png'))).convert('RGBA')
            assert ImageChops.difference(blank,before).getbbox() is None,(size,name,'blank mismatch')
            assert ImageChops.difference(blank.getchannel('A'),after.getchannel('A')).getbbox() is None,(size,name,'alpha mismatch')
            assert ImageChops.difference(blank.convert('RGB'),after.convert('RGB')).getbbox() is not None,(size,name,'missing carved rune')
            for frame in range(12):
                im=Image.open(BytesIO(z.read(f'{size}/{name}/{frame:02}.png')))
                assert im.size==(size,size)
print(f'RUNE CONSISTENCY OK — 24 x 12 x {len(manifest["sizes"])}; identical blank and final silhouette')
