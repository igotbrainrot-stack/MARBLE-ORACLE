# Marble Oracle — EIDOLITH 0.4.7.4 / AUGURSPEX Native Workspace

Date: 2026-11-13

## Summary
This patch keeps AUGURSPEX integrated as a native suite tab and makes two targeted improvements requested after the 0.4.7.3 release:

1. **Darker AUGURSPEX background using the Oggcultist look**
2. **Reduced `NOHISTORY` failures for supported major-market indices, plus clearer unsupported/error messaging**

## Changes

### 1) Darker Oggcultist-style AUGURSPEX workspace
- AUGURSPEX now uses a darker base palette inside the native suite tab.
- The left rail, main workspace, header/footer strips and option rows now use the same tiled Oggcultist texture surface family already bundled in the suite.
- Chart canvases now render over an Oggcultist sunken texture tile instead of a flat fill.
- Accent colours still follow the active Marble Oracle theme, but the background treatment is now closer to Oggcultist's darker textured identity.

### 2) `NOHISTORY` / unsupported-market improvements
- Added Stooq alias fallback attempts for major US index symbols:
  - `^GSPC`
  - `^IXIC`
  - `^DJI`
- The provider now tries multiple known symbol aliases when necessary instead of failing after a single mapping.
- Empty chart states are more explicit:
  - `LISTING NOT SUPPORTED`
  - `NO HISTORY FROM PROVIDER`
  - `NETWORK ISSUE`
  - `NETWORK DISABLED`

This does **not** substitute a different market silently. If a listing is still unsupported, the UI now says so clearly.

## Files changed
- `Application/Runtime/Marble_Oracle_App/oracle_augurspex_tab.py`
- `Application/Runtime/Marble_Oracle_App/Augurspex/augurspex/providers.py`
- `Application/Tests/test_augurspex_provider_mappings.py`
- `Application/Documentation/BUILD_MANIFEST.json`
- `Application/Documentation/FILE_INVENTORY.json`

## Verification run for this patch
Executed on the edited release copy:

- `python3 Tests/test_augurspex_provider_mappings.py` → PASS
- `xvfb-run -a python3 Tests/test_augurspex_native_tab.py` → PASS
- `xvfb-run -a python3 Tests/test_no_news_or_markets.py` → PASS
- `python3 Tests/test_augurspex_home_carousel.py` → PASS
- `python3 Application/Tools/verify_release.py` → PASS

## Notes
- Physical Windows 11 and physical Linux Mint were **not** re-verified for this point patch.
- The AUGURSPEX native tab remains local-first and account-free.
- Hosted TradingView widgets / standalone-browser behaviour remain outside this native Tk patch.
