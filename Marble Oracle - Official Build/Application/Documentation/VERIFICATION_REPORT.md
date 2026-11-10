# MARBLE ORACLE — Verification report

> **EIDOLITH 0.4 update (10 November 2026).** In the same Xvfb/Python 3.12/FFmpeg 6.1.1 environment, the 0.3 baseline passed all 21 tests. The 0.4 tree passes **23/23** (the 21 existing tests plus `test_eidolith_naming_regression.py` and `test_eidolith_queue_reliability.py`, now 62/62 checks including 720p scaling and short names). `verify_release.py` passes on the packaged 0.4 tree. An offline launch through `START MARBLE ORACLE - LINUX.sh` was confirmed. Defects, evidence and limitations are in `EIDOLITH_RELIABILITY_0_4.md`. Native Windows 11, physical Linux Mint and NVIDIA hardware remain **untested**. The historical 0.3 report follows unchanged.

**Release:** EIDOLITH 0.3 cleanup, 10 November 2026.  
**Source checkpoint:** `Marble-Oracle-OFFICIAL-EIDOLITH-0.3-Faster-Conversion-Standard-Naming-FULL-Windows-Linux.zip` (SHA-256 `df9f71512120d913f94b2e9736b5824cabc8e6f6ea07ac31928e40b355f9620a`).  
**Environment:** Linux virtual X display (Xvfb), available system Python 3, FFmpeg/FFprobe, isolated HOME/config folders per test. **Not** native Linux Mint or Windows 11.  
**Result:** **9/9 baseline and 19/19 post-cleanup tests passed**.

## Baseline tests — before any cleanup

| Check | Result | Duration |
|---|---|---:|
| `eidolith_speed` | **PASS** | 2.94s |
| `eidolith_workspaces` | **PASS** | 5.48s |
| `main_selftest` | **PASS** | 13.66s |
| `media_setup` | **PASS** | 2.21s |
| `oggcultist` | **PASS** | 7.19s |
| `rune_consistency` | **PASS** | 2.72s |
| `source_texture` | **PASS** | 3.66s |
| `tab_layout` | **PASS** | 15.75s |
| `touch_type` | **PASS** | 8.32s |

Baseline commands were invoked from the untouched extracted original release using `xvfb-run -a python3 Application/Tests/<test>.py`; `main_selftest` used `marble_oracle.py --selftest --no-network`. The tests ran with isolated per-test configuration directories; no user media or preferences were touched. Logs were retained in the cleanup workspace, not inserted into the distributable.

## Expanded post-cleanup tests

| Check | Result | Duration |
|---|---|---:|
| `actual_mode` | **PASS** | 10.07s |
| `ascii_visibility` | **PASS** | 8.91s |
| `console_free` | **PASS** | 1.54s |
| `eidolith_speed` | **PASS** | 3.33s |
| `eidolith_workspaces` | **PASS** | 5.49s |
| `exclusive_handoff` | **PASS** | 2.96s |
| `home_ascii` | **PASS** | 7.69s |
| `launch_gate` | **PASS** | 1.59s |
| `main_selftest` | **PASS** | 13.24s |
| `media_setup` | **PASS** | 1.21s |
| `oggcultist` | **PASS** | 8.10s |
| `refinement` | **PASS** | 1.12s |
| `rune_click` | **PASS** | 22.26s |
| `rune_consistency` | **PASS** | 2.74s |
| `rune_long` | **PASS** | 20.08s |
| `rune_scale` | **PASS** | 8.07s |
| `source_texture` | **PASS** | 5.01s |
| `tab_layout` | **PASS** | 16.82s |
| `touch_type` | **PASS** | 9.32s |

The post-cleanup checks ran against a separate exact copy of the cleaned tree to prevent test-generated screenshots or cache output from changing the packaged release. The test runner set `PYTHONDONTWRITEBYTECODE=1` and isolated `HOME` and `XDG_CONFIG_HOME`.

## What was exercised

- **All five tabs:** HOME, OGGCULTIST, EIDOLITH, PASSPHRASE, TOUCH TYPE; tested clean/retro/flat layouts, navigation, return-home, window resizing.
- **EIDOLITH:** actual generated H.264/AAC clip, in-tab preview controls, select all, user-only fullscreen, FFprobe media inspection, lossless remux, real fast CPU encoding, standardized TV/movie names, output validation, source preservation and filename collision protection. None of these tests establish a 30-minute workload speed guarantee.
- **Oggcultist:** integrated seven-page lifecycle and switching; core app did not receive source changes during cleanup.
- **Touch Type:** gameplay, key handling, pause/resume and save-score logic.
- **Rune, Tarot, ASCII, assets:** 24 Rune types × animation frames, actual clicks/resizing, repeated reading stress, font registration and real source-generated Oggcultist texture equivalence.
- **Launch/setup:** simulated platform-specific dependency checks, console-free process flags, setup GUI handoff and crash reporting. The `install_linux_desktop.sh` executable path was retained; only its `Comment=` metadata was updated.

## Additional package-level checks

- Final source archive integrity (`ZIP.testzip`) and top-level paths: **PASS** (363 files; the two official launchers and `Application/` are the only root entries; Linux launcher mode `0755`).
- All inventory SHA-256 hashes are verified with `python3 Application/Tools/verify_release.py` after the new manifests have been generated.
- Runtime code/artwork comparison against baseline: byte-identical **except** `Application/Runtime/install_linux_desktop.sh`, whose only edit is launcher menu-description text.
- Two documentation-only Rune preview duplicates were removed after SHA-256 identity checks and a reference search; the retained previews remain in `Application/Tools/`.
- Standalone Oggcultist data directories, Uberata Clear, all approved images and all large original ZIP archives are retained unmodified.
- User state folders and source video files are outside this extracted release and were not intentionally accessed or modified.

## Platform and feature limitations

| Item | Verification | Limitation |
|---|---|---|
| Linux/Xvfb GUI | **PASS** | Tests were in a virtual display, not an actual Mint desktop or Wayland session |
| Native Linux Mint | **NOT TESTED** | Real menu integration, hardware audio/video devices and GUI package installation require physical-host acceptance testing |
| Windows 11 | **NOT TESTED** | WScript/Pythonw behavior and Windows FFmpeg tool downloads were not run on a Windows host |
| NVIDIA NVENC | **NOT TESTED** | No physical NVIDIA GPU/driver verification; the selection logic and CPU fallback were tested separately |
| FFmpeg package installation | **SIMULATED** | No apt/pkexec/sudo system modification or Windows network download occurred |
| EIDOLITH AV1 playback | **PARTIAL** | In-app player is a basic preview, not complete libmpv, HDR-accurate, subtitle-switching or precisely synchronised playback |
| User-owned TV/movie media | **NOT TESTED** | Tests use synthetic clips only; unusual HDR/streams/copyrighted media paths may behave differently |
| Full archive / runnable application | **PASS in test environment** | Requires Python/Tkinter and locally available runtime dependencies |

## Verification reproducibility

From an extracted top-level release folder:

```sh
python3 Application/Tools/verify_release.py
xvfb-run -a python3 Application/Tests/test_tab_layout.py
xvfb-run -a python3 Application/Tests/test_ogg206_embedded.py
xvfb-run -a python3 Application/Tests/test_eidolith_speed_naming.py
xvfb-run -a python3 Application/Tests/test_eidolith_workspaces.py
xvfb-run -a python3 Application/Tests/test_eidolith_queue_reliability.py
python3 Application/Tests/test_eidolith_naming_regression.py
xvfb-run -a python3 Application/Runtime/Marble_Oracle_App/marble_oracle.py --selftest --no-network
```

Replace `xvfb-run -a` with normal desktop execution on a physical Linux environment. Tests and package checks must never be interpreted as native Windows or GPU verification.

**No test failures were suppressed.** Any unresolved platform/integration limitations are listed above.

## Fresh ZIP extraction acceptance check

After the final documentation-only cleanup changes, the release was zipped, integrity-tested, extracted into a **new clean folder**, and retested. The previous run recorded **4/4 PASS** for the actual Oracle GUI self-test, five-tab layout/navigation, EIDOLITH 0.3 real FFmpeg encoding/naming and Oggcultist 2.0.6 integration. The extracted release's SHA-256 inventory verifier also passed all 359 inventoried files, plus its internal Rune/Tarot/Latin archive CRC checks. The Linux launcher was extracted with mode `0755`; `bash -n` accepted both official Linux launcher scripts.

These tests are in a virtual Linux display and do **not** constitute native Windows, physical Mint or NVIDIA GPU verification.
