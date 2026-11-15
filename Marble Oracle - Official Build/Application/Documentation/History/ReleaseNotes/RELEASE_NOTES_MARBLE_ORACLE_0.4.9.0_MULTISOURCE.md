# Marble Oracle 0.4.9.0 — Multi-provider fallback audit and implementation

**Based on Marble Oracle 0.4.8.9** with the same 23-market curated watchlist and existing UI layout. This is a targeted provider update, not a claim that unrestricted licensed stock data is free.

### Added
- ECB SDMX and Bank of Canada Valet historical FX sources, after Frankfurter for every curated daily FX pair.
- Gemini public USD crypto candles for BTC/ETH/SOL/XRP/DOGE, after Coinbase and Kraken.
- CoinDesk Data/CryptoCompare aggregated USD historical crypto OHLC as a separate fallback, including BNB.
- Optional Alpaca IEX and Financial Modeling Prep US stock EOD adapters; both require your own access/key.
- SOURCE DETAILS now displays each market’s configured and unconfigured provider candidates.
- Eight new controlled provider/route tests, plus updated previous source-order assertions.

### Data integrity retained
- Never creates price points or asserts unavailable live data is current.
- FX historical rates are flagged as daily, close-only references; no intraday forex bars are invented.
- The CoinDesk aggregate is explicitly labelled as such and rejects cross-pair proxy conversion.
- Gemini only used for five independently documented USD pairs; BNB keeps aggregate USD sources.
- The personal watchlist and all existing saved settings are left unchanged.

### Restrictions / unverified items
- Actual third-party service responses could not be tested from this isolated execution environment; all new adapter tests use simulated valid/invalid responses.
- A stock can still show NO DATA without an authorized service. Documented US stock APIs require personal keys; Stooq and unofficial website feeds can block or rate limit.
- Free-tier quotas and licensing, hardware Windows/Linux Mint behavior and complete end-to-end live data remain unverified.

### Main files
- `Runtime/Marble_Oracle_App/Augurspex/augurspex/providers.py`
- `Runtime/Marble_Oracle_App/oracle_augurspex_tab.py`
- `Tests/test_augurspex_triple_source_0490.py`
- `Documentation/AUGURSPEX_0.4.9.0_TRIPLE_SOURCE_RESEARCH_AND_MARKET_MATRIX.md`

Full source references and per-ticker fallback choices are in the research document.
