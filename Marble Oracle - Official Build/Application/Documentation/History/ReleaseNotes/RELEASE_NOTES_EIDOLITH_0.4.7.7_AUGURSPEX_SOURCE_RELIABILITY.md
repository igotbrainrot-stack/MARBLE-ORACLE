# Marble Oracle EIDOLITH 0.4.7.7 — AUGURSPEX market-data reliability

**Date:** 13 November 2026

## What changed

- Retained AUGURSPEX as a native, in-suite Tk workspace (not a browser launcher).
- Preserved Oggcultist grain textures, darker palette, chart styling, widened sidebar and the HOME rotating market pulse.
- Added an independent **Nasdaq.com website history fallback** for exact US equity/ETF symbols, with the real source clearly labelled. Nasdaq's website historical table is an undocumented endpoint and is not a guaranteed or licensed data feed.
- Added an **optional Alpha Vantage integration** for documented US equities daily, weekly and monthly history, only when `AUGURSPEX_ALPHA_VANTAGE_KEY` exists in the process environment. No key is bundled, printed, saved in settings, or required to run the suite. Free-tier limits apply.
- Preserved Yahoo Finance (unofficial), Stooq, Naver Finance, Coinbase Exchange and Kraken history routes.
- Provider routing is now explicit: US stock/ETF day/week/month -> Yahoo, Nasdaq, optional Alpha Vantage, Stooq; AU/JP/other supported exact listings -> Yahoo and Stooq; KRX/KOSDAQ -> Naver and Yahoo; crypto -> Coinbase and Kraken.
- **No wrong interval substitution:** intraday equity history does not fall back to daily-only Stooq/Nasdaq/Naver or free Alpha Vantage. Weekly/monthly OHLC is aggregated from actual daily candles where required, and the Coinbase four-hour option now aggregates hourly data into four-hour buckets instead of requesting six-hour candles.
- Added clearer per-chart provider diagnostics and a provider-attempt record. Respect HTTP 403/429 and quota cooldowns. Try other independent sources on failure, while preserving cached results only with explicit stale labelling and a seven-day ceiling.
- No fake prices, substitute tickers or fabricated candlesticks.

## Optional documented data source

Alpha Vantage's official API requires a personal API key. Configure it in the environment used to start the application (do not commit it to GitHub):

Linux (terminal):

    export AUGURSPEX_ALPHA_VANTAGE_KEY='YOUR_API_KEY'
    ./START\ MARBLE\ ORACLE\ -\ LINUX.sh

Windows PowerShell (in the extracted program folder):

    $env:AUGURSPEX_ALPHA_VANTAGE_KEY='YOUR_API_KEY'
    & '.\START MARBLE ORACLE - WINDOWS (if the VBS launcher is blocked).bat'

The key is optional. The program works with its keyless providers when no key is configured. Alpha Vantage is limited to **US stock symbols** in this patch to avoid inventing international exchange mappings. Alpha Vantage's free plan currently advertises 25 API requests/day. The app caches history for 12 hours to reduce usage.

## Source investigation

- **Yahoo Finance:** unofficial chart endpoint, vulnerable to HTTP 403/429; no contractual service guarantee.
- **Stooq:** downloadable historical CSV; may return HTML/N-D/quota responses to automated clients.
- **Nasdaq.com:** historical web endpoint covers US symbols; best effort, susceptible to website restrictions.
- **Alpha Vantage:** documented and key-authenticated; free tier is rate-limited, no key provided by the suite.
- **Naver Finance:** unofficial Korean market history; if blocked, exact Yahoo listing is the alternative.
- **TradingView hosted widgets:** browser-rendered JavaScript with exchange licensing requirements; they are *not* a direct native Tk historical-data API. The standalone original browser module remains bundled, but the native tab does not open it.
- **ASX:** the older public history endpoint began using automated-access challenges; therefore it is not treated as a reliable new source.

Sources verified by web research (accessed 13 November 2026):
- https://www.nasdaq.com/market-activity/quotes/historical
- https://www.tradingview.com/widget-docs/widgets/charts/advanced-chart/
- https://www.alphavantage.co/documentation/
- https://www.alphavantage.co/support/api-key/
- https://financialliterature.com/data/stooq/
- https://forums.whirlpool.net.au/archive/9z8jypz9

## Tests executed

- `python3 Tests/test_augurspex_multisource_0477.py` — PASS (6 deterministic scenarios)
- `python3 Tests/test_augurspex_intervals_0477.py` — PASS
- `python3 Tests/test_augurspex_provider_mappings.py` — PASS
- `python3 Tests/test_augurspex_home_carousel.py` — PASS
- `xvfb-run -a python3 Tests/test_augurspex_chart_axes_and_history.py` — PASS
- `xvfb-run -a python3 Tests/test_augurspex_stock_fallback.py` — PASS
- `xvfb-run -a python3 Tests/test_augurspex_native_tab.py` — PASS
- `xvfb-run -a python3 Tests/test_no_news_or_markets.py` — PASS
- `xvfb-run -a python3 Tests/test_tab_layout.py` — PASS
- `xvfb-run -a python3 Tests/test_augurspex_home_gui.py` — PASS
- `python3 Tests/test_augurspex_integration.py` — PASS

These use controlled fixtures and Linux virtual display where required. **They do not verify live financial-service availability, physical Windows/Linux Mint operation, or hardware conversion acceleration.** Live services can still be blocked by providers. There is no universal unlimited free, no-key, guaranteed international equity history API.

GitHub repository: https://github.com/igotbrainrot-stack/MARBLE-ORACLE

This build has not been pushed to GitHub.
