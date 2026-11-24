"""Marble Oracle Ember surfaces for an independent or embedded OVERCAST workspace.

When the complete Marble Oracle suite is present, use the existing, exact
Oggcultist texture assets and widgets. Standalone OVERCAST includes original
small tiles generated using the Oggcultist grain method and matching palette;
Pillow is not required to render them at runtime.
"""
from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import ttk

C = {
    'page':'#1D1714','card':'#261F1B','side':'#130F0D',
    'sunken':'#16110F','control':'#2F2620',
    'accent':'#FB8E22','text':'#F2E8DE','muted':'#B9A99B',
}
ASSETS = Path(__file__).resolve().parent / 'assets'


def _suite_texture_available():
    try:
        from oracle_ogg_texture import TEXTURES
        return (TEXTURES / 'page.png').is_file()
    except ImportError:
        return False


def install(widget):
    if _suite_texture_available():
        from oracle_ogg_texture import install as suite_install
        suite_install(widget)
        return 'suite'
    root=widget.winfo_toplevel()
    style=ttk.Style(widget)
    state=getattr(root,'_signal_grain',None)
    if state is None:
        state={'photos':{},'themes':set()}
        root._signal_grain=state
    if style.theme_use() in state['themes']:
        return 'standalone'
    for role in ('page','card','side','sunken','control'):
        if role not in state['photos']:
            path=ASSETS / f'{role}.png'
            if not path.is_file():continue
            state['photos'][role]=tk.PhotoImage(master=root,file=str(path))
        if role not in state['photos']:continue
        element=f'Signal.Ember.{role}'
        if element not in style.element_names():
            style.element_create(element,'image',state['photos'][role],sticky='nswe',width=1,height=1)
        style.layout(f'Signal.Ember.{role}.TFrame',[(element,{'sticky':'nswe'})])
        style.layout(f'Signal.Ember.{role}.TLabel',[(element,{'sticky':'nswe','children':[
            ('Label.padding',{'sticky':'nswe','children':[('Label.label',{'sticky':'nswe'})]})
        ]})])
    state['themes'].add(style.theme_use())
    return 'standalone'


def frame(parent,role='page',**kwargs):
    if install(parent)=='suite':
        from oracle_ogg_texture import frame as suite_frame
        return suite_frame(parent,bg=C[role],**kwargs)
    return ttk.Frame(parent,style=f'Signal.Ember.{role}.TFrame',**kwargs)


def label(parent,text,role='page',fg=None,font=None,**kwargs):
    if install(parent)=='suite':
        from oracle_ogg_texture import label as suite_label
        return suite_label(parent,text=text,bg=C[role],fg=fg or C['text'],font=font,**kwargs)
    return ttk.Label(parent,text=text,style=f'Signal.Ember.{role}.TLabel',
                     foreground=fg or C['text'],font=font,**kwargs)
