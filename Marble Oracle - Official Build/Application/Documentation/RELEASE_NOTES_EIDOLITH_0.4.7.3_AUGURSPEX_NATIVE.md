# Marble Oracle — EIDOLITH 0.4.7.3 / AUGURSPEX Native Workspace

**Base:** EIDOLITH 0.4.7.2 (AUGURSPEX 1.2.0; HOME Market Pulse).  
**Target:** Windows 11 and Linux Mint (portable, no new dependencies).

## Change requested

The top-navigation **AUGURSPEX** tab is now a **native embedded Tk workspace** inside the Marble Oracle CRT window. Clicking it **does not launch a browser, standalone AUGURSPEX process, or localhost server**. It behaves like the native EIDOLITH, Oggcultist, and Touch Type tabs. HOME stays intact, and Escape / Back to Home close the workspace.

The workspace draws its own market charts using AUGURSPEX's original `MarketRouter`/public OHLC providers. It loads and saves the **same** `~/.config/augurspex/settings.json` and `watchlist.json` through the original `core.py` functions (Windows follows the original AUGURSPEX user home logic). Existing market names, favorites, chart slots, and saved workspaces carry over. Edits to the watchlist are reflected in HOME's rotating chart on its normal reload interval.

### Native UI

- Uses Marble Oracle's selected **GRADE palette**, CRT background, Uberata Clear typography, borders and accent colours. Follows subsequent GRADE changes.
- Watchlist search and filters (all, favourites, crypto, stocks), selection, add/remove ticker, favourite toggle and locally persisted choices.
- Layouts **1, 2, 4, 6, 9**; chart styles **candles/line**; periods **1, 5, 15, 60, 240, D, W, M**.
- Independent chart slots, active slot highlighting; **Overview, Healthcare, Crypto** workspaces and settings persistence.
- Asynchronous HTTP history requests off the Tk UI thread; every displayed graph uses actual provider-supplied OHLC data. Stale/cached price data and provider/date labels are shown if available, never generated or guessed.
- Supports `--no-network` / `--no-markets` by suppressing network fetching and showing **NETWORK DISABLED**.
- Scrollable watchlist, fixed bottom buttons, and responsive charts in the existing CRT aperture; on tab switching, existing charts/settings persist.
- New `oracle_augurspex_tab.py` implementation. The original standalone AUGURSPEX files are retained in the source bundle, but its browser launcher is no longer invoked by the Marble Oracle tab.

### Important compatibility differences

This is a **native Tk chart workspace**, not Chromium embedded inside Tk. TradingView-hosted interactive widgets and the old browser dashboard's real-time WebSocket trade tape have **not** been transplanted into the native panel. Native charts show historical OHLC from AUGURSPEX's existing public provider pipeline (some are EOD/delayed, and some instruments have no available feed). The standalone web assets remain bundled for reference/compatibility, but clicking the suite tab does not open them. Do not label these graphs live or claim feature-perfect parity with the original browser application. No API key or login is introduced.

## Preserved

- Six top-level suite tabs and the existing HOME AUGURSPEX rotating Market Pulse chart.
- News runner and fixed Bitcoin/gold price tape remain removed.
- EIDOLITH queue, FFmpeg pipeline, conversion profiles, embedded media player, Oggcultist, Passphrase, Touch Type, CRT, fonts, images, and native Linux/Windows file-selection behavior are unchanged.
- Older AUGURSPEX server and JS sources remain in the package; independent rollback is possible using the prior 0.4.7.2 archive.

## Regression results (this build)

- `xvfb-run -a python3 Tests/test_augurspex_native_tab.py`: **PASS** (native widgets, back-end fake-router history, cross-tab persistence, layout/style, saved watchlist and slots, add ticker, retheme, Escape closes, no browser launcher call).
- `xvfb-run -a python3 Tests/test_tab_layout.py`: **PASS** in default, retro and flat.
- `xvfb-run -a python3 Tests/test_eidolith_workspaces.py`: **PASS**.
- `xvfb-run -a python3 Tests/test_augurspex_home_gui.py`: **PASS** across GRADE layouts.
- `xvfb-run -a python3 Tests/test_no_news_or_markets.py`: **PASS**.
- `python3 -m unittest discover -s Tests -p test_augurspex_home_carousel.py`: **4/4 PASS**.
- `python3 -m unittest discover -s Tests -p test_augurspex_integration.py`: **4/4 PASS** (the retained standalone component).
- `xvfb-run -a python3 Tests/test_eidolith_native_file_dialogs.py`: **PASS**.
- Python compilation of changed modules: **PASS**.
- `Tests/test_eidolith_queue_reliability.py`: **NOT COMPLETED** (long full FFmpeg regression exceeded the available test window); conversion source is unchanged.

**Not verified:** actual external market provider responses on live networks, real stock exchange pricing, operating on physical Windows/Linux Mint machines, GPU encoding or full historical FFmpeg regression. Unit/GUI tests used Xvfb on Linux and offline/fake market data where stated.

## Run

Extract the whole zip. Launch `START MARBLE ORACLE - WINDOWS.vbs` on Windows or `START MARBLE ORACLE - LINUX.sh` on Linux. Select **AUGURSPEX** in the top menu. Choose a ticker from the watchlist and assign it to any active chart slot; changes persist locally. Press Escape or Back to Home to return to HOME.

GitHub: https://github.com/igotbrainrot-stack/MARBLE-ORACLE  
The ZIP is a **local** release; it has not been pushed to GitHub.
