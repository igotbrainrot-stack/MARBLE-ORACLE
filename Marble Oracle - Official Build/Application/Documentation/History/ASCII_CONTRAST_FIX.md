# ASCII Marble Statue Contrast Fix

Issue: the canvas drew the ASCII statue with a brighter ink ramp, but then
stacked the CRT/sepia and glass overlay layers over all the content, including
the artwork. This made the statues appear faded despite the bright palette.

Fix: the `statue` tag now sits above `crt`, `pixel-crt`, and `glare` while
remaining below secondary windows, chrome, popups and bezels. The normal CRT
appearance for the rest of the screen remains unchanged. The classic five-panel
layout, Tarot / Runes switch, rune animations, Uberata Clear, and other features
are preserved. Goyzepam was not reintroduced.

Validation: `python3 marble_oracle.py --selftest --no-network --no-bezel`
under Xvfb returns SELFTEST OK. A regression assertion verifies that a drawn
statue sits higher than any CRT and glass effect items present in the canvas.
Python syntax and distribution archive validation were also performed.

Limitations: Native Windows GUI and real monitor tests were not performed.
Separate external pixel-CRT/window or hardware-based post-processing effects
may still alter the final image; this patch addresses the Tk canvas layers.
