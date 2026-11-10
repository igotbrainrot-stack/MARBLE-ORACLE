"""FFmpeg / FFprobe / FFplay installer checks, with no real downloads or elevation."""
from __future__ import annotations
import importlib.util
from importlib.machinery import SourceFileLoader
from pathlib import Path
import queue
import subprocess
import sys
from unittest.mock import patch

BOOT=Path(__file__).resolve().parents[1]/'Runtime'/'launch_suite.pyw'
loader=SourceFileLoader('marble_setup_media_test',str(BOOT))
spec=importlib.util.spec_from_loader(loader.name,loader)
boot=importlib.util.module_from_spec(spec)
loader.exec_module(boot)

def status(**overrides):
    out={k:True for k in ('ffmpeg','ffprobe','ffplay')}
    out.update(overrides)
    return out

def test_present_tools_never_install():
    q=queue.Queue()
    assert boot.install_ffmpeg(q,platform='linux',check_tools=lambda:status(),
       runner=lambda *args,**kwargs: (_ for _ in ()).throw(AssertionError('unexpected process')))

def test_mint_pkexec_installs():
    q=queue.Queue()
    commands=[]
    states=[status(ffmpeg=False,ffprobe=False,ffplay=False), status()]
    def run(cmd,**kw):
        commands.append((cmd,kw))
        return subprocess.CompletedProcess(cmd,0,stdout='Installed ffmpeg',stderr='')
    def check(): return states.pop(0) if len(states)>1 else status()
    assert boot.install_ffmpeg(q,platform='linux',check_tools=check,runner=run,
       command_picker=lambda:(['/usr/bin/pkexec','/usr/bin/apt-get','install','-y','ffmpeg'],'PolicyKit'))
    assert commands[0][0]==['/usr/bin/pkexec','/usr/bin/apt-get','install','-y','ffmpeg']
    assert commands[0][1]['timeout']==1200
    assert commands[0][1]['capture_output'] is True

def test_packagekit_fallback():
    q=queue.Queue()
    commands=[]
    states=[status(ffplay=False),status()]
    def run(cmd,**kwargs):
        commands.append(cmd)
        return subprocess.CompletedProcess(cmd,0,stdout='',stderr='')
    def check(): return states.pop(0) if len(states)>1 else status()
    assert boot.install_ffmpeg(q,platform='linux',check_tools=check,runner=run,
        command_picker=lambda:(['/usr/bin/pkcon','--plain','-y','install','ffmpeg'],'PackageKit'))
    assert commands[0][0].endswith('pkcon')

def test_refused_auth_is_failure_not_success():
    q=queue.Queue()
    def run(cmd,**kwargs):return subprocess.CompletedProcess(cmd,126,stdout='',stderr='Not authorized')
    try:
        boot.install_ffmpeg(q,platform='linux',check_tools=lambda:status(ffmpeg=False),runner=run,
           command_picker=lambda:(['pkexec','apt-get','install','-y','ffmpeg'],'PolicyKit'))
    except RuntimeError as exc:
        assert 'declined' in str(exc).lower()
    else: raise AssertionError('Authorization refused but setup claimed success')

def test_no_graphical_installer_does_not_elevate():
    q=queue.Queue()
    try:
        boot.install_ffmpeg(q,platform='linux',check_tools=lambda:status(ffmpeg=False),
            command_picker=lambda:(None,None),
            runner=lambda *args,**kwargs: (_ for _ in ()).throw(AssertionError('unexpected process')))
    except RuntimeError as exc: assert 'Software Manager' in str(exc)
    else: raise AssertionError('Missing graphical installer reported as success')

def test_all_names_in_status():
    assert set(boot.media_tools())=={'ffmpeg','ffprobe','ffplay'}

def test_media_path_preserves_existing_path():
    before=dict(__import__('os').environ)
    try:
        boot.configure_media_path()
        assert all(boot.media_tools().values())  # This test host has ffmpeg tools.
    finally:
        __import__('os').environ.clear()
        __import__('os').environ.update(before)

def test_missing_python_venv_requests_desktop_authorization():
    """Emulate Mint without ensurepip, then successful GUI-authorized install."""
    from tempfile import TemporaryDirectory
    with TemporaryDirectory() as tmp:
        path=Path(tmp)
        commands=[]
        q=queue.Queue()
        attempts=[0]
        def run(cmd,**kwargs):
            commands.append(cmd)
            if '-m' in cmd and 'venv' in cmd:
                attempts[0]+=1
                if attempts[0]==1:
                    return subprocess.CompletedProcess(cmd,1,stdout='',stderr='ensurepip is not available. Install python3-venv')
            return subprocess.CompletedProcess(cmd,0,stdout='',stderr='')
        with patch.object(boot,'STATE_DIR',path), patch.object(boot,'VENV_DIR',path/'venv'), \
             patch.object(boot,'LOG_FILE',path/'requirements-install.log'), \
             patch.object(boot,'run_hidden',side_effect=run), \
             patch.object(boot,'linux_media_command',return_value=(['pkexec','apt-get','install','-y','python3-venv'],'Polkit')), \
             patch.object(boot,'inspect_python',return_value=({'pillow':{'ok':True},'mutagen':{'ok':True},'jeepney':{'ok':True}},None)):
            boot.install_venv(q,include_optional=False)
        assert attempts[0]==2
        assert ['pkexec','apt-get','install','-y','python3-venv'] in commands
        assert any(k=='python-ok' for k,_ in list(q.queue))

def test_windows_private_install_uses_upstream_verified_downloader():
    """Do not fetch media binaries during this test."""
    q=queue.Queue()
    from unittest.mock import MagicMock
    import oggcultist.services.ffmpeg_setup as upstream
    states=[status(ffmpeg=False,ffprobe=False,ffplay=False),status()]
    def check():return states.pop(0) if len(states)>1 else status()
    with patch.object(upstream,'download_verified_archive',return_value=b'fake checksum validated bytes') as download, \
         patch.object(upstream,'install_windows') as installer, \
         patch.object(upstream,'add_local_to_path'):
        assert boot.install_ffmpeg(q,platform='win32',check_tools=check)
        download.assert_called_once()
        assert installer.call_args.kwargs['filenames']==('ffmpeg.exe','ffprobe.exe','ffplay.exe')

if __name__=='__main__':
    for fn in (test_present_tools_never_install,test_mint_pkexec_installs,
               test_packagekit_fallback,test_refused_auth_is_failure_not_success,
               test_no_graphical_installer_does_not_elevate,test_all_names_in_status,
               test_media_path_preserves_existing_path,
               test_missing_python_venv_requests_desktop_authorization,
               test_windows_private_install_uses_upstream_verified_downloader):
        fn()
        print('PASS',fn.__name__)
