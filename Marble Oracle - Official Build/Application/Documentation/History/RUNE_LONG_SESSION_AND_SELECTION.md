# Rune long-session reliability patch

This release builds on the matched 12-frame, 24-stone animation artwork.

- Rune tiles have explicit click priority after the TAROT/RUNES mode switch and the NEW READING button, preventing broad dashboard hitboxes from swallowing stone selections.
- Tile hitboxes are constrained above the reading/interpretation pane, avoiding accidental selection when clicking text in that pane.
- Position captions provide visible gold feedback for the selected tile while the three stones flip.
- One source ZIP handle is reused for frame decoding. Previously, each animation tick reopened and rescanned the central directory of the large animation ZIP, making resizing and frame changes unnecessarily slow; the open handle is released with `RuneDeck.close()`.
- Cached Tk `PhotoImage` frames are now limited to the 144 most recently used images. Displayed images are still held by the active Scene/widget references and are never destroyed while displayed. This prevents endless image memory growth when drawing new stones repeatedly.
- A repeated GUI test covers 10 readings, all 12 flip frames, all three stone positions and 30 direct native-label clicks, plus every frame for all 24 symbols at three sizes; it checks click priority and the cache limit.

Launchers, visual theme, official folder layout, embedded Oggcultist, and first-run requirements manager are unchanged.
