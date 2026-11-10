# Marble Oracle — Refined Classic Edition

This package preserves the original five-panel display: archive and Latin on the left, Wire at centre, markets and tarot on the right. The previously removed sponsor feature remains absent. Uberata Clear is bundled and used for the application interface.

## Linux Mint
Install `python3` and `python3-tk` if missing. In the extracted application folder run `./install_linux_desktop.sh` once to add **Marble Oracle** to the Mint application menu. It opens the graphical program without a terminal. For troubleshooting run `./Marble_Oracle_Linux.sh` from a terminal. The original CRT hardware mode is available with `./Marble_Oracle_Linux_Original_CRT.sh` and additionally requires Pillow (`sudo apt install python3-pil python3-pil.imagetk`).

## Windows 11
Install Python 3 with Tkinter and the **Python Launcher for Windows**. Double-click `Marble_Oracle.pyw` to launch without Command Prompt, or `Launch_Marble_Oracle.vbs` if the Python Launcher supports `pyw`. The `.bat` file is a troubleshooting launcher (and opens a console). The default uses the modern original layout.

## Troubleshooting
Startup failures are recorded in the user state folder as `startup_error.log` when possible. Linux: `~/.local/state/Marble_Oracle/`. Windows: `%LOCALAPPDATA%\Marble_Oracle\`. To test: `python3 Marble_Oracle_App/oracle_bootstrap.py --selftest --no-network --no-bezel --os-frame` on Linux, or `py -3` on Windows. Never delete the user-state folder during updates: it contains preferences and cached media.

## Caveats
Tests conducted on this build use a Linux virtual display, not a physical Windows 11 or Linux Mint installation. Native Windows audio loopback, desktop environment integration, and external feeds require real-machine acceptance testing. This is a Python source distribution, not a standalone executable.

## Tarot / Runes animation
The right-hand THREE CUTS panel has a **TAROT / RUNES** toggle. Choose RUNES, click DRAW THREE, and three distinct stones turn over in sequence. Click any revealed stone for its interpretation. Switch to TAROT at any time to return to the original cards. Rune animation details are in `RUNE_ANIMATION_HANDOVER.md`.
