"""FFplay preflight and robust multi-selection tests for v1.6.3."""
from __future__ import annotations
import hashlib
import io
import sys
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest
import launch
import setup_ffmpeg as sf
from oggcultist.selection import bind_track_selection


def ffplay_zip():
    out = io.BytesIO()
    with zipfile.ZipFile(out,'w') as zf:
        for name in ('ffplay.exe', 'ffmpeg.exe', 'ffprobe.exe'):
            zf.writestr('ffmpeg-package/bin/' + name, name.encode())
    return out.getvalue()


def opener_for(archive, correct=True):
    def opener(request, timeout=90):
        if request.full_url.endswith('.sha256'):
            digest = hashlib.sha256(archive).hexdigest() if correct else 'a'*64
            return io.BytesIO(digest.encode('ascii'))
        return io.BytesIO(archive)
    return opener


def test_ffplay_installed_on_start_with_explicit_consent(tmp_path):
    env = {'LOCALAPPDATA': str(tmp_path), 'PATH': '/usr/bin'}
    bin_dir = sf.local_bin('win32', env)
    bin_dir.mkdir(parents=True)
    (bin_dir / 'ffmpeg.exe').write_bytes(b'old-ffmpeg')
    (bin_dir / 'ffprobe.exe').write_bytes(b'old-ffprobe')
    prompts, messages, installed = [], [], []
    result = sf.ensure_ffplay(platform='win32', env=env, input_fn=lambda p: (prompts.append(p) or 'y'),
                              opener=opener_for(ffplay_zip()), print_fn=messages.append,
                              check_fn=lambda _: (bin_dir/'ffplay.exe').exists(),
                              on_installed=lambda: installed.append(1))
    assert result and len(prompts) == 1 and installed == [1]
    assert (bin_dir/'ffplay.exe').read_bytes() == b'ffplay.exe'
    assert (bin_dir/'ffmpeg.exe').read_bytes() == b'old-ffmpeg'
    assert (bin_dir/'ffprobe.exe').read_bytes() == b'old-ffprobe'
    assert any('installed successfully' in m for m in messages)


def test_ffplay_existing_never_prompts_or_downloads(tmp_path):
    env = {'LOCALAPPDATA':str(tmp_path), 'PATH':'/bin'}
    result = sf.ensure_ffplay(platform='win32', env=env,
                check_fn=lambda _:True,
                input_fn=lambda p: pytest.fail('unexpected prompt'),
                opener=lambda *_a,**_k: pytest.fail('unexpected network'),print_fn=lambda _m:None)
    assert result and not (tmp_path/'Oggcultist').exists()


def test_ffplay_declined_does_not_download_or_fail_conversion(tmp_path):
    env = {'LOCALAPPDATA':str(tmp_path), 'PATH':'/bin'}
    assert not sf.ensure_ffplay(platform='win32', env=env, check_fn=lambda _:False,
               input_fn=lambda p:'n', opener=lambda *_a,**_k:pytest.fail('unexpected network'),
               print_fn=lambda _m:None)
    assert not sf.local_bin('win32', env).exists()


def test_ffplay_bad_digest_does_not_install(tmp_path):
    env = {'LOCALAPPDATA':str(tmp_path), 'PATH':'/bin'}
    assert not sf.ensure_ffplay(platform='win32', env=env, check_fn=lambda _:False,
               input_fn=lambda p:'y', opener=opener_for(ffplay_zip(), False), print_fn=lambda _m:None)
    assert not (sf.local_bin('win32',env)/'ffplay.exe').exists()


def test_ffplay_windowless_prompt_and_no_double_setup(monkeypatch):
    import tkinter as tk
    from tkinter import messagebox
    calls=[]
    class FakeRoot:
        def withdraw(self): calls.append('hide')
        def destroy(self): calls.append('destroy')
    monkeypatch.setattr(tk,'Tk',FakeRoot)
    monkeypatch.setattr(messagebox,'askyesno',lambda *a,**k: calls.append('prompt') or True)
    def setup(**kwargs):
        assert kwargs['input_fn']('install?') == 'y'
        kwargs['on_installed']()
        return True
    seen=[]
    assert launch._windowless_ffplay_setup(SimpleNamespace(ensure_ffplay=setup),lambda:seen.append(1))
    assert calls == ['hide','prompt','destroy'] and seen == [1]


def test_gui_launch_calls_ffplay_preflight_even_if_ffmpeg_is_ready(monkeypatch):
    setup=[]; launch_msgs=[]
    import setup_ffmpeg
    monkeypatch.setattr(setup_ffmpeg,'ensure_ffmpeg',lambda **kw:setup.append('ffmpeg') or True)
    monkeypatch.setattr(setup_ffmpeg,'ensure_ffplay',lambda **kw:setup.append('ffplay') or True)
    monkeypatch.setitem(sys.modules,'oggcultist.app', SimpleNamespace(main=lambda **kw:launch_msgs.append(kw)))
    launch._start_desktop()
    assert setup == ['ffmpeg','ffplay']
    assert len(launch_msgs) == 1


class FakeTree:
    def __init__(self):
        self.items = tuple(str(i) for i in range(8))
        self.selected = []
        self.bindings = {}
        self.focused = None
    def bind(self, event, callback): self.bindings[event] = callback
    def get_children(self, parent=''): return self.items
    def identify_row(self, y): return str(y) if str(y) in self.items else ''
    def focus_set(self): pass
    def focus(self, item): self.focused = item
    def see(self, item): pass
    def selection(self): return tuple(self.selected)
    def selection_set(self, ids): self.selected = list(ids)
    def selection_add(self, ids):
        for item in ids:
            if item not in self.selected: self.selected.append(item)
    def selection_remove(self, ids):
        for item in ids:
            if item in self.selected: self.selected.remove(item)


def click(t, pattern, y):
    return t.bindings[pattern](SimpleNamespace(y=y))


def test_selection_ctrl_a_and_toggle_and_ranges():
    t=FakeTree()
    bind_track_selection(t)
    click(t,'<Button-1>', 1)
    click(t,'<Control-Button-1>',4)
    assert set(t.selection()) == {'1','4'}
    click(t,'<Control-Button-1>',1)
    assert set(t.selection()) == {'4'}
    click(t,'<Shift-Button-1>',6)
    assert set(t.selection()) == {'4','5','6'}
    click(t,'<Control-Shift-Button-1>',2)
    assert set(t.selection()) == {'2','3','4','5','6'}
    assert t.bindings['<Control-a>'](None) == 'break'
    assert set(t.selection()) == set(t.items)
    click(t,'<Button-1>',0)
    assert t.selection() == ('0',)
    assert click(t,'<Button-1>',999) is None
    assert t.selection() == ('0',)


@pytest.mark.skipif(sys.platform != 'win32' and not __import__('os').environ.get('DISPLAY'), reason='No desktop display')
def test_real_tk_tree_selection_in_player_and_converter(tmp_path, monkeypatch):
    # v1.7: every track table (Library, Artists, Albums, Playlists, Converter)
    # lives in one window and uses the same selection bindings.
    import tkinter as tk
    monkeypatch.setenv('OGGCULTIST_DATA_DIR', str(tmp_path / 'data'))
    from oggcultist.app import OggcultistApp
    app = OggcultistApp()
    try:
        app.update()
        pages = ('library', 'artists', 'albums', 'playlists', 'converter')
        for key in pages:
            app.show_page(key)
            app.update()
            page = app.pages[key]
            tree = page.tree if key == 'converter' else page.table.tree
            for pattern in ('<Control-a>', '<Control-Button-1>', '<Control-Shift-Button-1>', '<Shift-Button-1>'):
                assert tree.bind(pattern)
            for n in range(5):
                tree.insert('', 'end', iid='sample' + str(n), values=('Song ' + str(n),))
            tree.focus_set()
            tree.event_generate('<Control-a>')
            app.update()
            assert len(tree.selection()) == 5, key
    finally:
        try: app.destroy()
        except Exception: pass
