"""CRT glass / barrel-curvature cues, using only stdlib PNGs + Tk.

The overlays are clipped to the display aperture and never paint over the bezel.
Tk still cannot apply a true pixel shader to live Canvas content, so the barrel
look is an optical effect: curved edge falloff, stronger corner shading and a
broad moving reflection that together make the live dashboard sit deeper in the
rounded glass.
"""
import math
from functools import lru_cache
from oracle_assets import rgba_png



def convex_warp(x, y, w, h, strength=0.12):
    """Map a point inside the aperture to its convex-CRT position.
    strength > 0 bows edges outward (convex). Matches the photographic glass curve.
    """
    if w < 2 or h < 2:
        return x, y
    nx = (x / (w - 1) - 0.5) * 2.0
    ny = (y / (h - 1) - 0.5) * 2.0
    r2 = nx * nx + ny * ny
    # Outward barrel: edges move further from center
    f = 1.0 + strength * r2
    return (nx * f * 0.5 + 0.5) * (w - 1), (ny * f * 0.5 + 0.5) * (h - 1)

def edge_png(vertical=True, width=32, reverse=False):
    """Transparent neutral-black glass falloff, fading fully to zero inward."""
    rows=[]
    w,h=(width,1) if vertical else (1,width)
    for y in range(h):
        row=bytearray()
        for x in range(w):
            d=(x if vertical else y)/(width-1)
            if reverse:d=1-d
            alpha=round(58*(1-d)**2.15)
            row.extend((4,9,15,alpha))
        rows.append(bytes(row))
    return rgba_png(w,h,rows)


@lru_cache(maxsize=4)
def barrel_png(width, height, strength=1.48):
    """Soft optical CRT bulge with stronger curved corners but clear centre.

    A translucent depth vignette; this does NOT remap live Tk Canvas pixels.
    LRU cache avoids regenerating a several-megabyte PNG during UI rebuilds.
    """
    if width < 2 or height < 2:
        raise ValueError('glass dimensions must be at least 2x2')
    strength = max(0.5, min(1.9, float(strength)))
    cx=(width-1)/2.0; cy=(height-1)/2.0
    rx=max(1.0,cx); ry=max(1.0,cy)
    rows=[]
    for y in range(height):
        row=bytearray()
        ny=abs((y-cy)/ry)
        for x in range(width):
            nx=abs((x-cx)/rx)
            # CRT shoulder: flat bright central region, rolled-off edges, and
            # a darkened diagonal recess where curved glass meets its gasket.
            edge=max(nx**2.8,ny**2.6)
            diagonal=nx*nx+ny*ny
            shoulder=max(0.0,(edge-.57)/.43)
            corner=max(0.0,(diagonal-.93)/.92)
            # The centre stays transparent enough for legibility while the
            # edges and corners sink further into the curved tube.
            opacity=min(148,round(strength*(16*shoulder**1.55 + 64*corner**1.85)))
            row.extend((3,8,14,opacity))
        rows.append(bytes(row))
    return rgba_png(width,height,rows)


def sweep_png(width=128,height=384):
    """Wide soft glass reflection with faint blue-white angled highlights."""
    rows=[]
    for y in range(height):
        row=bytearray()
        for x in range(width):
            pos=x/float(width-1)-0.15*(y/float(height-1)-.5)
            strength=max(0,1-abs(pos-.50)/.50)
            a=int(38*strength**2 * (0.28+0.72*math.sin(math.pi*y/(height-1))**2))
            row.extend((180,222,241,a))
        rows.append(bytes(row))
    return rgba_png(width,height,rows)


def silhouette_png(width=94,height=173):
    """A dim anonymous viewer shadow; no identifying characteristics."""
    rows=[]
    for y in range(height):
        row=bytearray()
        for x in range(width):
            # head, neck and shoulders, with soft 3px edge
            head=((x-width*.53)/(width*.21))**2+((y-height*.26)/(height*.22))**2
            shoulders=((x-width*.51)/(width*.45))**2+((y-height*.95)/(height*.40))**2
            neck=abs(x-width*.52)<width*.14 and height*.39<y<height*.70
            val=max(0,min(1,(1.05-head)*5),min(1,(1.06-shoulders)*5),0.6 if neck else 0)
            row.extend((7,12,16,int(30*val)))
        rows.append(bytes(row))
    return rgba_png(width,height,rows)

@lru_cache(maxsize=3)
def curved_screen_png(width, height):
    """Rounded CRT aperture shading with broader usable corner area.

    This darkens only the extreme glass shoulders and corner recesses, letting
    live content extend much nearer to the bezel corners than before.
    """
    if width < 80 or height < 60:
        raise ValueError('screen too small')
    rows=[]
    for y in range(height):
        ny=abs((y+.5-height/2)/(height/2))
        inset_x=.4 + min(11., width*.012) * (ny**3.75)
        buf=bytearray()
        for x in range(width):
            nx=abs((x+.5-width/2)/(width/2))
            inset_y=.4 + min(12., height*.022) * (nx**3.65)
            clearance=min(x-inset_x, width-1-x-inset_x,
                          y-inset_y, height-1-y-inset_y)
            if clearance < 0:
                opacity=round(196 * min(1., max(0., -clearance/3.2 + .52)))
            elif clearance < 14:
                opacity=round(52 * ((14-clearance)/14)**2.1)
            else:
                opacity=0
            buf.extend((2,7,12,opacity))
        rows.append(bytes(buf))
    return rgba_png(width,height,rows)


def scan_beam_png(width=968, height=96):
    """Feathered phosphor refresh beam, brighter at its horizontal centre."""
    rows=[]
    for y in range(height):
        pos=(y/(height-1)-.5)*2
        main=max(0., 1-abs(pos))**2.5
        stripe=max(0., 1-abs(pos-.13)*13)**2
        a=round(22*main+10*stripe)
        rows.append(bytes((52,189,204,a))*width)
    return rgba_png(width,height,rows)

@lru_cache(maxsize=3)
def convex_glass_png(width, height):
    """Stable, stationary convex-tube illumination (no screen capture).

    A translucent cool central bulge with narrow curved shoulder reflections.
    Centre remains almost transparent so text is readable.
    """
    if width < 80 or height < 60:
        raise ValueError('screen too small')
    rows=[]
    for y in range(height):
        ny=(y+.5-height*.5)/(height*.5)
        row=bytearray()
        for x in range(width):
            nx=(x+.5-width*.5)/(width*.5)
            r2=nx*nx+ny*ny
            centre=max(0,1-r2)**2
            # The vertical reflections curve in as they approach corners.
            shoulder=max(0,1-abs(abs(nx)-(.78-.14*ny*ny))/.095)**2
            light=int(min(20, 4*centre + 15*shoulder*(.55+.45*max(0,-ny))))
            row.extend((91,180,207,light))
        rows.append(bytes(row))
    return rgba_png(width,height,rows)
