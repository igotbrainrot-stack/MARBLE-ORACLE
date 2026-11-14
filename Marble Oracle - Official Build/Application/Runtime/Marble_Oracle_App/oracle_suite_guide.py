"""In-suite first-run/keyboard guide; no external browser or dependency.

Keeps the quirky Marble Oracle identity while making six embedded workspaces
findable for people who have never used the application before.
"""
from __future__ import annotations
import tkinter as tk
from marble_uberata import FAMILY

WORKSPACES = (
    ('HOME', 'tab_home', 'Oracle dashboard · runes, tarot, Latin, and rotating market pulse', '#FFB45C'),
    ('OGGCULTIST', 'tab_oggcultist', 'Audio collection, artwork and audio conversion tools', '#C2A4FF'),
    ('EIDOLITH', 'tab_eidolith', 'Local video conversion, queues and quality/size profiles', '#7ED8DE'),
    ('AUGURSPEX', 'tab_augurspex', 'Historical market charts, watchlists and source diagnostics', '#A9D68A'),
    ('PASSPHRASE', 'tab_passphrase', 'Interactive security and passphrase utilities', '#EAB881'),
    ('TOUCH TYPE', 'tab_touch_type', 'Typing practice and games', '#F39FA3'),
)

HOME_KEYS = (
    ('Space', 'Next quote / reading action'), ('Enter', 'Speak where enabled'),
    ('N', 'New Latin word'), ('T', 'Deal tarot'), ('V', 'Change GRADE layout'),
    ('F', 'Fullscreen'), ('C', 'CRT effect toggle'), ('M', 'Bezel style'),
    ('Escape', 'Exit when on HOME'),
)


def show_suite_guide(scene):
    old = getattr(scene, '_guide_window', None)
    if old is not None:
        try:
            if old.winfo_exists():
                old.lift();old.focus_set()
                return old
        except tk.TclError:
            pass
    root=scene.root
    win=tk.Toplevel(root)
    scene._guide_window=win
    win.title('MARBLE ORACLE · FIELD GUIDE')
    bg='#17120F';panel='#2C211B';fg='#F7EBE1';muted='#C6B6A9';accent='#FFA746'
    win.configure(bg=bg)
    sw, sh=root.winfo_screenwidth(),root.winfo_screenheight()
    w=max(520,min(840,sw-90));h=max(420,min(660,sh-90))
    win.geometry(f'{w}x{h}')
    win.transient(root)
    win.bind('<Escape>',lambda _e: win.destroy())
    head=tk.Frame(win,bg=bg);head.pack(fill='x',padx=24,pady=(20,8))
    tk.Label(head,text='MARBLE ORACLE',bg=bg,fg=accent,font=(FAMILY,24,'bold')).pack(anchor='w')
    tk.Label(head,text='FIELD GUIDE · CHOOSE A WORKSPACE · F1 TO REOPEN',bg=bg,fg=muted,
             font=(FAMILY,11)).pack(anchor='w',pady=(3,0))
    # Scroll the workspace list while keeping the RETURN action fixed; smaller
    # CRT apertures must never push the last workspace out of reach.
    body=tk.Frame(win,bg=bg);body.pack(fill='both',expand=True,padx=22)
    rail=tk.Scrollbar(body,orient='vertical')
    guide_canvas=tk.Canvas(body,bg=bg,bd=0,highlightthickness=0,
                           yscrollcommand=rail.set)
    rail.configure(command=guide_canvas.yview)
    rail.pack(side='right',fill='y')
    guide_canvas.pack(side='left',fill='both',expand=True)
    listframe=tk.Frame(guide_canvas,bg=bg)
    window=guide_canvas.create_window(0,0,window=listframe,anchor='nw')
    listframe.bind('<Configure>',lambda _e:guide_canvas.configure(
        scrollregion=guide_canvas.bbox('all')),add='+')
    guide_canvas.bind('<Configure>',lambda e:guide_canvas.itemconfigure(
        window,width=e.width),add='+')
    guide_canvas.bind('<MouseWheel>',lambda e:guide_canvas.yview_scroll(
        -int(e.delta/120)*2 if e.delta else 0,'units'),add='+')
    for i,(name,action,description,colour) in enumerate(WORKSPACES):
        section=tk.Frame(listframe,bg=panel,highlightbackground='#49382F',highlightthickness=1)
        section.grid(row=i,column=0,sticky='ew',padx=2,pady=3)
        stripe=tk.Frame(section,bg=colour,width=6);stripe.pack(side='left',fill='y')
        def go(command=action):
            win.destroy();scene.act(command)
        b=tk.Button(section,text=name,command=go,bg=panel,fg=colour,
                    font=(FAMILY,13,'bold'),activebackground='#46342B',activeforeground=fg,
                    relief='flat',anchor='w',bd=0,width=16,cursor='hand2',padx=10,pady=9)
        b.pack(side='left')
        tk.Label(section,text=description,bg=panel,fg=fg,wraplength=max(180,w-340),
                 justify='left',font=(FAMILY,10),anchor='w').pack(side='left',fill='x',expand=True,padx=(0,6))
    listframe.columnconfigure(0,weight=1)
    lower=tk.Frame(win,bg=bg);lower.pack(fill='x',padx=24,pady=(5,10))
    tk.Label(lower,text='HOME SHORTCUTS',bg=bg,fg=accent,font=(FAMILY,12,'bold')).pack(anchor='w')
    keys='   ·   '.join(f'{k} — {v}' for k,v in HOME_KEYS)
    tk.Label(lower,text=keys,bg=bg,fg=muted,font=(FAMILY,10),justify='left',
             wraplength=max(330,w-50),anchor='w').pack(fill='x',pady=(3,0))
    tk.Label(win,text='AUGURSPEX: click a chart to select; arrow keys inspect points; ATLAS compares markets. '
             'Displayed prices are historical and may be delayed.',bg=bg,fg=fg,font=(FAMILY,10),
             wraplength=max(330,w-50),justify='left').pack(fill='x',padx=24,pady=(0,10))
    tk.Button(win,text='RETURN TO SUITE',command=win.destroy,bg=accent,fg='#160F0A',
              font=(FAMILY,12,'bold'),bd=0,padx=16,pady=7,cursor='hand2').pack(pady=(0,15))
    return win
