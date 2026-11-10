"""Reusable Python CRT barrel-distortion filter for Pygame, Qt, Tkinter, etc.

The caller must render *only the screen's content* to an RGB/RGBA image, apply
this filter, then composite it BELOW the undistorted CRT bezel/hardware.

Dependencies: numpy, opencv-python, Pillow (Pillow only used for the CLI preview).

Preview of the original 1299x914 screenshot:
    python crt_barrel_filter.py --input "Screenshot 2026-10-25 003520.png" \
        --output crt_preview.png --rect 191 126 917 598

No application framework is assumed. All RGB arrays are H x W x 3 uint8;
RGBA arrays are H x W x 4 uint8. Color channel order is always RGB/RGBA.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Tuple

import cv2
import numpy as np


@dataclass(frozen=True)
class CRTSettings:
    # Lens-like geometry. 0 is flat; 0.04-0.10 is generally a realistic CRT.
    distortion: float = 0.075
    # Edge dimming, fractional amplitude at outer corners.
    vignette: float = 0.24
    # Alternating-row darkness (0 disables).
    scanlines: float = 0.075
    scanline_spacing: float = 3.0  # physical pixels at *final output resolution*
    # Maximum per-channel displacement in physical pixels, mostly at the edges.
    chromatic_pixels: float = 0.85
    bloom: float = 0.07    # modest glow from bright areas
    bloom_sigma: float = 1.7
    reflection: float = 0.035  # dim specular reflection near top of glass


class CRTBarrelFilter:
    """Cached inverse-sampling displacement map, efficient for changing frames.

    screen_to_source_point(x, y) maps a displayed, distorted screen click back to
    coordinates in the original (undistorted) UI. Keep hit-testing on the source
    UI rather than attempting to warp each widget separately.
    """

    def __init__(self, width: int, height: int, settings: CRTSettings | None = None):
        if width < 2 or height < 2:
            raise ValueError('Screen resolution must be at least 2x2')
        self.width, self.height = int(width), int(height)
        self.settings = settings or CRTSettings()
        if not (0.0 <= self.settings.distortion <= 0.35):
            raise ValueError('distortion should be between 0 and 0.35')
        if self.settings.scanline_spacing <= 0:
            raise ValueError('scanline_spacing must be positive')
        self._make_cached_mappings()

    def _make_cached_mappings(self) -> None:
        w, h, cfg = self.width, self.height, self.settings
        xx, yy = np.meshgrid(
            np.linspace(-1, 1, w, dtype=np.float32),
            np.linspace(-1, 1, h, dtype=np.float32),
        )
        r2 = xx * xx + yy * yy
        # Output-pixel -> input-sample inverse map. The factor increases
        # toward the corners, curving lines into a convincing convex CRT look.
        scale = 1.0 + cfg.distortion * r2
        self.map_x = np.ascontiguousarray((xx * scale + 1) * (w - 1) * 0.5)
        self.map_y = np.ascontiguousarray((yy * scale + 1) * (h - 1) * 0.5)

        # Smooth darkening, normalized so centre remains at 100%.
        radial = np.clip(r2 / 2.0, 0, 1)
        self.shading = np.clip(1.0 - cfg.vignette * radial ** 1.45, 0, 1)

        # Every pixel can be slightly dimmed, avoiding harsh aliasing on text.
        rows = np.arange(h, dtype=np.float32)[:, None]
        lines = (1.0 - np.cos(2.0 * np.pi * rows / cfg.scanline_spacing)) * 0.5
        self.shading *= 1.0 - cfg.scanlines * lines
        self.shading = self.shading[:, :, None].astype(np.float32)

        # Channel separation grows toward edges, minimal at centre.
        radial_edge = np.minimum(r2 / 2.0, 1.0)
        self.shift_x = (cfg.chromatic_pixels * radial_edge * xx).astype(np.float32)
        self.shift_y = (cfg.chromatic_pixels * radial_edge * yy).astype(np.float32)
        # An unobtrusive, broad curved-glass reflection in the upper region.
        top_highlight = np.exp(-((yy + 0.87) / 0.15) ** 2)
        side_falloff = np.clip(1.0 - 0.48 * np.abs(xx) ** 2, 0.0, 1.0)
        self.glare = (cfg.reflection * top_highlight * side_falloff)[:, :, None]

    def apply(self, frame: np.ndarray) -> np.ndarray:
        """Return the distorted RGB/RGBA frame (uint8, same dimensions).

        Assumes its pixels belong to screen content ONLY; for an existing
        screenshot, use apply_to_screenshot to protect the surrounding bezel.
        """
        h, w = frame.shape[:2]
        if (h, w) != (self.height, self.width):
            raise ValueError(f'Expected {self.width}x{self.height}, got {w}x{h}')
        if frame.dtype != np.uint8 or frame.ndim != 3 or frame.shape[2] not in (3, 4):
            raise ValueError('Input must be HxWx3 RGB or HxWx4 RGBA uint8')

        cfg = self.settings
        rgb = np.ascontiguousarray(frame[:, :, :3])
        # Constant black at the edges; the original bezel masks these margins.
        warped = cv2.remap(
            rgb, self.map_x, self.map_y, interpolation=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0)
        )

        if cfg.chromatic_pixels > 0:
            # Red and blue channels fringe in opposite radial directions.
            r = cv2.remap(
                rgb[:, :, 0], self.map_x + self.shift_x,
                self.map_y + self.shift_y, cv2.INTER_LINEAR,
                borderMode=cv2.BORDER_CONSTANT, borderValue=0
            )
            b = cv2.remap(
                rgb[:, :, 2], self.map_x - self.shift_x,
                self.map_y - self.shift_y, cv2.INTER_LINEAR,
                borderMode=cv2.BORDER_CONSTANT, borderValue=0
            )
            warped[:, :, 0] = r
            warped[:, :, 2] = b

        light = warped.astype(np.float32)
        # Process the glow before shading; preserves fine text with a restrained halo.
        if cfg.bloom > 0:
            bloom = cv2.GaussianBlur(light, (0, 0), sigmaX=cfg.bloom_sigma)
            # Only glow on relatively bright content, keeping the blacks black.
            bright = np.maximum(bloom - 65.0, 0.0)
            light = light + cfg.bloom * bright

        light *= self.shading
        light += 255.0 * self.glare
        result_rgb = np.clip(light, 0, 255).astype(np.uint8)

        if frame.shape[2] == 3:
            return result_rgb
        warped_alpha = cv2.remap(
            frame[:, :, 3], self.map_x, self.map_y,
            interpolation=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT, borderValue=0
        )
        return np.dstack((result_rgb, warped_alpha))

    def screen_to_source_point(self, x: float, y: float) -> Tuple[float, float] | None:
        """Distorted viewport pixel -> undistorted UI pixel for pointer events.

        This directly evaluates the same analytic mapping as cv2.remap. Return
        None if the point samples beyond the drawable content.
        """
        x_norm = 2.0 * x / (self.width - 1) - 1.0
        y_norm = 2.0 * y / (self.height - 1) - 1.0
        factor = 1.0 + self.settings.distortion * (x_norm*x_norm + y_norm*y_norm)
        sx = (x_norm * factor + 1.0) * 0.5 * (self.width - 1)
        sy = (y_norm * factor + 1.0) * 0.5 * (self.height - 1)
        if not (0 <= sx < self.width and 0 <= sy < self.height):
            return None
        return sx, sy


def rounded_mask(width: int, height: int, radius: int = 54,
                 feather: float = 4.0) -> np.ndarray:
    """Antialiased rounded-rectangle alpha mask for the interior of CRT glass."""
    r = max(0, min(int(radius), width // 2, height // 2))
    mask = np.zeros((height, width), dtype=np.uint8)
    if r == 0:
        mask[:] = 255
    else:
        cv2.rectangle(mask, (r, 0), (width-r-1, height-1), 255, -1)
        cv2.rectangle(mask, (0, r), (width-1, height-r-1), 255, -1)
        for cx, cy in ((r, r), (width-r-1, r),
                       (r, height-r-1), (width-r-1, height-r-1)):
            cv2.circle(mask, (cx, cy), r, 255, -1, lineType=cv2.LINE_AA)
    if feather > 0:
        mask = cv2.GaussianBlur(mask, (0, 0), feather)
    return mask.astype(np.float32) / 255.0


def apply_to_screenshot(
    image: np.ndarray,
    rect: Tuple[int, int, int, int],
    settings: CRTSettings | None = None,
    corner_radius: int = 58,
    feather: float = 5.0,
) -> np.ndarray:
    """Demo-only: apply filter inside a screenshot and preserve ALL bezel pixels.

    rect: (left, top, width, height) for the *inner black screen area*.
    Integration into the live app should use CRTBarrelFilter.apply() before
    compositing the screen behind the metal bezel; not this screenshot function.
    """
    x, y, w, h = [int(value) for value in rect]
    if x < 0 or y < 0 or w < 2 or h < 2 or x+w > image.shape[1] or y+h > image.shape[0]:
        raise ValueError('rect must be completely inside the image')
    out = image.copy()
    source = image[y:y+h, x:x+w]
    filtered = CRTBarrelFilter(w, h, settings).apply(source)
    mask = rounded_mask(w, h, radius=corner_radius, feather=feather)[:, :, None]
    # Composite only inside the selected glass; unchanged metal pixels remain exact.
    composite = source.astype(np.float32) * (1.0 - mask) + filtered.astype(np.float32) * mask
    out[y:y+h, x:x+w] = np.clip(composite, 0, 255).astype(np.uint8)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description='CRT barrel distortion screenshot preview')
    parser.add_argument('--input', required=True, help='Input screenshot or screen-content image')
    parser.add_argument('--output', required=True, help='Output image (PNG recommended)')
    parser.add_argument('--rect', type=int, nargs=4, metavar=('X', 'Y', 'W', 'H'),
                        help='Inner glass region; omit to transform the entire image')
    parser.add_argument('--distortion', type=float, default=0.075)
    parser.add_argument('--vignette', type=float, default=0.24)
    parser.add_argument('--scanlines', type=float, default=0.075)
    parser.add_argument('--chroma', type=float, default=0.85)
    parser.add_argument('--bloom', type=float, default=0.07)
    parser.add_argument('--reflection', type=float, default=0.035)
    parser.add_argument('--radius', type=int, default=58)
    args = parser.parse_args()

    from PIL import Image
    input_image = Image.open(args.input).convert('RGB')
    frame = np.array(input_image)
    cfg = CRTSettings(
        distortion=args.distortion, vignette=args.vignette,
        scanlines=args.scanlines, chromatic_pixels=args.chroma,
        bloom=args.bloom, reflection=args.reflection,
    )
    if args.rect:
        output = apply_to_screenshot(frame, tuple(args.rect), cfg, args.radius)
    else:
        output = CRTBarrelFilter(frame.shape[1], frame.shape[0], cfg).apply(frame)
    Image.fromarray(output, mode='RGB').save(args.output)
    print(f'Saved: {args.output}')


if __name__ == '__main__':
    main()
