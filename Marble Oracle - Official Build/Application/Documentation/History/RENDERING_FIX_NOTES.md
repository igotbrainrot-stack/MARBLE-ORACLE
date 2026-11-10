# Marble Oracle — Rune visibility and high-density ASCII repair

This is the complete cross-platform Marble Oracle application, not a patch.

## Rune panel
- Rune stone images are now drawn in a protected `rune-art` canvas layer above CRT/sepia/glare filtering, directly alongside the protected statue artwork.
- Every rune panel redraw explicitly reapplies the layer stack. This fixes a case where dynamically created rune images were obscured even though they loaded successfully.
- The application now reports rune-image exceptions in the rune reading area rather than silently displaying a blank substitute as if nothing had failed.
- The existing Tarot / Runes toggle, three-stone sequence and all animation assets remain part of this package.
- Automated GUI tests check actual canvas image objects and stacking order as well as the complete reveal sequence.

## Marble statue
- Restored dense character silhouettes by replacing weak punctuation shading with `#`, `%` and `@`-style ASCII ink.
- All ten shading bands now use bright near-white through pure white, with no low-contrast brown bands.
- Draws each character at the intended fixed column position even with proportional Uberata Clear, avoiding run-length text spacing errors.
- The cyan and magenta ghost copies are disabled for the statue itself; the rest of the interface retains its design treatment.
- Statue remains above CRT/glass effects.

## Tested
- Python compilation.
- Linux virtual-display full GUI self-test with CRT effects enabled.
- Linux virtual-display full GUI self-test with CRT effects disabled.
- 24-rune image/animation archive structural validation.

## Not tested
- Native Windows 11 desktop rendering.
- Physical Linux Mint desktop / display scaling / audio hardware.

Run: `Marble_Oracle.pyw` on Windows, or install the Linux application-menu entry with `install_linux_desktop.sh`.
