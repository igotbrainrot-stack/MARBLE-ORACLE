# Marble Oracle — Passphrase Studio integration

This is the full Marble Oracle application. The uploaded Marble Passphrase Studio interface replaces the original home-screen bench and canvas-only DICEKEY popup.

## Usage
- Launch Oracle normally and select **PASSPHRASE** from the existing top tab (or press **K**). On the CRT bezel, the **PASS** key opens it.
- Generate New / Copy / Swap Words / individual Reroll and Show Dice Codes all use the supplied Studio interface.
- Close by pressing **Escape**, selecting the tab again, or selecting another hardware section.
- All phrase generation stays local. The generator uses Python `secrets`, the bundled EFF word list, and keeps no phrase history.

## Implementation
- `Marble_Oracle_App/marble_passphrase_tab.py`: embedded Tk Frame adapted from the uploaded Marble Passphrase build. No second Tk root/window is created.
- `Marble_Oracle_App/oggcultist_design_system.py`: exact Ember design tokens from the supplied app.
- `Marble_Oracle_App/oracle_dicekey.py`: original cryptographic backend, with the uploaded `swap_first_two` method included; obsolete canvas Session removed.
- `Marble_Oracle_App/marble_oracle.py`: `EmbeddedPassphrase` canvas-window adapter; old home bench code removed.
- Uberata Clear is loaded by the existing application's font loader.
- Rune/Tarot modes, original five-panel view and latest bright-white ASCII artwork are carried forward unchanged.

## Tests executed on Linux virtual display
- Embedded Studio: new phrase, swap, reroll, copy-to-clipboard, Show Dice Codes.
- Oracle self-test default and --retro: PASS.
- Python compilation: PASS.
- Native Windows 11 launch / Linux Mint physical desktop: not tested here.

## Launch
Use `Marble_Oracle.pyw` on Windows with Python+Tk; on Linux Mint use `Marble_Oracle_Linux.sh` or install the desktop-menu launcher once with `install_linux_desktop.sh`.
