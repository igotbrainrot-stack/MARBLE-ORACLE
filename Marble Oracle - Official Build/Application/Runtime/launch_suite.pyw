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


def private_bin() -> Path:
    """Use Oggcultist's own tool directory, including its portable-mode setting."""
    sys.path.insert(0, str(OGG_ROOT))
    from oggcultist.paths import private_tools_dir
    return private_tools_dir()


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
                               ('\nOn Linux Mint: install python3-venv with Software Manager or sudo apt install python3-venv.'
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


def linux_media_command(package='ffmpeg'):
    """Pick a graphical-authentication path; never invoke sudo in a terminal.

    Packages are restricted to explicit requirements rather than accepting
    arbitrary command strings. Polkit handles authentication outside the app.
    """
    if package not in ('ffmpeg','python3-venv'):
        raise ValueError('Unsupported Linux setup package: '+str(package))
    apt = shutil.which('apt-get')
    pkexec = shutil.which('pkexec')
    if apt and pkexec:
        return [pkexec, apt, 'install', '-y', package], 'Linux Mint / apt with Polkit'
    pkcon = shutil.which('pkcon')
    if pkcon:
        return [pkcon, '--plain', '-y', 'install', package], 'Linux PackageKit'
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
            raise RuntimeError('No graphical package installer was found. On Linux Mint, install '
                               'the ffmpeg package using Software Manager, or use '
                               'sudo apt install ffmpeg in a terminal. Then reopen setup.')
        out_queue.put(('log',method+': requesting permission to install the ffmpeg system package...'))
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
                               'You can also install ffmpeg using Linux Mint Software Manager.')
    else:
        raise RuntimeError('Automatic FFmpeg installation is supported on Windows 11 and Linux Mint. '
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
        self.geometry('760x700')
        self.minsize(680,660)
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

    def _label(self,parent,text,size=11,fg='#F2E8DE',**kwargs):
        return tk.Label(parent,text=text,font=(FAMILY,size),bg='#1D1714',fg=fg,**kwargs)

    def _build(self):
        pad=tk.Frame(self,bg='#1D1714',padx=22,pady=12)
        pad.pack(fill='both',expand=True)
        self._label(pad,'MARBLE ORACLE  ·  REQUIREMENTS CHECK',16,fg='#FB8E22').pack(anchor='w')
        self._label(pad,'Every launch checks requirements before opening Marble Oracle.',11).pack(anchor='w',pady=(9,4))
        self._label(pad,'Nothing installs without your approval. Python libraries use a private\nenvironment. FFmpeg is optional for the main Oracle window.',10,
                    justify='left',wraplength=630).pack(anchor='w')
        self.details=self._label(pad,'',10,justify='left',anchor='nw',wraplength=625)
        self.details.pack(anchor='w',fill='x',pady=(15,12))
        self.opt=tk.Checkbutton(pad,text='Include optional CRT rendering / Linux media-key enhancements',variable=self.extras,
                                bg='#1D1714',fg='#F2E8DE',selectcolor='#2F2620',activebackground='#1D1714',
                                activeforeground='#FFF4E6')
        self.opt.pack(anchor='w')
        self.media_opt=tk.Checkbutton(pad,text='Install FFmpeg + FFprobe + FFplay for Oggcultist media functions',
                                variable=self.media,bg='#1D1714',fg='#F2E8DE',selectcolor='#2F2620',
                                activebackground='#1D1714',activeforeground='#FFF4E6')
        self.media_opt.pack(anchor='w',pady=(2,8))
        self._label(pad,'Linux Mint: missing FFmpeg or python3-venv may request administrator approval.\nIf authorization is unavailable, use Software Manager. Missing Tkinter: install python3-tk.',9,
                    justify='left',fg='#B9A99B').pack(anchor='w',pady=(0,9))
        self.progress=ttk.Progressbar(pad,mode='indeterminate')
        self.progress.pack(fill='x',pady=(0,8))
        self.log=tk.Text(pad,height=5,wrap='word',bg='#16110F',fg='#F2E8DE',relief='flat',bd=0,
                         highlightthickness=1,highlightbackground='#59473B',state='disabled',font=(FAMILY,10))
        self.log.pack(fill='both',expand=True)
        self._label(pad,'Setup logs are kept in your user profile for troubleshooting.',9,fg='#B9A99B').pack(anchor='w',pady=(7,0))
        buttons=tk.Frame(pad,bg='#1D1714')
        buttons.pack(fill='x',pady=(11,0))
        self.install_btn=tk.Button(buttons,text='INSTALL REQUIREMENTS',command=self.install,
            bg='#FB8E22',fg='#2B1405',activebackground='#FDA629',relief='flat',padx=16,pady=9)
        self.install_btn.pack(side='left')
        self.start_btn=tk.Button(buttons,text='START MARBLE ORACLE',command=self.start,
            bg='#2F2620',fg='#F2E8DE',activebackground='#372A23',relief='flat',padx=12,pady=9)
        self.start_btn.pack(side='left',padx=8)
        tk.Button(buttons,text='EXIT',command=self.destroy,bg='#1D1714',fg='#B9A99B',relief='flat',
                  padx=10,pady=9).pack(side='right')
        self._label(pad,'FFmpeg is recommended for Oggcultist playback/conversion, but not required\nto open Marble Oracle. Setup stays open after installation; choose START.',9,
                    justify='left',fg='#B9A99B').pack(anchor='w',pady=(8,0))

    def _write(self,txt):
        self.log.configure(state='normal')
        self.log.insert('end',txt+'\n')
        self.log.see('end')
        self.log.configure(state='disabled')

    def refresh(self):
        self.python, self.python_status, tools, missing_media = requirements_snapshot()
        def status(k):
            d = self.python_status.get(k, {})
            return 'Ready ('+str(d.get('version',''))+')' if d.get('ok') else 'Missing / incompatible'
        lines = ['Python 3 / Tkinter: Ready (setup is running)',
                 'Pillow + ImageTk: '+status('pillow'),
                 'Mutagen: '+status('mutagen')]
        if sys.platform.startswith('linux'):
            lines.append('Jeepney (optional media keys): '+status('jeepney'))
        lines.extend(['FFmpeg / FFprobe (optional converter): '+('Ready' if tools.get('ffmpeg') and tools.get('ffprobe') else 'Missing'),
                      'FFplay (optional player): '+('Ready' if tools.get('ffplay') else 'Missing')])
        if missing_media:
            lines.append('Media tools unavailable: '+', '.join(missing_media))
        self.details.configure(text='\n'.join(lines))
        self.ready = self.python is not None
        # Don't reset the user's media-install selection during a failed or
        # partial install. A new setup window defaults to selecting missing tools.
        self.status.set('Marble Oracle ready to start' if self.ready else 'Essential Python libraries missing')
        self.start_btn.configure(text='START MARBLE ORACLE', state='normal' if self.ready and not self.running else 'disabled')
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
        if busy: self.progress.start(12)
        else: self.progress.stop()

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
