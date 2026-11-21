"""0.4.9.9: install experience on every Linux family, the menu entry, and the setup window.

    xvfb-run -a python3 Application/Tests/test_install_0499.py

Before 0.4.9.9 the Linux launcher and the setup window only knew apt: on
Fedora (and Arch, openSUSE) a missing Tk or FFmpeg could not be installed,
and every message said "Linux Mint".
"""
from pathlib import Path
import os
import runpy
import subprocess
import sys
import tempfile
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
BUILD = HERE.parent.parent
RUNTIME = HERE.parent / 'Runtime'
START = BUILD / 'START MARBLE ORACLE - LINUX.sh'
sys.path.insert(0, str(RUNTIME / 'Marble_Oracle_App'))

failures = []
checks = 0


def check(name, ok, detail=''):
    global checks
    checks += 1
    if not ok:
        failures.append(name)
        print('FAIL', name, detail, flush=True)


SAMPLES = {
    'fedora': 'NAME="Fedora Linux"\nID=fedora\nVERSION_ID=41\nVARIANT_ID=kde\n',
    'debian': 'NAME="Linux Mint"\nID=linuxmint\nID_LIKE="ubuntu debian"\n',
    'arch': 'NAME="Arch Linux"\nID=arch\n',
    'suse': 'NAME="openSUSE Tumbleweed"\nID="opensuse-tumbleweed"\nID_LIKE="opensuse suse"\n',
    None: 'NAME=NixOS\nID=nixos\n',
}
folder = Path(tempfile.mkdtemp(prefix='mo-install-'))
files = {}
for family, text in SAMPLES.items():
    path = folder / f'os-release-{family}'
    path.write_text(text)
    files[family] = path

boot = runpy.run_path(str(RUNTIME / 'launch_suite.pyw'), run_name='install_test')

# ---- which family -------------------------------------------------------
for family, path in files.items():
    check(f'{family}: recognised from os-release', boot['linux_family'](str(path)) == family,
          boot['linux_family'](str(path)))

# ---- the exact privileged command --------------------------------------------
tools = {'pkexec': '/usr/bin/pkexec', 'dnf': '/usr/bin/dnf', 'apt-get': '/usr/bin/apt-get',
         'pacman': '/usr/bin/pacman', 'zypper': '/usr/bin/zypper'}
pick = boot['linux_media_command']
with patch('shutil.which', side_effect=lambda name: tools.get(name)):
    command, method = pick('ffmpeg', family='fedora')
    check('Fedora installs ffmpeg-free with dnf through Polkit',
          command == ['/usr/bin/pkexec', '/usr/bin/dnf', 'install', '-y', 'ffmpeg-free'], command)
    check('and says so', 'Fedora' in method, method)
    check('Fedora needs no python3-venv package', pick('python3-venv', family='fedora')[0] is None)
    command, _ = pick('tk', family='fedora')
    check('Fedora Tk is python3-tkinter', command[-1] == 'python3-tkinter', command)
    command, _ = pick('python3-venv', family='debian')
    check('Mint still gets python3-venv with apt-get',
          command == ['/usr/bin/pkexec', '/usr/bin/apt-get', 'install', '-y', 'python3-venv'], command)
    command, _ = pick('ffmpeg', family='arch')
    check('Arch uses pacman', command[:3] == ['/usr/bin/pkexec', '/usr/bin/pacman', '-S'] and command[-1] == 'ffmpeg',
          command)
    command, _ = pick('ffmpeg', family='suse')
    check('openSUSE uses zypper', command[1] == '/usr/bin/zypper' and command[-1] == 'ffmpeg', command)
try:
    pick('rm -rf /', family='fedora')
    refused = False
except ValueError:
    refused = True
check('anything but the known packages is refused', refused)
with patch('shutil.which', side_effect=lambda name: {'pkcon': '/usr/bin/pkcon'}.get(name)):
    command, method = pick('ffmpeg', family='fedora')
    check('without pkexec, PackageKit is used with the Fedora name',
          command == ['/usr/bin/pkcon', '--plain', '-y', 'install', 'ffmpeg-free'], command)
hint = boot['linux_install_hint']
check('the typed hint for Fedora', hint('ffmpeg', family='fedora') == 'sudo dnf install ffmpeg-free',
      hint('ffmpeg', family='fedora'))
check('the typed hint for Mint', hint('ffmpeg', family='debian') == 'sudo apt-get install ffmpeg',
      hint('ffmpeg', family='debian'))
check('an unknown distribution gets plain words, not a wrong command',
      'software manager' in hint('ffmpeg', family='unknown'))
source = (RUNTIME / 'launch_suite.pyw').read_text(encoding='utf-8')
check('no message assumes Linux Mint any more',
      'On Linux Mint' not in source and 'Linux Mint Software Manager' not in source)

# ---- the shell launcher sees the same families -----------------------------
expected = {'fedora': 'Fedora|dnf install -y|python3 python3-tkinter',
            'debian': 'Debian / Ubuntu / Linux Mint|apt-get install -y|python3 python3-tk python3-venv',
            'arch': 'Arch Linux|pacman -S --needed --noconfirm|python tk',
            'suse': 'openSUSE|zypper --non-interactive install|python3 python3-tk',
            None: 'your Linux distribution||'}
for family, path in files.items():
    env = dict(os.environ, MARBLE_ORACLE_PRINT_DISTRO='1', MARBLE_ORACLE_OS_RELEASE=str(path))
    out = subprocess.run(['bash', str(START)], env=env, capture_output=True, text=True, timeout=30).stdout.strip()
    check(f'START (Linux) recognises {family}', out == expected[family], out)

# ---- the applications-menu entry -------------------------------------------
data_home = Path(tempfile.mkdtemp(prefix='mo-xdg-'))
env = dict(os.environ, XDG_DATA_HOME=str(data_home))
done = subprocess.run(['bash', str(RUNTIME / 'install_linux_desktop.sh')], env=env, capture_output=True, text=True,
                      timeout=60)
entry = data_home / 'applications' / 'marble-oracle.desktop'
check('the menu entry is written', done.returncode == 0 and entry.is_file(), done.stderr)
text = entry.read_text() if entry.is_file() else ''
for line in ('Terminal=false', 'StartupWMClass=MarbleOracle', 'Name=Marble Oracle', 'Icon='):
    check(f'the menu entry has {line}', line in text, text)
check('it starts the official launcher', 'START MARBLE ORACLE - LINUX.sh' in text)
done = subprocess.run(['bash', str(RUNTIME / 'install_linux_desktop.sh'), '--remove'], env=env, capture_output=True,
                      text=True, timeout=60)
check('--remove takes it out again', done.returncode == 0 and not entry.exists(), done.stderr)

# ---- the setup window -------------------------------------------------------
if os.environ.get('DISPLAY') or os.name == 'nt':
    PYS = {'pillow': {'ok': True, 'version': '12.2.0'}, 'mutagen': {'ok': True, 'version': '1.48'}}
    ALL = {'ffmpeg': True, 'ffprobe': True, 'ffplay': True}
    accent = boot['OGG_EMBER']['accent'].lower()

    def make(ready):
        with patch.dict(boot['Setup'].__init__.__globals__, {
                'runtime_choice': lambda: (Path(sys.executable) if ready else None, PYS if ready else {}),
                'media_tools': lambda: ALL}):
            window = boot['Setup']()
            window.update()
            return window

    def fits_at_minimum(window, label):
        # At the smallest size the window allows, no button may leave it or overlap another.
        width, height = window.minsize()
        window.geometry(f'{width}x{height}')
        for _ in range(5):
            window.update()
        buttons = [w for w in (window.start_btn, window.install_btn, getattr(window, 'menu_btn', None)) if w]
        boxes = [(b.winfo_rootx() - window.winfo_rootx(), b.winfo_rooty() - window.winfo_rooty(),
                  b.winfo_width(), b.winfo_height()) for b in buttons]
        inside = all(x >= 0 and y >= 0 and x + w <= window.winfo_width() and y + h <= window.winfo_height()
                     for x, y, w, h in boxes)
        apart = all(a[0] + a[2] <= b[0] or b[0] + b[2] <= a[0] or a[1] + a[3] <= b[1] or b[1] + b[3] <= a[1]
                    for i, a in enumerate(boxes) for b in boxes[i + 1:])
        whole = all(b.winfo_width() >= b.winfo_reqwidth() for b in buttons)   # Tk squeezes rather than overlaps
        check(f'{label}: at {width}x{height} every button is whole, inside the window and apart from the others',
              inside and apart and whole, [(b.cget('text'), b.winfo_width(), b.winfo_reqwidth()) for b in buttons])

    window = make(True)
    fits_at_minimum(window, 'ready')
    check('ready: START is the bright button', str(window.start_btn.cget('bg')).lower() == accent)
    check('ready: INSTALL is quiet', str(window.install_btn.cget('bg')).lower() != accent)
    check('idle: no progress bar is shown', not window.progress.winfo_manager())
    check('installed FFmpeg: its install option is hidden', not window.media_opt.winfo_manager())
    if sys.platform.startswith('linux'):
        check('Linux: an ADD TO APP MENU button', hasattr(window, 'menu_btn'))
    window._setbusy(True)
    window.update()
    check('busy: the progress bar appears', bool(window.progress.winfo_manager()))
    window._setbusy(False)
    window.destroy()
    window = make(False)
    fits_at_minimum(window, 'not ready')
    check('not ready: INSTALL is the bright button', str(window.install_btn.cget('bg')).lower() == accent)
    check('not ready: START is disabled', str(window.start_btn.cget('state')) == 'disabled')
    window.destroy()

print(f'INSTALL 0.4.9.9: {checks - len(failures)}/{checks} checks passed')
sys.exit(1 if failures else 0)
