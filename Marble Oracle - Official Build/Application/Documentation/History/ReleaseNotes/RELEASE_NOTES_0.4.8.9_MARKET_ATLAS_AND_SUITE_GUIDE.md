# Marble Oracle 0.4.8.9 — Market Atlas / Suite Field Guide

**Date:** 13 November 2026  
**Baseline:** Complete Marble Oracle 0.4.8.8 Windows/Linux ZIP, unmodified provider credentials and exchange entitlements.  
**Release type:** Incremental app-wide usability and AUGURSPEX interaction update. Not a claim of unrestricted live data or a finished commercial platform.

## User-facing improvements

### 1. MARKET ATLAS — multi-market comparison inside AUGURSPEX
- New separate, scrollable, sortable and searchable Market Atlas view, available via `◈ MARKET ATLAS`.
- All 23 curated default markets are shown, **even if not currently available**. Each market has a status (RECENT, STALE, NOT LOADED, SOURCE ERROR, etc.), original ticker, category, last verified close, change within the selected observation range, observation date and the source that actually returned its candles.
- The comparison uses within-asset percentage changes; it never adds prices from instruments with different currencies. An unavailable observation is blank (`—`), not zero.
- Market Atlas supports opening the selected market in the currently active chart, sorting by columns, instant search, and exporting a CSV summary with provider identity and data health.
- All of these actions use the **existing validated memory cache**; simply opening the Atlas triggers no network requests.

### 2. Observation table and keyboard chart inspection
- `▤ OBSERVATION TABLE` opens a keyboard-scrollable historical-data table for the selected native chart; columns include timestamp, observed OHLC where available, close and volume. It is labelled as historical.
- Each chart Canvas can receive keyboard focus. **Left/Right** navigate observations, **Home/End** jump to the beginning/end of the currently plotted series; the existing crosshair and exact date/close readout follow the active point.
- Hover inspection and individual chart styles remain available.
- Corrected the native chart CSV export so *close-only* provider history has blank open/high/low fields, instead of writing repeated closing prices as if they had been observed. This is a data-integrity correction.

### 3. A coloured, discoverable workspace
- Stocks, FX and crypto use different legible category colours in the watchlist: amber, teal and lavender. A small legend explains them; watchlist selection and filters remain unchanged.
- Added a **secondary toolbar** for Atlas, Observation Table and Shortcuts. Existing chart controls, filters and source diagnostics are preserved.
- **F1** opens a dark, themed **Marble Oracle Field Guide** with descriptions and launch controls for all six suite workspaces: HOME, OGGCULTIST, EIDOLITH, AUGURSPEX, PASSPHRASE, TOUCH TYPE. HOME keyboard shortcuts are documented. The guide launches no external websites or servers.

## Accuracy, safety, privacy and provider restrictions
- No synthetic market data is present in production code; screenshots and test fixtures use synthetic values **only for tests**.
- No external API added, no new credentials required, no paid service introduced, and no personal saved watchlist reset beyond the existing one-time 0.4.8.8 migration logic.
- Market Atlas never presents historical closes as real-time tradable quotes. Verified freshness is computed from actual candle timestamps; the last received date and source are explicit.
- Both summary and per-chart CSV exports neutralise spreadsheet-formula text where relevant. See OWASP CSV injection guidance: https://owasp.github.io/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/07-Injection/21-CSV_Injection
- The native Tk observation table and keyboard controls were chosen using accessible-chart patterns from TradingView's official documentation: https://tradingview.github.io/lightweight-charts/plugins/accessibility . Their web plugin has **not** been integrated or bundled; the native UI is independently implemented.
- Existing free and optional-key market-data providers and their exchange entitlement restrictions are unchanged. `DATA SOURCE LIMITED` can still appear for markets without permitted access.

## Files changed / added

- `Application/Runtime/Marble_Oracle_App/oracle_augurspex_tab.py` — toolbar, categorical accents, keyboard chart inspection, CSV correction
- `Application/Runtime/Marble_Oracle_App/oracle_augurspex_insights.py` — Market Atlas and provider-record table
- `Application/Runtime/Marble_Oracle_App/oracle_suite_guide.py` — native F1 Field Guide
- `Application/Runtime/Marble_Oracle_App/marble_oracle.py` — F1 keyboard hook
- `Application/Tests/test_market_atlas_0489.py` — deterministic data and GUI tests
- `Application/Documentation/QUICK_START_0.4.8.9.md` — navigation and data-use guide
- This release note and regenerated build manifest/inventory.

## Executed regression results

- New Market Atlas/data tests: **2/2 passed**
- New Market Atlas/GUI/F1 tests under Linux Xvfb: **3/3 passed**
- AUGURSPEX 0.4.8.8 popular markets and FX history: **7/7 passed**
- AUGURSPEX 0.4.8.7 visible-range and CSV tests: **passed**
- AUGURSPEX 0.4.8.6 history/hover/source tests: **passed**
- AUGURSPEX source-routing, chart axes, sourced-only and chart-grid tests: **passed**
- Six-tab navigation: **default/retro/flat passed**
- HOME chart, news-removed regression: **passed**
- EIDOLITH workspace: **passed**
- EIDOLITH FFmpeg queue reliability: **103/103 checks passed**
- An older exhaustive 542-check chart-layout script did not finish within the current test window; it is not represented as passed for this version. New focused GUI checks exercise the new controls.
- Release file SHA-256 inventory: verified after packaging.
- ZIP extraction and Linux launcher mode: verified after packaging.

## Remaining limitations

- No hardware validation on physical Windows 11 or Linux Mint; this test environment uses Linux Xvfb.
- No independent live provider request can be made in this sandbox; historical market data remains restricted by providers and exchanges.
- Market Atlas is a factual comparison of *received* observations, not order execution, portfolio accounting or investment advice.
- The entire multi-module suite cannot honestly be certified defect-free or “perfect.” Only the tests above are claimed.
