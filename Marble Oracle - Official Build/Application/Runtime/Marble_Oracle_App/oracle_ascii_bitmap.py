"""Pixel-crisp bitmap rasterizer for the PLATE VAULT ASCII sculptures.

The original archive stores high-detail ASCII characters and luminance bands,
not RGB artwork.  Previously each character was passed individually to Tk as
3-pixel-high antialiased Uberata text; strokes became almost invisible at the
HOME panel's actual resolution.  At this size an intentional 3x5 pixel grid is
more faithful to the *visible* source characters than trying to hint a vector
font at a fractional glyph width. No new resource assets or network needed.

Only the ASCII artwork uses this micro bitmap representation; every ordinary
interface label continues to use the project's bundled Uberata Clear font.
"""
from __future__ import annotations
import io
from PIL import Image

# A 3x5 micro-ASCII alphabet. Keep the individual character identities and
# relative ink coverage: sparse punctuation vs medium and dense ASCII glyphs.
# The last row in the 6px cell remains transparent as a line gap.
MICRO = {
    '.': ('000','000','000','000','010'),
    ',': ('000','000','000','010','100'),
    ':': ('000','010','000','010','000'),
    ';': ('000','010','000','010','100'),
    '-': ('000','000','111','000','000'),
    '=': ('000','111','000','111','000'),
    '+': ('000','010','111','010','000'),
    '*': ('101','010','111','010','101'),
    '#': ('101','111','101','111','101'),
    '%': ('101','001','010','100','101'),
    '@': ('111','101','111','110','111'),
}

# Muted, opaque limestone shades against the genuine dark sidebar texture.
# The bitmap still uses full-alpha strokes; only RGB brightness is reduced.
# This prevents glare without reintroducing faint antialiasing or washout.
INKS = ('#675E57', '#766C63', '#857A70', '#94887C', '#A39789',
        '#B1A597', '#BDB1A2', '#C6BAAA', '#CDC1B0', '#D3C8B8')


def render(statue, plate, frame, cell_w, cell_h):
    """Return transparent PNG of one plate frame, sized exactly to its grid.

    `statue.runs()` already resolves the source glyph's brightness band. The
    bitmap draws strokes in full opacity so the display renderer cannot turn
    a tiny period or dash into a nearly transparent blur.
    """
    cols, rows = statue.dims(plate)
    width, height = max(1, cols * cell_w), max(1, rows * cell_h)
    im = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    pix = im.load()
    for row, col, source, band in statue.runs(plate, frame):
        if row >= rows:
            continue
        colour = tuple(int(INKS[band][i:i+2], 16) for i in (1,3,5)) + (255,)
        for offset, glyph in enumerate(source):
            xx = (col + offset) * cell_w
            yy = row * cell_h
            pattern = MICRO.get(glyph, MICRO['#'])
            if xx >= width:
                continue
            # A micro glyph scales to each cell without interpolation or
            # low-alpha downsampling. Retain one clean pixel of letter spacing
            # unless the output cell is only 2px wide.
            sy = max(1, min(5, cell_h - 1))
            inked = False
            for py in range(sy):
                # Always sample the glyph's bottom row even in a small panel;
                # otherwise tiny periods and commas disappear at 4-5px cells.
                pattern_y = 4 if sy == 1 else round(py * 4 / (sy - 1))
                for px in range(cell_w):
                    pattern_x = min(2, (px * 3) // cell_w)
                    if pattern[pattern_y][pattern_x] == '1':
                        if yy + py < height and xx + px < width:
                            pix[xx+px, yy+py] = colour
                            inked = True
            if not inked and yy < height:
                pix[min(width-1, xx + cell_w//2), min(height-1, yy + sy-1)] = colour
    out = io.BytesIO()
    im.save(out, format='PNG', optimize=False)
    return out.getvalue()
