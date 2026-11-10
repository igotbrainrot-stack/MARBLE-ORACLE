# Marble Oracle — Official Integrated Suite

This package contains the complete Marble Oracle application, including the embedded Oggcultist 2.0.6, Passphrase, Tarot/Rune animations, bundled assets and Uberata Clear.

## Start

- **Windows 11:** double-click `START MARBLE ORACLE - WINDOWS.vbs` at the top level. Windows requires Python 3 with Tkinter.
- **Linux Mint:** use `START MARBLE ORACLE - LINUX.sh` at the top level; mark it executable if your extractor removed permissions (`chmod +x`). Linux requires Python 3 and `python3-tk`. You may need to tell your file manager to run executable scripts rather than open them in an editor.
- The initial setup window asks permission before installing additional Python packages into a private environment. Multimedia tools may need to be installed through the OS package manager.

## Folder overview

`Application/Runtime/` — complete working Oracle source, embedded Oggcultist source, fonts, pictures, audio, Rune and Tarot animations, and setup manager.

`Application/Documentation/` — setup notes, historical release notes, detailed handovers and implementation reports.

`Application/Tests/` — regression tests and instructions.

The original source folder inside Runtime is intentionally preserved to avoid breaking its existing asset and import paths. Developer/alternate launchers remain inside Runtime rather than cluttering the top-level folder.

## Notes

This is a Python application distribution, not a self-contained compiled Windows executable. The integrated Oggcultist player/converter may also require FFmpeg/FFplay/FFprobe. No automatic system-wide installation occurs without your permission.


## Startup repair
The official top-level launcher checks requirements **every time** and confirms the real Oracle GUI has started before closing setup. Missing Python/media dependencies lead to a consent-based installer. See `OFFICIAL_LAUNCHER_REPAIR.md`.
