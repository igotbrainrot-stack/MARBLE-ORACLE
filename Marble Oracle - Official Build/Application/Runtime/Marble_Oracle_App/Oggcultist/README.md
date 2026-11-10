# Oggcultist 2.0.6 — Approved O/G/G identity

A local-first music player, safe FLAC→Opus converter and album-art editor for Windows and Linux.
Your original audio files are never changed.

## What's in the ZIP

```
Oggcultist-2.0.6/
├── WINDOWS LAUNCHER.bat     start Oggcultist on Windows
├── LINUX LAUNCHER.sh        start Oggcultist on Linux
└── Oggcultist/              the whole program (this README is in here)
```

Keep the launchers next to the `Oggcultist` folder. The private Python environment (`.venv`) the
launchers create on first run also goes inside `Oggcultist`.

## Run on Windows 11

1. Extract the **entire** ZIP to a new folder. Do not run it from inside the ZIP.
2. Double-click **`WINDOWS LAUNCHER.bat`**.
   - If no Python 3.10+ with Tkinter is found, it offers to install **Python 3.12** for you (from
     python.org, through Windows' own `winget`, for your user only; no administrator rights). Press **Y**.
   - It then sets up its private environment and downloads Mutagen and Pillow (internet needed once).
3. If the window does not open, run **`Oggcultist\DIAGNOSE_WINDOWS.bat`** and keep the log it writes.

If `winget` is not available (very old Windows 10), install Python from
https://www.python.org/downloads/windows/ (leave “tcl/tk and IDLE” ticked) and start again.

## Run on Linux Mint

1. Extract the ZIP, double-click **`LINUX LAUNCHER.sh`** and choose **Run in Terminal**.
2. On the first start it lists the standard packages Mint leaves out (`python3-tk`, `python3-venv` and
   `ffmpeg`, whichever are missing), asks **Install them now? [Y/n]**, and installs them with `sudo apt-get`
   after your password. If you chose plain **Run** instead, the same question appears in a window and the
   password is asked by the system's password dialog.
3. It then sets up `Oggcultist/.venv` and downloads Mutagen and Pillow (internet needed once).

Every start is logged to `Oggcultist/launcher-log.txt`. If double-clicking opens the file as text:
right-click it → Properties → Permissions → tick “Allow executing file as program”, or open a terminal in
the folder and run `bash "LINUX LAUNCHER.sh"`.

Playback needs FFplay and conversion needs FFmpeg; Oggcultist asks before downloading FFplay on Windows and
never downloads anything silently. Command-line help: `python launch.py --help` inside `Oggcultist`.

Your settings and playlists are kept in your user profile (`%APPDATA%\Oggcultist` on Windows,
`~/.config/Oggcultist` on Linux), so they carry over when you extract a newer version. To keep them inside
the program folder instead (for a USB stick), create an empty folder `Oggcultist/OggcultistData`; existing
settings are copied there, never moved.

## Brand replacement and future suite integration (v2.0.6)

- The **user-approved triple-G emblem** and matching OGGCULTIST wordmark now appear in
  the sidebar and the app/window/desktop icons. The approved PNG/SVG/ICO assets are included
  under `branding/approved-ogg` and `branding/original-identity`.
- The existing Uberata Clear v3.0 font and all player, converter and album-art functionality are retained.
- For a larger program suite, see `suite_integration/README.md` and
  `oggcultist/suite_bridge.py` for a standalone child-window adapter. This is a
  **separate process** integration, not a native tab/widget embedding.
- Full handover and acceptance checklist: `CLAUDE_SUITE_HANDOVER_v2.0.6.md`
  (included in the Claude-Handover archive).

## What the 2.0 series introduced

- **Typography:** Uberata Clear v3.0 exclusively for interface text, headings,
  ordinary sidebar labels and new album covers. The approved geometric OGGCULTIST wordmark is rendered as original artwork (not a replacement UI font). Its verified TTF and licences ship
  within the application, with no first-run ZIP discovery or user installation.
- **Ember design system:** reusable colour, spacing, typography and motion tokens.
- **Sidebar:** readable navigation and compact icon rail on narrow windows.
- **Pages:** library actions, search, restructured Settings, playback controls.

Settings, playlists, album-art designs and the music folder from 1.9.x carry over.
Old font-choice preferences (`heading_font`, `body_font`) are ignored.

## Your music is protected

The source library and originals are never deleted or overwritten by conversion, and an existing output is
never overwritten silently. Previews and dry runs stay non-destructive.

## Limitations

This is a **runnable Python source application**, not a Windows `.exe`. Version 2.0.0 was tested on Linux
(Python 3.12, Tk 8.6, Xvfb) only; native Windows start-up, high-DPI scaling and font registration on real PCs
still need checking on Windows. The fonts cover Latin, common accents, numerals and a set of symbols, not
every script; album covers fall back to a system serif for other scripts.


## Version 2.0.5: all typography is bundled Uberata Clear v3.0

**Uberata Clear v3.0 is the only UI font**. Every GUI text role (including
headings, sidebar, lists, settings, playback and song metadata), the
sidebar wordmark and newly generated album covers uses this family.
The supplied `Uberata-Clear.ttf` is now bundled at
`oggcultist/resources/fonts/Uberata-Clear.ttf`, with the SIL OFL licence and
Noto attribution. No font ZIP in Downloads, manual import, network download,
font-source build or global installation is needed. The font is registered
privately when Oggcultist starts, even from a fresh extracted folder.

The Converter source/destination and Library folder choosers still use Windows
Explorer's folder dialog or Linux Mint's GTK picker (Zenity/YAD), with safe
fallbacks. The patched Linux Mint launcher remains executable; running
`bash "INSTALL_LINUX_MINT_MENU.sh"` once adds a menu entry.

Windows: double-click `WINDOWS LAUNCHER.bat`. It opens the windowless GUI and
exits the command window. Diagnostic console: `Oggcultist/DIAGNOSE_WINDOWS.bat`.

The app is distributed as a Python source program, **not a standalone EXE**.
