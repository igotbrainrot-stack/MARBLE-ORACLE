# Marble Oracle 0.4.8.1 — AUGURSPEX Readability

Release date: 2026-11-13

## Scope

This is a **targeted presentation and layout release** based on the complete, verified Marble Oracle 0.4.8.0 application. AUGURSPEX remains an embedded native Tk tab directly beside EIDOLITH. The Oggcultist-generated background textures, original market-provider integrations, stored watchlists, and EIDOLITH's media converter are preserved.

## Changes

- **Market names:** Chart tickers increased from 11 to **15 pt bold**, with the proper company/market name in a separate **11 pt** row beneath. Prices increased to **14 pt bold**. The old single-line card titles did not identify companies consistently.
- **Watchlist:** Wider **292 px** fixed sidebar; tickers and names increased to **13 pt bold**. Rows are shortened by measured pixel width with a proper ellipsis, rather than clipped arbitrarily. Every market remains selectable and searchable.
- **Full selected market:** The sidebar displays the full company/market name, wrapped when necessary, for whichever chart slot is active. SOURCE DETAILS now includes this name as well as the ticker.
- **General readability:** Larger heading, filter, control, search, status, and source labels. Chart axes are now **11 pt**, and chart notes are **10 pt**. The high-contrast grid, thick outlined lines/candles, and themed colours remain unchanged.
- **Responsive controls:** The workspace/charts/period/display selectors automatically wrap into two rows at narrower widths and one column on very narrow viewports instead of disappearing off the right edge.
- **Small windows:** The status/footer strips are allocated space before charts expand, preventing their prior clipping at compact window heights.
- **HOME's rotating chart:** Market display name 14 pt, ticker 12 pt, value 13 pt, and source/time note 10 pt.

No live market prices or synthetic data are included in the application package. A separately generated visual-check screenshot (if provided) uses clearly labelled synthetic observations for illustration only.

## Tests performed

In a Linux virtual display with offline, temporary user settings:

- `Tests/test_augurspex_readability_0481.py` — **PASS**, including 1400×870 / 1000×650 / 900×580 viewport checks, full-name display, chart layouts 1/2/4/6/9, source-detail readout and truncation boundaries.
- `Tests/test_augurspex_grid_contrast_0480.py` — **PASS**.
- `Tests/test_augurspex_chart_axes_and_history.py` — **PASS**.
- `Tests/test_augurspex_stock_fallback.py` — **PASS**.
- `Tests/test_augurspex_source_details_gui_0478.py` — **PASS**.
- `Tests/test_augurspex_home_carousel.py` — **PASS**.
- Native panel/settings portion of `Tests/test_augurspex_native_tab.py` — **PASS**.
- `Application/Tools/verify_release.py` — **PASS**, including critical embedded archive integrity.

The remaining broad scene-entry test spends extended time in the existing large software-decoded CRT bezel image; it was not completed in this focused UI regression run. Native Windows and physical Linux Mint have not been retested. Existing external market provider reliability remains subject to network and exchange restrictions.

## Modified files

- `Application/Runtime/Marble_Oracle_App/oracle_augurspex_tab.py`
- `Application/Runtime/Marble_Oracle_App/marble_oracle.py`
- `Application/Tests/test_augurspex_readability_0481.py`
- Release notes and build/inventory JSON

## Launch

Extract the entire ZIP, then run `START MARBLE ORACLE - WINDOWS.vbs` or `START MARBLE ORACLE - LINUX.sh` from the extracted top-level folder. Previous per-user AUGURSPEX settings are not bundled or overwritten by this archive.
