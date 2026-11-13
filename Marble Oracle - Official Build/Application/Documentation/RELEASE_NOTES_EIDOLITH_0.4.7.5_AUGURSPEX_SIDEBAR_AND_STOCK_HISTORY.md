# Marble Oracle 0.4.7.5 — AUGURSPEX layout and stock-history repair

Date: 13 November 2026

This point release was prompted by a user screenshot showing an unreadably narrow AUGURSPEX sidebar and missing history for NVDA and COH.AX. It is based on 0.4.7.4. No EIDOLITH conversion code or user preferences were intentionally changed.

## Changes

- Fixed AUGURSPEX sidebar: a fixed-width 262-pixel Tk shell now holds the Oggcultist textured panel, avoiding ttk image-element width collapse. The market list, controls and labels have room to display.
- Fixed active navigation highlight: AUGURSPEX is highlighted while its native tab is active; HOME is highlighted when returning.
- Stock-history fallback: the native AUGURSPEX and HOME chart backends now try **Stooq, then Yahoo Finance Chart (unofficial)** when the first provider returns no usable history. The same exact ticker is requested; no other asset is substituted. Korea continues to prefer Naver, with Yahoo as fallback. Crypto continues to prefer Coinbase then Kraken.
- Expanded supported fallback symbol mapping for U.S. stocks, Australian (.AX), Japanese (.T), Korean (.KS/.KQ), U.K. (.L), and indices (^GSPC, ^IXIC, etc.).
- Charts always label their provider, currency and observation date. Cached provider responses are reused to prevent repeated rejected downloads.
- Added parser and user-interface regression tests for the issue seen in the screenshot.

## Privacy and provider limitations

**Change from AUGURSPEX 1.2's original no-Yahoo design:** a fallback now makes requests to Yahoo Finance's undocumented public chart endpoint. Yahoo and Stooq can see the requesting IP address and requested ticker; no account, key, password or brokerage access is used. The Yahoo endpoint is not officially supported, can change, throttle or block access, and has no guaranteed financial-data rights. Charts are for reference, not trading decisions. The source shown in the UI will always identify Yahoo when used.

It is not possible to guarantee that all 25+ markets will deliver public history. On provider failure, the chart still shows an honest unavailable message rather than generated or substituted prices. Historical stock data may be delayed or end-of-day.

## Tests executed

- `xvfb-run -a python Tests/test_augurspex_stock_fallback.py`: pass (stock-symbol mapping; mock Stooq N/D -> Yahoo history; cache; wrong-ticker refusal; 262px sidebar and tab highlight).
- `xvfb-run -a python Tests/test_augurspex_native_tab.py`: pass.
- `xvfb-run -a python Tests/test_no_news_or_markets.py`: pass.
- `python Tests/test_augurspex_provider_mappings.py`: pass.
- `python Tests/test_augurspex_home_carousel.py`: 4/4 pass.
- `xvfb-run -a python Tests/test_tab_layout.py`: default, retro and flat pass.
- `python Tests/test_augurspex_integration.py`: 4/4 pass.
- `xvfb-run -a python Tests/test_augurspex_home_gui.py`: extended redraw test timed out in this environment, **not claimed as passed**.
- Release inventory verification, zip integrity and Linux launcher permission: completed during packaging.

Real Yahoo/Stooq network responses on the user's desktop, hardware encoders, and physical Windows/Linux Mint GUI operation remain **unverified**. The network tests use controlled simulated provider responses and do not establish live availability.

GitHub: https://github.com/igotbrainrot-stack/MARBLE-ORACLE (this ZIP has not been uploaded).
