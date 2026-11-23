# OVERCAST changelog (formerly SIGNAL / News Oracle)

## 1.1.2 — Runs on real Tk; fits the Marble Oracle workspace (24 November 2026)

Made while bringing OVERCAST into Marble Oracle 0.5.0. Forecasts, the ledger, settings, the engine and the event API are unchanged.

- **Fixed: the window did not open on real Tk.** 1.1.1 put its pages in one frame and then packed the status line `before` them from another, which Tk refuses (`can't pack … inside …`). All 1.1 graphical tests had run against a stand-in for Tk, so this was not seen. On Tk 8.6.14 (Xvfb) the 9 graphical tests failed until this fix; all 97 tests pass now.
- **Fixed: controls as drawn by real Tk:**
  - **Buttons:** they were twice the intended height, because Tk adds a style's padding on top of the rounded artwork's border. They are now compact pills, and the ~11-character minimum width that the `clam` base theme gives every button is removed.
  - **Dropdown arrow:** it was the base theme's black square. It is now a drawn chevron in the field colour.
  - **Page border:** the white border round the page area is gone.
- **Fits small windows, down to the suite at 900x580 and its CRT housing (about 620x490):**
  - **Command bar:** it flows over two or three rows instead of losing Refresh and Cancel.
  - **Split views:** side-by-side views (News, Clusters, Evidence, Calendar) stack vertically when the page is narrow, with two-thirds of the height for the main view.
  - **Settings:** the page scrolls and uses one column when narrow; hints wrap to the card.
  - **Sidebar:**
    - It narrows (220 → 180 → 150 px) and drops its tagline, then its brand block and group headings, as the window gets shorter, so every page and the model status stay visible.
    - The page title shrinks and the description is hidden in very short windows.
- **Dashboard:** "Due to resolve" and "Top risks" keep their size on a narrow page.

## 1.1.1 — Installable package (24 November 2026)

- **Installable package:** `pyproject.toml` builds the wheel `overcast_forecast-1.1.1-py3-none-any.whl` and a source archive. There are no third-party dependencies, so it installs offline.
- **Commands:**
  - `overcast` opens the app; `overcast --version` and `overcast --help` work;
  - `overcast-cli` (or `overcast cli …`) runs the headless tools;
  - `overcast-gui` opens the app on Windows without a console window;
  - `python -m overcast` is the same as `overcast`.
- **Installers:**
  - `install_overcast_linux.sh` / `uninstall_overcast_linux.sh` (per-user): a private environment, commands in `~/.local/bin`, an app-menu entry and an icon;
  - `install_overcast_windows.bat` / `uninstall_overcast_windows.bat`: a private environment and a Start menu shortcut;
  - neither touches the forecast data folder.
- **App icon:** a cloud over an amber sun on a rounded tile (SVG, PNG, ICO). It is used for the window and dock, and the window class `Overcast` matches the desktop entry.
- **Clear error without Tkinter:** if Tkinter is missing, the app prints the exact install command (Fedora: `sudo dnf install python3-tkinter`) instead of a traceback.
- **Tests:** `test_v111_packaging.py` (8), covering entry points, version, CLI routing, the Tk-missing hint, icons, the desktop entry, and that installers never touch user data. 105 tests in total.

## 1.1.0 — Apple-inspired redesign, review and accuracy fixes (23 November 2026)

### Design
- New visual system in `overcast/theme.py`: Apple-style dark and light palettes, four accents (Amber, Blue, Green, Graphite) and a font chain (SF Pro / Inter / Adwaita Sans / Segoe UI / Cantarell).
- **Rounded, anti-aliased artwork** for pill buttons, cards, fields, chips, the sidebar selection, switches and thin scrollbars. It is rendered in pure Python, pre-blended per surface, and drawn with ttk nine-slice image elements. Every part installs inside a guard and falls back to flat styling; fallbacks are reported in Settings › About and on stderr.
- **Accessibility:** every text colour meets WCAG AA (an automatic readable-accent token, plus a darker secondary text in light mode). Visible keyboard-focus rings. This is enforced by tests.
- **Layout:**
  - large page titles with descriptions; sidebar groups with a rounded selection; brand ☁ mark;
  - segmented controls replace dropdowns for filters; toggle switches in Settings;
  - Settings rebuilt as two columns of grouped cards, with Appearance and Accent pickers;
  - Spotlight-style command palette and Apple-style month calendar;
  - sentence-case labels and reports throughout; scopes display in sentence case ("Trade & supply chains") while the engine keeps canonical values.
- Layout widths budgeted for 1024×680. Standalone sets the clam base theme and the option database; embedded panels leave the host theme alone.

### Accuracy and correctness (from a full code review)
- **Retrieval breadth:** coverage, related-story expansion, counter-evidence search and bridges now draw on the whole 15-day window (up to 4,000 stories) instead of the newest 500. In a 3,500-story test, broad coverage saw 3,500 candidates instead of 500 at the same speed. Tokenisation and topic tagging are cached; clustering is about 3× faster.
- **No double counting:** a question re-forecast across outlook revisions now counts once in gloom bias, calibration and the new per-question score (`score_report()['by_question']`, shown on the dashboard). Before, duplicates could narrow the gloom-bias interval falsely and leak between calibration folds.
- Headline search escapes SQL `%` and `_` wildcards.
- `Store.outlook(id)` is a direct query instead of parsing every outlook.
- Restore-on-launch now recognises older-version signposts.
- The custom-subject coverage count is debounced while typing.
- Exception chaining in the JSON parser; unused imports removed (ruff clean for F/E9/PLE/B904).

### Tests
- `test_v11_theme.py` (9): palettes and WCAG contrast, artwork geometry, symmetry and anti-aliasing, the fast renderer matching full supersampling, switch artwork, and the retrieval window.
- UI tests now cover the scope labels; revision de-duplication is covered in `test_v1_gloom.py`.
- In total, 97 tests.

## 1.0.0 — OVERCAST: renamed, redesigned, risk-first (23 November 2026)

### Renamed
- **SIGNAL → OVERCAST** ("Mostly cloudy, with a chance of being right."). The package is now `overcast`, with launchers `START_OVERCAST_*` and `launch_overcast.py`.
- `import news_oracle` (and every submodule) still works through an alias that returns the *same* module objects.
- The state folder, database file, ICS UIDs and `on_event` `module` value are deliberately unchanged, so data and calendar subscriptions carry over. Events gain `app: "overcast"`.

### Negative prognostication and accuracy
- Outlook scenarios now carry a **kind** (adverse, tail_risk, status_quo, stabilising) and a **severity** (1–5).
  - A **pre-mortem** drives early-warning signposts.
  - Outlooks report the **chance things go badly** and expected severity.
  - One-sided doom is rejected: an outlook needs at least one status-quo or stabilising scenario.
  - Missing kinds are inferred only from clear wording and flagged "?"; defaulted severities are never presented as assessments.
- **Risk register**: open forecasts ranked by P(bad answer) × severity. Superseded revisions are hidden. **MARK BAD NEWS** lets any forecast join it.
- **Gloom bias** check: mean forecast P(adverse) minus the observed adverse rate, with a 95% interval and a plain-English verdict.
- **Outlook revisions**: re-forecast open signposts and scenarios on fresh news, keeping the same question and deadline. The original is kept, and resolutions propagate across revisions (signposts and scenarios).
- **Early-warning feeds** (verified live 23 Nov 2026): Crisis Group, GDACS (Orange/Red only), UN Meetings Coverage and Bank of England. Added a **CRISES** topic and a **CRISES & DISASTERS** scope. Crisis Group's non-standard dates are parsed.
- Outlook prompts are now versioned `overcast-v1.0-outlook(-signpost)`. Older signposts are still recognised.

### Interface
- New layout:
  - a grouped navigation rail (Overview, Forecasts, Research, System);
  - a page header with a description;
  - a single command bar (scope, horizon, BROAD OUTLOOK, MORE ▾, ⟳ FEEDS, CANCEL);
  - live model and news status in the rail.
- New **DASHBOARD** landing page: gloom index, top risks, coming up & due, and track record, with clickable items and onboarding steps.
- New **SETTINGS** page: model, context, runs, extra models, deep-forecast options, auto-refresh and data folder.
- **Search & commands (Ctrl+K)**, opt-in standalone **keyboard shortcuts**, **hover tooltips**, **sortable columns** and **ledger filters and search** (including TOP RISKS). RESULTS **exports Markdown** as well as text.
- **Auto-refresh** of RSS (off by default; 3, 6 or 12 hours).
- The METHODS page is now a scrollable, sectioned reader.

### Fixes
- The compatibility alias restores each module's real `__spec__`, so relative imports stay correct.
- A malformed refresh result can no longer break later dashboard updates.

### Compatibility
- Additive schema only: table `forecast_orientation`, plus columns `outlooks.revision_of` and `outlook_signposts.severity` (migrated with `ALTER TABLE ADD COLUMN`).
- The panel now has 11 pages (`test_ui_smoke.py` was updated from 9). Forecast-ledger columns gained `risk`.

## 0.6.0 — Broad predictions and evidence-backed forecasting methods (23 November 2026)

Each change follows published findings from Metaculus FutureEval (2024–26), the AIA Forecaster report (2025), Halawi et al. (NeurIPS 2024), FutureSearch (ICLR 2026 workshop) and Paleka et al. (ICLR 2025). See `RESEARCH_METHODS.md`, v0.6.0.

### Added
- **BROAD OUTLOOK** (`outlook.py`, `NewsOracleEngine.broad_outlook`, CLI `outlook`): a question-cluster broad prediction. It produces a strategic question, 2–4 drivers, 3–4 mutually exclusive scenarios with probabilities, 4–8 resolvable signposts and a −100…+100 stress index. Costs 1 + RUNS calls. Everything is stored atomically, and each signpost is a normal ledger forecast with a frozen snapshot and audit.
- New **BROAD OUTLOOKS** page (now 9 pages). BROAD OUTLOOK is the primary action, and action labels are shortened to fit 1024 px.
- **Scenario resolution** (`resolve_outlook`, CLI `outlook-resolve`), allowed only after the horizon ends. Scenario scoring uses multiclass Brier and log loss. A **realised stress index** is shown once every signpost resolves.
- **RUNS** setting (1–5, default 3, remembered). Independent runs use shuffled evidence order and temperature 0.7 after the first, and are combined in code (median ≤3, trimmed mean 4+). `forecast_multi(runs=)` cycles the lenses for extra passes. `LMStudioClient.complete(temperature=)` added.
- **Similar resolved questions** from the user's own ledger are given to the outside view as reference outcomes (`similar_history`).
- **Learned recalibration** (`calibration.py`): regularised Platt scaling fitted on the user's resolved forecasts. It needs at least 40, is judged by 10-fold cross-validation, is shown only if it beats raw forecasts, and never alters the ledger.
- Score report adds `scenario_forecasts`, `biggest_misses` and `recalibration`.
- Tests: `test_v06_broad_outlook.py` (10, including an end-to-end run over loopback HTTP through the real client) and `test_v06_ui.py` (1, display-gated).

### Changed
- `aggregate()` uses a trimmed mean for 4 or more passes (unchanged median for ≤3) and reports `rule` and `aggregate_percent`.
- Deep-forecast prompt versions gain `+history` when similar past questions were supplied, and `+ensembleN` when more than 3 passes ran, so scores stay separable by method.

### Compatibility
- Additive tables only: `outlooks`, `outlook_signposts`, `outlook_resolutions`. No existing table changed.
- With RUNS = 3 and no resolved history, deep forecasts make the same calls with the same prompts as 0.5.2.
- `test_ui_smoke.py` now expects 9 pages (was 8).

## 0.5.2 — Review and refinement (23 November 2026)

### Fixed
- Deep forecasts could not fit the 4–8K context recommended for Vulkan recovery. A deep forecast needed an estimated 11–15K tokens. New **MODEL CONTEXT** profiles (8K/16K/32K) size evidence, hypotheses and reply budgets. Excerpts shorten step by step instead of failing, and the excerpt length sent is recorded in snapshots and audits.
- A 180 s client timeout made CPU-only inference (the recommended isolation test) fail as "Cannot reach LM Studio". The default is now 600 s, timeouts get their own error, and the CLI accepts `--timeout`.
- `Store.resolve` on an already-resolved forecast raised `sqlite3.IntegrityError`, which crashed the CLI. It now raises a clear `ValueError`. The evidence URL must contain a hostname.
- `Store.get_forecast` only searched the newest 2,000 forecasts. It now uses a direct query.
- ICS export lacked the RFC 5545-required `DTSTAMP`. PRODID now carries the real version.
- An empty `<atom:link rel="self"/>` before an RSS `<link>` hid the item URL. Double-escaped HTML survived in excerpts.
- The UI poll loop stopped permanently if a result handler raised an exception. All later results would then never appear.
- LM Studio lists embedding models. If one was listed first, CONNECT auto-selected it and every analysis failed.
- Quick forecasts mixed the local date with UTC snapshots.

### Added
- Stage progress callbacks and cooperative cancellation for `forecast_multi` and `overview` (`progress=`, `cancel=`, `OperationCancelled`). The UI gets a CANCEL button and per-stage status. Nothing is saved on cancel.
- Specific errors for context overflow (`LMStudioContextError`) and GPU out-of-memory (`LMStudioGPUMemoryError`, which fails fast like device loss). There is a clear message when a reasoning model exhausts its reply budget.
- Robust JSON extraction: `<think>` blocks are stripped, unfinished reasoning is never mined, and the first complete object after prose is used. An unsupported `json_object` mode is remembered per client.
- Concurrent, bounded RSS refresh with source order preserved.
- Ledger **DUE — RESOLVE** status. Score report adds log loss, per-horizon and per-method log loss, and an overdue-unresolved count with a selection-bias warning.
- `signal_settings.json` in the state folder (CONTEXT profile and last model ID only).
- Tests: `test_v052_refinements.py` (15) and `test_v052_ui.py` (3, display-gated).

### Compatibility
- No table or column changes; one additive index (`idx_articles_published`). Existing v0.1–0.5.1 data is untouched.
- `create_panel`, `EmbeddedSignal`, `EVENT_SCHEMA_VERSION` (1) and all engine signatures are unchanged. New keyword arguments are optional and default to the previous behaviour (16K equals the old 27,000-character packet).
- Prompt versions and the aggregation method are unchanged, so scores remain comparable with earlier forecasts.

## 0.5.1 — Vulkan device-loss recovery hotfix
- Classify `vk::Queue::submit: ErrorDeviceLost` even when LM Studio wraps a server-side 500 inside HTTP 400.
- Prevent JSON format fallback from retrying a GPU crash or unrelated 400.
- Fail fast across multi-pass forecasting after GPU failure, including optional research.
- Show targeted recovery guidance within the RESULTS page; preserve saved state.


## v0.5.0 — 23 November 2026

### User-facing fixes
- A first-class **RESULTS** workspace now displays every completed overview, briefing or forecast *in the running application*. Includes scrollable detailed text, copy-to-clipboard, `.txt` export, restored latest saved report and visible failures.
- Replaced cramped notebook/navigation with an **Oggcultist Ember-style left rail**, simple universal action bar, actual Ember palette and procedural source-compatible film grain. Existing Marble Oracle texture widgets take precedence when embedded.
- Improved sizing at 1024×680; preserved model selection, source review, event graph, forecast register, calendar, and saved archives.
- Added global geopolitics/markets/trade/combined/custom scopes, alongside manually selected headlines. A fresh sample is bounded and reports its coverage limitations.
- Added evidence-cited whole-topic **INTELLIGENCE OVERVIEW** summaries with separate downside and stabilising scenarios. Invalid cited article IDs result in no saved overview.
- Existing DEEP and QUICK forecasts can be seeded from broad scope selections, but still generate *one specific testable outcome* rather than a bogus probability for an entire market.

### Compatibility
- Preserved SQLite schema, legacy forecasts, existing interfaces and Marble Oracle embedded adapter API.
- No modification of the Marble Oracle suite itself. No internet or paid model API is needed for inference.
- Added pure-Python `scopes.py`, optional theme bridge `ember_theme.py`, pre-generated grain tiles and new v0.5 tests.
- 40 regression tests passed, including Tk virtual-display tests. Live remote RSS and LM Studio hardware testing not performed.

---
# SIGNAL Development Changelog

## v0.4.0 — Evidence-driven forecasting architecture (22 November 2026)

- Introduced SHA-256-checked full excerpt snapshots at prediction creation time, stored transactionally with forecast/audit. Older forecast rows remain available; no pretend reconstruction of missing historical snapshots.
- Added quote-verified event claim extraction with actor, action, target, location, optional explicitly sourced date and type; all records permanently marked unverified reported claims.
- Added shared-actor graph leads explicitly labeled as *possible relationships*, not proof of coordination.
- Added optional model-planned, bounded, point-in-time-safe targeted search over cached excerpts, including disconfirming search terms; logs failures and sources retrieved.
- Added optional conditional occurrence-time CDF across fixed, monotonic future checkpoints; derived unconditional interval masses and `FORECAST TIMING` calendar entries and ICS descriptions.
- Added sourced historical reference classes with minimum sample and topical match checks, user opt-in only; no automatic probability inflation or claimed statistical calibration.
- Added same-set Brier comparison against a constant 50% naive baseline.
- Updated embedded Tk GUI with an Evidence Graph workspace, frozen-source viewer and optional deep-forecast gap/timing toggles; compressed tabs for narrower desktop windows.
- Expanded CLI and ledger JSON export; maintained `create_panel()`, `NewsOracleEngine` and EmbeddedSignal lifecycle API compatibility.
- Added deterministic regression tests for historical source cutoffs, invalid quotes, immutable packet integrity, time CDF monotonicity, database migration and optional reference classes.

**Not included:** external autonomous web search, paid data APIs, live quantitative economic baselines, training/fine-tuning, independent automatic resolution, verified real-world improvement, or modifications to Marble Oracle. The latest deep research is guidance, not a claim of benchmark performance.

## v0.3.0

World politics / markets / trade editorial focus, optional strategic investigation, cross-sector research leads, estimated event windows and real calendar month view with manual schedules and ICS export.

## v0.2.0

Multi-publisher RSS research review, near-duplicate warnings, three-prompt-perspective forecasts, bounded citation validation, historical-cutoff support and Brier score reporting.

## v0.1.0

Local RSS collection, LM Studio API, news briefings, single-pass forecast ledger, manual resolution and embeddable Tk interface.
