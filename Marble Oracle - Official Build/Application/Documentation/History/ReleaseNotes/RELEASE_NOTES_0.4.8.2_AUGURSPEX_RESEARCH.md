# Marble Oracle 0.4.8.2 — AUGURSPEX research-led provider update

13 November 2026

## Added
- Official/documented optional-key Massive US stock OHLC, J-Quants v2 Japanese history, KRX date-scoped Korean daily history, and FRED daily US index closing levels.
- No-key CoinGecko and CoinPaprika crypto USD aggregated closing-price fallbacks. These remain **close-only line charts** and are identified as **aggregated multi-exchange**, not Coinbase or Kraken OHLC.
- Same-symbol/period concurrent request coalescing across shared suite router.
- Fresh cache selection by actual latest observation with provider priority for ties.
- Provider capability routing that excludes daily-only sources from intraday requests.
- Explicit exchange access required status when no eligible provider/entitlement is configured.
- A source setup/research report with source documentation and credentials guide.

## Preserved
- Original Coinbase/Kraken venues, Stooq, Twelve Data, Alpha Vantage, Frankfurter reference FX, optional Yahoo/Nasdaq/Naver legacy handlers.
- Existing AUGURSPEX UI/visibility, 0.4.8.1 larger text, 0.4.8.0 grid and outlined candles/lines, chart periods, watchlists, workspaces, six-tab order, HOME rotation and EIDOLITH converter.

## Changed behaviour and tradeoff
- Unofficial personal-use website history fallbacks are now **OFF by default** because they are not supported API services. Use `AUGURSPEX_ALLOW_UNOFFICIAL_SOURCES=1` only after checking provider terms. This may make some unlicensed ASX/international listings show `EXCHANGE ACCESS REQUIRED` where old versions repeatedly requested blocked unofficial endpoints.
- Authenticated providers require user-owned keys and appropriate permissions. No credentials are included.
- The latest history is the most recently **observed** provider datum, not a claim of real-time trading data.

## Tests
- Controlled provider fixtures; FRED close-only; KRX code filtering; J-Quants v2 headers; Massive same-ticker rejection; CoinGecko/CoinPaprika aggregate line-only; concurrency coalescing.
- Prior focused provider, interval, native GUI, chart/readability, HOME carousel tests run successfully.
- Live external-provider responses and physical Windows/Linux Mint operation were not tested in this environment.
- Existing long no-news GUI batch has an intermittent timeout in this headless environment and is not counted as a pass for this release.

See `AUGURSPEX_PROVIDER_RESEARCH_IMPLEMENTATION_0.4.8.2.md` for capability matrix, opt-in setup and references.
