# Marble Oracle 0.4.9.2 — AUGURSPEX PDF Research Integration

## Added

1. Strasmore public SQL demo as an additional **no-API-key** US stock/ETF daily history source, tried before Stooq (and after the user's configured documented API providers). It may populate some stocks that previously displayed `STOCK FEED LIMITED` without claiming a guaranteed feed.
2. Accurate `SIGNALS` tool in the native AUGURSPEX tab: actual last close, retrieved-range change, SMA20, SMA50, RSI14, observation date and source; no fake prices.
3. Both supplied source PDFs preserved in `Application/Documentation/Research/` and an audit note explaining which candidates can and cannot populate charts.
4. Tests for valid/mismatched stock identities, list/object JSON responses, weekly/monthly aggregation, source fallback, calculations, and GUI controls.

## Preserved

- 23-market starter watchlist and saved user config
- Existing fiat/crypto sources, alternate API-key routes, live-history caching and honest provider error descriptions
- Native AUGURSPEX, Market Atlas, HOME carousel, Oggcultist texture, EIDOLITH video functionality and other suite tabs
- Default refusal to enable unofficial Yahoo/Nasdaq website scraping

## Limitations

Strasmore demo is limited (currently around one year and 500 rows, short query timeouts). It is not live SIP or a data-redistribution license. The provider or third-party terms can change and the demo may throttle or reject requests. Stooq can also reject automated downloads. Public/regulatory SEC, FINRA and macro records do not provide traded OHLC for the user's selected stock and are not misleadingly used as substitutes.

The integration was tested with controlled responses, not verified live stock market retrieval from this environment. Physical Windows 11/Linux Mint desktop testing is still required.

Reference: `Application/Documentation/AUGURSPEX_PDF_RESEARCH_INTEGRATION_0.4.9.2.md`.