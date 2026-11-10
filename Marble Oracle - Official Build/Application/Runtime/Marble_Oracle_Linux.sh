#!/usr/bin/env bash
set -euo pipefail
BASE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$BASE_DIR/Marble_Oracle_App"
if [[ ! -f "$APP_DIR/oracle_bootstrap.py" ]]; then
  echo "Marble Oracle application files missing. Extract the whole archive." >&2
  exit 2
fi
if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 missing. Install python3 and python3-tk." >&2
  exit 2
fi
if ! python3 -c 'import tkinter' >/dev/null 2>&1; then
  echo "Tkinter missing. On Linux Mint run: sudo apt install python3-tk" >&2
  exit 2
fi
cd "$APP_DIR"
exec python3 oracle_bootstrap.py --no-bezel --os-frame "$@"
