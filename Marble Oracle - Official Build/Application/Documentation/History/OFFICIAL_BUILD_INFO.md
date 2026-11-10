# Marble Oracle — Official build layout

This is a reorganized distribution of the full Marble Oracle + embedded Oggcultist 2.0.6 suite. Application UI and functionality have not been changed.

## Launch
- **Windows 11:** Double-click `START MARBLE ORACLE - WINDOWS.vbs` in the parent release folder. Requires Python 3 with Tkinter and the Windows Python launcher (`pyw`). No console window is intended.
- **Linux Mint:** Right-click `START MARBLE ORACLE - LINUX.sh` in the parent release folder and choose **Run** or **Execute**. (Some file managers ask whether to run an executable script.) Requires `python3` and `python3-tk`. The launcher starts the graphical application, not a terminal.
- To install a Linux application-menu shortcut, run `Application/install_linux_desktop.sh` once from a terminal. It targets this extracted location, so move the folder before installing.

Both launchers resolve paths relative to their location; keep the `Application` folder beside them and extract the full ZIP.

## Source and documentation
The bundled application code, fonts, assets, tests, and development notes are retained inside `Application/`. The embedded Oggcultist 2.0.6 source is under `Application/Marble_Oracle_App/Oggcultist/`.

## Packaging notes
This is the full Python source distribution, **not** a compiled `.exe` or `.AppImage`.
