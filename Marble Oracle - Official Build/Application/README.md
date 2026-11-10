# MARBLE ORACLE — Integrated Desktop Suite

**Release:** EIDOLITH 0.4 conversion-reliability edition · 10 November 2026 (see `Documentation/EIDOLITH_RELIABILITY_0_4.md`)  
**Supported launch targets:** Windows 11, Linux Mint (x86-64 desktop)  
**Application:** Python/Tkinter, local-first media features

## Quick start

1. Extract the **complete ZIP** to a normal folder. Do not run directly from inside the ZIP.
2. **Windows:** double-click `START MARBLE ORACLE - WINDOWS.vbs` at the top level. Python 3 with Tkinter and the Windows Python launcher (`pyw`) or `pythonw` must already be installed for the graphical setup to start. Normal startup uses no Command Prompt window.
3. **Linux Mint:** run the top-level `START MARBLE ORACLE - LINUX.sh` (make executable with `chmod +x` if extraction removed its executable flag). For a launcher with no terminal, install the menu shortcut once using `bash Application/Runtime/install_linux_desktop.sh`, then open **Marble Oracle** from the application menu.
4. The **requirements checker runs before Oracle** and asks permission for missing components. Python libraries are installed in a private virtual environment. FFmpeg/FFprobe/FFplay may require the platform's package manager or a verified tool download. No unattended system-wide installation is performed.

### Tabs (left to right)

| Tab | Purpose |
|---|---|
| **HOME** | Wire, market ticker, Latin, 14 ASCII statues, Tarot and enlarged Rune animations |
| **OGGCULTIST** | Embedded Oggcultist 2.0.6 audio player, library and audio converter |
| **EIDOLITH** | Local video player, conversion profiles, video inspection, fail-and-continue queue with progress/ETA and per-job logs, standard TV/movie filenames |
| **PASSPHRASE** | Five-card Marble Passphrase Studio |
| **TOUCH TYPE** | Four touch-typing mini-games with finger guidance and saved scores |

All tabs retain the established dark Oggcultist-inspired visual style and bundled Uberata Clear font.

## EIDOLITH media notes

- FFmpeg and FFprobe are necessary for video encoding/probing. Playback capability depends on local multimedia support.
- The in-app video viewer is an **initial 12 fps preview implementation**, not a fully synchronised libmpv player; HDR, track switching and precise audio/video synchronisation are not assured.
- **Balanced archive** is 10-bit CPU SVT-AV1 and can encode slowly. Choose **USE FAST PROFILE** to prefer compatible NVIDIA NVENC hardware or a quicker CPU preset. Neither speed nor size reduction is guaranteed.
- Automatic TV/movie filenames recognise episode markers such as `S02E05` and movie years; ambiguous names should be reviewed before queuing.
- Outputs are written separately and checked (track counts, codec, 10-bit, duration); original input files are **never deleted or overwritten**. HDR and unsupported track cases are blocked for safety with a reason.
- The queue runs every **queued** job in order: a failed job is marked FAILED and the next one starts. **CANCEL CURRENT** skips one job, **STOP QUEUE** keeps the rest queued, and failed jobs re-run only with **RETRY**.
- The QUEUE page shows **JOB n OF m**, a progress bar (or an indeterminate sweep when duration is unknown), elapsed time, speed, ETA and the last FFmpeg activity. **OPEN LOG** shows the full per-job log; **COPY DIAGNOSTICS** copies a shareable report with your folder names removed.
- The queue is saved. After a restart, queued jobs come back (nothing starts by itself), interrupted jobs are marked, and only their own partial files are removed. Logs: `eidolith_logs` in the state folder below.

## Requirements and troubleshooting

| Requirement | Notes |
|---|---|
| Python 3 + Tkinter | Needed to display first-run setup on either OS |
| Pillow/ImageTk, Mutagen | First-run setup checks/install offers; exact support depends on platform |
| FFmpeg/FFprobe/FFplay | Video/audio processing and playback; first-run checker offers help |
| Optional OpenCV, NumPy, Jeepney, Soundcard | Needed only by particular video/audio integrations |
| NVIDIA driver + FFmpeg NVENC | Optional accelerated video conversion, not guaranteed by the encoder list alone |

If launching fails, check the setup window's diagnostic log path and these **platform state folders**:

- Linux: `~/.local/state/Marble_Oracle/` and `~/.local/share/MarbleOracleSuite/`
- Windows: `%LOCALAPPDATA%\Marble_Oracle\` and `%LOCALAPPDATA%\MarbleOracleSuite\`

Saved preferences, progress and user media live outside the release directory. **Do not delete state folders to perform an update.**

To run the main GUI self-test on a Linux desktop:

```bash
python3 Application/Runtime/Marble_Oracle_App/marble_oracle.py --selftest --no-network
```

Under a headless Linux virtual display, add `xvfb-run -a` before `python3`. See `Application/Tests/README.md` for the wider tests.

## Project layout and reference material

- `Application/Runtime/` — launch/checker entry points and the intact application source/assets (including embedded Oggcultist).
- `Application/Tests/` — regression tests and test assets.
- `Application/Tools/` — retained asset regeneration scripts, previews and utilities.
- `Application/Documentation/` — **current** feature notes, design reference, audits and manifests.
- `Application/Documentation/History/` — preserved historical guides, handovers and old manifests.

Start with `Application/Documentation/DOCUMENTATION_INDEX.md`. For cleanup evidence see `AUDIT_REPORT.md`, `VERIFICATION_REPORT.md` and `PROJECT_STRUCTURE.md`.

This package is **Python source**, not a self-contained Windows executable. Dependency installation, the native Windows launch path and actual NVIDIA encoding remain system-dependent.
