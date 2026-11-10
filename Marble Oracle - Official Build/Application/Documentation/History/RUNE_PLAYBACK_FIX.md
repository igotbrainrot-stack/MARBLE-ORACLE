# Rune animation visibility and playback correction

## Changes
- Entering the Rune panel for the first time begins a three-stone reading automatically after a brief delay. The original `DRAW THREE` / `NEW READING` controls are preserved and continue to work.
- The rune's blank and face-up artwork now come from the same supplied eight-frame sprite strip; the previous code displayed older static 96-pixel stones until the reveal began.
- The visible frame interval is at least 145 ms, making the sequential turns more perceptible on normal desktops. The three-stone reveal is still one stone at a time.
- No modifications to the original five-panel layout, Tarot, Passphrase, ASCII art, fonts, or other modules.

## Why previous testing wasn't sufficient
Prior self-tests established that the canvas contained image objects and that the playback state completed. Those checks didn't prove the user could see the frame-to-frame changes. This revision also captured GUI frames on an Xvfb Linux display and verified that the Rune panel changed between successive animation frames, then reached the completed three-stone state.

## Validation on Linux virtual display
- Python compilation passed.
- Original GUI self-test passed in standard, retro and CRT V2 modes.
- Live observation points: at 0.65s first rune frame 0; at 1.0s first rune frame 2; at 1.35s first rune frame 4; at 2.3s second rune frame 2; at 4.5s all three were complete.
- Pixel differences were nonzero between captured stages, confirming that frames really changed on the canvas.
- The animation archive includes 24 rune strips and all required source artwork.

## Outstanding
Physical Windows 11 and Linux Mint desktop visual checks were not available. If the user keeps an earlier extracted program directory and launches that instead of this ZIP, the earlier bug will remain. Extract this full package into a new directory.
