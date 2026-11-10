# Rune panel: larger matching artwork

The three Rune stones previously occupied less than half of each available
column's width in the HOME / THREE CUTS panel. This was not a user setting.

## Root causes

- `draw_runes` limited the stone sprite to 96×96 pixels, irrespective of panel
  width or height.
- The separate `RuneDeck._frame_size` helper subtracted five more pixels and
  rounded down to the next native PNG size (often 88px).
- The old high-resolution sprite builder called `thumbnail((183, 183))` on a
  171×165px rock. `thumbnail()` never enlarges an image, leaving the rock
  covering only about two-thirds of the 96×96 sprite area.
- Excessive per-column padding removed still more available width.

## Changes

- Dynamically fit the three sprite images to the column's safe rectangle,
  without the artificial 96px cap or double-subtracted safety padding.
- Rebuild all 24 rune faces, their matching blank backs and 12 flip frames
  with a true, larger master rock while preserving identical silhouettes.
- Supply additional native sprite sizes up to 192px; no runtime Pillow
  dependency or fake resizing is required.
- Keep complete transparent PNG margins and enforce an edge-safe alpha cutoff
  at small sizes to avoid resampling halos.
- Center larger stones in the available vertical area above the reading pane.
- At compact widths, show rune positions and names without crowded keywords;
  the full interpretation below retains all meanings.
- Keep native Tk label click handlers and canvas click regions working.

## Verification

The included `test_rune_panel_scale.py`, `test_rune_consistency.py` and existing
Rune interaction and full-app integration tests exercise the new geometry.
