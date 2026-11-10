# Marble Oracle — Original Passphrase Layout + Home Navigation

## Changes
- Replaced the embedded Passphrase Studio two-column, sidebar-based layout with the original horizontal five-card layout from user-supplied `Marble Passphrase(3).zip` (`app/marble_passphrase.py`).
- Preserved the original header, five reroll cards, full-phrase field, lower action row, dice toggle, and status lines.
- Applied Oracle's existing Oggcultist Ember colours and Uberata Clear typography; the passphrase generator engine and existing Oracle layout remain intact.
- Added a visible `BACK TO ORACLE` button on the Passphrase header. It calls Oracle's existing overlay-close mechanism to return to the five-panel home screen without opening a second window.
- Retained Escape-to-close, K-to-open, and the existing navigation controls.
- Added regression checks verifying five part cards, Back to Oracle returns to home, and the tab can be reopened and closed with Escape.

## Verification
- `python3 -m py_compile marble_passphrase_tab.py marble_oracle.py`: passed.
- Linux virtual-display GUI self-test (normal, retro and CRT V2): passed.
- Native Windows and physical Linux Mint visual QA: not performed in this environment.

## Launch
- Windows: extract package and launch `Marble_Oracle.pyw` (Python/Tkinter required).
- Linux Mint: extract package and use `install_linux_desktop.sh` for the graphical desktop launcher (Python 3 and python3-tk required).

## Note
The user-provided standalone Passphrase app's original arrangement is the design reference. Its separate Windows Python runtime was not incorporated because this is the embedded Oracle implementation.
