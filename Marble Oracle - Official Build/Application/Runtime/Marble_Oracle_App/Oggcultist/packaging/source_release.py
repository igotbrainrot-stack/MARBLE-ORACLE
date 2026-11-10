"""Build the runnable Python source distributions (Program ZIP and Claude handover ZIP).

Run from the project root::
    python packaging/source_release.py

Creates the Program ZIP and a complete source+Claude handover ZIP. The builder
checks the actual bundled Uberata TTF, its licence, launchers and icon resources before packaging.
The Program ZIP leaves out developer notes, the Claude handover and retired branding kits.
These are Python source packages (Tk required), not Windows executables.
"""
from __future__ import annotations

import hashlib
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]          # the "Oggcultist" program folder
TOP = ROOT.parent                                    # holds the two launchers next to it
DIST = TOP.parent
PROGRAM_FOLDER = 'Oggcultist'
LAUNCHERS = ('WINDOWS LAUNCHER.bat', 'LINUX LAUNCHER.sh', 'INSTALL_LINUX_MINT_MENU.sh')


def project_version() -> str:
    text = (ROOT / 'oggcultist/__init__.py').read_text(encoding='utf-8')
    return text.split('__version__ = ')[1].splitlines()[0].strip().strip("'\"")


def release_folder(version: str | None = None) -> str:
    return f'Oggcultist-{version or project_version()}'


def archive_name(relative: str, version: str | None = None) -> str:
    """Where a program file (path relative to the program folder) sits inside the ZIP."""
    return f'{release_folder(version)}/{PROGRAM_FOLDER}/{relative}'
SKIP_DIRS = {'__pycache__', '.pytest_cache', '.git', '.venv', 'dist', 'build', 'OggcultistData'}
SKIP_SUFFIXES = {'.pyc', '.pyo', '.log'}
SKIP_FILES = {'Thumbs.db', '.DS_Store', 'launcher-log.txt', 'launcher-log.old.txt'}


def files(complete: bool):
    for file in sorted(ROOT.rglob('*')):
        if not file.is_file() or set(file.relative_to(ROOT).parts) & SKIP_DIRS:
            continue
        if file.suffix in SKIP_SUFFIXES or file.name in SKIP_FILES:
            continue
        parts = file.relative_to(ROOT).parts
        # Developer notes, the Claude handover and retired brand kits stay in the handover archive.
        if not complete and (parts[0] == 'docs' or file.name.startswith('CLAUDE_')
                             or (parts[0] == 'branding' and len(parts) > 2 and parts[1] not in ('original-identity', 'approved-ogg'))):
            continue
        if not complete and parts[0] == 'oggcultist' and len(parts) > 1 and parts[1] == 'font_source':
            continue
        yield file


def make_archive(path: Path, complete: bool) -> None:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from oggcultist import fonts
    # The exact Uberata v3.0 TTF must ship in every runnable source archive.
    # No first-run font-release ZIP or Downloads folder is required.
    fonts.require_complete_bundle(strict=True)
    data = list(files(complete))
    expected = {'oggcultist/fonts.py',
                'oggcultist/gui/native_folders.py',
                'oggcultist/resources/fonts/Uberata-Clear.ttf',
                'oggcultist/resources/fonts/OFL_UBERATA_CLEAR.txt',
                'oggcultist/resources/fonts/NOTO_SOURCE_NOTICE.md',
                'branding/original-identity/symbol.svg',
                'branding/original-identity/wordmark-outlined.svg',
                'oggcultist/resources/brand_symbol.png',
                'oggcultist/resources/brand_wordmark.png',
                'oggcultist/resources/icon.ico',
                'oggcultist/suite_bridge.py',
                'suite_integration/manifest.json',
                'suite_integration/README.md',
                'branding/approved-ogg/Oggcultist.ico',
                'requirements.txt'}
    present = {p.relative_to(ROOT).as_posix() for p in data}
    missing = expected - present
    if missing:
        raise RuntimeError('Missing required bundled font or application assets: '+', '.join(sorted(missing)))
    path.parent.mkdir(parents=True, exist_ok=True)
    top = release_folder()
    for name in LAUNCHERS:
        if not (TOP / name).is_file():
            raise RuntimeError(f'Launcher missing next to the program folder: {name}')
    with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=7) as z:
        for name in LAUNCHERS:                      # the only files outside the program folder
            z.write(TOP / name, f'{top}/{name}')
        for file in data:
            z.write(file, archive_name(file.relative_to(ROOT).as_posix()))
    with zipfile.ZipFile(path) as z:
        if z.testzip():
            raise RuntimeError('Corrupt ZIP: ' + str(path))
        names = set(z.namelist())
        for p in expected:
            inside = archive_name(p)
            if inside not in names or z.read(inside) != (ROOT / p).read_bytes():
                raise RuntimeError('Archive asset missing/different: '+p)
        fonts_in_zip = sorted(n for n in names if n.lower().endswith(('.ttf', '.otf')) and '/resources/fonts/' in n)
        expected_font = archive_name('oggcultist/resources/fonts/Uberata-Clear.ttf')
        assert fonts_in_zip == [expected_font], 'Exactly one bundled Uberata TTF is required: ' + str(fonts_in_zip)
        assert hashlib.sha256(z.read(expected_font)).hexdigest() == fonts.FONT_SHA256, 'Wrong bundled Uberata version'
        for essential in ('Oggcultist.pyw', 'DIAGNOSE_WINDOWS.bat', 'requirements.txt', 'launch.py'):
            assert archive_name(essential) in names, essential
        outside = {n.split('/', 1)[1] for n in names if n.count('/') == 1}
        assert outside == set(LAUNCHERS), outside
        linux = z.getinfo(f'{top}/LINUX LAUNCHER.sh')
        assert (linux.external_attr >> 16) & 0o111, 'LINUX LAUNCHER.sh must be executable'
        menu = z.getinfo(f'{top}/INSTALL_LINUX_MINT_MENU.sh')
        assert (menu.external_attr >> 16) & 0o111, 'Mint menu installer must be executable'
        assert z.read(f'{top}/WINDOWS LAUNCHER.bat').count(b'\r\n') > 10
    print('Verified:', path, f'({len(data)} files)', flush=True)


def main() -> None:
    version = project_version()
    result = []
    for kind, complete in (('Program', False), ('Claude-Handover', True)):
        target = DIST / f'Oggcultist-{version}-{kind}.zip'
        make_archive(target, complete)
        result.append(target)
    sums = DIST / f'Oggcultist-{version}-SHA256SUMS.txt'
    sums.write_text(''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n' for p in result),encoding='ascii')
    print('Checksums:', sums)


if __name__ == '__main__':
    main()
