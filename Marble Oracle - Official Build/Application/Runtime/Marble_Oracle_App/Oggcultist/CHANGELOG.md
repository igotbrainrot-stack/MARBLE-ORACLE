# Oggcultist v2.0.6 — Approved Triple-G Branding Integration

## 2.0.6 — Approved triple-G icon and wordmark

- Replaced application branding with the user's approved triple-G/O logo and matching OGGCULTIST lettering.
- Added multi-size Windows ICO, Linux PNGs, and outlined SVGs with the approved geometry.
- Updated full and compact navigation branding, window/taskbar icon and packaging metadata, preserving Uberata Clear for ordinary UI text.
- Kept the v2.0.5 media player, Opus converter, launchers, user settings and safety behaviour unchanged.
- Original screenshot and brand integration instructions included for independent review.


- Replaced rejected knot logo with user-approved no-spikes O/G/G angular emblem.
- Shipped exact raster-derived wordmark art alongside matched icon assets and contour-traced SVGs.
- Regenerated Windows multi-resolution icon, runtime PNGs and Linux menu mark.
- Updated sidebar to display the approved wordmark instead of synthesizing new letterforms.
- Kept Uberata Clear v3.0 as the sole user-interface typeface; no playback or conversion code changed.
- Updated the asset generator to regenerate only the approved identity.

# Oggcultist v2.0.5 — Uberata Clear bundled font release

- Based directly on the last v2.0.4 Linux-launcher-fixed program.
- Embedded the user-supplied Uberata Clear v3.0 TTF (verified SHA-256) with OFL and Noto source attribution.
- Every active UI font role uses Uberata Clear; retained the already implemented dynamic Uberata sidebar wordmark and cover text.
- Removed the runtime Downloads ZIP discovery dependency and stale cached-font priority.
- Extended packaging checks to fail if the TTF is missing, wrong or replaced with another font.
- Preserved the Linux Mint executable launcher and application-menu installer.
- Left playback, conversion and folder-picker behaviour unchanged.

# Changelog

## 2.0.4 — Uberata-only interface and native folder choosers

- Continued from the supplied v2.0.3 source ZIP. No older branch or interface was substituted.
- Uberata Clear v3.0 is the only UI and new album-art typeface; removed bundled old font binaries.
- Added automatic private verification and caching from the user's Uberata v3.0 release ZIP.
- Windows conversion input/output and music folder pickers use the Explorer-style IFileOpenDialog.
- Linux Mint GTK desktops use Zenity/YAD file selectors; KDE and Tk fallbacks remain.
- Normal Windows batch startup closes CMD after launching the windowless player; troubleshooting retains a console.
- No changes to converter write safeguards or music playback logic.

## v2.0.3 — Requirements installed on first launch (8 November 2026)

Reported on Linux Mint with 2.0.2: "sudo apt install python3-tk python3-venv python3.12-venv" was needed.

- **Linux:** on first launch `LINUX LAUNCHER.sh` installs the missing system packages itself (python3-tk,
  python3-venv, the versioned python3.X-venv when the distribution has one, and ffmpeg when FFplay/FFprobe
  are missing). It asks once first: in a terminal `Install them now? [Y/n]` then `sudo`; when double-clicked,
  a window asks and the system password dialog (`pkexec`) installs, with a progress window. If apt-get
  fails it refreshes the package lists and tries again. Declining installs nothing and shows the command.
- **Windows:** `WINDOWS LAUNCHER.bat` looks for Python 3.10+ with Tkinter (py launcher, PATH and the standard
  install folders). If there is none it offers to install Python 3.12 from python.org through `winget`, for
  the current user (no administrator rights), after a Y/N question, and then carries on.
- Both launchers rebuild a private environment that is broken or lacks Tkinter, and only download Mutagen
  and Pillow when they are missing.

## v2.0.2 — Linux launcher that explains itself (8 November 2026)

Reported: 2.0.1 did not launch on Linux Mint, with no visible error.

- `LINUX LAUNCHER.sh` now checks, before doing anything, for Python 3.10+, Tkinter (`python3-tk`) and the
  venv module (`python3-venv`), and names the exact `sudo apt install ...` command when one is missing.
- A half-made `Oggcultist/.venv` from an earlier failed start (the usual result of a missing
  `python3-venv`, which then broke every later start) is detected and rebuilt.
- Errors no longer vanish: in a terminal it waits for Enter; when double-clicked without a terminal it
  shows the message in a window (zenity, kdialog or a notification). Every start is logged to
  `Oggcultist/launcher-log.txt` (the previous one is kept as `launcher-log.old.txt`).
- Mutagen and Pillow are only downloaded when missing, so later starts work offline.
- README: Mint steps, and what to do if double-click opens the launcher as text.

## v2.0.1 — Tidy folder layout (8 November 2026)

- The ZIP now holds three things: `WINDOWS LAUNCHER.bat`, `LINUX LAUNCHER.sh` and an `Oggcultist` folder with
  the whole program. The launchers switch into that folder, so the private Python environment (`.venv`) is
  created inside it too.
- `run_windows.bat` became `WINDOWS LAUNCHER.bat` and `run_linux.sh` became `LINUX LAUNCHER.sh`, next to the
  folder. Both stop with a clear message if the `Oggcultist` folder is not beside them.
- `LINUX LAUNCHER.sh` is now marked executable (1.9.13's `run_linux.sh` was not, so `./run_linux.sh` failed).
- `DIAGNOSE_WINDOWS.bat` stays inside the folder and calls `..\WINDOWS LAUNCHER.bat --console`.
- Release builder places the launchers outside the program folder and checks nothing else is there.
- README: start-up steps for Windows 11 and Linux Mint.

## v2.0.0 — “Ember” redesign (7 November 2026)

Built from the uploaded 1.9.13 program, following the approved audit and redesign plan.

**Fixes**
- Fonts ship ready-made (Uberfonto Refined Regular; Oggcultist Interface Regular and Bold) with SHA-256 pins.
  Nothing is generated at first launch; `fontTools` and `shapely` are no longer runtime requirements.
- 1.9.x settings with `heading_font` / `body_font` values that no longer exist start normally (1.9.13 could
  raise "Heading font could not be loaded" when switching). If fonts cannot be registered, the status line
  says so instead of a console-only message.
- Version metadata is consistent again (1.9.13 shipped `version_info.txt` saying 1.9.11).
- Album covers with every line left empty are a plain colour again, as the cover editor promises.
- Tertiary and disabled text raised from 2.6–2.9:1 to at least 4.3:1 contrast (#928174; 3.7:1 on disabled
  amber buttons).
- Release builder: the Program ZIP carries the fonts and leaves out the Claude handover and retired brand
  kits; it checks three fonts are present and byte-exact.

**Design (Ember tokens, Forge typography)**
- `gui/design_system.py` is the single source for colour roles, type scale, 4 px spacing, layout sizes, radii,
  bevels and motion; `theme.PALETTE` is derived from it.
- Display face only for page titles, the now-playing title and covers; section and card titles use bold
  Interface. Amber is reserved for the primary action, playing state, progress and focus.
- Sidebar: 208 px with line icons and group labels; a 64 px icon rail below 1100 px. Minimum window 960×600.
- Search field with icon and placeholder; Library gets Play all, Shuffle and Add to playlist in one row.
- Settings rebuilt as cards (Appearance, Playback, Fonts, Music folder, About), two columns when wide.
- Player bar: shuffle, repeat (with its mode name) and volume as icons; 64 px cover.
- Table headings in small capitals.

**Code**
- `player_view.py` (1,063 lines) split into `player_view.py`, `now_playing.py` and `collection_pages.py`.
- New `line_icons.py` (Pillow-drawn icons, no icon font).

**Tests**
- Removed font tests for features that no longer exist (test_v186_font, test_v187_fonts, test_v191_fonts,
  test_v192_bundle, test_v193_font_bootstrap, test_v193_fonts, test_v1911_original_typography,
  test_v195_titles, test_v197_aero); their still-relevant checks are rewritten in `test_v200_ember.py`.
- Updated tests that described deliberately changed behaviour: repeat button text, heading sizes, font
  bundle size, font warning, sidebar width/rail, Album Art layout at 960×600.

## v1.9.13 — Layout refresh, stronger typography and cover-art alignment (7 November 2026)

- Used the uploaded v1.9.11 program as the baseline and refined it instead of reverting to an older build.
- Rebalanced the desktop shell with a wider sidebar, larger display-type navigation, roomier spacing and a broader default window size for a friendlier first impression.
- Refined the top bar so search has more room and status text sits more cleanly in the available width.
- Increased the presence of the Oggcultist heading system so titles, section labels and branding feel less bland and more intentional.
- Reworked generated album-art text layout: the first line now prefers the Oggcultist Display face, supporting lines prefer the Oggcultist Interface family, and line fitting/centering was tightened to avoid uneven sizing and awkward alignment.
- Preserved existing playback, conversion and file-safety behaviour.

## v1.9.11 — Original Oggcultist Typeface System (7 November 2026)

- Built five original geometric TTF faces from new glyph outlines; 353 Unicode mappings per face.
- New Display Regular/Bold default for headings/album covers and Interface Regular/Medium/Bold for regular text.
- Rebuilt O-G-G knot, outlined wordmark, sidebar logo and Windows icon from original SVG paths.
- Automatic local source-to-TTF compilation and private registration on first launch; no user font import required.
- Kept historical font selections optional when available; added original-font previews and export options.
- Adjusted sidebar vertical padding to keep Settings reachable at 960x600 with new metrics.
- Preserved v1.9.9 GUI, playback, converter and file-safety behaviour.

## Earlier versions



## 1.9.9 — Visual system and interface redesign

- Rebalanced sidebar navigation with grouped collections/workspace, consistent padding and controlled heading size (no forced oversized text).
- Increased readability of dense music tables: clear bold column headings, comfortable row heights and clearer text contrast.
- Established reusable typography, spacing, buttons and layout tokens in `gui/design_system.py`.
- Redrew the logo and app icon from editable clean SVG source; simplified 16–48 px icons; retained the O/G/G knot, three-pronged lower link and ember.
- Rebalanced search/status area with responsive helper text, improved now-playing spacing, converter labels, album art and settings alignment.
- Introduced distinct destructive action appearance for playlist deletion, retaining all behaviour and keyboard shortcuts.
- Bundled original Aero, Legacy and Uberata font binaries unchanged; no import required.

---

# Changelog

## 1.9.8 — 7 November 2026: larger full-width sidebar tab titles

- Enlarged Library, Artists, Albums, Playlists, Converter, Album Art and Settings tab labels. The common font size is chosen from the available sidebar width using the actual selected font metrics, so the longest label nearly fills the sidebar without clipping.
- Removed ttk's implicit button-width reservation and reduced left/right padding. Buttons still occupy the full sidebar width, and Settings remains visible at the 960×600 minimum window size.
- Switching between Uberfonto Aero v6.7 and the old v5.3 edition recalculates the sidebar label size immediately.
- New sidebar regression tests and screenshots. No changes to playback, conversion, cover art, font binaries, controls or stored data.


## 1.9.7 — 7 November 2026: Uberfonto Aero v6.7

- The default heading and new album-cover font is now **Uberfonto Aero Main v6.7 — Clear Cuts**, from the user's most recent archive (supersedes the earlier v6.2 upload).
- The main font has internal family name `Uberfonto` and 507 encoded characters, with widened diagonal negative-space cuts in the updated glyph outlines. The old selectable heading alternative remains **Uberfonto Legacy v5.3**.
- **Uberata Clear v3.1** remains the body text default.
- Added automatic, hash-verified offline loading of the user's existing `Uberfonto-Aero-v6.7-Clear-Cuts-Complete*.zip` from the application folder or Windows Downloads folder; private cache only, no system font installation.
- Settings displays the correct release name; **Save Uberfonto (NEW)** exports the active v6.7 font after its local preparation. Existing album covers are not edited.
- This *patch/source handover* intentionally contains no font binaries; apply the patch over an extracted v1.9.6 installation, preserving its older fonts, and retain the v6.7 user-provided release ZIP locally. A full rebuild can bundle fonts when the user's release files are available to the builder.
- No changes to playback, converter, Stone Knot icon, 38° bevel, rounding, title sizing, or data formats.

## 1.9.6 — 7 November 2026: 38° bevel and tighter corners

- The raised/sunken bevel edges now use a layered, antialiased profile: a nominal 2 px rise
  at **38 degrees** gives an approximately 2.56 px bevel run. The resulting rim is sharper,
  with a defined top-left highlight and lower-right shadow and an unchanged flat interior.
- Corner rounding is reduced across buttons, cards, navigation, text fields, check boxes,
  scrollbars, swatches, artwork previews and converter status chips. Slider tracks are less
  pill-shaped; circular seek and volume knobs are preserved.
- The colour palette, animation, fonts, player and converter are unchanged. The requested
  additional Uberata replacement could not be applied because no new font file accompanied
  the instruction. **Uberata Clear v3.1 remains bundled** pending receipt of the replacement.
- Added `tests/test_v196_bevel.py`. GUI testing performed on Linux, not native Windows.


- Page titles increased by 4 pt (now body size +16 pt).
- Section and card-section headings increased by 2 pt (now body size +4 pt).
- Now-playing song title increased by 3 pt (now body size +6 pt), using existing width-aware ellipsis to avoid clipping.
- The sidebar's text-only brand fallback increased by 2 pt (now body size +9 pt). The Stone Knot image logo is unchanged.
- Song-list text, table-column labels, navigation, buttons, search and metadata fields stay at their previous sizes.
- The default Uberfonto (NEW) v6.1 and Uberata (NEW) v3.1 remain bundled. Uberfonto (OLD) stays selectable; font exports are unchanged.
- No playback, converter, library-data, launcher or album-art changes.

## 1.9.4 — 7 November 2026: Windows launch recovery and complete font bundle

- Fixed the previous **Bootstrap Program** ZIP that omitted all three custom font
  binaries and could fail at startup when the original release archives were
  not available. The runnable program distribution now bundles all three TTFs
  and SIL OFL documents directly; no font import step is needed.
- `run_windows.bat` now launches `Oggcultist.pyw` through its supervised
  windowless startup instead of launching `launch.py` without monitoring.
  Startup errors are logged and shown in a Windows dialog.
- New double-click `DIAGNOSE_WINDOWS.bat` keeps startup console output visible.
- Unexpected Windows/Tk private-font registration failures now warn visibly and
  let the player open instead of aborting the GUI. The release build still
  refuses to ship if any required bundled font is missing.
- Default headings Uberfonto Refined v6.1, text Uberata Clear v3.1; alternate
  Uberfonto Legacy v5.3; retired old Uberata remains absent. Font files and
  licence notices can still be exported from Settings.
- No changes to music conversion, playback or existing user data.

# Changelog

## 1.9.3 — 7 November 2026: fonts included in runnable distribution

- Fixed the previous **source-only ZIP** expectation by requiring compiled font files in the release-builder output. A source-only bootstrap now auto-detects the user-owned font release ZIPs in Downloads and prepares the custom fonts privately, without the Settings import workflow.
- The new defaults remain **Uberfonto Refined v6.1** (headings and new album covers) and
  **Uberata Clear v3.1** (all other UI text). The old Uberfonto v5.3 is an alternative in Settings.
- Startup checks that all bundled fonts are available to Tk. Missing fonts now result in an
  actionable error instead of silently substituting system fonts. Settings displays the
  actually active font families.
- Added a reproducible source distribution builder that validates font resources and the
  resulting archive. Music conversion/playback code is unchanged.
- Existing user-selected OLD heading preferences remain respected; Settings can select NEW.
  Existing embedded album covers are not rewritten automatically.

## 1.9.0 — 7 November 2026: modern sliders, rounded and bevelled edges

- **New sliders** for seeking and volume:
  - a slim, rounded groove;
  - the part up to the thumb is filled with the amber gradient, which drifts with the rest;
  - a round, shaded cream knob with a black rim and a soft shadow;
  - **hover:** the groove thickens and the knob grows, with a soft amber halo; it shrinks back
    when the pointer leaves;
  - **click anywhere** to jump there, as before; drag; or use the arrow keys, Home/End and the
    mouse wheel when it has focus.
- **The converter's progress bar** matches: a rounded groove filling with the gradient.
- **Slight rounding with a bevel on every surface.** Raised parts are lit along the top and left
  and shaded along the bottom and right; sunken parts are the reverse.
  - Buttons, chips and the gradient buttons gained the bevel.
  - Cards (the converter's Folders panel and its details box) are rounded and bevelled.
  - The sidebar's hover and current-page panels are rounded. The current-page marker is now a
    rounded gradient pill.
  - Text boxes and drop-downs are rounded and sunken, with a lighter rim on hover and an amber
    rim when focused. The drop-down arrow no longer sits in its own box.
  - Tables sit in a rounded, sunken frame.
  - Scrollbars are slim rounded thumbs without arrow buttons (lighter on hover, amber while
    dragged).
  - Check boxes are small rounded boxes with a tick.
  - The cover in the player bar, the Album Art preview and the colour swatches have rounded
    corners.
- The player bar and the window edges stay square, since they run edge to edge.

## 1.8.9 — 7 November 2026: moving gradients, animated buttons, bigger headings

- **The gradient slowly drifts.** Everything drawn with the amber → reddish-orange gradient
  slides slowly down its gradient towards red and back up to amber, once every 8 seconds, easing
  at each end. That covers:
  - the accent buttons (**Play all**, **Scan source**, **Convert**...);
  - the play/pause button;
  - the ⏮ ⏭ ■ icons;
  - the marker on the current page in the sidebar;
  - the line above the player bar.

  The drift frames are prepared in the background after start-up, so start-up isn't slower.
  The drift pauses while the window is minimised.
- **Buttons animate:**
  - **Hover:** every button fades into its hover look over about 0.1 s, and fades back out
    when the pointer leaves, instead of switching instantly.
  - **Press:** the label sinks by one pixel while a button is held down. Releasing gives a
    brief brighter flash before it settles.
- **Settings → Look → Animations** switches all of this off for a still interface (saved).
- **Bigger headings:**
  - page titles +4 pt;
  - section labels +2 pt;
  - the sidebar +1 pt;
  - the song title in the player bar +2 pt;
  - the sidebar wordmark fallback +2 pt.

  Table column headings keep their size, so tables don't lose a row.
- Settings: the Look and Playback options moved to the left column, under Fonts.

## 1.8.8 — 7 November 2026: one font each for headings and text

- **Uberata Clear is now the only font for non-heading text**: buttons, labels, messages, song
  lists, tables and text fields. Uberata (the version with blackletter capitals) and Uberata
  Display were removed from the app and from **Save font files...**.
- **Uberfonto Refined Regular is now the only heading font.** The Bold file was removed.
  Headings and album covers use Regular exactly as drawn: Oggcultist doesn't ask for a faked
  bold.
- The **Settings** page now lists and saves just these two fonts. The licence saved with Uberata
  Clear (`OFL-Uberata-Clear.txt`) now carries the Noto Serif copyright it's derived from,
  instead of Pirata One's.
- The accent fix for Uberata from 1.8.7 (`packaging/fonts/fix_uberata_accents.py`) is gone
  with the font it fixed. Uberata Clear never needed it.
- **Player bar:** a long artist/album line or song title is now cut to the space available
  and ends in "...", instead of being clipped mid-letter.
- Existing albums keep their covers. To give an album the Regular lettering, use **Apply to
  album** on the Album Art page.

## 1.8.7 — 7 November 2026: two fonts, and a Settings page

- **Headings now use Uberfonto Refined v5.3**, the traced-glyph release, and nothing else does,
  as its kit recommends. That covers page titles, section labels, the sidebar, column headings,
  the song title in the player bar and album covers. The two `.ttf` files are copied unchanged
  from the release, and their SHA-256 checksums match its manifest. The older "Uberfonto
  Reference" files have been removed.
- **All other text uses Uberata**, which you supplied as a build kit:
  - **Uberata** for buttons, labels and messages;
  - **Uberata Clear**, its plainer sibling, for song lists, tables and text fields, where the kit
    recommends it for readability.

  The kit contains no font files, so they were built with its own `build_uberata_v2.py`, which
  was not changed. The two open-licence fonts it needs, Pirata One and Noto Serif SemiBold, were
  downloaded from their official GitHub repositories (fonts only, nothing run). The kit's own
  12 tests pass on the result.
- **Fix to Uberata: accented capitals.** As built, Ä Ö Ü É Ç and similar capitals had their
  accent floating to the left of the letter, followed by a gap ("Ü bergröße"). The kit swaps in
  narrower blackletter capitals, but the accented ones still used the old widths and accent
  positions. `packaging/fonts/fix_uberata_accents.py` corrects the widths and accent positions
  of those 337 letters. No letter shapes were changed.
- **New Settings page** (sidebar, bottom; **Ctrl+7**):
  - **Fonts:** each of the five fonts in its own lettering, with where it's used.
  - **Save font files...** copies all five fonts into a new "Oggcultist Fonts" folder wherever
    you choose, together with their licences and a `HOW TO INSTALL.txt` for Windows. If that
    folder already exists, it makes "Oggcultist Fonts (2)" instead, so nothing is overwritten.
    **Open folder** then shows it. Oggcultist never installs fonts itself. You install them in
    Windows by right-clicking the files and choosing "Install", or "Install for all users".
  - **Playback:** the headset and keyboard media buttons can be switched off here. The change
    takes effect the next time Oggcultist starts.
- Tables have slightly less padding per row, so they show as many rows as before with Uberata
  Clear's taller lines.
- The few symbols neither font has (⇄ ↻) are borrowed from a standard font automatically, as
  before. The transport buttons are images, so they're unaffected.

## 1.8.6 — 6 November 2026: Uberfonto everywhere, bordered buttons

- **New font throughout: Uberfonto Reference** (SIL Open Font License, bundled with the app).
  - Every piece of text in the interface uses it: headings, lists, buttons, menus, text boxes
    and status messages. Bold text uses its Bold face.
  - It's loaded privately when Oggcultist starts and is never installed on your system. If it
    can't be loaded, the system font is used.
  - Interface text is one point larger than before, because this blackletter reads small.
  - The few symbols the font lacks (⇄ ↻ ⏩) are borrowed from a standard font automatically.
- **Album covers use Uberfonto too, with much larger text** (96/68/60 pt instead of 58/42/40).
  Long names still shrink to fit and end in "...". Text the font can't draw, such as Japanese
  or Arabic, still falls back to a font that can.
- **Existing albums keep their cover.** When new songs are converted into an album that's
  already in your library, they reuse that album's existing cover exactly, so one album never
  shows two styles. To give an existing album the new look, open it on the **Album Art** page
  and press **Apply to album**.
- **Black borders around buttons, and smoother edges.** Every boxed button has a black border,
  and "Rescan"-style buttons are now boxed too. Rounded corners and borders are drawn at four
  times the size and scaled down, so they're smooth instead of jagged. Keyboard focus is still
  shown with an accent border.
- "…" in the interface is now written as "...", because Uberfonto draws "…" as a single dot.

## 1.8.5 — 6 November 2026: subtler texture

- **Film grain halved.** It's still there, but much quieter: on the dark backgrounds it varies by
  about 2.7 brightness levels instead of 5.3, and on the amber buttons by 0.7 instead of 1.6.
- **The faint light mottle on dark areas is halved too**, to a lift of at most 4 levels (was 8).
- A single setting, `GRAIN` in `gui/textures.py`, now controls the overall strength (1.0 is the
  original 1.7.1 look; 0.5 now).

## 1.8.4 — 6 November 2026: Stone Knot logo

- **New logo: "Stone Knot".** A carved octagonal O with two angular G's woven into it, a
  three-pronged base and a flame, in stone (#D7B892) and ember (#C95A12). It replaces Ember
  Grooves:
  - the app and taskbar icon, including hand-simplified 16, 32 and 48 px versions;
  - the Windows icon file for the `.exe` (7 sizes, 16–256 px);
  - the sidebar logo (symbol + outlined "OGGCULTIST" wordmark), sized to the screen's DPI.
- The sidebar logo now keeps the symbol's own proportions instead of fitting it into a square.
- The Stone Knot kit, including its Runestone display font (SIL Open Font License), is kept with
  the project's brand files. The previous Ember Grooves kit is kept there too and can be restored.
- No behaviour changes.

## 1.8.3 — 6 November 2026: clean exit, no lingering console, dark window frame

- **FFplay no longer stays running after you close Oggcultist.**
  - Closing the window now ends playback at once and waits until FFplay and FFmpeg have
    exited. Before, closing straight after Stop left the fading FFplay behind.
  - FFplay is also told to exit as soon as its input ends, so it can't linger even if
    Oggcultist crashes.
  - On Windows, every playback process is tied to Oggcultist with a job object, so Windows
    ends them even if Oggcultist is ended from Task Manager.
- **`run_windows.bat` no longer leaves its console window open.** It prepares Python, opens
  Oggcultist with no console, and closes itself. First-run FFmpeg setup and any start-up
  problem appear in dialogs, and start-up errors still go to `startup-error.log`. For
  troubleshooting, `run_windows.bat --console` keeps the window open with all messages, as
  before.
- **Dark window frame on Windows.**
  - Windows 10 and 11: the title bar and border are dark instead of white.
  - Windows 11: they also use Oggcultist's own colours (a deep brown title bar, warm
    off-white title text, a dark brown edge).
  - This applies to Oggcultist's own dialogs too. Standard Windows message boxes and the colour
    picker follow your Windows theme.

## 1.8.2 — 6 November 2026: headset media buttons, firmer loops

- **Bluetooth headset and media-key control.** Play/pause, next, previous and stop buttons on
  headsets, earbuds and keyboards now control Oggcultist, even when it's in the background.
  - **Windows:** Oggcultist registers the system media keys. Windows delivers Bluetooth headset
    (AVRCP) buttons as these same keys. Nothing extra to install.
  - **Linux:** Oggcultist is a standard MPRIS media player on D-Bus. That's how desktops and
    BlueZ/PipeWire pass on headset buttons, and the desktop's media controls also show the
    current song, play/pause state, shuffle and loop. This needs the small pure-Python `jeepney`
    package, now in `requirements.txt` for Linux only. Without it, media keys work while the
    window has focus.
  - To leave the media keys to another program, set `"media_keys": false` in settings.json.
- **Loop One holds the song.** ⏭ and ⏮ (on screen, keyboard or headset) now just return to the
  start of the locked song; nothing moves on to another song until Loop One is turned off.
- **Loop Album uses the last song you selected.** It locks onto the album of the song you most
  recently clicked in a list or started playing. If something from another album is playing,
  that album starts when the current song ends, and the status line says so.

## 1.8.1 — 6 November 2026: smooth volume, loops that stay put

- **Smooth volume.** Dragging the volume slider now raises or lowers the sound continuously, with
  no glitches or dropouts. Oggcultist now passes the audio through itself, so it can set the
  level directly:
  - FFmpeg decodes the song;
  - Oggcultist applies the volume with a gentle ramp;
  - a single FFplay plays it.
  Before, every volume change restarted FFplay, which is what you heard.
- **Smoother everything else.**
  - Seeking, changing song and fast-forward swap only the decoder, with a 20 ms crossfade.
    There's no restart of the audio output and no click.
  - Songs that follow each other, including Loop One, join without a gap.
  - Pause fades out over 20 ms, and resume continues exactly where the sound stopped.
- **Loop Album locks onto the album playing when you turn it on.** Only that album plays until
  you change the setting. If you play a song from another album, playback returns to the locked
  album afterwards, and Next/Previous stay inside it.
- **Loop One locks onto the song playing when you turn it on.** Whenever a song ends, that song
  starts again, even if you pressed Next to hear something else in between.
- If a loop is turned on with nothing playing, it locks onto the next song you play. The status
  line names the locked song or album.
- No new software is needed: this uses the FFmpeg and FFplay you already have. Without FFmpeg,
  the previous FFplay-only playback is used automatically.

## 1.8.0 — 6 November 2026: album art editor, steady controls, live volume

### Album art editor (new **Album Art** page, Ctrl+6)
- Change the **background colour** and the **text** of the covers Oggcultist generates for each
  album:
  - set the colour with a colour picker, by typing a hex code, or with **Random**, which only
    picks unused colours;
  - edit up to three lines of text; empty lines are left out, and **Use album, artist and year**
    restores the default;
  - choose the **text colour**: automatic best contrast, black, white, or any custom colour.
- A **live preview** shows the cover exactly as it will be embedded, and the album list follows
  the search box.
- **Apply to album** checks the files, asks once, then updates the cover embedded in the album's
  songs. Your choice is also used for any songs you convert into that album later.
- **Safety:**
  - Only covers that Oggcultist itself generated, in files it converted and that haven't
    changed since (checked against the converter's records by size and checksum), are ever
    changed.
  - Real cover photos, files from elsewhere and edited files are listed and left alone.
  - Each file is updated on a temporary copy, and the copy must pass three checks before it
    replaces the original: the **decoded audio is bit-identical**, every other tag is unchanged,
    and the new cover is valid.
  - The converter's records are updated, so it still recognises every file as its own finished
    output.
  - Your original source music is never involved. If a song from that album is playing,
    playback pauses for a moment while it is updated.
- Every album keeps its own unique cover colour, because the converter uses the colour to
  recognise albums. If you pick a colour another album already has, a nearly identical shade is
  used and you're told which album has it.
- Text the cover font can't draw (for example ✦) is reported before anything is changed.

### Player
- **The music controls no longer move.** Play/pause sits at the exact centre of the bar, the
  other buttons keep fixed spacing either side, and nothing shifts when the song, its title
  length, or the shuffle/repeat state changes.
- **Volume follows the slider while you drag it**, not only when you let go. Changes are paced so
  playback stays smooth, and each one uses the gap-free handoff.

## 1.7.5 — 6 November 2026: hold to fast-forward, bold gradient controls

- **Hold ⏭ to fast-forward** through the song. You hear it sped up, and the progress bar races
  along. It starts at 4× after about a third of a second, goes to 8× if you keep holding, and
  returns to normal speed where you let go. A quick click still skips to the next song. Speed
  changes use the same gap-free handoff as seeking, so the sound never cuts out. Speed is
  pitch-corrected (FFmpeg's `atempo`), so voices stay recognisable.
- **Bold gradient controls.** ⏮ ⏭ ■ are now solid icons filled with the amber → reddish-orange
  gradient, brighter on hover and deeper when pressed. ▶/⏸ on the orange button is a matching
  bold dark icon.
- **Black outlines** around ⏮ ⏭ ■ and the play/pause button.
- Without Pillow, the buttons fall back to amber text symbols.

## 1.7.4 — 6 November 2026: shuffle, repeat and click-to-seek

- **Shuffle** (⇄, or Ctrl+S) plays every song in the list once, in random order, before any song
  repeats, and never plays the same song twice in a row.
- **Repeat** (↻, or Ctrl+R) cycles through four settings:
  - **off**: stop after the last song;
  - **all**: start the list again, with a fresh shuffle if shuffle is on;
  - **album**: keep playing the current song's whole album, in track order or shuffled, even when
    you started from a playlist or the full library;
  - **one**: play the current song again. Next and Previous still move on.
- Both buttons light up amber when on. The status line confirms each change, and your choice is
  remembered next time.
- **Previous** goes back through the songs you actually heard, so it works with shuffle.
- **Click anywhere on the progress bar** to jump straight to that point; dragging follows the
  pointer, and the time updates as you drag. Previously a click only nudged the position a step at
  a time. The volume bar works the same way.

## 1.7.3 — 6 November 2026: no more audio gaps when seeking or skipping

- **Seeking, changing the volume and changing track no longer cut the sound.** Previously the
  player stopped FFplay and then started a new one, leaving a silent gap while it opened the
  file and the audio device. Now the current audio keeps playing until the new position is
  actually audible, then switches over. Skipping quickly through several songs keeps playing the
  current song until you stop on one.
- **Accurate time display.** The elapsed time comes from FFplay's own audio clock instead of a
  stopwatch. Pausing and resuming now continue exactly where you paused instead of skipping ahead
  slightly each time. During a seek, the seek bar stays at the new position instead of jumping
  back.
- If a file can't be played, the status message now includes FFplay's own error text.

## 1.7.2 — 6 November 2026: Ember Grooves logo

- **New logo and app icon:** "Ember Grooves". A circular groove holds two interlocking g's and
  an ember flame, in the amber → reddish-orange gradient.
  - The window and taskbar icon now has hand-simplified versions for 16, 32 and 48 px.
  - The Windows icon file (used for the portable `.exe`) has seven sizes from 16 to 256 px.
- **Sidebar logo:** the mark and the custom-lettered "Oggcultist" wordmark replace the plain text
  title. It is sized for the screen's DPI. If an image can't be loaded, the text title comes back
  automatically.
- **Ember Grooves display font** (SIL Open Font License) is included with the project's brand
  files for future use. The app doesn't use it yet, so nothing needs installing.
- No behaviour changes; all settings, playlists and libraries carry over.

## 1.7.1 — 6 November 2026: warm dark theme with film grain

- **New warm dark theme.** Deep brown-black backgrounds with a subtle film grain and, on the
  darkest areas, a very faint light mottle. The sidebar, pages, cards, now-playing bar, buttons,
  navigation items, labels, check boxes and status chips are textured instead of flat colour.
- **Amber → reddish-orange gradient** on the coloured parts: Play all, Scan source, Convert,
  Apply, the play/pause button, the active sidebar item's marker, the seek and volume bars, the
  line above the now-playing bar, and the app icon.
- **Grain follows brightness.** It is full strength on dark surfaces and about a third as strong on
  bright ones like the amber buttons, so their labels stay clean. Text is always drawn in solid
  colour on top of the texture.
- Gradient buttons are rendered at exactly the button's own height, so the gradient is never
  stretched or banded.
- Lists and text fields stay a solid deep colour (Tk can't texture them) and read as inset panels.
  Status colours are tuned for the dark background.
- Textures are generated at start-up with Pillow (about 140 ms; no image files, no new
  dependencies) and are identical on every run.
- Menus, list boxes and Tk-drawn dialogs on Linux follow the dark colours.
- No behaviour changes; all v1.7.0 data and features carry over.

## 1.7.0 — 6 November 2026: interface redesign, project reorganisation, packaging readiness

### Interface
- **One window, player first.** The separate player and converter windows are replaced by a single
  window with a sidebar: **Library, Artists, Albums, Playlists**, and **Converter**.
- **Now-playing bar** across the bottom of every page: cover art, title, artist and album,
  ⏮ ▶/⏸ ⏭ ■, seek bar with times, and volume. Music keeps playing while you use the converter.
- The playing song is marked **▶** in every list and shown in the window title.
- **Search** box (Ctrl+F) filters songs, artists and albums as you type; Esc clears it.
- **Artists** and **Albums** pages: a list on the left and its songs on the right, with
  per-group play. Albums show the year and track numbers.
- **Playlists:** create inline (type a name and press Enter), rename (F2), delete, reorder
  (▲▼ or Ctrl+↑/↓) and remove (Delete). You can add from any list with **Add to playlist** or
  the right-click menu. Duplicate names are refused with a message instead of a dialog.
- **Track artist** column shows featured guests (e.g. "Singer feat. Guest"); grouping still uses
  the album artist.
- **Converter** reorganised into three numbered sections: Folders, Review and Convert.
  - Colour-coded status counters (Ready, Completed, Needs review, Skipped, Failed) filter the table.
  - Each row shows a status symbol and plain-language label.
  - A details panel explains where the selected file will go and why it needs attention. Its text
    can be copied.
  - The batch summary and the first failure now appear in that panel instead of a pop-up.
  - Column sorting toggles ascending and descending.
- **Fewer pop-ups.** Informational messages go to the status line. "Exclude from batch" and "Keep
  selected duplicate" no longer ask for confirmation, since neither deletes anything. Dialogs
  remain only for real decisions: starting a conversion, deleting a playlist, downloads and
  metadata editing.
- Keyboard: Ctrl+1…5 switch pages; Space plays or pauses; Ctrl+←/→ go to the previous or next
  song; Enter plays; Shift+F10 or the Menu key opens the song menu. Ctrl+A, Ctrl+click,
  Shift+click and Ctrl+Shift+click work in every song table and the converter table.
- New consistent visual style: palette, typography and flat controls. Sharp text on high-DPI
  Windows displays. The window remembers its size, volume, page and music folder. New app icon.

### Project organisation
- Code split into `oggcultist/gui`, `player`, `converter`, `metadata` and `services`, with
  `paths.py`, `startup.py` and `resources/`. Old import paths still work (compatibility aliases).
- `run_windows_debug.bat` merged into `run_windows.bat` (one console launcher). `Oggcultist.pyw`
  remains the quiet double-click launcher.
- Historical audits, handovers, patch notes and test reports moved from the program folder into
  `docs/reviews` and `docs/history`. The new user docs are `docs/user`.
- Python's bytecode cache is redirected to the user cache folder, so running from source no
  longer litters the program folder with `__pycache__`.
- `pyproject.toml` added; dependencies bounded (`requirements.txt`, `requirements-dev.txt`,
  `packaging/requirements-build.txt`).

### Portable executable preparation
- `oggcultist/paths.py`: frozen-aware program, bundle and resource paths; **portable mode**
  (`OggcultistData` next to the program, or `OGGCULTIST_DATA_DIR`) with a copy-only migration of
  settings and playlists.
- Bundled FFmpeg support: a `tools/` folder next to the program, or tools embedded in the
  executable, are used before the private or system copy.
- PyInstaller recipe (`packaging/oggcultist.spec`), a pure-Python build script
  (`packaging/build.py`), a Windows wrapper (`packaging/windows/build_windows.bat`), Windows
  version metadata and icon. The build produces a portable ZIP and `SHA256SUMS.txt`.
- `--paths` reports every location and tool in use; `--version` added.
- Windowed builds and `pythonw` log `stdout`/`stderr` to `logs/oggcultist.log`. Start-up errors go
  to `logs/startup-error.log` (previously next to the private FFmpeg folder).

### Fixes
- **No console windows for FFmpeg/FFprobe on Windows.** The converter now starts every child
  process with `CREATE_NO_WINDOW`. Under the windowless `.pyw` launcher (v1.6.2+) each probe,
  encode and verification could otherwise flash a console window.
- MusicBrainz and FFmpeg-download User-Agents now report the real version (previously fixed at 1.5 / 1.6.3).

### Unchanged
- Conversion settings (libopus, 96 kbps VBR), folder naming, artwork, duplicate and collision
  rules, the completion ledger, read-only previews, and the "never modify originals / never
  overwrite outputs" guarantees.
- Data file formats and default locations.

## Earlier versions

See `docs/history/` (patch notes and test reports for v1.1–v1.6.3) and `docs/reviews/`
(independent audits).
