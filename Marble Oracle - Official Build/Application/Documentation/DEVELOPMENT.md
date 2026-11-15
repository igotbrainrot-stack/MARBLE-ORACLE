# Development

## Requirements

- Python 3.10 or newer with Tkinter.
- Pillow, Mutagen (and optionally NumPy, OpenCV) for the full suite; FFmpeg/FFprobe/FFplay for EIDOLITH.
- For headless Linux testing: Xvfb.

On Linux Mint / Ubuntu:

```bash
sudo apt install python3-tk python3-pil python3-pil.imagetk python3-mutagen python3-numpy python3-opencv ffmpeg xvfb
```

On Windows: Python from python.org (includes Tk), then `python -m pip install pillow mutagen numpy opencv-python`, and FFmpeg from any source on `PATH`.

## Run from source

```bash
cd "Marble Oracle - Official Build"
python3 Application/Runtime/Marble_Oracle_App/marble_oracle.py --no-network     # skips the requirements window
python3 Application/Runtime/Marble_Oracle_App/marble_oracle.py --version
python3 Application/Runtime/Marble_Oracle_App/marble_oracle.py --selftest --no-network
```

Use `MARBLE_ORACLE_STATE=/tmp/somewhere` (and a different `HOME`) to keep experiments away from your real settings.

## Tests

Every test is a plain script that exits non-zero on failure. `Tools/run_tests.py` runs each in its own process with a throw-away state folder and with all `AUGURSPEX_*` variables removed, so a test can never touch real preferences or send a real API key.

```bash
xvfb-run -a -s "-screen 0 1920x1080x24" python3 Application/Tools/run_tests.py            # everything, headless Linux
python3 Application/Tools/run_tests.py augurspex signals                                   # only names containing these words
python Application\Tools\run_tests.py                                                      # Windows desktop session
```

A script that cannot start because Tk is missing is reported as SKIP with the reason; it is never counted as a pass. Tests that need no display (providers, signals, file safety, passphrase, process cleanup, naming) run anywhere.

Conventions:

- New behaviour gets a test in `Application/Tests/` named `test_<workspace>_<topic>_<version>.py`.
- Fixtures use dates relative to today. CI re-runs the AUGURSPEX tests with the clock 60 days ahead to catch fixed dates.
- A failing test is either a regression (fix the code) or a documented change of intent (update the test and say why in the test). Never loosen a check to get a pass.

## Continuous integration

`.github/workflows/tests.yml` runs on every push to a `claude/**` branch and on pull requests:

| Job | What it proves |
|---|---|
| Linux · Tk under Xvfb · FFmpeg | The whole suite on Ubuntu 24.04; lint; byte-compile; screenshots of every workspace at 900x580, 1000x650, 1216x848, 1280x720 and 1920x1080 (uploaded as an artifact). |
| Windows · native Tk · FFmpeg | The whole suite on Windows Server with the python.org Tk build and Chocolatey FFmpeg. |
| Linux · clock +60 days | Date-dependent fixtures. Informational. |
| Live provider probe | Manual only (`workflow_dispatch` with `probe_providers`): asks every no-key source for every starter market. |

Manual runs can filter tests by name and can print the screenshots into the log as base64 JPEG, for environments that cannot download artifacts.

## Lint

```bash
ruff check "Marble Oracle - Official Build/Application"
```

`ruff.toml` at the repository root enables the rules that find real mistakes (undefined names, unused variables and imports, redefinitions, comparison and exception mistakes). The embedded Oggcultist and the legacy shell modules are held to the correctness rules only. The formatter is not applied to existing modules.

## Looking at the interface

```bash
xvfb-run -a -s "-screen 0 1920x1080x24" python3 Application/Tools/capture_screens.py /tmp/screens
```

writes a PNG of every workspace (and EIDOLITH's four pages, and AUGURSPEX with fixture data at 1, 2, 4 and 9 charts) at each supported size. The AUGURSPEX fixture is labelled "TEST FIXTURE, NOT LIVE" on screen.

## Market providers

```bash
python3 Application/Tools/probe_providers.py --markdown probe.md
```

is the only code that contacts real providers outside the running application. It prints outcomes, bar counts and dates, never prices. Run it before changing routing, and record the result in `PROVIDER_PROBE.md`.

Adding a source: write `read_<name>(symbol, period, getter)` in `providers.py` returning `finish(...)`; add it to `SOURCE_INFO`, `CACHE_TTL`, `_routes`, `provider_plan` and the `functions` table in `_fetch_impl`; give it fixture tests for a good reply, an empty reply, a wrong-symbol reply and an error reply. A source that needs a key must not appear in a keyless route.

## Building a release

```bash
# 1. set the version and date in Application/Runtime/Marble_Oracle_App/oracle_version.py
# 2. put the two research PDFs in Application/Documentation/Research/ (they are not in Git)
python3 Application/Tools/build_release.py --zip ../Marble-Oracle-<version>-Windows-Linux.zip
python3 Application/Tools/verify_release.py
```

`build_release.py` rewrites `FILE_INVENTORY.json` and `BUILD_MANIFEST.json` from the tree on disk and writes a reproducible ZIP (sorted entries, fixed timestamps, launchers marked executable). `verify_release.py` then checks every file against the inventory; run it again on an extracted copy of the ZIP. Commit the regenerated JSON files with the release.

Do not commit: API keys, anything from the state folders, imported CSVs, provider caches, the research PDFs, or media you converted while testing.
