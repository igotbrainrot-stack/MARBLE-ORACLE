# Home sidebar surface and muted ASCII

This release corrects two appearance problems reported after the crisp ASCII overhaul.

- **HOME background:** The source of the earlier mismatch was a surface-role inconsistency. The canvas gutter used the actual Oggcultist `side.png` tile, but large HOME panels still used the lighter `raised` card tile. The HOME base colour and primary panel backgrounds are now both `#130F0D`, and their film grain/mottle is tiled directly from Oggcultist 2.0.6's bundled `side.png` (unchanged). Insets and ticker rows retain their depth treatment.
- **ASCII artwork:** The crisp micro-bitmap renderer remains in use, with 14 rotating plates, ten distinct shade bands, and opaque pixels. The bitmap palette and the fallback text palette have both been changed from nearly white to a muted limestone range (`#675E57` through `#D3C8B8`). The darkest bands remain legible; highlights no longer approach white.

No changes to the four tabs, media installer, Rune/Tarot artwork, Passphrase, or typing games.

Verification: `test_home_sidebar_and_muted_ascii.py`, `test_ascii_visibility.py`, GUI selftest, original Oggcultist texture provenance, embedded Oggcultist, tab layout, and Touch Type tests under a Linux virtual display. These checks are not a native Windows 11 or physical Linux Mint certification.
