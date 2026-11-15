# AUGURSPEX live provider probe - interval D
Run 2026-11-15 05:19 UTC on Linux (runnervm8axu0). No API keys were configured. No prices are recorded here.

**23 of 23 starter markets returned validated history from at least one no-key source.**

## Per market

| Market | Type | Chart without a key | First source that answered | Also answered | Failed (kind) | Newest observation |
|---|---|---|---|---|---|---|
| BTC-USD | Crypto | yes | coinbase | kraken, gemini, coingecko, coinpaprika | cryptocompare (auth) | 2026-11-15T05:14:50 |
| ETH-USD | Crypto | yes | coinbase | kraken, gemini, coingecko, coinpaprika | cryptocompare (cooldown) | 2026-11-15T05:15:10 |
| SOL-USD | Crypto | yes | coinbase | kraken, gemini, coingecko, coinpaprika | cryptocompare (cooldown) | 2026-11-15T05:15:40 |
| XRP-USD | Crypto | yes | coinbase | kraken, gemini, coingecko, coinpaprika | cryptocompare (cooldown) | 2026-11-15T05:15:20 |
| BNB-USD | Crypto | yes | coingecko | coinpaprika | cryptocompare (cooldown) | 2026-11-15T05:15:40 |
| DOGE-USD | Crypto | yes | coinbase | kraken, gemini, coingecko, coinpaprika | cryptocompare (cooldown) | 2026-11-15T05:16:10 |
| FX:EURUSD | FX | yes | frankfurter-history | boc-fx | ecb-fx (network) | 2026-11-15T00:00:00 |
| FX:USDJPY | FX | yes | frankfurter-history | ecb-fx, boc-fx | - | 2026-11-15T00:00:00 |
| FX:GBPUSD | FX | yes | frankfurter-history | boc-fx | ecb-fx (network) | 2026-11-15T00:00:00 |
| FX:AUDUSD | FX | yes | frankfurter-history | boc-fx | ecb-fx (network) | 2026-11-15T00:00:00 |
| FX:USDCAD | FX | yes | frankfurter-history | ecb-fx, boc-fx | - | 2026-11-15T00:00:00 |
| FX:USDCHF | FX | yes | frankfurter-history | boc-fx | ecb-fx (network) | 2026-11-15T00:00:00 |
| FX:USDAUD | FX | yes | frankfurter-history | boc-fx | ecb-fx (network) | 2026-11-15T00:00:00 |
| AAPL | Stocks | yes | strasmore | - | stooq (rate_limited) | 2026-11-13T00:00:00 |
| MSFT | Stocks | yes | strasmore | - | stooq (cooldown) | 2026-11-13T00:00:00 |
| NVDA | Stocks | yes | strasmore | - | stooq (cooldown) | 2026-11-13T00:00:00 |
| AMZN | Stocks | yes | strasmore | - | stooq (cooldown) | 2026-11-13T00:00:00 |
| TSLA | Stocks | yes | strasmore | - | stooq (cooldown) | 2026-11-13T00:00:00 |
| META | Stocks | yes | strasmore | - | stooq (cooldown) | 2026-11-13T00:00:00 |
| GOOG | Stocks | yes | strasmore | - | stooq (cooldown) | 2026-11-13T00:00:00 |
| AMD | Stocks | yes | strasmore | - | stooq (cooldown) | 2026-11-13T00:00:00 |
| SPY | Stocks | yes | strasmore | - | stooq (cooldown) | 2026-11-13T00:00:00 |
| QQQ | Stocks | yes | strasmore | - | stooq (cooldown) | 2026-11-13T00:00:00 |

## Per source

| Source | Markets asked | Answered | Failure kinds |
|---|---|---|---|
| Coinbase Exchange (`coinbase`) | 5 | 5 | - |
| Kraken (`kraken`) | 5 | 5 | - |
| Gemini Exchange (`gemini`) | 5 | 5 | - |
| CoinGecko aggregated prices (`coingecko`) | 6 | 6 | - |
| CoinPaprika aggregated prices (`coinpaprika`) | 6 | 6 | - |
| CoinDesk Data / CryptoCompare (`cryptocompare`) | 6 | 0 | auth x1, cooldown x5 |
| Frankfurter daily FX references (`frankfurter-history`) | 7 | 7 | - |
| European Central Bank SDMX (`ecb-fx`) | 7 | 2 | network x5 |
| Bank of Canada Valet (`boc-fx`) | 7 | 7 | - |
| Strasmore SQL public demo (`strasmore`) | 10 | 10 | - |
| Stooq (`stooq`) | 10 | 0 | rate_limited x1, cooldown x9 |

A source that answered here can still refuse a different network or a later request. Treat this as evidence for the date above, not as a guarantee.
##[group]Run actions/upload-artifact@v4

## How to repeat it

```bash
python3 Application/Tools/probe_providers.py --markdown probe.md
```

or run the `tests` workflow by hand with `probe_providers` ticked. Replace this file with the new result and its date. The run above came from a GitHub-hosted runner in a data centre; a home connection can be treated differently by the same provider (Stooq in particular).
