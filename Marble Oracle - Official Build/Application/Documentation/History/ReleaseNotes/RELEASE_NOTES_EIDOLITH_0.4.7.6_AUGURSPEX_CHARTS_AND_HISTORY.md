# Marble Oracle — EIDOLITH 0.4.7.6 / AUGURSPEX chart and market history

Date: 13 November 2026

## Changes to the native AUGURSPEX suite tab

### Chart readability
- The line chart stroke is now 3.4 px, with rounded joints and a clearly marked latest observation. Candle wicks and bodies have also been strengthened.
- Charts reserve space for a **bottom date axis** and a **right-hand price axis** rather than printing only minimum and maximum values.
- The X axis uses real provider observation timestamps, with adaptive daily (`09 NOV`), month/year (`NOV '26`) or annual (`2026`) tick labels as appropriate to the date span.
- The Y axis prints four to five real price levels, aligned to grid lines, with enough digits for smaller-priced assets.
- The wider axis margins work with the suite's single-, dual-, four-, six- and nine-chart layouts.

### Missing history diagnosis and remedies

**Prior root causes observed in the source:**
- Stooq CSV often returns `N/D` (symbol unavailable or provider restriction). Its automation quota can also reply with HTML/HTTP failures.
- Yahoo Finance's chart endpoint is *unofficial*, and may return no history or HTTP 403/429, even when a symbol is correct. Neither provider has guaranteed complete market coverage.
- Previous Yahoo chart parsing dropped entire days whenever one of open/high/low values was null, even though the real closing price was present.
- Unavailable charts stayed in an error state until manual REFRESH.
- International stocks were sent to a less-reliable Stooq route before Yahoo, unnecessarily delaying the fallback.

**New behavior:**
- When a Yahoo bar includes a real timestamp and close but incomplete OHLC, preserve that real close, mark `close_only`, and render a **line** even in candlestick mode; do not invent an OHLC bar. Include a close-only notice.
- Prefer Yahoo for the same ASX/Japan/LSE listing, retain Stooq as fallback; US and index symbols remain Stooq-first, while Korean symbols remain Naver-first with Yahoo fallback.
- Recognize Stooq HTML/quota challenges explicitly and respect the router's 15-minute provider cooldown. No proxy, CAPTCHA circumvention, or aggressive retry loop is introduced.
- Distinguish `DATA SOURCE LIMITED`, `NETWORK ISSUE`, `LISTING NOT SUPPORTED`, and `NO HISTORY FROM PROVIDER`. Clicking a chart surfaces its source/error detail in the bottom status line.
- Retry failed charts after 15 minutes if the tab remains open; the existing manual REFRESH continues to work and respects provider cooldowns.

### Preserved
- Native (not web-launcher) AUGURSPEX tab, textured dark Oggcultist styling, and persistent workspace layouts/watchlist.
- HOME rotating AUGURSPEX market chart, removed news ticker, removed fixed Bitcoin/gold HOME panel.
- EIDOLITH media conversion code and its native file pickers; no FFmpeg modifications in this release.

## Files edited
- `Application/Runtime/Marble_Oracle_App/oracle_augurspex_tab.py`
- `Application/Runtime/Marble_Oracle_App/Augurspex/augurspex/providers.py`
- `Application/Tests/test_augurspex_stock_fallback.py` (expected international route priority)
- `Application/Tests/test_augurspex_chart_axes_and_history.py` (new fixtures / GUI tests)
- Release manifests and these notes.

## Verification
- Python compilation: **pass**
- Dated chart axis and price tick regression: **pass**
- Sparse Yahoo real-close preservation regression: **pass**
- Provider cooldown/no-fake-history regression: **pass**
- Stock fallback mapping with fixtures, including ASX/US: **pass**
- Native AUGURSPEX panel and active-tab/sidebar regression: **pass**
- HOME rotating watchlist, removed fixed market/news ticker: **pass**
- Default, retro and flat suite tab navigation: **pass**
- Packaged source integrity and critical archive verifier: **pass**

**Not verified:** Real public market providers are unavailable from this container's network; the above market-history tests use controlled fixture responses. Physical Windows and Linux Mint desktop operation, and a full FFmpeg conversion regression, were not rerun for this GUI/provider-focused patch. Some symbols can still show missing data when *all* public sources refuse or lack history. The UI now explains that failure instead of inventing prices.

## Run
Extract the release ZIP and launch `START MARBLE ORACLE - LINUX.sh` on Linux or `START MARBLE ORACLE - WINDOWS.vbs` on Windows (or use the supplied `.bat` fallback).
