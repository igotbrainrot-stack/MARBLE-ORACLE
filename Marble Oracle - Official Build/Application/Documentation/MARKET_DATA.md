# Market data in AUGURSPEX

AUGURSPEX draws **history that a named source returned**. It is not a live quote terminal, and it never draws a value no source supplied.

## What you get without any key

Checked live on 15 November 2026 (`PROVIDER_PROBE.md`): all 23 starter markets returned validated daily history. That check predates the sources added in 0.4.9.4 (Bitstamp, Bitfinex, the second Coinbase host, the Binance mirror, Tiingo, EODHD, data.go.kr and Stooq with a key). Those are tested against recorded reply shapes only and have **not** been checked live; run `Tools/probe_providers.py` from your own connection to see what they answer.

| Markets | Sources tried, in order | What the data is |
|---|---|---|
| Crypto (BTC, ETH, SOL, XRP, DOGE, BNB) | Coinbase, Kraken, Bitstamp, Gemini, Bitfinex, Coinbase's second host, then CoinGecko and CoinPaprika, and last the Binance market-data mirror | Exchange candles in US dollars for one venue, or a cross-exchange aggregate (close only). Labelled as such. Binance prices are in **USDT** (Tether, a dollar-pegged token), not dollars: it is used only when no dollar source answered, and the chart then says `Binance BTC/USDT` and `USDT`. BNB has no dollar exchange candles here, so its candles and intraday come from Binance in USDT. |
| Currency pairs | Frankfurter, European Central Bank, Bank of Canada | Daily **reference rates**, one value a day. Not tradable quotes, no intraday. |
| US stocks and ETFs | Strasmore public SQL demo, then Stooq | End-of-day bars, about one year, daily/weekly/monthly only. The demo may throttle or change its terms. Since about March 2026 Stooq answers requests without a key with a "get your key" page; the chart reports that as a key being needed, and the key is free (below). |

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
| `AUGURSPEX_STOOQ_KEY` | Daily candles for US, Australian and Tokyo listings and the three US indices. Free: open `stooq.com/q/d/?s=aapl.us&get_apikey` in a browser, pass the captcha, copy the key. With a key Stooq no longer needs the unofficial-sources switch. |
| `AUGURSPEX_EODHD_KEY` | Daily candles for US, Australian, Tokyo and Korean listings and the three US indices. Free plan: about one year of history and 20 requests a day; which exchanges the free plan really includes is not confirmed. |
| `AUGURSPEX_TIINGO_KEY` | US stock and ETF daily candles. Free key; Tiingo's terms are for personal, internal use. |
| `AUGURSPEX_DATA_GO_KR_KEY` | Korean listings, daily, from the Korean government data portal (Financial Services Commission). Non-commercial licence; published the next business day. The request format was written from the published specification and is unverified. |
| `AUGURSPEX_TWELVE_DATA_KEY` | US stocks on the free plan. Australian, Japanese and Korean markets need a paid plan. |
| `AUGURSPEX_ALPHA_VANTAGE_KEY`, `AUGURSPEX_FMP_KEY`, `AUGURSPEX_MASSIVE_KEY` | US stock history. |
| `AUGURSPEX_ALPACA_KEY_ID` + `AUGURSPEX_ALPACA_SECRET_KEY` | US stock history (both are required). |
| `AUGURSPEX_JQUANTS_KEY` | Tokyo listings. |
| `AUGURSPEX_KRX_KEY` | Korean listings (daily). |
| `AUGURSPEX_FRED_KEY` | S&P 500, Nasdaq Composite and Dow index levels. |
| `AUGURSPEX_CRYPTOCOMPARE_KEY` | CoinDesk Data crypto aggregates (it rejects keyless requests). |
| `AUGURSPEX_ALLOW_UNOFFICIAL_SOURCES=1` | Opt-in only: the unofficial Yahoo, Nasdaq.com and Naver web endpoints. Off by default because they are undocumented and their terms restrict automated use. |

A key that the provider rejects starts the same cool-down as a rate limit, so it is not re-sent on every refresh. Entering a key in the dialog ends those waits at once.

There is no free official source for Australian (ASX) prices; Stooq and EODHD are third-party redistributors.

## Your own data

**MANAGE LIST → IMPORT STOCK CSV** reads a daily history file for a stock; the **CSV** button in the header exports what the charts are showing (close-only observations leave open, high and low empty rather than repeating the close). Imported history is kept in your settings folder, used ahead of network sources for that symbol, and removed with REMOVE IMPORTED CSV FOR ACTIVE STOCK. Exported text that begins with `=`, `+`, `-` or `@` is prefixed with an apostrophe so a spreadsheet does not run it as a formula.

## Limits to keep in mind

- Free sources are best-effort. One day's successful probe is not a guarantee for tomorrow or for your network.
- Nothing here is a licensed real-time feed, and nothing here grants a right to redistribute the data.
- Derived figures describe the past. They are not predictions or advice.
