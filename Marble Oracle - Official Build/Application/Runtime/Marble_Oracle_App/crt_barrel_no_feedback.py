"""Safe CRT post-process: warp ONE fresh, unmodified UI image per frame.

Dependencies: pip install numpy opencv-python

The caller MUST:
  1. Render the CRT screen contents (not the case, not the prior output) to a
     separate offscreen RGB/RGBA buffer on EVERY frame.
  2. Call CRTBarrel.apply(source) exactly once on that source buffer.
  3. Composite the returned image into the screen aperture.
  4. Draw the case/bezel/knobs/buttons AFTER the warped screen.

RGB and RGBA inputs use RGB channel order (NOT OpenCV BGR).
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import cv2
import numpy as np


# The photograph's glass is a curve, not a rectangle. These are the fractions
# of the dashboard the metal covers: left, top, right, bottom. The picture is
# seated inside that opening, so the corners are bent in rather than cut off.
GLASS_FIT = (0.078, 0.148, 0.078, 0.072)


@dataclass(frozen=True)
class CRTConfig:
    # With normalized radius-squared, 0.035 is intentionally mild.
    strength: float = 0.035
    vignette: float = 0.12
    scanlines: float = 0.035
    scanline_period: float = 3.0
    chromatic_pixels: float = 0.0   # keep off until geometry looks right
    bloom: float = 0.0              # keep off until geometry looks right


class CRTBarrel:
    def __init__(self, width: int, height: int, config: CRTConfig = CRTConfig()):
        self.w = int(width)
        self.h = int(height)
        self.cfg = config
        if self.w < 2 or self.h < 2:
            raise ValueError('CRT viewport width and height must be at least 2')
        if not 0 <= config.strength <= 0.12:
            raise ValueError('For this formula, strength should be between 0 and 0.12')
        if not 0 <= config.vignette <= 1 or not 0 <= config.scanlines <= 1:
            raise ValueError('vignette and scanlines must be in [0,1]')
        if config.chromatic_pixels < 0 or config.bloom < 0:
            raise ValueError('chroma and bloom must be nonnegative')
        if config.scanline_period <= 0:
            raise ValueError('scanline_period must be positive')

        xs = np.linspace(-1, 1, self.w, dtype=np.float32)
        ys = np.linspace(-1, 1, self.h, dtype=np.float32)
        x, y = np.meshgrid(xs, ys)
        self.x, self.y = x, y
        left, top, right, bottom = GLASS_FIT
        safe_x0, safe_x1 = -1 + 2 * left, 1 - 2 * right
        safe_y0, safe_y1 = -1 + 2 * top, 1 - 2 * bottom
        u = np.clip((x - safe_x0) / (safe_x1 - safe_x0), 0, 1)
        v = np.clip((y - safe_y0) / (safe_y1 - safe_y0), 0, 1)
        nx = u * 2 - 1
        ny = v * 2 - 1
        r2 = (nx * nx + ny * ny) / 2.0
        # Bend inside the glass. Clamp so the bend cannot sample off the picture.
        scale = 1.0 + config.strength * r2
        nx = np.clip(nx * scale, -1, 1)
        ny = np.clip(ny * scale, -1, 1)
        self.map_x = np.ascontiguousarray((nx + 1) * (self.w - 1) / 2)
        self.map_y = np.ascontiguousarray((ny + 1) * (self.h - 1) / 2)

        edge_falloff = np.clip(1 - config.vignette * (r2 ** 1.4), 0, 1)
        rows = np.arange(self.h, dtype=np.float32)[:, None]
        line_wave = (1 - np.cos(rows * 2 * np.pi / config.scanline_period)) * 0.5
        self.shading = np.ascontiguousarray(
            (edge_falloff * (1 - config.scanlines * line_wave))[:, :, None]
        )
        self.chroma_dx = config.chromatic_pixels * r2 * x
        self.chroma_dy = config.chromatic_pixels * r2 * y

    def apply(self, source: np.ndarray) -> np.ndarray:
        """Warp one FRESH source image; returns a new RGB/RGBA uint8 array.

        Calling this repeatedly with a constant source gives an identical output.
        NEVER pass the previous result into the next call.
        """
        if (source.shape != (self.h, self.w, 3)
                and source.shape != (self.h, self.w, 4)) or source.dtype != np.uint8:
            raise ValueError(f'Expected RGB/RGBA uint8 image of shape {(self.h, self.w)} + 3/4')

        rgb = np.ascontiguousarray(source[:, :, :3])
        # Never BORDER_WRAP or repeat: those cause mirrored/recursive-looking edges.
        pixels = cv2.remap(rgb, self.map_x, self.map_y, cv2.INTER_LINEAR,
                           borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0))
        cfg = self.cfg
        if cfg.chromatic_pixels:
            red = cv2.remap(rgb[:, :, 0], self.map_x + self.chroma_dx,
                            self.map_y + self.chroma_dy, cv2.INTER_LINEAR,
                            borderMode=cv2.BORDER_CONSTANT, borderValue=0)
            blue = cv2.remap(rgb[:, :, 2], self.map_x - self.chroma_dx,
                             self.map_y - self.chroma_dy, cv2.INTER_LINEAR,
                             borderMode=cv2.BORDER_CONSTANT, borderValue=0)
            pixels[:, :, 0] = red
            pixels[:, :, 2] = blue
        lit = pixels.astype(np.float32)
        if cfg.bloom:
            blurred = cv2.GaussianBlur(lit, (0, 0), 1.4)
            # avoid spreading black corners into a huge glow
            lit += cfg.bloom * np.maximum(blurred - 100.0, 0)
        lit *= self.shading
        warped_rgb = np.clip(lit, 0, 255).astype(np.uint8)
        if source.shape[2] == 3:
            return warped_rgb
        alpha = cv2.remap(source[:, :, 3], self.map_x, self.map_y,
                          cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
        return np.dstack((warped_rgb, alpha))

    def display_to_ui(self, local_x: float, local_y: float) -> tuple[float, float] | None:
        """Map a click on the curved glass back to the flat dashboard."""
        xn = 2 * local_x / (self.w - 1) - 1
        yn = 2 * local_y / (self.h - 1) - 1
        left, top, right, bottom = GLASS_FIT
        safe_x0, safe_x1 = -1 + 2 * left, 1 - 2 * right
        safe_y0, safe_y1 = -1 + 2 * top, 1 - 2 * bottom
        u = min(1.0, max(0.0, (xn - safe_x0) / (safe_x1 - safe_x0)))
        v = min(1.0, max(0.0, (yn - safe_y0) / (safe_y1 - safe_y0)))
        nx, ny = u * 2 - 1, v * 2 - 1
        scale = 1 + self.cfg.strength * ((nx * nx + ny * ny) / 2)
        nx = min(1.0, max(-1.0, nx * scale))
        ny = min(1.0, max(-1.0, ny * scale))
        return (nx + 1) * (self.w - 1) / 2, (ny + 1) * (self.h - 1) / 2


@lru_cache(maxsize=16)
def rounded_aperture(width: int, height: int, radius: int, feather: float = 3.0) -> np.ndarray:
    """Return 0..1 aperture opacity; reuse when window geometry unchanged."""
    w, h = width, height
    r = min(max(int(radius), 0), (w-1)//2, (h-1)//2)
    mask = np.zeros((h, w), np.uint8)
    if r == 0:
        mask[:] = 255
    else:
        cv2.rectangle(mask, (r, 0), (w-r-1, h-1), 255, -1)
        cv2.rectangle(mask, (0, r), (w-1, h-r-1), 255, -1)
        for cx, cy in ((r, r), (w-1-r, r), (r, h-1-r), (w-1-r, h-1-r)):
            cv2.circle(mask, (cx, cy), r, 255, -1, lineType=cv2.LINE_AA)
    if feather > 0:
        mask = cv2.GaussianBlur(mask, (0, 0), feather)
    return (mask.astype(np.float32) / 255.0)


def preview_on_screenshot(screenshot: np.ndarray, rect: tuple[int, int, int, int],
                          cfg: CRTConfig = CRTConfig(), corner_radius: int = 55,
                          feather: float = 3) -> np.ndarray:
    """Diagnostic preview only. For real-time app, use its offscreen source instead.

    Outputs preserved screenshot with fresh single-pass processing inside rect.
    Allows RGB/RGBA screenshots; does NOT repair already-recursive screen content.
    """
    x, y, w, h = rect
    if x < 0 or y < 0 or w < 2 or h < 2 or x+w > screenshot.shape[1] or y+h > screenshot.shape[0]:
        raise ValueError('CRT glass rectangle is outside input screenshot')
    original = screenshot[y:y+h, x:x+w].copy()
    warped = CRTBarrel(w, h, cfg).apply(original)
    mask = rounded_aperture(w, h, corner_radius, feather)[:, :, None]
    composed = original.astype(np.float32) * (1.0-mask) + warped.astype(np.float32) * mask
    result = screenshot.copy()
    result[y:y+h, x:x+w] = np.clip(composed, 0, 255).astype(np.uint8)
    return result


if __name__ == '__main__':
    import argparse
    from PIL import Image
    ap = argparse.ArgumentParser(description='CRT screen-only single-pass preview')
    ap.add_argument('--input', required=True)
    ap.add_argument('--output', required=True)
    ap.add_argument('--rect', nargs=4, type=int, required=True, metavar=('X','Y','W','H'))
    ap.add_argument('--strength', type=float, default=0.035)
    args = ap.parse_args()
    im = np.asarray(Image.open(args.input).convert('RGB'))
    result = preview_on_screenshot(im, tuple(args.rect), CRTConfig(strength=args.strength))
    Image.fromarray(result, 'RGB').save(args.output)
