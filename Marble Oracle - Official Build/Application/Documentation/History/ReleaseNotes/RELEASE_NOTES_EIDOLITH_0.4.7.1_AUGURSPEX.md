# Marble Oracle — EIDOLITH 0.4.7.1 + AUGURSPEX 1.2.0

**Build date:** 11 November 2026  
**Platforms packaged for:** Windows and Linux (Linux Mint target)  
**Distribution:** Portable ZIP including application source, launchers, bundled assets, and verification scripts.

## What this release changes

- Adds AUGURSPEX as the sixth Marble Oracle workspace launcher. It opens an independent localhost browser/app window, **not** an embedded Tk panel.
- Preserves the earlier 0.4.7 removals: no bottom news headline runner and no Bitcoin/gold market panel in HOME.
- Preserves native file-selection dialogs in EIDOLITH and opening existing folders with the device's default file manager (Thunar when configured on Linux, Explorer on Windows).
- Fixes AUGURSPEX repeatedly opening independent localhost services: use a private readiness file to reopen a running companion after the suite restarts or its browser window closes.
- Fixes explicitly cleared AUGURSPEX chart slots repopulating with starter symbols after reload.
- Corrects AUGURSPEX's Quit message for Windows/Linux suite users.
- Updates navigation regression tests from five to six tabs, without altering the existing five workspace implementations.
- Includes the standalone module installer and uninstaller in `Application/Tools/AUGURSPEX_Module/` for rollback. It backs up source and manifest files; it does not remove user settings/watchlists.
- Ensures Linux launcher scripts have executable permissions in the archive and removes test caches and compiled Python artifacts from distribution.

## Launch instructions

**Linux Mint:** Extract the ZIP. Run `START MARBLE ORACLE - LINUX.sh` from the `Marble Oracle - Official Build` folder. If a file manager does not offer to execute it, open a terminal in that folder and run `bash './START MARBLE ORACLE - LINUX.sh'`.

**Windows:** Extract the ZIP, then launch `START MARBLE ORACLE - WINDOWS.vbs`. If `.vbs` launching is blocked, use `START MARBLE ORACLE - WINDOWS (if the VBS launcher is blocked).bat`.

Click **AUGURSPEX** in the suite header to launch the market observatory in its own browser/app window. Click it again to reopen the dashboard. Use **Quit** inside AUGURSPEX to end its local server. The separate AUGURSPEX `.deb` is not required for this bundled module.

## Verification

From `Marble Oracle - Official Build`:

```
python3 Application/Tools/verify_release.py
python3 -m unittest discover -s Application/Tests -p 'test_augurspex_integration.py' -v
```

The local test record for this patch:

- EIDOLITH FFmpeg reliability test: **103/103 checks passed**, including failure continuation, restart recovery, cancel/retry, stream mapping, artwork, captions, naming, smart copy and Turbo AV1.
- Focused PyTest run: **9 passed**, including native file selection, market/news removal, EIDOLITH naming, speed and AUGURSPEX.
- Tk six-tab navigation: default, retro, flat, default-bezel checks passed under Xvfb; small-viewport numerical layout inspection performed.
- EIDOLITH embedded player/workspace test passed under Xvfb.
- Live localhost AUGURSPEX API smoke test: startup, bootstrap, token/origin restrictions, save/reload, Quit and startup readiness cleanup passed.
- Rollback against the packaged source/backup hashes successfully restored the prior source, manifest and inventory.
- The final release inventory and embedded asset archives are verified by `verify_release.py`.

## Limitations / outstanding manual verification

- **This distribution is reconstructed** from the supplied AUGURSPEX standalone module and the most recent accessible 0.4.7 native-file-pickers/no-news/no-markets ZIP. The separately uploaded combined `MARBLE_ORACLE_0.4.7_WITH_AUGURSPEX_1.2.0(1).zip` could not be materialized by the file service, so its exact byte-for-byte contents were not available for comparison.
- Native Windows execution and physical Linux Mint/Thunar desktop selection have not been tested in this container; actual browser, window-management and file-dialog behavior should be checked on both devices.
- NVIDIA NVENC, Intel Quick Sync and AMD AMF acceleration were not tested on real GPUs. Their failure paths were checked on the CPU-only environment.
- Internet market-feed responses, exchange credentials, TradingView availability, symbol coverage, and real-world quote freshness were not validated. Public market data can be delayed/unavailable; quotes should not be presented as financial advice.
- The full historical GUI suite exceeded its time limit; specifically affected navigation tests were updated and executed separately. No blanket assertion that every historical GUI test passes.

## Source and code continuity

The earlier 0.4.7 EIDOLITH conversion code and Oggcultist/Passphrase/Touch Type implementations are unmodified by the AUGURSPEX installer. New files are primarily the companion module, bridge, integration tests and documentation. No personal watchlist, configuration or media input file is included from the test environment.

**GitHub repository:** https://github.com/igotbrainrot-stack/MARBLE-ORACLE  
**Claude branch:** https://github.com/igotbrainrot-stack/MARBLE-ORACLE/tree/claude/eidolith-reliability  
**GitHub upload status:** This built ZIP is supplied for review and has not been pushed to GitHub.
