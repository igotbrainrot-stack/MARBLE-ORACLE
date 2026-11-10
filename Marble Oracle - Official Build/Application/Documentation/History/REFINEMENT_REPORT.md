# Marble Oracle — refinement report (8 November 2026)

## Baseline and scope
Based on the last complete Linux Marble Oracle Classic Modern release. Preserved its original five-panel layout, existing instrument logic, card/deck handling, Latin, archive, Wire, markets, passphrase generation, CRT display modes, and stored preferences. The intentionally removed sponsor feature remains excluded. This is a conservative refinement rather than another layout rewrite.

## Implemented
- Replaced the default Windows command-prompt-oriented launch path with a modern-layout `.pyw` entry point and optional VBScript shortcut; the `.bat` launcher remains for troubleshooting.
- Installed a Linux Mint app-menu launcher using `Terminal=false`, using the application's bundled icon, with correctly quoted locations containing spaces or shell metacharacters.
- Standardized remaining explicit Consolas fonts in classic/CRT/dicekey UI code to Uberata Clear; verified Fontconfig application font registration and Tk default-font selection on Linux Xvfb.
- Added GUI startup failure logging and actionable dialogs to the GUI launcher.
- Removed automatic dependency installation at application startup. Optional CRT and audio dependencies must be installed explicitly instead of silently modifying Python.
- Added clear launch instructions and separated clean runtime packaging from legacy internal developer scripts/documents.
- Preserved application data and preferences; no user-data folders were cleaned or overwritten.

## Technical / architecture
Python 3, Tkinter for canvas GUI, core `marble_oracle.py`, platform/bootstrap `oracle_bootstrap.py`, state/assets in `oracle_assets.py`, fonts in `marble_uberata.py`, and optional hardware look modules `oracle_crt_v2.py` and `oracle_photo_bezel.py`. `data/` contains reference media and auxiliary archives. External market/news feeds depend on network availability; local asset fallback is preserved.

## Verified checks
- Python compilation over all runtime source: passed.
- Shell syntax check for Linux scripts: passed.
- Complete built-in GUI self-test under Linux Xvfb (`--selftest --no-network --no-bezel --os-frame`): passed, reported `SELFTEST OK`.
- Bundled font registration in Linux Xvfb: `Uberata registered: True`, `TkDefaultFont = Uberata Clear`.
- Linux `.desktop` generation with a path containing spaces and `&`: passed, with `Terminal=false`.
- Archive checks and required asset inventory: passed at packaging time.

## Limits and remaining risks
- No access to native Windows 11 or a physical Linux Mint desktop for click-through, audio, full visual QA or display-scaling checks; do not treat virtual-display results as native acceptance.
- Python and Tk are system prerequisites; these are source distributions, not fully bundled executable installers.
- Windows optional speaker loopback and Linux audio backends need real-machine checks.
- Pixel-level visual review on multiple monitor sizes and accessibility audit are not fully complete. Further visual changes should be grounded in screenshots and may be delivered in another pass.
- Optional hardware-style CRT mode needs Pillow and may have additional platform dependencies.

## Files removed from runtime only
Legacy inner batch launchers, older release reports, stale handover notes, historical app readme duplications, caches. Full source package retains legacy source files except caches and intentionally removed feature. No required asset archives removed.

## Archive readability update
The Plate Vault ASCII statue colour ramp is now a warm high-contrast ten-step palette on Ember surfaces. This lifts previously invisible dark shading while preserving the original statue geometry, size, animation, controls and all other panels.
