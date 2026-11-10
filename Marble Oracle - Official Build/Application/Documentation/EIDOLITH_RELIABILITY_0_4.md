# EIDOLITH 0.4 — conversion reliability repair and release notes

**Date:** 10 November 2026 · **Baseline:** `Marble-Oracle-OFFICIAL-Audited-Cleaned-EIDOLITH-0.3-FULL-Windows-Linux.zip`
(SHA-256 `5b87d515188b9fa1722cb8bb18f9f598717178621d6d0e79e0eb716ee25319a9`)

Scope: EIDOLITH conversion only. HOME, OGGCULTIST, PASSPHRASE and TOUCH TYPE, the Oggcultist design
language, the Uberata Clear font, artwork, launchers and media assets are unchanged. The PLAYER page
is unchanged. Sources are still never modified, renamed or overwritten.

## 1. Defects found in 0.3 (with reproduction evidence)

Line numbers refer to the **baseline** `Runtime/Marble_Oracle_App/oracle_eidolith.py` unless stated.
All reproductions used synthetic media generated with FFmpeg 6.1.1.

| # | Defect | Location (0.3) | Reproduction / evidence |
|---|---|---|---|
| D1 | **CANCEL JOB / CANCEL CURRENT stopped the whole queue.** Both set the queue-wide `worker_stop` flag, so every remaining job was abandoned after one cancellation. | `cancel_current` L880–888, `_worker` L891–893 | Queue 3 jobs, cancel the first: jobs 2–3 never start. |
| D2 | **START QUEUE silently re-ran old failed/cancelled jobs** (accepted `queued`, `failed`, `cancelled`). A repeating failure looked like the queue was stuck on one file. | `start_queue` L871, `_worker` L894 | Fail a job, queue a new one, press START: the failed job runs again first. |
| D3 | **CLEAR FINISHED during a run detached the worker from the queue.** It rebinds `self.queue_items` to a new list while `_worker` iterates the old one, so jobs queued afterwards were never processed. | `clear_finished` L449–452 | Start a queue, clear finished, queue more: they stay QUEUED forever. |
| D4 | **Cover art made healthy encodes fail validation.** `-map 0:V:0` intentionally excluded attached pictures, but `_validate_output` compared raw `codec_type == video` counts. | `_build_command` L751–752, `_validate_output` L812–814 | `cover.mp4` (h264+aac+png attached_pic) remux → output has 1 video vs source 2 → “video stream count changed (2 -> 1)”. MKV image attachments behave the same (the Matroska demuxer exposes them as attached_pic video). |
| D5 | **MP4 profiles failed instantly on files with SRT/ASS subtitles.** `encoding_args` always added `-c:s copy`. | `oracle_eidolith_core.py` L134 | `subs.mkv` → *Fast CPU H.264*: FFmpeg exit 234, “Could not find tag for codec subrip … not currently supported in container”. A batch of such files fails every job within seconds. |
| D6 | **Any data stream blocked conversion,** e.g. the timecode (`tmcd`) track that phones and cameras write into `.mov`. | `_preflight_source` L786–787 | `camera.mov` (h264+aac+tmcd) → “Data streams detected”. |
| D7 | **Failures were nearly invisible.** FFmpeg stderr was mixed into the `-progress` pipe, the GUI log kept 300 lines and nothing was written to disk, errors were cut to 125 characters, and progress was text only. A fast failure followed by an idle-looking UI read as “stopped after one”. | `_append_log` L859–864, `_worker` L918–940, L983 | NVENC on a machine without CUDA: only “FFmpeg exited with status 255 (see log)”, with the real cause (“Cannot load libcuda.so.1”) scrolled away. |
| D8 | **Filename damage on human-formatted names.** Dots/underscores always became spaces, hyphens inside words were split, and cutting at `1080p` left a dangling `(`. | `oracle_eidolith_core.py` `clean_words` L55–60 | `Mr. Robot (2015) - S01E01 - eps1.0_hellofriend.mov (1080p BluRay x265 RCVR).mkv` → `Mr Robot (2015) - S01E01 - eps1 0 hellofriend mov ( [AV1].mkv` |
| D9 | **Closing the app during a conversion silently did nothing** (`shutdown` returned False with no message). | `shutdown` L1036–1041 | Click close while encoding: window stays, no explanation. |
| D10 | **No crash/restart handling.** The queue was memory-only; after a crash the `*.eidolith-*-part` file and possibly an orphaned FFmpeg remained. | (absent) | `kill -9` the app mid-encode: partial file and FFmpeg process survive. |
| D11 | Test hygiene: the EIDOLITH tests wrote to the user's real `MARBLE_ORACLE_STATE`; `test_actual_mode.py` rewrites `Tests/TAB_OGGCULTIST_DEFAULT.png`, so `verify_release.py` fails after a test run in a release tree. | Tests | `verify_release.py` passes on a fresh extract and fails after the suite. (EIDOLITH tests fixed; `test_actual_mode.py` left unchanged — run tests on a copy.) |

The SVT-AV1 “slow but alive” case was **not** a defect in itself: the profile description already warns
about it. The defect was that the UI could not show the difference between slow, stalled and failed (D7).

## 2. What changed

**New module `oracle_eidolith_jobs.py`** (UI-independent queue engine, testable without a display):

- **Queue rules.** START runs only `queued` jobs, in list order, and re-reads the list between jobs.
  Any failure (missing input, unreadable input, blocked track plan, FFmpeg non-zero exit, validation)
  marks *that* job FAILED and the queue continues. **CANCEL CURRENT** cancels one job and continues;
  **STOP QUEUE** cancels the current job and leaves the rest QUEUED. Failed, cancelled and interrupted
  jobs run again only after **RETRY FAILED** / **RETRY SELECTED**.
- **Track plan, decided and reported before encoding.**
  - Cover art: kept as MP4 cover art (`attached_pic` copy) or, for MKV, extracted and stored as a real
    Matroska attachment. Copying it as a stream would turn it into a 1-frame video track.
  - Subtitles: copied in MKV. Text subtitles become `mov_text` in MP4, and the report notes that ASS
    styling is lost. Bitmap subtitles (PGS/DVD/DVB) block MP4 with “choose an MKV profile”.
  - Attachments (fonts): copied in MKV; block MP4 as before.
  - Audio: copied. MP4-incompatible codecs (PCM, TrueHD, WMA, Vorbis…) block MP4 copy with a suggestion.
  - Data/timecode streams: dropped and **reported** instead of blocking.
  - HDR, Dolby Vision and multiple main-video tracks: still blocked, unchanged from 0.3.
- **Validation** compares main video, cover art, audio, subtitle and attachment counts against the plan.
  It also checks the output video codec, 10-bit pixel format for 10-bit profiles, and duration.
  Nothing is described as kept unless it was verified.
- **Per-job log files** in `<state>/eidolith_logs/` (Windows `%LOCALAPPDATA%\Marble_Oracle\eidolith_logs`,
  Linux `~/.local/state/Marble_Oracle/eidolith_logs`). Each log holds:
  - platform and FFmpeg version;
  - source, output and profile;
  - the track plan and the safely quoted command;
  - the **complete FFmpeg stderr**, read separately from the progress pipe;
  - the exit code, validation results and final status.

  The newest 300 logs are kept. On failure, the most specific FFmpeg error line is shown in the job
  (for example `Cannot load libcuda.so.1`, plus a hint to use a CPU profile).
- **Persistence and restart.** The queue is saved to `eidolith_queue.json` on every state change.
  On launch, completed jobs are dropped (their logs remain) and queued jobs come back QUEUED, but
  **nothing starts automatically**. Jobs that were running become INTERRUPTED. Only that job's own
  `*.eidolith-<12 hex>-part.*` and `-cover<n>.*` files are deleted. On Linux, an FFmpeg orphaned by a
  crash that is still writing that partial is stopped first. Look-alike or unrelated files are never touched.
- Temporary output, re-probe and the hard-link / `O_EXCL` no-overwrite publish are kept from 0.3.

**`oracle_eidolith.py` (panel)** delegates to the engine. `queue_items` and `worker_thread` are kept as
compatible properties. The QUEUE page adds the following, in the existing styling:

- a **current-job panel**: `JOB n OF m · STATE · file`, a determinate bar when duration is known, an
  **indeterminate sweep** when it is not (no invented percentage), encoded/duration, elapsed wall time,
  speed, ETA, and the time of the last FFmpeg activity;
- after 30 s without a progress report: “NO PROGRESS REPORT … FFmpeg (pid) is still running; check OPEN LOG”.
  If FFmpeg reports but output time stops advancing: “FFmpeg alive but no new output …”. Slow work is
  never labelled as hung;
- colour-coded job rows with `n/m`;
- buttons: **STOP QUEUE**, **RETRY SELECTED**, **OPEN LOG**, **LOG FOLDER**, and **COPY DIAGNOSTICS**
  (a shareable report in which source/output folders and the home folder are replaced by placeholders;
  the full log stays local).

Closing the app during a conversion now asks first. Choosing to stop removes the partial and keeps the
remaining jobs queued for the next launch. The profile description is no longer re-laid out every 180 ms.

**`oracle_eidolith_core.py` naming.**
- Names that already contain spaces keep their punctuation (`Mr.`, `eps1.0_hellofriend.mov`).
- Bracketed release groups are removed whole: `(1080p BluRay x265 RCVR)`, `[Group]`, `{…}`.
- `(2015)` and `(Part 2)` are kept.
- Only unambiguous technical tokens cut bare text, so words such as *Proper* or *Remux* in a title survive.
- In-word hyphens are kept; dangling brackets are removed.
- Scene-style names (`Show.Name.S01E02.Title.1080p…`) produce the same names as 0.3.

Result: `Mr. Robot (2015) - S01E01 - eps1.0_hellofriend.mov [AV1].mkv`.

## 2a. Speed and resolution (added after first review)

- **RESOLUTION** (Original / 1080p / 720p / 480p) is on the CONVERT page.
  - The video is scaled down to fit the box with its aspect ratio kept, and is never scaled up.
  - Portrait video uses the rotated box.
  - The exact even size is computed before encoding, applied to the main video only (cover art is untouched) and verified on the output.
  - Output names are short by default (`Mr. Robot (2015) - S01E01.mkv`). The episode title and a format tag such as `[AV1 720p]` are opt-in tick boxes under ORGANISE OUTPUT FILENAME.
  - Lossless remux cannot resize, so that combination is refused when queuing.
- **Fast AV1 (preset 8)** is a new SVT-AV1 10-bit profile at CRF 30.

Measured speed: grainy 1080p synthetic clip, 2-core Xeon at 2.1 GHz. Values are the fraction of real time (1.0× = as fast as playback).

| Profile | 1080p | 720p |
|---|---:|---:|
| Balanced archive (preset 5) | 0.02× | 0.13× |
| Fast AV1 (preset 8) | 0.20× | 0.62× |
| Faster CPU AV1 (preset 10) | 0.41× | 1.23× |
| Fast CPU H.264 (x264 veryfast) | 0.71× | 1.57× |

SVT-AV1 speed scales with CPU cores, so a desktop with 8–16 cores is typically several times faster than these figures. The ratios between rows are the useful part. NVIDIA NVENC was not measured (no GPU).

## 2b. Slim output (added after first review)

**SLIM OUTPUT** is on by default.
- **Kept:** the main video and one audio track (the source's *default* track, otherwise the first), with its language tag.
- **Dropped:** extra audio, subtitles, cover art, attachments/fonts, chapters and title/tag metadata. Each drop is listed in the plan and log. Dropping forced (foreign-dialogue) subtitles is called out.
- **Validation** expects exactly the kept tracks.

Measured on a 60 s 1080p synthetic source (lossless 5.1 main audio, AC3 commentary, AC3 5.1 Italian dub, 3 subtitles, 0.5 MB cover, font, chapters), encoded with Faster CPU AV1 at 720p:

| Output | Size |
|---|---:|
| Everything kept, audio copied | 29.75 MB |
| SLIM, audio copied | 22.22 MB (−25%; the 2 extra audio tracks were 6.2 MB, the cover 0.5 MB, subtitles ≈0) |
| SLIM + AUDIO opus | 15.68 MB (−47%) |

**Fixed:** AUDIO = opus failed on `5.1(side)` audio (most DVD/Blu-ray AC3/DTS) with “Invalid channel layout … mapping family”. Layouts Opus does not accept are now remapped by channel count (e.g. 5.1(side) → 5.1) and reported.

## 2c. Removing jobs (added after user report)

Before this change, only CLEAR FINISHED existed, so queued jobs could not be removed, and the saved queue brought them back on every launch.
- **REMOVE SELECTED** works on several jobs at once (Ctrl/Shift-click), and the Delete key does the same.
- **CLEAR ALL** empties the queue.
- Both leave the converting job alone, update the saved queue immediately, and never touch files on disk.

## 3. Tests and results

Environment: Ubuntu 24.04 container, Xvfb, Python 3.12.3 (system, Tk 8.6, Pillow 10.2, mutagen 1.48),
FFmpeg 6.1.1 with libx264, libx265, libsvtav1 1.7.0 and NVENC encoders compiled in. **No NVIDIA GPU.**
Each suite was run on a fresh copy of the tree with a temporary `MARBLE_ORACLE_STATE`.

```sh
xvfb-run -a python3 Application/Tests/test_eidolith_queue_reliability.py   # 54 checks
python3 Application/Tests/test_eidolith_naming_regression.py                # 14 cases + checks
# full suite: every Application/Tests/test_*.py, Runtime/Marble_Oracle_App/test_*.py,
# marble_oracle.py --selftest, then (on an untouched copy) Tools/verify_release.py
```

| Run | Result |
|---|---|
| Baseline 0.3, full suite (same environment) | 21/21 tests pass. `verify_release.py` fails only after the tests rewrite `TAB_OGGCULTIST_DEFAULT.png` (D11); it passes on a fresh extract |
| 0.4 branch, full suite | **23/23 tests pass** (the 21 existing tests plus 2 new EIDOLITH tests) |
| `test_eidolith_queue_reliability.py` | **79/79** including resolution, short-name, slim-output, Opus-layout and job-removal checks (54/54 before that addition, repeated 4× with no flakes) |
| `verify_release.py` on the packaged 0.4 tree | PASS (inventory regenerated) |
| Offline launch: `START MARBLE ORACLE - LINUX.sh`, no network namespace, Xvfb, Python 3.12 | Requirements window and main “Marble_Oracle CRT V2 - Integrated” window appear; no download attempted |

The reliability test covers:
- batch fail-and-continue across a missing input, a corrupt input, a truncated input (caught by duration
  validation), and NVENC without a GPU (actionable FFmpeg cause), with good jobs before, between and after;
- in-order execution, one log file per job with every required section, no partials and no live FFmpeg child;
- MP4 and MKV cover art, SRT→mov_text, subtitles and cover kept by remux, timecode drop reported,
  PGS/TrueHD→MP4 blocked, PGS copied in MKV, and real 10-bit AV1 output;
- cancel-continue, stop-keeps-queued, START not re-running cancelled jobs, and explicit RETRY;
- a real crash (`kill -9`) that leaves an orphaned FFmpeg: INTERRUPTED status, orphan stopped, own
  partial removed, three decoy files untouched, queued job not auto-started;
- persisted-queue restore in the GUI, the Mr. Robot end-to-end name with tracks kept, the
  JOB n OF m headline, indeterminate and determinate progress panels, GUI stop, and redacted diagnostics;
- every source file byte-identical afterwards.

## 4. Not verified / known limitations

- **Native Windows 11 is untested.** The Windows-specific paths (`os.startfile`, `CREATE_NO_WINDOW`
  on every new subprocess, hard-link publish on NTFS and the exFAT fallback) were reviewed but not run.
  After a crash on Windows, an orphaned FFmpeg is **not** stopped automatically: its locked partial is
  reported and removal is retried on the next launch.
- **Physical Linux Mint (X11 desktop) is untested.** Tests used Xvfb on Ubuntu 24.04 with Python 3.12,
  which matches Mint 22's Python.
- **NVIDIA hardware is untested.** No GPU was available. Verified only that NVENC profiles fail cleanly
  with the real cause when CUDA is missing. NVENC AV1/HEVC encoding, 10-bit `p010le` output and
  audio/subtitle copy on real hardware still need a run on an NVIDIA machine
  (`test_eidolith_queue_reliability.py` checks NVENC success automatically when `nvidia-smi` is present).
- **Real-world media** (multi-GB Blu-ray remuxes, VFR phone video, broken timestamps) was not available.
  Only synthetic clips were used.
- **Not implemented:** resuming a half-finished encode (an interrupted job restarts from zero on RETRY),
  HDR/Dolby Vision re-encoding (still blocked), and MKV→MP4 chapter fidelity checks.
- ASS/SSA → MP4 loses styling (reported in the plan). Choose MKV to keep it.
- Data/timecode streams are dropped, and MP4 may regenerate a timecode track from metadata.
- The interface font, artwork and other tabs were not visually re-reviewed on a physical display.
  The layout tests (`test_tab_layout`, `test_actual_mode`, `test_eidolith_workspaces`) pass under Xvfb.
