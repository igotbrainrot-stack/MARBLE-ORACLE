# Marble Oracle — Media tools first-run setup

The suite requires **FFmpeg** (media decoding/conversion), **FFprobe** (format validation) and **FFplay** (music playback). Oggcultist does not use a package named “FFmedia” or a separate MediaInfo binary.

## How installation works

On the first launch, Marble Oracle checks each binary and offers the **Install FFmpeg + FFprobe + FFplay** checkbox (selected by default when anything is missing). The user must select **INSTALL REQUIREMENTS** before any installation begins. Existing tools are retained.

- **Linux Mint / Ubuntu:** the installer attempts `pkexec /usr/bin/apt-get install -y ffmpeg` using the operating system's graphical Polkit authentication prompt. Where that tool is absent it tries PackageKit (`pkcon --plain -y install ffmpeg`). The installer does **not** open a terminal, request passwords directly, or run `sudo` in the background. If neither graphical authorisation method exists, it explains the fallback: Linux Mint Software Manager, or `sudo apt install ffmpeg`. The OS package manager is responsible for installing the media tools and their runtime libraries.
- **Windows 11:** the installer downloads the published Gyan FFmpeg Essentials ZIP over HTTPS and validates its SHA-256 against the publisher's published digest before extracting only the missing `ffmpeg.exe`, `ffprobe.exe`, and `ffplay.exe` executables. These go to Oggcultist's private user-profile tool directory. Windows administrator rights are not required.

After an installation attempt, Marble Oracle checks all three command names again and reports a meaningful error if anything is still missing. It will not claim complete setup until the tools are visible. If the user declines permission, there is no media installation.

Python dependencies are installed separately into a private Python virtual environment with prior consent. Python 3 and Tkinter are prerequisites for displaying the setup window itself. If creating the private virtual environment fails specifically because `python3-venv` or `ensurepip` is missing, the installer requests graphical authorisation to install `python3-venv` and retries once; Software Manager remains a fallback.

## Run and troubleshooting

Launch from the official package's top-level Windows or Linux start shortcut. First-run media setup happens in the graphical first-run window. The detailed installer log is stored in the application-specific user-data folder. No personal music or libraries are modified by installing the media tools.

Tested here: command-selection and permission handling via mocked Linux package-manager calls, dependency probe, GUI setup smoke test, and the Marble Oracle self-test. Actual administrative installation on a user's Linux Mint desktop and network download on Windows 11 still require validation in those environments.
