# Marble Oracle 0.4.8.6 — AUGURSPEX two-pass audit and repair

**Date:** 13 November 2026  
**Base archive:** `Marble-Oracle-0.4.8.5-AUGURSPEX-ALL-CHARTS-Windows-Linux.zip`  
**Base SHA-256:** `0247444f2e9a7ec8d740d3ffc59af70492666fe127400aaf71eedac5d3e9da85`

This release is based on the **user-uploaded 0.4.8.5 ALL-CHARTS** build, not an earlier 0.4.8.5 archive. The six-tab suite and Oggcultist texture are preserved.

## Phase 1 — reproducible defects corrected

1. **Date-axis/observation-text collisions.** Removed the redundant in-canvas bottom caption. Source/observation information remains in the card footer and SOURCE DETAILS, and candle/close-only status is prefixed to the footer when relevant. The real date axis and price axis remain in the plot. This resolves the 14 previous collision assertions without shrinking font sizes or suppressing axis labels.
2. **Wrong stock in SOURCE DETAILS.** The dialog now uses the selected card's **currently plotted symbol** from `_space_plan()`. If that card was auto-filled, the saved target is reported separately; provider attempts and data timestamps refer to the displayed stock.
3. **Ancient/undated history falsely counted as available.** `history_health()` now distinguishes `missing`, `undated`, `future`, `stale`, and `recent`. Only **recent** valid provider observations qualify for auto-filled slots and the WITH DATA filter. Historical values can still be viewed in SHOW ALL MARKETS, with a stale date label. Daily equity history tolerates approximately eight calendar days for weekends and extended exchange closures; crypto daily values use three days; weekly/monthly have wider windows. These are heuristic freshness checks, **not exchange-specific trading calendars or real-time data certification**.
4. **Small-window single-chart size.** In a compressed CRT aperture, the single-chart view may use vertical scrolling to preserve a taller plot than the minimum-sized four-chart cards. At normal size, a single chart still expands into available space.
5. **Saved candle-style migration.** The old automatic "convert previous styles to LINE" rule was destructive to intentionally saved CANDLES preferences. Existing selections and per-workspace/per-slot styles now survive upgrades; a new profile still defaults to LINE.
6. **Repeated timestamp scans.** Market-freshness results are cached per data-object identity and UTC day for smooth multi-chart refreshes. A changed provider response or a new UTC date causes re-evaluation.

## Phase 2 — practical features from market charting applications

1. **Observation inspector/crosshair.** Move the pointer across a line or candlestick chart to see the real observation date, close, and available open/high/low values in the chart footer. The matching data point is highlighted and a vertical guide follows the actual plotted bar. Moving the mouse away restores normal source information. No synthetic interpolation, prices or timestamps are inserted.
2. **CSV export.** The new **CSV** button exports the actual historical records of the market **currently displayed in the selected chart** (not its saved target when auto-filled). Includes symbol, timestamp, OHLC, volume, close-only flag, provider and currency; no API key or URL is exported. Exported provider strings are safeguarded against spreadsheet formula injection. Uses a save dialog and does not write unless the user chooses a destination.

Feature research: TradingView Lightweight Charts supports tracking tooltips, synchronized observation inspection and chart series; OpenBB charts offer technical overlays. The NSW Digital Design System and Morningstar responsive chart guidance emphasize readable axes, metadata and exact-value alternatives. Rather than introducing a webview and a new JavaScript rendering runtime into a Python/Tk suite, this release implements a small native hover inspector and data export while keeping existing native styling and no-login behavior.

References:
- https://www.tradingview.com/lightweight-charts/
- https://tradingview.github.io/lightweight-charts/examples/tooltips-and-legends/tracking-tooltip
- https://tradingview.github.io/lightweight-charts/examples
- https://docs.openbb.co/odp/v4/python/extensions/infrastructure/openbb-charting/indicators
- https://designsystem.nsw.gov.au/methods/charts-and-graphs.html
- https://design.tec7072a.eas.morningstar.com/systems/data-visualization/guidelines/responsive-design

## Verification and limitations

Completed using Linux Xvfb / Python 3 with deterministic fixture providers:
- 0.4.8.5 ALL-CHARTS geometry/text/selector suite: **542/542**, after adapting its fixtures to use current historical dates and its old migration assertions to preserve deliberately saved preferences.
- New `test_augurspex_0486_regressions.py`: provider identity after auto-fill; freshness, future dates and weekend grace; older preference migration; chart axes; crosshair; CSV export of real records; CSV injection safeguard.
- Focused native-tab, sourced-only, scroll, chart-axis, contrast, readability, source-details, providers, HOME, tab-layout and EIDOLITH workspace regressions.
- EIDOLITH FFmpeg queue reliability: **103/103 checks passed** (CPU encode/queue safety; hardware encoders cannot be tested without matching devices).
- Release integrity to be verified from an extracted ZIP after packaging.

**Important:** The app's bundled provider adapters and market-access restrictions were not changed. No current real-world provider response, native Windows machine, physical Linux Mint machine, or protected exchange entitlement was verified. Public APIs can become unavailable. A "recent" cached observation is NOT necessarily a live quote, nor proof that its provider can currently be reached. Failures do not delete personal watchlists or replace data with another ticker without a visible auto-fill label.

## Launch and use

Extract the entire release folder and use `START MARBLE ORACLE - LINUX.sh` or `START MARBLE ORACLE - WINDOWS.vbs`. Open AUGURSPEX after EIDOLITH. `CHARTS` controls 1/2/4/6/9 slots. Mouse over a graph to inspect dates and prices. Select a card and click `CSV` to save its provider records. `SOURCE DETAILS` gives complete provenance and missing-provider diagnostics. Existing user settings remain outside the portable release, under the local AUGURSPEX config directory.
