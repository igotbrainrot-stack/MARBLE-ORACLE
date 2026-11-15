# Official Marble Oracle Launcher — Requirements Check and Startup Repair

## What changed

The two files at the top of the release are the **only intended application entry points**:

- `START MARBLE ORACLE - LINUX.sh`
- `START MARBLE ORACLE - WINDOWS.vbs`

Each launches `Application/Runtime/launch_suite.pyw` rather than bypassing setup.
The launcher checks installed Python libraries and FFmpeg, FFprobe and FFplay **every time**. Prior successful setup state cannot bypass these checks.

When requirements are missing, the setup window lists them and offers **INSTALL REQUIREMENTS**; installation requires the user's explicit consent. It installs Python packages into a private environment, not the system Python. Linux graphical administrator approval is needed for Linux system packages. If Python or Tkinter is missing on Linux, the top-level launcher first offers to install `python3`, `python3-tk`, and `python3-venv` with graphical authorisation when available.

When prerequisites are ready:

- On the first launch, select **START APPLICATION**.
- After choosing **INSTALL REQUIREMENTS**, the verified application starts automatically.
- On future launches, requirements are checked again and the application starts automatically if nothing is missing.

## Preventing silent exits

The setup window remains open until the **actual Marble Oracle GUI** reports that its initial frame has been created. A subprocess spawn alone is not treated as successful startup. An early crash or a startup that fails to report readiness is shown as an error, with the path to a persistent log.

Logs: Linux `~/.local/share/MarbleOracleSuite/<suite-id>/startup.log`; Windows `%LOCALAPPDATA%/MarbleOracleSuite/<suite-id>/startup.log`. Python requirement installation logs are kept in the same directory as `requirements-install.log`. This design does not swallow errors silently.

## Requirements

- Windows: Python 3 with Tkinter must be available before the setup GUI can run; the windowless launcher uses `pyw` or `pythonw` and does not open a Command Prompt.
- Linux Mint: graphical desktop session; Python and Tkinter are offered for installation through a GUI dialog when the OS provides Zenity/KDialog/xmessage and a compatible package manager/polkit agent. If GUI authorisation is unavailable, install `python3 python3-tk python3-venv` through Linux Mint Software Manager before running the launcher.
- Internet access is needed for package installation. FFmpeg installation on Linux depends on available apt/PackageKit and permission. No packages are installed without consent.

## Files and layout

No Marble Oracle, Passphrase, Oggcultist 2.0.6, Tarot, Rune, font, or panel layouts were removed or redesigned. The official release retains only the two top-level launchers and an `Application/` directory containing Runtime, Documentation, and Tests.

## Checks performed

- `python3 Application/Runtime/launch_suite.pyw --probe`
- `python3 Application/Tests/test_media_setup.py`
- `xvfb-run -a python3 Application/Tests/test_launch_gate.py`
- `xvfb-run -a python3 Application/Runtime/Marble_Oracle_App/marble_oracle.py --selftest`
- `xvfb-run -a python3 Application/Tests/test_tab_layout.py`
- `xvfb-run -a python3 Application/Tests/test_ogg206_embedded.py`
- Real child GUI readiness signal tested under a Linux virtual display.

Real Linux Mint system package installation, Windows 11 GUI launching, and media conversion/audio on physical devices remain unverified. Do not regard simulated package-manager tests as proof of live installations.
