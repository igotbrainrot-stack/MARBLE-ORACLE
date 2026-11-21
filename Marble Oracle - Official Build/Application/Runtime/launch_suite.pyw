"""First-start graphical requirements manager for the Marble Oracle suite.

The suite itself is unchanged. This launcher prompts *before* installing
anything, installs Python dependencies in a private venv, then starts the
real application without a console. FFmpeg installation is separate because
it is an operating-system tool, not a Python module.
"""
from __future__ import annotations

import hashlib
import uuid
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import threading
import time
import traceback
import tkinter as tk
from tkinter import ttk, messagebox

# The graphical setup follows the suite's custom Uberata typeface.
sys.path.insert(0, str(Path(__file__).resolve().parent / 'Marble_Oracle_App'))
from marble_uberata import FAMILY, apply_tk_fonts
from oggcultist_design_system import COLOR as OGG_EMBER

APP_DIR = Path(__file__).resolve().parent
MAIN = APP_DIR / 'Marble_Oracle.pyw'
OGG_ROOT = APP_DIR / 'Marble_Oracle_App' / 'Oggcultist'
SUITE_ID = hashlib.sha256(str(APP_DIR.resolve()).encode('utf-8')).hexdigest()[:12]
LOCAL_DATA = (Path(os.environ.get('LOCALAPPDATA') or Path.home() / 'AppData' / 'Local')
              if os.name == 'nt' else Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local' / 'share'))
STATE_DIR = LOCAL_DATA / 'MarbleOracleSuite' / SUITE_ID
VENV_DIR = STATE_DIR / 'venv'
MENU_INSTALLER = APP_DIR / 'install_linux_desktop.sh'
MENU_ENTRY = Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local' / 'share') / 'applications' / 'marble-oracle.desktop'
STATE_FILE = STATE_DIR / 'first_run.json'
LOG_FILE = STATE_DIR / 'requirements-install.log'
STARTUP_LOG = STATE_DIR / 'startup.log'
SETUP_ERROR_LOG = STATE_DIR / 'setup-errors.log'
CORE_PACKAGES = ('Pillow>=10,<13', 'mutagen>=1.47,<2')
# Media-key support is optional: requiring it used to block Oracle itself
# when a Linux-specific integration could not be installed.
OPTIONAL_PACKAGES = ('numpy>=1.26', 'opencv-python-headless>=4.9')
if sys.platform.startswith('linux'):
    OPTIONAL_PACKAGES += ('jeepney>=0.8,<1',)
if sys.platform == 'win32':
    OPTIONAL_PACKAGES += ('soundcard>=0.4.3',)
PROBE_CODE = """
import json, importlib, importlib.metadata, sys
modules = {'pillow': 'PIL.ImageTk', 'mutagen':'mutagen', 'jeepney':'jeepney',
           'numpy':'numpy','opencv':'cv2','soundcard':'soundcard'}
results = {}
for name, module in modules.items():
    try:
        importlib.import_module(module)
        ver = importlib.metadata.version('Pillow' if name=='pillow' else 'opencv-python-headless' if name=='opencv' else name)
        digits = tuple(int(''.join(x for x in part if x.isdigit()) or '0') for part in ver.split('.')[:2])
        bounds = {'pillow':((10,0),(13,0)), 'mutagen':((1,47),(2,0)),
                  'jeepney':((0,8),(1,0))}
        lo, hi = bounds.get(name, ((0,0),(10000,0)))
        results[name] = {'ok':lo<=digits<hi,'version':ver}
    except Exception as exc:
        results[name] = {'ok':False,'reason':str(exc)[:180]}
print(json.dumps(results))
"""


def configure_media_path():
    sys.path.insert(0, str(OGG_ROOT))
    from oggcultist.paths import configure_tool_path
    configure_tool_path()


def media_tools():
    """Check availability without risking a fatal setup crash.

    A corrupt Oggcultist tools folder must not prevent core Marble Oracle
    from opening. Missing media tools are reported as optional instead.
    """
    try:
        configure_media_path()
    except (ImportError, OSError, ValueError, RuntimeError):
        pass
    return {name:bool(shutil.which(name)) for name in ('ffmpeg','ffprobe','ffplay')}


def venv_python(root=VENV_DIR):
    if sys.platform == 'win32':
        return root/'Scripts'/'python.exe'
    return root/'bin'/'python'


def console_python(executable):
    executable=Path(executable)
    if os.name == 'nt' and executable.name.lower()=='pythonw.exe':
        candidate=executable.with_name('python.exe')
        if candidate.is_file(): return candidate
    return executable


def hidden_process_options():
    """Do not create a Command Prompt for installers, probes, or media utilities.

    Windows GUI applications need both a no-console creation flag and a
    hidden startup state for tools that launch a secondary process. Linux
    doesn't use these Windows process flags at all.
    """
    if os.name != 'nt':
        return {}
    info = subprocess.STARTUPINFO()
    info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    info.wShowWindow = subprocess.SW_HIDE
    return {'creationflags': getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000),
            'startupinfo': info}


def run_hidden(cmd, **kwargs):
    return subprocess.run(cmd, **hidden_process_options(), **kwargs)


def inspect_python(executable):
    try:
        result = run_hidden([str(console_python(executable)), '-c', PROBE_CODE], timeout=20,
                            check=False, capture_output=True, text=True)
        if result.returncode:
            return {}, (result.stderr or result.stdout or 'Unable to inspect Python environment')[-600:]
        return json.loads(result.stdout.strip().splitlines()[-1]), None
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        return {}, str(exc)


def core_ok(status):
    required = ('pillow','mutagen')
    return all(status.get(k,{}).get('ok',False) for k in required)


def runtime_choice():
    vp = venv_python()
    if vp.is_file():
        vs, err = inspect_python(vp)
        if not err and core_ok(vs):
            return vp,vs
    ss,err = inspect_python(sys.executable)
    if not err and core_ok(ss):
        return Path(sys.executable),ss
    return None,ss


def load_state():
    try:
        d=json.loads(STATE_FILE.read_text('utf-8'))
        return d if isinstance(d,dict) else {}
    except (OSError,ValueError):
        return {}


def save_state():
    STATE_DIR.mkdir(parents=True,exist_ok=True)
    tmp=STATE_FILE.with_suffix('.tmp')
    tmp.write_text(json.dumps({'completed':True,'created':time.strftime('%Y-%m-%d %H:%M:%S')},indent=2),encoding='utf-8')
    os.replace(tmp,STATE_FILE)


def requirements_snapshot():
    """Always recheck *actual* imports and media tools before launching."""
    interpreter, python_status = runtime_choice()
    available = media_tools()
    missing_media = [name for name, ok in available.items() if not ok]
    return interpreter, python_status, available, missing_media


def launch_main(python, extra=()):
    """Start the GUI with a real startup handshake and a persistent error log.

    Merely spawning a child process used to be treated as success: rapid child
    crashes then looked like 'nothing happens' when the windowless launcher was
    used. The child signals readiness after its initial window render instead.
    """
    if not MAIN.is_file():
        raise FileNotFoundError('Application/Runtime/Marble_Oracle.pyw is missing. Extract the complete ZIP.')
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    python = Path(python)
    if os.name == 'nt':
        gui_py = python.with_name('pythonw.exe')
        if gui_py.exists():
            python = gui_py
    ready_file = STATE_DIR / ('startup-ready-' + uuid.uuid4().hex + '.flag')
    cmd = [str(python), str(MAIN), *extra]
    try:
        configure_media_path()
    except (ImportError, OSError, ValueError, RuntimeError):
        pass
    env = os.environ.copy()
    env['MARBLE_ORACLE_READY_FILE'] = str(ready_file)
    # Distinguish an intentional window close from a crash that happened to
    # return status 0 (for example a Tk rendering failure).
    env['MARBLE_ORACLE_EXIT_FILE'] = str(ready_file.with_name(
        ready_file.name.replace('startup-ready-', 'startup-exit-')))
    with STARTUP_LOG.open('w', encoding='utf-8', errors='replace') as logfile:
        logfile.write('Starting Marble Oracle from ' + str(MAIN) + '\n')
        logfile.flush()
        proc = subprocess.Popen(cmd, cwd=str(APP_DIR), env=env,
                                stdin=subprocess.DEVNULL, stdout=logfile,
                                stderr=subprocess.STDOUT,
                                close_fds=True,
                                # Linux desktop launchers may terminate their
                                # process group when the setup app exits.
                                # Isolate Oracle so that it stays alive.
                                **({'start_new_session': True} if os.name != 'nt' else {}),
                                **hidden_process_options())
    return proc, ready_file


def install_venv(out_queue, include_optional):
    try:
        STATE_DIR.mkdir(parents=True,exist_ok=True)
        out_queue.put(('log','Creating a private Python environment (no system Python changes)...'))
        venv_cmd=[str(console_python(sys.executable)),'-m','venv',str(VENV_DIR)]
        proc=run_hidden(venv_cmd,capture_output=True,text=True,timeout=150)
        if proc.returncode and sys.platform.startswith('linux'):
            venv_error=(proc.stderr or '')+'\n'+(proc.stdout or '')
            # Ubuntu/Mint commonly lack ensurepip until python3-venv is installed.
            # Only ask for an OS change if that exact prerequisite is implicated.
            if any(word in venv_error.lower() for word in ('ensurepip','python3-venv','no module named venv')):
                command, method=linux_media_command('python3-venv')
                if command:
                    out_queue.put(('log','Python virtual-environment support is missing; requesting administrator permission for python3-venv using '+method+'...'))
                    system_result=run_hidden(command,capture_output=True,text=True,timeout=900)
                    if system_result.returncode:
                        detail=(system_result.stderr or system_result.stdout or 'authorization declined')[-1000:]
                        raise RuntimeError('Could not install python3-venv: '+detail)
                    out_queue.put(('log','python3-venv installed; retrying private environment creation...'))
                    proc=run_hidden(venv_cmd,capture_output=True,text=True,timeout=150)
        if proc.returncode:
            detail=(proc.stderr or proc.stdout or 'venv creation failed')[-1800:]
            raise RuntimeError('Cannot create Python environment. '+detail+
                               ('\nOn Linux: ' + linux_install_hint('python3-venv') + '.'
                                if sys.platform.startswith('linux') else ''))
        python=venv_python()
        args=[str(python),'-m','pip','install','--disable-pip-version-check',
              '--no-input',*CORE_PACKAGES]
        if include_optional: args.extend(OPTIONAL_PACKAGES)
        out_queue.put(('log','Installing '+', '.join(CORE_PACKAGES) + (' and optional enhancements' if include_optional else '')+'...'))
        proc=run_hidden(args,capture_output=True,text=True,timeout=600)
        LOG_FILE.write_text('Command: python -m pip install [requirements]\n'+proc.stdout+'\n'+proc.stderr,encoding='utf-8')
        if proc.returncode:
            raise RuntimeError('Package installation failed. Check '+str(LOG_FILE)+'\n'+proc.stderr[-1000:])
        results,error=inspect_python(python)
        if error or not core_ok(results):
            raise RuntimeError('Installed packages could not be imported: '+str(error or results))
        out_queue.put(('log','Python requirements installed and import-checked successfully.'))
        out_queue.put(('python-ok',str(python)))
    except (OSError,subprocess.TimeoutExpired,RuntimeError) as exc:
        out_queue.put(('error',str(exc)))


# Linux families and their package names for the few things setup may install.
# Only these names can ever be passed to a package manager (never free text).
LINUX_FAMILIES = {
    'debian': {'label': 'Debian / Ubuntu / Linux Mint', 'manager': ('apt-get', 'install', '-y'),
               'ffmpeg': ('ffmpeg',), 'python3-venv': ('python3-venv',), 'tk': ('python3-tk',)},
    'fedora': {'label': 'Fedora', 'manager': ('dnf', 'install', '-y'),
               'ffmpeg': ('ffmpeg-free',), 'python3-venv': (), 'tk': ('python3-tkinter',)},
    'arch':   {'label': 'Arch Linux', 'manager': ('pacman', '-S', '--needed', '--noconfirm'),
               'ffmpeg': ('ffmpeg',), 'python3-venv': (), 'tk': ('tk',)},
    'suse':   {'label': 'openSUSE', 'manager': ('zypper', '--non-interactive', 'install'),
               'ffmpeg': ('ffmpeg',), 'python3-venv': (), 'tk': ('python3-tk',)},
}


def linux_family(os_release='/etc/os-release'):
    """'debian', 'fedora', 'arch', 'suse' or None, from /etc/os-release ID and ID_LIKE."""
    try:
        text = Path(os_release).read_text(encoding='utf-8', errors='replace')
    except OSError:
        return None
    ids = []
    for line in text.splitlines():
        key, _, value = line.partition('=')
        if key in ('ID', 'ID_LIKE'):
            ids.extend(value.strip().strip('"').lower().split())
    for name in ids:
        if name in ('debian', 'ubuntu', 'linuxmint', 'pop', 'elementary', 'zorin'):
            return 'debian'
        if name in ('fedora', 'rhel', 'centos', 'nobara', 'ultramarine'):
            return 'fedora'
        if name in ('arch', 'manjaro', 'endeavouros', 'cachyos'):
            return 'arch'
        if name.startswith('opensuse') or name in ('suse', 'sles'):
            return 'suse'
    return None


def linux_install_hint(package='ffmpeg', family=None):
    """The command a person can type themselves, for error messages."""
    family = family if family is not None else linux_family()
    info = LINUX_FAMILIES.get(family)
    if not info or not info.get(package):
        return 'install ' + package + ' with your distribution\'s software manager'
    return 'sudo ' + ' '.join(info['manager'][:2] + tuple(info[package]))


def linux_media_command(package='ffmpeg', family=None):
    """The privileged install command for one known package, or (None, reason).

    Uses Polkit (pkexec) so the desktop shows its own password prompt; never
    sudo in a terminal. Falls back to PackageKit's pkcon with the same names.
    """
    if package not in ('ffmpeg', 'python3-venv', 'tk'):
        raise ValueError('Unsupported Linux setup package: '+str(package))
    family = family if family is not None else linux_family()
    info = LINUX_FAMILIES.get(family)
    names = tuple(info[package]) if info else ((package,) if package != 'tk' else ('python3-tk',))
    if info is not None and not names:
        return None, 'not needed on ' + info['label']
    pkexec = shutil.which('pkexec')
    if info is not None:
        manager = shutil.which(info['manager'][0])
        if manager and pkexec:
            return [pkexec, manager, *info['manager'][1:], *names], info['label'] + ' with Polkit'
    pkcon = shutil.which('pkcon')
    if pkcon:
        return [pkcon, '--plain', '-y', 'install', *names], 'PackageKit'
    return None, None


def install_ffmpeg(out_queue, *, runner=None, platform=None, check_tools=None,
                   command_picker=None):
    """Install FFmpeg, FFprobe and FFplay only after the setup button is clicked.

    The injectable helpers make the system installer independently testable
    without invoking privileged package installation during QA.
    """
    platform = platform or sys.platform
    check_tools = check_tools or media_tools
    runner = runner or run_hidden
    command_picker = command_picker or linux_media_command
    missing=[name for name,available in check_tools().items() if not available]
    if not missing:
        out_queue.put(('log','FFmpeg, FFprobe and FFplay are already available.'))
        return True
    out_queue.put(('log','Missing media tools: ' + ', '.join(missing)))
    if platform=='win32':
        out_queue.put(('log','Downloading publisher-checksum-verified FFmpeg from gyan.dev into your user profile...'))
        sys.path.insert(0,str(OGG_ROOT))
        from oggcultist.services.ffmpeg_setup import download_verified_archive,install_windows,local_bin,add_local_to_path
        archive=download_verified_archive()
        install_windows(archive,local_bin(),filenames=tuple(name+'.exe' for name in missing))
        add_local_to_path(local_bin())
    elif platform.startswith('linux'):
        command, method = command_picker()
        if not command:
            raise RuntimeError('No graphical package installer was found. Install FFmpeg with your '
                               'software manager, or in a terminal: ' + linux_install_hint('ffmpeg') +
                               '. Then reopen setup.')
        out_queue.put(('log',method+': requesting permission to install FFmpeg ('+' '.join(command[-1:])+')...'))
        out_queue.put(('log','Approve the administrator authentication dialog if it appears. No terminal is needed.'))
        try:
            result=runner(command, capture_output=True, text=True, timeout=1200)
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError('The package manager timed out. Check that the authentication prompt was answered.') from exc
        except OSError as exc:
            raise RuntimeError('Cannot start the Linux package manager: '+str(exc)) from exc
        if result.returncode:
            detail=(result.stderr or result.stdout or 'No installer details were returned')[-1400:].strip()
            if result.returncode==126 or 'not authorized' in detail.lower() or 'cancelled' in detail.lower():
                raise RuntimeError('Installation was declined or administrator authorization was unavailable. '
                                   'No changes were made by Marble Oracle. '+detail)
            raise RuntimeError(f'Linux FFmpeg installation failed (exit {result.returncode}): {detail}\n'
                               'You can also install it yourself: ' + linux_install_hint('ffmpeg') + '.')
    else:
        raise RuntimeError('Automatic FFmpeg installation is supported on Windows and Linux. '
                           'Use the operating system package manager on this platform.')
    remaining=[name for name,found in check_tools().items() if not found]
    if remaining:
        raise RuntimeError('Media installation finished, but these tools are still missing: '+', '.join(remaining)+
                           '. Check your package manager or rerun first-start setup.')
    out_queue.put(('log','FFmpeg, FFprobe and FFplay are installed and detected.'))
    return True


class Setup(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Marble Oracle — Requirements and Startup')
        self.geometry('780x720')
        self.minsize(760,640)   # every button and status badge fits at this width
        self.configure(bg='#1D1714')
        apply_tk_fonts(self)
        self._queue=queue.Queue()
        self.running=False
        self.launching=False
        self.child=None
        self.ready_file=None
        self.launch_deadline=0
        self._ready_seen_at=None
        self._ready_verified=False
        self._monitoring=False
        self._opened_at=None
        self.exit_file=None
        self._pump_after=None
        self.extras=tk.BooleanVar(self,value=False)
        self.media=tk.BooleanVar(self,value=not all(media_tools().values()))
        self.status=tk.StringVar(self,value='Checking installed components...')
        self._build()
        try:
            self.refresh()
        except Exception as exc:
            self._report_setup_error('Initial requirements check', exc)
        self._pump_after=self.after(125,self.pump)

    def destroy(self):
        # Cancel timers before destroying the setup Tk interpreter. Otherwise
        # an active ttk.Progressbar can throw Tcl errors after the handoff.
        try:
            self.progress.stop()
        except tk.TclError:
            pass
        if self._pump_after is not None:
            try: self.after_cancel(self._pump_after)
            except tk.TclError: pass
            self._pump_after=None
        super().destroy()

    # ---- look ------------------------------------------------------------
    # The suite's colours (oggcultist_design_system), spelled out once here.
    BG = OGG_EMBER['canvas']
    CARD = OGG_EMBER['raised']
    LINE = OGG_EMBER['control_line']
    TEXT = OGG_EMBER['text']
    MUTED = OGG_EMBER['text_3']
    ACCENT = OGG_EMBER['accent']
    GOOD = '#8FC98A'

    def _label(self,parent,text,size=11,fg=None,bold=False,bg=None,**kwargs):
        return tk.Label(parent,text=text,font=(FAMILY,size,'bold' if bold else 'normal'),
                        bg=bg or self.BG,fg=fg or self.TEXT,**kwargs)

    @staticmethod
    def _wrap_to_width(label):
        """Keep a label's text wrapped to the width it is given, so it never runs off the edge."""
        label.bind('<Configure>',lambda event:label.configure(wraplength=max(200,event.width-4)),add='+')

    def _button(self,parent,text,command,primary=False):
        return tk.Button(parent,text=text,command=command,cursor='hand2',relief='flat',bd=0,
                         font=(FAMILY,11,'bold'),padx=16,pady=8,
                         bg=self.ACCENT if primary else OGG_EMBER['control'],
                         fg=OGG_EMBER['text_on_accent'] if primary else self.TEXT,
                         activebackground=OGG_EMBER['accent_deep'] if primary else OGG_EMBER['hover'],
                         activeforeground=OGG_EMBER['text_on_accent'] if primary else self.TEXT,
                         disabledforeground=self.MUTED,highlightthickness=2,
                         highlightbackground=self.ACCENT if primary else self.LINE,
                         highlightcolor=OGG_EMBER['focus'])

    def _check(self,parent,text,variable):
        return tk.Checkbutton(parent,text=text,variable=variable,font=(FAMILY,10),cursor='hand2',
                              bg=self.CARD,fg=self.TEXT,selectcolor=OGG_EMBER['control'],
                              activebackground=self.CARD,activeforeground=OGG_EMBER['text_bright'],
                              highlightthickness=0,bd=0,anchor='w',justify='left')

    def _build(self):
        self.configure(bg=self.BG)
        style=ttk.Style(self)
        try:
            style.theme_use('clam')
        except tk.TclError:
            pass
        style.configure('Oracle.Horizontal.TProgressbar',troughcolor=self.CARD,background=self.ACCENT,
                        bordercolor=self.CARD,lightcolor=self.ACCENT,darkcolor=self.ACCENT,thickness=6)
        pad=tk.Frame(self,bg=self.BG,padx=26,pady=16)
        pad.pack(fill='both',expand=True)

        # Footer first, from the bottom: the buttons never leave the window.
        buttons=tk.Frame(pad,bg=self.BG)
        buttons.pack(side='bottom',fill='x',pady=(12,0))
        self.start_btn=self._button(buttons,'START MARBLE ORACLE',self.start,primary=True)
        self.start_btn.pack(side='right')
        self.install_btn=self._button(buttons,'INSTALL REQUIREMENTS',self.install)
        self.install_btn.pack(side='right',padx=(0,10))
        self._button(buttons,'EXIT',self.destroy).pack(side='left')

        head=tk.Frame(pad,bg=self.BG)
        head.pack(fill='x')
        self._label(head,'MARBLE ORACLE',22,fg=self.ACCENT,bold=True).pack(side='left')
        self._label(head,'SETUP',11,fg=self.MUTED,bold=True).pack(side='left',padx=12,pady=(10,0))
        if sys.platform.startswith('linux') and MENU_INSTALLER.is_file():
            # In the header, not the footer: the footer keeps room for its three buttons.
            self.menu_btn=self._button(head,'ADD TO APP MENU',self.add_to_menu)
            self.menu_btn.configure(font=(FAMILY,9,'bold'),padx=10,pady=4)
            self.menu_btn.pack(side='right',pady=(6,0))
            if MENU_ENTRY.is_file():
                self.menu_btn.configure(text='IN APP MENU ✓')
        intro=self._label(pad,'Marble Oracle checks its parts each time it starts. Nothing is installed '
                    'without your approval: Python libraries go into a private folder for this app '
                    'only, and system packages ask for your password first.',10,fg=OGG_EMBER['text_2'],
                    justify='left',anchor='w',wraplength=700)
        intro.pack(fill='x',pady=(6,10))
        self._wrap_to_width(intro)

        # The checklist.
        card=tk.Frame(pad,bg=self.CARD,highlightthickness=1,highlightbackground=OGG_EMBER['line'],
                      padx=18,pady=8)
        card.pack(fill='x')
        self.rows={}
        rows=[('python','Python 3 with Tk','Draws every window',True),
              ('pillow','Pillow','Images, artwork and the CRT screen',True),
              ('mutagen','Mutagen','Reads music tags in OGGCULTIST',True)]
        if sys.platform.startswith('linux'):
            rows.append(('jeepney','Jeepney','Keyboard media keys on Linux',False))
        rows+= [('ffmpeg','FFmpeg and FFprobe','Video and audio converting',False),
                ('ffplay','FFplay','Video preview with sound',False)]
        for index,(key,name,role,essential) in enumerate(rows):
            line=tk.Frame(card,bg=self.CARD)
            line.pack(fill='x',pady=2)
            pill=self._label(line,'…',10,bold=True,bg=self.CARD,fg=self.MUTED,anchor='e')
            pill.pack(side='right')
            self._label(line,name,11,bold=True,bg=self.CARD,anchor='w').pack(side='left')
            self._label(line,('' if essential else 'optional · ')+role,9,fg=self.MUTED,bg=self.CARD,
                        anchor='w').pack(side='left',padx=(10,0),pady=(2,0))
            self.rows[key]=(pill,essential)
        # A one-line summary kept for scripts and tests that read it.
        self.details=self._label(card,'',9,fg=self.MUTED,bg=self.CARD,anchor='w',justify='left')

        options=tk.Frame(pad,bg=self.CARD,padx=18,pady=8)
        options.pack(fill='x',pady=(8,0))
        self.media_opt=self._check(options,'Also install FFmpeg, FFprobe and FFplay',self.media)
        self.media_opt.pack(fill='x')
        self.opt=self._check(options,'Also install optional extras (faster CRT drawing, Linux media keys)',self.extras)
        self.opt.pack(fill='x',pady=(2,0))
        if sys.platform.startswith('linux'):
            family=linux_family()
            info=LINUX_FAMILIES.get(family)
            hint=(info['label']+': system packages are installed with '+info['manager'][0]+
                  ' after your desktop asks for your password.') if info else \
                 ('System packages are installed through your desktop\'s software installer '
                  '(PackageKit) after it asks for your password.')
            hint_label=self._label(options,hint,9,fg=self.MUTED,bg=self.CARD,anchor='w',justify='left',
                                   wraplength=660)
            hint_label.pack(fill='x',pady=(6,0))
            self._wrap_to_width(hint_label)

        self.progress=ttk.Progressbar(pad,mode='indeterminate',style='Oracle.Horizontal.TProgressbar')
        self._progress_slot=tk.Frame(pad,bg=self.BG,height=10)
        self._progress_slot.pack(fill='x',pady=(8,2))
        self._label(pad,'MESSAGES',9,fg=self.MUTED,bold=True,anchor='w').pack(fill='x')
        log_box=tk.Frame(pad,bg=OGG_EMBER['sunken'],
                         highlightthickness=1,highlightbackground=self.LINE)
        log_box.pack(fill='both',expand=True,pady=(4,0))
        self.log=tk.Text(log_box,height=4,wrap='word',bg=log_box.cget('bg'),fg=self.TEXT,relief='flat',bd=0,
                         padx=10,pady=8,highlightthickness=0,state='disabled',font=(FAMILY,10))
        try:
            from oracle_widgets import SlimScrollbar
            bar=SlimScrollbar(log_box,command=self.log.yview)
            bar.pack(side='right',fill='y')
            self.log.configure(yscrollcommand=bar.set)
        except Exception:
            pass
        self.log.pack(fill='both',expand=True)
        self._write('Logs are kept in '+str(STATE_DIR)+' for troubleshooting.')

    def add_to_menu(self):
        """Linux: put Marble Oracle in the applications menu (no administrator rights needed)."""
        try:
            result=run_hidden(['bash',str(MENU_INSTALLER)],capture_output=True,text=True,timeout=60)
        except (OSError,subprocess.TimeoutExpired) as exc:
            self._write('Could not add the menu entry: '+str(exc))
            return
        if result.returncode:
            self._write('Could not add the menu entry: '+(result.stderr or result.stdout or '').strip()[-400:])
            return
        self._write('Marble Oracle is now in your applications menu. Search for "Marble Oracle".')
        try:
            self.menu_btn.configure(text='IN APP MENU ✓')
        except (tk.TclError,AttributeError):
            pass

    def _write(self,txt):
        self.log.configure(state='normal')
        self.log.insert('end',txt+'\n')
        self.log.see('end')
        self.log.configure(state='disabled')

    def _pill(self,key,ok,version=''):
        pill,essential=self.rows.get(key,(None,True))
        if pill is None:
            return
        if ok:
            pill.configure(text='READY'+(' '+version if version else ''),fg=self.GOOD)
        elif essential:
            pill.configure(text='MISSING',fg=self.ACCENT)
        else:
            pill.configure(text='NOT INSTALLED',fg=self.MUTED)

    def refresh(self):
        self.python, self.python_status, tools, missing_media = requirements_snapshot()
        def status(k):
            d = self.python_status.get(k, {})
            return 'Ready ('+str(d.get('version',''))+')' if d.get('ok') else 'Missing / incompatible'
        self._pill('python',True,'%d.%d'%sys.version_info[:2])
        for key in ('pillow','mutagen','jeepney'):
            d=self.python_status.get(key,{})
            self._pill(key,bool(d.get('ok')),str(d.get('version','') or ''))
        converter=bool(tools.get('ffmpeg') and tools.get('ffprobe'))
        self._pill('ffmpeg',converter)
        self._pill('ffplay',bool(tools.get('ffplay')))
        lines = ['Python 3 / Tkinter: Ready (setup is running)',
                 'Pillow + ImageTk: '+status('pillow'),
                 'Mutagen: '+status('mutagen')]
        if sys.platform.startswith('linux'):
            lines.append('Jeepney (optional media keys): '+status('jeepney'))
        lines.extend(['FFmpeg / FFprobe (optional converter): '+('Ready' if converter else 'Missing'),
                      'FFplay (optional player): '+('Ready' if tools.get('ffplay') else 'Missing')])
        if missing_media:
            lines.append('Media tools unavailable: '+', '.join(missing_media))
        self.details.configure(text='\n'.join(lines))
        self.ready = self.python is not None
        # The media option only matters while something is missing.
        try:
            if missing_media and not self.media_opt.winfo_manager():
                self.media_opt.pack(fill='x', before=self.opt)
            elif not missing_media:
                self.media_opt.pack_forget()
        except tk.TclError:
            pass
        # Don't reset the user's media-install selection during a failed or
        # partial install. A new setup window defaults to selecting missing tools.
        self.status.set('Marble Oracle ready to start' if self.ready else 'Essential Python libraries missing')
        self.start_btn.configure(text='START MARBLE ORACLE', state='normal' if self.ready and not self.running else 'disabled')
        # The bright button is the next useful step: START when ready, INSTALL when not.
        primary_install = not self.ready
        for button, primary in ((self.install_btn, primary_install), (self.start_btn, not primary_install)):
            try:
                button.configure(bg=self.ACCENT if primary else OGG_EMBER['control'],
                                 fg=OGG_EMBER['text_on_accent'] if primary else self.TEXT,
                                 activebackground=OGG_EMBER['accent_deep'] if primary else OGG_EMBER['hover'],
                                 activeforeground=OGG_EMBER['text_on_accent'] if primary else self.TEXT,
                                 highlightbackground=self.ACCENT if primary else self.LINE)
            except tk.TclError:
                pass
        self.install_btn.configure(text='INSTALL REQUIREMENTS' if not self.ready else 'INSTALL SELECTED')
        return self.ready

    def _report_setup_error(self, context, exc):
        try:
            STATE_DIR.mkdir(parents=True, exist_ok=True)
            with SETUP_ERROR_LOG.open('a', encoding='utf-8') as log:
                log.write(time.strftime('%Y-%m-%d %H:%M:%S')+' '+context+'\n')
                log.write(''.join(traceback.format_exception(type(exc), exc, exc.__traceback__))+'\n')
        except OSError:
            pass
        try:
            self._write(context+': '+str(exc))
            messagebox.showerror('Marble Oracle setup problem',
                context+'\n\n'+str(exc)+'\n\nDetails: '+str(SETUP_ERROR_LOG), parent=self)
        except tk.TclError:
            pass

    def _setbusy(self,busy):
        self.running=busy
        self.install_btn.configure(state='disabled' if busy else 'normal')
        self.start_btn.configure(state='disabled' if busy else 'normal')
        # The progress bar is shown only while setup is actually working.
        if busy:
            self.progress.pack(in_=self._progress_slot,fill='x')
            self.progress.start(12)
        else:
            self.progress.stop()
            self.progress.pack_forget()

    def install(self):
        if self.running or self.launching: return
        try:
            # Explicit consent comes from clicking INSTALL; never elevate on
            # app startup or automatically from the install-complete callback.
            wants_media = bool(self.media.get())
            wants_extras = bool(self.extras.get())
            self._setbusy(True)
            self._write('Installation requested. The setup window will remain open.')
            self._install_media_selected = wants_media
            if self.python is not None and not wants_extras:
                self._write('Essential Python libraries already installed.')
                if wants_media and not all(media_tools().values()):
                    threading.Thread(target=self._media_worker, daemon=True).start()
                else:
                    self.finish_success()
                return
            threading.Thread(target=lambda:install_venv(self._queue,wants_extras),daemon=True).start()
        except Exception as exc:
            self._setbusy(False)
            self._report_setup_error('Could not begin dependency installation', exc)

    def pump(self):
        try:
            while True:
                kind,msg=self._queue.get_nowait()
                try:
                    if kind=='log':
                        self._write(msg)
                    elif kind=='python-ok':
                        self._write('Python packages ready.')
                        if getattr(self,'_install_media_selected',False) and not all(media_tools().values()):
                            self._write('Starting the approved FFmpeg installation...')
                            threading.Thread(target=self._media_worker,daemon=True).start()
                        else:
                            self.finish_success()
                    elif kind=='media-ok':
                        self._write('Media tools installation completed. Rechecking...')
                        self.finish_success()
                    elif kind=='error':
                        self._write('INSTALLATION DID NOT COMPLETE: '+msg)
                        self._setbusy(False)
                        self.refresh()
                        messagebox.showwarning('Marble Oracle installation',
                            msg+'\n\nYou may still start Oracle if its essential Python libraries are ready. '
                            'FFmpeg can be installed later.', parent=self)
                except Exception as exc:
                    self._setbusy(False)
                    self._report_setup_error('Requirements setup event failed', exc)
        except queue.Empty:
            pass
        except Exception as exc:
            self._setbusy(False)
            self._report_setup_error('Requirements window encountered an error', exc)
        try:
            if self.winfo_exists():self._pump_after=self.after(125,self.pump)
        except tk.TclError:
            pass

    def _media_worker(self):
        try:
            installed=install_ffmpeg(self._queue)
            self._queue.put(('media-ok','' if installed else 'manual installation required'))
        except Exception as exc:
            self._queue.put(('error',str(exc)))

    def finish_success(self):
        self._setbusy(False)
        try:
            ready = self.refresh()
        except Exception as exc:
            self._write('Requirements check failed: ' + str(exc))
            messagebox.showerror('Marble Oracle requirements', str(exc), parent=self)
            return
        if not ready:
            self._write('Setup is incomplete. The main application will not open until all requirements are present.')
            messagebox.showwarning('Setup incomplete',
                'One or more requirements are still missing. See the check above.\n'
                'You can retry INSTALL REQUIREMENTS.',parent=self)
            return
        self._write('Installation/check completed. Click START MARBLE ORACLE to open the application.')
        self.status.set('Ready. Select START MARBLE ORACLE.')

    def start(self):
        # One running suite instance per setup process. A second launch should
        # never stack another Oracle window on top of an existing instance.
        if self.running or self.launching or self._monitoring:
            return
        try:
            ready = self.refresh()
            if not ready:
                self._write('Install the essential Python libraries first.')
                return
            if not all(media_tools().values()):
                self._write('Optional FFmpeg tools are missing; the core Oracle interface can still run.')
            self._setbusy(True)
            self.launching = True
            self._ready_verified = False
            self._ready_seen_at = None
            self._opened_at = time.monotonic()
            self.status.set('Starting Marble Oracle...')
            # IMPORTANT: hide setup BEFORE opening the app. Keeping two Tk
            # windows on screen during the old six-second verification period
            # caused the two-window report and an unreliable window handoff.
            self.withdraw()
            self.update_idletasks()
            self.child, self.ready_file = launch_main(self.python)
            self.exit_file = self.ready_file.with_name(
                self.ready_file.name.replace('startup-ready-', 'startup-exit-'))
            self.launch_deadline = time.monotonic() + 35
            self.after(180, self._check_child)
        except Exception as exc:
            self.launching = False
            self._setbusy(False)
            self._show_setup_after_failure()
            self._write('Launch failed: ' + str(exc))
            messagebox.showerror('Marble Oracle could not launch',
                str(exc) + '\n\nStartup log: ' + str(STARTUP_LOG), parent=self)

    def _show_setup_after_failure(self):
        """Restore the requirements UI only when Oracle could not run."""
        try:
            self.deiconify()
            self.lift()
            self.update_idletasks()
        except tk.TclError:
            pass

    def _check_child(self):
        if not self.launching:
            return
        try:
            if not self.winfo_exists():
                return
            code = self.child.poll() if self.child else -1
            if code is not None:
                # The user may deliberately close Oracle during its first
                # six seconds. Treat a confirmed user close as normal.
                if code == 0 and self.exit_file and self.exit_file.is_file():
                    self.launching = False
                    self.destroy()
                    return
                stage = ('during startup verification' if self._ready_seen_at is not None
                         else 'before its window was ready')
                self._startup_failed('Marble Oracle exited ' + stage +
                                     ' (code ' + str(code) + ').')
                return
            now = time.monotonic()
            if self._ready_seen_at is None:
                if self.ready_file and self.ready_file.is_file():
                    try:
                        self.ready_file.unlink()
                    except OSError:
                        pass
                    self._ready_seen_at = now
                    self._write('Oracle window opened; monitoring its startup...')
                elif now >= self.launch_deadline:
                    self._startup_failed('Marble Oracle did not report a ready window within 35 seconds.')
                    return
            elif now - self._ready_seen_at >= 6.0:
                if self.child.poll() is not None:
                    self._startup_failed('Marble Oracle exited shortly after opening.')
                    return
                self._ready_verified = True
                self._write('Oracle has stayed open after the startup check.')
                try:
                    save_state()
                except OSError as exc:
                    self._write('Could not save setup state: ' + str(exc))
                self.launching = False
                # Do not destroy the setup process here. A parent process
                # disappearing can kill its child in some desktop sessions.
                # Keep the setup *hidden* as a lightweight crash reporter and
                # exit when the actual Oracle program closes normally.
                self._monitoring = True
                self.after(750, self._monitor_child)
                return
            self.after(180, self._check_child)
        except Exception as exc:
            self._startup_failed('Startup monitoring failed: ' + str(exc))

    def _monitor_child(self):
        if not self._monitoring:
            return
        try:
            if not self.winfo_exists():
                return
            code = self.child.poll() if self.child else -1
            if code is None:
                self.after(750, self._monitor_child)
                return
            self._monitoring = False
            # Status 0 is not sufficient to classify a close as intentional:
            # certain GUI failures exit cleanly. Only the actual window's
            # intentional-quit handler writes this marker.
            normal_close = bool(code == 0 and self.exit_file and self.exit_file.exists())
            if normal_close:
                try:
                    self.exit_file.unlink(missing_ok=True)
                except OSError:
                    pass
                self.destroy()
            else:
                self._startup_failed('Marble Oracle closed unexpectedly (exit code '
                                     + str(code) + ').')
        except Exception as exc:
            self._monitoring = False
            self._startup_failed('Could not monitor Marble Oracle: ' + str(exc))

    def _startup_failed(self, message):
        self.launching = False
        self._monitoring = False
        self._setbusy(False)
        self._show_setup_after_failure()
        detail = ''
        try:
            detail = STARTUP_LOG.read_text('utf-8', errors='replace')[-1200:]
        except OSError: pass
        self._write(message)
        self.status.set('Startup failed — the requirements window remains open')
        self._write('Startup log: ' + str(STARTUP_LOG))
        # Oracle has its own per-user logs in addition to this launcher log.
        # Rendering failures previously had no visible traceback under pythonw.
        saved = os.environ.get('MARBLE_ORACLE_STATE') or os.environ.get('Marble_Oracle_STATE')
        if saved:
            oracle_logs = Path(saved)
        elif os.name == 'nt':
            oracle_logs = Path(os.environ.get('LOCALAPPDATA') or Path.home()) / 'Marble_Oracle'
        else:
            oracle_logs = Path(os.environ.get('XDG_STATE_HOME') or Path.home()/'.local'/'state') / 'Marble_Oracle'
        for name in ('startup_error.log', 'error.log', 'callback_error.log'):
            path = oracle_logs / name
            try:
                if path.is_file() and time.time() - path.stat().st_mtime < 600:
                    detail += '\n\n' + name + ':\n' + path.read_text(encoding='utf-8', errors='replace')[-900:]
            except OSError:
                pass
        messagebox.showerror('Marble Oracle startup problem',
            message + '\n\n' + (detail or 'No error text was captured.')[-3100:] +
            '\n\nLauncher log: ' + str(STARTUP_LOG) +
            '\nOracle logs: ' + str(oracle_logs), parent=self)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if '--probe' in argv:
        python, status, tools, missing = requirements_snapshot()
        print(json.dumps({'python':str(python) if python else None,
                          'packages':status,'media':tools,
                          'ready':bool(python),
                          'missing_media':missing,
                          'first_run':not load_state().get('completed',False)}))
        return 0
    # No cached-state shortcut: every launch runs the full check. A prior
    # successful setup must never mask newly missing/corrupted media tools.
    window = Setup()
    if '--show-setup' not in argv and load_state().get('completed',False) and window.ready:
        # When requirements are still intact, auto-start once checked. The
        # window stays present until Oracle signals an actual ready display.
        window.after(250, window.start)
    window.mainloop()
    return 0


if __name__=='__main__':
    try: raise SystemExit(main())
    except Exception as exc:
        try:
            STATE_DIR.mkdir(parents=True, exist_ok=True)
            with SETUP_ERROR_LOG.open('a', encoding='utf-8') as log:
                log.write('FATAL SETUP ERROR\n'+traceback.format_exc()+'\n')
        except OSError:
            pass
        # When launched by pythonw.exe there is no stderr to display.
        try:
            root=tk.Tk();root.withdraw()
            messagebox.showerror('Marble Oracle startup error',str(exc),parent=root)
            root.destroy()
        except Exception:
            print('Marble Oracle startup error:',exc,file=sys.stderr)
        raise SystemExit(1)
