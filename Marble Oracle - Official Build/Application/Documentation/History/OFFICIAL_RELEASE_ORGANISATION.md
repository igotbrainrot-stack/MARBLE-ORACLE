# Official file organisation — 2026-11-09

This release was reorganised from the latest first-run requirements / Oggcultist 2.0.6 integrated build.

- Top-level visible items: two graphical launch scripts and one `Application` folder.
- Original application source, artwork and module relative paths preserved under `Application/Runtime`.
- Moved 25 existing root documentation and inventory files to `Application/Documentation`.
- Moved four developer regression tests to `Application/Tests`; import paths updated to run from the new location.
- Fixed Windows and Linux root launchers to target the runtime setup manager from its new location.
- Removed 0 generated Python cache files/folders from the *release copy*; no user data or core assets removed.
- Original embedded Oggcultist folders, Rune/Tarot archives, fonts, and dependencies were not reorganised internally to avoid breaking resource paths.

Known limitations: Windows launching needs native verification; audio playback, conversion, live market access and real installation downloads are not verified by packaging tests. Python 3/Tkinter are base prerequisites, and Linux FFmpeg may still require OS installation.

## Tested after reorganisation

- Oracle GUI self-test passed under Xvfb.
- Tab-layout tests passed in normal, retro and flat modes.
- Embedded Oggcultist opened all seven pages and preserved state across tabs.
- Settings/rune/font/tarot regression passed.
- First-run probe detected installed and missing dependencies; no packages were installed in these tests.
