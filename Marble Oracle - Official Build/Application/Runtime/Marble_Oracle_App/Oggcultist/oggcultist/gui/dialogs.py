"""Modal forms used by the converter: metadata editor and MusicBrainz match review.

These stay modal on purpose: each edits pending conversion metadata, and a
conversion must not start while one is open (see the v1.1/v1.2 race fixes).
"""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from ..metadata import Track
from .theme import PALETTE


class Editor(tk.Toplevel):
    FIELDS = [
        ('title','Track title'),('artist','Track artist (including guests)'),('albumartist','Album artist'),
        ('album','Album'),('year','Original release year'),('date','Specific release date'),
        ('track','Track number'),('disc','Disc number'),('track_total','Total tracks on disc'),
        ('disc_total','Total discs'),('release_type','Release type (album/EP/single)'),
        ('release_id','MusicBrainz release ID'),('releasegroup_id','MusicBrainz release-group ID')]
    ALBUM_FIELDS = {'albumartist','album','year','date','release_type','release_id','releasegroup_id','disc_total'}

    def __init__(self, parent, track: Track):
        super().__init__(parent)
        self.parent = parent
        self.track = track
        self.title('Edit track metadata · Oggcultist')
        self.transient(parent.winfo_toplevel())
        self.configure(background=PALETTE['bg'])
        self.grab_set()
        self.resizable(True, False)
        root = ttk.Frame(self,padding=16)
        root.pack(fill='both',expand=True)
        ttk.Label(root,text='Edit metadata',style='Title.TLabel').grid(row=0,column=0,columnspan=2,sticky='w',pady=(0,9))
        self.inputs: dict[str,tk.StringVar] = {}
        for i,(key,label) in enumerate(self.FIELDS,1):
            ttk.Label(root,text=label).grid(row=i,column=0,sticky='w',padx=(0,14),pady=3)
            var = tk.StringVar(value=str(getattr(track,key)))
            ttk.Entry(root,textvariable=var,width=49).grid(row=i,column=1,sticky='ew',pady=3)
            self.inputs[key] = var
        self.comp = tk.BooleanVar(value=track.compilation)
        ttk.Checkbutton(root,text='Genuine Various Artists compilation',variable=self.comp).grid(row=14,column=0,columnspan=2,sticky='w',pady=(9,1))
        self.alltracks = tk.BooleanVar(value=False)
        ttk.Checkbutton(root,text='Apply album-level fields to tracks from the same source album',variable=self.alltracks).grid(row=15,column=0,columnspan=2,sticky='w',pady=(2,8))
        buttons = ttk.Frame(root)
        buttons.grid(row=16,column=0,columnspan=2,sticky='e',pady=(8,0))
        ttk.Button(buttons,text='Cancel',command=self.destroy).pack(side='right',padx=(8,0))
        ttk.Button(buttons,text='Apply changes',command=self.apply,style='Accent.TButton').pack(side='right')
        root.columnconfigure(1,weight=1)
        self.bind('<Escape>',lambda e:self.destroy())

    def apply(self):
        if self.parent.busy:
            messagebox.showwarning('Library busy', 'Cannot edit tags during scanning or conversion.', parent=self)
            return
        values: dict[str,str|int] = {}
        for key,var in self.inputs.items():
            value = var.get().strip()
            if key in {'track','disc','track_total','disc_total'}:
                try: values[key] = int(value or '0')
                except ValueError:
                    messagebox.showerror('Invalid number',f'{key} must be a whole number.',parent=self)
                    return
            else: values[key] = value
        if values['year'] and (len(str(values['year'])) != 4 or not str(values['year']).isdigit()):
            messagebox.showerror('Invalid year','Original release year must be a four-digit year.',parent=self)
            return
        group = self.track.album_group()
        targets = [self.track]
        if self.alltracks.get():
            targets = [t for t in self.parent.tracks if t.album_group()==group]
        for t in targets:
            for key,val in values.items():
                if t is not self.track and key not in self.ALBUM_FIELDS: continue
                setattr(t,key,val)
                tagkey = {
                    'track':'tracknumber','disc':'discnumber','track_total':'totaltracks',
                    'disc_total':'totaldiscs','release_type':'releasetype',
                    'release_id':'musicbrainz_albumid','releasegroup_id':'musicbrainz_releasegroupid',
                    'year':'originaldate',
                }.get(key,key)
                t.set_tag(tagkey,str(val))
                if key == 'year': t.originaldate = str(val)
            t.compilation = self.comp.get()
            t.set_tag('compilation','1' if t.compilation else '0')
            t.lookup_issue = ''
        self.destroy()
        self.parent.replan()


class MatchPicker(tk.Toplevel):
    def __init__(self, parent, matches: list[dict], on_apply):
        super().__init__(parent)
        self.title('Review MusicBrainz matches')
        self.geometry('720x360')
        self.transient(parent.winfo_toplevel())
        self.configure(background=PALETTE['bg'])
        self.parent_page = parent
        self.grab_set()  # Prevent starting a conversion while a match is pending.
        self.matches = matches
        self.on_apply = on_apply
        ttk.Label(self,text='Choose a confirmed release group; ambiguous matches are never applied automatically.',wraplength=650).pack(anchor='w',padx=14,pady=14)
        self.lb = tk.Listbox(self,selectmode='browse',font='OgList',relief='flat',highlightthickness=1,
                             highlightbackground=PALETTE['border'],selectbackground=PALETTE['accent_soft'],
                             selectforeground=PALETTE['text'],activestyle='none')
        self.lb.pack(fill='both',expand=True,padx=14)
        for m in matches:
            self.lb.insert('end',f"{m['album']}  —  {m['albumartist']}  |  {m['year'] or '?'}  |  {m['releasetype']}  |  score {m['score']}")
        buttons = ttk.Frame(self,padding=14)
        buttons.pack(fill='x')
        ttk.Button(buttons,text='Close without changing',command=self.destroy).pack(side='right')
        ttk.Button(buttons,text='Use selected match',command=self.choose,style='Accent.TButton').pack(side='right',padx=(0,8))

    def choose(self):
        if self.parent_page.busy:
            messagebox.showwarning('Processing in progress',
                                   'Finish or cancel the current job before editing metadata.',parent=self)
            return
        sel = self.lb.curselection()
        if not sel: return
        selected = self.matches[sel[0]]
        if not selected['year']:
            messagebox.showwarning('No original year','This match has no reliable first release year.',parent=self)
            return
        self.on_apply(selected)
        self.destroy()
