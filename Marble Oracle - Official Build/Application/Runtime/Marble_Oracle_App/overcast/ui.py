"""OVERCAST native-Tk panel, embeddable without changes to Marble Oracle navigation."""
from __future__ import annotations

from datetime import datetime, date, timedelta, timezone
import json
import re
import calendar as std_calendar
from pathlib import Path
from queue import Empty, Queue
import sys
import threading
import tkinter as tk
from tkinter import messagebox, simpledialog, filedialog, ttk
import webbrowser

from . import EVENT_SCHEMA_VERSION, __version__, APP_NAME, TAGLINE
from .engine import NewsOracleEngine, CONTEXT_PROFILES, DEFAULT_CONTEXT_PROFILE, OperationCancelled
from .lmstudio import LMStudioClient, DEFAULT_URL, is_chat_model
from .calendar import on_day, TYPES
from .risk import focus_tags
from . import outlook as outlook_method
from .scopes import SCOPES
from . import theme as theme_mod

# Colour globals are bound from the active theme palette before any widget is built
# (see _set_palette); these defaults are the dark appearance.
BG=PANEL=PANEL2=INK=DIM=GOLD=LINE=GREEN=SIDEBAR=HOVER=CONTROL=RED=SELECT=ACCENT=ON_ACCENT=FAINT=''


def _set_palette(p):
    global BG,PANEL,PANEL2,INK,DIM,GOLD,LINE,GREEN,SIDEBAR,HOVER,CONTROL,RED,SELECT,ACCENT,ON_ACCENT,FAINT
    BG,PANEL,PANEL2,INK,DIM=p['bg'],p['card'],p['field'],p['ink'],p['dim']
    GOLD,LINE,GREEN,SIDEBAR=p['accent_text'],p['line'],p['green'],p['side']
    HOVER,CONTROL,RED,SELECT=p['field_hover'],p['field'],p['red'],p['select']
    ACCENT,ON_ACCENT,FAINT=p['accent'],p['on_accent'],p['faint']


_set_palette(theme_mod.palette())


# Jobs that take over the RESULTS reader while they run (and report failures there).
ANALYSIS_ACTIONS=('Generating forecast','Multi-source forecast','Making briefing','Building overview','Building broad outlook',
                  'Revising broad outlook')


# Canonical scope values are what the engine understands; people see sentence case.
SCOPE_LABELS={scope:scope.capitalize() for scope in SCOPES}
SCOPE_FROM_LABEL={label:scope for scope,label in SCOPE_LABELS.items()}


def friendly_date(value):
    try: return datetime.fromisoformat(value).strftime('%Y-%m-%d %H:%M')
    except (TypeError, ValueError): return (value or 'unknown')[:16]


class Tooltip:
    """Small hover hint. Purely cosmetic: failures never affect the app."""
    def __init__(self, widget, text, delay=550):
        self.widget, self.text, self.delay = widget, text, delay
        self._after = None; self._tip = None
        try:
            widget.bind('<Enter>', self._schedule, add='+')
            widget.bind('<Leave>', self._hide, add='+')
            widget.bind('<ButtonPress>', self._hide, add='+')
        except (tk.TclError, AttributeError, TypeError):
            pass

    def _schedule(self, _event=None):
        self._cancel()
        try: self._after = self.widget.after(self.delay, self._show)
        except tk.TclError: pass

    def _cancel(self):
        if self._after is not None:
            try: self.widget.after_cancel(self._after)
            except tk.TclError: pass
            self._after = None

    def _show(self):
        try:
            x = self.widget.winfo_rootx() + 12
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
            self._tip = tk.Toplevel(self.widget)
            self._tip.wm_overrideredirect(True)
            self._tip.wm_geometry(f'+{x}+{y}')
            self._tip.configure(bg=LINE)
            tk.Label(self._tip, text=self.text, justify='left', wraplength=320, bg=PANEL, fg=INK,
                     font=('TkDefaultFont', 9), padx=10, pady=6, relief='flat', bd=0).pack(padx=1, pady=1)
        except (tk.TclError, TypeError):
            self._tip = None

    def _hide(self, _event=None):
        self._cancel()
        if self._tip is not None:
            try: self._tip.destroy()
            except tk.TclError: pass
            self._tip = None


def spans_to_markdown(spans):
    """RESULTS spans -> Markdown: headings become '##', everything else is kept verbatim."""
    out = []
    for text, tag in spans:
        if tag == 'head':
            out.append('\n## ' + text.strip() + '\n\n')
        else:
            out.append(text)
    return ''.join(out).lstrip() + '\n'


class NewsOraclePanel(tk.Frame):
    def __init__(self, parent, *, state_dir=None, on_event=None, standalone=False, appearance=None, accent=None):
        self.engine=NewsOracleEngine(state_dir=state_dir)
        self._settings_path=Path(self.engine.store.state_dir)/'overcast_settings.json'
        early=self._load_settings()
        # 1.1.2: a host (Marble Oracle) may set the look; OVERCAST's own saved choice is then kept, not used.
        self._host_look=appearance in theme_mod.APPEARANCES
        self.theme=theme_mod.Theme(appearance if self._host_look else early.get('appearance',theme_mod.DEFAULT_APPEARANCE),
                                   accent if (self._host_look and accent in theme_mod.ACCENTS)
                                   else early.get('accent',theme_mod.DEFAULT_ACCENT))
        _set_palette(self.theme.p)
        super().__init__(parent,bg=BG)
        self.state_dir=state_dir
        self.on_event=on_event
        self.standalone=standalone
        self.theme.install(self,standalone=standalone)
        for warning in self.theme.warnings:   # visible in a terminal; summarised in Settings › About
            print(f'OVERCAST theme: {warning}',file=sys.stderr)
        legacy=Path(self.engine.store.state_dir)/'signal_settings.json'
        saved=early
        if not saved and legacy.is_file():   # carry SIGNAL 0.5.2–0.6 preferences across the rename
            try:saved=json.loads(legacy.read_text(encoding='utf-8'))
            except (OSError,ValueError):saved={}
            if not isinstance(saved,dict):saved={}
        profile=saved.get('context_profile')
        self.context=tk.StringVar(master=self,value=profile if profile in CONTEXT_PROFILES else DEFAULT_CONTEXT_PROFILE)
        runs=saved.get('runs')
        self.runs=tk.StringVar(master=self,value=str(runs) if runs in (1,2,3,4,5) else '3')
        self.engine.context_profile=self.context.get()
        self.engine.budget=CONTEXT_PROFILES[self.context.get()]
        hours=saved.get('auto_refresh_hours')
        self.auto_refresh=tk.StringVar(master=self,value=str(hours) if hours in (0,3,6,12) else '0')
        self._auto_after=None
        self._last_refresh=None
        self._palette=None
        self.ledger_filter=tk.StringVar(master=self,value='ALL')
        self.ledger_search=tk.StringVar(master=self)
        self._sort_state={}
        self._jobs=Queue()
        self._running=False
        self._cancel_event=None
        self._running_action=''
        self._closed=False
        self._poll_after=None
        self._articles={}
        self._forecasts={}
        self._briefings={}
        self._events={}
        self._selected_url=''
        self._result_spans=[]
        self._result_plain=''
        self._result_kind='WELCOME'
        self.scope=tk.StringVar(master=self,value='GLOBAL EVENTS')
        self.scope_label=tk.StringVar(master=self,value=SCOPE_LABELS['GLOBAL EVENTS'])
        def _label_changed(*_):
            value=SCOPE_FROM_LABEL.get(self.scope_label.get())
            if value and value!=self.scope.get():self.scope.set(value)
        def _scope_changed(*_):
            label=SCOPE_LABELS.get(self.scope.get())
            if label and label!=self.scope_label.get():self.scope_label.set(label)
        self.scope_label.trace_add('write',_label_changed)
        self.scope.trace_add('write',_scope_changed)
        self.scope_query=tk.StringVar()
        self.coverage_note=tk.StringVar(value='Choose a subject to review available coverage.')
        self.result_label=tk.StringVar(master=self,value='Select an analysis or open a saved report')
        self.page_title=tk.StringVar(master=self,value='Dashboard')
        self._font=self.theme.family
        self.appearance=tk.StringVar(master=self,value=self.theme.appearance)
        self.accent=tk.StringVar(master=self,value=self.theme.accent)
        self.model=tk.StringVar(value=str(saved.get('model_id') or '')[:200])
        self.extra_models=tk.StringVar()
        self.use_gaps=tk.BooleanVar(master=self,value=bool(saved.get('use_gaps',True)))
        self.use_timing=tk.BooleanVar(master=self,value=bool(saved.get('use_timing',True)))
        self.extra_models.set(str(saved.get('extra_models') or '')[:300])
        self._claims={}
        self.horizon=tk.StringVar(value='90')
        self.search_var=tk.StringVar()
        self.focus=tk.StringVar(value='FOCUS TOPICS')
        self._calendar_month=date.today().replace(day=1)
        self._calendar_day=date.today()
        self._calendar_items=[]
        self.status=tk.StringVar(master=self,value='Ready. Connect a model in Settings, then refresh feeds.')
        self._build()
        self.reload_all()
        self._restore_latest_result()
        self._update_scope_note()
        self._dashboard_ready=True
        self.reload_dashboard()
        self._update_chips()
        self._schedule_auto_refresh()
        self._poll_after=self.after(140,self._poll_jobs)

    # ── Widget helpers: every widget gets its colours from the active theme ──
    def _setup_style(self):
        s=ttk.Style(self)
        # The notebook only switches pages; navigation lives in the sidebar.
        s.layout('O.Hidden.TNotebook.Tab',[])
        # Only the client area, with no border (the base theme draws a light frame round it).
        s.layout('O.Hidden.TNotebook',[('Notebook.client',{'sticky':'nsew'})])
        s.configure('O.Hidden.TNotebook',background=BG,borderwidth=0,tabmargins=0,padding=0,
                    bordercolor=BG,lightcolor=BG,darkcolor=BG)
        s.configure('O.Hidden.TNotebook.Tab',padding=0)

    @staticmethod
    def _surface_of(widget):
        while widget is not None:
            surface=getattr(widget,'_ovc_surface',None)
            if surface:return surface
            widget=getattr(widget,'master',None)
        return 'bg'

    def _bg_of(self,widget):
        return self.theme.surface_colour(self._surface_of(widget))

    def _label(self,parent,text,*,size=10,color=None,bold=False,**kwargs):
        return tk.Label(parent,text=text,font=(self._font,size,'bold' if bold else 'normal'),
                        fg=color or INK,bg=self._bg_of(parent),**kwargs)

    def _btn(self,parent,text,command,accent=False,kind=None):
        kind=kind or ('accent' if accent else 'secondary')
        return ttk.Button(parent,text=text,command=command,cursor='hand2',takefocus=True,
                          style=self.theme.button(kind,self._surface_of(parent)))

    def _entry(self,parent,variable,width=20):
        return ttk.Entry(parent,textvariable=variable,width=width,font=(self._font,11),
                         style=self.theme.entry(self._surface_of(parent)))

    def _combo(self,parent,variable,values,width=10,readonly=True):
        return ttk.Combobox(parent,textvariable=variable,values=values,width=width,font=(self._font,11),
                            state='readonly' if readonly else 'normal',style=self.theme.combo(self._surface_of(parent)))

    def _chips(self,parent,variable,options,command=None):
        """Segmented control: a row of rounded pills; options = [(value, label)]."""
        row=tk.Frame(parent,bg=self._bg_of(parent))
        row._ovc_surface=self._surface_of(parent)
        for value,label in options:
            ttk.Radiobutton(row,text=label,value=value,variable=variable,command=command,cursor='hand2',
                            style=self.theme.chip(row._ovc_surface)).pack(side='left',padx=(0,2))
        return row

    def _switch(self,parent,text,variable,command=None):
        return ttk.Checkbutton(parent,text=text,variable=variable,command=command,cursor='hand2',
                               style='O.switch.TCheckbutton')

    def _surface(self,parent,role,padding=10):
        """'page' plain window background, 'card' rounded card, 'side' sidebar."""
        if role=='card':
            card_style='O.card.bg.TFrame' if 'cards' in self.theme.installed else 'O.card.TFrame'
            widget=ttk.Frame(parent,style=card_style,padding=padding)
            widget._ovc_surface='card'
        elif role=='side':
            widget=tk.Frame(parent,bg=SIDEBAR);widget._ovc_surface='side'
        else:
            widget=tk.Frame(parent,bg=BG);widget._ovc_surface='bg'
        return widget

    def _nav(self,parent,title,tab):
        b=ttk.Radiobutton(parent,text=title,value=title,variable=self._nav_var,cursor='hand2',
                          command=lambda:self._open_page(tab),style='O.nav.TRadiobutton')
        b.pack(fill='x',padx=10,pady=1)
        self._nav_map[tab]=b
        return b

    def _open_page(self,tab):
        self.tabs.select(tab)
        self._update_nav()

    def _update_nav(self,event=None):
        active=self.tabs.select()
        for tab,name,blurb in self._page_specs:
            if str(tab)==active:
                self._nav_var.set(name)
                self.page_title.set(name);self.page_blurb.set(blurb)
                if tab is getattr(self,'dashboard_tab',None) and getattr(self,'_dashboard_ready',False):
                    self.reload_dashboard()

    def _section(self,parent,title):
        label=self._label(parent,title,color=FAINT,size=9,bold=True)
        label.pack(anchor='w',padx=22,pady=(12,3))
        if not hasattr(self,'_section_labels'):self._section_labels=[]
        self._section_labels.append(label)

    def _separator(self,parent):
        tk.Frame(parent,bg=LINE,height=1).pack(fill='x',padx=15,pady=8)

    def _toolbar(self,parent):
        bar=tk.Frame(parent,bg=self._bg_of(parent));bar._ovc_surface=self._surface_of(parent)
        bar.pack(fill='x',pady=(0,10))
        return bar

    def _build(self):
        self._setup_style()
        self._ovc_surface='bg'
        shell=self._surface(self,'page')
        shell.pack(fill='both',expand=True)
        # ── Sidebar: brand, search, grouped navigation, live status ──
        rail=tk.Frame(shell,bg=SIDEBAR,width=220);rail._ovc_surface='side'
        rail.pack(side='left',fill='y')
        rail.pack_propagate(False)
        tk.Frame(shell,bg=LINE,width=1).pack(side='left',fill='y')
        brand=tk.Frame(rail,bg=SIDEBAR);brand.pack(fill='x',padx=20,pady=(20,12))
        self._brand=brand
        tk.Label(brand,text='☁',font=(self._font,20),fg=GOLD,bg=SIDEBAR).pack(side='left',padx=(0,8))
        names=tk.Frame(brand,bg=SIDEBAR);names.pack(side='left')
        tk.Label(names,text=APP_NAME.title(),font=(self._font,16,'bold'),fg=INK,bg=SIDEBAR,anchor='w').pack(anchor='w')
        tk.Label(names,text=TAGLINE,font=(self._font,8),fg=DIM,bg=SIDEBAR,anchor='w',justify='left',
                 wraplength=150).pack(anchor='w')
        search=self._btn(rail,'⌕   Search    Ctrl K',self.open_palette)
        search.pack(fill='x',padx=12,pady=(0,6))
        self._search_button=search
        Tooltip(search,'Jump to any page, run any action or switch scope.')
        main=self._surface(shell,'page')
        main.pack(side='right',fill='both',expand=True)
        # The title, command bar, pages and status line share one column. (1.1.1 made the pages a child of
        # `main` and then packed the status line `before` them from inside `content`, which real Tk refuses.)
        content=tk.Frame(main,bg=BG);content._ovc_surface='bg'
        self.content=content
        self.tabs=ttk.Notebook(content,style='O.Hidden.TNotebook')
        def page():
            f=tk.Frame(self.tabs,bg=BG);f._ovc_surface='bg';return f
        self.dashboard_tab=page();self.results_tab=page();self.outlook_tab=page();self.forecast_tab=page()
        self.calendar_tab=page();self.news_tab=page();self.events_tab=page();self.claims_tab=page()
        self.brief_tab=page();self.settings_tab=page();self.info_tab=page()
        self._page_specs=[
            (self.dashboard_tab,'Dashboard','Where things stand: the gloom index, top risks, what is due, and how accurate we have been.'),
            (self.results_tab,'Results','The full text of the latest report. Copy it, or export it as Markdown or text.'),
            (self.outlook_tab,'Outlooks','Broad predictions: scenarios, gloom index and scored signposts. Revise them as news arrives.'),
            (self.forecast_tab,'Ledger','Every forecast, permanently recorded. Filter, mark the bad-news direction, and record outcomes.'),
            (self.calendar_tab,'Calendar','Resolution deadlines, estimated event windows and sourced schedules.'),
            (self.news_tab,'News','Cached headlines. Select stories for a deep forecast or a briefing.'),
            (self.events_tab,'Clusters','Related headlines grouped into event candidates (not verified facts).'),
            (self.claims_tab,'Evidence','Claims extracted with exact source quotes, and shared-actor research leads.'),
            (self.brief_tab,'Briefings','Saved overviews and briefings.'),
            (self.settings_tab,'Settings','Model, context, ensemble runs, appearance, deep-forecast options and auto-refresh.'),
            (self.info_tab,'Methods','How OVERCAST forecasts, what it will not claim, and how it is scored.')]
        self._page_names=[(t,n) for t,n,_ in self._page_specs]
        for tab,name,_ in self._page_specs:self.tabs.add(tab,text=name)
        self._nav_map={}
        self._nav_var=tk.StringVar(master=self,value='Dashboard')
        groups=(('Overview',(0,1)),('Forecasts',(2,3,4)),('Research',(5,6,7,8)),('System',(9,10)))
        # The model-status footer is packed first so it keeps its place when the window is short.
        foot=tk.Frame(rail,bg=SIDEBAR)
        foot.pack(side='bottom',fill='x',padx=20,pady=(6,12))
        self._section_first_nav=[]
        for title,indices in groups:
            self._section(rail,title)
            for n,i in enumerate(indices):
                button=self._nav(rail,self._page_specs[i][1],self._page_specs[i][0])
                if n==0:self._section_first_nav.append(button)
        self.conn_note=tk.StringVar(master=self,value='● Model not connected')
        self.news_note=tk.StringVar(master=self,value='No news cached yet')
        self.conn_label=tk.Label(foot,textvariable=self.conn_note,font=(self._font,9,'bold'),fg=RED,bg=SIDEBAR,
                                 anchor='w',cursor='hand2',justify='left',wraplength=180)
        self.conn_label.pack(fill='x')
        self.conn_label.bind('<Button-1>',lambda e:self._open_page(self.settings_tab))
        tk.Label(foot,textvariable=self.news_note,font=(self._font,8),fg=DIM,bg=SIDEBAR,anchor='w',
                 wraplength=180,justify='left').pack(fill='x',pady=(2,0))
        self.rail_footer=foot
        rail.bind('<Configure>',self._fit_rail,add='+')
        # ── Large title + description ──
        content.pack(fill='both',expand=True,padx=28,pady=(22,0))
        header=tk.Frame(content,bg=BG);header.pack(fill='x')
        self.page_blurb=tk.StringVar(master=self,value='')
        self._title_label=tk.Label(header,textvariable=self.page_title,font=self.theme.fonts['title'],fg=INK,bg=BG,
                                   anchor='w')
        self._title_label.pack(anchor='w')
        self._blurb_label=tk.Label(header,textvariable=self.page_blurb,font=(self._font,10),fg=DIM,bg=BG,anchor='w',
                                   justify='left')
        self._blurb_label.pack(anchor='w',pady=(2,0))
        # ── Command bar: the same controls on every page ──
        bar_row=tk.Frame(content,bg=BG);bar_row._ovc_surface='bg'
        bar_row.pack(fill='x',pady=(16,4))
        # Two groups: the right one (Refresh, Cancel) drops to a second row when the column is narrow (_reflow).
        bar=tk.Frame(bar_row,bg=BG);bar._ovc_surface='bg'
        bar_mid=tk.Frame(bar_row,bg=BG);bar_mid._ovc_surface='bg'
        bar_end=tk.Frame(bar_row,bg=BG);bar_end._ovc_surface='bg'
        self._bar_groups=(bar_row,bar,bar_mid,bar_end)
        self._bar_layout=None
        scope_box=self._combo(bar,self.scope_label,[SCOPE_LABELS[s_] for s_ in SCOPES],width=21)
        scope_box.pack(side='left',padx=(0,8))
        scope_box.bind('<<ComboboxSelected>>',lambda e:self._update_scope_note())
        Tooltip(scope_box,'What to forecast about. Broad scopes sample recent cached news; '
                          'Selected headlines uses rows you pick on the News page.')
        days=self._combo(bar,self.horizon,('7','30','90','180','365'),width=4)
        days.pack(side='left')
        self._label(bar,'days',color=DIM,size=10).pack(side='left',padx=(6,14))
        Tooltip(days,'Forecast horizon in days. Every question must resolve within it.')
        primary=self._btn(bar_mid,'Broad outlook',self.generate_outlook,accent=True)
        primary.pack(side='left',padx=(0,8))
        Tooltip(primary,'Ctrl+Enter. Scenarios, gloom index and scored signposts for the scope (1 + RUNS model calls).')
        more=ttk.Menubutton(bar_mid,text='More  ▾',style='O.TMenubutton',cursor='hand2')
        menu=tk.Menu(more,tearoff=0,bg=PANEL,fg=INK,activebackground=SELECT,activeforeground=INK,
                     font=(self._font,11),relief='flat',bd=0)
        menu.add_command(label='Deep forecast — one question, 3+ lenses',command=self.multi_forecast)
        menu.add_command(label='Quick forecast — one call',command=self.forecast)
        menu.add_command(label='Overview briefing — no probabilities',command=self.generate_overview)
        menu.add_separator()
        menu.add_command(label='Revise selected outlook with fresh news',command=self.revise_selected_outlook)
        menu.add_command(label='Review coverage — no model call',command=self.review_coverage)
        more.configure(menu=menu)
        more.pack(side='left')
        self.cancel_button=self._btn(bar_end,'Cancel',self.cancel_job,kind='danger')
        self.cancel_button.configure(state='disabled')
        self.cancel_button.pack(side='right')
        Tooltip(self.cancel_button,'Esc. Stops before the next model call; nothing incomplete is saved.')
        feeds_btn=self._btn(bar_end,'⟳  Refresh',self.refresh)
        feeds_btn.pack(side='right',padx=(0,8))
        self._place_bar(None)
        Tooltip(feeds_btn,'F5. Refresh feeds: fetch the latest RSS headlines (the only time OVERCAST uses the internet).')
        note_row=tk.Frame(content,bg=BG);note_row._ovc_surface='bg'
        note_row.pack(fill='x',pady=(4,14))
        self.subject_entry=self._entry(note_row,self.scope_query,width=28)
        self.scope_query.trace_add('write',lambda *_:self._schedule_scope_note())
        self.subject_hint=self._label(note_row,'e.g. oil sanctions',color=FAINT,size=9)
        self.scope_caption=tk.Label(note_row,textvariable=self.coverage_note,font=(self._font,9),fg=DIM,
                                    bg=BG,anchor='w',justify='left')
        self.scope_caption.pack(side='left',fill='x',expand=True)
        self.scope_note_widget=self.scope_caption
        self.tabs.pack(fill='both',expand=True)
        self.tabs.bind('<<NotebookTabChanged>>',self._update_nav,add='+')
        self._dashboard_tab()
        self._results_tab()
        self._outlook_tab()
        self._news_tab()
        self._events_tab()
        self._claims_tab()
        self._forecast_tab()
        self._calendar_tab()
        self._brief_tab()
        self._settings_tab()
        self._info_tab()
        status=tk.Frame(content,bg=BG);status._ovc_surface='bg'
        status.pack(side='bottom',fill='x',pady=(10,14),before=self.tabs)
        self.status_dot=tk.Label(status,text='●',font=(self._font,9),fg=GREEN,bg=BG)
        self.status_dot.pack(side='left',padx=(0,6))
        tk.Label(status,textvariable=self.status,font=(self._font,10),bg=BG,fg=DIM,
                 anchor='w').pack(side='left',fill='x',expand=True)
        self._open_page(self.dashboard_tab)
        self._rail=rail
        self._brand_tagline=[w for w in names.winfo_children()][-1]
        content.bind('<Configure>',self._reflow,add='+')
        self.bind('<Configure>',self._fit_panel,add='+')

    # ── Responsive layout (1.1.2): the suite embeds OVERCAST in boxes as small as ~830x500 ──
    NARROW=760          # content-column width below which split views stack and Settings uses one column

    def _place_bar(self,width):
        """Flow the command bar's three groups (scope and days · Broad outlook and More · Refresh and Cancel) over as
        few rows as fit `width`; on one row the last group sits at the right edge."""
        row,*groups=self._bar_groups
        if width is None:
            rows=[groups]
        else:
            rows,current,used=[],[],0
            for group in groups:
                need=group.winfo_reqwidth()+8          # each group carries 8 px of right padding
                if current and used+need>width:
                    rows.append(current);current,used=[],0
                current.append(group);used+=need
            rows.append(current)
        layout=tuple(tuple(str(g) for g in r) for r in rows)
        if layout==self._bar_layout:return
        self._bar_layout=layout
        if not hasattr(self,'_bar_lines'):     # one frame per row; the groups are packed into them with `in_`
            self._bar_lines=[tk.Frame(row,bg=BG) for _ in groups]
        for group in groups:group.pack_forget()
        for line in self._bar_lines:line.pack_forget()
        for index,(line,members) in enumerate(zip(self._bar_lines,rows)):
            line.pack(side='top',fill='x',pady=(0 if index==0 else 8,0))
            for position,group in enumerate(members):
                at_right=len(rows)==1 and len(members)>1 and position==len(members)-1
                group.pack(in_=line,side='right' if at_right else 'left',padx=(0 if at_right else 0,0 if at_right else 8))
                group.lift(line)   # the groups were created before the row frames, so raise them above

    def _reflow(self,event):
        if event.widget is not self.content or event.width<=1:return
        width=event.width
        self._place_bar(width)
        narrow=width<self.NARROW
        if getattr(self,'_narrow',None)==narrow:return
        self._narrow=narrow
        for pane,children in getattr(self,'_split_panes',()):
            try:
                pane.configure(orient='vertical' if narrow else 'horizontal')
                pane._settled_for=None
                for child,minsize in children:
                    pane.paneconfigure(child,minsize=min(140,minsize) if narrow else minsize)
            except tk.TclError:
                pass
        place=getattr(self,'_place_settings',None)
        if place:place(narrow)

    def _fit_panel(self,event):
        if event.widget is not self or event.width<=1:return
        rail_width=220 if event.width>=1100 else (180 if event.width>=760 else 150)
        if getattr(self,'_panel_rail',None)!=rail_width:
            self._panel_rail=rail_width
            self._rail.configure(width=rail_width)
            self._search_button.configure(text='⌕   Search' if rail_width<180 else '⌕   Search    Ctrl K')
        # 0 roomy; 1 (under 820 px) no tagline, tighter group headings; 2 (under 640 px, the suite at 900x580)
        # no brand block or page description, no group headings, smaller title and rows.
        level=2 if event.height<640 else (1 if event.height<820 else 0)
        self._panel_height=event.height
        if getattr(self,'_panel_base',None)==level:return
        self._panel_base=level
        self._apply_panel_level(level)
        self.after_idle(self._settle_rail)

    def _rail_needs(self):
        """Height the sidebar's packed items ask for, padding included."""
        total=0
        for child in self._rail.pack_slaves():
            pady=child.pack_info().get('pady',0)
            pads=[int(float(v)) for v in re.findall(r'-?\d+(?:\.\d+)?',str(pady))] or [0]
            total+=child.winfo_reqheight()+(sum(pads) if len(pads)>1 else 2*pads[0])
        return total

    def _settle_rail(self):
        """If the sidebar still does not fit (larger fonts or DPI than expected), step up the compaction."""
        try:
            while self._panel_level<2 and self._rail_needs()>self._rail.winfo_height():
                self._apply_panel_level(self._panel_level+1)
                self.update_idletasks()
        except tk.TclError:
            pass

    def _apply_panel_level(self,level):
        self._panel_level=level
        self._panel_short=level==2
        short=level==2
        if level>=1:self._brand_tagline.pack_forget()
        else:self._brand_tagline.pack(anchor='w')
        if short:
            self._brand.pack_forget()
            self._blurb_label.pack_forget()
            self._search_button.pack_configure(pady=(12,4))
        else:
            self._brand.pack(fill='x',padx=20,pady=(16 if level else 20,10 if level else 12),before=self._search_button)
            self._blurb_label.pack(anchor='w',pady=(2,0))
            self._search_button.pack_configure(pady=(0,6))
        self._title_label.configure(font=self.theme.f(17,'bold') if short else self.theme.fonts['title'])
        for index,label in enumerate(getattr(self,'_section_labels',())):
            nav_after=self._section_first_nav[index]
            label.pack_forget()
            if short:   # the groups stay apart by a small gap instead of a heading
                if index:nav_after.pack_configure(pady=(9,1))
            else:
                nav_after.pack_configure(pady=1)
                label.pack(anchor='w',padx=22,pady=(8,2) if level else (12,3),before=nav_after)
        try:ttk.Style(self).configure('O.nav.TRadiobutton',font=self.theme.f(10 if short else 11))
        except tk.TclError:pass
        self.content.pack_configure(pady=(12 if short else 22,0))

    def _wrap_label(self,label,margin=4):
        """Wrap a label's text to the width it is given instead of a fixed number of pixels."""
        label.bind('<Configure>',lambda e:label.configure(wraplength=max(120,e.width-margin)),add='+')
        return label

    def _fit_rail(self,event):
        if event.widget is not self.rail_footer.master or event.height<=1:return
        short=event.height<820
        if getattr(self,'_rail_short',None)==short:return
        self._rail_short=short
        try:ttk.Style(self).configure('O.nav.TRadiobutton',padding=(8,0) if short else (8,3))
        except tk.TclError:pass

    def _results_tab(self):
        bar=self._toolbar(self.results_tab)
        tk.Label(bar,textvariable=self.result_label,font=(self._font,10),fg=DIM,bg=BG,anchor='w').pack(side='left')
        self._btn(bar,'Export…',self.export_result).pack(side='right',padx=(8,0))
        self._btn(bar,'Copy',self.copy_result).pack(side='right')
        frame,self.result_text=self._text_area(self.results_tab,reader=True)
        frame.pack(fill='both',expand=True)
        self._render_result('Welcome',[
            ('Welcome to OVERCAST\n','head'),
            (TAGLINE+' OVERCAST looks hardest at what could go wrong, then keeps itself honest by scoring every forecast.\n\n',''),
            ('Pick a scope in the command bar and choose Broad outlook. You get scenarios with probabilities, a gloom index, '
             'and specific signpost questions that are scored as they resolve. For one specific event, select its '
             'headlines on the News page and run a deep forecast.\n\n',''),
            ('Where results appear\n','head'),
            ('Reports appear here as soon as the local model finishes, and are saved, so they survive a restart.\n\n',''),
            ('Limits\n','head'),
            ('Broad scopes summarise recent cached RSS excerpts, not live prices, full articles or every global event. '
             'Check sources before relying on findings. Probabilities are uncalibrated until forecasts are resolved.\n','muted')],show=False)

    def _render_result(self,kind,spans,*,show=False):
        self._result_kind=kind
        self._result_spans=list(spans)
        self._result_plain=''.join(text for text,_ in spans)
        self.result_label.set(f'{kind}  ·  {len(self._result_plain):,} characters')
        self._set_text(self.result_text,spans)
        self.result_text.yview_moveto(0)
        if show:self._open_page(self.results_tab)

    def copy_result(self):
        if not self._result_plain:return
        self.clipboard_clear();self.clipboard_append(self._result_plain)
        self.status.set('Current analysis copied to clipboard.')

    def export_result(self):
        if not self._result_plain:return
        path=filedialog.asksaveasfilename(parent=self,title='Export OVERCAST report',
                     defaultextension='.md',filetypes=[('Markdown report','*.md'),('Text report','*.txt')],
                     initialfile='OVERCAST_Report.md')
        if path:
            try:
                body=spans_to_markdown(self._result_spans) if str(path).lower().endswith('.md') else self._result_plain
                Path(path).write_text(body,encoding='utf-8')
                self.status.set('Report exported: '+path)
            except OSError as exc:messagebox.showerror(APP_NAME,str(exc),parent=self)

    def _restore_latest_result(self):
        forecasts=self.engine.forecasts()
        briefs=self.engine.store.briefings()
        latest_f=forecasts[0] if forecasts else None
        latest_b=briefs[0] if briefs else None
        standalone=[f for f in forecasts if f['prompt_version'] not in outlook_method.SIGNPOST_PROMPT_VERSIONS]
        outlooks=self.engine.outlooks(1)
        latest_o=outlooks[0] if outlooks else None
        newest_other=[x['created'] for x in (standalone[0] if standalone else None,latest_b) if x]
        if latest_o and all(latest_o['created']>=c for c in newest_other):
            self._show_outlook(latest_o['id'])
        elif latest_f and (not latest_b or latest_f['created']>=latest_b['created']):
            self._select_tree(self.forecast_tree,latest_f['id'])
        elif latest_b:
            self._select_tree(self.brief_tree,latest_b['id'])

    def _schedule_scope_note(self):
        """Debounce: recount coverage once typing pauses, not on every keystroke."""
        pending=getattr(self,'_scope_after',None)
        if pending is not None:
            try:self.after_cancel(pending)
            except tk.TclError:pass
        self._scope_after=self.after(350,self._update_scope_note)

    def _update_scope_note(self):
        self._scope_after=None
        scope=self.scope.get()
        if hasattr(self,'scope_caption'):
            if scope=='CUSTOM SUBJECT' and not self.subject_entry.winfo_manager():
                self.subject_entry.pack(side='left',padx=(0,6),ipady=3,before=self.scope_caption)
                self.subject_hint.pack(side='left',padx=(0,10),before=self.scope_caption)
            elif scope!='CUSTOM SUBJECT':
                self.subject_entry.pack_forget()
                self.subject_hint.pack_forget()
        if scope=='SELECTED HEADLINES':
            self.coverage_note.set('Select stories on the News page (Ctrl- or Shift-click).')
            return
        try:
            chosen=self.engine.coverage(scope,query=self.scope_query.get())
            self.coverage_note.set(f"Evidence: {chosen['selected_count']} of {chosen['fresh_count']} recent matching items "
                f"from {chosen['publisher_count']} sources (cached RSS, not complete coverage).")
        except ValueError as exc:self.coverage_note.set(str(exc))

    def _coverage(self):
        scope=self.scope.get()
        if scope=='SELECTED HEADLINES':
            ids=self._selected_ids()
            return ids,{'scope':scope,'article_ids':ids,'selected_count':len(ids),
                        'matched_count':len(ids),'fresh_count':len(ids),'publisher_count':None,
                        'coverage_warning':'Manually selected cached RSS snippets; not fact-checked.'}
        selected=self.engine.coverage(scope,query=self.scope_query.get(),limit=16)
        if not selected['article_ids']:
            raise ValueError('No recent cached reports for this subject. Refresh feeds, then retry or change the scope.')
        return selected['article_ids'],selected

    def review_coverage(self):
        try:
            ids,coverage=self._coverage()
            preview=self.engine.research_preview(ids)
        except ValueError as exc:
            messagebox.showwarning(APP_NAME,str(exc),parent=self);return
        rows=preview['articles']
        lines=[(f"Coverage review — {coverage['scope'].title()}\n",'head'),
              (self.coverage_note.get()+'\n\n','muted'),
              (f"{len(rows)} reports in preview from {preview['publisher_count']} publisher domains.\n"
               'Publisher count is not proof of independent confirmation.\n\n',''),
              ('Evidence list\n','head')]
        lines.extend((f"[{r['id']}] {r['publisher']}  |  {r['published_utc']}\n"
                      f"{r['title']}\n{r['rss_excerpt']}\n{r['url']}\n\n",'') for r in rows)
        lines.extend([('Limitations\n','head'),('\n'.join(preview['cautions'])+'\n','muted')])
        self._render_result('Coverage review',lines,show=True)

    def generate_overview(self):
        try:
            ids,coverage=self._coverage();model=self._model_id();days=int(self.horizon.get())
        except ValueError as exc:
            messagebox.showwarning(APP_NAME,str(exc),parent=self);return
        scope=coverage['scope']
        def task(progress,cancel):
            e=self._new_worker_engine()
            try:return e.overview(ids,model,scope=scope,horizon_days=days,coverage=coverage,
                                  progress=progress,cancel=cancel)
            finally:e.close()
        self._job('Building overview',task,staged=True)

    def _outlook_tab(self):
        row=self._toolbar(self.outlook_tab)
        self._btn(row,'Refresh',self.reload_outlooks,kind='plain').pack(side='left')
        self._btn(row,'Record scenario outcome…',self._resolve_outlook).pack(side='right',padx=(8,0))
        revise=self._btn(row,'Revise with fresh news',self.revise_selected_outlook,accent=True)
        revise.pack(side='right')
        Tooltip(revise,'Re-forecast this outlook\'s open signposts and scenarios on the latest cached news. '
                       'The original stays in the ledger; frequent updating is a core accuracy habit.')
        pane=self._pane(self.outlook_tab,'vertical')
        pane.pack(fill='both',expand=True)
        left,self.outlook_tree=self._tree(pane,('id','created','deadline','index','pbad','question'),
                    ('#','Created','Until','Gloom','P(bad)','Strategic question'),(46,130,95,64,64,600))
        pane.add(left,minsize=150,stretch='always')
        right,self.outlook_text=self._text_area(pane)
        pane.add(right,minsize=190,stretch='always')
        self.outlook_tree.bind('<<TreeviewSelect>>',lambda e:self._show_outlook())
        self._outlooks={}

    def generate_outlook(self):
        try:
            ids,coverage=self._coverage();model=self._model_id();days=int(self.horizon.get())
        except ValueError as exc:
            messagebox.showwarning(APP_NAME,str(exc),parent=self);return
        scope=coverage['scope'];query=self.scope_query.get().strip() if scope=='CUSTOM SUBJECT' else ''
        runs=self._runs()
        def task(progress,cancel):
            e=self._new_worker_engine()
            try:return e.broad_outlook(ids,model,scope=scope,query=query,horizon_days=days,runs=runs,
                                       coverage=coverage,progress=progress,cancel=cancel)
            finally:e.close()
        self._job('Building broad outlook',task,staged=True)

    def reload_outlooks(self):
        rows=self.engine.outlooks()
        self._outlooks={str(o['id']):o for o in rows}
        self.outlook_tree.delete(*self.outlook_tree.get_children())
        for o in rows:
            p_bad=(o.get('audit') or {}).get('aggregation',{}).get('p_adverse_scenarios')
            mark=' ↻' if o.get('revision_of') else ''
            self.outlook_tree.insert('','end',iid=str(o['id']),values=(o['id'],friendly_date(o['created']),
                o['deadline'],f"{o['stress_index']:+.0f}",f"{p_bad:.0%}" if p_bad is not None else '—',
                o['strategic_question']+mark))
        if rows:self._select_tree(self.outlook_tree,rows[0]['id'])
        else:self._set_text(self.outlook_text,[('No broad outlooks yet\n','head'),
            ('Choose a scope in the command bar and press Broad outlook. The broad question is split into drivers and '
             'specific signpost questions; scenario probabilities and a gloom index come from several independent runs. '
             'Signposts go into the Ledger, so the outlook is scored as they resolve.\n','')])

    def _outlook_spans(self,item):
        calibrated={}
        for sp in item.get('signposts',[]):
            value=self.engine.calibrated_probability(sp['probability'])
            if value:calibrated[sp['forecast_id']]=value
        spans=[]
        for i,(heading,body,style) in enumerate(outlook_method.report_sections(item,calibrated)):
            spans+=[(heading+'\n','head'),(body+'\n\n',(style if style in ('muted','adverse','good') else '') if i else 'muted')]
        return spans

    def _show_outlook(self,outlook_id=None,open_results=False):
        if outlook_id is None:
            selected=self.outlook_tree.selection()
            if not selected:return
            outlook_id=int(selected[0])
        item=self.engine.outlook_detail(outlook_id)
        if not item:return
        spans=self._outlook_spans(item)
        self._set_text(self.outlook_text,spans)
        self._render_result('Broad outlook #'+str(item['id']),spans,show=open_results)

    def _resolve_outlook(self):
        selected=self.outlook_tree.selection()
        if len(selected)!=1:
            messagebox.showwarning(APP_NAME,'Select one broad outlook.',parent=self);return
        item=self.engine.outlook_detail(int(selected[0]))
        letters=', '.join(f"{s['id']} = {s['name']}" for s in item['scenarios'])
        letter=simpledialog.askstring('Which scenario happened?',
            f'Outlook #{item["id"]} ran to {item["deadline"]}.\nEnter the scenario letter that matches what happened:\n{letters}',parent=self)
        if letter is None:return
        url=simpledialog.askstring('Resolution evidence','Published evidence URL supporting that scenario:',parent=self)
        if url is None:return
        note=simpledialog.askstring('Resolution note','How were the scenario\'s defining conditions met?',parent=self)
        if note is None:return
        try:self.engine.resolve_outlook(item['id'],letter.strip().upper(),url.strip(),note.strip())
        except ValueError as exc:
            messagebox.showerror(APP_NAME,str(exc),parent=self);return
        self.reload_outlooks();self._select_tree(self.outlook_tree,item['id'])
        self.status.set(f"Outlook #{item['id']} scenario resolved; multiclass scenario score updated.")
        self._emit('outlook_resolved',id=item['id'],scenario=letter.strip().upper())

    # ── DASHBOARD ─────────────────────────────────────────────────────────
    def _dashboard_tab(self):
        strip=self._toolbar(self.dashboard_tab)
        self.dash_news=tk.StringVar(master=self,value='')
        # Buttons are packed first, so on a narrow page the caption gives way, not them.
        self._btn(strip,'Top risks',lambda:self._show_ledger('TOP RISKS')).pack(side='right',padx=(8,0))
        self._btn(strip,'Due to resolve',lambda:self._show_ledger('DUE — RESOLVE')).pack(side='right')
        tk.Label(strip,textvariable=self.dash_news,font=(self._font,9),fg=DIM,bg=BG,anchor='w').pack(side='left',fill='x',expand=True)
        grid=tk.Frame(self.dashboard_tab,bg=BG);grid._ovc_surface='bg';grid.pack(fill='both',expand=True)
        for c in range(2):grid.grid_columnconfigure(c,weight=1,uniform='dash')
        for r in range(2):grid.grid_rowconfigure(r,weight=1,uniform='dashr')
        self.dash_cards={}
        for (r,c),key,title in (((0,0),'gloom','Gloom index'),((0,1),'risks','Top open risks'),
                                ((1,0),'due','Coming up and due'),((1,1),'record','Track record')):
            card=self._surface(grid,'card',padding=14)
            card.grid(row=r,column=c,sticky='nsew',padx=(0 if c==0 else 7,7 if c==0 else 0),pady=(0 if r==0 else 7,7 if r==0 else 0))
            tk.Label(card,text=title,font=self.theme.fonts['headline'],fg=INK,bg=PANEL,anchor='w').pack(fill='x',padx=4,pady=(2,4))
            text=tk.Text(card,wrap='word',relief='flat',bg=PANEL,fg=INK,padx=4,pady=2,height=8,
                         font=(self._font,11),borderwidth=0,highlightthickness=0,cursor='arrow',spacing1=3,spacing3=3,
                         selectbackground=SELECT,inactiveselectbackground=SELECT)
            text.pack(fill='both',expand=True)
            for tag,cfg in (('muted',{'foreground':DIM}),('adverse',{'foreground':RED}),('good',{'foreground':GREEN}),
                            ('big',{'font':self.theme.fonts['big']}),('head',{'foreground':INK,'font':(self._font,11,'bold')}),
                            ('link',{'foreground':GOLD})):
                text.tag_configure(tag,**cfg)
            text.config(state='disabled')
            self.dash_cards[key]=text

    def _write_card(self,key,items):
        """items: (text, tag) or (text, tag, callback). Callbacks become clickable links."""
        text=self.dash_cards[key]
        text.config(state='normal');text.delete('1.0','end')
        for n,item in enumerate(items):
            content,tag=item[0],item[1]
            if len(item)>2 and item[2]:
                name=f'link{n}'
                text.insert('end',content,(tag or 'link',name))
                text.tag_configure(name,underline=False)
                text.tag_bind(name,'<Button-1>',lambda e,fn=item[2]:fn())
                text.tag_bind(name,'<Enter>',lambda e,t=text,n=name:(t.config(cursor='hand2'),t.tag_configure(n,underline=True)))
                text.tag_bind(name,'<Leave>',lambda e,t=text,n=name:(t.config(cursor='arrow'),t.tag_configure(n,underline=False)))
            else:
                text.insert('end',content,tag)
        text.config(state='disabled')

    def reload_dashboard(self):
        if not hasattr(self,'dash_cards'):return
        today=datetime.now(timezone.utc).date()
        articles=self.engine.store.articles(1)
        total_articles=self.engine.store.db.execute('SELECT count(*) FROM articles').fetchone()[0]
        outlooks=self.engine.outlooks(1)
        # Gloom index card (or onboarding when empty).
        if not outlooks:
            connected=getattr(self,'_connected',False)
            self._write_card('gloom',[
                ('Three steps to your first broad prediction:\n\n','muted'),
                (('✓ ' if connected else '1  ')+'Connect a local model in LM Studio  ','good' if connected else ''),
                ('open Settings\n','link',lambda:self._open_page(self.settings_tab)),
                (('✓ ' if total_articles else '2  ')+f'Fetch headlines ({total_articles} cached)  ','good' if total_articles else ''),
                ('refresh feeds\n','link',self.refresh),
                ('3  Pick a scope above and choose Broad outlook  ',''),
                ('run it now\n','link',self.generate_outlook)])
        else:
            o=self.engine.outlook_detail(outlooks[0]['id'])
            agg=(o.get('audit') or {}).get('aggregation') or {}
            idx=o['stress_index'];p_bad=agg.get('p_adverse_scenarios')
            tone='adverse' if idx>=15 or (p_bad or 0)>=0.5 else ('good' if idx<=-15 else '')
            items=[(f'{idx:+.0f}  ','big'),(outlook_method.index_label(idx)+'\n',tone)]
            if p_bad is not None:items.append((f'Chance things go badly: {p_bad:.0%}\n',tone or ''))
            items+=[(o['strategic_question']+'\n',''),
                    (f"{o['scope']} · to {o['deadline']} · {o.get('signposts_resolved',0)}/{len(o.get('signposts',[]))} signposts resolved\n",'muted'),
                    ('Open full outlook','link',lambda oid=o['id']:self._show_outlook(oid,open_results=True)),('    ',''),
                    ('Revise with fresh news','link',lambda oid=o['id']:self.revise_outlook_id(oid))]
            self._write_card('gloom',items)
        # Risk register card.
        risks=self.engine.risk_register(6)
        if risks:
            items=[('chance of bad news × severity (1–5)\n','muted')]
            for r in risks:
                tone='adverse' if r['risk_score']>=2.5 else ''
                items+=[(f"{r['risk_score']:.1f}  ",tone),(f"{r['p_adverse']:.0%}×{r['severity']}  ",'muted'),
                        (r['question'][:110],'link',lambda fid=r['id']:self._show_forecast_id(fid)),(f"  by {r['target_date']}\n",'muted')]
        else:
            items=[('No open risks with a known bad-news direction yet.\n\n',''),
                   ('Broad outlook signposts are added automatically. For other forecasts, use Mark bad news in the Ledger.\n','muted')]
        self._write_card('risks',items)
        # Due and upcoming card.
        forecasts=self.engine.forecasts(2000)
        open_rows=[f for f in forecasts if f['outcome'] is None]
        due=[f for f in open_rows if f['target_date']<today.isoformat()]
        soon=sorted((f for f in open_rows if today.isoformat()<=f['target_date']<=(today+timedelta(days=21)).isoformat()),
                    key=lambda f:f['target_date'])
        items=[]
        if due:
            items+=[(f'{len(due)} forecast(s) past deadline need an outcome. ','adverse'),
                    ('Resolve now\n','link',lambda:self._show_ledger('DUE — RESOLVE')),
                    ('Unresolved misses quietly flatter the score.\n\n','muted')]
            for f in due[:3]:
                items+=[(f"#{f['id']} ",'muted'),(f['question'][:100],'link',lambda fid=f['id']:self._show_forecast_id(fid)),('\n','')]
            items.append(('\n',''))
        items.append(('Next 21 days\n','head'))
        if soon:
            for f in soon[:5]:
                items+=[(f"{f['target_date']}  ",'muted'),(f['question'][:95],'link',lambda fid=f['id']:self._show_forecast_id(fid)),('\n','')]
        else:
            items.append(('Nothing resolves in the next three weeks.\n','muted'))
        self._write_card('due',items)
        # Track record card.
        rep=self.engine.score_report()
        unique=rep.get('by_question') or {}
        n=unique.get('count') or 0
        if not n:
            items=[('No resolved forecasts yet.\n\n',''),
                   ('Accuracy is measured, not claimed: resolve forecasts as they fall due, and this card shows '
                    'Brier score, log loss, gloom bias and calibration.\n','muted')]
        else:
            brier=unique['brier']
            better=brier<0.25
            items=[(f"{n} question{'s' if n!=1 else ''} resolved · ",''),(f'Brier {brier:.3f} ','good' if better else 'adverse'),
                   (f"({'better' if better else 'worse'} than coin-flip 0.250)\n",'muted')]
            if unique.get('log_loss') is not None:items.append((f"Log loss {unique['log_loss']:.3f} (coin-flip 0.693)\n",'muted'))
            g=rep.get('gloom_bias') or {}
            if g.get('gloom_bias_points') is not None:
                items.append((f"Gloom bias {g['gloom_bias_points']:+.1f} pts — ",'adverse' if g['verdict'].startswith(('TOO','NOT')) else ''))
            items.append(((g.get('verdict') or '')+'\n',''))
            cal=rep.get('recalibration') or {}
            items.append(('Calibration: '+(cal.get('note') or '')+'\n','muted'))
            misses=rep.get('biggest_misses') or []
            if misses:
                m=misses[0]
                items+=[('Biggest miss: ','muted'),(m['question'][:90],'link',lambda fid=m['id']:self._show_forecast_id(fid)),
                        (f" ({m['probability']:.0%}, was {'YES' if m['outcome'] else 'NO'})\n",'muted')]
        self._write_card('record',items)
        # News strip.
        newest=articles[0]['collected'] if articles else None
        refresh=self._last_refresh
        bits=[f'{total_articles} headlines cached']
        if newest:bits.append('newest fetched '+friendly_date(newest)+' UTC')
        sources=(refresh or {}).get('sources') or []
        if sources:
            ok=sum(1 for x in sources if not x.get('error'))
            bits.append(f"last refresh {ok}/{len(sources)} feeds OK")
        hours=self.auto_refresh.get()
        bits.append(f'auto-refresh every {hours} h' if hours not in ('0','') else 'auto-refresh off')
        self.dash_news.set('   ·   '.join(bits))
        self._update_chips()

    def _show_ledger(self,mode):
        self.ledger_filter.set(mode);self.ledger_search.set('')
        self.reload_forecasts();self._open_page(self.forecast_tab)

    def _show_forecast_id(self,forecast_id):
        if not self.forecast_tree.exists(str(forecast_id)):
            self.ledger_filter.set('ALL');self.ledger_search.set('');self.reload_forecasts()
        self._select_tree(self.forecast_tree,forecast_id)
        self._open_page(self.forecast_tab)

    def _update_chips(self):
        if not hasattr(self,'conn_note'):return
        model=self.model.get().strip()
        short=(model[:22]+'…') if len(model)>23 else model
        if getattr(self,'_connected',False) and model:
            self.conn_note.set(f'● {short} · {self.context.get()} · {self._runs()} runs');self.conn_label.configure(fg=GREEN)
        elif model:
            self.conn_note.set(f'● {short} (not checked) — CONNECT');self.conn_label.configure(fg=GOLD)
        else:
            self.conn_note.set('● Model not connected · open Settings');self.conn_label.configure(fg=RED)
        try:
            count=self.engine.store.db.execute('SELECT count(*) FROM articles').fetchone()[0]
            newest=self.engine.store.articles(1)
            self.news_note.set(f'{count} headlines cached' + (f' · newest {friendly_date(newest[0]["collected"])}' if newest else ''))
        except Exception:
            pass

    # ── SETTINGS ──────────────────────────────────────────────────────────
    def _settings_tab(self):
        # 1.1.2: the page scrolls (its cards are taller than small windows) and uses one column when narrow.
        holder=tk.Frame(self.settings_tab,bg=BG);holder._ovc_surface='bg';holder.pack(fill='both',expand=True)
        canvas=tk.Canvas(holder,bg=BG,highlightthickness=0,bd=0)
        bar=ttk.Scrollbar(holder,orient='vertical',command=canvas.yview,style='O.Vertical.TScrollbar')
        canvas.configure(yscrollcommand=bar.set)
        canvas.pack(side='left',fill='both',expand=True)
        cols=tk.Frame(canvas,bg=BG);cols._ovc_surface='bg'
        window=canvas.create_window(0,0,anchor='nw',window=cols)
        def fit(_event=None):
            canvas.itemconfigure(window,width=max(1,canvas.winfo_width()-2))
            canvas.configure(scrollregion=(0,0,canvas.winfo_width(),cols.winfo_reqheight()))
            needed=cols.winfo_reqheight()>canvas.winfo_height()+2
            if needed and not bar.winfo_ismapped():bar.pack(side='right',fill='y',padx=(6,0))
            elif not needed and bar.winfo_ismapped():bar.pack_forget();canvas.yview_moveto(0)
        canvas.bind('<Configure>',fit,add='+');cols.bind('<Configure>',fit,add='+')
        def wheel(event):
            if bar.winfo_ismapped():
                canvas.yview_scroll(-1 if (getattr(event,'delta',0)>0 or event.num==4) else 1,'units')
        for sequence in ('<MouseWheel>','<Button-4>','<Button-5>'):
            canvas.bind_all(sequence,lambda e:wheel(e) if self.tabs.select()==str(self.settings_tab) and
                            str(e.widget).startswith(str(holder)) else None,add='+')
        left=tk.Frame(cols,bg=BG);left._ovc_surface='bg'
        right=tk.Frame(cols,bg=BG);right._ovc_surface='bg'
        def place(narrow):
            left.grid_forget();right.grid_forget()
            for column in (0,1):cols.grid_columnconfigure(column,weight=0,uniform='')
            if narrow:
                cols.grid_columnconfigure(0,weight=1)
                left.grid(row=0,column=0,sticky='nsew')
                right.grid(row=1,column=0,sticky='nsew')
            else:
                cols.grid_columnconfigure(0,weight=1,uniform='settings');cols.grid_columnconfigure(1,weight=1,uniform='settings')
                left.grid(row=0,column=0,sticky='nsew',padx=(0,7))
                right.grid(row=0,column=1,sticky='nsew',padx=(7,0))
        self._place_settings=place
        place(False)

        def group(parent,title):
            self._label(parent,title,color=DIM,size=9,bold=True).pack(anchor='w',padx=6,pady=(0,4))
            card=self._surface(parent,'card',padding=(14,8));card.pack(fill='x',pady=(0,12))
            card.grid_columnconfigure(0,weight=1)
            card._row=0
            return card

        def row(card,label,widget,hint=None):
            # When the card is narrow the control column gives way, never the label.
            card.grid_columnconfigure(0,weight=0)
            card.grid_columnconfigure(1,weight=1)
            tk.Label(card,text=label,font=(self._font,11),fg=INK,bg=PANEL,anchor='w').grid(
                row=card._row,column=0,sticky='w',pady=(4,0))
            widget.grid(row=card._row,column=1,sticky='e',pady=(4,0),padx=(12,0))
            card._row+=1
            if hint:
                self._wrap_label(tk.Label(card,text=hint,font=(self._font,9),fg=DIM,bg=PANEL,anchor='w',justify='left',
                                          wraplength=340)).grid(row=card._row,column=0,columnspan=2,sticky='ew',pady=(1,4))
                card._row+=1

        model=group(left,'Local model')
        picker=tk.Frame(model,bg=PANEL);picker._ovc_surface='card'
        self.model_choice=self._combo(picker,self.model,(),width=24,readonly=False)
        self.model_choice.pack(side='left',padx=(0,8))
        self.model_choice.bind('<<ComboboxSelected>>',lambda e:(self._save_settings(),self._update_chips()))
        self._btn(picker,'Connect',self.connect,accent=True).pack(side='left')
        row(model,'Model',picker,f'Load a chat model in LM Studio and start its local server ({DEFAULT_URL}). '
            'Connect lists loaded models; embedding models are never picked automatically.')
        row(model,'Context',self._chips(model,self.context,[(k,k) for k in CONTEXT_PROFILES],command=self._apply_context),
            "Match the context length the model is loaded with. 8K is safest after a GPU error.")
        row(model,'Ensemble runs',self._chips(model,self.runs,[(str(n),str(n)) for n in range(1,6)],
            command=lambda:(self._save_settings(),self._update_chips(),self.status.set(
                f'Ensemble runs set to {self._runs()}: independent model runs averaged per forecast.'))),
            'Independent runs averaged per forecast: one of the best-supported accuracy techniques. '
            'A broad outlook costs 1 + runs model calls.')
        extra=self._entry(model,self.extra_models,width=26)
        extra.bind('<FocusOut>',lambda e:self._save_settings())
        row(model,'Extra models',extra,'Optional: up to two more loaded model IDs, comma-separated. '
            'Deep forecasts rotate their lenses across them.')

        deep=group(left,'Deep forecasts')
        row(deep,'Counter-evidence search',self._switch(deep,'',self.use_gaps,self._save_settings),
            'Looks for cached reports that argue against the forecast (one extra call).')
        row(deep,'Event-timing windows',self._switch(deep,'',self.use_timing,self._save_settings),
            'Estimates when the event would happen if it does (one extra call).')

        look=group(right,'Appearance')
        mode_chips=self._chips(look,self.appearance,(('dark','Dark'),('light','Light')),command=self._apply_appearance)
        accent_chips=self._chips(look,self.accent,[(a,a) for a in theme_mod.ACCENTS],command=self._apply_appearance)
        row(look,'Mode',mode_chips)
        row(look,'Accent',accent_chips,
            'Follows Marble Oracle (its sidebar › Appearance).' if self._host_look else
            'Applies the next time OVERCAST opens.')
        if self._host_look:
            for chips in (mode_chips,accent_chips):
                for chip in chips.winfo_children():
                    chip.state(['disabled'])

        feeds=group(right,'News feeds')
        row(feeds,'Auto-refresh',self._chips(feeds,self.auto_refresh,(('0','Off'),('3','3 h'),('6','6 h'),('12','12 h')),
            command=lambda:(self._save_settings(),self._schedule_auto_refresh(),self.reload_dashboard())),
            'Only downloads RSS headlines on a schedule while OVERCAST is open; it never runs a model on its own.')

        data=group(right,f'About OVERCAST {__version__}')
        path=self._wrap_label(tk.Label(data,text=str(self.engine.store.state_dir),font=(self.theme.mono,9),fg=INK,bg=PANEL,
                                       anchor='w',justify='left',wraplength=330))
        path.grid(row=data._row,column=0,columnspan=2,sticky='ew',pady=(6,2));data._row+=1
        self._wrap_label(tk.Label(data,text='Back this folder up with OVERCAST closed. Upgrades never delete it.',
                                  font=(self._font,9),fg=DIM,bg=PANEL,anchor='w',justify='left')).grid(
                                  row=data._row,column=0,columnspan=2,sticky='ew');data._row+=1
        tk.Label(data,text='Ctrl K  search & commands   ·   Ctrl ↵  broad outlook\nF5  refresh feeds   ·   Esc  cancel   ·   '
                 'Ctrl 1–9  pages',font=(self._font,9),fg=INK,bg=PANEL,anchor='w',justify='left').grid(
                 row=data._row,column=0,columnspan=2,sticky='w',pady=(10,4));data._row+=1
        look_note=(f'Font: {self.theme.family}. Rounded controls: '
                   +('all active.' if not self.theme.warnings else
                     f"{len(self.theme.warnings)} part(s) fell back to flat style on this Tk ({tk.TkVersion})."))
        self._wrap_label(tk.Label(data,text=look_note,font=(self._font,9),fg=DIM,bg=PANEL,anchor='w',justify='left',
                                  wraplength=340)).grid(row=data._row,column=0,columnspan=2,sticky='ew',pady=(2,4));data._row+=1

    def _apply_appearance(self):
        self._save_settings()
        changed=(self.appearance.get(),self.accent.get())!=(self.theme.appearance,self.theme.accent)
        self.status.set(f'{self.appearance.get().title()} mode, {self.accent.get()} accent'
                        +(' will apply the next time OVERCAST opens.' if changed else ' is active.'))

    # ── COMMAND PALETTE & SHORTCUTS ───────────────────────────────────────
    def _commands(self):
        cmds=[(f'Go to {name.title()}',lambda t=tab:self._open_page(t)) for tab,name,_ in self._page_specs]
        cmds+=[('Broad outlook for the current scope',self.generate_outlook),
               ('Deep forecast (one question)',self.multi_forecast),
               ('Quick forecast',self.forecast),
               ('Overview briefing',self.generate_overview),
               ('Revise selected outlook with fresh news',self.revise_selected_outlook),
               ('Refresh feeds',self.refresh),
               ('Connect to LM Studio',self.connect),
               ('Show top risks',lambda:self._show_ledger('TOP RISKS')),
               ('Show forecasts due to resolve',lambda:self._show_ledger('DUE — RESOLVE')),
               ('Review coverage (no model call)',self.review_coverage),
               ('Copy current report',self.copy_result),
               ('Export current report (Markdown or text)',self.export_result),
               ('Export calendar (.ics)',self._export_calendar),
               ('Cancel running analysis',self.cancel_job)]
        cmds+=[(f'Scope: {SCOPE_LABELS[name]}',lambda n=name:(self.scope.set(n),self._update_scope_note())) for name in SCOPES]
        return cmds

    @staticmethod
    def filter_commands(commands,query):
        """Every query word must appear in the label (case-insensitive), in any order."""
        words=query.casefold().split()
        return [c for c in commands if all(w in c[0].casefold() for w in words)]

    def open_palette(self,event=None):
        if self._palette is not None:
            try:self._palette.lift();return 'break'
            except tk.TclError:self._palette=None
        top=tk.Toplevel(self);self._palette=top
        top.title('OVERCAST — search');top.configure(bg=PANEL)
        top._ovc_surface='card'
        try:
            top.transient(self.winfo_toplevel())
            x=self.winfo_rootx()+max(40,(self.winfo_width()-560)//2);y=self.winfo_rooty()+90
            top.geometry(f'560x400+{x}+{y}')
        except (tk.TclError,TypeError):
            pass
        query=tk.StringVar(master=top)
        entry=ttk.Entry(top,textvariable=query,font=(self._font,14),style=self.theme.entry('card'))
        entry.pack(fill='x',padx=16,pady=(16,10))
        box=tk.Listbox(top,bg=PANEL,fg=INK,selectbackground=SELECT,selectforeground=INK,relief='flat',
                       font=(self._font,12),activestyle='none',highlightthickness=0,bd=0)
        box.pack(fill='both',expand=True,padx=12)
        tk.Label(top,text='↑ ↓ move   ·   ↵ run   ·   Esc close',font=(self._font,9),fg=FAINT,bg=PANEL).pack(pady=(6,10))
        commands=self._commands();shown=[]
        def refresh_list(*_):
            shown[:]=self.filter_commands(commands,query.get())
            box.delete(0,'end')
            for label,_fn in shown:box.insert('end','  '+label)
            if shown:box.selection_set(0)
        def run(*_):
            sel=box.curselection()
            if not sel or not shown:return 'break'
            fn=shown[sel[0]][1];close();fn();return 'break'
        def move(delta):
            sel=box.curselection();i=(sel[0] if sel else 0)+delta
            if shown:
                i=max(0,min(len(shown)-1,i));box.selection_clear(0,'end');box.selection_set(i);box.see(i)
            return 'break'
        def close(*_):
            try:top.destroy()
            except tk.TclError:pass
            self._palette=None;return 'break'
        query.trace_add('write',refresh_list)
        entry.bind('<Return>',run);box.bind('<Double-Button-1>',run);box.bind('<Return>',run)
        entry.bind('<Down>',lambda e:move(1));entry.bind('<Up>',lambda e:move(-1))
        for w in (entry,box,top):w.bind('<Escape>',close)
        top.protocol('WM_DELETE_WINDOW',close)
        refresh_list();entry.focus_set()
        return 'break'

    def install_shortcuts(self,window):
        """Opt-in keyboard shortcuts on a window this app owns (standalone). Hosts that
        embed OVERCAST keep their keys unless they call this themselves."""
        window.bind('<Control-k>',self.open_palette,add='+')
        window.bind('<Control-K>',self.open_palette,add='+')
        window.bind('<Control-Return>',lambda e:(self.generate_outlook(),'break')[1],add='+')
        window.bind('<F5>',lambda e:(self.refresh(),'break')[1],add='+')
        window.bind('<Escape>',lambda e:self.cancel_job() if self._running else None,add='+')
        for i,(tab,_name,_b) in enumerate(self._page_specs[:9],1):
            window.bind(f'<Control-Key-{i}>',lambda e,t=tab:(self._open_page(t),'break')[1],add='+')

    # ── TABLE SORTING ─────────────────────────────────────────────────────
    def _sort_tree(self,tree,column):
        reverse=not self._sort_state.get((str(tree),column),False)
        self._sort_state[(str(tree),column)]=reverse
        def key(value):
            text=str(value).replace('%','').replace('+','').replace('—','').strip()
            try:return (0,float(text))
            except ValueError:return (1,str(value).casefold())
        rows=[(key(tree.set(item,column)),item) for item in tree.get_children('')]
        rows.sort(reverse=reverse)
        for index,(_k,item) in enumerate(rows):tree.move(item,'',index)

    # ── RISK ACTIONS ──────────────────────────────────────────────────────
    def _mark_bad_news(self):
        selected=self.forecast_tree.selection()
        if len(selected)!=1:
            messagebox.showwarning(APP_NAME,'Select one forecast.',parent=self);return
        fid=int(selected[0]);x=self._forecasts.get(selected[0])
        answer=simpledialog.askstring('Which answer is bad news?',
            f"Forecast #{fid}: {x['question'] if x else ''}\n\nType YES if a YES outcome is the bad news, or NO if NO is.",parent=self)
        if answer is None:return
        answer=answer.strip().upper()
        if answer not in ('YES','NO'):
            messagebox.showwarning(APP_NAME,'Please type YES or NO.',parent=self);return
        severity=simpledialog.askinteger('How bad would it be?',
            'Severity if the bad news happens:\n1 negligible · 2 minor · 3 significant · 4 severe · 5 systemic',
            parent=self,minvalue=1,maxvalue=5,initialvalue=3)
        if severity is None:return
        try:self.engine.set_orientation(fid,answer=='YES',int(severity))
        except ValueError as exc:
            messagebox.showerror(APP_NAME,str(exc),parent=self);return
        self.reload_forecasts();self._select_tree(self.forecast_tree,fid)
        self.status.set(f'Forecast #{fid} marked: bad news if {answer}, severity {severity}. Added to the risk register.')

    def revise_selected_outlook(self):
        selected=self.outlook_tree.selection() if hasattr(self,'outlook_tree') else ()
        if selected:return self.revise_outlook_id(int(selected[0]))
        latest=self.engine.outlooks(1)
        if not latest:
            messagebox.showwarning(APP_NAME,'There is no broad outlook to revise yet. Run Broad outlook first.',parent=self);return
        return self.revise_outlook_id(latest[0]['id'])

    def revise_outlook_id(self,outlook_id):
        try:model=self._model_id()
        except ValueError as exc:
            messagebox.showwarning(APP_NAME,str(exc),parent=self);return
        runs=self._runs()
        def task(progress,cancel):
            e=self._new_worker_engine()
            try:return e.revise_outlook(outlook_id,model,runs=runs,progress=progress,cancel=cancel)
            finally:e.close()
        self._job('Revising broad outlook',task,staged=True)

    def _selected_ids_or_warn(self):
        try:return self._selected_ids()
        except ValueError as exc:
            messagebox.showwarning(APP_NAME,str(exc),parent=self);return None

    # ── AUTO-REFRESH (opt-in) ─────────────────────────────────────────────
    def _schedule_auto_refresh(self):
        if self._auto_after is not None:
            try:self.after_cancel(self._auto_after)
            except tk.TclError:pass
            self._auto_after=None
        try:hours=int(self.auto_refresh.get())
        except (TypeError,ValueError):hours=0
        if hours>0 and not self._closed:
            self._auto_after=self.after(hours*3600*1000,self._auto_refresh_tick)

    def _auto_refresh_tick(self):
        self._auto_after=None
        if self._closed:return
        if not self._running:self.refresh()
        self._schedule_auto_refresh()

    def _pane(self,parent,orient='horizontal'):
        """Resizable split view with an invisible, generous sash."""
        pane=tk.PanedWindow(parent,orient=orient,bg=BG,bd=0,sashwidth=12,sashrelief='flat',
                            showhandle=False,opaqueresize=True)
        pane._ovc_surface='bg'
        pane.pack(fill='both',expand=True)
        if orient=='horizontal':     # side-by-side views stack when the column is narrow (_reflow)
            entry=(pane,[])
            if not hasattr(self,'_split_panes'):self._split_panes=[]
            self._split_panes.append(entry)
            original=pane.add
            def add(child,**kw):
                entry[1].append((child,kw.get('minsize',0)))
                return original(child,**kw)
            pane.add=add
            def settle(event):
                # Stacked, the main view gets two-thirds of the height (the details box, a third).
                if pane.cget('orient')!='vertical' or event.height<=1 or len(entry[1])<2:return
                if getattr(pane,'_settled_for',None)==event.height:return
                pane._settled_for=event.height
                try:pane.sash_place(0,0,int(event.height*0.66))
                except tk.TclError:pass
            pane.bind('<Configure>',settle,add='+')
        return pane

    def _tree(self,parent,cols,headings,widths):
        wrap=self._surface(parent,'card',padding=(8,6,4,8))
        tree=ttk.Treeview(wrap,columns=cols,show='headings',selectmode='extended',style='O.Treeview')
        scroll=ttk.Scrollbar(wrap,orient='vertical',command=tree.yview,style='O.Vertical.TScrollbar')
        tree.configure(yscrollcommand=scroll.set)
        for name,head,width in zip(cols,headings,widths):
            tree.heading(name,text=head,anchor='w',command=lambda c=name,t=tree:self._sort_tree(t,c))
            tree.column(name,width=width,anchor='w',minwidth=40,stretch=(name==cols[-1]))
        tree.tag_configure('due',foreground=RED)
        tree.tag_configure('muted',foreground=DIM)
        tree.pack(side='left',fill='both',expand=True)
        scroll.pack(side='right',fill='y',padx=(4,0))
        return wrap,tree

    def _text_area(self,parent,reader=False):
        """Rounded card holding a read-only rich text view. reader=True uses a roomier measure."""
        frame=self._surface(parent,'card',padding=(6,6,4,6))
        pad=(26,20) if reader else (16,12)
        text=tk.Text(frame,wrap='word',relief='flat',bg=PANEL,fg=INK,insertbackground=INK,
                     padx=pad[0],pady=pad[1],font=(self._font,12 if reader else 11),borderwidth=0,highlightthickness=0,
                     spacing1=3,spacing2=2,spacing3=4,selectbackground=SELECT,selectforeground=INK,
                     inactiveselectbackground=SELECT)
        scroll=ttk.Scrollbar(frame,orient='vertical',command=text.yview,style='O.Vertical.TScrollbar')
        text.config(yscrollcommand=scroll.set)
        text.pack(side='left',fill='both',expand=True)
        scroll.pack(side='right',fill='y',padx=(4,0))
        text.tag_configure('head',foreground=INK,font=(self._font,15 if reader else 13,'bold'),spacing1=10,spacing3=6)
        text.tag_configure('muted',foreground=DIM)
        text.tag_configure('adverse',foreground=RED)
        text.tag_configure('good',foreground=GREEN)
        text.tag_configure('big',font=self.theme.fonts['big'],foreground=INK)
        text.tag_configure('link',foreground=GOLD,underline=True)
        text.config(state='disabled')
        return frame,text

    @staticmethod
    def _set_text(text,spans):
        text.config(state='normal')
        text.delete('1.0','end')
        for content,tag in spans:
            text.insert('end',content,tag)
        text.config(state='disabled')

    def _news_tab(self):
        row=self._toolbar(self.news_tab)
        search=self._entry(row,self.search_var,width=20)
        search.pack(side='left',padx=(0,10))
        search.bind('<Return>',lambda e:self.reload_articles())
        Tooltip(search,'Search headlines and excerpts; press Enter.')
        self._chips(row,self.focus,(('FOCUS TOPICS','Focus'),('WORLD POLITICS','Politics'),('MARKETS','Markets'),
                                    ('TRADE','Trade'),('CRISES','Crises'),('ALL','All')),
                    command=self.reload_articles).pack(side='left')
        self._btn(row,'Open source ↗',self.open_article,kind='plain').pack(side='right')
        opt=self._toolbar(self.news_tab)
        self._btn(opt,'Deep forecast selected',lambda:self._multi_from_ids(self._selected_ids_or_warn()),accent=True).pack(side='left',padx=(0,8))
        self._btn(opt,'Briefing',self.briefing).pack(side='left',padx=(0,8))
        self._btn(opt,'Examine sources',self.preview).pack(side='left')
        self._label(opt,'Ctrl- or Shift-click to select several stories.',color=FAINT,size=9).pack(side='right')
        pane=self._pane(self.news_tab)
        left,self.article_tree=self._tree(pane,('published','source','headline'),
                                         ('Published (UTC)','Source','Headline'),(120,130,340))
        pane.add(left,minsize=265,stretch='always')
        right,self.news_text=self._text_area(pane)
        pane.add(right,minsize=205,stretch='always')
        self.article_tree.bind('<<TreeviewSelect>>',lambda e:self._show_article())
        self._set_text(self.news_text,[('News\n','head'),
           ('Refresh feeds, then select stories to analyse. For broad coverage, pick a scope in the command bar instead.\n','')])

    def _events_tab(self):
        row=self._toolbar(self.events_tab)
        self._btn(row,'Refresh',self.reload_events,kind='plain').pack(side='left')
        self._label(row,'Groups are topic matches, not verified facts.',color=FAINT,size=9).pack(side='left',padx=12)
        self._btn(row,'Deep forecast this event',self.forecast_event,accent=True).pack(side='right')
        pane=self._pane(self.events_tab)
        left,self.event_tree=self._tree(pane,('pubs','items','newest','event'),
                  ('Sources','Stories','Newest (UTC)','Event candidate'),(80,80,140,600))
        pane.add(left,minsize=420,stretch='always')
        right,self.event_text=self._text_area(pane)
        pane.add(right,minsize=300,stretch='always')
        self.event_tree.bind('<<TreeviewSelect>>',lambda e:self._show_event())

    def _claims_tab(self):
        toolbar=self._toolbar(self.claims_tab)
        self._btn(toolbar,'Refresh',self.reload_claims,kind='plain').pack(side='left')
        self._label(toolbar,'Claims quote their source exactly but are not verified facts.',color=FAINT,size=9).pack(side='left',padx=12)
        self._btn(toolbar,'Extract from selected news',self.extract_claims,accent=True).pack(side='right',padx=(8,0))
        self._btn(toolbar,'Relationship leads',self.show_relationships).pack(side='right')
        pane=self._pane(self.claims_tab)
        left,self.claim_tree=self._tree(pane,('id','date','actor','kind','action'),
             ('#','Event date','Actor','Report type','Reported action'),(46,95,180,150,360))
        pane.add(left,minsize=490,stretch='always')
        right,self.claim_text=self._text_area(pane)
        pane.add(right,minsize=300,stretch='always')
        self.claim_tree.bind('<<TreeviewSelect>>',lambda e:self._show_claim())

    def reload_claims(self):
        rows=self.engine.event_claims()
        self._claims={str(c['id']):c for c in rows}
        self.claim_tree.delete(*self.claim_tree.get_children())
        for c in rows:
            self.claim_tree.insert('','end',iid=str(c['id']),values=(
                c['id'],c['event_date'] or 'unknown',c['actor'],c['kind'],c['action']))
        if rows:self._select_tree(self.claim_tree,rows[0]['id'])
        else:self._set_text(self.claim_text,[('No claims yet\n','head'),
                 ('Select stories on the News page, then choose Extract from selected news. '
                  'Only claims that quote the cached excerpt exactly are kept.\n','')])

    def _show_claim(self):
        selected=self.claim_tree.selection()
        if not selected:return
        c=self._claims.get(selected[0])
        if not c:return
        self._set_text(self.claim_text,[(c['claim_text']+'\n','head'),
            (f"STATUS: {c['status']}\nACTOR: {c['actor']}\nACTION: {c['action']}\n"
             f"TARGET: {c['target'] or 'unavailable'}\nLOCATION: {c['location'] or 'unavailable'}\n"
             f"EVENT DATE: {c['event_date'] or 'not established'}\n\n",'muted'),
            ('Exact excerpt\n','head'),(c['evidence_quote']+'\n\n',''),
            ('Provenance\n','head'),
            (f"Article #{c['source_article_id']} | {c['publisher']}\n"
             f"Publication: {c['article_published'] or 'unknown'}\n"
             f"First seen: {c['article_first_seen']}\n"
             f"Source: {c['source_url']}\nModel: {c['model_id']}\n\n",''),
            ('Caution\n','head'),
            ('The exact quote is verified against the saved RSS excerpt, but the underlying statement '
             'has not been independently fact-checked. Co-occurring names do not prove coordination.\n','muted')])

    def extract_claims(self):
        try:ids=self._selected_ids();model=self._model_id()
        except ValueError as exc:messagebox.showwarning(APP_NAME,str(exc),parent=self);return
        if not messagebox.askyesno('Extract event claims',
               f'Ask local model {model} to extract sourced claims from {len(ids)} cached headline(s)?\n'
               'Each claim must carry a verbatim quote and a source article ID.\n'
               'No claim will be treated as verified fact.',parent=self):return
        def task():
            e=self._new_worker_engine()
            try:return e.extract_events(ids,model)
            finally:e.close()
        self._job('Extracting event claims',task)

    def show_relationships(self):
        leads=self.engine.relationship_leads()
        content=('No shared-actor links found. These are research leads, never causal proof.\n' if not leads
                 else '\n\n'.join(
                    f"Claims #{x['from_claim']} and #{x['to_claim']} share named-actor terms: "
                    f"{', '.join(x['shared_actor_terms'])}.\n"
                    'UNVERIFIED association. Check source documents and alternative explanations.'
                    for x in leads))
        self._set_text(self.claim_text,[('Possible relationships — unverified\n','head'),(content,'')])

    def reload_events(self):
        groups=self.engine.events(focus_only=True)
        self._events={str(x['event_id']):x for x in groups}
        self.event_tree.delete(*self.event_tree.get_children())
        for g in groups:
            self.event_tree.insert('','end',iid=str(g['event_id']),
                values=(g['publisher_count'],g['articles'],friendly_date(g['newest']),g['title']))
        if groups:self._select_tree(self.event_tree,groups[0]['event_id'])
        else:self._set_text(self.event_text,[('No clusters yet\n','head'),
                ('Refresh news, then browse algorithmically related headlines here.\n','')])

    def _show_event(self):
        selected=self.event_tree.selection()
        if not selected:return
        event=self._events.get(selected[0])
        if not event:return
        rows=self.engine.store.article_ids(event['article_ids'][:30])
        lines='\n\n'.join(f"[{a['id']}] {a['source']} | {a['title']}\n{a['url']}" for a in rows)
        self._set_text(self.event_text,[(event['title']+'\n','head'),
            (f"{event['articles']} reports  •  {event['publisher_count']} publisher domains\n\n",'muted'),
            ('Matched stories\n','head'),(lines+'\n\n',''),
            ('Caution\n','head'),('Same topic is not independently verified. Headlines may be syndicated; ' 
              'inspect the URLs and original sources before concluding claims are corroborated.\n','muted')])

    def forecast_event(self):
        selection=self.event_tree.selection()
        if not selection:return
        event=self._events.get(selection[0])
        if event:self._multi_from_ids(event['article_ids'][:30])

    def preview(self):
        try:
            research=self.engine.research_preview(self._selected_ids())
        except ValueError as exc:
            messagebox.showwarning(APP_NAME,str(exc),parent=self);return
        report=(f"{len(research['article_ids'])} cached reports from {research['publisher_count']} publisher domains "
                f"({research['expanded']} auto-expanded).\n\n"+
                '\n\n'.join(f"[{a['id']}] {a['publisher']} ({a['domain']}) | {a['published_utc']}\n"
                f"{a['title']}\n{a['rss_excerpt'] or '[No excerpt]'}\n{a['url']}"
                for a in research['articles'])+
                '\n\nCROSS-SECTOR RESEARCH LEADS (NOT CAUSAL PROOF):\n'+
                ('\n'.join(f"Article {x['article_id']} shared {x['shared_terms']}; additional sector {x['new_focus']}" for x in research.get('cross_sector_bridges', [])) or 'None found')+
                '\n\nWARNINGS:\n'+'\n'.join(research['cautions']))
        self._render_result('Source review', [('Source review / no model call\n','head'),(report,'')],show=True)
        self.status.set('Research preview is read-only. Review source links; multi-source analysis will use these cached items.')

    def multi_forecast(self):
        try:ids,coverage=self._coverage()
        except ValueError as exc:messagebox.showwarning(APP_NAME,str(exc),parent=self);return
        self._multi_from_ids(ids,coverage=coverage)

    def _multi_from_ids(self,ids,coverage=None):
        if not ids:return
        try:
            model=self._model_id();days=int(self.horizon.get())
            preview=self.engine.research_preview(ids)
            models=[model]+[name.strip() for name in self.extra_models.get().split(',') if name.strip()]
            if len(models)>3 or len(set(models))!=len(models):
                raise ValueError('Provide 1 to 3 DISTINCT loaded model IDs (main selector + up to two others).')
        except ValueError as exc:
            messagebox.showwarning(APP_NAME,str(exc),parent=self);return
        gap_enabled=bool(self.use_gaps.get())
        timing_enabled=bool(self.use_timing.get())
        runs=self._runs()
        if not messagebox.askyesno('Multi-source forecast',
              f"Coverage: {(coverage or {}).get('scope','SELECTED EVENT')}\n\n"
              f"Send {len(preview['article_ids'])} cached RSS excerpts from "
              f"{preview['publisher_count']} publisher domains to LOCAL LM Studio?\n\n"
              f'This makes {2+max(3,runs)+int(gap_enabled)+int(timing_enabled)} sequential local model calls '
              f'sized for a {self.context.get()} context. '
              'Risk analysis, multiple perspectives, and optional gap/timing passes. '
              'No cloud model is contacted. CANCEL stops after the current call; nothing is saved.\n\n'
              +('WARNING: Only one publisher is represented.\n' if preview['publisher_count']<2 else '')
              +'News content is not independently fact-checked.',parent=self):return
        def task(progress,cancel):
            e=self._new_worker_engine()
            try:return e.forecast_multi(ids,model,days,model_ids=models,investigate=True,
                        gap_search=gap_enabled,timing=timing_enabled,
                        scope_label=(coverage or {}).get('scope','SELECTED EVENT'),
                        progress=progress,cancel=cancel,runs=runs)
            finally:e.close()
        self._job('Multi-source forecast',task,staged=True)

    def _forecast_tab(self):
        row=self._toolbar(self.forecast_tab)
        show=self._chips(row,self.ledger_filter,(('ALL','All'),('OPEN','Open'),('DUE — RESOLVE','Due'),
                                                  ('RESOLVED','Resolved'),('TOP RISKS','Top risks'),('SIGNPOSTS','Signposts')),
                         command=self.reload_forecasts)
        show.pack(side='left')
        Tooltip(show,'Top risks lists open forecasts whose bad-news direction is known, ranked by chance × severity.')
        find=self._entry(row,self.ledger_search,width=22)
        find.pack(side='right')
        find.bind('<Return>',lambda e:self.reload_forecasts())
        Tooltip(find,'Search questions; press Enter.')
        actions=self._toolbar(self.forecast_tab)
        self._btn(actions,'Resolved: yes',lambda:self._resolve(1)).pack(side='left',padx=(0,8))
        self._btn(actions,'Resolved: no',lambda:self._resolve(0)).pack(side='left',padx=(0,8))
        mark=self._btn(actions,'Mark bad news…',self._mark_bad_news)
        mark.pack(side='left',padx=(0,8))
        Tooltip(mark,'Say which answer is the bad news and how severe it would be. Adds the forecast to the '
                     'risk register and the gloom-bias check. Outlook signposts are marked automatically.')
        self._btn(actions,'Frozen evidence',self.show_forecast_packet,kind='plain').pack(side='right')
        pane=self._pane(self.forecast_tab,'vertical')
        left,self.forecast_tree=self._tree(pane,('id','p','risk','deadline','outcome','question'),
                                          ('#','P(yes)','Risk','Resolves by','Status','Question'),(46,64,56,100,100,640))
        pane.add(left,minsize=160,stretch='always')
        right,self.forecast_text=self._text_area(pane)
        pane.add(right,minsize=190,stretch='always')
        self.forecast_tree.bind('<<TreeviewSelect>>',lambda e:self._show_forecast())

    def _calendar_tab(self):
        toolbar=self._toolbar(self.calendar_tab)
        self._btn(toolbar,'‹',lambda:self._move_month(-1),kind='plain').pack(side='left')
        self.cal_heading=self._label(toolbar,'',size=17,bold=True)
        self.cal_heading.pack(side='left',padx=6)
        self._btn(toolbar,'›',lambda:self._move_month(1),kind='plain').pack(side='left')
        self._btn(toolbar,'Today',self._calendar_today).pack(side='left',padx=(10,0))
        self._btn(toolbar,'Export .ics',self._export_calendar).pack(side='right',padx=(8,0))
        self._btn(toolbar,'Add sourced date…',self._add_schedule).pack(side='right',padx=(8,0))
        self._btn(toolbar,'Refresh',self.reload_calendar,kind='plain').pack(side='right')
        legend=self._toolbar(self.calendar_tab)
        for colour,label in ((RED,'resolution deadline'),(GOLD,'estimated window'),(DIM,'timing bucket'),(GREEN,'sourced schedule')):
            tk.Label(legend,text='●',fg=colour,bg=BG,font=(self._font,9)).pack(side='left',padx=(0,4))
            self._label(legend,label,color=DIM,size=9).pack(side='left',padx=(0,16))
        pane=self._pane(self.calendar_tab)
        holder=self._surface(pane,'card',padding=10)
        pane.add(holder,minsize=455,stretch='always')
        left=tk.Frame(holder,bg=PANEL);left._ovc_surface='card';left.pack(fill='both',expand=True)
        for col,name in enumerate(('Mon','Tue','Wed','Thu','Fri','Sat','Sun')):
            tk.Label(left,text=name,fg=DIM,bg=PANEL,font=(self._font,9,'bold')).grid(
                row=0,column=col,sticky='ew',pady=(2,6))
            left.grid_columnconfigure(col,weight=1,uniform='day')
        self.cal_buttons=[]
        for row in range(1,7):
            left.grid_rowconfigure(row,weight=1)
            for col in range(7):
                button=tk.Button(left,justify='left',anchor='nw',bg=PANEL,fg=INK,
                    activebackground=HOVER,activeforeground=INK,relief='flat',bd=0,cursor='hand2',
                    highlightthickness=0,wraplength=90,font=(self._font,9),padx=6,pady=5)
                button.grid(row=row,column=col,sticky='nsew',padx=1,pady=1)
                self.cal_buttons.append(button)
        right,self.cal_text=self._text_area(pane)
        pane.add(right,minsize=240,stretch='always')

    def _move_month(self,delta):
        d=self._calendar_month
        year,month=divmod(d.year*12+d.month-1+delta,12)
        self._calendar_month=date(year,month+1,1)
        self._draw_calendar()

    def _calendar_today(self):
        self._calendar_day=date.today()
        self._calendar_month=self._calendar_day.replace(day=1)
        self._draw_calendar()

    def reload_calendar(self):
        self._calendar_items=self.engine.calendar_items()
        self._draw_calendar()

    def _draw_calendar(self):
        self.cal_heading.config(text=self._calendar_month.strftime('%B %Y'))
        weeks=std_calendar.Calendar(firstweekday=0).monthdatescalendar(
            self._calendar_month.year,self._calendar_month.month)
        while len(weeks)<6:
            weeks.append([weeks[-1][-1]+timedelta(days=n) for n in range(1,8)])
        today=date.today()
        for index,button in enumerate(self.cal_buttons):
            day=weeks[index//7][index%7]
            items=on_day(self._calendar_items,day)
            counts={kind:sum(x['kind']==kind for x in items) for kind in
                    ('forecast_deadline','forecast_window','forecast_timing_bucket','reported_schedule')}
            marks=[f'● {n} {label}' for kind,label in (('forecast_deadline','due'),('forecast_window','window'),
                   ('reported_schedule','sched.'),('forecast_timing_bucket','timing')) if (n:=counts[kind])]
            current=day.month==self._calendar_month.month
            selected=day==self._calendar_day
            bg=SELECT if selected else PANEL
            fg=(GOLD if day==today else INK) if current else FAINT
            if counts['forecast_deadline'] and current and not selected:fg=RED if day!=today else GOLD
            button.configure(text=str(day.day)+('  ·  today' if day==today else '')+'\n'+'\n'.join(marks[:3]),
                      fg=fg,bg=bg,activebackground=SELECT if selected else HOVER,
                      font=(self._font,9,'bold' if day==today else 'normal'),command=lambda d=day:self._pick_day(d))
        self._show_calendar_day()

    def _pick_day(self,day):
        self._calendar_day=day
        if day.month!=self._calendar_month.month:
            self._calendar_month=day.replace(day=1)
        self._draw_calendar()

    def _show_calendar_day(self):
        day=self._calendar_day
        items=on_day(self._calendar_items,day)
        spans=[(day.strftime('%A %d %B %Y')+'\n','head')]
        if not items:
            spans.append(('No forecast timing, deadline or recorded scheduled event for this day.\n','muted'))
        for entry in items:
            spans.extend([('\n'+TYPES[entry['kind']]+'\n','head'),
              (entry['title']+'\n',''),
              (f"Period: {entry['start_date']} → {entry['end_date']}\n",'muted')])
            if entry.get('probability') is not None:
                spans.append((f"P(YES) by resolution deadline: {entry['probability']:.0%} — NOT probability of occurrence on this day.\n",'muted'))
            if entry.get('bucket_probability') is not None:
                spans.append((f"Model estimate of event occurring during ENTIRE interval: {entry['bucket_probability']:.1%}. Not calibrated.\n",'muted'))
            spans.append(('Basis: '+(entry.get('timing_basis') or 'unspecified')+'\n',''))
            if entry.get('source_url'):
                spans.append(('Source: '+entry['source_url']+'\n',''))
            if entry.get('notes'):
                spans.append((entry['notes']+'\n','muted'))
        self._set_text(self.cal_text,spans)

    def _add_schedule(self):
        title=simpledialog.askstring('Record reported date','Event name (use exact sourced wording):',parent=self)
        if title is None:return
        start=simpledialog.askstring('Start date','YYYY-MM-DD start:',parent=self)
        if start is None:return
        end=simpledialog.askstring('End date','YYYY-MM-DD end (same date for one day):',
                                   initialvalue=start,parent=self)
        if end is None:return
        url=simpledialog.askstring('Public source','HTTPS link to the published event schedule:',parent=self)
        if url is None:return
        note=simpledialog.askstring('Provenance note','Optional note on publisher and source:',parent=self)
        if note is None:return
        try:
            identifier=self.engine.add_scheduled_event(title,start,end,url.strip(),note)
            self._calendar_day=date.fromisoformat(start)
            self._calendar_month=self._calendar_day.replace(day=1)
            self.reload_calendar()
            self.status.set(f'Reported schedule #{identifier} recorded with supplied source; date not independently verified.')
            self._emit('scheduled_date_added',id=identifier)
        except ValueError as exc:
            messagebox.showerror('Invalid calendar entry',str(exc),parent=self)

    def _export_calendar(self):
        path=filedialog.asksaveasfilename(parent=self,title='Export forecast calendar',
                defaultextension='.ics',filetypes=[('iCalendar','*.ics')],
                initialfile='OVERCAST_Forecast_Calendar.ics')
        if not path:return
        try:
            Path(path).write_text(self.engine.calendar_ics(),encoding='utf-8',newline='')
            self.status.set('Forecast calendar exported to '+path)
        except OSError as exc:
            messagebox.showerror(APP_NAME,str(exc),parent=self)

    def _brief_tab(self):
        pane=self._pane(self.brief_tab,'vertical')
        left,self.brief_tree=self._tree(pane,('id','date','title'),
                                       ('#','Created','Briefing'),(46,150,900))
        pane.add(left,minsize=150)
        right,self.brief_text=self._text_area(pane)
        pane.add(right,minsize=190)
        self.brief_tree.bind('<<TreeviewSelect>>',lambda e:self._show_briefing())

    def _info_tab(self):
        top=self._toolbar(self.info_tab)
        self.score=tk.StringVar(master=self)
        self._label(top,'Score',color=DIM,size=10,bold=True).pack(side='left')
        tk.Label(top,textvariable=self.score,bg=BG,fg=INK,font=(self._font,10),anchor='w').pack(side='left',padx=10)
        frame,self.info_text=self._text_area(self.info_tab,reader=True)
        frame.pack(fill='both',expand=True)
        sections=[
            ('The idea','OVERCAST is deliberately pessimistic about what it EXAMINES and deliberately neutral about what it '
             'PREDICTS. Every outlook must include adverse and tail-risk scenarios, a pre-mortem ("assume it went wrong: how?") '
             'and early-warning signposts, and risks are ranked by chance × severity. But the pessimistic lens never inflates '
             'a probability, and the GLOOM BIAS check on the dashboard tells you if forecasts have been too gloomy (or not gloomy '
             'enough) compared with what actually happened.'),
            ('Broad outlooks','A broad question ("where are trade tensions heading?") cannot be scored directly, so it is split '
             'into drivers and specific signpost questions that resolve from public records (the question-cluster method used by '
             'Good Judgment, RAND\'s Forecasting Initiative and Metaculus Indexes). RUNS independent model runs, each seeing the '
             'evidence in a different order, forecast every signpost and 3–4 mutually exclusive scenarios. Code, not the model, '
             'combines them (median, or trimmed mean for 4+ runs) into scenario probabilities, the chance of a bad outcome and a '
             '−100…+100 gloom index. Runs whose scenarios do not add up to 100% are rejected. REVISE re-forecasts the same '
             'outlook on fresh news; resolving a signpost resolves its copies in every revision.'),
            ('Accuracy','Methods follow published evidence on AI forecasting: averaging independent runs, numeric (not '
             'model-written) aggregation, checking similar past questions, decomposition, coherence checks, and calibration '
             'learned only from your own resolved forecasts (40+, shown only when it beats raw forecasts on held-out data). '
             'Accuracy is measured, never claimed: resolve every forecast as it falls due (YES or NO), or the score is flattered. '
             'Brier score: average of (probability − outcome)², 0 is perfect, 0.25 is a coin flip. Log loss: coin flip 0.693.'),
            ('Evidence and privacy',f'Headlines come from public RSS feeds, fetched only when you refresh (or on an auto-refresh '
             f'schedule you switch on). Only cached excerpts are sent to your own LM Studio server ({DEFAULT_URL}); nothing '
             'goes to a cloud model. The model does not browse, and cannot tell whether a claim is true. Different publishers '
             'are not proof of independent confirmation. Incentives, motives and cross-event links are hypotheses, not findings.'),
            ('The ledger','Every forecast is permanent: original probability, model, frozen evidence (SHA-256 checked), '
             'resolution rule and deadline. Resolving requires a public evidence URL. Mark bad news records which answer is '
             'the adverse one and how severe it would be, adding the forecast to the risk register and the gloom-bias check.'),
            ('Model settings','CONTEXT (8K/16K/32K) must match the context length loaded in LM Studio; excerpts are shortened '
             'to fit and the length is recorded. Each model call may take up to 10 minutes on slow hardware; CANCEL stops '
             'before the next call and saves nothing incomplete. A Vulkan "device lost" error is an LM Studio/GPU problem: '
             'restart LM Studio and load the model at 8K with less GPU offload.'),
            ('Deep forecasts','One precise yes/no question from selected headlines, then outside-view, inside-view and red-team '
             'passes (more with RUNS > 3), optional counter-evidence search, incentive investigation and timing windows. Lenses '
             'from one model are correlated, not independent experts.'),
            ('Calendar','Resolution deadlines, model-estimated windows and timing buckets are shown separately from schedules '
             'you record with a source URL. An estimated window is never presented as a confirmed date.'),
            ('Data',f'Stored in {self.engine.store.state_dir}. The folder name is unchanged from earlier versions so upgrades '
             'keep every forecast. Back it up with the app closed.'),
            ('Marble Oracle','Mount overcast.create_panel(parent) in a workspace (the old news_oracle import still works). '
             'The panel never takes over host keyboard shortcuts unless install_shortcuts() is called.')]
        spans=[]
        for head,body in sections:spans+=[(head+'\n','head'),(body+'\n\n','')]
        self._set_text(self.info_text,spans)

    def _job(self,action,func,*,staged=False):
        """Run func on a worker thread. Tk is touched only from _poll_jobs.

        staged=True passes (progress, cancel) so long pipelines can report each
        local model call and stop cooperatively between calls.
        """
        if self._running:
            self.status.set('Another operation is running.');return
        self._running=True
        self._running_action=action
        cancel=threading.Event()
        self._cancel_event=cancel
        if staged:
            self.cancel_button.configure(state='normal')
        self.status.set(action+'…')
        if action in ANALYSIS_ACTIONS:
            self._render_running(action,'Starting')
        def progress(step,total,label):
            self._jobs.put(('__progress__',True,(action,step,total,label),None))
        def run():
            try:
                value=func(progress,cancel) if staged else func()
                self._jobs.put((action,True,value,None))
            except OperationCancelled as exc:
                self._jobs.put((action,False,str(exc),'cancelled'))
            except Exception as exc:
                self._jobs.put((action,False,str(exc),'error'))
        threading.Thread(target=run,daemon=True,name='overcast-'+action.lower().replace(' ','-')).start()

    def _render_running(self,action,stage_text):
        self._render_result('Running',[
            ('Local analysis in progress\n','head'),
            (action+' is running against the selected loaded LM Studio model.\n\n',''),
            ('CURRENT STAGE: '+stage_text+'\n\n',''),
            ('The completed report will replace this message automatically. '
             'Each local model call can take several minutes on CPU or small GPUs.\n',''),
            ('Your news and existing saved forecasts remain accessible during analysis. '
             'CANCEL (where enabled) stops after the current model call; nothing incomplete is saved.\n','muted')],show=True)

    def cancel_job(self):
        if self._running and self._cancel_event is not None and not self._cancel_event.is_set():
            self._cancel_event.set()
            self.cancel_button.configure(state='disabled')
            self.status.set(self._running_action+': cancelling after the current local model call finishes…')

    def _load_settings(self):
        try:
            data=json.loads(self._settings_path.read_text(encoding='utf-8'))
            return data if isinstance(data,dict) else {}
        except (OSError,ValueError):
            return {}

    def _save_settings(self):
        """UI preferences only (context profile, last model). Never forecasts or evidence."""
        try:hours=int(self.auto_refresh.get())
        except (TypeError,ValueError):hours=0
        data={'context_profile':self.context.get(),'model_id':self.model.get().strip()[:200],
              'runs':self._runs(),'auto_refresh_hours':hours if hours in (0,3,6,12) else 0,
              'use_gaps':bool(self.use_gaps.get()),'use_timing':bool(self.use_timing.get()),
              'extra_models':self.extra_models.get().strip()[:300],
              'appearance':self.appearance.get() if hasattr(self,'appearance') else self.theme.appearance,
              'accent':self.accent.get() if hasattr(self,'accent') else self.theme.accent}
        try:
            tmp=self._settings_path.with_suffix('.tmp')
            tmp.write_text(json.dumps(data),encoding='utf-8')
            tmp.replace(self._settings_path)
        except OSError:
            pass

    def _runs(self):
        try:
            value=int(self.runs.get())
        except (TypeError,ValueError):
            return 3
        return value if 1<=value<=5 else 3

    def _apply_context(self):
        profile=self.context.get()
        if profile in CONTEXT_PROFILES:
            self.engine.context_profile=profile
            self.engine.budget=CONTEXT_PROFILES[profile]
            self._save_settings()
            self._update_chips()
            self.status.set(f'Model context set to {profile}. Match the context length loaded in LM Studio; '
                            'evidence excerpts are shortened to fit.')

    def _poll_jobs(self):
        if self._closed:return
        try:
            while True:
                try:item=self._jobs.get_nowait()
                except Empty:break
                try:self._handle_job(*item)
                except Exception as exc:  # never let one bad result stop all future polling
                    self.status.set('Could not display result: '+str(exc)[:200])
        finally:
            if not self._closed:
                self._poll_after=self.after(140,self._poll_jobs)

    def _handle_job(self,action,ok,value,kind=None):
        if action=='__progress__':
            name,step,total,label=value
            text=f'step {step} of {total}: {label}'
            self.status.set(f'{name} — {text}…')
            if self._result_kind=='Running':
                self._render_running(name,text)
            return
        self._running=False
        self._cancel_event=None
        self.cancel_button.configure(state='disabled')
        if not ok:
            if action=='Connecting to LM Studio':
                self._connected=False;self._update_chips()
            if kind=='cancelled':
                self._render_result('Cancelled',[('Analysis cancelled\n','head'),
                    (str(value)+'\n\n',''),
                    ('The prediction ledger and briefing archive are unchanged.\n','muted')],show=True)
                self.status.set(action+' cancelled. Nothing was saved.')
                return
            gpu_lost='VULKAN GPU DEVICE LOST' in str(value)
            if action in ANALYSIS_ACTIONS:
                self._render_result('Error',[
                    ('Analysis could not complete\n','head'),
                    (str(value)+'\n\n',''),
                    (('A Vulkan device-loss error needs recovery in LM Studio first. Avoid repeating heavy analysis until a short LM Studio chat works.\n' if gpu_lost else 'No incomplete forecast was added to the ledger. Check the loaded model, LM Studio server, MODEL CONTEXT setting and source selection.\n'),'muted')],show=True)
            self.status.set((action+' failed: LM Studio lost the GPU (Vulkan); see Results for recovery steps.')
                            if gpu_lost else (action+' failed: '+str(value)[:250]))
            messagebox.showerror(APP_NAME+' — '+action,
                ('LM Studio lost the Vulkan GPU during inference. Restart LM Studio, lower GPU offload and context length, then test a short chat. See Results for details.'
                 if gpu_lost else str(value)[:1500]),parent=self)
            return
        if action=='Fetching headlines':
            if isinstance(value,dict) and isinstance(value.get('sources'),list):
                self._last_refresh=value
            self.reload_articles()
            self.reload_events()
            self._update_scope_note()
            errors=[x for x in value['sources'] if x['error']]
            stale=[x for x in value['sources'] if x['stale']]
            self.status.set(f"News updated: {value['new']} new of {value['total_fetched']} fetched; {len(errors)} source errors, {len(stale)} stale feeds (>3d).")
            self._emit('news_refreshed',new=value['new'],source_errors=len(errors))
            self.reload_dashboard()
        elif action=='Connecting to LM Studio':
            chat=[m for m in value if is_chat_model(m)]
            skipped=len(value)-len(chat)
            self.model_choice['values']=value
            if chat and self.model.get() not in chat:self.model.set(chat[0])
            self._save_settings()
            self._connected=bool(chat)
            self._update_chips()
            note=f' ({skipped} embedding model(s) not selectable for reports)' if skipped else ''
            self.status.set((f"LM Studio reachable. {len(chat)} chat model(s) listed{note}. "
                             f"Set CONTEXT to the model's loaded context length.") if chat
                            else 'LM Studio reachable but no chat model is loaded.'+note)
            self._emit('model_connected',models=len(chat))
        elif action=='Extracting event claims':
            self.reload_claims()
            self.tabs.select(self.claims_tab)
            self.status.set(f"Extracted {value['validated_claims']} validated-excerpt claims; "
                            f"{value['new_claims']} new entries. No facts verified.")
            self._emit('claims_extracted',count=value['new_claims'])
        elif action in ('Making briefing','Building overview'):
            self.reload_briefings()
            self._open_page(self.results_tab)
            self._select_tree(self.brief_tree,value['id'])
            self.status.set(f"Report #{value['id']} displayed and saved locally.")
            self._emit('briefing_created',id=value['id'])
        elif action in ('Building broad outlook','Revising broad outlook'):
            self.reload_forecasts()
            self.reload_calendar()
            self.reload_outlooks()
            self._select_tree(self.outlook_tree,value['id'])
            self._show_outlook(value['id'])
            self._open_page(self.results_tab)
            self.status.set(f"Broad outlook #{value['id']}{' (revision of #'+str(value['revision_of'])+')' if value.get('revision_of') else ''} saved: gloom index {value['stress_index']:+.0f}, "
                            f"{value['signposts']} signposts added to the ledger, {value['valid_runs']} valid runs. Not calibrated.")
            self._emit('outlook_created',id=value['id'],stress_index=value['stress_index'])
        elif action in ('Generating forecast','Multi-source forecast'):
            self.reload_forecasts()
            self.reload_calendar()
            self._open_page(self.results_tab)
            self._select_tree(self.forecast_tree,value['id'])
            caveat=' Only one publisher domain in evidence.' if value['independent_sources']<2 else ''
            if action=='Multi-source forecast':caveat+=f" Median of {value['valid_passes']} correlated model passes (spread {value['spread_percent']:.0f} points); not calibrated."
            self.status.set(f"Forecast #{value['id']} locked at {value['probability']:.0%} through {value['target_date']}.{caveat}")
            self._emit('forecast_created',id=value['id'],probability=value['probability'])

    def _emit(self,event,**data):
        if self.on_event:
            # 'module' stays 'signal' for EVENT_SCHEMA_VERSION 1 hosts; 'app' carries the new name.
            try:self.on_event({'schema_version':EVENT_SCHEMA_VERSION,'module':'signal','app':'overcast','event':event,**data})
            except Exception:pass  # host event handlers must not bring down the panel

    def _select_tree(self,tree,id):
        iid=str(id)
        if tree.exists(iid):
            tree.selection_set(iid)
            tree.see(iid)
            tree.event_generate('<<TreeviewSelect>>')

    def _new_worker_engine(self):
        return NewsOracleEngine(state_dir=self.engine.store.state_dir,context_profile=self.engine.context_profile)

    def connect(self):
        self._job('Connecting to LM Studio',lambda:LMStudioClient().models())

    def refresh(self):
        def task():
            e=self._new_worker_engine()
            try:return e.refresh()
            finally:e.close()
        self._job('Fetching headlines',task)

    def reload_all(self):
        self.reload_articles();self.reload_events();self.reload_claims();self.reload_forecasts();self.reload_calendar();self.reload_briefings();self.reload_outlooks()

    def reload_articles(self):
        rows=self.engine.articles(query=self.search_var.get().strip())
        selected=self.focus.get()
        if selected=='FOCUS TOPICS': rows=[row for row in rows if focus_tags(row)]
        elif selected!='ALL': rows=[row for row in rows if selected in focus_tags(row)]
        self._articles={str(x['id']):x for x in rows}
        self.article_tree.delete(*self.article_tree.get_children())
        for a in rows:
            self.article_tree.insert('', 'end', iid=str(a['id']),
                values=(friendly_date(a['published'] or a['collected']),a['source'],a['title']))
        if rows and not self.article_tree.selection():self._select_tree(self.article_tree,rows[0]['id'])
        if not rows:
            self._set_text(self.news_text,[('No cached articles\n','head'),
                ('Choose Refresh feeds (internet needed) to fetch headlines.\n','')])

    def _selected_ids(self):
        ids=[int(x) for x in self.article_tree.selection()]
        if not ids:
            raise ValueError('Select at least one headline from the News Wire.')
        if len(ids)>30:
            raise ValueError('Select at most 30 articles for analysis.')
        return ids

    def _show_article(self):
        ids=self.article_tree.selection()
        if not ids:return
        a=self._articles.get(ids[0])
        if not a:return
        self._selected_url=a['url']
        source_note=f"\n{len(ids)} items selected for analysis.\n" if len(ids)>1 else ''
        self._set_text(self.news_text,[(a['title']+'\n','head'),
           (a['source']+'  •  '+friendly_date(a['published'])+' UTC\n'+
            'TOPICS: '+(', '.join(focus_tags(a)) or 'OUTSIDE FOCUS')+'\n\n','muted'),
           ((a['summary'] or 'No summary in RSS feed.')+'\n\n',''),
           ('Original source\n','head'),(a['url']+'\n',''),
           ('\nFeed excerpt only. Open the original article to check the complete context and reporting.\n'+source_note,'muted')])

    def open_article(self):
        if self._selected_url.startswith(('https://','http://')):
            webbrowser.open(self._selected_url)

    def _model_id(self):
        model=self.model.get().strip()
        if not model:raise ValueError('Connect to LM Studio and select or enter a loaded model ID.')
        return model

    def briefing(self):
        try:ids=self._selected_ids();model=self._model_id()
        except ValueError as exc:messagebox.showwarning(APP_NAME,str(exc),parent=self);return
        def task():
            e=self._new_worker_engine()
            try:return e.briefing(ids,model)
            finally:e.close()
        self._job('Making briefing',task)

    def forecast(self):
        try:ids,_coverage=self._coverage();model=self._model_id();days=int(self.horizon.get())
        except ValueError as exc:messagebox.showwarning(APP_NAME,str(exc),parent=self);return
        def task():
            e=self._new_worker_engine()
            try:return e.forecast(ids,model,days)
            finally:e.close()
        self._job('Generating forecast',task)

    def reload_forecasts(self):
        all_rows=self.engine.forecasts()
        self._forecasts={str(x['id']):x for x in all_rows}
        self.forecast_tree.delete(*self.forecast_tree.get_children())
        today=datetime.now(timezone.utc).date().isoformat()
        oriented={r['id']:r for r in self.engine.store.oriented_forecasts()}
        def state_of(x):
            if x['outcome'] is not None:return 'Yes' if x['outcome']==1 else 'No'
            return 'Due' if x['target_date']<today else 'Open'
        mode=self.ledger_filter.get();needle=self.ledger_search.get().strip().casefold()
        if mode=='TOP RISKS':
            rows=[self._forecasts[str(r['id'])] for r in self.engine.risk_register(50) if str(r['id']) in self._forecasts]
        else:
            rows=[x for x in all_rows if mode=='ALL'
                  or (mode=='OPEN' and state_of(x)=='Open') or (mode=='DUE — RESOLVE' and state_of(x)=='Due')
                  or (mode=='RESOLVED' and x['outcome'] is not None)
                  or (mode=='SIGNPOSTS' and x['prompt_version'] in outlook_method.SIGNPOST_PROMPT_VERSIONS)]
        if needle:rows=[x for x in rows if needle in x['question'].casefold()]
        for x in rows:
            o=oriented.get(x['id'])
            risk=f"{o['risk_score']:.1f}" if o and x['outcome'] is None else ('—' if not o else '')
            state=state_of(x)
            self.forecast_tree.insert('','end',iid=str(x['id']),values=(x['id'],f"{x['probability']:.0%}",risk,
                                      x['target_date'],state,x['question']),
                                      tags=('due',) if state=='Due' else (('muted',) if x['outcome'] is not None else ()))
        report=self.engine.score_report()
        score=report['brier']
        due=report.get('overdue_unresolved') or 0
        due_note=f"   •   {due} past deadline, unresolved" if due else ''
        self.score.set((f"Resolved forecasts: {score['count']}   •   Brier: {score['score']:.4f} (coin-flip 0.25)"
                        f"   •   Log loss: {report['log_loss']:.3f} (coin-flip 0.693){due_note}")
                       if score['count'] else 'No resolved forecasts yet — scoring not available.'+due_note)
        if rows:self._select_tree(self.forecast_tree,rows[0]['id'])
        elif all_rows:self._set_text(self.forecast_text,[('Nothing matches this filter\n','head'),
                                               ('Choose ALL or clear the search box.\n','muted')])
        else:self._set_text(self.forecast_text,[('No forecasts yet\n','head'),
                                               ('Run Broad outlook for a scope, or pick stories on the News page and run a deep forecast.\n','')])
        if getattr(self,'_dashboard_ready',False):self.reload_dashboard()

    def show_forecast_packet(self):
        selection=self.forecast_tree.selection()
        if len(selection)!=1:return
        packet=self.engine.forecast_packet(int(selection[0]))
        if not packet:
            self._set_text(self.forecast_text,[('No legacy snapshot\n','head'),
                      ('This forecast predates v0.4 immutable evidence snapshots.\n','muted')]);return
        items=packet['packet'].get('articles',[])
        report='\n\n'.join(
             f"[{a['id']}] {a['source']} | {a['published'] or 'undated'} | first seen {a['collected']}\n"
             f"{a['title']}\n{a['summary']}\n{a['url']}" for a in items)
        self._set_text(self.forecast_text,[('Frozen forecast evidence\n','head'),
             (f"AS OF {packet['as_of_utc']}\nSHA256: {packet['sha256']}\n"
              f"CHECKSUM: {'OK' if packet['checksum_valid'] else 'FAILED'}\n"
              f"{len(items)} cached RSS records; NOT full article bodies.\n"
              +(f"Model saw each excerpt cut to {packet['packet']['excerpt_chars_sent']} characters "
                f"({packet['packet'].get('context_profile') or 'unknown'} context profile).\n"
                if packet['packet'].get('excerpt_chars_sent') else '')+'\n','muted'),
             (report,'')])

    def _show_forecast(self):
        selected=self.forecast_tree.selection()
        if not selected:return
        x=self._forecasts.get(selected[0])
        if not x:return
        evidence=json.loads(x['evidence_json'])
        resolution='Open: outcome not yet recorded.' if x['outcome'] is None else f"Resolved {'YES' if x['outcome'] else 'NO'} on {x['resolved_at']}\nEvidence: {x['resolution_url']}\n{x['resolution_note']}"
        cited='\n'.join(f"[{row['article_id']}] {row['source']} — {row['title']}\n{row['url']}" for row in evidence)
        audit=self.engine.forecast_audit(x['id'])
        extra=[]
        if audit:
            q=audit.get('question') or {}
            if q.get('window_start'):
                extra.extend([('Model-estimated event window / not a schedule\n','head'),
                    (f"{q['window_start']} through {q['window_end']}\nBasis: {q.get('timing_basis') or 'unknown'}\n\n",'')])
            inv=audit.get('investigation')
            if inv:
                actors='\n\n'.join(f"{a['actor']}\n  Observed: {a['observed_action']}\n  Possible incentive (not verified): {a['possible_incentive']}\n  Alternative: {a['alternative_explanation']}\n  Sources: {a['evidence_article_ids']}" for a in inv['actors'])
                links='\n\n'.join(f"{c['from']} → {c['to']}\n  Hypothesis: {c['mechanism_hypothesis']}\n  Other explanation: {c['noncausal_alternative']}\n  Would be disproved by: {c['disconfirming_signal']}\n  Sources: {c['evidence_article_ids']}" for c in inv['connections'])
                extra.extend([('Strategic incentives — hypotheses, not facts\n','head'),
                    ((actors or 'No sourced incentive hypotheses.')+'\n\n',''),
                    ('Possible correlations / connections (not causal proof)\n','head'),
                    ((links or 'No evidenced cross-event links.')+'\n\n',''),
                    ('Downside scenario\n','head'),(inv['downside_path']+'\n\n',''),
                    ('Stabilising / benign alternative\n','head'),(inv['stabilising_path']+'\n\n',''),
                    ('Early warning indicators\n','head'),('\n'.join('• '+i for i in inv['watch_signals'])+'\n\n','')])
            elif audit.get('investigation_error'):
                extra.extend([('Investigation incomplete\n','head'),
                    (audit['investigation_error']+'\n\n','muted')])
            extra=[('Method / audit\n','head'),
                (f"{audit['method']} | as-of {audit['created_as_of_utc']} | "
                 f"{len(audit['expanded_article_ids'])} source items / "
                 f"{len(audit['publisher_domains'])} domains\n"
                 f"Scope: {SCOPE_LABELS.get(audit.get('scope_label'),audit.get('scope_label')) or 'individual event'}\n"
                 f"{(audit['aggregation'].get('rule') or 'median').capitalize()} {audit['aggregation'].get('aggregate_percent',audit['aggregation']['median_percent']):.1f}% | "
                 f"Range {audit['aggregation']['range_percent'][0]:.1f}–{audit['aggregation']['range_percent'][1]:.1f}% "
                 f"({audit['aggregation']['valid_passes']} valid passes)\n\n",'muted'),
                ('Perspectives\n','head'),
                ('\n\n'.join(f"{p['lens']}: {p['probability_percent']:.1f}% — source IDs "
                f"{p['cited_article_ids']}\n{p['reasoning']}\nAgainst: {p['counterargument']}"
                for p in audit['valid_votes'])+'\n\n',''),
                ('Data quality\n','head'),('\n'.join(audit['quality_warnings'])+'\n\n','')] + extra
            gap=audit.get('gap_research') or {}
            if gap.get('attempted'):
                extra += [('Targeted evidence-gap review\n','head'),
                    (f"Retrieved {len(gap.get('added') or [])} extra cached sources; "
                     f"plan: {json.dumps(gap.get('plan'),ensure_ascii=False)}\n"
                     f"Error: {gap.get('error') or 'none'}\n\n",'')]
            timing=audit.get('conditional_timing')
            if timing:
                bins='\n'.join(f"Through {b['end_date']}: conditional cumulative "
                     f"{b['conditional_cdf']:.0%}; event occurs in this time bucket "
                     f"{b['unconditional_event_bucket']:.1%} (uncalibrated)"
                     for b in timing['checkpoints'])
                extra += [('Event timing distribution — model estimate\n','head'),
                          (bins+'\n\n'+timing['reasoning']+'\n\n','')]
            elif audit.get('timing_error'):
                extra += [('Timing estimate not available\n','head'),
                          (audit['timing_error']+'\n\n','muted')]
        cal=self.engine.calibrated_probability(x['probability'])
        cal_text=(f"Calibrated from your {cal['resolved']} resolved forecasts: {cal['probability']:.0%} "
                  "(display only; the ledger keeps the raw value)\n") if cal else ''
        spans=[(x['question']+'\n','head'),
          (f"P(yes) {x['probability']:.0%}   ·   resolves by {x['target_date']}   ·   model {x['model_id']}\nCreated {friendly_date(x['created'])} UTC\n"+cal_text+'\n','muted'),
          ('Resolution rule\n','head'),(x['resolution_criteria']+'\n\n',''),
          ('Rationale\n','head'),(x['reasoning']+'\n\n',''),
          ('Counterargument\n','head'),(x['counterargument']+'\n\n',''),
          ('What would change the odds\n','head'),(x['change_mind']+'\n\n',''),
          *extra,('Source evidence\n','head'),(cited+'\n\n',''),
          ('Outcome / scoring\n','head'),(resolution+'\n','')]
        self._set_text(self.forecast_text,spans)
        self._render_result('Forecast #'+str(x['id']),spans)

    def _resolve(self,outcome):
        selected=self.forecast_tree.selection()
        if not selected:
            messagebox.showwarning(APP_NAME,'Select one forecast to resolve.',parent=self);return
        if len(selected)!=1:
            messagebox.showwarning(APP_NAME,'Resolve one forecast at a time.',parent=self);return
        x=self._forecasts[selected[0]]
        if x['outcome'] is not None:
            messagebox.showinfo(APP_NAME,'This forecast has already been resolved and cannot be overwritten.',parent=self);return
        url=simpledialog.askstring('Resolution evidence',
                f"Provide a published evidence URL supporting {'YES' if outcome else 'NO'} for forecast #{x['id']}.",parent=self)
        if url is None:return
        note=simpledialog.askstring('Resolution note','Explain briefly how the resolution criteria were met:',parent=self)
        if note is None:return
        if not messagebox.askyesno('Confirm permanent result',
              f"Record forecast #{x['id']} as {'YES' if outcome else 'NO'}? This locks its result.",parent=self):return
        try:self.engine.resolve(x['id'],outcome,url.strip(),note.strip())
        except (ValueError,Exception) as exc:
            messagebox.showerror(APP_NAME,str(exc),parent=self);return
        self.reload_forecasts()
        self._select_tree(self.forecast_tree,x['id'])
        self.status.set(f"Forecast #{x['id']} resolved; Brier score recalculated.")
        self._emit('forecast_resolved',id=x['id'],outcome=outcome)

    def reload_briefings(self):
        rows=self.engine.store.briefings()
        self._briefings={str(x['id']):x for x in rows}
        self.brief_tree.delete(*self.brief_tree.get_children())
        for x in rows:
            self.brief_tree.insert('','end',iid=str(x['id']),values=(x['id'],friendly_date(x['created']),x['title']))
        if rows:self._select_tree(self.brief_tree,rows[0]['id'])
        else:self._set_text(self.brief_text,[('No briefings\n','head'),
                                             ('Select stories on the News page, then choose Briefing.\n','')])

    def _show_briefing(self):
        selected=self.brief_tree.selection()
        if not selected:return
        x=self._briefings[selected[0]]
        evidence=json.loads(x['evidence_json'])
        cited='\n'.join(f"[{row['article_id']}] {row['source']} — {row['url']}" for row in evidence)
        spans=[(x['title']+'\n','head'),
            (f"Generated {x['created']} • Model {x['model_id']}\n\n",'muted'),
            ('Briefing\n','head'),(x['briefing']+'\n\n',''),
            ('Uncertainties\n','head'),(x['uncertainties']+'\n\n',''),
            ('Evidence\n','head'),(cited+'\n','')]
        self._set_text(self.brief_text,spans)
        self._render_result('Briefing #'+str(x['id']),spans)

    def destroy(self):
        self._closed=True
        if self._auto_after is not None:
            try:self.after_cancel(self._auto_after)
            except tk.TclError:pass
            self._auto_after=None
        if self._palette is not None:
            try:self._palette.destroy()
            except tk.TclError:pass
        if self._poll_after is not None:
            try:self.after_cancel(self._poll_after)
            except tk.TclError:pass
            self._poll_after=None
        self.engine.close()
        super().destroy()


def _set_window_icon(root):
    """Dock/taskbar icon from the packaged PNG; silently skipped on a Tk without PNG support."""
    assets=Path(__file__).resolve().parent/'assets'
    try:
        icons=[tk.PhotoImage(master=root,file=str(assets/name)) for name in ('overcast.png','overcast_64.png')
               if (assets/name).exists()]
        if icons:
            root.iconphoto(True,*icons)
            root._overcast_icons=icons     # keep references alive
    except tk.TclError:
        pass


def run_standalone():
    root=tk.Tk(className='Overcast')   # WM_CLASS matches StartupWMClass in the .desktop file
    root.title(f'{APP_NAME.title()} — {TAGLINE}')
    _set_window_icon(root)
    try:
        width,height=min(1440,root.winfo_screenwidth()-80),min(920,root.winfo_screenheight()-100)
        root.geometry(f'{max(1024,width)}x{max(680,height)}')
    except tk.TclError:
        root.geometry('1360x860')
    root.minsize(1024,680)
    panel=NewsOraclePanel(root,standalone=True)
    root.configure(bg=BG)
    panel.pack(fill='both',expand=True)
    panel.install_shortcuts(root)
    root.mainloop()
