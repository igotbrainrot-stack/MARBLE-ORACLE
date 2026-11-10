Rune visual fixes
=================

This build fixes two issues in the Rune panel:

1. Pre-flip symbol bleed:
   - The first three animation frames now use true blank stone backs.
   - This prevents rune symbols from showing before the reveal begins.

2. Stone clipping:
   - Reduced fitted rune stone size slightly.
   - Added extra top/bottom and side clearance within the card panel.
   - Ensured the loaded image budget leaves breathing room inside the frame.

Self-test status:
- marble_oracle.py --selftest: passed under xvfb
