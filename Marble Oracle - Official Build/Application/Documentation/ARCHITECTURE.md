# Architecture

Marble Oracle is one Python/Tk process. A single window hosts the HOME dashboard, drawn on a canvas, and five workspaces that are ordinary Tk frames laid over it. There is no plugin system, no database and no web view; state is a handful of JSON files in the user's own folders.

```
Marble Oracle - Official Build/
├── START MARBLE ORACLE - WINDOWS.vbs / .bat / LINUX.sh   launchers (no console window)
└── Application/
    ├── Runtime/
    │   ├── launch_suite.pyw            requirements check (asks before installing), then starts the app
    │   └── Marble_Oracle_App/          the application (see below)
    ├── Tests/                          regression scripts, one process each
    ├── Tools/                          run_tests, verify_release, build_release, capture_screens, probe_providers
    └── Documentation/                  this folder; History/ keeps everything older
```

## Layers

Reading order for a new developer. Each layer only imports from the ones above it.

| Layer | Modules | Responsibility |
|---|---|---|
| **Release identity** | `oracle_version.py` | The one suite version; window title, `--version`, build manifest. |
| **Design system** | `oggcultist_design_system.py` (colours, type scale, spacing), `oracle_shell.py` (the page shell every workspace is built in: rail, brand, page title, HOME, status line, button and type scale; 0.4.9.5), `oracle_design.py` (market category colours, the HOME wording, `flow_layout`), `oracle_ogg_texture.py` (grain textures), `marble_uberata.py` (the bundled font) | Every colour, size and label a workspace uses. No Tk in the first two. |
| **Shared widgets** | `oracle_widgets.py` | `flow` (toolbars that wrap) and `wrap_to_parent` (text that wraps). |
| **Platform and state** | `oracle_assets.py` (asset lookup, `state_dir()`, atomic `save_json`/`load_json`), `oracle_asset_recovery.py`, `oracle_native_files.py` (native file dialogs), `oracle_window_shape.py`, `oracle_bootstrap.py` | Everything that differs between Windows and Linux. |
| **Workspace logic (no Tk)** | `oracle_augurspex_logic.py`, `oracle_augurspex_signals.py`, `Augurspex/augurspex/providers.py` and `core.py`, `oracle_eidolith_core.py`, `oracle_eidolith_jobs.py`, `oracle_dicekey.py` | Rules, calculations, provider adapters, the conversion queue, the passphrase generator. Testable without a display. |
| **Workspace interfaces (Tk)** | `oracle_augurspex_tab.py`, `oracle_augurspex_insights.py`, `oracle_augurspex_home.py`, `oracle_eidolith.py`, `oracle_eidolith_player.py`, `marble_passphrase_tab.py`, `oracle_touch_type.py`, `oracle_ogg_tab.py` (adapter for the embedded `Oggcultist/` app), `oracle_suite_guide.py` | One module (or a small group) per workspace. Each exposes an `Embedded…` class with `layout(box)`, `clear()`, `shutdown()` and `key()`. |
| **Shell** | `marble_oracle.py` (`Scene`, `WindowApp`, `launch_plan`, the HOME panels), `oracle_chrome.py` (tab strip, window chrome, themes), `oracle_skin.py` | Owns the window, the render loop, navigation and the workspace lifecycle. |
| **HOME content** | `oracle_media.py`, `oracle_runes.py`, `oracle_ascii*.py`, `oracle_latin.py`, `oracle_sententiae.py`, `oracle_audio.py`, `oracle_wire.py`, `oracle_train.py` | Tarot, runes, statues, Latin, voices, the transmission scene. |
| **Optional CRT housing** | `oracle_crt_v2.py`, `oracle_photo_bezel.py`, `oracle_pixel_crt.py`, `oracle_nixie.py`, `oracle_glass.py`, `oracle_vhs.py`, `crt_barrel_no_feedback.py`, `oracle_sysmetrics.py`, `oracle_audio_scope.py` | The photographic CRT frame (`--crt-v2`). Not used by the default window. |

## How a workspace is hosted

`Scene.act('tab_<name>')` builds the workspace the first time and caches it; switching away calls `clear()` (hide, pause playback), switching back calls `layout(box)`. Closing the window calls each cached workspace's `shutdown()`; EIDOLITH's returns `False` if the user chooses to keep a running conversion, which cancels the close.

Workspaces never reach into each other. The only shared services are the design modules and, for market data, one process-wide `MarketRouter` (`shared_market_router`) used by both the AUGURSPEX tab and the HOME chart so they share caches and cool-downs.

## Threads

Tk is touched only from the main thread. Background work hands results back through a queue that the main thread drains on a timer:

- AUGURSPEX: a 3-thread pool fetches history; `_drain_results` applies it.
- EIDOLITH: one queue thread runs FFmpeg jobs; one reader thread per playing video.
- HOME: one thread for the market carousel; optional sensor and audio-scope threads for the CRT housing.

All are daemon threads; `shutdown()` stops the ones that own a process.

## AUGURSPEX data path

```
watchlist symbol ──► MarketRouter._routes()        which sources are eligible (keys, interval, asset class)
                     MarketRouter.fetch()           per-source cache → cool-down → rate gap → adapter
                     read_<source>()                one adapter per provider: fetch, validate, normalise
                     candle() / finish()            reject impossible rows; never synthesise a value
                 ──► oracle_augurspex_logic         freshness, status wording, chart geometry, labels
                 ──► oracle_augurspex_tab           drawing, SOURCE DETAILS, CSV
```

A failure carries a *kind* (`providers.ERROR_KINDS`) from the adapter to the screen, so "rate limited", "key rejected", "network problem" and "no source configured" are never merged into one message. See `MARKET_DATA.md`.

## EIDOLITH job path

```
CONVERT page ──► new_job()                     source, profile, output path (never the source, never an existing file)
                 QueueRunner._run()            probe → plan → FFmpeg to "<name>.partial.<ext>" → validate → publish
                 stop_process_tree()           cancel/stop ends FFmpeg (and a launcher's child on Windows)
                 remove_owned_partial()        deletes only files this queue created
```

The queue is saved to `eidolith_queue.json` in the state folder and restored on the next start; nothing restarts by itself.

## State files

| What | Where |
|---|---|
| Suite preferences, Touch Type scores, EIDOLITH queue and logs | `state_dir()`: `~/.local/state/Marble_Oracle` (Linux), `%LOCALAPPDATA%\Marble_Oracle` (Windows), or `MARBLE_ORACLE_STATE` |
| Requirements manager, private virtual environment | `MarbleOracleSuite` under the OS user-data folder |
| AUGURSPEX settings, watchlist, imported CSVs | `~/.config/augurspex` (or `XDG_CONFIG_HOME`) |
| AUGURSPEX history cache (7 days, 400 files at most) | `~/.cache/augurspex` (or `XDG_CACHE_HOME`) |

API keys are read from environment variables or entered for the session only; they are never written to disk.

## Known structural debt

Recorded so nobody has to rediscover it; none of it is a defect.

- `marble_oracle.py` is 3,700 lines: the shell, the render loop and every HOME panel in one class. Splitting the HOME panels into their own modules is the next worthwhile refactor; it needs the GUI tests green on both platforms first.
- `oracle_augurspex_tab.py` (1,600 lines) still mixes dialogs with the panel; `oracle_augurspex_logic.py` already holds everything that needs no Tk.
- `providers.py` (1,600 lines) keeps all adapters in one file. They share only `get_bytes`, `candle` and `finish`, so splitting by asset class is mechanical.
- The embedded `Oggcultist/` is a complete standalone application with its own tests and design modules; the suite deliberately does not edit it.
- Much of the older code is written in a dense one-statement-per-line style. `ruff.toml` holds the rules that are enforced today; the formatter is not applied to legacy modules, to keep history readable.
