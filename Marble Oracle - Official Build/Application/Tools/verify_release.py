#!/usr/bin/env python3
"""Verify the Marble Oracle tree against its release inventory.

Reads data only: it does not install anything, edit media or open a window.

    python3 Application/Tools/verify_release.py

Checks, in order: the top-level layout, the files a launch cannot do without,
the launcher's executable bit and line endings, every inventoried file's size
and SHA-256, files the inventory does not know about, and the integrity of
the media archives. Files the inventory marks "optional" (distributed in the
portable ZIP but not kept in Git) are checked when present.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / 'Application' / 'Documentation'
SELF_REFERENTIAL = {'Application/Documentation/BUILD_MANIFEST.json', 'Application/Documentation/FILE_INVENTORY.json'}
IGNORED_DIRS = {'__pycache__', '.ruff_cache', '.pytest_cache', '.mypy_cache', '.git', '.venv'}
IGNORED_SUFFIXES = ('.pyc', '.pyo', '.log', '.tmp', '.part')
TOP_LEVEL = {
    'START MARBLE ORACLE - WINDOWS.vbs', 'START MARBLE ORACLE - LINUX.sh', 'Application',
    'START MARBLE ORACLE - WINDOWS (if the VBS launcher is blocked).bat',
}
APP = 'Application/Runtime/Marble_Oracle_App/'
REQUIRED = [
    'START MARBLE ORACLE - WINDOWS.vbs',
    'START MARBLE ORACLE - LINUX.sh',
    'START MARBLE ORACLE - WINDOWS (if the VBS launcher is blocked).bat',
    'Application/README.md',
    'Application/Runtime/launch_suite.pyw',
    'Application/Runtime/Marble_Oracle.pyw',
    APP + 'marble_oracle.py', APP + 'oracle_version.py', APP + 'oracle_design.py',
    APP + 'oracle_eidolith.py', APP + 'oracle_ogg_tab.py', APP + 'oracle_touch_type.py',
    APP + 'marble_passphrase_tab.py', APP + 'oracle_augurspex_tab.py',
    APP + 'Augurspex/augurspex/providers.py', APP + 'Augurspex/augurspex/default_watchlist.json',
    APP + 'fonts/Uberata-Clear.ttf',
    APP + 'Oggcultist/oggcultist/resources/fonts/Uberata-Clear.ttf',
    APP + 'data/eff_large.txt',
]
MEDIA_ARCHIVES = ['rune_consistent_flips.zip', 'rune_native_frames.zip', 'rune_flip_strips.zip', 'runes.zip',
                  'tarot_cards.zip', 'latin_voices.zip', 'marble_archive.zip', 'photo_bezel_locked.zip', 'bezel.zip']
REQUIRED += [APP + 'data/' + name for name in MEDIA_ARCHIVES]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    errors = []
    actual = {p.name for p in ROOT.iterdir() if p.name not in IGNORED_DIRS}
    if actual != TOP_LEVEL:
        errors.append(f'Unexpected top-level entries: {sorted(actual.symmetric_difference(TOP_LEVEL))}')
    for name in REQUIRED:
        if not (ROOT / name).is_file():
            errors.append(f'Missing required: {name}')
    launcher = ROOT / 'START MARBLE ORACLE - LINUX.sh'
    if launcher.is_file():
        if os.name != 'nt' and not launcher.stat().st_mode & 0o100:
            errors.append('Linux launcher is not executable')
        if b'\r\n' in launcher.read_bytes():
            errors.append('Linux launcher has Windows line endings and will not start')
    inventory = json.loads((DOC / 'FILE_INVENTORY.json').read_text(encoding='utf-8'))
    listed = {entry['path']: entry for entry in inventory['files']}
    disk = {p.relative_to(ROOT).as_posix(): p for p in ROOT.rglob('*')
            if p.is_file() and not IGNORED_DIRS.intersection(p.parts) and not p.name.endswith(IGNORED_SUFFIXES)}
    unknown = sorted(set(disk) - SELF_REFERENTIAL - set(listed))
    missing = sorted(name for name, entry in listed.items() if name not in disk and not entry.get('optional'))
    absent_optional = sorted(name for name, entry in listed.items() if name not in disk and entry.get('optional'))
    if unknown:
        errors.append(f'Files not in the inventory: {unknown}')
    if missing:
        errors.append(f'Inventoried files missing from disk: {missing}')
    for relative, entry in listed.items():
        path = disk.get(relative)
        if path is None:
            continue
        if path.stat().st_size != entry['bytes'] or sha256(path) != entry['sha256']:
            errors.append('Checksum/size mismatch: ' + relative)
    for name in MEDIA_ARCHIVES:
        archive = ROOT / APP / 'data' / name
        if archive.is_file():
            try:
                with zipfile.ZipFile(archive) as opened:
                    if opened.testzip() is not None:
                        errors.append('Corrupt asset archive: ' + name)
            except zipfile.BadZipFile:
                errors.append('Unreadable asset archive: ' + name)
    if errors:
        print('RELEASE VERIFICATION FAILED')
        for error in errors:
            print(' -', error)
        return 1
    print(f'RELEASE VERIFICATION PASS: {inventory.get("release", "?")} · {len(listed) - len(absent_optional)} inventoried files checked; '
          f'{len(MEDIA_ARCHIVES)} media archives valid')
    if absent_optional:
        print(f'Note: {len(absent_optional)} optional file(s) not present (they ship in the portable ZIP, not in Git): '
              + ', '.join(Path(name).name for name in absent_optional))
    return 0


if __name__ == '__main__':
    sys.exit(main())
