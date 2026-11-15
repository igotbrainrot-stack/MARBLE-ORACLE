# Handover: Marble Oracle 0.4.9.3

15 November 2026. For whoever picks this up next, human or AI.

## Where things are

- **Repository:** `igotbrainrot-stack/MARBLE-ORACLE`
- **This work:** branch `claude/marble-oracle-0493-refinement`, based on `handover/marble-oracle-0492-source-20261114` (PR #5). Nothing was merged; the five earlier pull requests are untouched.
- **The branch is the whole application.** It contains every asset archive, font and texture. Only the two third-party research PDFs are left out of Git (they are in the release ZIP under `Documentation/Research/`).
- **Read first:** `README.md`, then `ARCHITECTURE.md`, `DEVELOPMENT.md`, `TESTING_REPORT.md`, `CHANGELOG.md`.

## State in one paragraph

All six workspaces work as in 0.4.9.2. This release fixed real defects (market failure reporting, a broken adapter, FFmpeg left running on Windows, controls lost at 900x580), removed dead code that still shipped, gave the project a test runner, CI on Linux and Windows, lint, a build tool and current documentation. The Linux suite is fully green; Windows has one known failure at a window size below the supported minimum. Nothing has yet been run on a physical PC.

## What was not done, honestly

The brief asked for a complete redesign and refactor of every workspace. What was done is the stabilising half of that, plus a start on the rest:

| Area | Done | Not done |
|---|---|---|
| AUGURSPEX | Provider layer, failure kinds, routing from live evidence, header and rail tidied, axis labels, signals | Splitting `providers.py` by asset class; per-source freshness thresholds |
| EIDOLITH | Layout at all sizes, process handling, file-safety proof | No change to the conversion pipeline itself; viewer is still a 12 fps preview |
| HOME | Dead feeds removed | No visual or layout redesign; `marble_oracle.py` is still one 3,700-line module |
| OGGCULTIST | One crash fixed | Deliberately not edited: it is a complete vendored application |
| PASSPHRASE | Security reviewed and tested (OS random source, nothing logged, clipboard cleared) | No interface change |
| TOUCH TYPE | A focus fix in its test | No interface change |
| Design system | Shared tokens and two shared widgets, used by two workspaces | Not yet adopted by HOME, PASSPHRASE, TOUCH TYPE; no shared focus/hover/disabled styling, tooltips or context menus |
| Refactor | Tk-free logic split out of AUGURSPEX; dead code removed; one version number | The large modules remain large (listed in `ARCHITECTURE.md`) |
| Optimisation | Cache bounded; helper processes collected; two unused start-up objects removed | No start-up or redraw measurements were taken |

## Next steps, in order of value

1. **Run it on a real Windows 11 PC and a real Linux Mint PC.** Launchers, first-run requirements window, sound, a GPU encode, a long conversion, AUGURSPEX from a home connection. Record the result in `TESTING_REPORT.md`. Nothing else on this list is worth more.
2. **Windows, 640x460, rune stones.** `Scene.draw_runes` in `marble_oracle.py` computes the stone height from the panel height minus fixed bands; with Windows font metrics that reaches zero in the STATUE layout. Either raise the minimum window size on Windows or let the bands give way. `test_rune_click_and_art.py` reproduces it on the Windows CI job.
3. **Make the Windows job required.** It is informational (`continue-on-error`) until item 2 is closed.
4. **Carry the shared design into HOME, PASSPHRASE and TOUCH TYPE:** tokens from `oracle_design.py`, `flow` and `wrap_to_parent` from `oracle_widgets.py`, then one focus/hover/disabled treatment for every button.
5. **Split `marble_oracle.py`:** move each HOME panel (tarot, runes, Latin, statues, wire, market chart) into its own module behind the existing `Scene` methods. Keep the GUI tests green on both systems at every step.
6. **Run the embedded Oggcultist's own tests** (`Oggcultist/tests/`) from the suite runner, or record why not.
7. **Measure** start-up time and tab-switch time before optimising anything further.

## Rules worth keeping

- Never draw a price no source returned; never swap a market without saying so on the chart.
- Never delete or overwrite a user's source file; delete only partial files the queue itself created.
- A test that cannot run is a SKIP, not a pass. Do not loosen a check to get green.
- Do not commit keys, state folders, caches, imported CSVs or the research PDFs.
- Do not remove an asset because a checkout lacks it; `verify_release.py` knows what is required.
- Leave earlier pull requests alone; merge nothing without the owner's say-so.

## Working without a local display

This release was developed on a machine with no Tk. The loop that worked: push to a `claude/**` branch, let the `tests` workflow run, read the job log. A manual run of the workflow can filter tests by name, print the screenshots into the log as base64 JPEG, and run the live provider probe. The test runner prints every thread's position shortly before a test's time limit, which is how the Windows freeze was located.

## Release artefact

Filled in when the ZIP is built; see the pull request description for the same values.

- **ZIP:** `Marble-Oracle-0.4.9.3-Windows-Linux.zip`
- **SHA-256:** recorded in the pull request (the checksum cannot be written inside the file it describes)
- **Previous release:** `Marble-Oracle-0.4.9.2-PDF-RESEARCH-STOCK-FEEDS-Windows-Linux.zip`, SHA-256 `839970fe65eef4c77ec3e0edfbea6d4e4f7f501fe458158e1327719fac764945` (checked against the handover before work began)
