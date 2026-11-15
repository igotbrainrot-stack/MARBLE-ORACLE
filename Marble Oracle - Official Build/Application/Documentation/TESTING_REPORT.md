# Testing report: Marble Oracle 0.4.9.3

15 November 2026. Everything below was run; nothing is inferred. Where something could not be checked, it says so.

## Where the tests ran

The development environment for this release had no Tk, so every graphical test ran on GitHub Actions rather than on the developer's machine:

| Environment | What it is | What it is not |
|---|---|---|
| **Linux** | Ubuntu 24.04, Python 3.12, Tk 8.6 under Xvfb at 1920x1080, FFmpeg from the distribution | Not Linux Mint, not a real display or GPU |
| **Windows** | GitHub's Windows Server runner, Python 3.12 from python.org with its native Tk, FFmpeg from Chocolatey, desktop set to 1920x1080 | Not Windows 11, not a physical PC |
| **Linux, clock +60 days** | The AUGURSPEX tests with the system date moved forward | |

## Results (code commit `e7e6de6`, workflow run 43709186385)

| Check | Linux | Windows |
|---|---|---|
| Regression scripts (`Tools/run_tests.py`) | **60 passed, 0 failed, 0 skipped** | **59 passed, 1 failed, 0 skipped** |
| AUGURSPEX scripts with the clock 60 days ahead | 30 passed, 0 failed | not run |
| Byte-compile every source file | pass | not run |
| Lint (`ruff.toml`) | pass | not run |
| Screenshots of every workspace and page at 900x580, 1000x650, 1216x848, 1280x720, 1920x1080 | 71 captured; the 900x580 set and a sample of the larger sizes reviewed by eye | not captured |

The one Windows failure: `test_rune_click_and_art.py` at a **640x460** window in the STATUE layout. On Windows the rune stones are given no height at that size. 640x460 is the smallest size the window allows, below the supported 900x580; the same test passes on Windows at 1216x848, 900x620 and 760x550, and on Linux at all four. Not fixed in this release; see `HANDOVER.md`.

The 60 scripts are the 57 in `Application/Tests/` and `Runtime/Marble_Oracle_App/test_*.py` that existed in 0.4.9.2 (one removed, see the changelog) plus the new ones listed there. The embedded Oggcultist application's own `Oggcultist/tests/` folder is **not** run by the suite runner and was not run for this release; the suite's `test_ogg206_embedded.py` (which opens Oggcultist inside the suite) was, and passes on both systems.

## Defects the tests found during this work

Recorded because each one is the reason a test now exists.

| Found by | Defect | State |
|---|---|---|
| Screenshots at 900x580 | EIDOLITH QUEUE, CONVERT and PLAYER lost controls off the edges | Fixed; `test_eidolith_layout_0493.py` (345 checks at four sizes) |
| Windows job | STOP left the real `ffmpeg.exe` running behind a launcher, file still locked | Fixed; `test_eidolith_process_cleanup_0493.py` |
| Windows job | The window froze laying out the CONVERT page: wrapped text and its container's width caused each other for ever. Introduced and fixed within this release | Fixed; the settling rule is tested without a display |
| Clock +60 days | A fixture with fixed calendar dates began failing on 15 November 2026 | Fixed; fixture dates are relative |
| Live probe | CoinDesk Data rejects keyless requests; ECB timed out at 9 s | Fixed; routing follows the evidence |
| Reading the code | Alpaca adapter could not send its credentials | Fixed; `test_augurspex_provider_errors_0493.py` |

## Acceptance criteria

| # | Criterion | Evidence | Verdict |
|---|---|---|---|
| 1 | Application launches | `--selftest` and the GUI tests open the real window on both systems | Verified in CI. Not on a physical PC |
| 2 | All six workspaces accessible | `test_tab_layout.py`, `capture_screens.py` open each | Verified in CI |
| 3 | Navigation works repeatedly | Layout tests switch tabs and pages at four sizes in one session | Verified in CI |
| 4 | Settings and data preserved | No persistence format changed; state paths unchanged; tests use throw-away state folders | By inspection. No upgrade test from a real 0.4.9.2 profile was run |
| 5 | No overlap or lost controls at tested sizes | EIDOLITH: every button, slider, menu and entry checked inside its page at four sizes. AUGURSPEX: chart, axis-label and scroll tests. Others: 900x580 screenshots reviewed | EIDOLITH and AUGURSPEX verified by test; HOME, OGGCULTIST, PASSPHRASE, TOUCH TYPE by eye only |
| 6 | Valid, stale, partial and unavailable provider replies handled | `test_augurspex_provider_errors_0493.py` and the earlier provider tests, with controlled replies | Verified with fixtures |
| 7 | Calculations use only verified observations | `test_augurspex_signals_0493.py`, `test_augurspex_pdf_integration_0492.py` | Verified with fixtures |
| 8 | CSV import/export integrity | Export formula-injection and close-only tests; import tests from 0.4.9.1 | Verified with fixtures |
| 9 | Conversions preserve originals | `test_eidolith_file_safety_0493.py`: real FFmpeg, source byte-identical after success, failure, cancel, stop | Verified on both systems |
| 10 | Failed and cancelled operations recover | Same test: no partial file left, queue continues; process-cleanup test | Verified on both systems |
| 11 | Background work does not freeze the interface | Fetches and conversions run off the Tk thread (by inspection); the one freeze found was fixed and tested | Partly: no automated responsiveness measurement |
| 12 | Keyboard navigation | Existing chart-inspection and Touch Type key tests pass | Only what those tests cover |
| 13 | No sensitive data in the repository | Tests run with all `AUGURSPEX_*` variables removed and throw-away state; no key, cache or user file is committed; the research PDFs are ignored by Git | Verified by inspection of the diff |
| 14 | Package contains required assets | `verify_release.py` against the regenerated inventory, on the tree and on an extracted copy of the ZIP | See "Packaging" |
| 15 | Windows and Linux launch files valid | `test_console_free_launch.py`, `test_launch_gate.py` pass on both systems; line endings pinned in `.gitattributes` | The `.vbs` and `.bat` themselves were not double-clicked on a Windows desktop |
| 16 | Existing regression tests pass | Table above | Yes on Linux; one failure on Windows (above) |
| 17 | New functionality has tests | Listed in the changelog | Yes |
| 18 | Manifests match the package | `build_release.py` writes them from the tree; `verify_release.py` re-checks | See "Packaging" |

## Live market sources

One real check, 15 November 2026 05:19 UTC, from a GitHub runner, no keys: **23 of 23 starter markets returned validated history** (`PROVIDER_PROBE.md`). Stooq refused; Strasmore answered for all ten stocks. This is evidence for that hour and that network. It was not repeated from a home connection.

## Packaging

`Tools/build_release.py` regenerated `FILE_INVENTORY.json` and `BUILD_MANIFEST.json` and wrote the ZIP; `Tools/verify_release.py` passed on the source tree and again on a fresh extraction of the ZIP. The ZIP's name and SHA-256 are in `HANDOVER.md` and the pull request. The ZIP was not launched on a desktop: the build machine has no Tk.

## Not verified

- HOME's PLATE VAULT panel is empty in the automated screenshots, although `test_ascii_visibility.py` passes. Whether that is the capture tool or the panel was not established; check it on a real screen.

- Any physical Windows 11 or Linux Mint machine, any real monitor, high-DPI or fractional scaling.
- GPU encoders (NVENC, Quick Sync, AMF) on real hardware.
- Sound: Oggcultist playback, the Latin voices, EIDOLITH viewer audio.
- The first-run requirements window installing into a fresh machine.
- Long sessions, large libraries, long conversions, HDR or unusual sources.
- Market sources from a residential network, and any keyed source with a real key.
- The embedded Oggcultist's own test folder.
