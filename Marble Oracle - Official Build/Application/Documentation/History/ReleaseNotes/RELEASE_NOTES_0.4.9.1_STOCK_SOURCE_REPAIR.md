# Marble Oracle 0.4.9.1 — Stock-history access and diagnostics

## User-reported issue
All ten curated US stocks (AAPL, MSFT, NVDA, AMZN, TSLA, META, GOOG, AMD, SPY, QQQ) appeared as **DATA SOURCE LIMITED** despite the prior 'triple-source' matrix. This was a real configuration shortfall: multiple providers were *implemented* but did not become eligible for requests until their personal keys were configured. On a fresh profile, the automatic stock history router has Stooq only. Stooq is best-effort and may return no valid CSV or reject downloads. The presence of three providers in release notes was not proof of three live usable sources.

## Changes
1. **Manage List → Connect API Key:** a small in-suite dialog for current-session Twelve Data, Alpha Vantage and Alpaca (ID/secret) credentials. Entries are masked, never written to Marble Oracle settings and never bundled. Additional documented sources can still be configured by the existing environment-variable mechanism. The user must obtain access to each provider directly. There is no built-in shared API key.
2. **Manage List → Import Stock CSV:** import genuine daily stock-price records directly into the selected stock's chart, using a user-owned local CSV. Accepts Date/Time, Close or Price, optional Open/High/Low/Volume; also accepts the suite's own CSV export shape. If OHLC is missing, the record is `close_only`, rendered as line data; OHLC is not invented. The importer checks embedded ticker identity if present, dates, numeric prices, 2 MB maximum size, and 7500 maximum source rows.
3. **Local-first and offline:** the selected stock's file is stored only under the user's local AUGURSPEX config `imported-history` folder (not in the application ZIP). On subsequent runs the imported symbol has a local historical-data route even when the network is disabled. It is clearly labelled `LOCAL CSV · USER IMPORT` and has a warning that currency/identity/licensing are not independently verified. Imported dates are not converted into current prices.
4. **Clear imported CSV:** a reversible Remove Imported CSV button in Manage List. Only the selected stock's imported file is deleted, with user confirmation.
5. **Stock Feed Guide:** shows exact routes currently enabled for US stocks, which credential names are configured (not their values), and why a free plan may not grant all exchange data.
6. **Clearer source diagnostics:** the app now refers users to the Stock Feed Guide and import facility instead of implying all providers are ready. Existing provider cooldowns, cache, no-fabricated-data guarantees and stored watchlist are preserved.

## How to use
Open **AUGURSPEX → MANAGE LIST**. Choose **CONNECT API KEY** if you already have a personal free-tier key, or select a stock and choose **IMPORT STOCK CSV** to chart its authentic dated price records without network access. For a provider explanation, use **STOCK FEED GUIDE / CURRENT ROUTES**. If no data is available, SOURCE DETAILS gives the attempted route and error. The import file may need refreshing over time; historic CSVs are not live quotes.

## Legitimate provider access and limitations (checked November 2026)
- Twelve Data Basic: free key/credits, access depends on exchange and plan: https://twelvedata.com/pricing
- Alpaca Basic: free IEX-only equities feed and account keys; IEX bars are not consolidated US market prices: https://docs.alpaca.markets/docs/about-market-data-api
- Alpha Vantage: free key with 25 calls per day in the standard tier: https://www.alphavantage.co/support/#api-key
- FMP Basic: key required, limited free symbols/endpoints: https://site.financialmodelingprep.com/developer/docs
- Stooq: no-key history is best effort and may be rate-limited. Not guaranteed.
- Unofficial Yahoo/Nasdaq routes remain opt-in; Yahoo's published terms restrict automated retrieval. This release does not silently enable, scrape around challenges, or bypass rate limits.

**Important:** 0.4.9.1 cannot guarantee automatic fresh stock data on a machine with no usable provider credentials or local history. Claims of 'three available sources for every stock' should be understood as a research/fallback *plan*, not a three-source uptime guarantee. External market provider availability was not tested live in this environment. A personal key or legitimate local source may be needed.

## Files changed
- `Runtime/Marble_Oracle_App/Augurspex/augurspex/providers.py`
- `Runtime/Marble_Oracle_App/oracle_augurspex_tab.py`
- `Runtime/Marble_Oracle_App/oracle_augurspex_home.py`
- `Tests/test_augurspex_stock_history_0491.py`
- `Tests/test_augurspex_stock_gui_0491.py`
- Manifest/inventory and this release note.

## Verification
- New stock history / path safety / close-only / identity / offline HOME tests: passed.
- New Tk API key dialog / CSV import GUI test under Xvfb: passed.
- AUGURSPEX native tab, GUI stock fallback, provider triple-source, HOME carousel and Market Atlas tests: passed.
- The old suite-wide FFmpeg reliability suite was not rerun in this patch; EIDOLITH source files are unchanged.
- Physical Linux Mint/Windows and real live stock feeds were not verified.
