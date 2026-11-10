# PLATE VAULT — washed-out ASCII root cause and repair

## Root cause (confirmed)

The artwork's original archive contains high-density, animated ASCII plates. The PLATE VAULT panel is relatively narrow, so `Scene._arch_fit` commonly fitted a `-3` pixel Tk font with approximately 3 x 6-pixel character cells and downsampled the plates (e.g. 114 x 76 to 57 x 38). Passing punctuation such as `:`, `;`, and `-` through the anti-aliased Uberata Clear text renderer at 3px caused most of the character strokes to turn into dim subpixel greys. The colour ramp was also bunched into near-ivory tones, flattening the original shading distinctions. Brightening the colours did not repair the glyph coverage.

The source Oggcultist texture and CRT were not the primary cause: the statue uses a canvas layer above the CRT/glass (`Scene.LAYERS`).

## Changes

- Added `oracle_ascii_bitmap.py`: a 3 x 5 micro-ASCII rasterizer that preserves source characters and luminance bands while providing sharp opaque strokes, even when the GUI has only 3 x 6 pixels per character.
- Widened the highlight-to-shadow ramp for the bitmapped statue while preserving bright ivory highlights.
- Replaced thousands of tiny antialiased Tk text objects with one transparent bitmap per animation frame, keeping the figure above CRT filters and preserving panel textures.
- Bounded the cached Tk frame images to 48 entries to avoid unbounded memory growth.
- Preserved legacy Tk text rendering as a fallback if Pillow or PNG rendering is unavailable.
- Kept the Uberata Clear font for all ordinary interface text; only the micro-ASCII art uses pixel glyphs.
- Added a regression test for 84 frames covering all 14 statue types and very small cell dimensions.

## Verification

- `marble_oracle.py --selftest` passed in an Xvfb Linux display.
- `test_ascii_visibility.py` passed: bitmap pixel coverage, 14 statue types, 84 representative frames, small-cell visibility, and real Tk canvas rendering.
- `test_tab_layout.py`, `test_touch_type.py`, `test_source_ogg_texture.py`, and `test_ogg206_embedded.py` passed.
- Native Windows 11 and physical Linux Mint verification remain outstanding.

The 14 source plates and their turn animations are unchanged, as are the Oggcultist-generated background texture PNGs and all other tabs.
