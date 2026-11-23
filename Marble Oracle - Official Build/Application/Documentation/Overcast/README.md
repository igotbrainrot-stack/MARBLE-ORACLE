# Overcast 1.1.1 — *Mostly cloudy, with a chance of being right.*

A local, pessimism-first forecasting desk for world politics, markets, trade and crises. It looks hardest at what could go wrong, then keeps itself honest by scoring every forecast. It runs on your own LM Studio models and keeps everything in a local SQLite database. It is designed to embed in **Marble Oracle**. It was formerly SIGNAL / News Oracle; old imports and data still work.

## Install

**Fedora:**
1. Run `sudo dnf install python3-tkinter` (once).
2. Unzip the package and run `./install_overcast_linux.sh`.
3. Open **Overcast** from the app menu, or type `overcast`.

**Windows:** run `install_overcast_windows.bat`.

Both installers are per-user, work offline and never touch your forecasts. See `INSTALL.md` for pip, upgrading and removal. You can still run without installing, from the source folder: `./START_OVERCAST_LINUX.sh` or `START_OVERCAST_WINDOWS.bat`.

## Start

1. Install Overcast (above), or extract the source folder.
2. Open Overcast.
3. In LM Studio, load an instruction-following chat model and start the local server (`127.0.0.1:1234`).
4. In Overcast, open **Settings**:
   - choose **Connect** and pick the model;
   - set **Context** to the model's loaded context length (8K / 16K / 32K).
5. Choose **⟳ Refresh** to fetch headlines. This is the only time Overcast uses the internet, unless you turn on auto-refresh.
6. Pick a scope in the command bar (for example *Global markets* or *Crises & disasters*) and choose **Broad outlook**.

## Design

The interface follows Apple's design conventions on Linux and Windows:

- a quiet sidebar with grouped pages and a rounded selection;
- a large page title with a one-line description;
- rounded cards, pill buttons and rounded fields with a visible focus ring;
- segmented controls, toggle switches and thin scrollbars;
- sentence-case labels.

**Appearance:**
- **Dark** or **Light** mode, with an **Amber** (default), **Blue**, **Green** or **Graphite** accent (Settings › Appearance; takes effect on next launch).
- Every text colour meets WCAG AA contrast (4.5:1 or better) in every combination.
- The font is the system's best match: SF Pro, Inter or Adwaita Sans (Fedora's own), then Segoe UI or Cantarell.

**How it is drawn:** the rounded artwork is generated in pure Python (no Pillow needed) and drawn through ttk image elements, so it looks the same on every platform. If a Tk build rejects any part, that part falls back to a flat style. The app always starts, and Settings › About shows the font in use and whether any part fell back.

```
┌ ☁ Overcast ────────┬────────────────────────────────────────────────────────────────┐
│ ⌕ Search    Ctrl K │ Dashboard                                                      │
│ Overview           │ Where things stand: the gloom index, top risks, …              │
│ ▌Dashboard         │ (Global events ▾) (90 ▾) days (Broad outlook) (More ▾)   (⟳ Refresh) (Cancel) │
│  Results           │ Evidence: 16 of 214 recent matching items from 11 sources …    │
│ Forecasts          │ ╭─ Gloom index ───────────╮ ╭─ Top open risks ─────────────╮    │
│  Outlooks          │ │ +31  Leaning adverse    │ │ 3.6  72%×5  Will Arcadia …   │    │
│  Ledger            │ ╰─────────────────────────╯ ╰──────────────────────────────╯    │
│  Calendar          │ ╭─ Coming up and due ─────╮ ╭─ Track record ───────────────╮    │
│ Research · System… │ │ …                       │ │ Brier 0.187 · gloom bias …   │    │
│ ● model · 8K · 3   │ ╰─────────────────────────╯ ╰──────────────────────────────╯    │
└────────────────────┴────────────────────────────────────────────────────────────────┘
```

## Pages

| Page | Purpose |
| --- | --- |
| **Dashboard** | Gloom index, top open risks (chance × severity), coming up and due, and track record. Items are clickable. |
| **Results** | The full text of the latest report. Copy it, or export it as Markdown or text. |
| **Outlooks** | Broad predictions. **Revise with fresh news**, or record which scenario happened. |
| **Ledger** | Every forecast, permanently recorded. Segmented filter (All / Open / Due / Resolved / Top risks / Signposts), search, sortable columns, **Mark bad news…**, and resolve yes or no. |
| **Calendar** | Month view of deadlines, estimated windows and sourced schedules, plus `.ics` export. |
| **News · Clusters · Evidence · Briefings** | Research tools: headlines, related-story groups, quoted claims and saved briefings. |
| **Settings** | Model, context, ensemble runs, extra models, deep-forecast switches, appearance, auto-refresh and data folder. |
| **Methods** | How Overcast forecasts and what it will not claim. |

**Search & commands (Ctrl K)** jumps to any page, runs any action or switches scope. Other shortcuts in the standalone window: Ctrl ↵ broad outlook, F5 refresh, Esc cancel, Ctrl 1–9 pages. When embedded, Overcast never takes over the host's keys.

## Negative prognostication, done accurately

Overcast is pessimistic about **what it examines** and neutral about **what it predicts**:

- **What gets examined:**
  - every outlook has adverse and tail-risk scenarios rated for severity;
  - a pre-mortem drives early-warning signposts;
  - reports lead with "Bad news first";
  - risks are ranked by chance × severity;
  - early-warning sources are included (Crisis Group, GDACS Orange/Red alerts, UN meeting coverage).
- **What keeps the probabilities neutral:**
  - an outlook with only bad scenarios is rejected, and scenario probabilities must add up to 100%;
  - independent runs are averaged in code, and the prompts forbid inflating adverse odds;
  - the **gloom-bias check** shows whether forecasts have been too gloomy or not gloomy enough compared with what happened;
  - calibration is learned from your own record (40+ resolved, cross-validated, display only).
- **Honest statistics:** a question re-forecast in several revisions counts **once** in the track record, gloom bias and calibration.

## Broad outlooks

A broad question becomes a scorable cluster: drivers, 3–4 mutually exclusive scenarios with severity, 4–8 resolvable signposts, and a pre-mortem. RUNS independent calls forecast every signpost and scenario. The app computes the chance things go badly, the gloom index (−100 stabilising … +100 adverse) and the risk ranking. Signposts go into the ledger, so the broad prediction is scored as they resolve. The method and its sources are in `RESEARCH_METHODS.md`.

## Troubleshooting LM Studio

- **Context window exceeded:** set Context to the model's loaded length, narrow the scope, or reload the model with more context.
- **"did not finish within 600 seconds":** use 8K, fewer runs, or a smaller model. The CLI accepts `--timeout`.
- **"ran out of its N-token reply budget":** usually a reasoning model. Turn thinking off, or use an instruct model.
- **"Only N usable signposts" or "incoherent run":** try a stronger instruct model.
- **`vk::Queue::submit: ErrorDeviceLost`:** restart LM Studio, reload the model at 8192 context with less GPU offload, and set Context to 8K. For a CPU-only test: `lms load MODEL_KEY --gpu off --context-length 8192`.

## Command line

```bash
python3 -m overcast.cli outlook "CRISES & DISASTERS" --model MODEL_ID --days 90 --runs 3
python3 -m overcast.cli outlooks | outlook-show ID | outlook-resolve ID B --evidence-url URL
python3 -m overcast.cli score-report      # per-question Brier, log loss, gloom bias, scenarios, calibration, misses
```

## Data, privacy and upgrades

- Data lives in `~/.local/state/Marble_Oracle/news_oracle/` (or `%LOCALAPPDATA%\Marble_Oracle\news_oracle\`). The folder name is unchanged on purpose, so upgrades keep every forecast. `overcast_settings.json` there holds only UI preferences. Close the app before backing up.
- Database changes are additive only.
- There is no cloud inference, account, trading or background model run. The model reads cached RSS excerpts and cannot verify claims; motives and links are hypotheses.

## Tests

```bash
python3 -m unittest discover -s tests -v
xvfb-run -a python3 -m unittest discover -s tests -v     # include the graphical tests on headless Linux
```

There are 105 tests. In the build environment the 96 non-graphical tests passed. The 9 graphical tests passed only against a headless Tk stand-in, because Tkinter was unavailable there. **Run them under `xvfb-run` or on your desktop, and look at the app, to confirm the real rendering.** The images in `PREVIEW/` are design mockups with sample data, not screenshots.
