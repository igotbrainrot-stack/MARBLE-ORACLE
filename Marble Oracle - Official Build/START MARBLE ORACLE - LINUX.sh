#!/usr/bin/env bash
# Official Linux Mint entry point: verify Tk first, then enter Python requirements setup.
# No terminal is opened by this launcher when launched graphically.
set -euo pipefail
BASE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
BOOT="$BASE_DIR/Application/Runtime/launch_suite.pyw"
if [[ ! -f "$BOOT" ]]; then
  if command -v zenity >/dev/null 2>&1; then
    zenity --error --title="Marble Oracle" --text="Application files not found. Extract the complete ZIP before opening Marble Oracle." || true
  elif command -v kdialog >/dev/null 2>&1; then
    kdialog --error "Application files missing. Extract the entire ZIP." || true
  else
    echo "Marble Oracle files missing: $BOOT" >&2
  fi
  exit 2
fi

if ! command -v python3 >/dev/null 2>&1 || ! python3 -c 'import tkinter; root=tkinter.Tk();root.withdraw();root.destroy()' >/dev/null 2>&1; then
  PROMPT="Marble Oracle requires Python 3 and Tkinter to show its graphical setup.\n\nInstall the Linux Mint packages python3, python3-tk and python3-venv?\n\nAdministrator approval will be requested."
  APPROVED=1
  if command -v zenity >/dev/null 2>&1; then
    zenity --question --title="Marble Oracle — Install initial requirements" --width=500 --text="$PROMPT" && APPROVED=0 || true
  elif command -v kdialog >/dev/null 2>&1; then
    kdialog --yesno "$PROMPT" --title "Marble Oracle — Install initial requirements" && APPROVED=0 || true
  elif command -v xmessage >/dev/null 2>&1; then
    xmessage -center -buttons 'Install:0,Cancel:1' "$PROMPT" && APPROVED=0 || true
  fi
  if [[ "$APPROVED" -ne 0 ]]; then
    echo 'Python/Tkinter setup cancelled or no graphical dialog available.' >&2
    exit 3
  fi
  if command -v pkexec >/dev/null 2>&1 && command -v apt-get >/dev/null 2>&1; then
    pkexec apt-get install -y python3 python3-tk python3-venv || true
  elif command -v pkcon >/dev/null 2>&1; then
    pkcon --plain -y install python3 python3-tk python3-venv || true
  fi
  if ! command -v python3 >/dev/null 2>&1 || ! python3 -c 'import tkinter; root=tkinter.Tk();root.withdraw();root.destroy()' >/dev/null 2>&1; then
    MSG="Python 3 / Tkinter could not be installed. Use Linux Mint Software Manager, or run: sudo apt install python3 python3-tk python3-venv"
    if command -v zenity >/dev/null 2>&1; then
      zenity --error --title="Marble Oracle" --text="$MSG" || true
    elif command -v kdialog >/dev/null 2>&1; then
      kdialog --error "$MSG" || true
    else
      echo "$MSG" >&2
    fi
    exit 4
  fi
fi

# This checks *all* suite requirements on every launch. It asks permission
# before installing Python libraries or the FFmpeg tools, then verifies the
# actual GUI starts instead of silently quitting when the child fails.
exec python3 "$BOOT" "$@"
