# AUGURSPEX 1.2.0 — MARBLE ORACLE SUITE module

A **self-contained**, **no-login** AUGURSPEX dashboard that can be incorporated into **MARBLE ORACLE EIDOLITH 0.4.7** (Linux Mint and Windows).

This is an **integration module**, not another Debian installer. It includes the AUGURSPEX Python/HTML/CSS/JS application, a suite navigation bridge, a validated installer, backup and rollback tools, and a manifest.

## Installation into an existing MARBLE ORACLE Suite

1. Close MARBLE ORACLE and AUGURSPEX.
2. Extract this ZIP anywhere, e.g. `~/Downloads/AUGURSPEX_MARBLE_ORACLE_MODULE/`.
3. Open a terminal in the extracted module directory.
4. Supply the location of your **Marble Oracle - Official Build** folder:

   ```bash
   python3 install_into_suite.py "/path/to/Marble Oracle - Official Build"
   ```

   Windows PowerShell equivalent: `py install_into_suite.py "C:\path\to\Marble Oracle - Official Build"`.

5. Verify:

   ```bash
   python3 "/path/to/Marble Oracle - Official Build/Application/Tools/verify_release.py"
   ```

6. Start MARBLE ORACLE using its **existing** `START MARBLE ORACLE - LINUX.sh` or Windows starter. Click **AUGURSPEX** in the top navigation to open the market observatory.

The installer **refuses incompatible or previously modified source** rather than replacing or rewriting a different build. It does not require administrator privileges, pip installs or a standalone `.deb`.

## Removing the integration

```bash
python3 uninstall_from_suite.py "/path/to/Marble Oracle - Official Build"
```

Then run the suite's original verifier. This restores source, inventory and manifest from in-suite backups. Existing user market lists remain at `~/.config/augurspex/` and are not deleted.

## Preserved functionality

MARBLE ORACLE's original HOME, Oggcultist, EIDOLITH, Passphrase, Touch Type, Tarot/Rune/ASCII, protected media archives, fonts, launcher, theme and CRT remain unchanged except for two small **opt-in** navigation/dispatch patches. AUGURSPEX reads its own local market list (with optional one-time Merkato import), preserving your original suite state.

AUGURSPEX includes up to nine graphs, CSV/JSON/TXT watchlist import/export, independent Kraken/Coinbase public crypto sources, and public historical/hosted stock charting. It does **not** promise real-time ASX/TSE/KRX prices; those may be delayed or unavailable due to exchange licensing.

## How it is integrated

See [`SUITE_INTEGRATION.md`](SUITE_INTEGRATION.md) for exact paths, storage and verification. `MODULE_MANIFEST.json` lists version, origin, integration points and payload hashes. `tests/` includes a source-patching/rollback test. The suite-ready **complete release** is provided separately when available; this smaller module ZIP can be applied to any compatible copy of the official 0.4.7 release.

## No-login conditions

No account, personal ID, API key or linked brokerage is required. The application server binds only to `127.0.0.1` on the user computer. Public third-party feeds still observe network requests and may enforce their own rate limits and licensing rules.
