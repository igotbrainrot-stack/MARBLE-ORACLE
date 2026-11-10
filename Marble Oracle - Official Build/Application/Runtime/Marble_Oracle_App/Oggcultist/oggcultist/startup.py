"""Program entry: desktop GUI start-up, or the safe headless command line.

``launch.py``, ``python -m oggcultist`` and the packaged executable all call
:func:`main`. The root ``launch.py`` is an alias of this module, so
``import launch`` keeps working for scripts and tests.
"""
from __future__ import annotations
import argparse
import sys
import threading
import traceback
from pathlib import Path
from . import __version__, paths
from .converter.artwork import ArtworkStore
from .converter.core import scan, plan, process, validate_folders
from .converter.musicbrainz import MusicBrainz, MetadataLookupError
from .services import ffmpeg_setup as setup_ffmpeg


def cli(args: argparse.Namespace) -> int:
    if not args.input or not args.output:
        print('CLI requires --input and --output. Example: python launch.py --cli --input SOURCE --output OUTPUT')
        return 2
    try:
        source,dest = validate_folders(Path(args.input),Path(args.output))
        if args.run:
            dest.mkdir(parents=True,exist_ok=True)
        tracks,errors = scan(source, lambda n,p: print(f'Scanned {n}: {p}',flush=True) if n%100==0 else None)
        if args.musicbrainz:
            mb = MusicBrainz(args.contact_email or '')
            groups={t.album_group():[] for t in tracks}
            for t in tracks:groups[t.album_group()].append(t)
            for n, group in enumerate(groups.values(),1):
                lead=group[0]
                if not lead.album or not (lead.albumartist or lead.artist): continue
                if not mb.auto_lookup_safe(group):
                    print(f'MusicBrainz {n}/{len(groups)}: kept existing MBIDs', flush=True)
                    continue
                print(f'MusicBrainz {n}/{len(groups)}: {lead.album}',flush=True)
                try:
                    matches=mb.search(lead.album,lead.albumartist or lead.artist)
                    match=mb.confident(matches)
                    if match:
                        for t in group:mb.apply(t,match)
                    elif matches:
                        for t in group:t.lookup_issue='Ambiguous MusicBrainz results — manual review required'
                except MetadataLookupError as exc:
                    print('Lookup skipped: '+str(exc),file=sys.stderr)
        store = ArtworkStore(dest, read_only=not args.run)
        try:plan(tracks,dest,store)
        finally:
            if store: store.close()
        print(f'Found {len(tracks)} audio files; {len(errors)} unreadable files.')
        for p,error in errors:print(f'ERROR {p}: {error}')
        for t in tracks:
            print(f'[{t.status:9}] {t.source} -> {t.target or "(review required)"} {t.note}')
        ready=sum(t.status=='Ready' for t in tracks)
        if not args.run:
            print(f'\nDRY RUN ONLY. {ready} files ready. Use --run to convert; originals are never modified.')
            return 0
        if not ready:
            print('Nothing ready to convert.')
            return 0
        print(f'\nConverting {ready} tracks. Originals remain untouched.',flush=True)
        summary=process(tracks,dest,threading.Event(),lambda name,i,total,f:
                        print(f'[{i}/{total}] {name} {f*100:.0f}%',end='\r',flush=True))
        print(f"\nConverted {summary['converted']}; errors {summary['errors']}; unprocessed {summary['not_processed']}")
        print(f"Bytes saved {summary['input_bytes']-summary['output_bytes']:+,}")
        return 1 if summary['errors'] or errors else 0
    except Exception as exc:
        print(f'Oggcultist: {exc}',file=sys.stderr)
        return 2


def _report_startup_error(exc: BaseException) -> None:
    """Keep a useful log when a double-clicked Windows app fails to start."""
    report = ''.join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    print('\nOggcultist could not open the desktop window:', file=sys.stderr, flush=True)
    print(report, file=sys.stderr, flush=True)
    try:
        logfile = paths.logs_dir() / 'startup-error.log'
        logfile.parent.mkdir(parents=True, exist_ok=True)
        logfile.write_text(report, encoding='utf-8')
        print(f'Startup diagnostics saved to: {logfile}', file=sys.stderr, flush=True)
    except OSError as log_error:
        print(f'Could not save startup diagnostics: {log_error}', file=sys.stderr, flush=True)


def _windowless_ffmpeg_setup(setup_ffmpeg, on_installed) -> bool:
    """Obtain first-run consent through Tk dialogs, never hidden stdin."""
    import tkinter as tk
    from tkinter import messagebox
    prompt_root = tk.Tk()
    prompt_root.withdraw()
    notices = []
    def prompt(_question: str) -> str:
        return ('y' if messagebox.askyesno('Oggcultist — FFmpeg setup',
                    'FFmpeg and FFprobe are missing. Download the official Windows FFmpeg '
                    'Essentials build into your user profile?\n\n'
                    'The download is checksum-verified and requires no administrator rights.',
                    parent=prompt_root) else 'n')
    try:
        ok = setup_ffmpeg.ensure_ffmpeg(input_fn=prompt, print_fn=lambda msg: notices.append(str(msg)),
                                        on_installed=on_installed)
        if notices:
            print('\n'.join(notices), flush=True)
        if not ok:
            messagebox.showerror('Oggcultist — setup incomplete',
                    '\n'.join(notices[-3:]) or 'FFmpeg setup did not complete.', parent=prompt_root)
        return ok
    finally:
        prompt_root.destroy()



def _windowless_ffplay_setup(setup_ffmpeg, on_installed) -> bool:
    """Windows GUI consent for FFplay; launch still proceeds if declined."""
    import tkinter as tk
    from tkinter import messagebox
    root = tk.Tk()
    root.withdraw()
    approved = []
    notices = []
    progress = []
    def ask(_question: str) -> str:
        answer = messagebox.askyesno(
            'Oggcultist — music playback setup',
            'FFplay is missing. Install it now so Oggcultist can play music?\n\n'
            'A checksum-verified FFmpeg Essentials download will be installed in your '
            'Windows user profile. No administrator access or system PATH changes are needed.',
            parent=root)
        approved.append(answer)
        if answer and hasattr(root, 'tk'):
            # The network install may be slow. Keep an explicit progress window
            # visible rather than leaving Windows with no feedback after Yes.
            try:
                from tkinter import ttk
                dialog = tk.Toplevel(root)
                dialog.title('Oggcultist — installing FFplay')
                dialog.resizable(False, False)
                ttk.Label(dialog, text='Installing FFplay for music playback…',
                          padding=(22, 20)).pack()
                ttk.Label(dialog, text='Downloading and verifying the official build.\n'
                          'Oggcultist will open when setup is complete.',
                          padding=(22, 0)).pack()
                dialog.protocol('WM_DELETE_WINDOW', lambda: None)
                dialog.update()
                progress.append(dialog)
            except tk.TclError:
                pass
        return 'y' if answer else 'n'
    try:
        ok = setup_ffmpeg.ensure_ffplay(input_fn=ask,
                                        print_fn=lambda message: notices.append(str(message)),
                                        on_installed=on_installed)
        if notices:
            print('\n'.join(notices), flush=True)
        if approved and approved[-1] and not ok:
            messagebox.showwarning('Oggcultist — FFplay setup',
                '\n'.join(notices[-2:]) or 'FFplay installation could not be completed. '
                'You can still use the audio converter.', parent=root)
        return ok
    finally:
        for dialog in progress:
            try:
                dialog.destroy()
            except tk.TclError:
                pass
        root.destroy()

def _start_desktop(windowless: bool = False) -> None:
    # Keep install and GUI startup inside *one* Python process. Windows child
    # processes do not inherit another Python subprocess's environment changes.
    paths.configure_tool_path()
    try:
        copied = paths.migrate_to_portable()
        if copied:
            print('Portable mode: copied ' + ', '.join(copied) + ' into the portable data folder.', flush=True)
    except OSError as exc:
        print(f'Portable data migration skipped: {exc}', file=sys.stderr, flush=True)
    installed_now = []
    install_notice = lambda: installed_now.append(True)
    ready = (_windowless_ffmpeg_setup(setup_ffmpeg, install_notice)
             if windowless and sys.platform == 'win32'
             else setup_ffmpeg.ensure_ffmpeg(on_installed=install_notice))
    if not ready:
        raise SystemExit('FFmpeg setup did not complete. Install FFmpeg and try again.')
    # The player is the home screen, so offer the playback dependency at launch.
    # Installing FFplay is optional; declining never blocks the converter.
    ffplay_installed_now = []
    if windowless and sys.platform == 'win32':
        ffplay_ready = _windowless_ffplay_setup(setup_ffmpeg, lambda: ffplay_installed_now.append(True))
    else:
        ffplay_ready = setup_ffmpeg.ensure_ffplay(on_installed=lambda: ffplay_installed_now.append(True))
    print('Opening Oggcultist desktop window...', flush=True)
    try:
        from oggcultist.app import main as gui_main
        notice = ('FFmpeg installed successfully. Oggcultist is ready to scan your music.'
                  if installed_now else
                  'FFmpeg is ready. Select your source and destination folders to get started.')
        if ffplay_installed_now:
            notice = 'FFplay installed successfully. Music playback is ready.'
        elif not ffplay_ready:
            notice = 'FFplay is not installed. You can still browse music and convert audio.'
        gui_main(startup_message=notice)
    except (Exception, SystemExit) as exc:
        _report_startup_error(exc)
        raise SystemExit(1) from exc


def _redirect_missing_streams() -> None:
    """A windowed executable or pythonw has no stdout/stderr; keep a log instead."""
    if sys.stdout is not None and sys.stderr is not None:
        return
    try:
        folder = paths.logs_dir()
        folder.mkdir(parents=True, exist_ok=True)
        stream = open(folder / 'oggcultist.log', 'a', encoding='utf-8', buffering=1)
    except OSError:
        return
    if sys.stdout is None:
        sys.stdout = stream
    if sys.stderr is None:
        sys.stderr = stream


def describe_paths() -> str:
    """Human-readable report of every location Oggcultist uses (for support/diagnosis)."""
    import shutil
    portable = paths.portable_root()
    tool_dirs = paths.configure_tool_path()
    lines = [
        f'Oggcultist {__version__}  (Python {sys.version.split()[0]}, {"frozen executable" if paths.is_frozen() else "source"})',
        f'Program folder:   {paths.app_dir()}',
        f'Bundled files:    {paths.bundle_dir()}',
        f'Icon resource:    {paths.resource_path("icon.png")}  (exists: {paths.resource_path("icon.png").is_file()})',
        f'Portable mode:    {"yes — " + str(portable) if portable else "no"}',
        f'Settings:         {paths.settings_file()}',
        f'Playlists:        {paths.playlist_file()}',
        f'Logs:             {paths.logs_dir()}',
        f'Private tools:    {paths.private_tools_dir()}',
        f'Bundled tools:    {", ".join(map(str, paths.bundled_tools_dirs())) or "none"}',
    ]
    for name in ('ffmpeg', 'ffprobe', 'ffplay'):
        lines.append(f'{name + ":":<17} {shutil.which(name) or "not found"}')
    lines.append('Conversion records stay inside each destination library (.oggcultist folder).')
    return '\n'.join(lines)


def _default_windowless() -> bool:
    """Packaged Windows builds and pythonw have no console to answer prompts."""
    return sys.platform == 'win32' and (paths.is_frozen() or sys.stdin is None)


def main(argv=None):
    _redirect_missing_streams()
    parser=argparse.ArgumentParser(prog='oggcultist', description='Oggcultist · music player and safe Opus library organiser')
    parser.add_argument('--version', action='version', version=f'Oggcultist {__version__}')
    parser.add_argument('--paths', action='store_true', help='Show where settings, logs and tools are found, then exit')
    parser.add_argument('--windowless', action='store_true', help='Use GUI prompts for silent Windows startup')
    parser.add_argument('--cli',action='store_true',help='Run headless; defaults to dry-run')
    parser.add_argument('--input',help='Input music folder')
    parser.add_argument('--output',help='Separate destination music folder')
    parser.add_argument('--run',action='store_true',help='Perform conversion (CLI only; default preview)')
    parser.add_argument('--musicbrainz',action='store_true',help='Opt in to online release-group metadata lookup')
    parser.add_argument('--contact-email',help='Your contact address to identify MusicBrainz API requests')
    args=parser.parse_args(argv)
    if args.paths:
        print(describe_paths())
        sys.exit(0)
    if args.cli and not args.run:
        sys.exit(cli(args))
    if args.cli:
        paths.configure_tool_path()
        if not setup_ffmpeg.ensure_ffmpeg():
            sys.exit('FFmpeg setup did not complete. Install FFmpeg and try again.')
        sys.exit(cli(args))
    _start_desktop(windowless=args.windowless or _default_windowless())


if __name__=='__main__': main()
