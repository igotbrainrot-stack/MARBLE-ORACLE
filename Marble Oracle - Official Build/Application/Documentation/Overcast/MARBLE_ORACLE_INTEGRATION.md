# Marble Oracle integration — done in Marble Oracle 0.5.0

OVERCAST 1.1.2 is the suite's seventh workspace, the **OVERCAST** tab between AUGURSPEX and PASSPHRASE.

- **Code:** the package is `Application/Runtime/Marble_Oracle_App/overcast/`, plus the `news_oracle/` alias. `oracle_overcast_tab.EmbeddedOvercast` mounts `overcast.create_panel(...)` on the suite canvas with the usual `layout/clear/shutdown/key`. The package still imports nothing from the suite and still runs on its own with `python -m overcast`.
- **Ledger:** it lives in the suite state folder, `<state>/news_oracle/`. That is the same folder as a standalone OVERCAST install, so both see the same forecasts.
- **Lifetime:** the panel is built on first open and kept while other tabs are shown, so a running forecast or refresh continues and lands in the ledger. Finished jobs are announced in the suite's status line (`on_event`). Closing the suite cancels a model call between steps; nothing incomplete is saved.
- **Keys:** OVERCAST binds no suite keys. Escape returns HOME, as in every workspace. Ctrl K and the other standalone shortcuts are not installed when embedded.
- **Tests:**
  - `Tests/test_overcast_package.py` runs OVERCAST's own 97 tests (in `Tests/overcast/`) against this copy.
  - `Tests/test_overcast_workspace_0500.py` (44 checks) checks the fit at the five sizes, that opening makes no network call, where the ledger is, switching tabs and closing during a refresh, and that no Tk call comes from a worker thread.

The original contract, kept for reference, follows.

---

# Marble Oracle integration — Overcast 1.1 (formerly SIGNAL)

**Use `overcast` in new code:** `from overcast import create_panel` and `from overcast.marble_adapter import EmbeddedSignal`. Old `news_oracle.*` imports keep working and return the same modules. The panel opens on its DASHBOARD and has 11 internal pages. Keyboard shortcuts are **not** installed when embedded; call `panel.install_shortcuts(window)` only if the host wants them. Events keep `module: "signal"` for `EVENT_SCHEMA_VERSION` 1 and add `app: "overcast"`. New engine calls: `revise_outlook`, `risk_register`, `gloom_bias` and `set_orientation`.

**1.1 theming when embedded:** `create_panel(parent)` builds with `standalone=False`. The panel then adds its own uniquely named ttk styles and elements (prefixed `O.`) but does **not** switch the host's ttk theme or set the option database. Only `run_standalone()` selects the `clam` base theme. The panel reads Appearance and Accent from its own settings file. If the host's theme rejects any artwork, the panel falls back to flat styling for that part and continues.

---

# SIGNAL → Marble Oracle integration contract

**Target reviewed:** `igotbrainrot-stack/MARBLE-ORACLE`, branch `claude/marble-oracle-0499-professional`, 0.4.9.9 as inspected 22 November 2026.

Current source layout: `Marble Oracle - Official Build/Application/Runtime/Marble_Oracle_App/`. Current architecture says HOME uses Canvas, six workspaces occupy Tk frames over it, and workspaces expose `layout(box)`, `clear()`, `shutdown()`, `key(event)`. `oracle_shell.py`, `oggcultist_design_system.py`, `oracle_widgets.py`, `marble_uberata.py`, `oracle_assets.py` are shared services.

## Safe integration pathway (NOT implemented in suite yet)

1. Copy the `news_oracle/` package into `Application/Runtime/Marble_Oracle_App/news_oracle/` in a **new feature branch** based on the latest Marble Oracle development branch. Keep its name stable.
2. Mount it in an existing/new suite workspace via `from news_oracle import create_panel`, then `panel = create_panel(parent, state_dir=Path(oracle_assets.state_dir())/'news_oracle', on_event=handler)`. `panel` is an ordinary `tk.Frame`, with no second Tk root. Alternatively use `from news_oracle.marble_adapter import EmbeddedSignal` for `layout/clear/shutdown/key` lifecycle semantics.
3. Use the host's `oracle_shell` page/rail/HOME affordance when the host UI integration is designed; do **not** replace the suite's tab strip, reorder existing six tabs or alter the HOME canvas without explicit planning/testing. Keep the existing brand palette and only use the bundled Uberata Clear family in the integrated UI (SIGNAL standalone has a fallback font).
4. Bind a workspace into `Scene.act` once, cache it and call the lifecycle functions just as the other workspaces do. Do not call Tk methods from worker threads. SIGNAL uses queues and main-thread polling.
5. Retain existing launch paths, package assets, FFmpeg/Oggcultist and previous state directories. The new SQLite ledger lives in its own `news_oracle` subdirectory, not the install tree, and is never deleted on upgrade.
6. Extend development test discovery and end-to-end screenshots at the five documented viewport sizes. Add evidence-backed integration tests for switching tabs during an active RSS request or local model inference, and closing while work is pending.
7. Only after this test matrix succeeds should the host version, manifest, file inventory and release ZIP be regenerated. The prototype does not modify those files.

## Stable APIs

```python
from news_oracle import create_panel, NewsOracleEngine

widget = create_panel(parent, state_dir=None, on_event=handle_event)
widget.pack(fill='both', expand=True)

engine = NewsOracleEngine(state_dir=None)
# engine.refresh()          -> {'new':int,'total_fetched':int,'sources':[...]} (network)
# engine.articles(query='') -> [{id,title,summary,source,published,url,...}]
# engine.models()           -> [str, ...] from local LM Studio
# engine.briefing([ids], 'model-id') -> dict, stored in local SQLite
# engine.forecast([ids],'model-id',90) -> dict, stored in local SQLite
# engine.forecasts()        -> all saved forecasts, newest first
# engine.resolve(id,1,'https://...') -> manually score YES
# engine.performance()      -> {'count':int,'score':float|None}
# engine.export_json()      -> dict format=news-oracle-ledger-v1
engine.close()
```

`on_event` receives dictionaries like `{'schema_version':1,'module':'signal','event':'forecast_created','id':3,'probability':0.63}`. Other events: `news_refreshed`, `model_connected`, `briefing_created`, `forecast_resolved`. Maintain backwards compatibility with schema v1; add new fields rather than breaking existing ones.

A forecast's evidence is a JSON array of original cached news items with `article_id,source,title,url,published`. The `forecast` probability and creation date are immutable; outcome is recorded in a separate resolution table. No market-trading action is triggered by these events. Downstream AUGURSPEX integration should display such forecasts **as annotations only** and must never silently treat them as signals or validated financial guidance.

## Gaps before production

1. Read-only host navigation: design an approved SIGNAL place in the suite (e.g., sibling workspace) rather than squeezing a seventh tab without checking widths, scaled layouts, keyboard navigation and accessibility.
2. Host palette/font: rewrite only the SIGNAL view using `oracle_shell` and shared design tokens; keep engine independent of Tk and shell.
3. Event grouping: use cross-publisher deduplication, primary sources and extraction/source reliability; never present a one-publisher snippet as an independently corroborated event.
4. Forecast audit: persist model version/settings, user changes to source selection, and last-model prompt token usage when returned. Add independent adjudication and an appeal/uncertain outcome process.
5. Freshness/quality: rate limits, RSS stale timestamps, missing publication dates, robots/terms and source failures.
6. Security: when user-configured feeds are added, explicitly block localhost/private IPs and off-domain redirects to avoid SSRF. Keep LM Studio loopback-only unless client explicitly opts into a local-LAN host.
7. Calibration: predefined forecast question sets, unbiased full-resolution tracking, reliability diagrams, baseline comparisons, and evaluation cohorts; never advertise model-based confidence as measured accuracy.

## Compatibility conclusions

SIGNAL shares Marble Oracle's Python standard-library/Tk approach, uses user-state storage outside the app directory, returns an embeddable frame, and avoids cloud model providers or GUI shells. **It is structurally compatible but has not yet been wired into Marble Oracle's actual `Scene` navigation, nor has the complete suite test matrix been run against this module.**

---

## Update for SIGNAL 0.2.0 (22 November 2026)

This 0.2 build retains the v0.1 public package name, `create_panel()` host API, `EmbeddedSignal` lifecycle adapter and `EVENT_SCHEMA_VERSION=1`. The changes are **additive**, and no Marble Oracle suite files or tabs were modified. The ZIP's launch scripts still start SIGNAL standalone.

**New headless methods:**

```python
engine.events(limit=100, days=14)                   # candidate clusters; no network/model
engine.research_preview([article_id], expand=True)  # audited context packet; no model
engine.forecast_multi([article_id], 'local-model', 90)  # local question + 3 forecasting passes
engine.forecast_multi([article_id], 'model-1', 90,
                      model_ids=['model-1','model-2','model-3'])
engine.forecast_audit(forecast_id)
engine.score_report()     # score, unresolved count, calibration bins, per-method Brier
```

**Modules:** `news_oracle/research.py` provides bounded, lexical source clustering and time-valid evidence retrieval, with an explicit disclaimer that syndication can appear to be independent. `news_oracle/forecasting.py` provides question validation, inside/outside/red-team prompts and deterministic median aggregation. `engine.py` orchestrates and persists forecasts. `store.py` adds an optional `forecast_audits` table without altering legacy data.

**New UI:** The package creates five internal notebook pages (**NEWS WIRE**, **EVENT CLUSTERS**, **FORECASTS**, **BRIEFINGS**, **SYSTEM**). These are inside the single embeddable Frame, not new Marble Oracle top-level tabs. The upper controls include an optional `OTHER MODEL IDs` text field for assigning two extra loaded LM Studio models; blanks use the selected model for all three viewpoints. No Tk calls originate from background model/network threads.

**Audit contract:** The additional `forecast_audits` row contains method version, the fixed question and resolution rule, initial seeds, expanded evidence IDs, publisher domains and near-duplicate IDs, three viewpoint responses and any errors, aggregation median/range, optional user-supplied base rate/provenance, and data-quality warnings. The `forecasts` table and `resolutions` constraints are unchanged. Future migrations must preserve old forecasts and audits.

**Next integration requirements:** Keep the suite's six existing workspace tabs intact until a deliberate navigation design is approved. The host page should eventually swap SIGNAL's standalone UI tokens for `oracle_shell`, the shared design system and Uberata Clear, without coupling the inference or research modules to Tk. Do not automatically connect SIGNAL forecasts to AUGURSPEX trade/chart signals or treat forecast probabilities as calibrated market data. Set the same `MARBLE_ORACLE_STATE` parent as the suite so the ledger lives in its existing user state area.

**Validation carried out for standalone v0.2:** 20 Python unit tests passed (including Tk under Xvfb at 1000x620), legacy test coverage still passes, CLI parses the new commands, and module byte-compilation succeeds. Not yet verified: on-device LM Studio inference, the live 9 RSS sources, real predictive accuracy, end-to-end mounted suite navigation, UI screenshots at every Marble Oracle viewport, or suite-specific font/assets. Do not merge as an official Marble Oracle feature or regenerate its release manifest on the strength of these standalone tests alone.

---

## Update for SIGNAL 0.3.0 (22 November 2026) — risk intelligence and forecast calendar

**Standalone-only development.** The host has NOT been modified; the existing six Marble Oracle workspace tabs and HOME layout remain unchanged. The embedded SIGNAL panel now has **six internal notebook pages**, including CALENDAR. Retain compatibility with `create_panel`, `EmbeddedSignal`, `EVENT_SCHEMA_VERSION = 1` and all existing headless `NewsOracleEngine` APIs.

Additional standard-library modules: `news_oracle/risk.py` (topic tagging, evidence-restricted incentive/connections audit), `news_oracle/calendar.py` (strict date windows, calendar entries, month/day queries and ICS export). There are no new PyPI dependencies. `research.py` now also returns *cross_sector_bridges*: transparent research leads based on shared terms and differing focus, never causal proof. `feeds.py` adds WTO/ECB/Federal Reserve primary-source publication feeds. `store.py` adds the `calendar_schedules` table, preserving all earlier tables and IDs. `forecast_multi` has optional `investigate=False` to keep previous API behavior; the SIGNAL GUI and CLI use `investigate=True` by default for the deeper five-call path. There are no automatic cloud API calls.

**New public engine methods:**

```python
engine.articles(query='',focus='TRADE')
engine.topic_summary()
engine.events(focus_only=True)
engine.forecast_multi([1], 'local-model-id', 90, investigate=True)
engine.calendar_items()     # mixed records with kind: forecast_window, forecast_deadline, reported_schedule
engine.add_scheduled_event('WTO committee', '2026-12-01', '2026-12-01', 'https://published.example/meeting', 'User provenance')
engine.calendar_ics()       # RFC 5545 all-day .ics content, never alters ledger
```

**Calendar model:** `target_date` is a resolution deadline, NOT a most-likely day. The optional, bounded `window_start`/`window_end` are obtained from the model's question-selection output, stored in the **forecast audit** (not as a schema-breaking addition to the main forecast table). A calendar with a forecast but no supported window shows only its deadline. Manual source dates reside in `calendar_schedules`; the URL is required but not automatically visited or authenticated. For precise scheduled event ingestion in the future, prefer official publishers' calendar feeds/APIs and retain provenance, the source's timezone and revision history. Do not automatically turn model windows into event bookings or notifications.

**Audit:** `forecast_audits.audit_json` now optionally adds `cross_sector_bridges`, `investigation` and `investigation_error`. Each accepted structured actor/connection has an allowlisted `evidence_article_ids` array, a competing ordinary explanation and, for links, a disconfirming observation. This validation verifies IDs exist in the packet, **not** the truth of the prose. The numeric `aggregation` still contains exactly the three forecasting estimates, their median/range and failure list; neither downside prompting nor hypothetical motives mechanically adjust odds.

**Integration UI work still required:** wire SIGNAL into a deliberate suite navigation design only after testing at 900x580, 1000x650, 1216x848, 1280x720 and 1920x1080, including the new calendar's 7-column grid, keyboard focus, status line and compact mode. Adapt SIGNAL palette and widgets to host `oracle_shell`, `oracle_widgets`, `marble_uberata` without changing the independent engine. Test tab switching during source fetch or long model calls and closing with queued jobs. Preserve all existing Marble Oracle and SIGNAL user state.

**Observed tests for standalone v0.3:** 30 offline unit tests, including legacy 0.1/0.2 regression, mocked model multi-pass workflows, dated window rejection, hypothetical citation allowlisting, SQLite schedule persistence, ICS generation, and a Tk virtual-display smoke test. No on-device LM Studio inference, live official RSS probe, prospectively measured accuracy or full Marble Oracle integration has been verified.

## SIGNAL 0.4 implementation update (22 November 2026)

The stable integration boundary **has not changed**: `create_panel`, `NewsOracleEngine`, `EmbeddedSignal.layout/clear/shutdown/key`, and `EVENT_SCHEMA_VERSION=1` remain available. Only internal Tk Notebook tabs changed (added **Evidence Graph**). All code remains stdlib Python and uses the existing SQLite ledger under a user-state subdirectory. Existing `forecasts` and `resolutions` records were not migrated destructively.

New optional headless entry points:

```python
engine.extract_events([1, 2], 'local-model-id')                 # opt-in claim extractor; stores unverified reported claims
engine.event_claims()                                           # view source-anchored claims
engine.relationship_leads()                                     # tentative shared-actor associations
engine.forecast_multi([1], 'local-model-id', 90, investigate=True,
                      gap_search=True, timing=True)            # up to 7 sequential local model calls
engine.forecast_packet(1)                                       # SHA256 validated source excerpt snapshot
engine.reference_classes()                                      # user-registered historical reference data
engine.calendar_items()                                         # includes distinct conditional timing bucket entries
```

When wiring into Marble Oracle, ensure the source ZIP's own standalone title/Notebook does not duplicate the suite's navigation. No connection has yet been made to AUGURSPEX; price data are NOT assumed to be evidence of a specific political event. The GUI emits a new `claims_extracted` event in addition to existing schema-v1 events. **No automatic polling, trade execution, or auto-resolution.**

Next work for actual host integration: confirm branch head and current architecture, mount on a feature branch, fit its palette/font to the host shell, run the complete cross-platform Tk test suite, and do not merge an untested UI. A raw source copy can be integrated without importing outside-project code or extra third-party licenses.

---

## SIGNAL v0.5 (2026-11-23) — UI and scope compatibility update

This release is a standalone module. **It has not been merged into the Marble Oracle shell.** The stable adapter is still `news_oracle.marble_adapter.EmbeddedSignal` with `layout(box)`, `clear()`, `shutdown()` and `key(event)` methods; `news_oracle.create_panel()` still returns a native Tk `Frame`.

The new `news_oracle.ember_theme` imports `oracle_ogg_texture` and uses its **original** role-mapped textured frame and label widgets when running in a complete Marble Oracle checkout with texture assets. In standalone SIGNAL it falls back to pre-rendered texture assets created with the Oggcultist-compatible grain algorithm and Ember tokens. No new runtime Pillow dependency. Existing `oggcultist_design_system.py`, `oracle_shell.py`, fonts and Marble assets are not copied or modified by integration.

The UI uses a left rail for its own workspaces inside the SIGNAL panel and **does not** call `Tk()` when embedded. It does not bind global keys or assume an external browser for results. There are no navigation changes to the six existing Marble Oracle workspaces. The new `RESULTS` view is internal to SIGNAL, so integration does not need a new suite-level tab for each report.

The new headless API is `NewsOracleEngine.coverage(scope,query='',limit=16)` for a transparent, bounded sample of cached RSS and `NewsOracleEngine.overview(article_ids,model_id,scope=...,horizon_days=...,coverage=...)` for a saved, evidence-cited qualitative overview. All previous methods continue to exist. `forecast_multi()` gains an optional `scope_label` argument that is recorded in the audit. The data format and existing SQLite tables remain valid.

User-state migration is automatic and additive: **do not remove or rewrite user state folders**. When integrating, instantiate the workspace lazily using the existing suite conventions; keep Tk mutations on the main UI thread; allow completion messages to update the internal Results reader via the existing worker queue. No root-level `mainloop` is created by the adapter.

## Known integration and coverage limitations

The current panel creates its own internal rail, which uses horizontal space. Test at Marble Oracle's supported frame sizes, especially 900×580 and 1000×650, before integration; standalone was reviewed at 1024×680 and 1440×900, but the embedded smaller sizes have not been validated. Do **not** treat broad scopes as a complete stock universe or global event database. Full AUGURSPEX market series integration, official economic calendar ingestion and live LM Studio validation remain separate follow-up work.

## SIGNAL v0.5.1 LM Studio Vulkan stability (23 November 2026)

The public adapter and ledger schema are unchanged. The LM Studio client now raises
`LMStudioDeviceLostError` for `vk::Queue::submit: ErrorDeviceLost`, even if
the engine error arrives wrapped by an HTTP 400 response. Only errors that
explicitly reject `response_format` trigger a single compatibility retry.
The multi-pass pipeline immediately aborts after device loss (including during
optional research), to avoid submitting further work to the failed backend.
The RESULTS reader displays recovery guidance for this failure.
No automatic device recovery or driver switching is performed by SIGNAL.

## SIGNAL v0.5.2 host-facing additions (23 November 2026)

All additions are optional keyword arguments; existing calls behave exactly as in 0.5.1.

- `NewsOracleEngine(..., context_profile='8K'|'16K'|'32K')`. Default `'16K'` reproduces the previous budgets. Hosts that know the loaded context length should pass it.
- `engine.forecast_multi(..., progress=fn, cancel=event)` and `engine.overview(..., progress=fn, cancel=event)`. `progress(step, total, label)` is called **on the worker thread** before each model call, so a host must marshal it to Tk via a queue, as `ui.py` does. `cancel` is any object with `is_set()`, for example `threading.Event`. Cancelling raises `news_oracle.OperationCancelled`, which is deliberately not a `RuntimeError`, and writes nothing.
- The embedded panel stores `signal_settings.json` (context profile, last model ID) in its own state folder. It never writes outside the state folder.
- The panel's internal job queue now carries 4-tuples. This is internal only, with no change to `on_event` payloads.

## SIGNAL v0.6.0 host-facing additions (23 November 2026)

- `engine.broad_outlook(article_ids, model_id, *, scope, query='', horizon_days=90, runs=3, coverage=None, progress=None, cancel=None)` returns `{id, forecast_ids, strategic_question, stress_index, scenarios, valid_runs, failed_runs, signposts}`. Use `engine.coverage(scope, query=...)` for `article_ids`.
- `engine.outlooks()`, `engine.outlook_detail(id)` and `engine.resolve_outlook(id, letter, url, note='')`. `news_oracle.outlook.report_sections(item)` renders a plain-text report without Tk.
- `forecast_multi(..., runs=3)` and `LMStudioClient.complete(..., temperature=0.2)` take new optional arguments.
- New `on_event` events: `outlook_created {id, stress_index}` and `outlook_resolved {id, scenario}`. `EVENT_SCHEMA_VERSION` stays 1, because these are additive event names.
- The panel has 9 internal pages. A host that relies on the count (for example a smoke test) must update it.
