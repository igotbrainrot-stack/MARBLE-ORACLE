# Marble Oracle — conservative refinement pass

## Baseline
Based on `Marble-Oracle-FULL-Passphrase-Studio-Integrated-Windows-Linux.zip` (supplied in this conversation). The application layout, panels, menus, controls, Tarot / Runes toggle, Passphrase Studio tab, fonts, themes, and normal startup flags were not changed. Goyzepam remains absent.

## Changes made
- **Rune animation performance:** retain a decoded source strip for each rune in memory, so successive animation frames no longer repeatedly open the 6.5 MB flip-asset ZIP and decode the same image. Frame order, artwork, display sizes and 115 ms animation timing are unchanged. Existing rendered-frame cache behaviour is preserved.
- **Settings safety:** `oracle_assets.save_json()` now writes a uniquely named temporary file within the same directory, flushes it, and atomically replaces the old file. Concurrent calls cannot overwrite one another's fixed `.tmp` file. The saved JSON schema and callers are unchanged; previous settings are preserved on a failed write.
- **Release hygiene:** removed only generated `__pycache__` folders and `.pyc` files from the distribution. No historical application assets, scripts, user settings, or runtime files were removed.
- **Regression checks:** added `test_refinement.py` for settings persistence and assets. No new runtime dependencies.

## Verified in this development environment
- Baseline and refined GUI self-tests: normal no-bezel, CRT enabled, CRT disabled (Linux Xvfb) — all passed.
- Rune package: 24 named Rune animations present; original and reverse Rune assets and Tarot zip present.
- Passphrase Studio functionality exercised by existing GUI self-test, including phrase creation, swap and reroll.
- Settings concurrent-write regression and artifact checks passed.
- Python syntax compilation and release ZIP integrity validated.

## Limitations / verification pending
- Native Windows 11 GUI launching, visual scaling, audio devices, and final physical Linux Mint desktop operation were **not** tested in this environment.
- GUI self-test covers representative workflows, not every external network integration or every possible setting. Live market feeds and local audio hardware were not tested.
- No intentional layout or visual design changes were made, in accordance with the brief.
- The Windows `.pyw` launcher requires a compatible Python + Tk installation; the packaged source is not a standalone compiled `.exe`. The existing `Launch_Marble_Oracle.vbs` is an alternate console-free launcher on systems with the Windows Python launcher installed. On Linux use the included application-menu installer (`Terminal=false`).
