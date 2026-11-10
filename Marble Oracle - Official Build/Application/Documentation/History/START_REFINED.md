# Marble Oracle — refined release

Extract the whole ZIP; keep `Marble_Oracle_App/` alongside the launchers.

**Linux Mint:** Install Python 3, Tkinter, and Pillow (Pillow is needed for rune imagery). On Mint, `sudo apt install python3 python3-tk python3-pil python3-pil.imagetk` generally supplies these. Run `install_linux_desktop.sh` once in a terminal, then launch **Marble Oracle** from the application menu without a terminal. Or run `./Marble_Oracle_Linux.sh` for diagnostics.

**Windows 11:** Install Python 3 with Tkinter and Pillow. Double-click `Marble_Oracle.pyw`; if the Python `.pyw` file association is unavailable, use `Launch_Marble_Oracle.vbs` on a system with the Python Windows launcher (`pyw`) installed. Normal `.pyw`/VBS launches do not leave a console window. `Marble_Oracle.bat` is for troubleshooting only.

**Test:** From the application directory, run `python3 test_refinement.py`. On a Linux GUI/display run `python3 Marble_Oracle_App/oracle_bootstrap.py --selftest --no-bezel --os-frame --no-network` from inside `Marble_Oracle_App`.

See `REFINEMENT_CHANGELOG.md` for changes and limitations. Previous help documents and functionality remain included.
