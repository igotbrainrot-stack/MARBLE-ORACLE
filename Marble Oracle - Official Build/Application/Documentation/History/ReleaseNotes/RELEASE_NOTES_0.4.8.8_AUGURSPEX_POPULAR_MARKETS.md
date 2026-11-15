# Marble Oracle 0.4.8.8 — AUGURSPEX popular markets / spacious workspace
**Date:** 13 November 2026 (Australia/Sydney)

## What changed
- Replaced the starter list with 23 widely followed assets: 10 US securities, 7 reference-rate FX pairs, 6 cryptocurrencies. The popular-watchlist source is a starting shortlist, **not a guarantee that every stock is accessible without credentials**.
- **Once on upgrade**, the app backs up both `~/.config/augurspex/settings.json` and `watchlist.json` (or XDG_CONFIG_HOME equivalent) into `watchlist-backups/popular-reset-*`, then replaces the saved market list and chart slots with this curated set. A separate marker stops the reset from repeating; later manual changes are preserved. Original Merkato files are not edited. The previous files can be restored manually from backup.
- Default chart count is **2**, with a wider 312px sidebar, larger card minimums, readable 2-column category filter rows, and a **MANAGE LIST** dialog that frees up space for the market list.
- Watchlist categories: ALL, STOCKS, CURRENCIES, CRYPTO and SAVED; categories are now based on real instrument type, not ticker suffix assumptions.
- Added 7 free, keyless daily FX reference-rate histories through the documented **Frankfurter v2 `/v2/rates?from=...&base=...&quotes=...` API**. FX charts are **close-only**; there are no artificial OHLC wicks or trade prices. D / W / M supported, not 1–240-minute intervals.
- Added BNB and Dogecoin with labelled aggregate crypto history from CoinGecko / CoinPaprika (not guaranteed exchange venue candles). BTC, ETH, SOL and XRP keep Coinbase/Kraken exchange routes and their aggregate fallbacks.
- Added an explicit **Additional Stock Sources** control in Manage List: opting in to Yahoo/Nasdaq website fallbacks may help where Stooq has no data. Unofficial sources may be refused and can change; no bypasses of rate limits or access controls are attempted. Opt-in persists.
- The HOME market carousel reads the same new list after the one-time migration.

## Curated watchlist
**Crypto:** BTC-USD, ETH-USD, SOL-USD, XRP-USD, BNB-USD, DOGE-USD.  
**Currencies (daily official/reference):** FX:EURUSD, FX:USDJPY, FX:GBPUSD, FX:AUDUSD, FX:USDCAD, FX:USDCHF, FX:USDAUD.  
**Stocks/ETFs:** AAPL, MSFT, NVDA, AMZN, TSLA, META, GOOG, AMD, SPY, QQQ.

These are drawn from the Yahoo Finance most-watched list, CoinGecko market-cap leaders, and BIS/RBA FX turnover analysis. Source URLs:
- https://finance.yahoo.com/research-hub/screener/most_watched_tickers
- https://www.coingecko.com/
- https://www.bis.org/media-releases/20250930-global-fx-trading-hits-96-trillion-day-april-2025-and-otc-interest-rate-derivatives-surge-79
- https://www.rba.gov.au/media-releases/2025/mr-25-28-tables.html
- https://frankfurter.dev/

## Provider truthfulness and limitations
- Frankfurter publishes reference FX rates at least daily; it **does not provide real-time forex trading candles**.
- CoinGecko and CoinPaprika provide aggregate market histories, not Coinbase/Kraken venue candles.
- Popular stocks are *not* proof of stock-data entitlement. Stooq may block CSV access, and documented US stock APIs may require a key, trial or paid subscription. No code can guarantee every asset has a free current feed. Unavailable stock charts remain clearly marked and should not be mistaken for valid quotes.
- Live requests could not be verified in this build environment. All provider tests use injected fixtures. The user should assess actual stock and FX connectivity on their own network.
- The original standalone AUGURSPEX hosted TradingView widgets and real-time WebSockets are still not integrated into the native Tk suite workspace.

## Verification
- Curated-market identity, 1-time settings+watchlist backups, idempotency, genuine FX timestamps, provider routes and no-fake-interval checks: **PASS**.
- Tk market category filters, default two-chart layout, compact-window sidebar, toggle persistence: **PASS**.
- Native-tab, readability, source-details and prior chart fixes: **PASS in focused test runs**.
- Older exhaustive 0.4.8.5 geometry test depends on a sourced-only default and a sidebar 'BACK TO HOME' button; it is **not a valid full pass for these intentionally changed UI defaults**. New focused geometry and category checks cover the new behavior. The EIDOLITH conversion engine is unchanged and the full historical FFmpeg suite was not rerun for this point release.
- Physical Windows 11 and Linux Mint machines: **not tested**.
- Package ZIP integrity, release inventory, extraction, executable Linux launcher: checked at packaging time.
