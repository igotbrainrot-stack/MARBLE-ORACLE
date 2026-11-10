# First-run requirements setup

The two top-level launchers run `Application/Runtime/launch_suite.pyw` before starting the full program. On every launch the requirements are inspected before starting the program. On first launch the GUI offers installation where needed; later launches also stop for installation when previously installed requirements are missing. The setup does not treat launching a child as success until the application reports its window is ready. To reopen, run `Application/Runtime/launch_suite.pyw --show-setup` using Python 3.

The installer uses `venv` to create a private Python environment in the user's data directory, not the system Python. It installs Pillow (including `ImageTk`), Mutagen, and, on Linux, Jeepney. Users can elect optional CRT and soundcard extras. Python downloads require internet access and pip. No packages install unless the user clicks Install Requirements. If the existing Python packages are already sufficient, clicking Install Requirements skips recreating Python environments and proceeds directly to the selected media tools.

FFmpeg, FFprobe, and FFplay are separate media tools. On Windows, with consent, the installer uses Oggcultist's checksum-verified downloader for FFmpeg binaries. On Linux Mint, after the user clicks INSTALL REQUIREMENTS and leaves the media-tools checkbox selected, the installer tries a graphical administrator authorisation using Polkit (`pkexec`) to install the system `ffmpeg` package. The package supplies `ffmpeg`, `ffprobe` and `ffplay`. If `pkexec` is unavailable, PackageKit (`pkcon`) is used when available. If no graphical package installer is available, or the administrator declines, setup shows a precise error and the Software Manager / `sudo apt install ffmpeg` alternative. No system package is installed silently or without the user pressing Install Requirements.

If `tkinter` is absent, the Linux launch script displays a desktop dialog if Zenity/KDialog is present, or explains the apt command if invoked in a terminal. Python 3/Tkinter must exist before a Tk setup dialog can run. Incomplete package installation creates a log in the user's local data folder; the GUI reports the path.

The Oggcultist tab is bundled under `Application/Marble_Oracle_App/Oggcultist/`. A portable Tk PNG adapter supports Linux installations where `PIL.ImageTk` is not present. The private virtual environment avoids the broken system package where pip installation is possible.

## Development checks

* `python3 Application/launch_suite.pyw --probe` prints a dependency check without showing the GUI.
* `xvfb-run -a python3 Application/test_ogg206_embedded.py` validates the embedded pages.
* `xvfb-run -a python3 Application/Marble_Oracle_App/marble_oracle.py --selftest` runs the Oracle smoke tests.

Native Windows 11 and physical Linux Mint tests are still needed.
