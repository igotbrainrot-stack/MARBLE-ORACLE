# Marble Oracle / EIDOLITH 0.4.7 — Dashboard simplification

Date: 11 November 2026. Based on the user-supplied Claude release EIDOLITH 0.4.7, archive SHA256 55e36728e25f3bb1c3925cb01f7f0dd13b386ca5eacbbd50d9b303bc04554a2a.

Changes requested: remove the bottom scrolling news runner and remove the complete market panel showing Bitcoin/gold/silver.

Implementation:
- Home dashboard layouts now contain only arch, lex, trans and cards. Freed market area is given to the remaining panels, including every GRADE preset.
- News feed worker and market-feed worker are disabled at construction, to avoid unnecessary network traffic.
- News marquee rendering and market refresh calls are removed from the update loop.
- Both legacy and modern footers now show only transient application messages; the scrolling news area is gone.
- Existing EIDOLITH conversion, queue, presets, and media files remain untouched.
- Removed features are not deleted from support modules; those modules remain as archival code for compatibility.

Tests: test_tab_layout.py (default, retro, flat) passed under Xvfb; test_no_news_or_markets.py passed under Xvfb. Python compileall passed. Full GUI/hardware encoding across target Windows/Linux machines not verified.

GitHub: https://github.com/igotbrainrot-stack/MARBLE-ORACLE
This locally modified package has NOT been pushed to the repository.
