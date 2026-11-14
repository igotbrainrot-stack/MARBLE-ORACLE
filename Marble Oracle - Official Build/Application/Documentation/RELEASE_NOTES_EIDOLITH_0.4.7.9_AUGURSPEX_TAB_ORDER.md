# Marble Oracle 0.4.7.9 — AUGURSPEX tab order

Date: 2026-11-13

## Change

Moved AUGURSPEX immediately to the right of EIDOLITH in Marble Oracle's main navigation. New order:

**HOME · OGGCULTIST · EIDOLITH · AUGURSPEX · PASSPHRASE · TOUCH TYPE**

No other workspace behavior, provider routing, media conversion code, textures or saved data was modified.

## Tests completed

- `xvfb-run -a python3 Application/Tests/test_tab_layout.py` — PASS (standard, retro, flat). Includes actual left-to-right hit-region assertions.
- `xvfb-run -a python3 Application/Tests/test_augurspex_native_tab.py` — PASS.
- `xvfb-run -a python3 Application/Tests/test_no_news_or_markets.py` — PASS.
- `python3 Application/Tools/verify_release.py` — PASS after inventory refresh.

Tests executed using Linux Xvfb. Physical Windows/Linux Mint desktop validation was not performed; 0.4.7.8 market-data provider limitations are unchanged.

GitHub repository: https://github.com/igotbrainrot-stack/MARBLE-ORACLE
This ZIP is packaged locally and has not been published to GitHub.
