# Marble Oracle × Oggcultist 2.0.6 — Integration handover

## Changes
- Replaced the older bundled Oggcultist with the complete user-supplied Oggcultist 2.0.6 program (source, artwork, assets, fonts, tests and optional standalone launchers).
- Embedded Oggcultist's *actual* seven-page Tk interface in the OGGCULTIST tab: Library, Artists, Albums, Playlists, Converter, Album Art, Settings, and its persistent now-playing bar.
- Refactored the Oggcultist 2.0.6 Tk app class into shared UI logic with `OggcultistApp` (unchanged standalone Tk root) and `OggcultistEmbeddedApp` (Frame hosted inside Oracle). This avoids a second desktop window during normal tab use.
- `oracle_ogg_tab.py` creates the embedded Oggcultist UI and adds BACK TO HOME. A standalone launcher remains for error recovery.
- `marble_oracle.py` caches the Oggcultist tab instance: HOME and PASSPHRASE hide it rather than destroying it, preserving player, library, conversion and settings state. Suite exit requests clean Oggcultist shutdown and protects ongoing conversions.
- Oggcultist's window-specific animation logic now supports a Frame hosted in Oracle. Global keyboard actions are scoped to Oggcultist descendants while its tab is active.
- Media event and converter polling callbacks are explicitly cancelled at shutdown to avoid Tk callbacks firing after the parent is destroyed.

## Files changed
- `Marble_Oracle_App/oracle_ogg_tab.py`
- `Marble_Oracle_App/marble_oracle.py`
- `Marble_Oracle_App/Oggcultist/oggcultist/gui/app.py`
- `Marble_Oracle_App/Oggcultist/oggcultist/gui/{converter_view,art_view,media_keys}.py`
- `Marble_Oracle_App/Oggcultist/` — complete Oggcultist 2.0.6 program
- `Marble_Oracle_App/{WINDOWS LAUNCHER.bat,LINUX LAUNCHER.sh,INSTALL_LINUX_MINT_MENU.sh}` — optional standalone Oggcultist wrappers from original release
- `test_ogg206_embedded.py` — regression test

## Preserved
Original Oracle five-panel HOME layout, HOME/PASSPHRASE/OGGCULTIST tabs, GRADE on right, WIRE/TONGUE/CUT positions, Tarot/Rune art/animations, bright ASCII, Uberata Clear and retained original features. Existing per-user Oggcultist config and libraries are read from their normal paths; no migration or deletion is performed.

## Verified in Linux virtual display
- Oracle GUI self-test: pass.
- Three layout tab-position tests: pass.
- New Oggcultist embedded integration: seven pages, visibility, HOME ↔ PASSPHRASE ↔ OGGCULTIST, same live instance: pass.
- Oggcultist standalone 2.0.6 window launches and closes: pass.
- Oggcultist targeted tests: suite bridge 8 passed; bundled Uberata 5 passed; core 14 passed.
- Full historical Oggcultist test suite was not completed. One old test expects obsolete pre-Uberata fonts, so it is not compatible with the 2.0.6 font policy. The first large suite run stalled and was terminated; do not describe the entire suite as passing.

## Limitations / next QA
- Native Windows 11 and physical Linux Mint testing still needed, especially media keys, audio devices, FFmpeg conversion and the compact CRT-bezel viewport.
- Oggcultist 2.0.6 requires its listed dependencies (`Oggcultist/requirements.txt`, chiefly Pillow and Mutagen). They are not vendored into this source distribution.
- In compact CRT layouts, Oggcultist's responsive UI is rendered inside the available instrument screen; some long converter workflows benefit from a larger Oracle window or the original standalone Oggcultist launcher.
- Older changelog files describe historical external-launch behaviour and are superseded by this document.
