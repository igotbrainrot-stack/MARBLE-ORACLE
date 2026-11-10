# Marble Oracle — Three-Tab Navigation / Relocated Controls

## Changes in this release

- Replaced the old top-left WIRE, TONGUE, CUT, and GRADE header buttons with a persistent three-tab navigation strip: **HOME**, **PASSPHRASE**, **OGGCULTIST**.
- **HOME** returns to the original five-panel Oracle dashboard without closing the program.
- **PASSPHRASE** opens the existing five-card Marble Passphrase interface. Its Back button and Escape key continue to return Home.
- **OGGCULTIST** opens a dedicated Ember/Uberata workspace tab. It starts the complete bundled Oggcultist 2.0.4 program in its own window, preserving its independent audio-player/converter lifecycle. The workspace has an Open Oggcultist button and a Back to Home button. Oggcultist remains running if you return to Oracle. This is a *launcher tab*, not an in-window embedded copy of Oggcultist's full multi-page GUI.
- Restored the four former menu commands as small buttons in the **lower-left** of their relevant panels:
  - **WIRE** — lower-left of THE WIRE (next quotation).
  - **TONGUE** — lower-left of DEAD TONGUE (next Latin word).
  - **CUT** — lower-left of THREE CUTS (draw new tarot cards or runes).
  - **GRADE** — lower-left of the global status/footer region (cycle layout).
- Moved the old Wire quotation attribution and Latin voice-mode text slightly right to make room for their controls.
- Reserved a narrow bottom strip for CUT in the divination panel, keeping its explanatory text clear of the button.
- Kept the original Rusted CRT hardware buttons, which remain usable in CRT V2 mode; adjusted header navigation inset to avoid the physical bezel's protruding upper-left module.
- Preserved Tarot/Rune selection and 24 rune flip animations, bright ASCII statue art, existing Oracle features, and all existing preset layouts.
- Bundled Oggcultist's source, resources, licenses, and an actual Uberata Clear TTF, so it does not have to look in the user's Downloads folder for its font.
- Oggcultist writes startup diagnostics to Marble Oracle's per-user state directory rather than to the application source tree.

## Launching

- **Windows 11:** Extract the ZIP and double-click `Marble_Oracle.pyw` (Python 3 with Tkinter required). No console window is used by this normal launcher. The **OGGCULTIST** tab launches its own window without a shell.
- **Linux Mint:** Extract the ZIP and run `install_linux_desktop.sh` to install the GUI menu shortcut (`Terminal=false`), or use `Marble_Oracle_Linux.sh` for troubleshooting. Python 3 and Tkinter are required. For Oggcultist conversion/playback, provide FFmpeg, FFprobe and FFplay (e.g. install the `ffmpeg` package).
- The entire folder must remain together, including `Marble_Oracle_App/Oggcultist/` and `Marble_Oracle_App/fonts/`.

## Tests and limitations

- Python compilation passed for the changed application modules.
- Marble Oracle's existing Linux virtual-display GUI self-test passed in normal and retro configurations.
- `test_tab_layout.py` passed in clean, retro, and flat modes: exact three tab labels and click regions; four controls in assigned lower panel regions; switches between Home, Passphrase, and Oggcultist; back-home and Escape; passphrase re-opening.
- `test_actual_mode.py` passed for both the standard no-bezel screen and a CRT V2 hardware configuration. Captured screenshots of both the Home and Oggcultist states were visually inspected.
- Oggcultist was started as a real child desktop process in Linux virtual-display testing; it remained alive and responsive after startup.
- The original Rune artwork, fonts, animation data and user configuration formats were kept intact; no mass refactoring was undertaken.
- Native physical Windows 11 and Linux Mint testing is still outstanding. Media codecs and audio hardware on the user's machine have not been independently verified.
- The Oggcultist section does **not** embed its entire multi-window desktop interface inside Marble Oracle. It opens the complete independent Oggcultist program to avoid fragile Tk root and media lifecycle changes.
