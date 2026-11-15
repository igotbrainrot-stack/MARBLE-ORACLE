# AUGURSPEX 0.4.9.0 — source-provider review and 23-market routing matrix

**Research date:** 14 November 2026 (Australia/Sydney). **Scope:** entire 0.4.8.9 starter watchlist, 10 US stocks/ETFs, 7 FX pairs and 6 cryptocurrencies.

## What this release actually fixes

- Three independent **keyless historical reference providers** for all seven FX pairs: Frankfurter v2, the ECB SDMX API and the Bank of Canada Valet API. FX cross rates are calculated only from observations on the **same date**; missing dates are not filled and no OHLC values are invented.
- A new independent, keyless Gemini Exchange USD candle fallback for BTC, ETH, SOL, XRP and DOGE. Coinbase and Kraken are retained; Dogecoin now gets venue-specific historical pairs before aggregators.
- An additional CoinDesk Data/CryptoCompare USD aggregated price-history route covering BNB and the other five curated coins. Access may require a personal key or be rejected at the provider; the application does not circumvent it. Converted BTC/other-currency proxy routes are explicitly rejected.
- Optional **Financial Modeling Prep** and **Alpaca IEX** adapters for US shares and ETFs, in addition to existing Twelve Data, Massive and Alpha Vantage support. Both require personal credentials and plan permission. Alpaca IEX is **not** consolidated US market data.
- SOURCE DETAILS now displays what providers are actually configured and which additional options require keys/opt-in. HTTP quota failures remain subject to cooldown.

## The 23 markets — three researched sources per market

| Market | Primary | Secondary | Tertiary | Important condition |
|---|---|---|---|---|
| `BTC-USD` | Coinbase Exchange | Kraken | Gemini Exchange | Venue-specific USD spot candles; aggregators provide fourth/fifth fallbacks. |
| `ETH-USD` | Coinbase Exchange | Kraken | Gemini Exchange | Venue-specific USD spot candles; aggregators provide fourth/fifth fallbacks. |
| `SOL-USD` | Coinbase Exchange | Kraken | Gemini Exchange | Venue-specific USD spot candles; aggregators provide fourth/fifth fallbacks. |
| `XRP-USD` | Coinbase Exchange | Kraken | Gemini Exchange | Venue-specific USD spot candles; aggregators provide fourth/fifth fallbacks. |
| `BNB-USD` | CoinGecko | CoinPaprika | CoinDesk Data / CryptoCompare | USD aggregate, not executable venue quote. CryptoCompare may require a key. |
| `DOGE-USD` | Coinbase Exchange | Kraken | Gemini Exchange | Venue-specific USD spot candles; aggregators provide fourth/fifth fallbacks. |
| `FX:EURUSD` | Frankfurter v2 | ECB SDMX | Bank of Canada Valet | All three are **daily reference**, not live FX trading quotes; no keys. |
| `FX:USDJPY` | Frankfurter v2 | ECB SDMX | Bank of Canada Valet | All three are **daily reference**, not live FX trading quotes; no keys. |
| `FX:GBPUSD` | Frankfurter v2 | ECB SDMX | Bank of Canada Valet | All three are **daily reference**, not live FX trading quotes; no keys. |
| `FX:AUDUSD` | Frankfurter v2 | ECB SDMX | Bank of Canada Valet | All three are **daily reference**, not live FX trading quotes; no keys. |
| `FX:USDCAD` | Frankfurter v2 | ECB SDMX | Bank of Canada Valet | All three are **daily reference**, not live FX trading quotes; no keys. |
| `FX:USDCHF` | Frankfurter v2 | ECB SDMX | Bank of Canada Valet | All three are **daily reference**, not live FX trading quotes; no keys. |
| `FX:USDAUD` | Frankfurter v2 | ECB SDMX | Bank of Canada Valet | All three are **daily reference**, not live FX trading quotes; no keys. |
| `AAPL` | Twelve Data (key) | Massive (key) | Alpaca IEX (key) | Additional FMP/Alpha Vantage (keys), Stooq (keyless best effort), opt-in unofficial Nasdaq/Yahoo. |
| `MSFT` | Twelve Data (key) | Massive (key) | Alpaca IEX (key) | Additional FMP/Alpha Vantage (keys), Stooq (keyless best effort), opt-in unofficial Nasdaq/Yahoo. |
| `NVDA` | Twelve Data (key) | Massive (key) | Alpaca IEX (key) | Additional FMP/Alpha Vantage (keys), Stooq (keyless best effort), opt-in unofficial Nasdaq/Yahoo. |
| `AMZN` | Twelve Data (key) | Massive (key) | Alpaca IEX (key) | Additional FMP/Alpha Vantage (keys), Stooq (keyless best effort), opt-in unofficial Nasdaq/Yahoo. |
| `TSLA` | Twelve Data (key) | Massive (key) | Alpaca IEX (key) | Additional FMP/Alpha Vantage (keys), Stooq (keyless best effort), opt-in unofficial Nasdaq/Yahoo. |
| `META` | Twelve Data (key) | Massive (key) | Alpaca IEX (key) | Additional FMP/Alpha Vantage (keys), Stooq (keyless best effort), opt-in unofficial Nasdaq/Yahoo. |
| `GOOG` | Twelve Data (key) | Massive (key) | Alpaca IEX (key) | Additional FMP/Alpha Vantage (keys), Stooq (keyless best effort), opt-in unofficial Nasdaq/Yahoo. |
| `AMD` | Twelve Data (key) | Massive (key) | Alpaca IEX (key) | Additional FMP/Alpha Vantage (keys), Stooq (keyless best effort), opt-in unofficial Nasdaq/Yahoo. |
| `SPY` | Twelve Data (key) | Massive (key) | Alpaca IEX (key) | Additional FMP/Alpha Vantage (keys), Stooq (keyless best effort), opt-in unofficial Nasdaq/Yahoo. |
| `QQQ` | Twelve Data (key) | Massive (key) | Alpaca IEX (key) | Additional FMP/Alpha Vantage (keys), Stooq (keyless best effort), opt-in unofficial Nasdaq/Yahoo. |

**Meaning of tiers:** These are independent *candidate* sources, not three verified live connections on this machine. Actual automatic order is the code in `MarketRouter._routes`; sources without a configured personal key are **skipped**. No credentials are included in the ZIP.

## Why some US stock charts can still be blank

The application cannot legally create market-data entitlements for the user. Without configured credentials, the built-in US stock auto route is primarily **Stooq**, which can serve empty CSVs/HTML challenges or rate-limit automated access. The previously added unofficial Yahoo Finance/Nasdaq website feeds remain **user-controlled opt-in**. Adding more names of providers does not make their paid/licensed content unrestricted.

For better EOD coverage on a personal/free plan, choose a provider with compatible free historical US bars and configure its environment variable before launching Marble Oracle. Free accounts, rate limits, data depth and permitted uses vary. Examples:

- `AUGURSPEX_MASSIVE_KEY` — US daily stock/ETF aggregates, Stocks Basic free tier: EOD, 2 years, **5 requests/minute**, after midnight New York time for previous day.
- `AUGURSPEX_TWELVE_DATA_KEY` — covered stocks/ETFs/FX subject to market entitlements; free Basic lists **8 credits/minute, 800/day**.
- `AUGURSPEX_ALPACA_KEY_ID` and `AUGURSPEX_ALPACA_SECRET_KEY` — IEX-sourced US equities/ETF historical bars; requires individual Alpaca access. **IEX-only data are not US consolidated SIP quotes.**
- `AUGURSPEX_FMP_KEY` — Financial Modeling Prep stable `/historical-price-eod/full` endpoint. Available access depends on plan. No credentials are bundled.
- `AUGURSPEX_ALPHA_VANTAGE_KEY` — free tier roughly **25 requests/day**; DAILY compact returns 100 records. Not live stock data.
- `AUGURSPEX_ALLOW_UNOFFICIAL_SOURCES=1` — optional, personal-use best-effort Yahoo and Nasdaq *website* fallback. They are **not** officially supported developer APIs and may block automation; leave off when disallowed or unwanted.

For cryptos, exchange USD quotes differ from multi-exchange market averages. A USD stablecoin quote (USDT/USDC) is **not** silently treated as US dollars. For FX, weekends/public holidays produce normal missing reference dates; the app does not invent weekend observations.

## Integration notes and safety

- All HTTP calls run in provider workers, not the Tk render loop; the native tab and HOME share a router, cache and cooldown state.
- New sources use HTTPS on fixed hosts; no arbitrary user URL injection; Alpaca credentials are sent as headers. Personal keys in query strings, where provider specifications require them, are redacted before surfaced error messages.
- Invalid numbers and impossible OHLC relationships are rejected; close-only FX history is flagged, not turned into supposedly observed candlesticks.
- Provider fallback happens only after a real failure, never as a merge of different providers or substitute ticker. A cached result must retain source/observation metadata.
- Auth/429/403 failures cause cooldown. Do not reduce delay simply to make a dashboard populate.
- Source summary distinguishes **configured candidate**, **historical observation** and **verified live feed**. The latter has not been tested on the user’s machine.

## Verified docs / research links

1. Frankfurter v2 FX daily history: https://frankfurter.dev/
2. ECB official API series keys and CSV: https://data.ecb.europa.eu/help/api/data-examples
3. Bank of Canada Valet API: https://www.bankofcanada.ca/valet/docs/ and reference methodology https://www.bankofcanada.ca/rates/exchange/background-information-on-foreign-exchange-rates/
4. Gemini public candles/symbol list: https://developer.gemini.com/trading/rest-api/market-data
5. Coinbase product candles: https://docs.cdp.coinbase.com/exchange/reference/exchangerestapi_getproductcandles
6. Kraken OHLC 720 recent rows: https://support.kraken.com/au/articles/360047124832-downloadable-historical-ohlcvt-open-high-low-close-volume-trades-data
7. CoinPaprika keyless history limits: https://coinpaprika.com/api/historical-data
8. CoinGecko free historical plan limits: https://www.coingecko.com/learn/coingecko-api-troubleshooting-guide-and-solutions
9. CoinDesk/CryptoCompare historical endpoints and API keys: https://min-api.cryptocompare.com/documentation and https://www.cryptocompare.com/coins/guides/how-to-use-our-api/
10. Massive stock plans: https://massive.com/stocks and https://massive.com/knowledge-base/article/on-the-free-basic-plan-when-can-i-pull-the-previous-trading-days-data
11. Twelve Data Basic plan: https://twelvedata.com/pricing-business
12. Alpaca historical stock bars and IEX: https://docs.alpaca.markets/us/reference/stockbars and https://alpaca.markets/support/data-provider-alpaca
13. Financial Modeling Prep stable historical EOD: https://site.financialmodelingprep.com/developer/docs/stable/historical-price-eod-full
14. Alpha Vantage docs and free limit: https://www.alphavantage.co/documentation/ and https://www.alphavantage.co/support/api-key/

## How to verify on Linux Mint

Run `python3 Application/Tests/test_augurspex_triple_source_0490.py` for deterministic simulated-provider tests; open AUGURSPEX -> SOURCE DETAILS and check the actual configured order. In a network-connected installation, check representative AAPL, BTC-USD, BNB-USD, FX:EURUSD, FX:USDJPY, and compare their source/date badges. Do not assume every endpoint works until actual responses are received.
