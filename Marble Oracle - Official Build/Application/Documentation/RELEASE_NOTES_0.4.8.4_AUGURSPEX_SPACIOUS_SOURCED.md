# Marble Oracle 0.4.8.4 — Spacious AUGURSPEX + sourced-only market display

Date: 13 November 2026

## User request
- Make AUGURSPEX less compact.
- Remove markets from the visible dashboard when no actual market-data source works.

## Implemented

### Spacious, legible charts
- The chart deck now uses **at most two columns** (one on narrower screens) with **405px minimum card height** and larger gaps. The nine-slot workspace remains selectable and scrolls instead of crushing charts.
- The active-market identity has moved into the main panel, freeing space for the left watchlist at 900×580.
- The existing dark Oggcultist styling, chart axes, thick outlined lines/candles and familiar tab order remain intact.

### Only show charts with real returned history
- AUGURSPEX now defaults to **SOURCED ONLY**. Main-chart cards and the sidebar are included only after a provider returns usable historical OHLC/close observations for the selected interval.
- Unsupported exchanges with no currently eligible route are excluded immediately; failed requests are hidden after they complete. The dashboard no longer fills nine slots with repeating 'DATA SOURCE LIMITED' or 'EXCHANGE ACCESS REQUIRED' cards.
- The app checks the saved watchlist asynchronously with a conservative **one-at-a-time background source audit**, after prioritising assigned chart slots. Existing shared provider cache, cooldown, retry and request-coalescing rules remain in force.
- The sidebar reports the number of markets with actual observations and how many have been checked.
- **SHOW ALL MARKETS** toggles review mode, allowing a user to inspect, reassign, or remove unsuccessful tickers and to retry with REFRESH. Markets can reappear when access recovers.
- User-saved watchlists, workspace chart slots and favourites are **not erased** by temporary network outages or provider quota failures. This is a non-destructive *visible removal* rather than irrevocable deletion of personal selections.

### Important source limitations
- Provider coverage, exchange licensing and account/API entitlement requirements remain unchanged from 0.4.8.3. This patch improves what is displayed; it does **not** bypass market-data restrictions or guarantee a live source for every stock.
- A market can be temporarily hidden when all configured sources fail; the retry and REFRESH paths allow recovery. A cached historical response may qualify if it contains genuine observations and was accepted by the router; cache state remains labelled.
- Initial source verification can take time because public-provider rate limits are respected, rather than firing dozens of concurrent requests.

## Tests run
- test_augurspex_sourced_layout_0484.py — PASS (mock successful, unavailable, no-route, recovery and personal watchlist preservation)
- test_augurspex_native_tab.py — PASS
- test_augurspex_readability_0481.py — PASS
- test_augurspex_scrollable_0483.py — PASS
- test_augurspex_grid_contrast_0480.py — PASS
- test_augurspex_source_details_gui_0478.py — PASS
- test_augurspex_home_carousel.py — PASS
- test_no_news_or_markets.py — PASS
- test_tab_layout.py — PASS (default/retro/flat)
- Application/Tools/verify_release.py — PASS after re-inventory

Real third-party feed responses, physical Windows and Linux Mint GUI tests, and the complete FFmpeg suite were not rerun. EIDOLITH conversion and the provider code are unchanged.

## Main source changes
- Application/Runtime/Marble_Oracle_App/oracle_augurspex_tab.py
- Application/Tests/test_augurspex_native_tab.py (updated expectation for sourced-only default)
- Application/Tests/test_augurspex_sourced_layout_0484.py (new)
- Application/Documentation/BUILD_MANIFEST.json and FILE_INVENTORY.json
