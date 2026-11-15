# Marble Oracle 0.4.8.3 — AUGURSPEX chart-area repair

Release date: 13 November 2026

## Reported defect

A screenshot from the installed 0.4.8.2 build showed (1) serious overlap between chart titles, date axes, data-source captions and graph contents in the nine-chart workspace; (2) unavailable equity histories, including several US and Australian/Japanese listings.

The embedded suite was reproduced under Xvfb at a 1086 × 814 desktop. Its available AUGURSPEX panel was only about 794 × 475 pixels. With nine charts, each chart card was approximately 156 × 84 pixels and **its plot canvas collapsed to 1 × 1 pixel**. Existing isolated tests used much larger workspaces and had missed this actual-suite geometry.

## Changes made in this release

- Replaced the non-scrollable 3×3 price-chart grid with a **vertically scrollable chart viewport**. All nine saved chart slots remain available, but graph columns respond to the real available width. Each chart row receives a minimum 280-pixel allocation so graph axes, prices and status do not collapse.
- At smaller widths, display one large chart per row; larger apertures display two or three columns if the plotted cards will remain usable. The scrollbar and mouse wheel navigate additional charts.
- Chart source/status caption now claims its space before the expandable plot widget. Tk Canvas default requested dimensions no longer squeeze the status row or graph into a 1×1 area.
- Hide redundant in-canvas observation text in compact charts (the data source and observation details remain in the chart's dedicated status line). Date axes and prices remain visible. Smaller widths get appropriately sized axis type.
- The native SOURCE DETAILS popup recognises all current adapters, including Massive, J-Quants, KRX, FRED, CoinGecko and CoinPaprika. For unavailable histories it provides truthful provider-specific configuration suggestions.
- Changed the no-eligible-source graph label to **DATA SOURCE SETUP NEEDED** rather than implying the market exchange is necessarily inaccessible.

## Deliberately unchanged

- **No false data fix.** Existing providers are unchanged. The missing equity charts in the screenshot are mostly source-access, authentication, licensing or temporary rate-limit issues. There is no legitimately guaranteed keyless data coverage for every ASX/JPX/KRX/US instrument.
- Stooq public EOD history may be unavailable or rate-limited. It is the keyless default for eligible US equity listings. The optional Yahoo/Nasdaq website endpoints remain opt-in and cannot be represented as official or reliable APIs.
- Do not substitute index ETFs, unrelated exchange shares or synthesized OHLC candles for an unavailable listing.
- Watchlists, local settings, tab order and EIDOLITH/Oggcultist modules remain unchanged.

For documented optional feed configuration and exchange entitlements see `Application/Documentation/AUGURSPEX_PROVIDER_RESEARCH_IMPLEMENTATION_0.4.8.2.md`.

## Checks performed

- New nine-chart, min-size, scrolling and axis regression: PASS under Linux Xvfb, including actual suite aperture.
- Native AUGURSPEX tab/navigation: PASS.
- Resize/readability GUI regression: PASS.
- Chart grid/line/candlestick and date-axis regression: PASS.
- Provider source-details GUI regression: PASS.
- Multisource history and interval routing regressions: PASS (offline controlled fixtures).
- Tab navigation across default/retro/flat: PASS.
- Release inventory integrity: verify on packaged archive.

## Limits

- Live upstream provider responses were **not** tested from the user's desktop, and US/ASX/JPX/KRX data availability is not guaranteed.
- No physical Windows 11 or Linux Mint run was completed; Linux tests use a virtual X server.
- FFmpeg encoder code was not changed and its long regression suite was not rerun for this chart-only release.
