# Rune image visibility and flip playback: definitive dependency fix

## Root cause
The earlier Rune code used `PIL.ImageTk` even for the *normal* Linux Mint graphical launch mode, while the Linux launcher deliberately did not require Pillow. The application could therefore show its other sections while Rune image creation raised `ModuleNotFoundError` and fell back to featureless ovals. Additional CRT canvas effects could cover images in some display modes.

## Fix
- Bundled all 24 runes × 8 stages in native 64px and 96px transparent PNG files inside `Marble_Oracle_App/data/rune_native_frames.zip` (384 pre-rendered PNGs).
- RuneDeck loads those PNGs using **Tkinter `PhotoImage`**, not Pillow/ImageTk. Playback does not require installing Pillow.
- Three persistent, native Tk image labels display stones on top of the canvas's CRT/glass layers. The original canvas artwork and Rune reading positions are retained.
- Labels are updated in place for each frame, hidden when switching to Tarot, and hidden when the Passphrase overlay opens, then restored when returning home.
- Existing original Rune and flip-strip archives are preserved; no original card, Passphrase, or layout changes.

## Verified
- Original GUI self-test passes on Linux Xvfb.
- Same GUI self-test passes with Pillow deliberately disabled (`sys.modules['PIL']=None`).
- A screenshot of actual Rune images displayed in the application was captured on a Linux virtual display.
- All 24 Rune strips and 384 native PNGs are bundled.

## Starting
Extract the whole ZIP into a **new folder**, then use `Marble_Oracle_Linux.sh` on Linux or `Marble_Oracle.pyw` on Windows. Pillow remains optional for some CRT effects but is **not needed for the Rune panel**.

Native Windows 11 and physical-machine Linux Mint rendering has not been verified.
