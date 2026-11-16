# Marble Oracle

**Version 0.4.9.5 · 16 November 2026 · Windows 11 and Linux Mint**

A dark, local-first desktop suite: an oracle dashboard, a music player, a video converter, a market observatory, a passphrase generator and a typing trainer in one window. Python and Tk; nothing is sent anywhere except the market-history requests AUGURSPEX makes when you open it.

## Start it

1. Extract the whole ZIP to a normal folder (do not run it from inside the ZIP).
2. **Windows:** double-click `START MARBLE ORACLE - WINDOWS.vbs`.
   If Windows blocks VBScript, use `START MARBLE ORACLE - WINDOWS (if the VBS launcher is blocked).bat`.
3. **Linux Mint:** run `START MARBLE ORACLE - LINUX.sh` (`chmod +x` it first if extraction dropped the executable flag).
   For a menu entry with no terminal: `bash Application/Runtime/install_linux_desktop.sh`, once.

You need Python 3 with Tkinter already installed. On first run a requirements window checks for the rest (Pillow, Mutagen, FFmpeg) and asks before installing anything; Python libraries go into a private environment, never system-wide.

## The six workspaces

| Tab | What it is for |
|---|---|
| **HOME** | The oracle dashboard: Latin word of the moment, ASCII statues, tarot and runes, the transmission scene, and a rotating history chart from your AUGURSPEX watchlist. |
| **OGGCULTIST** | Music player, library and audio converter (embedded Oggcultist 2.0.6). |
| **EIDOLITH** | Video player and converter: AV1/HEVC/H.264 profiles, a queue that carries on past a failed job, per-job logs, tidy TV and film filenames. Originals are never deleted or overwritten. |
| **AUGURSPEX** | Market history for stocks, currencies and crypto: 1 to 9 charts, line or candles, source details, signals, an observation table and CSV import/export. History, not live quotes. |
| **PASSPHRASE** | Three words, a number and a symbol drawn from the operating system's secure random source. Nothing is saved; a copied phrase is cleared from the clipboard after 60 seconds. |
| **TOUCH TYPE** | Four typing games with finger guidance and saved best scores. |

Press **F1** anywhere for the field guide. Every workspace has a **HOME** button, and the tab strip is always visible.

## Market data in one paragraph

AUGURSPEX shows what public sources return and says where each chart came from. Without any API key, all 23 starter markets returned validated history in the live check of 15 November 2026 (crypto from exchanges, currencies from central-bank reference rates, US stocks and ETFs from a public end-of-day demo feed limited to about a year). That is evidence for that day and network, not a guarantee: free sources throttle, change and disappear. When a source fails, the chart says which kind of failure it was; it never draws an invented price or quietly swaps in another market. Details, the optional API keys and what each status means: [`Documentation/MARKET_DATA.md`](Documentation/MARKET_DATA.md).

## Where your data lives

Settings, scores, queues, watchlists and caches are outside the program folder, so replacing the folder with a newer release keeps them:

- Linux: `~/.local/state/Marble_Oracle/`, `~/.local/share/MarbleOracleSuite/`, `~/.config/augurspex/`, `~/.cache/augurspex/`
- Windows: `%LOCALAPPDATA%\Marble_Oracle\`, `%LOCALAPPDATA%\MarbleOracleSuite\`, and `.config\augurspex` / `.cache\augurspex` in your user folder

Do not delete these to update.

## If something goes wrong

See [`Documentation/TROUBLESHOOTING.md`](Documentation/TROUBLESHOOTING.md). The short version: the requirements window shows the path of its diagnostic log; EIDOLITH's QUEUE page has **OPEN LOG** and **COPY DIAGNOSTICS**; AUGURSPEX has **SOURCE DETAILS**.

## Known limitations

- Not yet run on a physical Windows 11 or Linux Mint machine by this project. Automated tests run on Ubuntu (Tk under a virtual display) and on Windows Server (native Tk); see [`Documentation/TESTING_REPORT.md`](Documentation/TESTING_REPORT.md) for exactly what passed where.
- GPU encoders (NVIDIA, Intel, AMD) are probed with a one-second test encode before use but have not been verified on real hardware.
- EIDOLITH's in-app viewer is a 12 fps preview, not a frame-accurate player; HDR sources are refused for conversion rather than converted wrongly.
- Free market sources are best-effort (above). The no-key stock source gives daily bars only.
- This is Python source, not a self-contained executable.

## For developers

- [`Documentation/ARCHITECTURE.md`](Documentation/ARCHITECTURE.md): how the code is organised.
- [`Documentation/DEVELOPMENT.md`](Documentation/DEVELOPMENT.md): running tests, linting, CI, building the release ZIP.
- [`Documentation/CHANGELOG.md`](Documentation/CHANGELOG.md): what changed, release by release.
- [`Documentation/HANDOVER.md`](Documentation/HANDOVER.md): current state and what to do next.
- [`Documentation/DOCUMENTATION_INDEX.md`](Documentation/DOCUMENTATION_INDEX.md): everything else, including the preserved history.

Quick check from the extracted folder:

```bash
python3 Application/Tools/verify_release.py                    # every file matches the inventory
xvfb-run -a python3 Application/Tools/run_tests.py             # all regression tests (Linux, headless)
python Application\Tools\run_tests.py                          # the same, in a Windows desktop session
```
