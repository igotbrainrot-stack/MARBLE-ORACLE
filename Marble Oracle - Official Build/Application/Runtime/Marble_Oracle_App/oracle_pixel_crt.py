"""Live barrel bend for the dashboard only.

The last build photographed the window after the bent picture had already been
drawn into it, then bent that photograph again. The rectangles nested and the
middle smeared. This file bends one fresh drawing of the dashboard, once.
The metal case is not in that drawing.

The fresh drawing is made by hiding the previous bend and asking the canvas to
paint into a bitmap. The screen is locked while that happens, so the flat
dashboard is never shown. The visible window is not photographed.
"""
from __future__ import annotations

import math
import os
import time
import traceback


# One geometry governs the Pillow mesh, OpenCV remap, and mouse hit-testing.
# Earlier builds used a different OpenCV formula, making the supposedly more
# extreme barrel distortion appear unchanged whenever acceleration was present.
DEFAULT_STRENGTH = 0.62


def source_at(x: float, y: float, width: int, height: int,
              strength: float = DEFAULT_STRENGTH):
    """Inverse CRT barrel map: output coordinate -> live Tk Canvas source.

    The projection bows horizontal and vertical elements together. Source
    coordinates remain inside the live screen, including all four corners;
    there are no black sampling gaps. The near-centre distortion is small so
    text and buttons remain usable while outer shoulders curve dramatically.
    """
    cx, cy = width * .5, height * .5
    nx = (x - cx) / max(1., cx)
    ny = (y - cy) / max(1., cy)
    radial = min(1.0, (nx * nx + ny * ny) / 1.70)
    bend = strength * (.15 + .45 * radial)
    sx = cx + (x - cx) * (1.0 - bend * (.72 * ny * ny + .28 * radial))
    sy = cy + (y - cy) * (1.0 - bend * (.72 * nx * nx + .28 * radial))
    return (max(0., min(width - 1., sx)),
            max(0., min(height - 1., sy)))


def remap_arrays(np, width: int, height: int,
                 strength: float = DEFAULT_STRENGTH):
    """Vectorized exact equivalent of source_at, cached by PixelCRT per size."""
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    cx, cy = width * .5, height * .5
    nx, ny = (xx - cx) / max(1., cx), (yy - cy) / max(1., cy)
    radial = np.minimum(1.0, (nx * nx + ny * ny) / 1.70)
    bend = strength * (.15 + .45 * radial)
    sx = cx + (xx - cx) * (1.0 - bend * (.72 * ny * ny + .28 * radial))
    sy = cy + (yy - cy) * (1.0 - bend * (.72 * nx * nx + .28 * radial))
    return (np.clip(sx, 0, width - 1).astype(np.float32),
            np.clip(sy, 0, height - 1).astype(np.float32))


def barrel_mesh(width: int, height: int, strength=DEFAULT_STRENGTH, steps=28):
    """Build a Pillow MESH transform with smooth radial mapping and straight tiles.

    Each output rectangle maps to a source quad. All six coordinates use one
    formula and shared vertices, avoiding visible seams between tiles.
    """
    cols = max(4, min(32, round(width / max(18, width / steps))))
    rows = max(4, min(24, round(height / max(18, height / (steps * .65)))))
    xs = [round(i*width/cols) for i in range(cols+1)]
    ys = [round(i*height/rows) for i in range(rows+1)]
    mesh = []
    for j in range(rows):
        for i in range(cols):
            x0, x1, y0, y1 = xs[i], xs[i+1], ys[j], ys[j+1]
            # Pillow QUAD point order: top-left, bottom-left, bottom-right, top-right.
            quad = (*source_at(x0,y0,width,height,strength),
                    *source_at(x0,y1,width,height,strength),
                    *source_at(x1,y1,width,height,strength),
                    *source_at(x1,y0,width,height,strength))
            mesh.append(((x0,y0,x1,y1), quad))
    return mesh


class PixelCRT:
    """Bends the live dashboard and leaves the metal bezel alone.

    The picture is a new paint of the canvas, with the previous bend hidden.
    crt_barrel_no_feedback.CRTBarrel runs once on that paint.
    """

    def __init__(self, app, settings=None, target_fps=12):
        from PIL import Image, ImageTk
        import numpy as np
        from crt_barrel_no_feedback import CRTBarrel, CRTConfig
        self.Image = Image
        self.ImageTk = ImageTk
        self.np = np
        self.CRTBarrel = CRTBarrel
        self.settings = settings or CRTConfig()
        self.app = app
        self.interval = 1.0 / max(1, target_fps)
        self._filter = None
        self.item = None
        self.photo = None
        self.last = 0.0
        self.size = (0, 0)
        self.errors = 0
        self._last_out = None

    def reset(self):
        self._filter = None
        self.photo = None
        self.item = None
        self.size = (0, 0)
        self.last = 0.0
        self._last_out = None

    def hit_source(self, ex, ey):
        """A click on the curved glass, mapped back to the flat dashboard."""
        scene = self.app.scene
        filt = getattr(self, '_filter', None)
        if filt is not None and filt.w == scene.W and filt.h == scene.H:
            if 0 <= ex < scene.W and 0 <= ey < scene.H:
                which = getattr(scene, '_which_overlay', None)
                if which is not None and which() is not None:
                    return ex, ey
                point = filt.display_to_ui(ex, ey)
                if point is not None:
                    return point
            return ex, ey
        if 0 <= ex < scene.W and 0 <= ey < scene.H:
            return source_at(ex, ey, scene.W, scene.H, getattr(self, 'strength', DEFAULT_STRENGTH))
        return ex, ey

    def tick(self):
        a = self.app
        scene, c = a.scene, a.canvas
        if (not scene.case_on() or not scene.W or not scene.H
                or getattr(scene, 'crt_off', False)
                or not c.winfo_viewable()):
            self.hide()
            return
        now = time.perf_counter()
        if now - self.last < self.interval:
            return
        self.last = now
        width, height = int(scene.W), int(scene.H)
        if self.size != (width, height) or self._filter is None:
            self.size = (width, height)
            self._filter = self.CRTBarrel(width, height, self.settings)
            self._last_out = None
        locked = _redraw(c, False) if os.name == 'nt' else False
        hidden = []
        try:
            # The previous bend is a picture on this same canvas. It has to be
            # hidden before the paint, or the next bend will bend it again.
            for tag in ('bezel', 'pixel-crt', 'crt', 'glare',
                        'overlaywin', 'dkwin', 'chrome', 'popup'):
                for item in c.find_withtag(tag):
                    hidden.append((item, c.itemcget(item, 'state')))
                    c.itemconfigure(item, state='hidden')
            # The window is not allowed to draw (WM_SETREDRAW), so this refresh
            # does not flash the flat dashboard.
            c.update_idletasks()
            image = _grab_fresh(c)
            if image is None:
                raise RuntimeError('the screen could not be read')
            ww, wh = c.winfo_width(), c.winfo_height()
            if image.size != (ww, wh) and ww > 1 and wh > 1:
                image = image.resize((ww, wh), self.Image.Resampling.BILINEAR)
            left, top = int(scene.mg[0]), int(scene.mg[1])
            crop = image.crop((left, top, left + width, top + height)).convert('RGB')
            if crop.size != (width, height):
                return
            source = self.np.asarray(crop)
            if self._last_out is not None and _same_picture(source, self._last_out):
                # This paint is the previous result. Bending it again is the
                # nested-screen fault. Keep the picture we already have.
                return
            warped = self._filter.apply(source)
            self._last_out = warped
            self.photo = self.ImageTk.PhotoImage(
                self.Image.fromarray(warped), master=c)
            if self.item is None:
                self.item = c.create_image(0, 0, image=self.photo, anchor='nw', tags='pixel-crt')
            else:
                c.itemconfigure(self.item, image=self.photo, state='normal')
            for tag in ('glare', 'overlaywin', 'dkwin', 'chrome', 'popup', 'bezel'):
                c.tag_raise(tag)
            self.errors = 0
        except Exception:
            self.errors += 1
            self.hide()
            if self.errors >= 3:
                details = traceback.format_exc()
                try:
                    from pathlib import Path
                    from oracle_assets import state_dir
                    Path(state_dir()).mkdir(parents=True, exist_ok=True)
                    (Path(state_dir()) / 'crt_pixel_error.log').write_text(details, encoding='utf-8')
                except Exception:
                    pass
                a.pixel_crt = None
        finally:
            for item, state in hidden:
                try:
                    c.itemconfigure(item, state=state or 'normal')
                except Exception:
                    pass
            if locked:
                _redraw(c, True)

    def hide(self):
        if self.item is not None:
            try:
                self.app.canvas.itemconfigure(self.item, state='hidden')
            except Exception:
                pass


def _redraw(widget, on):
    """Stop or start the window painting. Used so a hidden bend is not a flash."""
    import ctypes
    try:
        user32 = ctypes.windll.user32
        hwnd = int(widget.winfo_id())
        user32.SendMessageW(hwnd, 0x000B, 1 if on else 0, 0)  # WM_SETREDRAW
        if on:
            user32.RedrawWindow(hwnd, None, None, 0x0001 | 0x0100 | 0x0080)
        return True
    except Exception:
        return False


def _same_picture(a, b):
    """True only when the new paint is the previous bent frame, not a new dashboard."""
    if a.shape != b.shape:
        return False
    step = max(1, a.shape[0] // 24)
    diff = abs(a[::step, ::step].astype('int16') - b[::step, ::step].astype('int16'))
    return float(diff.mean()) < 0.4


def _grab_fresh(widget):
    """A new paint of the widget. Never a photograph of the visible screen on Windows."""
    width, height = widget.winfo_width(), widget.winfo_height()
    if width < 2 or height < 2:
        return None
    if os.name == 'nt':
        return _print_window(widget.winfo_id(), width, height)
    from PIL import ImageGrab
    widget.update_idletasks()
    x, y = widget.winfo_rootx(), widget.winfo_rooty()
    return ImageGrab.grab(bbox=(x, y, x + width, y + height), all_screens=True)


def _print_window(hwnd, width, height):
    """Ask the widget to paint into a bitmap. Flag 2 is not used: it copies the screen."""
    import ctypes
    from ctypes import wintypes
    from PIL import Image
    user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32
    hwnd = int(hwnd)
    hdc = user32.GetDC(hwnd)
    if not hdc:
        return None
    mem = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, width, height)
    old = gdi32.SelectObject(mem, bmp)
    user32.SendMessageW(hwnd, 0x0317, mem, 0x0002 | 0x0008 | 0x0010)
    image = _bitmap(gdi32, mem, bmp, width, height)
    if image is None:
        # A plain print. Not flag 2, which copies whatever is already on screen.
        user32.PrintWindow(hwnd, mem, 0)
        image = _bitmap(gdi32, mem, bmp, width, height)
    gdi32.SelectObject(mem, old)
    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(mem)
    user32.ReleaseDC(hwnd, hdc)
    return image


def _bitmap(gdi32, mem, bmp, width, height):
    import ctypes
    from ctypes import wintypes
    from PIL import Image
    class HEADER(ctypes.Structure):
        _fields_ = [
            ('biSize', wintypes.DWORD), ('biWidth', wintypes.LONG),
            ('biHeight', wintypes.LONG), ('biPlanes', wintypes.WORD),
            ('biBitCount', wintypes.WORD), ('biCompression', wintypes.DWORD),
            ('biSizeImage', wintypes.DWORD), ('biXPelsPerMeter', wintypes.LONG),
            ('biYPelsPerMeter', wintypes.LONG), ('biClrUsed', wintypes.DWORD),
            ('biClrImportant', wintypes.DWORD),
        ]
    class INFO(ctypes.Structure):
        _fields_ = [('bmiHeader', HEADER), ('bmiColors', wintypes.DWORD * 3)]
    info = INFO()
    info.bmiHeader.biSize = ctypes.sizeof(HEADER)
    info.bmiHeader.biWidth = width
    info.bmiHeader.biHeight = height
    info.bmiHeader.biPlanes = 1
    info.bmiHeader.biBitCount = 32
    info.bmiHeader.biCompression = 0
    buf = ctypes.create_string_buffer(width * height * 4)
    rows = gdi32.GetDIBits(mem, bmp, 0, height, buf, ctypes.byref(info), 0)
    if rows == 0:
        return None
    image = Image.frombuffer('RGB', (width, height), buf, 'raw', 'BGRX', 0, -1)
    if image.getextrema() == ((0, 0), (0, 0), (0, 0)):
        return None
    return image
