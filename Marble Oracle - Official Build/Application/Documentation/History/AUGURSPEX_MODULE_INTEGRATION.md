# AUGURSPEX module for MARBLE ORACLE SUITE

**Module release:** 1.2.0 · **Integration build:** 11 November 2026  
**Target:** MARBLE ORACLE EIDOLITH 0.4.7, five-tab Tk/Canvas release (Windows/Linux)

## What changes

- Registers `AUGURSPEX` as a sixth button in the suite's existing navigation, after TOUCH TYPE.
- Adds a narrow `tab_augurspex` handler in `marble_oracle.py` to call `oracle_augurspex_bridge.launch()`.
- Adds the standard-library AUGURSPEX browser app and runner inside `Application/Runtime/Marble_Oracle_App/Augurspex/`.
- Updates `BUILD_MANIFEST.json` and recalculates `FILE_INVENTORY.json`, allowing the official suite verification tool to validate the modified distribution.
- Keeps the unmodified originals inside `Augurspex/integration_backup/`, so this release can be rolled back without downloading a prior official archive.

## Window model

AUGURSPEX **opens in its own companion browser/app window**, not as an embedded Tk widget. A web engine isn't shipped inside MARBLE ORACLE's Tk Canvas, avoiding heavyweight browser dependencies and preserving the existing rendering pipeline. Click AUGURSPEX in the suite's header to open it. Repeated clicks during the same suite session don't spawn another service process. Closing MARBLE ORACLE may leave AUGURSPEX open until you close/quit it separately.

It does **not** restore the removed news ticker or old Yahoo market panel, nor alter the five existing workspace implementations. The AUGURSPEX tab is a launcher into its own financial dashboard.

## Data, logins and limitations

AUGURSPEX uses locally stored watchlists and settings in `~/.config/augurspex/` on Linux. It does not require an account, brokerage login, personal ID, API token or password; requests are made to public market feeds. Its localhost HTTP service binds `127.0.0.1`. The market data services and chart hosts can receive IP address and requested symbols. Crypto exchange trades can be live while stock chart prices may be delayed, daily, or unavailable depending on provider and exchange rights.

The module requires Python 3 and a normal browser, already present/expected in the suite's target environment. There is no need to install the separate AUGURSPEX `.deb` when using this module. Do not open the separately installed AUGURSPEX instance and the suite copy concurrently if both would write to the same settings file.

## Verification

From the **Marble Oracle - Official Build** folder:

```bash
python3 Application/Tools/verify_release.py
python3 -m py_compile Application/Runtime/Marble_Oracle_App/oracle_augurspex_bridge.py
python3 -m py_compile Application/Runtime/Marble_Oracle_App/Augurspex/run.py
```

To run the AUGURSPEX dashboard independently from the suite, for troubleshooting:

```bash
python3 Application/Runtime/Marble_Oracle_App/Augurspex/run.py
```

For a rollback, use `uninstall_from_suite.py` from the original module ZIP with the same suite folder argument. The rollback checks whether the patched source files have changed and refuses to overwrite newer edits. It does not delete watchlists or preferences.
