#!/usr/bin/env bash
# Linux entry point (Debian/Ubuntu/Mint, Fedora, Arch, openSUSE): make sure Python 3
# with Tk exists, then open the requirements check, which starts the suite.
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

# Python 3 with Tk is the one thing setup cannot show a window without.
# Package names differ between Linux families; only these fixed names are used.
TK_PACKAGES=""
MANAGER=""
DISTRO="your Linux distribution"
OS_RELEASE="${MARBLE_ORACLE_OS_RELEASE:-/etc/os-release}"   # overridable for tests
if [[ -r "$OS_RELEASE" ]]; then
  IDS="$(. "$OS_RELEASE"; echo "${ID:-} ${ID_LIKE:-}" | tr '[:upper:]' '[:lower:]')"
  case " $IDS " in
    *" debian "*|*" ubuntu "*|*" linuxmint "*|*" pop "*|*" elementary "*|*" zorin "*)
      DISTRO="Debian / Ubuntu / Linux Mint"; MANAGER="apt-get install -y"; TK_PACKAGES="python3 python3-tk python3-venv" ;;
    *" fedora "*|*" rhel "*|*" centos "*|*" nobara "*|*" ultramarine "*)
      DISTRO="Fedora"; MANAGER="dnf install -y"; TK_PACKAGES="python3 python3-tkinter" ;;
    *" arch "*|*" manjaro "*|*" endeavouros "*|*" cachyos "*)
      DISTRO="Arch Linux"; MANAGER="pacman -S --needed --noconfirm"; TK_PACKAGES="python tk" ;;
    *opensuse*|*" suse "*|*" sles "*)
      DISTRO="openSUSE"; MANAGER="zypper --non-interactive install"; TK_PACKAGES="python3 python3-tk" ;;
  esac
fi

if [[ -n "${MARBLE_ORACLE_PRINT_DISTRO:-}" ]]; then   # for tests: report and stop
  echo "$DISTRO|$MANAGER|$TK_PACKAGES"
  exit 0
fi

say() {   # say error|question "text"  (returns 0 for yes)
  local kind="$1" text="$2"
  if command -v kdialog >/dev/null 2>&1; then
    if [[ "$kind" == question ]]; then kdialog --title "Marble Oracle setup" --yesno "$text"; else kdialog --title "Marble Oracle" --error "$text"; fi
  elif command -v zenity >/dev/null 2>&1; then
    if [[ "$kind" == question ]]; then zenity --question --title="Marble Oracle setup" --width=480 --text="$text"; else zenity --error --title="Marble Oracle" --width=480 --text="$text"; fi
  elif command -v xmessage >/dev/null 2>&1; then
    if [[ "$kind" == question ]]; then xmessage -center -buttons 'Install:0,Cancel:1' "$text"; else xmessage -center "$text"; fi
  else
    echo "$text" >&2
    [[ "$kind" != question ]] || return 1
  fi
}

tk_ok() { command -v python3 >/dev/null 2>&1 && python3 -c 'import tkinter; root=tkinter.Tk();root.withdraw();root.destroy()' >/dev/null 2>&1; }

if ! tk_ok; then
  if [[ -n "$MANAGER" ]]; then
    HINT="sudo ${MANAGER% -y*} ${TK_PACKAGES}"
    [[ "$MANAGER" == pacman* ]] && HINT="sudo pacman -S ${TK_PACKAGES}"
    [[ "$MANAGER" == zypper* ]] && HINT="sudo zypper install ${TK_PACKAGES}"
    if say question "Marble Oracle needs Python 3 with Tk to open its setup window.

Install ${TK_PACKAGES} on ${DISTRO} now? Your desktop will ask for your password."; then
      if command -v pkexec >/dev/null 2>&1; then
        # shellcheck disable=SC2086  # fixed, known package names only
        pkexec ${MANAGER} ${TK_PACKAGES} || true
      elif command -v pkcon >/dev/null 2>&1; then
        # shellcheck disable=SC2086
        pkcon --plain -y install ${TK_PACKAGES} || true
      fi
    else
      exit 3
    fi
  else
    HINT="install Python 3 and its Tk package with your software manager"
  fi
  if ! tk_ok; then
    say error "Python 3 with Tk is still missing, so Marble Oracle cannot start.

Install it with your software manager, or in a terminal:
${HINT}

Then start Marble Oracle again."
    exit 4
  fi
fi

# This checks *all* suite requirements on every launch. It asks permission
# before installing Python libraries or the FFmpeg tools, then verifies the
# actual GUI starts instead of silently quitting when the child fails.
exec python3 "$BOOT" "$@"
