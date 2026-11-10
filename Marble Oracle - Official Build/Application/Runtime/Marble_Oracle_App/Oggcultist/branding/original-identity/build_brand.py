#!/usr/bin/env python3
"""Rebuild Oggcultist approved assets from the vector outlines in this folder.

Requires Pillow and cairosvg during asset development only. Does not regenerate fonts.
The approved user logo artwork is path-based; never replace it with the old Stone Knot.
"""
from __future__ import annotations
import io
from pathlib import Path
from PIL import Image
import cairosvg

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RESOURCE = ROOT / 'oggcultist' / 'resources'


def image(name: str, width: int, height: int, colour: str) -> Image.Image:
    svg = (HERE / name).read_text(encoding='utf-8').replace('#080808', colour)
    data = cairosvg.svg2png(bytestring=svg.encode(), output_width=width, output_height=height)
    return Image.open(io.BytesIO(data)).convert('RGBA')


def icon(size: int) -> Image.Image:
    bg = Image.new('RGBA', (size, size), '#1D1714')
    width, height = round(size*.80), round(size*.85)
    mark = image('symbol.svg', width, height, '#F2E8DE')
    bg.alpha_composite(mark, ((size-width)//2, (size-height)//2))
    return bg


def main() -> None:
    RESOURCE.mkdir(parents=True,exist_ok=True)
    image('symbol.svg',700,733,'#F2E8DE').save(RESOURCE/'brand_symbol.png')
    image('wordmark-outlined.svg',1255,235,'#F2E8DE').save(RESOURCE/'brand_wordmark.png')
    for size in (16,24,32,48,64,128,256,512,1024):
        im = icon(size)
        im.save(HERE/f'icon-{size}.png')
        if size in (16,32,48):im.save(RESOURCE/f'icon-{size}.png')
        if size==256:im.save(RESOURCE/'icon.png')
    icon(1024).save(RESOURCE/'icon.ico',format='ICO',sizes=[(s,s) for s in (16,24,32,48,64,128,256)])
    print('Approved triple-G logo assets regenerated')

if __name__ == '__main__':main()
