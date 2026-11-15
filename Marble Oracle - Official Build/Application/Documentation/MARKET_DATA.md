# Market data in AUGURSPEX

AUGURSPEX draws **history that a named source returned**. It is not a live quote terminal, and it never draws a value no source supplied.

## What you get without any key

Checked live on 15 November 2026 (`PROVIDER_PROBE.md`): all 23 starter markets returned validated daily history.

| Markets | Sources tried, in order | What the data is |
|---|---|---|
| Crypto (BTC, ETH, SOL, XRP, DOGE; BNB from the aggregators only) | Coinbase, Kraken, Gemini, then CoinGecko and CoinPaprika | Exchange candles for one venue, or a cross-exchange aggregate (close only). Labelled as such. |
| Currency pairs | Frankfurter, European Central Bank, Bank of Canada | Daily **reference rates**, one value a day. Not tradable quotes, no intraday. |
| US stocks and ETFs | Strasmore public SQL demo, then Stooq | End-of-day bars, about one year, daily/weekly/monthly only. The demo may throttle or change its terms; Stooq often blocks automated requests. |

Australian, Japanese and Korean listings and the US indices have **no** no-key route. They show DATA SOURCE SETUP NEEDED until you add a key (below) or import a CSV.

## What the status words mean

Each failure keeps its cause from the source to the screen. SOURCE DETAILS lists every source tried and what each one said.

| On the chart | Meaning | What to do |
|---|---|---|
| (a chart, no badge) | History whose newest observation is recent for its interval. | Nothing. |
| STALE *date* | History exists but its newest observation is older than expected (8 days for daily stocks and currencies, 3 for crypto). | REFRESH; if it stays, the source has stopped updating that listing. |
| DATE UNVERIFIED | The newest observation has no usable date, or a date in the future. The history is drawn but is not called current. | Open SOURCE DETAILS. |
| CACHED | Shown from the local cache because the source did not answer just now. The observation date is on the chart. | REFRESH later. |
| DATA SOURCE LIMITED | The source rate-limited or refused the request, or the app is waiting out a cool-down before asking again. | Wait for the time shown in SOURCE DETAILS. |
| API KEY OR PLAN REJECTED | A key was sent and the provider said no (wrong key, or the plan does not include that market). | Check the key and its entitlements. |
| DATA SOURCE SETUP NEEDED | No source is available for that listing without your own key. | Add a key or import a CSV. |
| NETWORK ISSUE | The request never reached the provider (DNS, connection, timeout). | Check the connection. |
| NETWORK DISABLED | The suite was started with `--no-network`. | Start it normally. |
| LISTING NOT SUPPORTED | The source does not carry that symbol or interval. | Choose another interval or source. |
| NO HISTORY FROM PROVIDER | The source answered with no rows for that symbol. | Check the symbol. |
| PROVIDER REPLY REJECTED | The reply failed validation (wrong symbol echoed back, impossible values, a web page instead of data). It is discarded, not drawn. | Report it; the source changed. |
| PROVIDER FAULT | The provider returned a server error. | Try later. |
| AUTO-FILLED | With **CHARTS N**, a slot whose saved market has no data shows another watchlist market that has, under this label and its own name. Your saved choice is kept. | Nothing. |

## Rules the code keeps

- A row with a missing, zero or negative price is not an observation and is dropped.
- A reply for a different symbol than the one asked for is rejected.
- Close-only sources are drawn as a line; candles are offered only where the source supplied open, high, low and close.
- Weekly and monthly bars are built only from real daily bars.
- SIGNALS (SMA20, SMA50, RSI14, change over the range) use the plotted closes only, name the dates they span, and say "not enough observations" rather than estimating.
- Filings, short interest, positioning and macro series are not prices and are never used as chart data.

## Optional API keys

Set these in the operating system's environment before starting, or enter them for the session with **MANAGE LIST → CONNECT API KEY**. They are never written to disk and must not be committed.

| Variable | Adds |
|---|---|
| `AUGURSPEX_TWELVE_DATA_KEY` | Stocks worldwide by exchange code (Australian, Japanese and Korean markets usually need a paid add-on). |
| `AUGURSPEX_ALPHA_VANTAGE_KEY`, `AUGURSPEX_FMP_KEY`, `AUGURSPEX_MASSIVE_KEY` | US stock history. |
| `AUGURSPEX_ALPACA_KEY_ID` + `AUGURSPEX_ALPACA_SECRET_KEY` | US stock history (both are required). |
| `AUGURSPEX_JQUANTS_KEY` | Tokyo listings. |
| `AUGURSPEX_KRX_KEY` | Korean listings (daily). |
| `AUGURSPEX_FRED_KEY` | S&P 500, Nasdaq Composite and Dow index levels. |
| `AUGURSPEX_CRYPTOCOMPARE_KEY` | CoinDesk Data crypto aggregates (it rejects keyless requests). |
| `AUGURSPEX_ALLOW_UNOFFICIAL_SOURCES=1` | Opt-in only: the unofficial Yahoo, Nasdaq.com and Naver web endpoints. Off by default because they are undocumented and their terms restrict automated use. |

A key that the provider rejects starts the same cool-down as a rate limit, so it is not re-sent on every refresh.

## Your own data

**MANAGE LIST → IMPORT STOCK CSV** reads a daily history file for a stock; the **CSV** button in the header exports what the charts are showing (close-only observations leave open, high and low empty rather than repeating the close). Imported history is kept in your settings folder, used ahead of network sources for that symbol, and removed with REMOVE IMPORTED CSV FOR ACTIVE STOCK. Exported text that begins with `=`, `+`, `-` or `@` is prefixed with an apostrophe so a spreadsheet does not run it as a formula.

## Limits to keep in mind

- Free sources are best-effort. One day's successful probe is not a guarantee for tomorrow or for your network.
- Nothing here is a licensed real-time feed, and nothing here grants a right to redistribute the data.
- Derived figures describe the past. They are not predictions or advice.
