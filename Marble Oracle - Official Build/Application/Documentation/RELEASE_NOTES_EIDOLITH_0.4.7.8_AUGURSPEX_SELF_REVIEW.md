# Marble Oracle — 0.4.7.8 AUGURSPEX self-review

**Date:** 13 November 2026  
**Baseline:** 0.4.7.7 Multi-Source release (no replacement of the EIDOLITH conversion engine)  
**Platforms targeted:** Windows 11 and Linux Mint

## Research and limitations

This release considers documented APIs and exchange rights, in addition to examining the existing source. There is no unrestricted, reliable, licensed *free* historical feed for all stocks in the Australian, Japanese, Korean and US watchlists. Website endpoints (Yahoo, Nasdaq, Stooq, Naver) are best-effort. TradingView's documented embeddable charts are web iframe/components, not a free OHLC API for a native Tk Canvas.

Sources reviewed (13 Nov 2026):
- https://www.alphavantage.co/documentation/ — documented history/time-series API; optional key required; free quotas apply.
- https://www.alphavantage.co/support/api-key/ — free request frequency and regulated quote freshness.
- https://twelvedata.com/docs/ai/ai-data-assistant — official `time_series` response fields, interval parameters and exchange metadata.
- https://twelvedata.com/pricing — free and commercial plan boundaries.
- https://support.twelvedata.com/en/articles/5332349-commercial-and-personal-usage — ASX exchange-data entitlement restrictions.
- https://twelvedata.com/exchanges — market-level plan/exchange details, including XASX and XJPX.
- https://en.tradingview.com/widget-docs/getting-started/ — hosted iframe and web component widget types.
- https://support.kraken.com/au/articles/360047124832-downloadable-historical-ohlcvt-open-high-low-close-volume-trades-data — REST limits and real historical OHLCVT.

## Implemented fixes

### 1. Shared provider load management
HOME's rotating chart and native AUGURSPEX's multi-chart workspace now reuse one market router per local cache path. The provider cache, cooldown and request-spacing state is shared *within the same Marble Oracle process*, avoiding duplicate streams of requests to the same restricted source. A separately launched browser companion remains an independent process.

### 2. Optional documented exchange-data route
Added a Twelve Data `/time_series` parser, enabled only if the environment variable `AUGURSPEX_TWELVE_DATA_KEY` is present. This is an additional fallback, not a default requirement. It validates the response ticker and explicit exchange MIC (`XASX`, `XJPX`, `XKRX`, `XKOS`, `XLON`) where provided, and refuses a mismatched listing. Uses real returned OHLC, timestamps and currency, with interval-specific requests. API errors or entitlement rejections remain visible, and rate-limit/cooldown handling applies. **This does not make ASX data free.** An exchange subscription may be required.

Existing documented optional Alpha Vantage integration and the unkeyed public data sources remain in place. No API keys are bundled, logged, persisted in app settings or included in diagnostics.

### 3. Cache freshness and honest status
- Do not accept a future-dated cache record as a fresh quote after clock drift or bad data.
- Validate disk-cache structure before using it. FX-rate records still remain cacheable.
- If the HOME chart's subsequent request fails, its most recent successful chart is marked **stale** (not fresh) and the source failure remains visible. Old history older than seven days is withheld from HOME.
- Preserve the existing seven-day stale cutoff for provider chart caches; no simulated candles are generated.

### 4. Native diagnostic panel
AUGURSPEX now includes **SOURCE DETAILS** next to REFRESH. It shows the selected ticker, interval, provider routing order, source, currency, last observation, cache status and any failing source attempts. When the chart is unavailable, it reports the reason and approximate automatic retry delay. Original LONG provider failure details are now retained in memory rather than being clipped after 180 characters. API-key strings are redacted from provider errors.

### 5. Accuracy and documentation
- Retained the date/price axes, thick chart lines, local Oggcultist textures and all existing suite tabs.
- Updated the README to remove an obsolete claim that the deleted news runner still fetches RSS, and documented the native AUGURSPEX workflow.
- Updated the browser companion's legacy provider-directory description to distinguish unkeyed public feeds from *optional* API-key providers.

## Regression scope
- The new tests verify controlled Twelve Data response parsing, explicit MIC mapping, wrong-exchange refusal, credential denial, no-key behavior, multi-source fallback, future-cache exclusion, FX cache integrity, credential redaction, HOME stale labels, shared cooldowns and the native SOURCE DETAILS button.
- Existing AUGURSPEX provider routing, interval-integrity, in-tab history charts, HOME carousel, six-tab navigation, EIDOLITH workspace, original texture checks and offline companion API security tests are rerun.
- Packaging integrity is checked against a regenerated file inventory and after clean extraction.

**What is not guaranteed:** live provider availability on a particular user's network, exchange entitlements, current-price licensing, physical Windows/Linux operation, or NVIDIA/Intel/AMD hardware acceleration. These require real environment testing. No claim of flawless access is made.
