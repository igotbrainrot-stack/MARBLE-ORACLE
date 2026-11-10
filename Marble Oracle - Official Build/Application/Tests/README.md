# Marble Oracle tests

Run from the extracted top-level folder:

```sh
python3 Application/Tests/test_refinement.py
xvfb-run -a python3 Application/Tests/test_ogg206_embedded.py
xvfb-run -a python3 Application/Tests/test_tab_layout.py
xvfb-run -a python3 Application/Runtime/Marble_Oracle_App/marble_oracle.py --selftest
```

Xvfb is optional if you are running with a graphical Linux desktop. All tests are non-destructive when used as documented. For Windows run the Python tests in a desktop session; the Xvfb wrapper is Linux-only.

Media requirements: `python3 Application/Tests/test_media_setup.py` validates Linux/Windows installer decision paths without changing packages or downloading binaries.

### EIDOLITH 0.4 queue reliability and naming

```sh
xvfb-run -a python3 Application/Tests/test_eidolith_queue_reliability.py
python3 Application/Tests/test_eidolith_naming_regression.py
```

The reliability test (about 40 s) builds synthetic clips: cover art, subtitles, a timecode track, plus truncated, corrupt and missing inputs. It then checks:
- fail-and-continue batches and per-job logs;
- cover, subtitle and data-stream handling, and 10-bit verification;
- cancel and stop semantics, and explicit retry;
- a real crash/restart with an orphaned FFmpeg (Linux);
- the persisted queue, the progress panel, the Mr. Robot naming case and redacted diagnostics.

It uses a temporary `MARBLE_ORACLE_STATE`. When `nvidia-smi` is present it expects the NVENC job to succeed; otherwise it expects a clean, explained failure. Note: `test_actual_mode.py` rewrites `Tests/TAB_OGGCULTIST_DEFAULT.png`, so run `Tools/verify_release.py` on an untouched copy.

### EIDOLITH 0.2 viewer + workspace test

Run `xvfb-run -a python3 Application/Tests/test_eidolith_workspaces.py` from the build root. This creates a temporary H.264/AAC test video, decodes frames into the in-app viewer, exercises playback controls and fullscreen, checks SELECT ALL in PLAYER and CONVERT, queues a lossless remux, verifies the output and deletes the temporary test files. FFmpeg and FFprobe must be available.
