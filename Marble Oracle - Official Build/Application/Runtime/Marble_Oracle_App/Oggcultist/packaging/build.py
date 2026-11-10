"""Reproducible build of the portable Oggcultist executable (Python only, no PowerShell).

Usage, from the project folder, in a clean virtual environment::

    python -m pip install -r requirements.txt -r packaging/requirements-build.txt
    python packaging/build.py                      # dist/Oggcultist(.exe) + portable ZIP
    python packaging/build.py --bundle-tools C:\\ffmpeg\\bin   # also embed FFmpeg (see PACKAGING.md)
    python packaging/build.py --onedir              # folder build (faster start-up)

PyInstaller does not cross-compile: run this on Windows to get a Windows .exe.
On Linux it produces a Linux executable, which is useful for checking the
frozen-application code paths.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import platform
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def project_version() -> str:
    text = (ROOT / 'oggcultist' / '__init__.py').read_text(encoding='utf-8')
    return re.search(r"__version__ = '([^']+)'", text).group(1)


def check_versions(version: str) -> None:
    problems = []
    if f'version = "{version}"' not in (ROOT / 'pyproject.toml').read_text(encoding='utf-8'):
        problems.append('pyproject.toml')
    info = (ROOT / 'packaging' / 'windows' / 'version_info.txt').read_text(encoding='utf-8')
    parts = [int(n) for n in version.split('.')]
    numbers = ', '.join(str(n) for n in parts + [0] * (4 - len(parts)))
    for expected in (f'filevers=({numbers})', f"StringStruct('FileVersion', '{version}')",
                     f"StringStruct('ProductVersion', '{version}')"):
        if expected not in info:
            problems.append(f'packaging/windows/version_info.txt ({expected})')
    if problems:
        raise SystemExit(f'Version {version} is not consistent in: ' + ', '.join(problems))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--onedir', action='store_true', help='build a folder instead of one executable')
    parser.add_argument('--bundle-tools', metavar='DIR', help='folder containing ffmpeg, ffprobe and ffplay to embed')
    parser.add_argument('--dist', default=str(ROOT / 'dist'), help='output folder (default: dist)')
    args = parser.parse_args(argv)

    version = project_version()
    check_versions(version)
    # Distribution gate: never build without the bundled fonts, byte-exact.
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from oggcultist import fonts as app_fonts
    app_fonts.require_complete_bundle(strict=True)
    dist = Path(args.dist).resolve()
    work = ROOT / 'build' / 'pyinstaller'
    env = dict(os.environ)
    env['OGGCULTIST_ONEDIR'] = '1' if args.onedir else '0'
    if args.bundle_tools:
        env['OGGCULTIST_BUNDLE_TOOLS'] = str(Path(args.bundle_tools).resolve())
    else:
        env.pop('OGGCULTIST_BUNDLE_TOOLS', None)
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    command = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean',
               '--distpath', str(dist), '--workpath', str(work), str(ROOT / 'packaging' / 'oggcultist.spec')]
    print('Running:', ' '.join(command), flush=True)
    subprocess.run(command, cwd=str(ROOT), env=env, check=True)

    exe_name = 'Oggcultist.exe' if sys.platform == 'win32' else 'Oggcultist'
    built = dist / 'Oggcultist' / exe_name if args.onedir else dist / exe_name
    if not built.is_file():
        raise SystemExit(f'Build finished but {built} was not produced.')

    system = {'win32': 'windows', 'darwin': 'macos'}.get(sys.platform, sys.platform)
    arch = platform.machine().lower().replace('amd64', 'x64').replace('x86_64', 'x64')
    tools = '-with-ffmpeg' if args.bundle_tools else ''
    archive = dist / f'Oggcultist-{version}-{system}-{arch}{tools}-portable.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
        if args.onedir:
            for path in sorted((dist / 'Oggcultist').rglob('*')):
                if path.is_file():
                    z.write(path, Path('Oggcultist') / path.relative_to(dist / 'Oggcultist'))
        else:
            z.write(built, f'Oggcultist/{exe_name}')
        z.write(ROOT / 'LICENSE', 'Oggcultist/LICENSE.txt')
        z.write(ROOT / 'packaging' / 'PORTABLE_README.txt', 'Oggcultist/README.txt')
        if args.bundle_tools:
            notice = Path(args.bundle_tools) / 'LICENSE.txt'
            if notice.is_file():
                z.write(notice, 'Oggcultist/FFMPEG-LICENSE.txt')
    sums = dist / 'SHA256SUMS.txt'
    lines = [f'{sha256(p)}  {p.name}' for p in (built, archive)]
    sums.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('\n'.join(['', 'Built:', f'  {built}', f'  {archive}', f'  {sums}']))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
