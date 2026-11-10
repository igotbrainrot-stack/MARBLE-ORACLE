# Marble Oracle — exclusive startup / crash monitoring repair

## Problem reported
The requirements setup and the Oracle GUI appeared together. Oracle then disappeared soon after the setup window closed.

## Changes

1. The setup window withdraws **before** starting Oracle. Both windows are no longer visible simultaneously.
2. The launcher stays alive **hidden**, monitoring the real Oracle process until it exits. It does not destroy its own Tk interpreter six seconds after Oracle is ready.
3. On Linux, Oracle is started with `start_new_session=True` so its process is independent of any desktop launcher's process group. This avoids the risk of the GUI terminating when a parent launcher ends.
4. Intentional Oracle window closing writes a private one-time exit marker. The hidden launcher then exits normally. A missing marker (even with exit code zero) is treated as an unexpected shutdown and is reported.
5. When an unexpected exit occurs, the requirements window reappears **after** Oracle has closed, with startup diagnostics. Early failures do the same.
6. No screen layouts, Tarot/Rune functionality, Passphrase features, Oggcultist media features, or font assets have been changed. No dependencies are installed automatically without the user's consent.

## Startup lifecycle

- Double-click the appropriate top-level launcher.
- The setup screen checks requirements. Missing essentials are offered for installation.
- Click `START MARBLE ORACLE`, or let a previously configured setup autostart.
- The requirements window hides first, **then** Oracle appears.
- A private background watchdog confirms readiness and monitors Oracle. It does not show a terminal or any setup UI while Oracle is operating normally.
- Close Oracle normally to exit both processes. If Oracle crashes, setup reappears and displays an error with a log location.

## Diagnostics

Launcher logs are stored in the platform-specific per-user `MarbleOracleSuite/<installation-id>` directory (Linux: `~/.local/share/MarbleOracleSuite/`, Windows: `%LOCALAPPDATA%/MarbleOracleSuite/`). The launcher shows the exact path when reporting an error. Oracle's own logs are in `~/.local/state/Marble_Oracle/` on Linux or `%LOCALAPPDATA%/Marble_Oracle/` on Windows.

## Verification

- `Application/Tests/test_exclusive_handoff.py`: all tests passed under a Linux X virtual display. Covers hidden setup during launch, late crashes, zero-status crashes, early deliberate closes, deliberate closes after handoff, and Unix process isolation.
- `Application/Tests/test_launch_gate.py`: passed.
- Oracle built-in `--selftest`: passed.
- `Application/Tests/test_tab_layout.py`: passed in normal, retro, and flat layouts.
- `Application/Tests/test_ogg206_embedded.py`: passed for seven embedded Oggcultist pages and tab lifecycle.
- **Live Linux GUI smoke test:** Oracle remained open with setup hidden for 15 seconds after readiness (more than 20 seconds total), then was terminated by the test.
- **Live graceful-close test:** X11 WM_DELETE_WINDOW closed Oracle normally and the hidden launcher exited without a crash warning.

## Limits

The exact failure on the user's physical Linux Mint desktop has not been reproduced in this testing environment. Windows 11 was not available for native testing. If an OS-specific crash continues, the startup and Oracle logs must be inspected to find the cause. No claim is made that all media hardware workflows are tested.
