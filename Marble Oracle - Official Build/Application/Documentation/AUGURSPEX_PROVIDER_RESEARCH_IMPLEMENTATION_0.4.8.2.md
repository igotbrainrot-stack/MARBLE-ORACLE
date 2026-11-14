# AUGURSPEX 0.4.8.2 — Research review and implementation notes

**Reviewed 13 November 2026.** This report records changes made to the local application after reviewing the deep-research recommendation. It is not a claim that all live external feeds were verified. Source access remains subject to each provider's terms, plan, and exchange entitlements.

## Why markets could appear as DATA SOURCE LIMITED

Earlier builds relied heavily on the unofficial Yahoo Finance chart endpoint, Nasdaq.com's website history, and Stooq CSV. All can refuse automated requests, return no history, or enforce quotas. Calling more of the same sources cannot overcome an exchange's information licence. Distinguish (a) a missing route, (b) missing credentials/entitlement, (c) a provider outage or 429, (d) an unknown symbol, and (e) a delayed but valid observation.

## Implemented in 0.4.8.2

| Provider | Symbols | Credential | Data | Notes |
|---|---|---|---|---|
| Coinbase | configured BTC/ETH/SOL/XRP USD | none | venue OHLC | original retained |
| Kraken | same | none | venue OHLC | original retained |
| CoinGecko | configured BTC/ETH/SOL/XRP USD | none | aggregated close-only USD | independent fallback; not a venue price; no invented OHLC |
| CoinPaprika | same | none | aggregated close-only USD | independent fallback; interval/retention depend on free plan |
| Stooq | US daily equity best effort | none | EOD OHLC | rate-limited/unofficial; source retained |
| Massive | US stocks/ETFs | optional personal API key | EOD OHLC | documented aggregate-bars API, plan-dependent delay |
| Twelve Data | US/ASX/JPX/KRX as subscription allows | optional API key | OHLC | original adapter retained; exchange MIC required for international instruments |
| Alpha Vantage | verified US stocks | optional API key | daily/weekly/monthly OHLC | original adapter retained; 25 free calls/day |
| JPX J-Quants v2 | explicit TSE listings | optional personal API key | daily OHLC | v2 x-api-key authentication, delayed free plan; actual observation date shown |
| KRX Open API | 6-digit .KS/.KQ listings | approved API key **and** service approval | date-scoped daily OHLC | bounded 17-calendar-day lookback; no intraday coverage |
| FRED | ^GSPC / ^IXIC / ^DJI | optional API key | daily close-only index levels | FRED may carry underlying licensed data; NOT OHLC |
| Naver | KRX/KOSDAQ | optional unofficial personal-use mode | daily OHLC | retained legacy website adapter |
| Yahoo / Nasdaq.com | supported website listings | optional unofficial personal-use mode | historical | now explicitly opt-in; website endpoints are not production APIs |
| Frankfurter | reference FX | none | FX reference rate | existing rate helper preserved, not a live OHLC chart |

**Source selection:** only eligible providers are tried. When both Coinbase and Kraken fail for a recognized USD coin, an independently sourced CoinGecko USD price series and then CoinPaprika may be tried. Aggregated data are visibly labelled and rendered as lines, not venue-specific candlesticks. A crypto BTC-USDT exchange pair is **never** silently used as BTC-USD.

**Cache/traffic:** HOME and the AUGURSPEX tab continue sharing one router. Identical in-flight requests are coalesced. Per-provider pacing is applied, and fresh caches prefer the latest actual observation among available provider entries rather than merely the most recently downloaded response. Provenance, original timestamps and stale labels are retained. The native SOURCE DETAILS popup lists the eligible providers and issues.

## Personal API keys (optional)

The application never bundles credentials. To enable a source, set an environment variable *for the application process* before launching:

| Variable | Source |
|---|---|
| `AUGURSPEX_MASSIVE_KEY` | Massive personal stock-data API |
| `AUGURSPEX_TWELVE_DATA_KEY` | Twelve Data (including ASX only with appropriate add-on) |
| `AUGURSPEX_ALPHA_VANTAGE_KEY` | Alpha Vantage |
| `AUGURSPEX_JQUANTS_KEY` | J-Quants **v2**, not v1 token |
| `AUGURSPEX_KRX_KEY` | KRX approved key and approved service |
| `AUGURSPEX_FRED_KEY` | FRED indices |

Example on Linux, replace only the key locally (never submit it to ChatGPT or Git):

```bash
export AUGURSPEX_MASSIVE_KEY='YOUR_PERSONAL_KEY'
./'START MARBLE ORACLE - LINUX.sh'
```

On Windows, run the application from a shell where the variables have been set, or set them in the local user environment. They are read at request time. **No code change or bundled secret is needed.**

`AUGURSPEX_ALLOW_UNOFFICIAL_SOURCES=1` enables the existing Yahoo, Nasdaq.com, Naver and best-effort international Stooq website fallbacks for personal research; this is **OFF by default**. Respect each website's terms and applicable data rights; enabling it does not bypass an access restriction or make the feeds reliable.

## Coverage limitations and decisions

1. **ASX**: there is no guaranteed lawful, broad, current, no-key historical exchange feed for an independently distributed desktop app. Twelve Data needs XASX entitlement, or the user must configure a separately licensed vendor. Explicitly report access requirements rather than using a proxy ETF or different listing.
2. **J-Quants**: free prices can be delayed around twelve weeks; the app displays the *actual* latest observation. The v2 API uses `x-api-key`. Daily stock rows may have null OHLC for no-trade sessions and are dropped rather than invented.
3. **KRX**: the endpoint is date-scoped and keys/services need approval. The adapter currently pulls at most 17 calendar days for the D chart, so history is not a full-year reconstruction. More persistent incremental backfill can be added later.
4. **Crypto aggregate**: CoinGecko/CoinPaprika closing-price observations are not tradable quotes and may differ from Coinbase or Kraken. No fake candle wicks are generated.
5. **Yahoo/TradingView**: no hidden TradingView REST adapter, scraping of authenticated sites or access-control bypass was added. TradingView hosted widgets are display components, not a native market-data licence.
6. **FRED**: underlying stock-index series may have separate copyright limits. User-supplied keys and personal display do not grant redistributable rights.

## Primary source documentation

- Massive stocks OHLC: https://massive.com/docs/rest/stocks/aggregates/custom-bars
- J-Quants v2 daily bars and key migration: https://jpx-jquants.com/en/spec/eq-bars-daily ; https://jpx-jquants.com/en/spec/migration-v1-v2
- Official KRX services and terms: https://openapi.krx.co.kr/contents/OPP/INFO/service/OPPINFO004.cmd ; https://openapi.krx.co.kr/contents/OPP/INFO/OPPINFO005.jsp
- CoinGecko market chart: https://www.coingecko.com/learn/how-to-fetch-historical-crypto-data-with-python
- CoinPaprika historical ticks/free limits: https://coinpaprika.com/api/historical-data
- Coinbase Exchange API: https://www.coinbase.com/en-au/developer-platform/products/exchange-api
- Kraken REST rate limits: https://support.kraken.com/articles/206548367-what-are-the-api-rate-limits-
- FRED daily index series: https://fred.stlouisfed.org/docs/api/fred/series_observations.html
- ASX market vendors: https://www.asx.com.au/connectivity-and-data/information-services/vendor-and-isv-list

## Verification scope

Automated tests use controlled responses for source routing, authentication headers, symbol/exchange rejection, data parsing, aggregate price attribution, missing data and in-flight coalescing. These do **not** verify real provider access from Windows/Linux or promise every market will be covered for free.
