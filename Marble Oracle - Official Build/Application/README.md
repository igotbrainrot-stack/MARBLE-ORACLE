# MARBLE ORACLE — Integrated Desktop Suite

**Release:** Marble Oracle 0.4.8.5 — EIDOLITH + integrated AUGURSPEX · 13 November 2026 (latest changes: `Documentation/RELEASE_NOTES_0.4.8.5_AUGURSPEX_CHART_LAYOUT.md`)  
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
| **HOME** | Oracle dashboard with rotating AUGURSPEX market history, Latin, ASCII statues, Tarot and Rune animations |
| **OGGCULTIST** | Embedded Oggcultist 2.0.6 audio player, library and audio converter |
| **EIDOLITH** | Local video player, conversion profiles, video inspection, fail-and-continue queue with progress/ETA and per-job logs, standard TV/movie filenames |
| **PASSPHRASE** | Five-card Marble Passphrase Studio |
| **TOUCH TYPE** | Four touch-typing mini-games with finger guidance and saved scores |
| **AUGURSPEX** | Native multi-market watchlist and historical charts inside the suite; no browser tab launch. **CHARTS** shows N chart spaces sized to the available area. Each shows its saved market when it has data, otherwise another watchlist market with data, labelled AUTO-FILLED. Each chart has a **LINE / CANDLES** switch that it remembers; **ALL CHARTS** sets every chart at once. Line by default |

All tabs retain the established dark Oggcultist-inspired visual style and bundled Uberata Clear font.

### AUGURSPEX history sources (0.4.7.8)

- Native charts use price observations returned by public providers: Coinbase/Kraken (cryptocurrency), Yahoo Chart, Stooq, Nasdaq.com website history and Naver (best-effort stock history). Several stock endpoints are unofficial and may refuse requests; they are **not** guaranteed real-time market feeds. TradingView hosted charts remain separate from the Tk-native history canvas.
- If already entitled to documented API access, you can optionally set `AUGURSPEX_ALPHA_VANTAGE_KEY` or `AUGURSPEX_TWELVE_DATA_KEY` in the operating system environment before launching. These are **not required** to run Marble Oracle, not bundled in the ZIP, and must not be committed to public Git repositories. Keys are never written to the settings file.
- Twelve Data uses the exact market ticker and explicit MIC for Australian (XASX), Japanese (XJPX) and Korean (XKRX/XKOS) securities. **Access to ASX markets generally requires paid exchange-specific entitlement/add-ons**, not the provider's free tier.
- HOME and the AUGURSPEX tab share request cooldowns to avoid duplicate provider hammering. Charts label cached or stale history; the native tab's **SOURCE DETAILS** button shows attempted providers and the retry delay.


## EIDOLITH media notes

- FFmpeg and FFprobe are necessary for video encoding/probing. Playback capability depends on local multimedia support.
- The in-app video viewer is an **initial 12 fps preview implementation**, not a fully synchronised libmpv player; HDR, track switching and precise audio/video synchronisation are not assured.
- **RESOLUTION** (CONVERT page): Original, 1080p, 720p or 480p. Video is only scaled down, keeping its aspect ratio (a widescreen film at 720p becomes 1280×536). From 1080p, 720p encodes about 2–3× faster, more for grainy video.
- **Speed (0.4.7):** see `Documentation/EIDOLITH_SPEED_RESEARCH_0_4_7.md`.
  - **Turbo AV1 (preset 12)** is about 2.5× the speed of Fast AV1 for roughly 15% larger files.
  - **USE FAST PROFILE** runs a one-second test encode on each hardware encoder (NVIDIA, Intel Quick Sync, AMD) and picks the first that works. Hardware encoders have not been verified on real hardware by this project.
  - **Don't re-encode video that is already compact AV1/HEVC** (on by default) copies such video in seconds; untick it to force a re-encode.
  - A newer FFmpeg (SVT-AV1 2.3 or later) makes the CPU AV1 profiles faster.
- **Default profile** is now **Fast AV1 (preset 8)**. The old default is still available as **Balanced archive** (much slower, smaller files); a saved choice is kept.
- Upright phone video keeps its shape when resized, interlaced sources (DVD, old TV captures) are deinterlaced automatically, and a job is refused up front when the output folder has under 200 MB free.
- **Network use:** the scrolling news runner and old Bitcoin/gold market panel are removed. HOME uses the AUGURSPEX watchlist for a rotating historical chart, and the native AUGURSPEX tab retrieves market history when networking is enabled. These are public or optionally configured API feeds, which may be delayed, rate-limited or unavailable; `--no-network` disables automatic market requests. Video and audio conversion never use the network.
- **Windows:** if `START MARBLE ORACLE - WINDOWS.vbs` is blocked (VBScript disabled), use `START MARBLE ORACLE - WINDOWS (if the VBS launcher is blocked).bat`. This fallback has not been run on a real Windows machine yet.
- **PASSPHRASE:** a copied passphrase is cleared from the clipboard after 60 seconds (clipboard-history tools may still keep it).
- **SLIM OUTPUT** (on by default) keeps only the video and the main audio track. It drops extra audio tracks (dubs, commentary), subtitles, cover art, fonts, chapters and title metadata, and lists every drop in the job log. Untick it to keep everything. Most of the saving comes from extra audio tracks; subtitles, cover art and metadata are usually under 1 MB together. For the biggest audio saving, also set **AUDIO** to `opus`.
- Two optional SLIM settings (both off by default): **keep English subtitles** (untagged subtitles are kept too; picture-based ones can't go in MP4) and **prefer English audio** over the source's default track (commentary tracks are not chosen).
- **Skip files already converted** (on by default): a file whose output already exists in the output folder, or is already waiting in the queue, is not queued again. Untick it to convert again as ` (2)`.
- **Fast AV1 (preset 8)** sits between Balanced and Faster CPU AV1: several times faster than Balanced, with slightly larger files.
- **Balanced archive** is 10-bit CPU SVT-AV1 and can encode slowly. Choose **USE FAST PROFILE** to prefer compatible NVIDIA NVENC hardware or a quicker CPU preset. Neither speed nor size reduction is guaranteed.
- Automatic TV/movie filenames recognise episode markers such as `S02E05` and movie years; ambiguous names should be reviewed before queuing. Names are short by default (`Mr. Robot (2015) - S01E01.mkv`). Tick **Add episode title** or **Add format tag** (e.g. `[AV1 720p]`) under ORGANISE OUTPUT FILENAME to include them. Clashing names get ` (2)`, and nothing is overwritten.
- Outputs are written separately and checked (track counts, codec, 10-bit, duration); original input files are **never deleted or overwritten**. HDR and unsupported track cases are blocked for safety with a reason.
- The queue runs every **queued** job in order: a failed job is marked FAILED and the next one starts. **CANCEL CURRENT** skips one job, **STOP QUEUE** keeps the rest queued, and failed jobs re-run only with **RETRY**.
- To take jobs off the queue, select them (Ctrl/Shift-click for several) and press **REMOVE SELECTED** or the Delete key, or press **CLEAR ALL**. A job that is converting stays until you CANCEL CURRENT or STOP QUEUE. Removing jobs never touches source files, finished outputs or logs.
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
