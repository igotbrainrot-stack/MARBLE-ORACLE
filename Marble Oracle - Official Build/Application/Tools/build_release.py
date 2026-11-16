#!/usr/bin/env python3
"""Regenerate the release inventory and manifest, and build the portable ZIP.

    python3 Application/Tools/build_release.py --manifests          # rewrite the two JSON files
    python3 Application/Tools/build_release.py --zip ../out.zip     # manifests, then the portable ZIP

The inventory is a SHA-256 for every file in the release tree. Files that are
part of the distribution but deliberately not kept in Git (the two third-party
research PDFs) are recorded with "optional": true: verify_release.py checks
them when they are present and does not fail when they are absent, so the same
inventory is valid for a Git checkout and for the full ZIP.

Nothing here touches user state, and the ZIP is byte-for-byte reproducible for
a given tree (sorted names, fixed timestamps).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]            # "Marble Oracle - Official Build"
APPLICATION = ROOT / 'Application'
DOC = APPLICATION / 'Documentation'
sys.path.insert(0, str(APPLICATION / 'Runtime' / 'Marble_Oracle_App'))

SELF_REFERENTIAL = ('Application/Documentation/BUILD_MANIFEST.json', 'Application/Documentation/FILE_INVENTORY.json')
IGNORED_DIRS = {'__pycache__', '.ruff_cache', '.pytest_cache', '.mypy_cache', '.git', '.venv'}
IGNORED_SUFFIXES = ('.pyc', '.pyo', '.log', '.tmp', '.part')
OPTIONAL_PREFIXES = ('Application/Documentation/Research/',)
EXECUTABLE_SUFFIXES = ('.sh',)
TABS = ('HOME', 'OGGCULTIST', 'EIDOLITH', 'AUGURSPEX', 'PASSPHRASE', 'TOUCH TYPE')


def release_files() -> dict[str, Path]:
    """Every distributable file under the release root, keyed by its POSIX path."""
    found = {}
    for path in ROOT.rglob('*'):
        if not path.is_file() or IGNORED_DIRS.intersection(path.parts) or path.name.endswith(IGNORED_SUFFIXES):
            continue
        found[path.relative_to(ROOT).as_posix()] = path
    return dict(sorted(found.items()))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def write_manifests() -> dict:
    from oracle_version import RELEASE_DATE, RELEASE_TITLE, SUITE_NAME, SUITE_VERSION
    files = release_files()
    entries = []
    for relative, path in files.items():
        if relative in SELF_REFERENTIAL:
            continue
        entry = {'path': relative, 'bytes': path.stat().st_size, 'sha256': sha256(path)}
        if relative.startswith(OPTIONAL_PREFIXES):
            entry['optional'] = True
        entries.append(entry)
    generated = datetime.now(timezone.utc).isoformat(timespec='seconds')
    inventory = {
        'release': f'{SUITE_NAME} {SUITE_VERSION}', 'generated_utc': generated, 'schema': 'sha256-inventory-v2',
        'excluded_from_hashes': list(SELF_REFERENTIAL),
        'optional_note': 'Entries marked optional are in the portable ZIP but not in Git; verify_release.py checks them when present.',
        'inventory_file_count': len(entries), 'inventory_total_bytes': sum(e['bytes'] for e in entries),
        'files': entries,
    }
    manifest = {
        'release': f'{SUITE_NAME} {SUITE_VERSION}', 'version': SUITE_VERSION, 'title': RELEASE_TITLE,
        'release_date': RELEASE_DATE, 'generated_utc': generated,
        'platform_targets': ['Windows 11', 'Linux Mint'],
        'entry_points': {
            'windows': 'START MARBLE ORACLE - WINDOWS.vbs',
            'windows_fallback': 'START MARBLE ORACLE - WINDOWS (if the VBS launcher is blocked).bat',
            'linux': 'START MARBLE ORACLE - LINUX.sh',
            'requirements_checker': 'Application/Runtime/launch_suite.pyw',
            'application': 'Application/Runtime/Marble_Oracle_App/marble_oracle.py',
        },
        'workspaces': list(TABS),
        'file_count': len(entries) + len(SELF_REFERENTIAL),
        'inventory_file_count': len(entries),
        'python_source_count': sum(1 for e in entries if e['path'].endswith(('.py', '.pyw'))),
        'test_script_count': sum(1 for e in entries if Path(e['path']).name.startswith('test_') and e['path'].endswith('.py')),
        'total_bytes': inventory['inventory_total_bytes'],
        'previous_release': {
            'version': '0.4.9.4',
            'branch': 'claude/marble-oracle-0494-data-sources',
        },
        'verification': {
            'see': 'Application/Documentation/TESTING_REPORT.md',
            'automated_linux_gui': 'Ubuntu 24.04, Tk under Xvfb (GitHub Actions)',
            'automated_windows_gui': 'see TESTING_REPORT.md',
            'physical_windows_11_verified': False,
            'physical_linux_mint_verified': False,
            'gpu_encoders_verified_on_hardware': False,
            'live_provider_probe': 'see Application/Documentation/PROVIDER_PROBE.md (dated evidence, not a guarantee)',
        },
        'history': 'Earlier manifests are preserved in Application/Documentation/History/.',
    }
    (DOC / 'FILE_INVENTORY.json').write_text(json.dumps(inventory, indent=1) + '\n', encoding='utf-8')
    (DOC / 'BUILD_MANIFEST.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print(f'manifests written: {len(entries)} inventoried files, {inventory["inventory_total_bytes"]:,} bytes')
    return manifest


def build_zip(target: Path) -> None:
    files = release_files()
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for relative, path in files.items():
            info = zipfile.ZipInfo(f'{ROOT.name}/{relative}', date_time=(2026, 11, 16, 0, 0, 0))
            mode = 0o755 if relative.endswith(EXECUTABLE_SUFFIXES) else 0o644
            info.external_attr = (0o100000 | mode) << 16
            # Media archives are already compressed; storing them keeps the build fast and no larger.
            info.compress_type = zipfile.ZIP_STORED if relative.endswith(('.zip', '.png', '.gif', '.pdf')) else zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())
    print(f'{target.name}: {len(files)} files, {target.stat().st_size:,} bytes, sha256 {sha256(target)}')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--manifests', action='store_true', help='rewrite FILE_INVENTORY.json and BUILD_MANIFEST.json')
    parser.add_argument('--zip', type=Path, help='also write the portable ZIP to this path')
    args = parser.parse_args()
    if not (args.manifests or args.zip):
        parser.error('nothing to do: pass --manifests and/or --zip PATH')
    write_manifests()
    if args.zip:
        build_zip(args.zip.resolve())
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
