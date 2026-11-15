# Changelog

Newest first. Releases before 0.4.9.3 have their original notes in `History/ReleaseNotes/`.

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
- New tests: provider failure kinds and validation, axis labels, signals, EIDOLITH file safety (real FFmpeg: sources byte-identical after success, failure, cancel and stop; nothing overwritten; no partial files left), EIDOLITH layout at four sizes, process cleanup, passphrase randomness and secrecy.
- Fixtures with fixed calendar dates (one began failing on 15 November 2026) now use dates relative to today.

### Documentation

README rewritten around how to start the program. New: `ARCHITECTURE.md`, `DEVELOPMENT.md`, `MARKET_DATA.md`, `PROVIDER_PROBE.md`, `TROUBLESHOOTING.md`, `TESTING_REPORT.md`, `HANDOVER.md`, this file. Subsystem notes are grouped under `Workspaces/` and `Launch/`; release notes, the 0.3 audit reports and old manifests are under `History/`.

## 0.4.9.2 and earlier

See `History/ReleaseNotes/` (0.4.7.1 to 0.4.9.2) and `History/` (0.3 and before).
