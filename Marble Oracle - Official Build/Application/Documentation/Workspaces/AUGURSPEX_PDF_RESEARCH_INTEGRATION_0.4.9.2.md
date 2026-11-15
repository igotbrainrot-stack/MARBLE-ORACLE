# AUGURSPEX Research Integration — 0.4.9.2

## Scope and provenance

This is a targeted integration of the user-supplied research documents:

- `Research/Free No-Login Market Data Sources.pdf` (10 pages)
- `Research/Equities & Exchange Data.pdf` (4 pages)

The documents are research inputs, **not** evidence that every listed provider still offers unrestricted, reliable automated API access. The integration below is intentionally conservative and implements functionality that is usable in the existing Python/Tk desktop application without fake prices.

## New code implemented

### Strasmore public SQL demonstration (US stock and ETF history)

- Native stock routing uses **Strasmore no-key SQL demo → Stooq** when no credentials are configured, with documented optional-key feeds ahead of them when present. The unofficial Yahoo/Nasdaq website endpoints remain opt-in.
- SQL query is limited to a strictly validated same-listing ticker, the `global_markets.stocks_daily_aggs` table, a date-descending 320-row sample and the provider's built-in demo constraints.
- The provider's actual OHLCV records are parsed; malformed rows or mismatched ticker identities are discarded, and empty responses are explicit errors.
- Only `D`, `W`, and `M` are supported by this adapter. Weekly and monthly candles aggregate genuine returned **daily** observations; no minute data is represented as available.
- Currency is USD and provider is identified as Strasmore SQL public demo with delayed/EOD, one-year/500-row source limits.
- Requests share the existing per-provider cooldown, disk cache, and in-process request coalescing. 429/403 failures trigger cooldown and then Stooq fallback without rapid retries.
- The demo is for evaluation/personal research under third-party terms; **not a licensed consolidated real-time feed, unrestricted use, or redistribution right**.

Official provider docs: https://api.strasmore.com/docs and https://www.strasmore.com/blog/free-stock-api-with-curl-and-jq
Terms: https://www.strasmore.com/terms/

### Market Signals (derived values, no external feed)

A new native `SIGNALS` tool shows the actual source, observation timestamp and valid close records for the selected chart, then computes:

- the change across retrieved observations
- 20-observation simple moving average
- 50-observation simple moving average
- 14-period RSI from last 15 prices

It shows "not enough observations" where needed and never generates missing observations. Derivatives are historical descriptive measures, not predictions or investment advice. For close-only FX/crypto data, the statistics use actual recorded closes only.

## Research evaluated, not misrepresented as chart data

| Research source | Finding | Integration decision |
|---|---|---|
| SEC EDGAR submissions / companyfacts | Public filings/XBRL, not traded OHLCV | Retained in research library for later optional company-fundamentals module; not used as chart prices |
| FINRA Reg SHO / short interest | Short-volume and twice-monthly interest data, not price bars | Research library only; ingestion would need its own reporting fields and reporting date |
| CFTC Commitments of Traders | Weekly position reports | Reference only; cannot stand in for security prices |
| Treasury/World Bank/IMF | Public macro indicators at daily/monthly/yearly cadence | Reference only; cannot stand in for asset quotes |
| Fawaz Currency API, FloatRates, OpenER-API | Daily FX snapshots | Not used as historical chart substitutes; existing Frankfurter/ECB/BoC history has matching actual dated observations |
| Coinbase, Kraken, Gemini | Genuine venue-specific cryptocurrency candles | Already integrated, not duplicated |
| CoinGecko, CoinPaprika, CoinDesk Data | Cross-exchange crypto aggregates | Existing integration retains aggregate/close-only provenance |
| Yahoo Finance chart and Stooq | Free best-effort historical stock sources with automation/licensing restrictions | Stooq kept; Yahoo/Nasdaq remain opt-in; no silent scraping |
| Strasmore SQL demo | Documented keyless US stock/ETF daily OHLCV sample | **Integrated** as a new stock provider, with hard limits and provenance |

Some claims about CoinGecko's keyless Demo plan differ from the present official API-key signup guidance. We did not extend use of an undocumented/unverified endpoint to compensate.

## Independent verification limitations

Offline unit tests with controlled provider responses verify SQL ticker validation, parser shapes, candle aggregation, fallback, source identity, statistics and the native signals control. This container could not resolve external provider domains, so **live market responses were not verified**. A successful unit test is not proof that a third-party service is available to the end user.

## Tests

Run from `Application/`:

```bash
python3 -m unittest discover -s Tests -p test_augurspex_pdf_integration_0492.py -v
xvfb-run -a python3 Tests/test_augurspex_pdf_gui_0492.py
python3 Tools/verify_release.py
```

The PDFs are bundled for further research, not redistributed as current price information. Avoid treating publicly readable data as automatically licensed for republication or automated bulk redistribution.
