# Marble Oracle — startup crash repair

## Problem

The graphical requirements window could close immediately when Oracle wrote its `startup-ready` marker, even if the Oracle process then exited. Its "ready" check was only a one-frame acknowledgement, not a stability test. Separately, the Marble Oracle rendering loop counted every rendering exception for the lifetime of the process and closed after 51, including isolated/transient errors separated by successful frames.

## Changes

- Keep the requirements window running for **6 seconds after Oracle reports that its GUI is ready**, monitoring the actual child process. Only finish the setup after the child remains alive for that period.
- If Oracle exits before or during verification, **keep the requirements window open** and show a graphical error containing the relevant logs. Windows normal startup remains console-free.
- Increase the initial readiness deadline from 18 to 35 seconds for slower machines.
- Stop the progress bar and cancel the requirements polling callback before closing the requirements window, avoiding Tcl callbacks against destroyed widgets.
- Count **consecutive** frame-rendering failures, not a lifetime total. Reset the counter after successful frames; capture Tk callback exceptions in `callback_error.log` and report prolonged fatal rendering failures before shutting down.
- Make the Rune animation self-test tolerate slow asset loading (15-second QA deadline instead of 5 seconds); animation playback timing is unchanged.
- Preserve the supplied layout, HOME/PASSPHRASE/OGGCULTIST tabs, media functions, fonts, and all application artwork.

## Starting

**Windows 11:** Double-click `START MARBLE ORACLE - WINDOWS.vbs` in the release root. It runs the graphical requirements manager without opening a command window.

**Linux Mint:** Use the installed application-menu entry, or the top-level `START MARBLE ORACLE - LINUX.sh`. For app-menu integration use the installer in `Application/Runtime/install_linux_desktop.sh` (once). The app-menu entry specifies `Terminal=false`.

## Diagnostic logs if a crash persists

- Windows launcher setup: `%LOCALAPPDATA%\\MarbleOracleSuite\\<installation-id>\\startup.log`
- Windows Oracle: `%LOCALAPPDATA%\\Marble_Oracle\\startup_error.log`, `error.log`, or `callback_error.log`
- Linux launcher setup: `~/.local/share/MarbleOracleSuite/<installation-id>/startup.log`
- Linux Oracle: `~/.local/state/Marble_Oracle/startup_error.log`, `error.log`, or `callback_error.log`

The requirements dialog now shows the log paths after an early failure. Please include the latest error log and your Linux Mint / Windows version if the app still closes, since platform-specific failures cannot be diagnosed from Linux virtual-display tests alone.

## Test evidence (Linux virtual display)

- Verified real setup-to-Oracle process handoff and process survival beyond the 6-second monitoring window.
- Passed GUI self-test including Tarot/Rune, Passphrase and other Oracle interactions twice.
- Passed launch-gate tests including a synthetic crash **after** the ready marker.
- Passed Linux/Windows launcher static regression tests, tab-position tests, asset and settings checks, media-setup simulations, and normal/bezel display tests.
- Real Windows 11 and physical Linux Mint launch validation remain outstanding.

This is a complete application package and contains no compiled Windows executable.
