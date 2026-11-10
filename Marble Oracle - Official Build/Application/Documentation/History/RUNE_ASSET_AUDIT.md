# Rune asset audit and integration notes

Supplied by user: `Rune_Seeing_AI_Agent_Package(1).zip` containing `Runes.zip` and handover.
All 48 PNGs were checked: 24 marked and 24 matching blank stone pictures; each 96×96.

**Mapping remains provisional.** The filenames are NOT standard Elder Futhark order. The mapping
is recorded in `Marble_Oracle_App/data/rune_asset_manifest.json`, with source files and
reference Unicode glyphs. This is an implementation interpretation of the supplied stylized art,
not a claim that the uploader or artist verified the symbols. In particular **01, 16, 17 and 18**
need final artist/manual confirmation before a public release. Do not silently substitute
semantic meanings if a glyph is incorrect. Reference chart consulted:
https://wayoftherunes.com/blog/

Uses all 24 outcomes, three without replacement, with modern reflective interpretations.
Blank pictures are backs only and never appear as reading outcomes. Does not claim to reconstruct
historical Viking divination. No reversed stones.

Art remains in the user-supplied file exactly as provided, and is resized in-memory with Pillow.
Redistribution provenance and rights for the rune art have not been established.

Switch with TAROT/RUNES at the top right of the existing THREE CUTS panel. Draw Three and click
stones to focus a position-specific interpretation. Selection is made once before staggered
reveal and stays stable through repaints. Switching away cancels pending reveal callbacks.
The original Tarot daily draw, custom deal, and selected-card readings remain unchanged.

Automated test command (Linux with Xvfb):
`xvfb-run -a python Marble_Oracle_App/marble_oracle.py --selftest --no-bezel --no-network --no-markets`

Further QA: inspect the layout on real Windows 11 and Linux Mint displays; review the rune
asset matching with the original artist; inspect 24 front/back registration visually.
