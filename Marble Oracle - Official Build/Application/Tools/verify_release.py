#!/usr/bin/env python3
"""Verify the packaged Marble Oracle tree against its current release inventory.

Reads data only. Does not install dependencies, edit media, or launch the GUI.
Run: python3 Application/Tools/verify_release.py
"""
from __future__ import annotations
import hashlib, json, sys, zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
DOC=ROOT/'Application'/'Documentation'
EXCLUDE={
 'Application/Documentation/BUILD_MANIFEST.json',
 'Application/Documentation/FILE_INVENTORY.json',
 'Application/Documentation/AUDIT_REPORT.md',
 'Application/Documentation/VERIFICATION_REPORT.md',
}
REQUIRED=[
 'START MARBLE ORACLE - WINDOWS.vbs',
 'START MARBLE ORACLE - LINUX.sh',
 'Application/Runtime/launch_suite.pyw',
 'Application/Runtime/Marble_Oracle.pyw',
 'Application/Runtime/Marble_Oracle_App/marble_oracle.py',
 'Application/Runtime/Marble_Oracle_App/oracle_eidolith.py',
 'Application/Runtime/Marble_Oracle_App/oracle_ogg_tab.py',
 'Application/Runtime/Marble_Oracle_App/oracle_touch_type.py',
 'Application/Runtime/Marble_Oracle_App/marble_passphrase_tab.py',
 'Application/Runtime/Marble_Oracle_App/fonts/Uberata-Clear.ttf',
 'Application/Runtime/Marble_Oracle_App/Oggcultist/oggcultist/resources/fonts/Uberata-Clear.ttf',
 'Application/Runtime/Marble_Oracle_App/data/rune_consistent_flips.zip',
 'Application/Runtime/Marble_Oracle_App/data/tarot_cards.zip',
 'Application/Runtime/Marble_Oracle_App/data/latin_voices.zip',
 'Application/Runtime/Marble_Oracle_App/data/marble_archive.zip',
]

def main():
    errors=[]
    expected={'START MARBLE ORACLE - WINDOWS.vbs', 'START MARBLE ORACLE - LINUX.sh', 'Application'}
    actual={p.name for p in ROOT.iterdir()}
    if actual!=expected:errors.append(f'Unexpected top-level entries: {actual.symmetric_difference(expected)}')
    for f in REQUIRED:
        if not (ROOT/f).is_file():errors.append(f'Missing required: {f}')
    if not (ROOT/'START MARBLE ORACLE - LINUX.sh').stat().st_mode&0o100:
        errors.append('Linux launcher not executable')
    inventory=json.loads((DOC/'FILE_INVENTORY.json').read_text())
    listed={entry['path']:entry for entry in inventory['files']}
    disk={p.relative_to(ROOT).as_posix():p for p in ROOT.rglob('*') if p.is_file() and
          '__pycache__' not in p.parts and not p.name.endswith(('.pyc','.pyo'))}
    if set(disk)-EXCLUDE!=set(listed):
        errors.append(f'Inventory mismatch: missing records={sorted(set(disk)-EXCLUDE-set(listed))}, missing files={sorted(set(listed)-set(disk))}')
    for rel,entry in listed.items():
        p=disk.get(rel)
        if p is None:continue
        h=hashlib.sha256(p.read_bytes()).hexdigest()
        if h!=entry['sha256'] or p.stat().st_size!=entry['bytes']:
            errors.append('Checksum/size mismatch: '+rel)
    for name in ('rune_consistent_flips.zip','tarot_cards.zip','latin_voices.zip','marble_archive.zip'):
        file=ROOT/'Application'/'Runtime'/'Marble_Oracle_App'/'data'/name
        if file.is_file():
            with zipfile.ZipFile(file) as z:
                if z.testzip() is not None:errors.append('Corrupt asset archive: '+name)
    if errors:
        print('RELEASE VERIFICATION FAILED')
        for e in errors:print(' -',e)
        return 1
    print('RELEASE VERIFICATION PASS:',len(listed),'inventoried files, all checked; critical asset archives valid')
    return 0

if __name__=='__main__':sys.exit(main())
