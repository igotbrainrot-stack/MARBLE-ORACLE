# MARBLE ORACLE — TABS RELEASE

**Windows:** Extract the full ZIP, open the `Marble_Oracle` folder, then double-click `Marble_Oracle.pyw`. Python 3 and Tkinter are required.

**Linux Mint:** Extract the full ZIP, open the `Marble_Oracle` folder, and use `install_linux_desktop.sh` to install the application-menu shortcut. For diagnostics, run `./Marble_Oracle_Linux.sh` in a terminal. Python 3 and Tkinter are required.

Tabs at top left: **HOME** (five-panel dashboard), **PASSPHRASE** (the original five-card generator), and **OGGCULTIST** (launches the bundled complete Oggcultist in its own desktop window). Use HOME to return to the dashboard. Oggcultist remains running separately until you close its window.

Bottom controls: WIRE on THE WIRE, TONGUE on DEAD TONGUE, CUT on THREE CUTS, and GRADE at the left of the status/footer. The physical CRT chin keys still work in CRT V2 mode.

See `TAB_NAVIGATION_CHANGELOG.md` for a full changelog and testing/limitations.

## Updated Oggcultist tab (2.0.6)

The OGGCULTIST tab now runs the **full Oggcultist 2.0.6 interface inside Marble Oracle**, rather than opening a separate window. Its Library, Artists, Albums, Playlists, Converter, Album Art and Settings sections, plus the persistent player bar, are all available within the tab.

**HOME** hides Oggcultist but preserves its running state (music and conversions continue). The program is closed cleanly when the entire Marble Oracle suite exits; an active conversion must finish or be cancelled first.

The complete standalone Oggcultist source and launcher are still bundled under `Marble_Oracle_App/Oggcultist/`. A standalone launch is available as a recovery option if the embedded UI cannot load.

**Dependencies:** Python 3, Tkinter, Pillow and Mutagen. Install Oggcultist requirements with `python -m pip install -r Marble_Oracle_App/Oggcultist/requirements.txt` (using the same Python interpreter as the suite). FFmpeg/FFplay is required for media processing and playback. Linux Mint also needs `python3-tk`; use its graphical launcher as before.
