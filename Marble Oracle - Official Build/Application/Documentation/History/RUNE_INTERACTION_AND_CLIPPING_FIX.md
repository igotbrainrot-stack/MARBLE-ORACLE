# Rune Panel Interaction and Top-Edge Visibility Repair

This release is based on Marble Oracle's Official Ember Style / Startup Fix suite.
No tab positions, panel structure, Oggcultist pages, Passphrase layout or Tarot functions were redesigned.

## Fixes

1. **Top-edge cutoff:** Reprocessed the 1,920 native Rune flip PNGs (24 runes × 8 frames × 10 output sizes) with transparent insets. Artwork is scaled inwards, never trimmed or cropped. Runtime Tk photo loading remains Pillow-free.
2. **Vertical fit:** The Rune panel computes a real image budget from the available cell height and width, with reserved top/bottom clearance; loaded image dimensions and widget placement both obey that budget.
3. **Unresponsive clicks:** Tarot/Rune mode controls and the Rune draw button now take precedence in pointer hit testing over broad dashboard controls.
4. **Disabled redraw:** The draw button is now available during an ongoing reveal as `RESTART DRAW`, and new presses invalidate old animation callbacks to avoid overlapping flips.
5. **Original functionality:** Three unique runes, eight-frame reveal, interpretation selection, return to Tarot, existing tabs, and the bundled Oggcultist 2.0.6 remain intact.

## Validation actually performed (Linux virtual display)

- `marble_oracle.py --selftest`: PASS, including three timed stone reveals and returning to Tarot.
- `test_rune_border_fit.py`: PASS, 456 widget placements, 11 layouts, four window sizes, full eight-frame check in Classic.
- `test_rune_click_and_art.py`: PASS, 178 actual Tk canvas click events across 11 layouts and four window sizes, plus native stone-widget selection click.
- `test_tab_layout.py`: PASS, normal/retro/flat, including tab switching and preserved panel actions.
- Native animation asset audit: all 1,920 PNG files have at least 2 pixels of transparent margin on all sides.

## Caveats

- Native Windows 11 and physical Linux Mint interaction testing still need to be performed.
- Insets cannot restore image details that were already missing in the originally supplied/generated artwork. They prevent further cropping at the image/widget/panel boundary.
- Audio hardware and live FFmpeg installation were not re-tested as part of this targeted Rune patch.
