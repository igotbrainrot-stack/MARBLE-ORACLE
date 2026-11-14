#!/usr/bin/env python3
"""Revert AUGURSPEX's opt-in MARBLE ORACLE integration; preserve user settings."""
from __future__ import annotations
import argparse
import json
import shutil
import sys
from pathlib import Path
from install_into_suite import (find_suite, sha, APP_RELPATH, ADDON_RELPATH,
                                BRIDGE_RELPATH, DOC_RELPATH, ORACLE_RELPATH,
                                CHROME_RELPATH, MANIFEST_RELPATH, INV_RELPATH)


def uninstall(suite: Path) -> None:
    addon = suite / ADDON_RELPATH
    backup = addon / 'integration_backup'
    state_file = addon / 'integration_state.json'
    if not backup.is_dir() or not state_file.is_file():
        raise ValueError('No installed AUGURSPEX suite module backup found; no changes made.')
    state = json.loads(state_file.read_text(encoding='utf-8'))
    for rel in (ORACLE_RELPATH, CHROME_RELPATH):
        p = suite / rel
        if state.get('patched_checksums', {}).get(p.name) != sha(p):
            raise ValueError('The suite has been modified since AUGURSPEX installation: '
                             + p.name + '. Refusing to overwrite newer changes.')
    for rel in (ORACLE_RELPATH, CHROME_RELPATH, MANIFEST_RELPATH, INV_RELPATH):
        saved = backup / rel.name
        if not saved.is_file():
            raise ValueError('Backup file missing: ' + str(saved))
    if (suite / BRIDGE_RELPATH).is_file() and sha(suite / BRIDGE_RELPATH) != state.get('bridge_sha256'):
        raise ValueError('AUGURSPEX bridge changed since installation; manual review required.')
    # Restore exactly the previous suite sources and inventory. User app state
    # (~/.config/augurspex) and browser settings are deliberately excluded.
    for rel in (ORACLE_RELPATH, CHROME_RELPATH, MANIFEST_RELPATH, INV_RELPATH):
        shutil.copy2(backup / rel.name, suite / rel)
    (suite / BRIDGE_RELPATH).unlink(missing_ok=True)
    (suite / DOC_RELPATH).unlink(missing_ok=True)
    shutil.rmtree(addon)
    print('AUGURSPEX removed from MARBLE ORACLE. Original source and manifests restored.')
    print('AUGURSPEX user watchlist and preferences have NOT been deleted.')


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('suite', type=Path, help='Folder "Marble Oracle - Official Build" or its parent')
    args = p.parse_args(argv)
    try:
        uninstall(find_suite(args.suite))
    except Exception as exc:
        print('UNINSTALL STOPPED:', exc, file=sys.stderr)
        return 1
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
