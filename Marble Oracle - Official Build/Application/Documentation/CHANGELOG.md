# Changelog

Newest first. Releases before 0.4.9.3 have their original notes in `History/ReleaseNotes/`.

## 0.4.9.6 · 16 November 2026 · Design prototype

The first slice of the redesign in the design document (phase 7). Built on 0.4.9.5; nothing removed.

- **Readable labels.** Tertiary text is lighter (#A79686): 5.2:1 on buttons, 5.7:1 on panels. It was 3.96:1 and 4.34:1, below WCAG AA.
- **Visible buttons.** Button outlines are lighter (#85705F), 3.2 to 4.1:1 against what surrounds them (was about 2:1).
- **Focus is not "current".** Keyboard focus is a 2 px cream ring. The current page is an amber-tinted fill with no outline, so the two can no longer be confused.
- **Escape never quits.** On HOME it now says to use the close button. Two presses from any tab used to close the suite, conversions included.
- **No GRADE footer on workspaces.** GRADE changes only HOME; workspaces gain its 30 px.
- **EIDOLITH Convert.** QUEUE SELECTED and START QUEUE sit in the page title row at every size; they were the last controls of a scrolling form. The output folder comes first. ADD FILES is secondary, so the page has one main button. Cancelling stays on QUEUE. The rail shows the suite version, not 0.4.7.
- **AUGURSPEX.** The minimum chart card is 380x260 px (was 420x320), so four charts form a 2x2 grid at the default window instead of one scrolling column.
- **AUGURSPEX month axis.** Month and year labels now sit on the first bar of each month (or year) and step evenly, counting back from the newest: JUL, SEP, NOV rather than JUN, AUG, SEP, NOV. When the labels would not fit the axis font, the card asks for fewer at a wider step instead of dropping one from the middle. The smaller cards made the uneven spacing more visible. Labels still name only dates the provider returned.

### Tests

- New `test_design_tokens_0496.py` (128 checks): contrast for every allowed pair, focus colour, Escape, footer, the 2x2 grid, and an even step on month and year axes (the 0.4.9.5 axis fails it).
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
