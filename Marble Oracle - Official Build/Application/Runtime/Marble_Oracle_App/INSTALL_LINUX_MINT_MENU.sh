#!/usr/bin/env bash
# Installs a per-user Linux Mint application-menu shortcut. Does not need sudo.
set -euo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT="$HERE/LINUX LAUNCHER.sh"
if [ ! -f "$SCRIPT" ]; then
    printf 'Cannot find LINUX LAUNCHER.sh beside this installer.\n' >&2
    exit 1
fi
chmod u+x "$SCRIPT"
MENU="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
mkdir -p "$MENU"
TARGET="$MENU/oggcultist.desktop"
# Escape the characters that have special meaning in a .desktop Exec quoted argument.
ESCAPED_SCRIPT="${SCRIPT//\\/\\\\}"
ESCAPED_SCRIPT="${ESCAPED_SCRIPT//\"/\\\"}"
ICON="$HERE/Oggcultist/oggcultist/resources/icon.png"
if [ ! -f "$ICON" ]; then
    ICON="$HERE/Oggcultist/branding/original-identity/icon-128.png"
fi
{
   printf '%s\n' '[Desktop Entry]' 'Version=1.0' 'Type=Application' 'Name=Oggcultist' \
       'GenericName=Music player and audio converter' 'Comment=Play and organise music locally' \
       'Categories=AudioVideo;Audio;Player;' 'Terminal=false' 'StartupNotify=true'
   printf 'Exec=bash "%s"\n' "$ESCAPED_SCRIPT"
   printf 'Icon=%s\n' "$ICON"
} > "$TARGET"
chmod 644 "$TARGET"
if command -v update-desktop-database >/dev/null 2>&1; then
   update-desktop-database "$MENU" >/dev/null 2>&1 || true
fi
printf '\nOggcultist is now available in the Linux Mint application menu.\n'
printf 'Look under Sound & Video, or search for Oggcultist.\n'
printf 'Installed shortcut: %s\n' "$TARGET"
