# Rune panel: no-clipping fix

This is the complete Marble Oracle application based on `Marble-Oracle-FULL-Rune-Art-Guaranteed-Visible-Fix-Windows-Linux.zip`. Existing layouts, navigation, Passphrase Studio, Tarot, 24 Rune animations, Ember colours and Uberata Clear have been retained.

## Root cause

The Rune frame loader selected a 96-pixel PNG whenever the intended stone slot was 80–95 pixels, but the Tkinter image Label was placed at the smaller requested slot size. Tkinter clips an image when the widget's rectangle is smaller than the PhotoImage. Smaller slots could also clip the 64px asset. Labels could encroach on the panel's reading boundary.

## Repair

- Added high-quality, pre-rendered PNG frame sizes (24, 32, 40, 48, 56, 72, 80, 88); existing 64 and 96-pixel PNGs are retained unchanged.
- `oracle_runes.py` now selects the largest asset that fits the actual available display space, without requiring Pillow at runtime.
- `marble_oracle.py` now uses the PhotoImage's actual dimensions for both canvas and overlay Label placement, with per-stone safe bounds that preserve padding inside the existing panel border and above the reading box.
- Position captions fit inside their card column at reduced window sizes; the full layout is unchanged.
- No changes to the underlying three-stone reading logic or Tarot mode.

## Verification

- `test_rune_border_fit.py`: 456 visible widget placements across 11 saved layouts and four window sizes (1216×848, 900×620, 760×550, 640×460); all eight flip frames in Classic layout; verified image dimensions equal widget dimensions and all edges remain within safe panel bounds. Tarot switching remains functional.
- `test_rune_native_assets.py`: all 24 runes x eight original animation frames load under native Tkinter without Pillow.
- Marble Oracle `--selftest` passed with plain and CRT V2 modes. Existing retro-mode self-test also passed.
- All generated frame assets have alpha transparency and remain separate from the CRT overlay.

## Launch

- Windows 11: run `Marble_Oracle.pyw` from the extracted `Marble_Oracle` directory (Python + Tkinter required).
- Linux Mint: use `Marble_Oracle_Linux.sh` or install the desktop launcher with `install_linux_desktop.sh`.

The test environment used a Linux virtual X11 display. Native Windows 11 and physical Linux Mint desktop verification remain outstanding.
