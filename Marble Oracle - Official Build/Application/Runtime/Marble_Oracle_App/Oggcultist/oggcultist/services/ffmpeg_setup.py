"""First-run FFmpeg installer for Oggcultist (stdlib only).

Windows: verify HTTPS-delivered Gyan Essentials ZIP against its published SHA-256,
extract only ffmpeg.exe and ffprobe.exe into the user's LOCALAPPDATA, and add the
private bin directory to the launched process's PATH. Does not require admin.
Linux Mint/Ubuntu: offer installation through the system apt package manager.
No download or installation happens without consent. No media files are touched.
"""
from __future__ import annotations

import hashlib
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile

from .. import __version__
from .. import paths as _paths
from pathlib import Path

FFMPEG_BASE = 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip'
MAX_ARCHIVE_BYTES = 300 * 1024 * 1024
MAX_BINARY_BYTES = 180 * 1024 * 1024


class SetupError(RuntimeError):
    """An FFmpeg setup step did not complete."""


def local_bin(platform: str | None = None, env: dict | None = None) -> Path:
    """Oggcultist's private FFmpeg folder (portable-aware; unchanged default location)."""
    return _paths.private_tools_dir(os.environ if env is None else env, platform or sys.platform)


def add_local_to_path(bin_dir: Path, env: dict | None = None) -> None:
    env = os.environ if env is None else env
    old = env.get('PATH', '')
    if str(bin_dir).casefold() not in [p.casefold() for p in old.split(os.pathsep)]:
        env['PATH'] = str(bin_dir) + os.pathsep + old


def binaries_available(platform: str | None = None, which=None) -> bool:
    platform = platform or sys.platform
    which = which or shutil.which
    suffix = '.exe' if platform == 'win32' else ''
    # A pair is required: the application uses both programs.
    return all(which(name + suffix) for name in ('ffmpeg', 'ffprobe'))


def _get_bytes(url: str, max_bytes: int, opener=None) -> bytes:
    opener = opener or urllib.request.urlopen
    request = urllib.request.Request(url, headers={'User-Agent': f'Oggcultist-FFmpeg-Setup/{__version__}'})
    try:
        with opener(request, timeout=90) as response:
            result = bytearray()
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                result.extend(chunk)
                if len(result) > max_bytes:
                    raise SetupError('FFmpeg download exceeded the allowed size.')
            return bytes(result)
    except SetupError:
        raise
    except Exception as exc:
        raise SetupError(f'Could not download FFmpeg from {url}: {exc}') from exc


def _expected_sha(text: bytes) -> str:
    match = re.search(rb'(?<![0-9a-fA-F])[0-9a-fA-F]{64}(?![0-9a-fA-F])', text)
    if not match:
        raise SetupError('FFmpeg publisher did not provide a usable SHA-256 checksum.')
    return match.group().decode('ascii').lower()


def download_verified_archive(opener=None) -> bytes:
    """Refuse unverified or unexpectedly large remote executables."""
    expected = _expected_sha(_get_bytes(FFMPEG_BASE + '.sha256', 16 * 1024, opener))
    archive = _get_bytes(FFMPEG_BASE, MAX_ARCHIVE_BYTES, opener)
    actual = hashlib.sha256(archive).hexdigest()
    if actual != expected:
        raise SetupError('FFmpeg SHA-256 verification failed. No executable was installed.')
    return archive


def install_windows(archive: bytes, bin_dir: Path, filenames: tuple[str, ...] = ('ffmpeg.exe', 'ffprobe.exe')) -> Path:
    """Extract only the matching executable pair; install in an app-owned user dir."""
    try:
        with zipfile.ZipFile(io.BytesIO(archive)) as zf:
            members = {}
            for name in filenames:
                if name not in ('ffmpeg.exe', 'ffprobe.exe', 'ffplay.exe'):
                    raise SetupError('Invalid FFmpeg executable requested.')
                candidates = [zi for zi in zf.infolist() if zi.filename.replace('\\', '/').lower().endswith('/bin/' + name)
                              and not zi.is_dir()]
                if len(candidates) != 1 or not 0 < candidates[0].file_size <= MAX_BINARY_BYTES:
                    raise SetupError(f'The official FFmpeg ZIP does not contain one valid {name}.')
                members[name] = candidates[0]
            parent = bin_dir.parent
            parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix='ffmpeg-install-', dir=parent) as scratch:
                stage = Path(scratch)
                for name, member in members.items():
                    with zf.open(member) as source, open(stage / name, 'wb') as target:
                        shutil.copyfileobj(source, target, 1024 * 1024)
                # Both files must be extracted successfully before publishing any of them.
                bin_dir.mkdir(parents=True, exist_ok=True)
                for name in filenames:
                    os.replace(stage / name, bin_dir / name)
    except (zipfile.BadZipFile, OSError) as exc:
        raise SetupError(f'Could not install FFmpeg binaries: {exc}') from exc
    return bin_dir


def _consent(question: str, input_fn=input) -> bool:
    try:
        answer = input_fn(question).strip().lower()
    except (EOFError, OSError, KeyboardInterrupt):
        return False
    return answer in ('', 'y', 'yes')


def ensure_ffmpeg(platform: str | None = None, input_fn=input, print_fn=print,
                  opener=None, check_fn=None, run_fn=None, env: dict | None = None,
                  on_installed=None) -> bool:
    """Return True iff both tools are available to Oggcultist in this process.

    Does not auto-install in unattended sessions; the user must be able to
    confirm the download or system-package installation interactively.
    """
    platform = platform or sys.platform
    env = os.environ if env is None else env
    add_local_to_path(local_bin(platform, env), env)
    check_fn = check_fn or binaries_available
    if check_fn(platform):
        print_fn('FFmpeg and FFprobe are available.')
        return True
    if platform == 'win32':
        print_fn('FFmpeg / FFprobe not found. Oggcultist can install its own private copy.')
        print_fn('Source: gyan.dev (official Windows build). SHA-256 is verified.')
        print_fn('The files will be installed only in your Windows user profile; no admin or PATH changes.')
        if not _consent('Install FFmpeg for Oggcultist now? [Y/n]: ', input_fn):
            print_fn('Installation declined. Audio conversion requires FFmpeg and FFprobe.')
            return False
        try:
            archive = download_verified_archive(opener)
            install_windows(archive, local_bin(platform, env))
            # FFplay powers the optional built-in music player. An older or
            # unusual archive may lack it; conversion must still work.
            try:
                install_windows(archive, local_bin(platform, env), filenames=('ffplay.exe',))
            except SetupError:
                print_fn('FFplay was not included; the music player can offer to install it later.')
        except (SetupError, OSError) as exc:
            print_fn(f'FFmpeg installation failed: {exc}')
            print_fn('Manual alternative: https://www.gyan.dev/ffmpeg/builds/')
            return False
        # The current process (and its child launch.py) will see the local bin in PATH.
        if check_fn(platform):
            print_fn('FFmpeg installed successfully. Launching Oggcultist.')
            if on_installed is not None:
                on_installed()
            return True
        print_fn('The files were downloaded, but FFmpeg could not be detected. Please restart Oggcultist.')
        return False
    if platform.startswith('linux'):
        if not shutil.which('apt-get'):
            print_fn('FFmpeg missing. Install ffmpeg and ffprobe using your Linux package manager.')
            return False
        print_fn('FFmpeg is missing. Linux Mint/Ubuntu can install it with apt.')
        if not _consent('Install FFmpeg through the system package manager? [Y/n]: ', input_fn):
            return False
        runner = run_fn or subprocess.run
        command = ['apt-get', 'install', '-y', 'ffmpeg']
        if hasattr(os, 'geteuid') and os.geteuid() != 0:
            if not shutil.which('sudo'):
                print_fn('sudo is unavailable. Please run: sudo apt install ffmpeg')
                return False
            command.insert(0, 'sudo')
        try:
            status = runner(command, check=False)
        except OSError as exc:
            print_fn(f'Could not start package installer: {exc}')
            return False
        if status.returncode == 0 and check_fn(platform):
            print_fn('FFmpeg is installed.')
            return True
        print_fn('FFmpeg installation did not complete. Run: sudo apt install ffmpeg')
        return False
    print_fn('FFmpeg missing. Install ffmpeg and ffprobe using your OS package manager.')
    return False



def ensure_ffplay(platform: str | None = None, input_fn=input, print_fn=print,
                  opener=None, check_fn=None, env: dict | None = None,
                  on_installed=None) -> bool:
    """Offer FFplay during desktop startup; never download without consent.

    Reuse an installed FFplay, including Oggcultist's private user-profile
    binary. Never touch existing ffmpeg.exe or ffprobe.exe when installing.
    A declined/failed player install must not prevent audio conversion.
    """
    platform = platform or sys.platform
    env = os.environ if env is None else env
    target = local_bin(platform, env) if platform == 'win32' else None
    if target is not None:
        add_local_to_path(target, env)
    if check_fn is None:
        suffix = '.exe' if platform == 'win32' else ''
        check_fn = lambda _: bool(shutil.which('ffplay' + suffix) or
                                  (target is not None and (target / ('ffplay' + suffix)).is_file()))
    if check_fn(platform):
        print_fn('FFplay is available. Music playback is ready.')
        return True
    if platform == 'win32':
        print_fn('FFplay is missing. It is required to play audio in Oggcultist.')
        print_fn('Install from the checksum-verified Gyan FFmpeg Essentials archive (user profile only).')
        if not _consent('Install FFplay for music playback now? [Y/n]: ', input_fn):
            print_fn('FFplay setup declined; the player can offer it again when you press Play.')
            return False
        try:
            archive = download_verified_archive(opener)
            install_windows(archive, target, filenames=('ffplay.exe',))
        except (SetupError, OSError) as exc:
            print_fn(f'FFplay installation failed: {exc}')
            return False
        if check_fn(platform):
            print_fn('FFplay installed successfully. Music playback is ready.')
            if on_installed is not None:
                on_installed()
            return True
        print_fn('FFplay was extracted but could not be detected; use the diagnostic launcher.')
        return False
    if platform.startswith('linux'):
        print_fn('FFplay is missing. On Linux Mint/Ubuntu install it with: sudo apt install ffmpeg')
        return False
    print_fn('FFplay is missing; install FFplay to enable music playback.')
    return False

def main() -> int:
    # First-run setup is called from the launchers; dry-run CLI mode does not
    # need FFmpeg and never triggers installation.
    return 0 if ensure_ffmpeg() else 1


if __name__ == '__main__':
    raise SystemExit(main())
