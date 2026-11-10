# Marble Oracle — Linux edition

This edition preserves the original PR17 five-panel arrangement (Archive / Latin, Wire, Markets / Cards), with the calmer Oggcultist Ember redesign and bundled Uberata Clear font.

## Start it

1. Extract the **entire ZIP** into a directory, not just the launch script.
2. Install Python 3 with Tkinter using your distribution's package manager.
3. Open a terminal in the extracted `Marble_Oracle` directory and run:

   ```bash
   ./Marble_Oracle_Linux.sh
   ```

   Or launch from a terminal without executable permission: `bash Marble_Oracle_Linux.sh`.

### Linux packages

- Ubuntu / Debian / Mint: `sudo apt install python3 python3-tk`
- Fedora: `sudo dnf install python3 python3-tkinter`
- Arch: `sudo pacman -S python tk`

The modern view runs without Pillow. For the optional original photographic CRT, install Pillow with your distro's `python3-pil` / `python3-pil.imagetk` packages or into a virtual environment, then use `./Marble_Oracle_Linux_Original_CRT.sh`.

For optional sound effects, install PulseAudio/PipeWire's `paplay` or ALSA's `aplay`. Without them, sound may be silent. Windows-only system audio loopback scopes aren't available on Linux.

Internet-connected news and markets require network access. The other built-in sections work offline.

## Linux desktop shortcut (optional)

In a terminal **inside the extracted directory**, run `./install_linux_desktop.sh` to create an application-menu entry. It uses absolute paths, so if you move the directory later, run the installer again.

## Notes

- Uberata Clear is shipped in `Marble_Oracle_App/fonts` and registered at runtime through Fontconfig.
- Linux settings and runtime data are stored under the XDG user state directory by the app.
- The Windows BAT launchers are left in the archive for compatibility; Linux uses the SH launchers.
- Windows-only "start with Windows" commands are intentionally unavailable on Linux.
- Automated GUI self-test: `xvfb-run -a ./Marble_Oracle_Linux.sh --selftest` (requires `xvfb`).
