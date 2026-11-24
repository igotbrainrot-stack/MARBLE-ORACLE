# Changelog

Newest first. Releases before 0.4.9.3 have their original notes in `History/ReleaseNotes/`.

## 0.5.3 · 24 November 2026 · Rounded corners and the Inter typeface

Built on 0.5.2. No saved setting changes format. Classic is unchanged.

- **Rounded corners everywhere in Dark and Light.**
  - **Buttons** are `oracle_widgets.RoundButton`: a `tk.Button` whose face is an anti-aliased rounded picture, with Tk drawing the text on top. It keeps the whole Button interface (command, invoke, state, keyboard, textvariable), and `bg`/`fg` still mean what they did. Its face follows hover, press, focus and disabled, and stretches to fill a grid cell. `oracle_shell.button()` and `nav_button()` return it, so every workspace and the setup window get it.
  - **Textured cards** (the pumice frames and panels) use a rounded nine-slice image (`oracle_pumice.rounded_tile_png`): one whole tile in the middle, the texture wrapped round it, transparent anti-aliased corners.
  - **Fields, lists, text boxes, dropdowns, bordered panels and badges** get four small corner pieces laid over their corners (`oracle_round.py`). Each piece is the surface outside the curve, the widget's border on it and its fill inside. Widgets made later are picked up as they appear, and a light check redraws pieces whose colours change (focus, toggles).
  - **Canvas shapes:** HOME's section buttons, TAROT/RUNES toggle, rune boxes and focus ring, and Touch Type's keyboard are drawn rounded. `oracle_sidebar.round_rect` now pins each straight edge, so a corner curves over its whole radius (before, Tk's spline cut it to half).
  - **Oggcultist** draws its own rounded artwork. Its corner radius is raised to match.
- **Inter, a modern sans-serif designed for screens, is the interface face** in Dark and Light, on every system. Its four styles ship in `fonts/` with the SIL Open Font License 1.1 (`fonts/Inter-OFL.txt`) and are registered at start-up for this process only, like Uberata in Classic. Nothing is installed into the system. OVERCAST inside the suite uses it too; `MARBLE_ORACLE_FONT` still overrides it.
- **The setup window follows the chosen appearance:** OVERCAST's palette, Inter, sentence case and rounded buttons in Dark and Light; Classic as before.
- **Passphrase:** in a narrow rail the key meanings and the dice-code option wrap instead of being cut off.
- **Performance:** rounded faces and card images are worked out from a small corner table rather than pixel by pixel. They are identical to the per-pixel result and about eight times faster: 40 button faces take about 0.06 s.
- **Fixed during the work:**
  - A rounded button stretched across shared grid columns kept resizing its neighbours. A button now always asks for its natural size; only its face stretches.
  - A rounded button asking for 2 px more on every redraw (Tk's own image inset).
  - Corner pieces sat inside a widget's border and covered left-anchored text.
- **Tests:** new `test_rounded_0530.py` (24 checks): Inter and its licence ship; card images (transparent corners, opaque body, wrapped texture); rounded faces match a pixel-by-pixel reference and are fast; RoundButton keeps the Button interface and settles in shared columns; in Dark the suite uses Inter, its buttons are RoundButtons, fields and lists are rounded, and nothing is freed from a worker thread. `test_install_0499.py` checks the setup window's bright button against the chosen look's accent.

## 0.5.2 · 24 November 2026 · A faint pumice surface for Dark and Light

Built on 0.5.1. No saved setting changes format.

- **Pumice instead of flat colour.** Dark and Light surfaces now carry a faint pumice-stone texture, where Classic has its film grain. It covers HOME's page and cards, the sidebar, header and footer, the workspaces' textured frames and labels, AUGURSPEX's chart backgrounds, and the embedded Oggcultist's generated artwork.
  - The texture is small pores stretched along one direction, with ragged edges, a lit inner wall and a faint rim, plus a slow mottle and a fine grain.
  - It is faint: 95% of pixels move by 3 levels or fewer, the deepest pores by about 15. Light surfaces get a quarter more, so the pores still read on white.
- **How:**
  - `oracle_pumice.py` computes one seamless 256 px relief in pure Python and tints it to each surface colour. It needs no Pillow and takes about 0.3 s at start-up.
  - `oracle_ogg_texture.use_pumice()` puts these tiles where Classic uses the grain PNGs.
  - HOME's cards are the tile with drawn rounded corners and a hairline.
  - Oggcultist's artwork gets the relief in place of its film grain.
- **Not textured:** OVERCAST's own panel. Its pages are built from plain Tk frames and labels, which cannot sit on a picture, so a texture there would show only as gaps between them.
- **Fixes:** texture images are shared per window and kept for the life of the process, so none is freed from a worker thread. This is the same issue 0.4.9.9 fixed for other images.
- **Tests:** `test_appearance_0510.py` now has 275 checks. They cover the relief (deterministic, fast, faint, has pores, tiles without a seam, encodes) and that the page, sidebar and cards carry it in Dark and Light at four sizes.

## 0.5.1 · 24 November 2026 · OVERCAST's design for the whole suite

Built on 0.5.0. No saved setting changes format. Your forecasts, music library, queues and scores are untouched.

- **Three appearances.** The choice is saved in `appearance.json` in the state folder. `MARBLE_ORACLE_APPEARANCE` and `MARBLE_ORACLE_ACCENT` override it for one run.
  - **Dark**, the new default, and **Light** use OVERCAST's design throughout:
    - its palette, with WCAG AA text contrast;
    - a sans-serif face (SF Pro, Inter, Adwaita Sans or Segoe UI, whichever the system has);
    - flat rounded cards, no film grain, and sentence-case labels.
  - Dark and Light also take an accent: Amber, Blue, Green or Graphite.
  - **Classic** is the suite exactly as in 0.5.0.
  - The **Appearance** window (sidebar, or the A key on HOME) saves the choice and offers **Restart now**. A conversion in progress still asks before the suite closes.
- **The left sidebar** (Dark and Light) replaces the tab strip.
  - It has the seven workspaces with drawn icons, plus Welcome guide and Appearance at its foot.
  - It is 212 px wide from 1200 px, 184 px from 1100 px, and a 60 px icon rail below that, so the workspaces keep their width at 900x580.
  - A header names the open workspace and what it is for.
  - Every workspace opens in the whole area right of the sidebar. The CRT housing keeps the tab strip.
- **How the restyle is done:**
  - Every workspace already took its colours from the shared Ember tokens and its font from `marble_uberata.FAMILY`.
  - `oracle_appearance.apply()` points those tokens at OVERCAST's palette once at start-up, before anything is drawn.
  - **HOME** gets flat cards with titles like "Plate vault", and plainly named buttons: Next quote, New word, Deal again, Layout.
  - **Shared helpers:** `oracle_shell`'s buttons, labels and rail items lose their box and use sentence case.
  - **Grain:** the film-grain helpers return flat widgets.
  - **The embedded Oggcultist:** its own tokens and fonts are retinted. Its generated artwork is drawn without grain or bevel, and its few literal Ember colours are mapped to the matching OVERCAST colour.
  - The ASCII statue keeps Uberata Clear, because its proportions depend on it.
- **OVERCAST follows the suite.** In Dark and Light it uses the suite's appearance and accent, and its own saved setting is left for when it runs alone. Its Settings say so.
- **Nothing squeezed at 900x580** (every appearance):
  - EIDOLITH's player controls and file tools wrap instead of squeezing SELECT ALL, STOP and FULLSCREEN.
  - OGGCULTIST's Folders, Create and Delete buttons stay whole. These are three small layout changes inside the bundled Oggcultist (`converter_view.py`, `collection_pages.py`).
- **Tests:**
  - `test_appearance_0510.py` (260 checks):
    - the sentence-case rule, the saved choice and its overrides, and the colour mapping;
    - in Dark and in Light, at four sizes: the sidebar, where HOME's panels sit, every workspace filling its box and being marked in the sidebar and header, no button squeezed or cut off in any workspace, rune stones, passphrase words, the Appearance window and the A key, and no Tk call from a worker thread.
  - Ten older tests that check Classic's exact labels and surfaces now pin Classic.

## 0.5.0 · 24 November 2026 · OVERCAST joins the suite

Built on 0.4.9.9. No saved setting changes format.

- **New seventh workspace, OVERCAST** (*Mostly cloudy, with a chance of being right.*). It is the pessimism-first news forecasting desk, version 1.1.2, and its tab sits between AUGURSPEX and PASSPHRASE.
  - Broad outlooks with scenarios and a gloom index, yes/no forecasts in a permanent ledger, a calendar, research pages and an honest track record.
  - It uses public RSS feeds (fetched only when you refresh) and a model in LM Studio on your own computer.
  - The panel is built on first open and kept while other tabs are shown, so a running forecast carries on. Finished jobs are announced in the status line.
  - Its ledger is in the suite's state folder (`news_oracle/`), the same folder a standalone OVERCAST install uses.
  - Escape returns HOME, and the welcome guide describes it. Code: `oracle_overcast_tab.py`; package: `overcast/` (plus the `news_oracle` alias).
- **OVERCAST 1.1.2** (fixes to the delivered 1.1.1; full list in `Documentation/Overcast/CHANGELOG.md`):
  - **Window:** 1.1.1's window failed to build on real Tk; it opens now.
  - **Controls:** buttons, dropdown arrows and the page border are drawn as designed.
  - **Small windows:** the layout fits down to the suite's 900x580 and the CRT housing. The command bar wraps, split views stack, Settings scrolls in one column, and the sidebar narrows and compacts.
- **Tests:**
  - `test_overcast_package.py` runs OVERCAST's own 97 tests against the suite's copy. The standalone packaging test is not included, because the suite has no `pyproject.toml`.
  - `test_overcast_workspace_0500.py` (44 checks) covers the fit at the five sizes, no network on open, the ledger location, switching tabs and closing during a refresh, and no Tk calls from worker threads.
  - Tab-count tests updated for seven tabs. The screenshot tool captures OVERCAST.

## 0.4.9.9 · 22 November 2026 · Welcome, install, clean-up

Built on 0.4.9.8. No saved setting changes format; every workspace keeps its features.

### First start

- **Welcome guide.** On first start a window explains what Marble Oracle is and what each of the six workspaces is for, with two or three tips each and an OPEN button that goes straight there. A checkbox ("Show this when Marble Oracle starts") decides whether it comes back; the choice is kept in the state folder (`welcome.json`). F1, or the new **?** button beside the tabs, opens it at any time. It is sized from the main window, reflows its cards into three, two or one column, scrolls, and works from the keyboard (Tab, Enter, Escape). It does not open during `--selftest` or when `MARBLE_ORACLE_NO_WELCOME` is set. In the CRT housing the ? button is left out (the curved glass has no room); F1 still works there. New module content in `oracle_suite_guide.py`.

### Look

- **Slim scrollbars.** Every scrollbar in EIDOLITH, AUGURSPEX (watch list, charts, insights tables) and the setup window is a thin themed bar that shows a thumb only when there is something to scroll; it lightens on hover and turns amber while dragged. The platform scrollbars (grey on Linux, white on Windows) are gone. `oracle_widgets.SlimScrollbar`.
- **One dropdown look.** EIDOLITH's profile and audio menus, AUGURSPEX's chart controls and TOUCH TYPE's lesson menu share one style: flat, 1 px outline, a drawn chevron, the cream focus ring, and Space or Enter to open. `oracle_widgets.style_dropdown`.
- The window has a proper class name (`MarbleOracle`) and icon on Linux, so the taskbar and app menu group it correctly.

### Install

- **Every common Linux family.** The Linux start script and the setup window recognise Debian/Ubuntu/Mint (apt), Fedora (dnf), Arch (pacman) and openSUSE (zypper), name the right packages (for example `python3-tkinter` and `ffmpeg-free` on Fedora) and install them through `pkexec`, or PackageKit where that is missing. Messages use kdialog on KDE, then zenity, then xmessage.
- **A clearer setup window.** One line per requirement with a READY / MISSING / NOT INSTALLED badge; the media-tools option only while tools are missing; a progress bar only while installing; the main button reads START when everything is ready and INSTALL when not.
- **ADD TO APP MENU** (Linux) creates a desktop entry with icon, description and keywords; `install_linux_desktop.sh --remove` takes it away again.

### Clean-up

- Removed launchers that the START scripts replaced (five in `Runtime/`, four in `Marble_Oracle_App/`), the browser version of AUGURSPEX (`Augurspex/run.py` and its web server, page, script, style and icon) with the bridge that started it, a duplicate `VERSION.txt` and two requirements files nothing read, unused functions, and seven test pictures that were outputs, not references. Each was checked for references first. About 2,500 lines fewer.
- Tests no longer write pictures into the repository; they go to `MARBLE_ORACLE_TEST_OUTPUT` or the temp folder. Two stray test scripts moved into `Tests/`.

### Fixes

- A Tk image could be freed on a worker thread after its window closed, printing "main thread is not in main loop"; such images are now kept until exit.

### Tests

- New `test_welcome_and_widgets_0499.py` (34 checks): guide sizes and column reflow at the four sizes, preferences file, keyboard, the ? button, scrollbar and dropdown behaviour.
- New `test_install_0499.py` (38 checks): distro detection for each family, package names, the install-command allowlist, the start script's detection, the desktop entry.

## 0.4.9.8 · 22 November 2026 · OGGCULTIST rail

Built on 0.4.9.7. One defect, found by running the suite on a virtual display rather than by reading screenshots from CI.

- **OGGCULTIST's Settings could be hidden.** The suite packs its HOME button and Oggcultist's version line ahead of the rail's other items so they always keep their place; Settings, which also sits at the foot of the rail, was left last in line. At 1280x720 HOME covered half of it, and at 900x580 it was not reachable at all. It is now kept with HOME and the version line.
- **900x580: the icon rail fits.** In the 64 px icon rail of a short window, Converter was cut in half and Album Art was gone. The rail's logo, which repeats the OGGCULTIST tab directly above it, now gives way when (and only when) the items would not otherwise fit, and comes back as soon as there is room. Oggcultist's own code is unchanged; both fixes are in the suite's `oracle_ogg_tab.py`.

### Tests

- New `test_ogg_rail_0498.py`: resizes the window through seven sizes and checks that every rail item and HOME are fully inside the rail, that HOME covers nothing, that Settings sits just above HOME, and that the logo, when shown, is at the top. It fails on 0.4.9.7 (six failures at 900x580) and passes on 0.4.9.8.

## 0.4.9.7 · 16 November 2026 · Keyboard and fit

Built on 0.4.9.6. Nothing removed; no saved setting changes format.

- **HOME from the keyboard.** HOME's controls are drawn on its canvas, so Tab did nothing there and it could only be used with a mouse. Tab and Shift+Tab now step through the visible controls in reading order, Enter or Space presses the focused one, and Escape puts the focus away (with no focus, Enter, Space and Escape mean what they did before; Escape still never quits). The focused control gets the suite's cream focus ring. Close, minimise and the dials are left out of the Tab order. New module `oracle_home_focus.py`.
- **HOME hover.** The control under the pointer gets a quiet 1 px outline in the tertiary text colour, distinct from the focus ring and from the amber "current" fill. Before, only the cursor changed.
- **THREE CUTS at 900x580.** The line under each card ("REVERSED · ALREADY") is fitted to its card like the name; neighbouring lines ran into each other. The TAROT / RUNES switch sits in the panel's header row; below the header it covered the top of the third card.
- **Page descriptions fit their line.** The shared shell shortens a description with "…" to the width it has and shows the whole text on hover. PASSPHRASE's and TOUCH TYPE's ran off the right edge mid-word at 900x580. New helper `oracle_widgets.ellipsize`.
- **PLATE VAULT in screenshots.** The statues were missing from every automated screenshot because `capture_screens.py` never ran the frame loop that draws them; the panel itself was fine. The tool now ticks the scene as the running program does.
- **Windows CI is required.** The Windows job passed on every commit from 0.4.9.5's review fixes to 0.4.9.6, so it no longer runs as informational.
- **Handover rewritten** as one current document; the layered 0.4.9.3 to 0.4.9.5 notes are in `History/HANDOVER_0.4.9.3-0.4.9.5.md`.

### Tests

- New `test_home_keyboard_0497.py`: Tab order rule, focus ring, Enter and Space press, Escape, hover outline, ring after a resize, Tab left to Tk inside a workspace.
- New `test_polish_0497.py`: `ellipsize` on its own; at 900x580 no tarot caption overlaps another or leaves the panel, the switch covers no card, and each page description fits its line.

## 0.4.9.6 · 16 November 2026 · Design prototype

The first slice of the redesign in the design document (phase 7). Built on 0.4.9.5; nothing removed.

- **Readable labels.** Tertiary text is lighter (#A79686): 5.2:1 on buttons, 5.7:1 on panels. It was 3.96:1 and 4.34:1, below WCAG AA.
- **Visible buttons.** Button outlines are lighter (#85705F), 3.2 to 4.1:1 against what surrounds them (was about 2:1).
- **Focus is not "current".** Keyboard focus is a 2 px cream ring. The current page is an amber-tinted fill with no outline, so the two can no longer be confused.
- **Escape never quits.** On HOME it now says to use the close button. Two presses from any tab used to close the suite, conversions included.
- **No GRADE footer on workspaces.** GRADE changes only HOME; workspaces gain its 30 px.
- **EIDOLITH Convert.** QUEUE SELECTED and START QUEUE sit in the page title row at every size; they were the last controls of a scrolling form. The output folder comes first. ADD FILES is secondary, so the page has one main button. Cancelling stays on QUEUE. The rail shows the suite version, not 0.4.7.
- **AUGURSPEX.** The minimum chart card is 380x260 px (was 420x320), so four charts form a 2x2 grid at the default window instead of one scrolling column.
- **AUGURSPEX month axis.** Month and year labels now sit on the first bar of each month (or year) and step evenly, counting back from the newest: JUL, SEP, NOV rather than JUN, AUG, SEP, NOV. When the labels would not fit the axis font, the card asks for fewer at a wider step instead of dropping one from the middle. Because month labels now sit inside the plot, the first and last labels get a vertical grid line as well. The smaller cards made the uneven spacing more visible. Labels still name only dates the provider returned.
- **AUGURSPEX card footer follows the chart.** "LAST n OF m REAL BARS" and the VIEW change were worked out once, at the card's first size; after the grid or window changed they could describe a different window from the one drawn (for example LAST 18 over 52 candles). They are now recomputed whenever the card redraws. This fault was in 0.4.9.5 too; the smaller cards made it easier to hit.

### Tests

- New `test_design_tokens_0496.py` (131 checks): contrast for every allowed pair, focus colour, Escape, footer, the 2x2 grid, an even step on month and year axes, and a chart card's footer that follows a resize (the 0.4.9.5 code fails the last two).
- Updated, on purpose: `test_eidolith_layout_0493.py` now requires the Convert actions on screen without scrolling (it checked they could be reached by scrolling). `test_augurspex_charts_layout_0485.py` tests its small-view rule with a view shorter than the new minimum card.

## 0.4.9.5 · 16 November 2026 · One layout for every workspace

Built on 0.4.9.4. No feature was removed and no saved setting changes format.

The workspaces had grown their own layouts: side rails of 208, 225, 240 and 312 px (and none at all on PASSPHRASE), page titles from 15 to 23 pt in three colours, buttons at 10 or 11 pt with four paddings, and HOME in the rail, beside MANAGE LIST, in the top-right corner or in an extra title bar depending on the tab. They now share one page shell, `oracle_shell.py`, based on Oggcultist's type scale:

- **The same frame everywhere.** Left rail with the workspace name in the same type, grey group labels, navigation items that are outlined in orange when current, and **HOME at the foot of the rail with the version line under it**. The main area opens with the page title (20 pt) and a one-line description, and ends with the status line.
- **One button.** Every push button is the same 11 pt bold with the same padding; one orange primary per area.
- **EIDOLITH:** rail, title, field labels, video-player buttons and status line moved to the shared styles.
- **TOUCH TYPE:** the games list uses the same rail navigation as EIDOLITH; title and READY badge in the shared header.
- **PASSPHRASE:** now has the rail (options, keys, privacy note, HOME). The parts are compact cards instead of tall empty ones, each word is sized to fit its card, and in a narrow window the rail steps aside so the five parts stay on one row.
- **AUGURSPEX:** uses the suite's surface colours (it was 10-24 % darker than every other tab), the shared brand, title and status line, and a full-width HOME at the foot of the rail. Its rail stays wider (312 px) because it is the market list.
- **OGGCULTIST:** the extra title bar above it is gone (its rail already shows the name and version); HOME is at the foot of its rail. Oggcultist's own pages are unchanged.
- **All rails narrow together** below an 850 px workspace, and in a very short window every tab drops the same things first (page description, the line under the name, the version line) and tightens its rail items, so small windows behave the same in every tab.

### Review fixes (before release)

- Windows: at 900x580 the larger buttons squeezed EIDOLITH's MEDIA PROBE box to 28 px (the Windows CI job failed). The file list now asks for two rows instead of three; it still grows with the window.
- At the 640x460 minimum: HOME had dropped off OGGCULTIST's short rail (it now claims its place first), EIDOLITH's wordmark was clipped in the narrowed rail (it is redrawn smaller), and AUGURSPEX's CSV button was pushed off its row (SOURCE DETAILS shortens to SOURCES). EIDOLITH and TOUCH TYPE now show HOME at that size too, which they did not before.
- AUGURSPEX reserves the foot of its rail first too: with Windows' taller text, HOME had been pushed off the rail at 640x460 (caught by the new test on GitHub's Windows runner).
- PASSPHRASE: the widest list word ("mammogram", about 98 px at the 10 pt minimum) could be clipped at 640x460 (seen once on GitHub's Linux runner). Narrow cards now use tighter padding, and the test checks that word directly instead of relying on random rolls.
- OGGCULTIST's narrow-rail HOME no longer uses a house symbol the suite font does not have.
- AUGURSPEX's search box uses the suite field size, and its title colour comes from the shared palette.

### Tests

- `test_unified_shell_0495.py` (88 checks): rail widths, brand and title type, HOME position and size on all five tabs, button type, AUGURSPEX colours, no PASSPHRASE word cut off from 640x460 up (including the widest word in the list), and at 640x460 HOME visible on every tab and the EIDOLITH wordmark inside its rail.

### Not changed

- The HOME dashboard (the oracle, runes and panels) is drawn on its own canvas and was left as it is.
- At the 640x460 minimum some EIDOLITH buttons and AUGURSPEX tool captions are still clipped, as they were in 0.4.9.4.

## 0.4.9.4 · 16 November 2026 · Backup data sources

Built on 0.4.9.3. Nothing was removed and no saved setting changes format.

**Not checked live.** The build environment cannot reach any market-data provider. Every source below is tested against the reply format its provider documents, using made-up numbers; none has been seen answering for real. Run `Tools/probe_providers.py` on a home connection to find out.

### Fixed

- **Stooq.** Since about March 2026 Stooq answers a request without a key with a "get your key" page. AUGURSPEX read that as broken data. It is now reported as a key being needed, a free key can be entered (`AUGURSPEX_STOOQ_KEY`, or STOCK FEEDS in the app), and with a key Stooq serves Australian and Tokyo listings and the US indices without the unofficial-sources switch.
- **Rune stones at the smallest window.** In the STATUE layout at 640x460 the stones were drawn about 3 pixels tall (and on Windows, with its taller fonts, failed their test). The caption band now gives way so a real stone always fits; captions that no longer fit are left out and the reading pane still names the rune.
- A source waiting out a "key needed" cool-down is asked again as soon as a key is entered, instead of up to fifteen minutes later.

### Added

- **Crypto:** Bitstamp, Bitfinex and Coinbase's second public host as further US-dollar exchange sources, and the Binance market-data mirror as a last resort. Binance prices are in USDT, not dollars, and are always labelled `USDT`; a cached dollar series is preferred over a fresh USDT one. BNB gains real candles and intraday this way.
- **Stocks, with a free personal key each:** Tiingo (US), EODHD (US, Australia, Tokyo, Korea, US indices) and the Korean government data portal (Korea). The key dialog has the four new fields and says where to get each key.
- SOURCE DETAILS for Australian, Tokyo, Korean and index listings now lists the sources a free key would unlock.

### Tests

- `test_augurspex_backup_sources_0494.py` (22 checks, no network) and `test_rune_tall_fonts_0494.py`. Seven older checks that spelled out the previous source order were updated to the new order.

## 0.4.9.3 · 15 November 2026 · Refinement

Built on 0.4.9.2. No feature was removed from any workspace, no saved setting changes format, and no asset was repacked.

### Fixed: things that were wrong

**AUGURSPEX**
- A failed request now keeps its cause all the way to the screen. Before, a rate limit, a rejected key, a timeout and "no source for this listing" could all read as "provider refused the request". There are now eleven kinds (offline, not configured, key rejected, rate limited, refused, cooling down, network, unsupported, no data, reply rejected, provider fault), one wording each, used by the chart, the slot tabs and SOURCE DETAILS.
- The Alpaca adapter could never work: the transport dropped its second credential header, so it failed before sending anything. It now sends both.
- A provider's "please verify you are human" web page was reported as a JSON error; it is now reported as a blocked automated request.
- A rejected key started no cool-down, so it was re-sent on every refresh. It now waits like a rate limit.
- Zero and negative "prices" were accepted as observations. They are dropped.
- CoinDesk Data answers HTTP 401 without a key (live check), yet was listed as a free route and failed on every crypto refresh. It is now a route only when its key is set.
- The European Central Bank source timed out for five of seven pairs at 9 s; it gets 20 s.
- Date labels on the time axis could overlap; they are measured and thinned, always keeping the newest. Price labels that did not fit were clipped; they step down a size. Sub-cent prices read `0.0000`; they keep three significant digits.
- The SOURCES line silently omitted Strasmore, Gemini, FMP, Alpaca, ECB and Bank of Canada.
- SIGNALS: the change figure now names the two dates it spans, and RSI states its method.
- The disk cache grew without limit. It is pruned to 7 days and 400 files, and only the router's own cache files are ever deleted.

**EIDOLITH**
- On Windows, stopping or cancelling ended only the launcher process when FFmpeg was installed through Chocolatey or Scoop; the real `ffmpeg.exe` kept running and kept the file locked. The whole process tree is now ended.
- Every pause or seek in the viewer left a defunct helper process until the suite closed. Helpers are now collected (and killed if they ignore the request), which also releases the video file at once.
- At 900x580 the QUEUE page lost CLEAR FINISHED, CLEAR ALL and RETRY SELECTED off the right edge and the whole conversion log off the bottom; CONVERT cut its explanations mid-sentence and half-hid the status line; PLAYER lost the volume control. All three pages now fit at every supported size.

**PASSPHRASE**
- An internal error message could contain the generated phrase, and unhandled errors are written to the error log. The phrase no longer appears in any error text.

**Suite**
- Tools and tests that opened a window from the parsed options got the photographic CRT housing instead of the plain window users get. `launch_plan()` is now the single place that turns a command line into launch options.
- Oggcultist media keys: `stop()` referenced an undefined name.

### Changed: how it looks and behaves

- **One design vocabulary.** `oracle_design.py` holds the suite-level tokens (market category colours and labels, the wording for leaving a workspace) and `oracle_widgets.py` holds two shared behaviours: toolbars that wrap to a second row instead of running off the edge, and explanatory text that wraps instead of being cut. EIDOLITH and AUGURSPEX both use them.
- **AUGURSPEX header.** The selected market's name sits in the header beside CSV / SOURCE DETAILS / REFRESH. The separate "active chart market" box and the second status strip are gone, which returns three rows of height to the charts at 900x580. The four tools share equal columns and shorten their captions in a narrow window. The filter buttons are lettered in their category colour, replacing a separate legend (two more watchlist rows at 900x580).
- **EIDOLITH QUEUE.** Job actions (REMOVE SELECTED, RETRY SELECTED) sit with the job list; log actions (OPEN LOG, LOG FOLDER, COPY DIAGNOSTICS) sit with the log. In a short window the list and the log stand side by side; in a tall one they stack.
- **One hover, focus and disabled look everywhere.** A button under the pointer lightens slightly in every workspace (on Windows, buttons gave no hover feedback at all). The control that has keyboard focus gets an accent outline; it used to be black on near-black, so Tab moved an invisible focus. Disabled captions use the tertiary text colour.
- **Shortened text can be read.** AUGURSPEX's fitted status lines and shortened watchlist rows show their full wording when the pointer rests on them.
- **TOUCH TYPE coaching line.** It was cut at 30 characters at every window size, so every hint ended in "…". It now uses the width the row has, and shows the rest on hover when it still cannot fit.
- **EIDOLITH rail.** The wordmark is the title; the name is no longer written twice above the navigation.
- **One version number.** `oracle_version.py`; shown in the window title and by `--version`.

### Removed: verified unused, then deleted

- `marketdata.py` and `oracle_feeds.py`: the old AUD ticker (which could display simulated prices) and the RSS reader. Both were switched off in 0.4.7 but still shipped and were still constructed at start. Their drawing code and the `--wire` option went with them.
- `Tools/AUGURSPEX_Module`: a one-time installer carrying a stale second copy of the provider package; running it would have downgraded `providers.py`. Also `Augurspex/integration_backup` (old copies of two shell modules) and `integration_state.json`.
- `test_augurspex_chart_repair_0485.py`: written for a function signature that 0.4.9.2 does not contain; it could not run.
- Unused imports across the suite modules.

Net effect on the source tree: about 10,500 lines removed, 3,900 added. The release ZIP is the same size (113 MB); it is almost entirely artwork archives, none of which were touched.

### Added: engineering

- `Tools/run_tests.py`: runs every regression script in its own process with a throw-away state folder and no API keys in the environment; reports PASS, FAIL or SKIP (a test that cannot start without Tk is a SKIP, never a pass); says where a hung test is stuck.
- Continuous integration (`.github/workflows/tests.yml`): the whole suite on Ubuntu (Tk under Xvfb, FFmpeg) and on Windows (native Tk, FFmpeg), lint, byte-compile, screenshots of every workspace at five window sizes, a run with the clock 60 days ahead, and an on-request live provider probe.
- `Tools/probe_providers.py`: asks every no-key source for every starter market and records outcome, bar count and newest date (never prices).
- `Tools/capture_screens.py`: a picture of every workspace and page at each supported size.
- `Tools/build_release.py`: regenerates the inventory and manifest and writes a reproducible ZIP; `verify_release.py` checks more and ignores caches.
- `ruff.toml`: the lint rules that find real mistakes, enforced in CI.
- New tests: provider failure kinds and validation, axis labels, signals, EIDOLITH file safety (real FFmpeg: sources byte-identical after success, failure, cancel and stop; nothing overwritten; no partial files left), EIDOLITH layout at four sizes, process cleanup, passphrase randomness and secrecy, hover/focus/tooltip behaviour.
- Fixtures with fixed calendar dates (one began failing on 15 November 2026) now use dates relative to today.

### Documentation

README rewritten around how to start the program. New: `ARCHITECTURE.md`, `DEVELOPMENT.md`, `MARKET_DATA.md`, `PROVIDER_PROBE.md`, `TROUBLESHOOTING.md`, `TESTING_REPORT.md`, `HANDOVER.md`, this file. Subsystem notes are grouped under `Workspaces/` and `Launch/`; release notes, the 0.3 audit reports and old manifests are under `History/`.

## 0.4.9.2 and earlier

See `History/ReleaseNotes/` (0.4.7.1 to 0.4.9.2) and `History/` (0.3 and before).
