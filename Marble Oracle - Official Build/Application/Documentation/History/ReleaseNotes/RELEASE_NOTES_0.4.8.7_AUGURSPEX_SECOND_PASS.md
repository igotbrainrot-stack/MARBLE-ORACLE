# Marble Oracle 0.4.8.7 — independent AUGURSPEX second pass

Date: 13 November 2026

**Starting point:** `Marble-Oracle-0.4.8.6-AUGURSPEX-TWO-PASS-FIXES-Windows-Linux.zip`. This release preserves the complete native suite and does not replace the existing converter, watchlist, data providers or source permissions.

## Phase 1 — correctness fixes

1. **Unusable future-dated price rows must not make a market look fresh.** The observation-age check now looks only at OHLC rows with valid finite prices and valid price relationships. A malformed row stamped with today's date cannot turn a stale 2021 market into a recently verified chart. A valid observation date is required for inclusion in the `WITH DATA` / auto-fill view.
2. **CSV exports were truncated to the last 120 plotted rows.** Export now uses the complete set of validated received observations, independent of the plot's visible window. It does not fabricate missing OHLC values, silently backfill historical prices or download additional data when saving.
3. **Percentage change did not match the viewed history.** Price change in the chart footer now describes the **visible plotted bars**; the footer identifies it with `VIEW`. Latest price remains the provider's latest actual value.
4. **Extra spreadsheet formula prefixes.** CSV cell escaping now also handles tab/newline prefixes, byte-order marks and common full-width formula characters. This is defense in depth, not a claim of universal Excel CSV safety; treat files from untrusted feeds with care.

## Phase 2 — independent usability feature

**Chart observation window: `VISIBLE 30 BARS / 90 BARS / MAX BARS`.** This uses only received historical observations, so it works offline when cached data is available and generates no extra API requests. The selection is saved across launches in the AUGURSPEX local settings. A bar is a data observation, **not necessarily a calendar day** (it can be an hourly, weekly or monthly bar depending on the selected PERIOD). This avoids a misleading "30 days" or "1 year" claim without continuous provider availability.

- LINE uses the selected number of real observation points; MAX uses the complete valid response.
- CANDLES always respects minimum visible bar width. If MAX exceeds a readable number of candlesticks in a small card, it displays the most recent readable bars, with that count already disclosed by the chart footer.
- The source-details view, watchlist and selected-market identity remain unchanged.
- Range selection persists globally across AUGURSPEX workspaces. Existing saved workspace symbols, individual chart LINE/CANDLES choices, and custom watchlists are not overwritten.

## Research context

TradingView Lightweight Charts documents adjustable time-scale bar spacing, visible ranges and automatic fit-to-data as core chart-navigation features. A smaller observation-count control is suitable for the existing Python/Tk interface without adding a browser or JavaScript runtime.

- https://tradingview.github.io/lightweight-charts/docs/time-scale
- https://tradingview.github.io/lightweight-charts/tutorials/customization/time-scale
- https://owasp.github.io/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/07-Injection/21-CSV_Injection

## Tests performed in Linux Xvfb / Python 3

- `Tests/test_augurspex_0487_second_pass.py`: **PASS** (synthetic history 250 rows, invalid future row, visible ranges, persisted setting, right-side date ticks, all 250 CSV records, safe-string handling, narrow 920x580 aperture, and visible-window percentage).
- `Tests/test_augurspex_charts_layout_0485.py`: **542/542 PASS** (real Tk geometry, selected chart counts, source auto-fill, 900x580/1000x650/1400x870, text fit and preset persistence).
- `Tests/test_augurspex_0486_regressions.py`: **PASS** (older fixes still hold).
- `Tests/test_augurspex_native_tab.py`, `test_augurspex_chart_axes_and_history.py`, `test_augurspex_grid_contrast_0480.py`, `test_augurspex_readability_0481.py`, `test_augurspex_source_details_gui_0478.py`, `test_augurspex_sourced_layout_0484.py`, `test_augurspex_scrollable_0483.py`: **PASS**.
- `test_augurspex_home_carousel.py`, `test_augurspex_multisource_0477.py`, `test_augurspex_research_0482.py`: **PASS**.
- ZIP integrity, fresh extraction and manifest checks: run after packaging, reported separately.

The latest provider responses, protected exchange permissions, physical Windows 11 and physical Linux Mint installations were **not** verified. The 0.4.8.6 EIDOLITH FFmpeg regression passed 103/103 checks; its converter was not changed in 0.4.8.7. This release adds **no new live market-data providers** and cannot guarantee missing market-history sources will become available.

## Changed files

- `Application/Runtime/Marble_Oracle_App/oracle_augurspex_tab.py`
- `Application/Runtime/Marble_Oracle_App/Augurspex/augurspex/core.py`
- `Application/Tests/test_augurspex_0487_second_pass.py`
- `Application/Documentation/RELEASE_NOTES_0.4.8.7_AUGURSPEX_SECOND_PASS.md`
- `Application/Documentation/BUILD_MANIFEST.json` (regenerated)
- `Application/Documentation/FILE_INVENTORY.json` (regenerated)
