# Marble Oracle 0.4.9.2 — GitHub source handover

## What was uploaded

This branch contains **384 UTF-8 source, script, test and text-documentation files** copied from the full portable Marble Oracle **0.4.9.2** release (not reconstructed from the older GitHub 0.4.8.5 sources). Paths in `Marble Oracle - Official Build/` match the application's distribution layout.

Base: `fix/augurspex-chart-layout-0485-20261113` (existing draft PR #4). This is a new review branch; no merges into `main`, no changes to earlier PR branches.

## Verified source

Full portable build: `Marble-Oracle-0.4.9.2-PDF-RESEARCH-STOCK-FEEDS-Windows-Linux.zip`

SHA-256:
`839970fe65eef4c77ec3e0edfbea6d4e4f7f501fe458158e1327719fac764945`

The portable ZIP was verified locally before import. Its complete contents consist of 471 file members; only text/code files have been committed to this GitHub branch.

A source-only ZIP can also be downloaded from the same ChatGPT conversation. Its SHA-256 is:
`107ccf2aa6c4963f2ac3d5ed6086b65bec053f3f15958cff8e8dc61c40e2e38f`

## Assets needed for a runnable build

**This GitHub source tree is not by itself a complete runnable portable distribution.** The ~108 MB full ZIP also contains media and artwork packages, e.g. `rune_consistent_flips.zip`, `rune_native_frames.zip`, `rune_flip_strips.zip`, `photo_bezel_locked.zip`, `tarot_cards.zip`, `latin_voices.zip`, Oggcultist artwork, fonts, PDF research sources and other binary resources.

The GitHub connector does not expose a GitHub Release asset-upload operation, and the portable ZIP exceeds the standard 100 MB single-repository-file limit. **The full ZIP was not uploaded to GitHub.** Download the full package and checksum from the ChatGPT conversation, verify its SHA-256, and extract locally for the complete application. Do not commit large media archives or third-party fonts into Git without checking distribution rights and a deliberate large-file strategy.

## Major current features

- AUGURSPEX 23-market starter watchlist: 10 US stocks/ETFs, 7 FX pairs, 6 crypto assets
- Provider routing and honest source/limited-data diagnostics; Strasmore public demonstration stock history as a best-effort no-key route ahead of Stooq; optional documented stock API keys and stock CSV import
- Source details, MARKET ATLAS, selectable chart count, LINE/CANDLES, history-range selector, data CSV export, keyboard observation inspection and technical SIGNALS (SMA20, SMA50, RSI14)
- Six-tab suite and the EIDOLITH converter remain in the complete portable distribution

## Validation / known limitations

- Previous release test results were based on synthetic fixtures/virtual-desktop checks, **not** proof of successful current live stock-provider access.
- Stock feeds can still return LIMITED DATA without applicable API credentials or provider access.
- The GitHub source-only tree lacks binary dependencies and cannot pass the full portable file-inventory check on its own.
- Physical Windows and Linux Mint operation must be tested locally.
- No API keys, personal caches or user settings should be committed.

## How to continue

1. Use the full portable 0.4.9.2 ZIP to run the app; use **this branch's editable source** for review and further programming.
2. Run relevant tests under `Marble Oracle - Official Build/Application/Tests` in an environment with Tk/Xvfb and optional converter dependencies installed.
3. Do not regard older 0.4.8.4/0.4.8.5 draft PR code as the most recent source.
4. Keep existing draft PRs separate; no merges were performed.
