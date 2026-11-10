# Rune flip integration — Marble Oracle

## What changed
The original five-panel Oracle layout and in-panel TAROT / RUNES toggle are retained. Runes now use the **24 supplied eight-frame animation strips** (192 frames total) in `Marble_Oracle_App/data/rune_flip_strips.zip` instead of instantly swapping static stone art. The original `data/runes.zip` is deliberately retained as a fallback and for the unused-draw state. There are no changes to Tarot artwork, selection or daily reading data.

### Implementation
- `Marble_Oracle_App/oracle_runes.py`: `RuneDeck` reads `manifest.json` from the animation archive, resolves 24 names (including Berkano → Berkana), and loads/caches individual frames from PNG strips in the original source set.
- `Marble_Oracle_App/marble_oracle.py`: Rune mode renders the animation frame for the currently flipping stone. Each selected stone flips through eight frames at the manifest's 115 ms interval, then the next begins 220 ms later. The final face is held, interpretations appear after the third stone, and returning to Tarot invalidates pending animation callbacks.
- All 24 rune image animations are kept at their original visual fidelity; they were not redrawn or relabeled in this integration.
- The reading keeps the original `Past / Present / Possible Future` positions and reuses the existing click-to-focus interpretation.

## Verification
- `python -m compileall` completed successfully.
- `xvfb-run -a python marble_oracle.py --selftest --no-network --no-markets` passed, including automatic playback of all three sequential rune animations and Tarot toggle regression.
- Additional virtual-Tk test loaded all 24 × 8 PNG animation frames at screen size.
- ZIP archives are checked for corrupt entries at packaging time.

## Known limitations
- Native Windows 11 and physical Linux Mint desktop/graphics/audio have not been tested here.
- The provided animation PNGs inherit glyphs from the generated source artwork, **not font-derived glyph overlays**; original rune-shape validation remains recommended before release. Reversed readings are not implemented, matching the prior Rune mode.
- The normal platform builds are Python application distributions, not compiled self-contained executables. Pillow is required for rune PNG decoding.

## Launch
- Linux Mint: run `install_linux_desktop.sh` from the extracted `Marble_Oracle` directory to add a console-free menu entry; or run `Marble_Oracle_Linux.sh` in a terminal for diagnostics.
- Windows: double-click `Marble_Oracle.pyw` (Python with Tkinter needed) for a console-free launch.

## Notes
The previous 'Goyzepam' feature remains removed. Do not remove the `rune_flip_strips.zip` or old `runes.zip` runtime assets during future cleanup. Uberata Clear remains the interface font. The special runic symbols are only image artwork, not interface text.
