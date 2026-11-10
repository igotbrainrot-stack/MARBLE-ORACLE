#!/usr/bin/env bash
# Install an application-menu launcher for the *official* suite entry point.
# Linux Mint double-click uses Terminal=false: no terminal stays open.
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
         'Name=Marble Oracle', 'Comment=Marble Oracle with Oggcultist, Eidolith, Passphrase and Touch Type',
         'Exec=' + quote(launch), 'Terminal=false', 'StartupNotify=true',
         'Categories=Utility;AudioVideo;']
if icon.is_file(): lines.append('Icon=' + str(icon.resolve()))
output.write_text('\n'.join(lines)+'\n',encoding='utf-8')
output.chmod(0o644)
print('Installed terminal-free Marble Oracle menu shortcut:', output)
PYDESKTOP
