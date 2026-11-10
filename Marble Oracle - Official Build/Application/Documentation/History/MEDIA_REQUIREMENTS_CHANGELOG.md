# Media setup refinement — FFmpeg / FFprobe / FFplay

Updated the first-run graphical requirements setup without changing Marble Oracle’s layout, Oggcultist pages, Passphrase, Tarot, or Runes.

- Linux Mint / Ubuntu: with consent, installs `ffmpeg` through an available graphical-authorisation system (Polkit `pkexec`, or PackageKit `pkcon`). This package supplies FFmpeg, FFprobe and FFplay on the target distributions. Never invokes `sudo` without a terminal or requests a password inside Marble Oracle.
- Windows 11: retains Oggcultist’s HTTPS download with publisher SHA-256 check, now extracting only the missing media executables to the app’s private user directory.
- Shared: checks the three tools after installation; provides error details on failure or cancellation instead of claiming success.
- Python: skips virtual environment creation if the required packages are already available. When Linux Python environment creation fails due to missing `python3-venv` / `ensurepip`, the installer offers a graphical administrator-authenticated prerequisite installation and retries.
- Media PATH uses Oggcultist's canonical private-tool path, including its portable mode.

Verification performed:
- 9 mocked installer/permission tests; no privileged changes or downloads performed.
- First-run GUI smoke test with missing tools simulated.
- Marble Oracle full GUI self-test.
- Three tab/layout checks (normal, retro, flat).
- Embedded Oggcultist seven-page and lifecycle test.
- Fresh-package integrity/probe validation.

Not tested: a real administrator-authorised FFmpeg installation on a physical Linux Mint desktop, a real Windows checksum download and Windows 11 media playback, or hardware audio. Internet and user permissions are required when installing missing components.
