#!/usr/bin/env bash
# Oggcultist launcher for Linux (Linux Mint, Ubuntu, Debian ...).
# Keep this file next to the "Oggcultist" folder, as they came out of the ZIP.
#
# What it does:
#   1. checks Python 3.10+, Tkinter, the venv module and FFmpeg are installed; on first launch it
#      offers to install the missing ones (apt; asks first, then your password);
#   2. creates a private Python environment in Oggcultist/.venv (repairs it if a previous try broke it);
#   3. installs Mutagen and Pillow into it (only when missing);
#   4. opens Oggcultist.
# Everything it prints also goes to Oggcultist/launcher-log.txt. When it was started by
# double-click without a terminal and something goes wrong, it shows the message in a window.
#
#   ./"LINUX LAUNCHER.sh"            open Oggcultist
#   ./"LINUX LAUNCHER.sh" --version  show the version (no window)
#   bash "LINUX LAUNCHER.sh"         use this if double-click does nothing (file not executable)
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
APP="$HERE/Oggcultist"
LOG="$APP/launcher-log.txt"
INTERACTIVE=0
if [ -t 0 ] && [ -t 1 ]; then INTERACTIVE=1; fi

show_error() {
  # $1 = message. Terminal: print it and wait. Double-click: a window if one can be shown.
  local message="$1"
  printf '\nOggcultist could not start:\n%s\n\nDetails are in: %s\n' "$message" "$LOG" >&2
  if [ "$INTERACTIVE" = 1 ]; then
    read -r -p 'Press Enter to close this window.' _ || true
  elif command -v zenity >/dev/null 2>&1; then
    zenity --error --title='Oggcultist' --width=460 \
      --text="Oggcultist could not start.\n\n${message}\n\nDetails: ${LOG}" >/dev/null 2>&1 || true
  elif command -v kdialog >/dev/null 2>&1; then
    kdialog --title Oggcultist --error "Oggcultist could not start.

${message}

Details: ${LOG}" >/dev/null 2>&1 || true
  elif command -v notify-send >/dev/null 2>&1; then
    notify-send 'Oggcultist could not start' "${message} Details: ${LOG}" || true
  fi
  exit 1
}

if [ ! -f "$APP/launch.py" ]; then
  LOG="(no log: the Oggcultist folder is missing)"
  show_error 'The "Oggcultist" folder was not found next to this launcher.
Keep "LINUX LAUNCHER.sh" in the same folder as the "Oggcultist" folder, exactly as they came out of the ZIP.'
fi
cd "$APP" || show_error "Cannot open the folder $APP"

# Keep a log of this start (the previous one is kept as launcher-log.old.txt).
[ -f "$LOG" ] && mv -f "$LOG" "$APP/launcher-log.old.txt" 2>/dev/null
if [ "$INTERACTIVE" = 1 ]; then
  exec > >(tee -a "$LOG") 2>&1
else
  exec >>"$LOG" 2>&1
fi
echo "Oggcultist launcher — $(date '+%Y-%m-%d %H:%M:%S')"
echo "Folder: $APP"

# ---- 1. system Python and the parts Linux distributions ship separately --------------------------
PYTHON="${PYTHON:-python3}"
if ! command -v "$PYTHON" >/dev/null 2>&1; then
  show_error "Python 3 is not installed. Install it with:
  sudo apt install python3 python3-venv python3-tk"
fi
if ! "$PYTHON" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)'; then
  show_error "Oggcultist needs Python 3.10 or newer; this system has $("$PYTHON" -V 2>&1)."
fi
echo "Python: $("$PYTHON" -V 2>&1) ($(command -v "$PYTHON"))"

NEEDS_WINDOW=1
case " $* " in
  *" --cli "*|*" --version "*|*" --paths "*|*" --help "*|*" -h "*) NEEDS_WINDOW=0 ;;
esac
PYVER="$("$PYTHON" -c 'import sys; print("%d.%d" % sys.version_info[:2])')"

missing_packages() {
  # The Debian/Ubuntu/Mint packages this computer still needs (empty when nothing is missing).
  local list=""
  if [ "$NEEDS_WINDOW" = 1 ] && ! "$PYTHON" -c 'import tkinter' 2>/dev/null; then list="$list python3-tk"; fi
  if ! "$PYTHON" -c 'import venv, ensurepip' 2>/dev/null; then
    list="$list python3-venv"
    # Mint/Ubuntu split ensurepip into a versioned package as well
    if command -v apt-cache >/dev/null 2>&1 && apt-cache show "python${PYVER}-venv" >/dev/null 2>&1; then
      list="$list python${PYVER}-venv"
    fi
  fi
  if [ "$NEEDS_WINDOW" = 1 ] && { ! command -v ffplay >/dev/null 2>&1 || ! command -v ffprobe >/dev/null 2>&1; }; then
    list="$list ffmpeg"
  fi
  echo "${list# }"
}

install_packages() {
  # First launch: install the missing system packages, after asking. Needs the user's password.
  local packages="$1"
  local script="apt-get install -y $packages || { apt-get update && apt-get install -y $packages; }"
  if ! command -v apt-get >/dev/null 2>&1; then
    show_error "Oggcultist needs these parts of Python: Tkinter and venv (and FFmpeg for playback).
This system does not use apt, so please install them with your package manager and start again."
  fi
  echo "Missing system packages: $packages"
  if [ "$INTERACTIVE" = 1 ]; then
    printf '\nOggcultist needs a few standard packages before its first start:\n  %s\n\n' "$packages"
    read -r -p 'Install them now? Your password will be asked. [Y/n] ' answer || answer=n
    case "$answer" in [nN]*) show_error "Not installed. To install them yourself, run:
  sudo apt install $packages" ;; esac
    sudo sh -c "$script" || show_error "The packages could not be installed. Run this yourself:
  sudo apt install $packages"
  elif command -v zenity >/dev/null 2>&1 && command -v pkexec >/dev/null 2>&1; then
    zenity --question --title='Oggcultist — first start' --width=460 --ok-label='Install' --cancel-label='Not now' \
      --text="Oggcultist needs a few standard packages before its first start:\n\n    ${packages}\n\nInstall them now? Your password will be asked." \
      >/dev/null 2>&1 || show_error "Not installed. To install them yourself, run:
  sudo apt install $packages"
    pkexec sh -c "$script" 2>&1 | tee -a "$LOG" | zenity --progress --pulsate --auto-close --no-cancel \
      --title='Oggcultist' --text='Installing the packages Oggcultist needs...' >/dev/null 2>&1
    [ "${PIPESTATUS[0]}" = 0 ] || show_error "The packages could not be installed. Open a terminal and run:
  sudo apt install $packages"
  else
    show_error "Some standard Python parts are not installed. Open a terminal and run:
  sudo apt install $packages
then start Oggcultist again. (Or start this launcher with \"Run in Terminal\" and it will install them.)"
  fi
}

MISSING="$(missing_packages)"
if [ -n "$MISSING" ]; then
  install_packages "$MISSING"
  STILL="$(missing_packages)"
  # FFmpeg is only needed for playback and conversion: Oggcultist explains that itself
  STILL="$(echo " $STILL " | sed 's/ ffmpeg / /; s/^ *//; s/ *$//')"
  if [ -n "$STILL" ]; then
    show_error "These packages are still missing after installing: $STILL
Run: sudo apt install $STILL"
  fi
  echo "System packages installed."
fi

# ---- 2. the private environment (repaired if an earlier attempt left it half-made) -----------------
venv_ok() {
  [ -x .venv/bin/python ] && .venv/bin/python -c 'import sys, pip; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null
}
if [ -d .venv ] && ! venv_ok; then
  echo "The private Python environment is incomplete (probably from an earlier failed start); rebuilding it."
  rm -rf .venv
fi
if [ ! -d .venv ]; then
  echo "Creating the private Python environment in Oggcultist/.venv (first start only)..."
  "$PYTHON" -m venv .venv || { rm -rf .venv; show_error "Python could not create its private environment (.venv).
On Linux Mint/Ubuntu this usually means the venv package is missing:
  sudo apt install python3-venv
then start Oggcultist again."; }
fi
VPY="$APP/.venv/bin/python"

# ---- 3. Mutagen and Pillow (only downloaded when missing) ---------------------------------------------
if ! "$VPY" -c 'import mutagen, PIL' 2>/dev/null; then
  echo "Installing Mutagen and Pillow (needs the internet once)..."
  "$VPY" -m pip install --disable-pip-version-check -q -r requirements.txt \
    || show_error "Mutagen and Pillow could not be installed. Check the internet connection and try again."
else
  "$VPY" -m pip install --disable-pip-version-check -q -r requirements.txt >/dev/null 2>&1 || true
fi

# ---- 4. open Oggcultist ---------------------------------------------------------------------------------
# launch.py handles FFmpeg/FFplay checks and starts the window in this process.
"$VPY" -u launch.py "$@"
STATUS=$?
if [ "$STATUS" != 0 ]; then
  show_error "Oggcultist stopped with an error (code $STATUS). The last lines of the log say why."
fi
exit 0
