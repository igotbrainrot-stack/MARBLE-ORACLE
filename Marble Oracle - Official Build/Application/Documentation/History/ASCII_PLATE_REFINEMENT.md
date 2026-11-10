ASCII Plate Refinement
======================

This build updates the PLATE VAULT / ASCII statue rendering.

Changes
- Reduced the statue ink from bright white to a slightly duller warm off-white.
- Preserved more of the source ASCII glyph variety to improve the perceived detail.
- Reduced the minimum fit probe size so more source characters can remain visible before downsampling.

Result
- The ASCII art appears a little less glaring.
- The statue reads as higher-resolution and more sculptural.
- The darker Oggcultist-like panel treatment remains intact.

Verification
- marble_oracle.py --selftest passed under xvfb.
