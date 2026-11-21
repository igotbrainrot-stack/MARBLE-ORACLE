#!/usr/bin/env bash
# Add Marble Oracle to the Linux applications menu (KDE, GNOME, Cinnamon, XFCE).
# Runs the official START launcher without a terminal. Use --remove to take it out again.
set -euo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd -- "$HERE/../.." && pwd)"
START="$ROOT/START MARBLE ORACLE - LINUX.sh"
if [[ ! -f "$START" ]]; then
  echo 'Official Marble Oracle launcher missing; extract the complete release.' >&2
  exit 2
fi
chmod u+x "$START"
DEST="${XDG_DATA_HOME:-$HOME/.local/share}/applications/marble-oracle.desktop"
if [[ "${1:-}" == "--remove" ]]; then
  rm -f -- "$DEST"
  command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$(dirname "$DEST")" >/dev/null 2>&1 || true
  echo "Removed the Marble Oracle menu entry: $DEST"
  exit 0
fi
mkdir -p "$(dirname "$DEST")"
export START DEST HERE
python3 - <<'PYDESKTOP'
import os
from pathlib import Path
launch = Path(os.environ['START']).resolve()
output = Path(os.environ['DEST'])
def quote(path):
    path = str(path)
    if '\n' in path or '\r' in path:
        raise ValueError('Application folder path contains a newline')
    return '"' + (path.replace('\\', '\\\\')
                      .replace('"', '\\"')
                      .replace('$', '\\$')
                      .replace('`', '\\`')) + '"'
icon = Path(os.environ['HERE'])/'Marble_Oracle_App'/'marble_oracle.png'
lines = ['[Desktop Entry]', 'Type=Application', 'Version=1.0',
         'Name=Marble Oracle',
         'GenericName=Desktop suite',
         'Comment=Oracle dashboard, music player, video converter, market charts, passphrases and typing practice',
         'Exec=' + quote(launch), 'Terminal=false', 'StartupNotify=true',
         'StartupWMClass=MarbleOracle',
         'Keywords=music;video;converter;ffmpeg;markets;stocks;passphrase;password;typing;tarot;',
         'Categories=Utility;AudioVideo;']
if icon.is_file(): lines.append('Icon=' + str(icon.resolve()))
output.write_text('\n'.join(lines)+'\n',encoding='utf-8')
output.chmod(0o644)
print('Installed terminal-free Marble Oracle menu shortcut:', output)
PYDESKTOP
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$(dirname "$DEST")" >/dev/null 2>&1 || true
