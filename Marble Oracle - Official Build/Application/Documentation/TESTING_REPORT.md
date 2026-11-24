# Testing report: Marble Oracle 0.5.1

## 0.5.0 and 0.5.1 addendum (24 November 2026)

Same development machine as 0.4.9.9 (Ubuntu 24.04, Python 3.12, Tk 8.6.14 under Xvfb). It is still a virtual display, not a physical PC.

| Check | Development machine (Xvfb) | GitHub Linux (Xvfb) | GitHub Windows (native Tk) |
|---|---|---|---|
| Regression scripts, 0.5.0 (PR #13, commit 67aafd9) | 71 passed | **71 passed** (run 45298123831) | **71 passed** (same run) |
| Regression scripts, 0.5.1 (PR #14, commit 2832f72) | **72 passed, 0 failed, 0 skipped** | **72 passed** (run 45303183699) | **72 passed** (same run) |
| OVERCAST's own tests against the suite copy (`test_overcast_package.py`) | 97/97 | pass | pass |
| `test_overcast_workspace_0500.py` | 45/45 | pass | pass |
| `test_appearance_0510.py` (Dark and Light, four sizes) | 260/260; also 260/260 with the interface font forced to DejaVu Sans | pass | pass |
| `--selftest` from a fresh extraction of the ZIP | pass | | |
| `verify_release.py` | pass on the tree and on the extraction | | |

**OVERCAST 1.1.1 as delivered did not open on real Tk.** Its panel failed while being built (`can't pack … inside …`); its own 9 graphical tests failed on Tk 8.6.14. Installing the delivered wheel in a clean environment and running `overcast` reproduced the crash. The 1.1.2 wheel built from the suite's copy installs with the delivered Linux installer and stays running. All 105 of its tests pass on real Tk, packaging tests included.

**Found by CI and fixed in this round:**
- OVERCAST's sidebar lost "Methods" with the runner's fonts. It now measures itself and compacts.
- A few buttons squeezed with a wider fallback font. Dark/Light now use OVERCAST's type sizes.
- On Windows, the EIDOLITH media probe was squeezed by wrapped tools.
- A test assumed a 1920x1080 window on a smaller screen.

**Not verified:**
- A real LM Studio model and live RSS feeds.
- Anything on a physical PC.
- The real system fonts on Fedora (Adwaita Sans or Cantarell) and Windows (Segoe UI).
- Sound.

**Known cosmetic gaps:**
- AUGURSPEX keeps some of its own styling.
- Labels whose text is set while running stay in capitals.
- In Light, OGGCULTIST's cream logo is faint.
- In Classic, OGGCULTIST's HOME button is 4 px narrower than it asks for at 900x580 (this predates 0.5.0).

---

## 0.4.9.9 addendum (22 November 2026)

Same development machine as 0.4.9.8 (Ubuntu 24.04, Python 3.12.3, Tk 8.6.14 under Xvfb at 1920x1080). Still a virtual display, not a physical PC.

| Check | Development machine (Xvfb) | GitHub Linux (Xvfb) | GitHub Windows (native Tk) |
|---|---|---|---|
| `--selftest` (from a fresh extraction of the ZIP) | pass | | |
| Regression scripts | **69 passed, 0 failed, 0 skipped** | **69 passed, 0 failed** (run 44918082283) | **69 passed, 0 failed** (same run) |
| `test_welcome_and_widgets_0499.py` | 34/34 | pass | pass |
| `test_install_0499.py` | 40/40 | pass | pass (the Linux shell-script checks are skipped on Windows, where `bash` is the WSL stub) |
| Screenshots | 71 captured; the welcome guide at 1280x720 and 900x580, the setup window at 780x720 and its minimum 760x640, every workspace at 900x580 and 1280x720 and the CRT housing reviewed by eye | 71 captured | not captured |
| `verify_release.py` | pass on the tree and on a fresh extraction | | |
| "main thread is not in main loop" warnings | 0 (was several per run before the image-lifetime fix) | | |

Found by this round and fixed: the setup window at its old minimum (640x600) clipped its text and squeezed ADD TO APP MENU to 69 px (new check fails on the old layout); the ? guide button did not fit the CRT housing's curved glass (now flat layout only); stale Tk images freed on a worker thread; `test_install_0499.py` failed on Windows because `bash` there is the WSL stub.

Not verified: the installer's `pkexec`/`dnf`/`pacman`/`zypper` installs for real (tests check the command built, not its effect); KDE's `kdialog` messages; the app-menu entry in a real KDE or GNOME menu; anything on a physical PC; sound; live market data. In the CRT housing, EIDOLITH's controls are still clipped by the small glass area (as in 0.4.9.8).

---

## 0.4.9.8 addendum (22 November 2026)

**First run outside GitHub.** The suite ran on the development machine: Ubuntu 24.04, Python 3.12.3, Tk 8.6.14 under Xvfb at 1920x1080, Pillow 12.2.0, mutagen 1.48.1, numpy 2.2.6, FFmpeg present. Still a virtual display, not a physical PC.

| Check | Development machine (Xvfb) | GitHub Linux (Xvfb) | GitHub Windows (native Tk) |
|---|---|---|---|
| `--selftest` | pass | | |
| Regression scripts on 0.4.9.7 as released | 66 passed, 0 failed, 0 skipped | | |
| Regression scripts on 0.4.9.8 | **67 passed, 0 failed, 0 skipped** | **67 passed, 0 failed** (run 44912891286) | **67 passed, 0 failed** (same run) |
| Screenshots | 71 captured (five sizes plus the CRT housing); all six workspaces reviewed at 1280x720, OGGCULTIST at four sizes | 71 captured | not captured |
| Live provider probe | **not possible**: the machine's network refused every market-data host (each source reported "network", nothing was drawn) | not run | |

Found by this run: OGGCULTIST's Settings half covered at 1280x720 and unreachable at 900x580 (fixed; `test_ogg_rail_0498.py` fails on 0.4.9.7 and passes on 0.4.9.8).

---

## 0.4.9.7 addendum (16 November 2026)

GitHub Actions, workflow run 43822976791, no physical PC:

| Check | Linux (Ubuntu 24.04, Tk under Xvfb) | Windows (Server runner, native Tk) |
|---|---|---|
| Regression scripts (`Tools/run_tests.py`) | **66 passed, 0 failed, 0 skipped** | **66 passed, 0 failed, 0 skipped** |
| AUGURSPEX with the clock 60 days ahead | 31 passed | not run |
| Lint, byte-compile | pass | not run |
| Screenshots (five sizes plus the CRT housing) | 71 captured; HOME, PASSPHRASE and TOUCH TYPE at 900x580, HOME at 1216x848 and the CRT housing reviewed by eye | not captured |

The two new scripts are `test_home_keyboard_0497.py` and `test_polish_0497.py`. The Windows job is required from this release. HOME's PLATE VAULT now shows its statues in the screenshots (the capture tool had never run the frame loop), which closes the open question from 0.4.9.3. Hover and focus rings were checked with synthetic events, not with a real mouse.

---

## Earlier addenda

## 0.4.9.5 addendum (16 November 2026)

Linux container (Python 3.12, Tk under Xvfb). `Tools/run_tests.py`: **63 passed, 0 failed, 0 skipped** (62 from 0.4.9.4 plus `test_unified_shell_0495.py`). Every tab was also inspected in screenshots at 1216x848, 960x640, 820x560 and 640x460, and compared with 0.4.9.4 at 640x460. The first push failed one check on GitHub's Windows runner (EIDOLITH MEDIA PROBE at 900x580, 28 px of 30); fixed in the review commit, whose Windows result is in the pull request. Not run on a physical PC.

---


## 0.4.9.4 addendum (16 November 2026)

Run in a Linux container (Python 3.12, Tk under Xvfb at 1600x1000, FFmpeg 6.1), not on a real PC and not on Windows.

| Check | Result |
|---|---|
| Regression scripts (`Tools/run_tests.py`) | **62 passed, 0 failed, 0 skipped** (the 60 from 0.4.9.3 plus two new) |
| Lint (`ruff.toml`) on the changed files | pass |
| New market-data sources against live providers | **not run**: the container cannot reach any provider |
| Rune-stone fix on Windows | GitHub's Windows runner, commit `c29a79e`: `test_rune_click_and_art.py`, the script that failed in 0.4.9.3, **passed**. Not checked on a physical Windows 11 PC |
| GitHub Actions for this branch | see the pull request; not part of this report |

The rest of this file is the 0.4.9.3 report, unchanged.

---

## The 0.4.9.3 report

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
