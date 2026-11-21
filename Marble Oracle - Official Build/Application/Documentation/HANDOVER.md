# Handover: Marble Oracle 0.4.9.8

22 November 2026 (0.4.9.7: 16 November). For whoever picks this up next, human or AI. Earlier handovers (0.4.9.3 to 0.4.9.5) are in `History/HANDOVER_0.4.9.3-0.4.9.5.md`; this file replaces them.

## Where things are

- **Repository:** `igotbrainrot-stack/MARBLE-ORACLE`. `main` is still the 10 November 2026 baseline; nothing has been merged since.
- **Pull requests:** each version is a draft PR stacked on the one before, so each diff shows only its own work. **Merge nothing without the owner's say-so.**

| PR | Branch | Version | In one line |
|---|---|---|---|
| #1 to #5 | various | 0.3 to 0.4.9.2 | EIDOLITH 0.4, AUGURSPEX chart repairs, the 0.4.9.2 handover |
| #6 | `claude/marble-oracle-0493-refinement` | 0.4.9.3 | Honest market states, file safety, layouts at 900x580, test runner, CI, docs |
| #7 | `claude/marble-oracle-0494-data-sources` | 0.4.9.4 | Stooq key, backup market sources, rune stones at 640x460 |
| #8 | `claude/marble-oracle-0495-unified-design` | 0.4.9.5 | One page shell (`oracle_shell.py`) for every workspace |
| #9 | `claude/marble-oracle-0496-design-prototype` | 0.4.9.6 | Contrast, focus vs current, Escape never quits, EIDOLITH Convert, AUGURSPEX grid and axis |
| #10 | `claude/marble-oracle-0497-polish` | 0.4.9.7 | HOME keyboard and hover, fit fixes at 900x580, Windows CI required, this handover |
| **#11** | **`claude/marble-oracle-0498-ogg-rail`** | **0.4.9.8** | **OGGCULTIST rail: Settings always reachable, icons fit at 900x580** |

- **The branch is the whole application:** every asset archive, font and texture is in Git. Only the two third-party research PDFs are left out (`.gitignore`); they are in the release ZIP under `Documentation/Research/`.
- **Read next:** `README.md`, `ARCHITECTURE.md`, `DEVELOPMENT.md`, `CHANGELOG.md`, `TESTING_REPORT.md`.

## State in one paragraph

All six workspaces work, share one page shell and one interaction look (hover, a cream keyboard-focus ring, an amber "current" fill), and HOME can now be used from the keyboard. The whole regression suite passes on GitHub's Linux runner (Tk under Xvfb) and on its Windows runner (native Tk), and since 0.4.9.7 the Windows job is required. **Nothing has been run on a physical PC, and none of the market sources added in 0.4.9.4 has been seen answering live.**

## What 0.4.9.8 changed

OGGCULTIST's Settings item was half covered by HOME at 1280x720 and unreachable at 900x580, where Converter and Album Art were also cut off. Fixed in `oracle_ogg_tab.py`; see the changelog. It was found by running the suite on a virtual display with a local Tk (below), not from CI screenshots.

## What 0.4.9.7 changed

- **HOME from the keyboard.** HOME's controls are drawn on a canvas, so Tab did nothing there. `oracle_home_focus.HomeFocusMixin` (mixed into `Scene`) gives them a Tab order (reading order), Enter/Space to press, Escape to leave, the suite's cream focus ring, and a quiet hover outline. Close, minimise and the dials are not in the Tab order.
- **Fit fixes at 900x580.** THREE CUTS: card captions no longer run into each other, and the TAROT / RUNES switch moved into the header row (it covered the third card). Page descriptions in the shared shell are shortened with "…" (full text on hover) instead of running off the edge mid-word.
- **PLATE VAULT was never broken.** It looked empty in every automated screenshot because the capture tool never ran the frame loop that draws the statues. The tool now does; the statues appear.
- **Windows CI is required.**

## What is verified, and how

| Claim | Evidence |
|---|---|
| The suite launches and every workspace opens | GUI tests on Linux and Windows runners |
| HOME keyboard focus, Enter, Escape, hover, ring after a resize | `test_home_keyboard_0497.py`, both runners |
| No overlap or cut-off text at the four supported sizes | Layout tests (EIDOLITH, AUGURSPEX, shell, polish) plus screenshots reviewed by eye |
| Conversions never touch the original | `test_eidolith_file_safety_0493.py` with real FFmpeg, both runners |
| No invented prices | Provider tests with controlled replies; live probe of the keyless sources on 15 Nov 2026 |

## Not verified

- Any physical Windows 11 or Linux Mint PC: the launchers by double-click, the first-run requirements window, real monitors and display scaling.
- Sound (Oggcultist, the Latin voices, the EIDOLITH viewer), GPU encoders, long conversions, HDR sources.
- Market sources from a home connection; every keyed source; all sources added in 0.4.9.4.
- The hover outline and focus ring as seen with a real mouse on a real screen (tests drive them with synthetic events).
- The embedded Oggcultist's own `Oggcultist/tests/` folder.

## Next steps, in order of value

1. **Run it on a real Windows 11 PC and a real Linux Mint PC.** Launch, first run, sound, one conversion, AUGURSPEX from a home connection, HOME with Tab. Record what happens in `TESTING_REPORT.md`.
2. **Probe the market sources from a normal connection:** `python3 Application/Tools/probe_providers.py --markdown probe.md`, with keys set for the keyed ones; replace `PROVIDER_PROBE.md`. Least certain: data.go.kr's request format, EODHD's free-plan coverage, Stooq's keyed reply.
3. **Continue the redesign list from 0.4.9.6** (its design document is not in the repository; ask the owner for it): sentence case, tab subtitles, HOME at the smallest sizes, AUGURSPEX's single control row, PASSPHRASE and TOUCH TYPE changes, the CRT glass inset, the requirements window.
4. **640x460.** It is the smallest size the window allows (below the supported 900x580). Some EIDOLITH buttons and AUGURSPEX tool captions are still clipped there.
5. **Split `marble_oracle.py`** (about 3,700 lines): move each HOME panel into its own module behind the existing `Scene` methods, the way `oracle_home_focus.py` was added. Keep the GUI tests green on both runners at every step.
6. **Run Oggcultist's own tests** from the suite runner, or record why not.
7. **Measure** start-up and tab-switch time before optimising anything.

## Rules worth keeping

- Never draw a price no source returned; never swap a market without saying so on the chart.
- Never delete or overwrite a user's source file; delete only partial files the queue itself created.
- A test that cannot run is a SKIP, not a pass. Do not loosen a check to get green.
- Do not commit keys, state folders, caches, imported CSVs or the research PDFs.
- Do not remove an asset because a checkout lacks it; `verify_release.py` knows what is required.
- New workspace UI uses `oracle_shell.py` (layout, type, buttons) and `oracle_widgets.py` (`flow`, `wrap_to_parent`, `ellipsize`, `tooltip`); colours come from `oggcultist_design_system.COLOR`.
- Escape never quits. Focus is the cream ring; "current" is the amber fill. Do not reuse one for the other.

## Running the suite on a development machine without Tk

From 0.4.9.8 the suite was run directly on the development machine (Ubuntu 24.04, Python 3.12, Xvfb and FFmpeg already present) after installing, from files the owner supplied and checked against the publishers' SHA-256 values: the Ubuntu 24.04 packages `libtcl8.6`, `libxft2`, `libtk8.6`, `tk8.6-blt2.5`, `blt` and `python3-tk` (`dpkg -i`), and the cp312 wheels for Pillow, mutagen and numpy into a venv made with `--system-site-packages` (`pip install --no-index --find-links`). Then:

```bash
xvfb-run -a -s "-screen 0 1920x1080x24" <venv>/bin/python Application/Tools/run_tests.py
xvfb-run -a -s "-screen 0 1920x1080x24" <venv>/bin/python Application/Tools/capture_screens.py <out>
```

The whole suite runs in a few minutes and a full set of screenshots in under three, against about ten minutes per CI round. The machine's network did not reach any market-data host, so the live provider probe still has to run on CI or a home connection.

## Working without a local display

Every release from 0.4.9.3 to 0.4.9.7 was developed on machines with no Tk. The loop that works: push to a `claude/**` branch, let the `tests` workflow run, read the job logs. A manual run (`workflow_dispatch`) can filter tests by name, print the screenshots into the log as base64 JPEG (`screens_in_log`), and run the live provider probe. The test runner prints every thread's position shortly before a test's time limit.

## Release artefact

Built with `python3 Application/Tools/build_release.py --zip <path>` from this branch plus the two research PDFs; checked with `verify_release.py` on the tree and on a fresh extraction. The ZIP's name and SHA-256 are in the pull request (a checksum cannot be written inside the file it describes).
