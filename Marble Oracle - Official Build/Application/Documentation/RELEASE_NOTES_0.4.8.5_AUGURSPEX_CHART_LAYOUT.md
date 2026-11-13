# Marble Oracle 0.4.8.5 — AUGURSPEX chart count, chart size and text fit

Date: 13 November 2026 · Baseline: 0.4.8.4 (ZIP SHA-256 `9505949117c4ccd36d3ab6c73cb803f689dec42f4c192350b3048f604ddd1209`)

Scope: `oracle_augurspex_tab.py`, the AUGURSPEX settings default in `Augurspex/augurspex/core.py` and `app.js` (and their identical installer copies under `Tools/AUGURSPEX_Module/payload`), plus one new test. EIDOLITH, OGGCULTIST, PASSPHRASE, TOUCH TYPE, HOME,
the market providers, assets and launchers are unchanged.

## Defects reproduced in 0.4.8.4

Synthetic data labelled `TEST FIXTURE, NOT LIVE`, served by a fake router; no network.

| Defect | Measured in 0.4.8.4 | Cause |
|---|---|---|
| CHARTS selector did nothing | Data in slots 1/5/9: CHARTS 1, 2 and 4 all showed only slot 1. Data in slots 4/8: CHARTS 1 and 2 showed **no chart**. | In sourced-only mode `_chart_indices` dropped every slot without verified data, so the count only changed which unverified slots were hidden. |
| Charts never grew | One chart alone in a 1078×652 area was 284 px tall, the same as with several. | Every row had `minsize=405`; the grid used at most 2 columns and never filled the height. |
| Overlapping/clipped text | At 900×580 the status line ran under "LOCAL · NO LOGIN" ("STOCKS" showed as "KS"), the footer was cut mid-word and "15/25 CHECKED" was clipped. | Fixed-text labels; Tk crops overlong text on both sides. Text inside the charts did not collide. |

## Changes

- **CHARTS N always represents saved slots 1..N.**
  - In sourced-only mode (the default), a slot with real history is a full chart.
  - A slot without data becomes a compact tab above the charts with its number, market and state: `CHECKING…`, `LIMITED`, `NETWORK`, `UNSUPPORTED`, `NO HISTORY`, `NEEDS SETUP`, `PICK A MARKET`.
  - Clicking a tab selects that slot, so a market can be assigned to it from the list. When tabs exceed two rows, a `+N MORE · SHOW ALL` tab opens SHOW ALL MARKETS.
  - SHOW ALL MARKETS shows all N slots as full cards, as before.
- **Count badge** under the selectors states the requested count and how many have data, e.g. `CHARTS: 4 REQUESTED · 1 WITH DATA · 3 SHOWN AS TABS ABOVE · SLOT 9 ALSO HAS DATA`. It never implies more usable charts than exist.
- **Chart size follows the available area** (`chart_grid_plan`, a pure function).
  - One chart fills the chart area. Two sit side by side when wide enough. Four form a 2×2 grid.
  - Dense layouts keep a legible minimum card (360×280) and scroll vertically.
  - Relayout is debounced to one pass per geometry change.
- **Text fit:** the status line, footer note, sidebar counter, count badge and slot tabs are fitted to their measured pixel width with an ellipsis. The selected market name wraps to the real panel width instead of a fixed 660 px.
- All nine saved slots, the watchlist, favourites and settings are preserved; CHARTS changes never delete them.
- **LINE / CANDLES switch on every chart**, as in other market viewers.
  - Each chart remembers its own choice, per workspace and across restarts (`slot_styles` in settings).
  - The selector formerly labelled DISPLAY is now **ALL CHARTS**: it sets every chart at once and clears per-chart choices.
  - The switch sits between the chart's name and its price and fits at 900×580 and in 2-column layouts.
- **Line graphs by default.**
  - New installs draw line graphs. Settings saved by earlier versions are converted to line once, including saved workspaces: they recorded candles only because that was the default.
  - CANDLES remains under DISPLAY. Choosing it afterwards is saved and kept (marker `line_default_0485`).
  - LINE is listed first. The standalone browser AUGURSPEX uses line for new workspaces too.
  - The HOME chart was already a line.
- **Hang fix:** text is measured through Tk directly instead of `tkinter.font.Font` objects.
  - A Font object deletes its Tk font when garbage-collected, and the collector can run on a market-data worker thread. If that font's window was already closed, the worker hung and its chart stayed on "CHECKING…" forever.
  - Found by the new test, which opens many windows in one process. Not observed in normal single-window use.

## Tests

New: `Application/Tests/test_augurspex_charts_layout_0485.py`, **519/519** checks, including the per-chart switch (only the clicked chart changes; kept across workspace switch and restart; ALL CHARTS sets every chart; header fits), line default, one-time conversion of old candle settings and a remembered CANDLES choice. It fails on 0.4.8.4 (104 of 334 checks at that time).

| Area | What is checked |
|---|---|
| Layout function | `chart_grid_plan` sizes for 1, 4 and 9 charts and small views. |
| CHARTS 1/2/4/6/9 at 900×580, 1000×650 and 1400×870, data in slots 1/5/9 and then 4/8 | Exactly the slots with data among 1..N are full charts; every slot 1..N is a chart or a tab. |
| Chart text | No overlapping or out-of-canvas text (`Canvas.bbox`). |
| Interface text | Status, footer, counter, badge and tabs fit their widgets. |
| Controls | BACK TO HOME, SOURCE DETAILS and REFRESH stay inside the window. |
| Size | At 1400×870 one chart has more than 1.8× the area of each of four. At smaller sizes one chart fills the area and four scroll. |
| Persistence | All nine saved slots survive; CHARTS=2 is restored after a restart. |

Full suite on a clean copy: 43/43 test scripts pass. That is the 42 from 0.4.8.4, all unchanged, plus the new one.

## Not verified

- Physical Windows 11 or Linux Mint desktops: tests ran under Xvfb only.
- Live third-party market data: only synthetic fixture data was used.
- Below about 1000×650 the chart area is only ~300–370 px tall. One chart fills it and dense layouts scroll; the 292 px sidebar was not changed.
