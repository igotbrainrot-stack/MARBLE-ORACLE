# Marble Oracle / EIDOLITH 0.4.7.2 — AUGURSPEX Market Pulse

**Date:** 11 November 2026  
**Base:** 0.4.7.1 + bundled AUGURSPEX 1.2.0 (Windows/Linux portable suite).

## What changed

- Restores the **former small market panel footprint** on the HOME dashboard, but **does not restore** the retired static Bitcoin/USD/gold/silver price tape.
- Its replacement is a rotating **AUGURSPEX / Market Pulse** line chart, using actual historical candles from the very same market-history providers the bundled AUGURSPEX module uses.
- Rotates **every 12 seconds** through **every symbol on the effective AUGURSPEX watchlist**, preserving list order. Previous/next arrows appear in the chart header. Default starter list has 25 entries, but the user's saved AUGURSPEX list and edits override it. Empty saved lists stay empty.
- Re-reads the AUGURSPEX watchlist every **20 seconds** (including after the user edits it in the separate browser dashboard); no restart is needed.
- Uses AUGURSPEX's MarketRouter and its on-disk cache, with an isolated **daemon background thread** for history requests. The Tk rendering thread is never blocked by market history downloads.
- Shows historical line graphs with observed latest prices, percentage change across the displayed history, original provider label and date of the last observation. The data is **not claimed to be live**. Green/red follows the displayed history, not speculative forecasts.
- For symbols without usable public historical data or when offline, the panel visibly says **HISTORY UNAVAILABLE** or **NETWORK DISABLED**. It does **not invent data**. Such symbols still rotate, and full TradingView charts may be accessible in the separate AUGURSPEX workspace when a network connection is available.
- The bottom news runner remains removed. All six workspaces, EIDOLITH conversion pipeline, native OS file dialogs, and AUGURSPEX independent window are retained.
- The previous GRADE layouts remain selectable, with chart positions and adjacent panels restored from the original pre-removal layout geometry so the chart has its own region.
- Existing `--no-network` and `--no-markets` startup options prevent the new chart from fetching remote data. The watchlist can still be viewed offline.

## Usage

Extract the whole ZIP, then run the existing Linux `.sh` or Windows `.vbs` launcher. On HOME, **AUGURSPEX** now appears as a changing line chart in the upper portion of the former right-side market position. Use its `<` / `>` header controls to change symbol immediately. To edit the watchlist or view full charts, select the **AUGURSPEX** tab in the top navigation bar. 

The embedded HOME panel does not need the browser companion server to be running; it uses the bundled data providers and locally saved AUGURSPEX settings directly. It never writes to the user's other application settings.

## Verification performed

- `python3 -m unittest discover -s Application/Tests -p test_augurspex_home_carousel.py -v`: **4/4 passed** (saved list, whole-list rotation, network thread isolation, unavailable quotes, explicit empty list, edits, offline mode).
- `python3 -m unittest discover -s Application/Tests -p test_augurspex_integration.py -v`: **4/4 passed** (existing AUGURSPEX server, window reopen and persistence tests).
- `xvfb-run -a python3 Application/Tests/test_no_news_or_markets.py`: passed (no retired ticker or news; new AUGURSPEX panel present in all layouts).
- `xvfb-run -a python3 Application/Tests/test_augurspex_home_gui.py`: passed (injected known history rendered, arrows advance and wrap, GRADE chart location and click targets across clean layouts).
- `xvfb-run -a python3 Application/Tests/test_tab_layout.py`: passed (default, retro, flat).
- `xvfb-run -a python3 Application/Tests/test_eidolith_workspaces.py`: passed.
- Python compilation and packaged release inventory verification.

**Not verified:** actual third-party market network responses, live quote freshness, native Windows and Linux Mint physical desktop behavior, hardware GPU transcoding and the entire historical suite. The prices shown by external providers may be delayed or end-of-day. Do not use the panel as execution-grade trading data.

**GitHub:** https://github.com/igotbrainrot-stack/MARBLE-ORACLE  
**Status:** New local release ZIP provided here; this patch has not been pushed to GitHub.
