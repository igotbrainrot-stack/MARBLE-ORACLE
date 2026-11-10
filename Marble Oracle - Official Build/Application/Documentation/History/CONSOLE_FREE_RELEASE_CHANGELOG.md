# Marble Oracle — console-free startup maintenance

## Scope

No changes were made to the HOME, PASSPHRASE or OGGCULTIST layouts, the five-panel Oracle screen, Tarot/Rune artwork, or the generator/media feature logic.

## Changes

- Confirmed the only official Windows entry point is `START MARBLE ORACLE - WINDOWS.vbs` (Windows Script Host, hidden `pyw.exe`/`pythonw.exe`), not `.bat` or a Command Prompt wrapper.
- Hardened first-run dependency checks and application subprocess startup with Windows `CREATE_NO_WINDOW` and hidden `STARTUPINFO`. All startup errors are written to the existing logs and shown in the graphical setup.
- Corrected `Application/Runtime/install_linux_desktop.sh` to create a Linux Mint `Terminal=false` application-menu shortcut pointing to the actual official requirements-checking entry point, not an obsolete inner application launcher.
- Added console-free startup regression tests and updated user instructions.

## Usage

Windows: open the top-level `START MARBLE ORACLE - WINDOWS.vbs` file. Do not use internal diagnostic `.bat` files.

Linux Mint: for a guaranteed menu shortcut without a terminal, run `Application/Runtime/install_linux_desktop.sh` once (install/setup action); thereafter open **Marble Oracle** from the Mint application menu. The top-level `.sh` can also be run directly, but some file managers choose to launch shell scripts inside terminal windows.

## Verification

- Oracle GUI self-test under Linux virtual display: passed.
- Existing startup-gate, simulated installer and tab/navigation tests: passed.
- Windows process-creation options and VBS entry-point checks: passed by code-level simulated checks.
- Linux Mint menu `.desktop` generated with `Terminal=false` from a path containing spaces: passed.

## Remaining limitations

No physical Windows 11 test was available here. Confirm with Task Manager that no Command Prompt/PowerShell window appears or remains during FFmpeg and playback operations. FFmpeg's GUI privilege prompt on Linux Mint is intentionally allowed, and is not a terminal. Python and Tkinter remain prerequisites for the first-run graphical installer.
