#!/usr/bin/env bash
# Optional original photographic CRT hardware appearance.
set -e
BASE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if ! python3 -c 'from PIL import Image, ImageTk' >/dev/null 2>&1; then
  echo 'The original CRT mode needs Pillow: install python3-pil and python3-pil.imagetk.' >&2
  exit 2
fi
cd "$BASE_DIR/Marble_Oracle_App"
exec python3 oracle_bootstrap.py --crt-v2 --os-frame "$@"
