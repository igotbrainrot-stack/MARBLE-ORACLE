"""Reference adapter for Marble Oracle Pass 12. Copy into app and opt in explicitly.

Replaces only the legacy nixie_frames function in oracle_nixie.py; existing
NixieState and bezel geometry stay intact. Loads the fixed shell and overlays.
"""
from pathlib import Path
import io
from PIL import Image, ImageEnhance

_DIR = Path(__file__).resolve().parent / 'data' / 'nixie_layers'
_SOURCES = {}

def _source(digit):
    digit = str(digit)
    if digit not in '0123456789' or len(digit) != 1:
        raise ValueError('Nixie digit must be 0 through 9')
    if not _SOURCES:
        with Image.open(_DIR / 'nixie_shell_base.png') as im:
            _SOURCES['shell'] = im.convert('RGBA')
        for d in '0123456789':
            with Image.open(_DIR / f'digit_{d}.png') as im:
                _SOURCES[d] = im.convert('RGBA')
    return _SOURCES['shell'], _SOURCES[digit]

def layered_nixie_frames(digit, width, height, steps=9):
    """Return PNG bytes matching oracle_nixie.nixie_frames output contract.

    Resizing shell and overlay ONCE per digit and varying ONLY overlay light.
    Avoid applying legacy whole-frame orange-pixel recoloring or lead fades.
    """
    shell, overlay = _source(digit)
    size=(max(8,int(width)),max(8,int(height)))
    shell=shell.resize(size,Image.Resampling.LANCZOS)
    overlay=overlay.resize(size,Image.Resampling.LANCZOS)
    n=max(2,int(steps))
    result=[]
    for i in range(n):
        level=i/(n-1)
        alpha_gain=0.82+0.18*level
        brightness=0.92+0.08*level
        rgb=ImageEnhance.Brightness(overlay.convert('RGB')).enhance(brightness)
        r,g,b=rgb.split()
        a=overlay.getchannel('A').point(lambda v:round(v*alpha_gain))
        overlay_frame=Image.merge('RGBA',(r,g,b,a))
        im=shell.copy()
        im.alpha_composite(overlay_frame)
        buf=io.BytesIO()
        im.save(buf,format='PNG',optimize=True)
        result.append(buf.getvalue())
    return result
