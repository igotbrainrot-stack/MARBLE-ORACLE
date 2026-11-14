#!/usr/bin/env python3
"""Install portable AUGURSPEX v1.2 into the existing MARBLE ORACLE SUITE.

This is an opt-in, validated patch of the navigation and handler only.
Preserves all other suite assets, original source snapshots, and per-user state.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parent
PAYLOAD = MODULE_ROOT / 'payload'
APP_RELPATH = Path('Application/Runtime/Marble_Oracle_App')
INV_RELPATH = Path('Application/Documentation/FILE_INVENTORY.json')
MANIFEST_RELPATH = Path('Application/Documentation/BUILD_MANIFEST.json')
CHROME_RELPATH = APP_RELPATH / 'oracle_chrome.py'
ORACLE_RELPATH = APP_RELPATH / 'marble_oracle.py'
ADDON_RELPATH = APP_RELPATH / 'Augurspex'
BRIDGE_RELPATH = APP_RELPATH / 'oracle_augurspex_bridge.py'
DOC_RELPATH = Path('Application/Documentation/AUGURSPEX_MODULE_INTEGRATION.md')
EXCLUDED = {
    'Application/Documentation/AUDIT_REPORT.md',
    'Application/Documentation/VERIFICATION_REPORT.md',
    INV_RELPATH.as_posix(),
    MANIFEST_RELPATH.as_posix(),
}


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with p.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def find_suite(path: Path) -> Path:
    root = path.expanduser().resolve()
    if (root / APP_RELPATH / 'marble_oracle.py').is_file():
        return root
    if (root / 'Runtime/Marble_Oracle_App/marble_oracle.py').is_file():
        return root.parent
    if (root / 'Marble_Oracle_App/marble_oracle.py').is_file():
        return root.parent.parent.parent
    maybe = [x for x in root.glob('*/Application/Runtime/Marble_Oracle_App/marble_oracle.py') if x.is_file()]
    if len(maybe) == 1:
        return maybe[0].parents[3]
    raise ValueError(f'Cannot locate the MARBLE ORACLE release under {path}. Select the "Marble Oracle - Official Build" folder.')


def edit_chrome(src: str) -> str:
    if 'tab_augurspex' in src:
        raise ValueError('Suite source already mentions AUGURSPEX. Aborting to avoid duplicate integration.')
    old = '("TOUCH TYPE", "tab_touch_type"))'
    new = '("TOUCH TYPE", "tab_touch_type"), ("AUGURSPEX", "tab_augurspex"))'
    if src.count(old) != 1:
        raise ValueError('Navigation layout differs from the verified Marble Oracle 0.4.7 structure.')
    src = src.replace(old, new, 1)
    src = src.replace('Five persistent workspace tabs in the header', 'Six persistent workspace tabs in the header')
    marker = '"EIDOLITH": "EIDO"}.get(label, label)'
    if src.count(marker) != 1:
        raise ValueError('Short-label mapping differs from verified release; refusing patch.')
    src = src.replace(marker, '"EIDOLITH": "EIDO", "AUGURSPEX": "AUGUR"}.get(label, label)', 1)
    return src


def edit_oracle(src: str) -> str:
    if 'tab_augurspex' in src:
        raise ValueError('Suite source already mentions AUGURSPEX. Aborting.')
    anchor = '        if name == "tab_eidolith":\n'
    if src.count(anchor) != 1:
        raise ValueError('Suite tab dispatch differs from verified source; refusing patch.')
    addition = '''        if name == "tab_augurspex":
            # AUGURSPEX runs in a browser/app companion window, never in the
            # Tk canvas. Other Oracle tools and media modules remain intact.
            try:
                from oracle_augurspex_bridge import launch
                started = launch()
                self.say("AUGURSPEX OPENING" if started else "AUGURSPEX REOPENED", 4)
            except Exception as exc:
                self.say("AUGURSPEX UNAVAILABLE: %s" % exc, 6)
            return
'''
    return src.replace(anchor, addition + anchor, 1)


def inventory_for(root: Path, base: dict) -> dict:
    rows = []
    for p in root.rglob('*'):
        if not p.is_file() or '__pycache__' in p.parts or p.name.endswith(('.pyc', '.pyo')):
            continue
        relative = p.relative_to(root).as_posix()
        if relative in EXCLUDED:
            continue
        rows.append({'path': relative, 'bytes': p.stat().st_size, 'sha256': sha(p)})
    rows.sort(key=lambda r: r['path'])
    out = dict(base)
    out['generated_utc'] = datetime.now(timezone.utc).isoformat()
    out['inventory_file_count'] = len(rows)
    out['inventory_total_bytes'] = sum(r['bytes'] for r in rows)
    out['files'] = rows
    return out


def write_json(p: Path, obj) -> None:
    p.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def install(suite: Path) -> None:
    app = suite / APP_RELPATH
    original = suite / ORACLE_RELPATH
    chrome = suite / CHROME_RELPATH
    manifest = suite / MANIFEST_RELPATH
    inventory = suite / INV_RELPATH
    backup = suite / ADDON_RELPATH / 'integration_backup'
    if (suite / ADDON_RELPATH).exists() or (suite / BRIDGE_RELPATH).exists():
        raise ValueError('AUGURSPEX module already exists. No files changed.')
    for p in (original, chrome, manifest, inventory):
        if not p.is_file():
            raise ValueError(f'Expected suite file is missing: {p}')
    if not (suite / 'START MARBLE ORACLE - LINUX.sh').exists():
        raise ValueError('The selected folder is not an official MARBLE ORACLE release.')
    # All preconditions before any writes.
    new_chrome = edit_chrome(chrome.read_text(encoding='utf-8'))
    new_oracle = edit_oracle(original.read_text(encoding='utf-8'))
    base_inv = json.loads(inventory.read_text(encoding='utf-8'))
    base_manifest = json.loads(manifest.read_text(encoding='utf-8'))
    expected = {r['path']: r['sha256'] for r in base_inv.get('files', [])}
    # Validate the files that we are about to edit against the official inventory.
    for p in (original, chrome):
        rel = p.relative_to(suite).as_posix()
        if expected.get(rel) != sha(p):
            raise ValueError('Source diverges from suite inventory: ' + rel)
    payload_files = sorted(p for p in (PAYLOAD / 'Augurspex').rglob('*') if p.is_file())
    if not payload_files or not (PAYLOAD / 'oracle_augurspex_bridge.py').is_file():
        raise ValueError('The AUGURSPEX module payload is incomplete')
    try:
        (suite / ADDON_RELPATH).mkdir(parents=True, exist_ok=False)
        # Keep originals inside module: future releases can be rolled back even
        # when no original suite ZIP is available on the user's computer.
        backup.mkdir(parents=True)
        for orig_file in (original, chrome, manifest, inventory):
            shutil.copy2(orig_file, backup / orig_file.name)
        shutil.copytree(PAYLOAD / 'Augurspex', suite / ADDON_RELPATH, dirs_exist_ok=True)
        shutil.copy2(PAYLOAD / 'oracle_augurspex_bridge.py', suite / BRIDGE_RELPATH)
        chrome.write_text(new_chrome, encoding='utf-8')
        original.write_text(new_oracle, encoding='utf-8')
        doc = suite / DOC_RELPATH
        doc.write_text((MODULE_ROOT / 'SUITE_INTEGRATION.md').read_text(encoding='utf-8'), encoding='utf-8')
        new_manifest = dict(base_manifest)
        new_manifest['release'] = str(base_manifest.get('release', 'Marble Oracle')) + ' + AUGURSPEX 1.2 companion module'
        new_manifest['release_date'] = '2026-11-11'
        tabs = list(base_manifest.get('tabs') or [])
        if 'AUGURSPEX' not in tabs:
            tabs.append('AUGURSPEX')
        new_manifest['tabs'] = tabs
        new_manifest['augurspex_integration'] = {
            'version': '1.2.0', 'mode': 'portable companion window',
            'entry': 'Application/Runtime/Marble_Oracle_App/Augurspex/run.py',
            'account_required': False, 'api_key_required': False,
            'shared_user_config': '~/.config/augurspex',
            'external_deb_required': False,
        }
        write_json(manifest, new_manifest)
        new_inv = inventory_for(suite, base_inv)
        write_json(inventory, new_inv)
        state = {
            'version': '1.2.0',
            'installed_utc': datetime.now(timezone.utc).isoformat(),
            'patched_checksums': {p.name: sha(p) for p in (original, chrome)},
            'bridge_sha256': sha(suite / BRIDGE_RELPATH),
        }
        write_json(suite / ADDON_RELPATH / 'integration_state.json', state)
        # Recompute inventory to record the state file itself.
        new_inv = inventory_for(suite, base_inv)
        write_json(inventory, new_inv)
    except Exception:
        # Restore the suite's exact original core and reports before re-raising.
        if backup.is_dir():
            for orig_file, name in ((original, original.name), (chrome, chrome.name),
                                    (manifest, manifest.name), (inventory, inventory.name)):
                if (backup / name).is_file():
                    shutil.copy2(backup / name, orig_file)
        (suite / BRIDGE_RELPATH).unlink(missing_ok=True)
        (suite / DOC_RELPATH).unlink(missing_ok=True)
        shutil.rmtree(suite / ADDON_RELPATH, ignore_errors=True)
        raise
    print('SUCCESS: AUGURSPEX 1.2 integrated into MARBLE ORACLE SUITE')
    print('Suite:', suite)
    print('Navigation: AUGURSPEX (opens a separate account-free chart window)')
    print('Original suite modules and assets preserved; original source backed up in:', backup)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('suite', type=Path, help='Folder "Marble Oracle - Official Build" or its parent')
    args = parser.parse_args(argv)
    try:
        install(find_suite(args.suite))
    except Exception as exc:
        print('INSTALLATION STOPPED:', exc, file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
