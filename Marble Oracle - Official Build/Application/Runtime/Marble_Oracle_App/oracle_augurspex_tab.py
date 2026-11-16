"""AUGURSPEX as a native Marble Oracle workspace (no browser/server process).

Uses AUGURSPEX's original state, watchlist validation and rate-limited public
market providers. Tk owns the UI; blocking provider calls run on worker threads.
There is no fabricated quote, alternate ticker substitution, or login.
"""
from __future__ import annotations

import csv
import os
import re
from datetime import datetime, timezone
import queue
import threading
import time
import tkinter as tk
from tkinter import messagebox, filedialog
from tkinter import font as tkfont  # noqa: F401  (kept for importers)
from oracle_ogg_texture import frame as ogg_frame, FILES as OGG_TEXTURE_FILES
from concurrent.futures import ThreadPoolExecutor
from collections import deque
from pathlib import Path

from Augurspex.augurspex.core import (
    LAYOUTS, WORKSPACES, INTERVALS, read_settings,
    save_settings, merge_watchlists, update_watchlist, clean_item,
    market_category, reset_to_popular_markets_once, app_folder,
)
from Augurspex.augurspex.providers import (MarketRouter, shared_market_router,
    local_stock_path, read_local_stock_csv, LOCAL_IMPORT_LIMIT)
from marble_uberata import FAMILY
from oracle_design import HOME_LABEL, MARKET_COLORS, MARKET_LABELS, flow_layout
from oracle_widgets import tooltip
import oracle_shell as shell
# Re-exported on purpose: tests and oracle_augurspex_insights import these names from this module.
from oracle_augurspex_logic import (  # noqa: F401
    CARD_CHROME_H, CARD_CHROME_W, CARD_GAP, CHART_PAD_B, CHART_PAD_L, CHART_PAD_R, CHART_PAD_T,
    MIN_CARD_H, MIN_CARD_W, SHORT_STATUS, _blend, _darken, _plotted_candles, _rgb,
    axis_date_labels, chart_date_ticks, chart_display_bars, chart_geometry, chart_grid_plan, csv_safe, fit_date_ticks,
    fit_text_pixels, format_price, format_quote, history_health, observed_at, plot_points,
    provider_diagnostics, status_for_error,
)

DEFAULT_FILE = Path(__file__).resolve().parent / 'Augurspex' / 'augurspex' / 'default_watchlist.json'


def _parent_bg(widget, fallback):
    return getattr(widget,'_oracle_bg',fallback)


from oggcultist_design_system import COLOR as _SUITE  # noqa: E402
C_TEXT_BRIGHT=_SUITE['text_bright']   # titles, as oracle_shell draws them in every workspace


def palette(theme=None):
    """The suite's Ember surfaces and text (as every workspace uses); a GRADE theme sets the accents.

    Until 0.4.9.4 AUGURSPEX darkened every surface by 10-24 %, so it looked
    like a different application from the tab next to it, and its labels sat
    on a slightly different colour from the textured panels behind them.
    """
    from oggcultist_design_system import COLOR as C
    colours = dict(bg=C['canvas'], panel=C['raised'], inset=C['sunken'], rail=C['sidebar'],
                   border=C['line'], control=C['control'], active=C['accent_soft'],
                   accent=C['accent'], ink=C['text'], muted=C['text_2'],
                   weak=C['text_3'], green=C['done'], red=C['failed'])
    if theme is not None:
        colours.update(accent=theme.get('cyan',colours['accent']),
                       green=theme.get('lime',colours['green']), red=theme.get('red',colours['red']))
    return colours


class FontMeasure:
    """Measure text in a Tk font without a tkinter.font.Font object.

    Font objects delete their Tk font in __del__. Python's garbage collector
    may run that on a market-data worker thread; if the font's interpreter is
    gone, the call never returns and the worker (and its chart) hangs. This
    keeps no Tk resource, so there is nothing to delete.
    """
    __slots__ = ('_tk', '_spec')

    def __init__(self, widget, spec):
        self._tk = widget.tk
        self._spec = spec

    def measure(self, text):
        return int(self._tk.call('font', 'measure', self._spec, str(text)))


class PriceChart(tk.Frame):
    """A chart card, rendered entirely by Tk Canvas in the suite palette."""
    def __init__(self, master, colours, index, click, on_style=None):
        self.p=colours;self.index=index;self.symbol='';self.name='';self.result=None
        self.on_style=on_style
        self.view_bars='MAX'
        self.error=None;self.loading=False;self.selected=False;self.style='2'
        super().__init__(master,bg=self.p['panel'],highlightbackground=self.p['border'],highlightthickness=1)
        head=tk.Frame(self,bg=self.p['panel'])
        head.pack(fill='x', padx=10,pady=(7,2))
        headline=tk.Frame(head,bg=self.p['panel'])
        headline.pack(fill='x')
        self.title=tk.Label(headline,text='UNASSIGNED',anchor='w',bg=self.p['panel'],
                            fg=self.p['ink'],font=(FAMILY,15,'bold'))
        self.title.pack(side='left',fill='x',expand=True)
        self.price=tk.Label(headline,text='',bg=self.p['panel'],fg=self.p['green'],
                            font=(FAMILY,14,'bold'))
        self.price.pack(side='right',padx=(6,0))
        # Per-chart LINE / CANDLES switch, as in other market viewers.
        self.style_toggle=tk.Frame(headline,bg=self.p['border'])
        self.style_toggle.pack(side='right',padx=(6,0))
        self.style_buttons={}
        for code,text in (('2','LINE'),('1','CANDLES')):
            button=tk.Label(self.style_toggle,text=text,font=(FAMILY,9,'bold'),padx=6,pady=1,cursor='hand2',
                            bg=self.p['control'],fg=self.p['muted'])
            button.pack(side='left',padx=(0 if code=='2' else 1,0),pady=1)
            button.bind('<Button-1>',lambda _e,c=code:self._choose_style(c))
            self.style_buttons[code]=button
        self.company=tk.Label(head,text='',anchor='w',bg=self.p['panel'],fg=self.p['muted'],
                              font=(FAMILY,11),height=1)
        self.company.pack(fill='x',pady=(1,0))
        self._company_text=''
        self._info_text=''
        self._hover_text=None
        self._plot_bars=[]
        self._plot_points=[]
        self._company_font=FontMeasure(self,(FAMILY,11))
        self._info_font=FontMeasure(self,(FAMILY,10))
        self.bind('<Configure>',lambda _e:self._fit_card_labels(),add='+')
        # The info strip must claim its space BEFORE the expandable canvas.
        # Packing the canvas first made its requested height squeeze the info
        # and graph axes out of 3x3 cards on real CRT-sized windows.
        self.info=tk.Label(self,text='Select a market from the left',anchor='w',bg=self.p['panel'],fg=self.p['muted'],font=(FAMILY,10))
        self.info.pack(side='bottom',fill='x',padx=8,pady=(0,5))
        self.canvas=tk.Canvas(self,bg=self.p['inset'],bd=0,highlightthickness=0,width=100,height=100)
        self._texture_tile=None  # Oggcultist's unmodified sunken grain PNG
        self.canvas.pack(side='top',fill='both',expand=True,padx=6,pady=(3,5))
        for widget in (self,self.canvas,head,headline,self.title,self.company,self.price,self.info):
            widget.bind('<Button-1>',lambda _e, i=index:click(i),add='+')
        self.canvas.bind('<Configure>',lambda _e:self.redraw())
        self.canvas.bind('<Motion>',self._on_chart_motion,add='+')
        self.canvas.bind('<Leave>',self._on_chart_leave,add='+')
        # Keyboard alternative to mouse-only crosshair. Focus stays on the
        # graph after selection and arrow/Home/End inspect real observations.
        self.canvas.configure(takefocus=True)
        self._cursor_index=None
        self.canvas.bind('<Button-1>',lambda _e:self.canvas.focus_set(),add='+')
        self.canvas.bind('<Right>',lambda _e:self._step_observation(1),add='+')
        self.canvas.bind('<Left>',lambda _e:self._step_observation(-1),add='+')
        self.canvas.bind('<Home>',lambda _e:self._jump_observation(0),add='+')
        self.canvas.bind('<End>',lambda _e:self._jump_observation(-1),add='+')
        self.canvas.bind('<FocusIn>',lambda _e:self.canvas.configure(highlightthickness=2,
                          highlightbackground=self.p['accent']),add='+')
        self.canvas.bind('<FocusOut>',lambda _e:self.canvas.configure(highlightthickness=0),add='+')

    def _choose_style(self, code):
        if self.on_style is not None:
            self.on_style(self.index, code)
        return 'break'

    def _paint_style_toggle(self):
        for code,button in self.style_buttons.items():
            on=code==self.style
            button.configure(bg=self.p['active'] if on else self.p['control'],
                             fg=self.p['accent'] if on else self.p['muted'])

    def _fit_card_labels(self):
        width=max(80,self.winfo_width()-24)
        self.company.configure(text=fit_text_pixels(self._company_text,self._company_font,width))
        self.info.configure(text=fit_text_pixels(self._hover_text or self._info_text,self._info_font,width))

    def _on_chart_motion(self, event):
        """Read an actual observation with mouse hover; no new data fetch."""
        if not self._plot_points or event.x < CHART_PAD_L or event.x > self.canvas.winfo_width()-CHART_PAD_R:
            self._on_chart_leave();return
        width=max(1,self.canvas.winfo_width()-CHART_PAD_L-CHART_PAD_R)
        index=max(0,min(len(self._plot_points)-1,int((event.x-CHART_PAD_L)*len(self._plot_points)/width)))
        self._inspect_observation(index)

    def _inspect_observation(self, index):
        if not self._plot_points or not self._plot_bars:return
        index=max(0,min(len(self._plot_points)-1,index))
        self._cursor_index=index
        row=self._plot_bars[index]
        x,y=self._plot_points[index][0],self._plot_points[index][4]
        raw_date=str(row.get('time') or 'UNKNOWN DATE')[:19]
        self._hover_text=f'{raw_date} · CLOSE {format_price(row["close"])}'
        if not row.get('close_only'):
            self._hover_text+=f' · O {format_price(row["open"])} · H {format_price(row["high"])} · L {format_price(row["low"])}'
        self._fit_card_labels()
        c=self.canvas;c.delete('cursor-guide')
        c.create_line(x,CHART_PAD_T,x,self._plot_bottom,fill=self.p['muted'],dash=(3,4),width=1.4,tags=('cursor-guide',))
        c.create_oval(x-5,y-5,x+5,y+5,outline=self.p['ink'],fill=self.p['accent'],width=1.7,tags=('cursor-guide',))

    def _step_observation(self, delta):
        if self._plot_points:
            current=self._cursor_index
            if current is None:current=-1 if delta>0 else len(self._plot_points)
            self._inspect_observation(current+delta)
        return 'break'

    def _jump_observation(self, index):
        if self._plot_points:self._inspect_observation(len(self._plot_points)-1 if index==-1 else 0)
        return 'break'

    def _on_chart_leave(self,_event=None):
        self.canvas.delete('cursor-guide')
        self._cursor_index=None
        if self._hover_text is not None:
            self._hover_text=None
            self._fit_card_labels()

    def _message_for_error(self, error):
        return status_for_error(error, getattr(self,'symbol',''))

    def _draw_texture(self, width, height):
        """Tile the original bundled Oggcultist grain behind charts, not labels."""
        if self._texture_tile is None:
            try:
                self._texture_tile=tk.PhotoImage(master=self.canvas,file=str(OGG_TEXTURE_FILES['sunken']))
            except tk.TclError:
                return
        tile=self._texture_tile
        w,h=max(1,tile.width()),max(1,tile.height())
        self.canvas.delete('bgtex')
        for x in range(0,width,w):
            for y in range(0,height,h):
                self.canvas.create_image(x,y,image=tile,anchor='nw',tags=('bgtex',))
        self.canvas.tag_lower('bgtex')

    @staticmethod
    def _provider_diagnostics(error):
        """Short visible status for each attempted market source."""
        return provider_diagnostics(error)

    def display(self,symbol,name,data,error,loading,style,selected,auto_note='',period='D',view_bars='MAX'):
        self.symbol=symbol;self.name=name;self.result=data;self.error=error;self.auto_note=auto_note
        self._hover_text=None
        self._cursor_index=None
        self.loading=loading;self.style=style;self.selected=selected
        self.view_bars=view_bars if str(view_bars) in ('30','90','MAX') else 'MAX'
        self._paint_style_toggle()
        self.configure(highlightbackground=self.p['accent'] if selected else self.p['border'],
                       highlightthickness=2 if selected else 1)
        self.title.configure(text=f'{self.index+1:02d}  {symbol or "EMPTY SLOT"}')
        self._company_text=(name if name and name!=symbol else ('MARKET NOT ASSIGNED' if not symbol else ''))
        if auto_note:
            # Shown, never silent: this space is borrowing a watchlist market
            # because its own saved market has no data.
            self._company_text=f'AUTO-FILLED · {auto_note}'
        self.company.configure(fg=self.p['accent'] if auto_note else self.p['muted'])
        candles=(data or {}).get('candles',[])
        if candles:
            # The percentage must describe the same real observations as the
            # selected visible window, not an unrelated provider-wide span.
            display_style='2' if any(b.get('close_only') for b in _plotted_candles(candles,limit=None)) else style
            window=chart_display_bars(candles,max(200,self.canvas.winfo_width()),display_style,self.view_bars)
            last=float(window[-1]['close']) if window else float(candles[-1]['close'])
            first=float(window[0]['close']) if window else last
            change=((last/first)-1)*100 if first else 0
            self.price.configure(text=format_quote(last),
                                 fg=self.p['green'] if change>=0 else self.p['red'])
            src=data.get('source','');cur=data.get('currency','');obs=data.get('latest_observation','')[:10]
            health,last_at=history_health(data,symbol,period)
            stale_tag=(f' · STALE {last_at:%Y-%m-%d}' if health=='stale' else
                       ' · DATE UNVERIFIED' if health in ('undated','future') else '')
            close_only=any(bool(row.get('close_only')) for row in _plotted_candles(candles,limit=None))
            bar_count=len(_plotted_candles(candles,limit=None))
            visible_count=len(chart_display_bars(candles,max(200,self.canvas.winfo_width()),style,self.view_bars))
            history_label=('CLOSE-ONLY HISTORY · ' if close_only else
                           f'LAST {visible_count} OF {bar_count} REAL BARS · '
                           if visible_count<bar_count and style=='1' else '')
            self._info_text=(history_label+f'{src} · {cur} · {obs} · VIEW {change:+.2f}%'
                             + stale_tag
                             + (' · CACHED' if data.get('cache')=='stale' else ''))
        else:
            self.price.configure(text='')
            if not symbol:info='Click a market on the left to assign'
            elif error:info=('SOURCE DETAILS → configure a supported market feed' if 'no eligible provider' in str(error).lower() else 'SOURCES · '+(self._provider_diagnostics(error) or str(error)[:120]))
            elif loading:info='Loading public market history…'
            else:info='Awaiting market data'
            self._info_text=info
        self._fit_card_labels()
        self.redraw()

    def redraw(self):
        c=self.canvas;c.delete('all')
        self._plot_bars=[];self._plot_points=[]
        width,height=max(40,c.winfo_width()),max(40,c.winfo_height())
        self._draw_texture(width,height)
        candles=(self.result or {}).get('candles',[])
        # Draw the latest *real* observations at a minimum useful candle width.
        # Never manufacture OHLC values, compress dates or rename intervals.
        close_only=any(row.get('close_only') for row in _plotted_candles(candles,limit=None))
        render_as_candles=self.style=='1' and not close_only
        display_style='1' if render_as_candles else '2'
        visible=chart_display_bars(candles,width,display_style,self.view_bars)
        points,bounds=plot_points(visible,width,height,display_style)
        if not points:
            txt=('NO MARKET SELECTED' if not self.symbol else
                 self._message_for_error(self.error) if self.error else
                 'LOADING' if self.loading else 'AWAITING DATA')
            c.create_text(width/2,height/2,text=txt,fill=self.p['muted'],font=(FAMILY,12,'bold'))
            return
        self._plot_bars=visible
        self._plot_points=points
        mn,mx=bounds
        plot_right=max(CHART_PAD_L+1,width-CHART_PAD_R)
        plot_bottom=max(CHART_PAD_T+1,height-CHART_PAD_B)
        self._plot_bottom=plot_bottom
        grid_minor=_blend(self.p['inset'],self.p['muted'],0.26)
        grid_major=_blend(self.p['inset'],self.p['muted'],0.49)
        graph_outline=_blend(self.p['inset'],'#000000',0.70)
        # Clear rectangle outline and vertical guides make trends readable
        # without competing with the chart or its axis labels.
        c.create_rectangle(CHART_PAD_L,CHART_PAD_T,plot_right,plot_bottom,
                           outline=grid_major,width=1.2,tags=('plot-frame',))
        tick_count=5 if height>=250 else 4 if height>=180 else 3
        axis_size=11 if width>=370 else 9
        price_labels=[format_price(mx-(mx-mn)*k/(tick_count-1)) for k in range(tick_count)]
        # Six-figure and sub-cent prices are wider than the reserved band at
        # the normal size: step the axis font down instead of clipping them.
        price_size=axis_size
        for price_size in dict.fromkeys((axis_size,9,8,7)):
            fitter=FontMeasure(c,(FAMILY,price_size,'bold'))
            if max(fitter.measure(text) for text in price_labels)<=CHART_PAD_R-12:break
        for k in range(tick_count):
            f=k/(tick_count-1)
            yy=CHART_PAD_T+(plot_bottom-CHART_PAD_T)*f
            c.create_line(CHART_PAD_L,yy,plot_right,yy,
                          fill=grid_major if k in (0,tick_count-1) else grid_minor,
                          dash=() if k in (0,tick_count-1) else (3,4),
                          width=1.2 if k in (0,tick_count-1) else 1,
                          tags=('chart-grid','horizontal-grid'))
            c.create_line(plot_right,yy,plot_right+5,yy,
                          fill=grid_major,width=1.3)
            c.create_text(plot_right+8,yy,text=price_labels[k],
                          fill=self.p['ink'],font=(FAMILY,price_size,'bold'),anchor='w',
                          tags=('axis-label','price-label'))
        date_font=FontMeasure(c,(FAMILY,axis_size,'bold'))
        dates=axis_date_labels(visible,width,date_font.measure)
        for x,label,anchor in dates:
            if anchor=='n':
                c.create_line(x,CHART_PAD_T,x,plot_bottom,
                              fill=grid_minor,dash=(3,5),width=1.1,
                              tags=('chart-grid','vertical-grid'))
            c.create_line(x,plot_bottom,x,plot_bottom+5,fill=grid_major,width=1.3)
            c.create_text(x,plot_bottom+8,text=label,anchor=anchor,
                          fill=self.p['ink'],font=(FAMILY,axis_size,'bold'),
                          tags=('axis-label','date-label'))
        if render_as_candles:
            step=max(1.0,(plot_right-CHART_PAD_L)/len(points))
            body=max(3.8,min(11.5,step*.72))
            for x,yo,yh,yl,yc in points:
                col=self.p['green'] if yc<=yo else self.p['red']
                # Two-pass wick: deep outline, bright core.
                c.create_line(x,yh,x,yl,fill=graph_outline,width=5.0,
                              capstyle=tk.ROUND,tags=('price-outline','candle-wick'))
                c.create_line(x,yh,x,yl,fill=col,width=2.8,
                              capstyle=tk.ROUND,tags=('price-mark','candle-wick'))
                top,bottom=min(yo,yc),max(yo,yc)
                if bottom-top<2.8:
                    middle=(top+bottom)/2
                    top,bottom=middle-1.6,middle+1.6
                c.create_rectangle(x-body/2,top,x+body/2,bottom,
                                   outline=graph_outline,fill=col,width=2.0,
                                   tags=('price-mark','candle-body'))
                # A faint light edge helps the body show up on black textures.
                if body>=6.0 and bottom-top>=5.0:
                    c.create_line(x-body/2+1,top+1,x+body/2-1,top+1,
                                  fill=_blend(col,self.p['ink'],0.38),width=1.0,
                                  tags=('price-mark','candle-highlight'))
        else:
            coords=[]
            for x,_,_,_,close_y in points:
                coords.extend((x,close_y))
            if len(points)>1:
                c.create_line(*coords,fill=graph_outline,width=7.4,
                              capstyle=tk.ROUND,joinstyle=tk.ROUND,
                              tags=('price-outline','price-line'))
                c.create_line(*coords,fill=self.p['accent'],width=4.4,
                              capstyle=tk.ROUND,joinstyle=tk.ROUND,
                              tags=('price-mark','price-line'))
            last_x,last_y=points[-1][0],points[-1][4]
            c.create_oval(last_x-5,last_y-5,last_x+5,last_y+5,
                          fill=self.p['accent'],outline=graph_outline,width=2.2,
                          tags=('price-mark','last-point'))
        count=len(_plotted_candles(candles,limit=None))
        note=('CLOSE-ONLY HISTORY · line chart' if close_only else
              f'LAST {len(points)} OF {count} REAL BARS' if len(points)<count else
              f'{count} observations · historical / provider delay')
        # Source metadata is already in the card footer and SOURCE DETAILS.
        # Never draw a competing caption under the date axis: the date labels
        # can be taller than one line in Uberata fonts at different DPI levels.
        self._observation_note=note


class AugurspexPanel(tk.Frame):
    """Full featured, native watchlist/multi-chart AUGURSPEX tab."""
    def __init__(self,master,on_home,theme=None,home=None,router=None,offline=False):
        self.p=palette(theme);self.home=Path(home) if home else Path.home()
        self.on_home=on_home;self.offline=offline
        self.router=router if router is not None else shared_market_router(self.home/'.cache/augurspex/market')
        if home is None:
            # One-time, backed-up replacement explicitly requested for the public release.
            reset_to_popular_markets_once(self.home,DEFAULT_FILE)
        self.settings=read_settings(self.home)
        if hasattr(self.router,'allow_unofficial') or isinstance(self.router,MarketRouter):
            self.router.allow_unofficial=self.settings.get('unofficial_sources',False)
        if isinstance(self.router,MarketRouter):
            self.router.import_dir=app_folder(self.home)/'imported-history'
        self.watchlist=[];self.rows=[];self.active=0;self.cards=[];self._visible=False
        self._errors={};self._data={};self._requests={};self._pending=set();self._failed_at={}
        self._health_cache={}  # by result identity + UTC day, not stale across sessions
        # Only charts with real returned observations are shown by default.
        # We never remove a user's saved selections on a transient outage.
        self.sourced_only=False  # Show curated categories immediately; never hide the watchlist during verification
        self._audit_queue=deque();self._audit_queued=set();self._audit_active=None
        self._audit_completed=set()
        self._layout_job=None;self._layout_sig=None;self._chip_sig=None;self._view_size=(0,0)
        self.chip_widgets=[];self._chip_slots=[]
        self._stopped=False;self._after=None;self._lock=threading.Lock()
        self._results=queue.Queue();self._pool=ThreadPoolExecutor(max_workers=3,thread_name_prefix='augurspex-chart')
        super().__init__(master,bg=self.p['bg'],highlightthickness=0)
        self._load_watchlist()
        self.search=tk.StringVar(value='');self.search.trace_add('write',lambda *_:self._refresh_watch())
        self.symbol_input=tk.StringVar(value='')
        self.status=tk.StringVar(value='HISTORY, NOT LIVE QUOTES · STOCKS DELAYED / END OF DAY · CRYPTO VENUE PRICES · SEE SOURCE DETAILS')
        self._build_ui()
        self._refresh_watch();self._refresh_charts()

    def _label(self,parent,text,fg='ink',size=10,bold=False,**kw):
        kw.setdefault('font',(FAMILY,size,'bold' if bold else 'normal'))
        return tk.Label(parent,text=text,bg=_parent_bg(parent,self.p['bg']),fg=self.p[fg],**kw)

    def _button(self,parent,text,callback,active=False):
        # The suite button (oracle_shell), a little narrower: AUGURSPEX fits
        # rows of filters and tools. `active` marks the current filter.
        btn=shell.button(parent,text,callback,padx=10,pady=6)
        if active:
            btn.configure(bg=self.p['active'],fg=self.p['accent'],highlightbackground=self.p['accent'])
        return btn

    def _fit_rail_height(self,event):
        short=event.height<shell.SHORT_HEIGHT
        if short==self._rail_short:
            return
        self._rail_short=short
        if short:
            self.rail_tagline.pack_forget();self.rail_version.pack_forget()
        else:
            self.rail_tagline.pack(fill='x',padx=shell.RAIL_PADX,pady=(4,0),after=self._rail_brand)
            self.rail_version.pack(fill='x',pady=(8,0))

    def _watch_tip(self,event):
        """The full symbol and name of the watchlist row under the pointer, if it was shortened."""
        try:
            row=self.watch.nearest(event.y)
            box=self.watch.bbox(row)
        except tk.TclError:
            return ''
        if not box or not (box[1]<=event.y<=box[1]+box[3]) or not 0<=row<len(self._watch_full):
            return ''
        return self._watch_full[row]

    def _entry(self,parent,variable):
        return tk.Entry(parent,textvariable=variable,relief='flat',bd=0,
                        bg=self.p['inset'],fg=self.p['ink'],insertbackground=self.p['accent'],
                        highlightthickness=1,highlightbackground=self.p['border'],font=shell.font('body'))

    def _option(self,parent,var,values,command):
        btn=tk.OptionMenu(parent,var,*values,command=command)
        btn.configure(bg=self.p['control'],fg=self.p['ink'],activebackground=self.p['active'],
                      activeforeground=self.p['ink'],highlightthickness=0,bd=0,relief='flat',
                      font=(FAMILY,11),indicatoron=True)
        btn['menu'].configure(bg=self.p['control'],fg=self.p['ink'],activebackground=self.p['active'],
                              activeforeground=self.p['ink'],font=(FAMILY,11))
        return btn

    def _fit(self,label,text,width=None):
        """Show `text` in one line of `label`, ellipsised to its measured width."""
        if width is None:
            width=label.winfo_width()
            if width<=1:width=label.winfo_reqwidth()
        width=max(20,int(width)-2*int(label.cget('padx') or 0)-2)
        fitted=fit_text_pixels(text,FontMeasure(self,label.cget('font')),width)
        if label.cget('text')!=fitted:label.configure(text=fitted)
        # The full wording is one hover away whenever it had to be shortened.
        label._full_text=text if fitted!=text else ''
        if not getattr(label,'_has_tip',False):
            label._has_tip=True
            tooltip(label,lambda _e,l=label:getattr(l,'_full_text',''))

    def _build_ui(self):
        # Native layout matches the palette and proportions of EIDOLITH/Oggcultist.
        # A *Tk* shell holds the rail width. The textured ttk child alone
        # may collapse to a tiny image-element width on some Linux Tk themes.
        self.rail_shell=tk.Frame(self,bg=self.p['rail'],width=shell.LIST_RAIL_WIDTH)
        self.rail_shell.pack(side='left',fill='y')
        self.rail_shell.pack_propagate(False)
        self.rail=ogg_frame(self.rail_shell,bg='#130F0D')
        self.rail._oracle_bg=self.p['rail']
        self.rail.pack(fill='both',expand=True)
        tk.Frame(self,bg=self.p['border'],width=1).pack(side='left',fill='y')
        self.work=ogg_frame(self,bg='#1D1714');self.work._oracle_bg=self.p['bg'];self.work.pack(side='left',fill='both',expand=True)
        # Brand and group labels in the suite's rail style (oracle_shell).
        pad=shell.RAIL_PADX
        brand=tk.Label(self.rail,text='AUGURSPEX',bg=self.p['rail'],fg=C_TEXT_BRIGHT,font=shell.font('brand'),anchor='w')
        brand.pack(fill='x',padx=pad,pady=(shell.RAIL_TOP,0))
        self._rail_brand=brand
        self.rail_tagline=self._label(self.rail,'MARKETS · HISTORY','weak',anchor='w',font=shell.font('group'))
        self.rail_tagline.pack(fill='x',padx=pad,pady=(4,0))
        self._label(self.rail,'FIND MARKET','weak',anchor='w',font=shell.font('group')).pack(fill='x',padx=pad,pady=(14,6))
        self._entry(self.rail,self.search).pack(fill='x',padx=pad,pady=(0,6))
        filt=ogg_frame(self.rail,bg='#130F0D');filt._oracle_bg=self.p['rail'];filt.pack(fill='x',padx=pad-2,pady=(0,6))
        self.filters={}
        # Each category filter is lettered in the colour its rows use in the
        # list below, so the filters double as the legend (the label carries
        # the meaning; the colour only repeats it).
        for index,(text,name) in enumerate([('ALL','all'),(MARKET_LABELS['stocks'],'stocks'),
                                            (MARKET_LABELS['fx'],'fx'),(MARKET_LABELS['crypto'],'crypto'),
                                            ('★ SAVED','favorites')]):
            btn=self._button(filt,text,lambda n=name:self._set_filter(n))
            btn.configure(padx=4)
            btn.grid(row=index//3,column=index%3,padx=2,pady=2,sticky='ew')
            self.filters[name]=btn
        for column in range(3):
            filt.columnconfigure(column,weight=1,uniform='filter')
        sourcing=ogg_frame(self.rail,bg='#130F0D');sourcing._oracle_bg=self.p['rail']
        sourcing.pack(fill='x',padx=pad,pady=(0,5))
        self.sourced_button=self._button(sourcing,'SHOW ALL MARKETS',self._toggle_sourced)
        self.sourced_button.pack(side='left',fill='x',expand=True)
        self.source_count=self._label(self.rail,'VERIFYING DATA SOURCES','weak',anchor='w',font=shell.font('group'))
        self.source_count.pack(fill='x',padx=pad,pady=(4,6))
        # Keep the entire watchlist visible on the suite's compact CRT.
        # Rarely used editing controls now live in a separate MANAGE dialog.
        # HOME and the version line at the foot of the rail, as in every
        # workspace; MANAGE LIST is the list's own action, just above.
        bottom=ogg_frame(self.rail,bg='#130F0D');bottom._oracle_bg=self.p['rail']
        # Packed ahead of everything else in the rail, so a short window (or
        # Windows' taller text) shrinks the list rather than pushing HOME out.
        bottom.pack(side='bottom',fill='x',padx=pad,pady=(8,14),before=brand)
        self._button(bottom,'MANAGE LIST',self._manage_watchlist).pack(fill='x',pady=(0,6))
        self.home_button=shell.button(bottom,HOME_LABEL,self.on_home)
        self.home_button.pack(fill='x')
        self.rail_version=self._label(bottom,'MARKET HISTORY · LOCAL','weak',anchor='w',font=shell.font('small'))
        self.rail_version.pack(fill='x',pady=(8,0))
        # In a short window the tagline and version line go first, as on every tab (oracle_shell).
        self._rail_short=None
        self.rail_shell.bind('<Configure>',self._fit_rail_height,add='+')
        lst=ogg_frame(self.rail,bg='#130F0D');lst._oracle_bg=self.p['rail'];lst.pack(fill='both',expand=True,padx=pad)
        self.watch=tk.Listbox(lst,selectmode='browse',exportselection=False,
                              bg=self.p['inset'],fg=self.p['ink'],selectbackground=self.p['active'],
                              selectforeground=self.p['accent'],relief='flat',bd=0,
                              highlightthickness=1,highlightbackground=self.p['border'],
                              activestyle='none',font=(FAMILY,13,'bold'))
        self._watch_full=[]
        tooltip(self.watch,self._watch_tip)        # a shortened row shows its whole name on hover
        sb=tk.Scrollbar(lst,orient='vertical',command=self.watch.yview)
        self.watch.configure(yscrollcommand=sb.set)
        self.watch.pack(side='left',fill='both',expand=True);sb.pack(side='right',fill='y')
        self.watch.bind('<<ListboxSelect>>',lambda _e:self._choose_from_list())
        self.watch.bind('<Configure>',lambda _e:self._watch_resize(),add='+')

        # One header row: the market the selected chart shows, and the actions
        # that apply to it. The actions are packed first so they are never the
        # part that gets clipped in a narrow window; the name gives way instead.
        # The page title row of the suite shell: the selected market as the
        # title, its actions on the right.
        mx=shell.MAIN_PADX
        header=ogg_frame(self.work,bg='#1D1714');header._oracle_bg=self.p['bg']
        header.pack(fill='x',padx=mx,pady=(shell.HEADER_PADY[0],8))
        self._button(header,'REFRESH',self._force_refresh).pack(side='right',padx=(6,0))
        details=self._button(header,'SOURCE DETAILS',self._show_source_details)
        details.pack(side='right',padx=(6,0))
        # In a narrow window the caption shortens rather than push CSV off the row.
        header.bind('<Configure>',lambda e,b=details:b.configure(
            text='SOURCES' if e.width<520 else 'SOURCE DETAILS') if e.widget is header else None,add='+')
        self._button(header,'CSV',self._export_chart_csv).pack(side='right',padx=(6,0))
        self._selected_text='Choose a market'
        self.selected_market=tk.Label(header,text=self._selected_text,bg=self.p['bg'],
                                      fg=C_TEXT_BRIGHT,font=shell.font('page_title'),anchor='w')
        self.selected_market.pack(side='left',fill='x',expand=True,padx=(0,8))
        self.selected_market.bind('<Configure>',lambda _e:self._fit(self.selected_market,self._selected_text),add='+')
        # Secondary tools: a whole-watchlist comparison and an accessible
        # provider-observation table. Equal columns; the captions shorten
        # (see _reflow_tools) rather than run off the edge.
        tools=tk.Frame(self.work,bg=self.p['bg'])
        tools.pack(fill='x',padx=mx,pady=(0,6))
        self.tool_buttons=[]
        for column,(caption,short,command) in enumerate((
                ('◈ MARKET ATLAS','◈ ATLAS',self._show_market_atlas),
                ('▣ SIGNALS','▣ SIGNALS',self._show_market_signals),
                ('▤ OBSERVATION TABLE','▤ TABLE',self._show_observation_table),
                ('? SHORTCUTS','? KEYS',self._show_shortcuts))):
            button=self._button(tools,caption,command)
            button.grid(row=0,column=column,sticky='ew',padx=(0,5),pady=1)
            tools.columnconfigure(column,weight=1,uniform='augurspex-tools')
            self.tool_buttons.append((button,caption,short))
        self._tools_compact=None
        tools.bind('<Configure>',lambda e:self._reflow_tools(e.width),add='+')
        opts=ogg_frame(self.work,bg='#1D1714');opts._oracle_bg=self.p['bg'];opts.pack(fill='x',padx=mx,pady=(0,4))
        self.workspace_var=tk.StringVar(value=self.settings['workspace'])
        self.layout_var=tk.StringVar(value=str(self.settings['layout']))
        self.interval_var=tk.StringVar(value=self.settings['interval'])
        self.style_var=tk.StringVar(value='CANDLES' if self.settings['style']=='1' else 'LINE')
        self.view_bars_var=tk.StringVar(value=self.settings.get('view_bars','MAX')+' BARS')
        self.option_parts=[]
        self._option_columns=0
        for label,var,items,fn in [
            ('WORKSPACE',self.workspace_var,WORKSPACES,self._change_workspace),
            ('CHARTS',self.layout_var,tuple(map(str,LAYOUTS)),self._change_layout),
            ('PERIOD',self.interval_var,INTERVALS,self._change_interval),
            ('ALL CHARTS',self.style_var,('LINE','CANDLES'),self._change_style),
            ('VISIBLE',self.view_bars_var,('30 BARS','90 BARS','MAX BARS'),self._change_view_bars),
        ]:
            part=ogg_frame(opts,bg='#1D1714');part._oracle_bg=self.p['bg']
            self._label(part,label,'weak',font=shell.font('group')).pack(side='left',padx=(0,4))
            self._option(part,var,items,fn).pack(side='left')
            self.option_parts.append(part)
            # A menu showing a longer value (LINE -> CANDLES) grows; re-flow so
            # it never runs into its neighbour.
            part.bind('<Configure>',lambda _e:self._options_changed(),add='+')
        # The options flow left to right and wrap where the window ends, so
        # they use as few rows as the width allows and none is ever cut off.
        self.options_bar=opts
        opts.bind('<Configure>',lambda e:self._reflow_options(e.width),add='+')
        self._reflow_options(1000)  # initial geometry; updates after layout
        # Requested chart spaces vs slots with real data, always stated.
        self.count_badge=tk.Label(self.work,text='',anchor='w',bg=self.p['bg'],fg=self.p['weak'],
                                  font=shell.font('group'))
        self.count_badge.pack(fill='x',padx=mx,pady=(0,2))
        self._badge_text=''
        self.count_badge.bind('<Configure>',lambda _e:self._fit(self.count_badge,self._badge_text),add='+')
        # A 9-chart layout cannot physically fit in some embedded CRT apertures.
        # Keep all saved chart slots, give each a real minimum plot area, and
        # scroll through rows rather than reducing Tk canvases to 1x1 pixels.
        self.chart_port=tk.Frame(self.work,bg=self.p['bg'])
        self.chart_port.pack(fill='both',expand=True,padx=mx-4,pady=4)
        self.chart_canvas=tk.Canvas(self.chart_port,bg=self.p['bg'],bd=0,
                                    highlightthickness=0,width=120,height=140)
        self.chart_scroll=tk.Scrollbar(self.chart_port,orient='vertical',command=self.chart_canvas.yview)
        self.chart_canvas.configure(yscrollcommand=self.chart_scroll.set)
        self.chart_scroll.pack(side='right',fill='y')
        self.chart_canvas.pack(side='left',fill='both',expand=True)
        # Slots without real history become compact tabs here instead of
        # vanishing (0.4.8.4) or taking chart-sized space.
        self.chip_strip=tk.Frame(self.chart_port,bg=self.p['bg'])
        self.grid_frame=ogg_frame(self.chart_canvas,bg='#1D1714')
        self.grid_frame._oracle_bg=self.p['bg']
        self._grid_window=self.chart_canvas.create_window(0,0,window=self.grid_frame,anchor='nw')
        self._chart_columns=0
        self.chart_canvas.bind('<Configure>',self._resize_chart_view,add='+')
        self.grid_frame.bind('<Configure>',self._sync_chart_scrollregion,add='+')
        self.empty_notice=tk.Label(self.chart_port,bg=self.p['bg'],fg=self.p['muted'],
                                   justify='center',font=(FAMILY,14,'bold'),
                                   text='CHECKING HISTORICAL DATA SOURCES…')
        for widget in (self.chart_canvas,self.grid_frame):
            widget.bind('<MouseWheel>',self._scroll_charts,add='+')
            widget.bind('<Button-4>',self._scroll_charts,add='+')
            widget.bind('<Button-5>',self._scroll_charts,add='+')
        # One footer row: what kind of data this is, then the latest status.
        # The status line at the foot of the page, as in every workspace.
        footer=ogg_frame(self.work,bg='#1D1714');footer._oracle_bg=self.p['bg'];footer.pack(fill='x',side='bottom',padx=mx,pady=(4,10))
        footer_tag=self._label(footer,'LOCAL · NO LOGIN','accent',font=shell.font('group'))
        footer_tag.pack(side='left',padx=(0,10))
        self.status_label=tk.Label(footer,text='',anchor='w',bg=self.p['bg'],fg=self.p['muted'],font=shell.font('status'))
        self.status_label.pack(side='left',fill='x',expand=True)
        # Fitted to measured pixels: a long status was cropped on both sides.
        self.status.trace_add('write',lambda *_:self._fit(self.status_label,self.status.get()))
        self.status_label.bind('<Configure>',lambda _e:self._fit(self.status_label,self.status.get()),add='+')
        # Reserve footer/status before allocating the expandable chart grid;
        # otherwise smaller application windows can clip these controls.
        self.chart_port.pack_forget()
        self.chart_port.pack(fill='both',expand=True,padx=mx-4,pady=4)
        self._render_grid()

    def _reflow_options(self,width):
        """Flow the option groups across `width`, wrapping to a new row when one does not fit."""
        positions,height=flow_layout([(part.winfo_reqwidth(),part.winfo_reqheight()) for part in self.option_parts],
                                     width,gap_x=10,gap_y=3)
        signature=(tuple(positions),height)
        if signature==self._option_columns:return
        self._option_columns=signature
        for part,(x,y) in zip(self.option_parts,positions):
            part.place(x=x+2,y=y)
        self.options_bar.configure(height=height+2)

    def _options_changed(self):
        bar=getattr(self,'options_bar',None)
        if bar is not None and bar.winfo_width()>1:self._reflow_options(bar.winfo_width())

    def _reflow_tools(self,width):
        """Full captions when all four fit in equal columns, short ones otherwise."""
        if not self.tool_buttons:return
        measure=FontMeasure(self,self.tool_buttons[0][0].cget('font')).measure
        column=max(1,width)/len(self.tool_buttons)
        compact=any(measure(caption)+34>column for _button,caption,_short in self.tool_buttons)
        if compact==self._tools_compact:return
        self._tools_compact=compact
        for button,caption,short in self.tool_buttons:
            button.configure(text=short if compact else caption)

    def _toggle_sourced(self):
        self.sourced_only=not self.sourced_only
        self._refresh_watch()
        self._refresh_charts()

    def _valid_history(self,data):
        return bool(isinstance(data,dict) and _plotted_candles(data.get('candles') or []))

    def _eligible_sources(self,symbol,period):
        # An empty router route is definite unavailability with the present
        # credentials/configuration; an HTTP failure is *not* proof of this.
        routes=getattr(self.router,'_routes',None)
        if routes is None:return True
        try:return bool(routes(symbol,'auto',period))
        except (TypeError,ValueError):return True

    def _market_health(self,symbol,period=None):
        period=period or self.settings['interval']
        key=(symbol,period)
        data=self._data.get(key)
        day=datetime.now(timezone.utc).date()
        cached=self._health_cache.get(key)
        if cached and cached[0] is data and cached[1]==day:
            return cached[2]
        result=history_health(data,symbol,period)
        self._health_cache[key]=(data,day,result)
        return result

    def _market_verified(self,symbol,period=None):
        # A historical chart can exist even when its provider went away.
        # Only recent actual observations qualify for auto-filled sourced-only charts.
        return self._market_health(symbol,period)[0]=='recent'

    def _source_summary(self):
        period=self.settings['interval']
        verified=sum(self._market_verified(x['symbol'],period) for x in self.watchlist)
        done=sum((x['symbol'],period) in self._audit_completed or
                 (x['symbol'],period) in self._errors for x in self.watchlist)
        total=len(self.watchlist)
        pending=len(self._pending)
        busy=bool(pending or self._audit_queue)
        self._fit(self.source_count,f'{verified} WITH DATA · {"CHECKING" if busy else "CHECKED"} {done}/{total}')
        self.sourced_button.configure(text=('SHOW ALL MARKETS' if self.sourced_only else 'SHOW SOURCED ONLY'))
        self.empty_notice.configure(text=('VERIFYING HISTORICAL DATA…\n'
                                          'Charts appear after a provider returns real observations.'
                                          if pending or self._audit_queue else
                                          'NO VERIFIED MARKETS FOR THIS PERIOD\n'
                                          'Use SHOW ALL MARKETS to review unavailable tickers.'))

    def _prepare_audit(self):
        # Probe the saved watchlist conservatively, one background request at
        # a time *after* visible chart requests. Respect the router's shared
        # provider cooldowns, caching and request coalescing.
        period=self.settings['interval']
        if self.offline:return
        for entry in self.watchlist:
            symbol=entry['symbol'];key=(symbol,period)
            if key in self._audit_queued or key in self._audit_completed or key in self._pending:
                continue
            if not self._eligible_sources(symbol,period):
                self._errors.setdefault(key,'NO ELIGIBLE SOURCE WITH CURRENT PERMISSIONS')
                self._audit_completed.add(key)
                continue
            if self._market_verified(symbol,period):
                self._audit_completed.add(key)
                continue
            if key in self._errors:
                self._audit_completed.add(key)
                continue
            self._audit_queue.append(key);self._audit_queued.add(key)
        self._source_summary()

    def _audit_next(self):
        if self.offline or self._stopped or not self._visible or self._audit_active is not None:return
        # Do not exhaust independent public endpoints with nine simultaneous
        # initial scans. Chart requests retain priority.
        if self._pending:return
        while self._audit_queue:
            key=self._audit_queue.popleft();self._audit_queued.discard(key)
            if key[1]!=self.settings['interval'] or key in self._audit_completed or key in self._errors or self._market_verified(*key):continue
            self._audit_active=key
            self._request(*key)
            if key not in self._pending:self._audit_active=None
            break

    def _space_plan(self):
        """What each of the N chart spaces shows: list of (symbol, auto).

        CHARTS N always gives N chart spaces. A space shows its own saved
        market when that has real history. In sourced-only mode a space whose
        market has no data borrows the next watchlist market that does
        (favourites first), labelled AUTO-FILLED; saved slots are not changed.
        A space shows its own market's status only when no such market is left.
        """
        n=min(self.settings['layout'],len(self.cards))
        symbols=self.settings['symbols']
        if not self.sourced_only or self.offline:
            return [(symbols[i],False) for i in range(n)]
        period=self.settings['interval']
        own=[bool(symbols[i]) and self._market_verified(symbols[i],period) for i in range(n)]
        taken={symbols[i] for i in range(n) if symbols[i]}
        fav=set(self.settings.get('favorites',[]))
        ordered=sorted(self.watchlist,key=lambda row:row['symbol'] not in fav)
        spare=[row['symbol'] for row in ordered
               if row['symbol'] not in taken and self._market_verified(row['symbol'],period)]
        plan=[]
        for i in range(n):
            if own[i]:plan.append((symbols[i],False))
            elif spare:plan.append((spare.pop(0),True))
            else:plan.append((symbols[i],False))
        return plan

    def _display_slots(self):
        """(chart slots, tab slots): every requested space is a chart card."""
        n=min(self.settings['layout'],len(self.cards))
        return list(range(n)),[]

    def _chart_indices(self):
        """Spaces showing real history (their own market or an auto-filled one)."""
        period=self.settings['interval']
        return [i for i,(symbol,_auto) in enumerate(self._space_plan())
                if symbol and self._market_verified(symbol,period)]

    def chip_slots(self):
        return list(self._chip_slots)

    def _slot_status(self,i):
        symbol=self.settings['symbols'][i]
        if not symbol:return 'PICK A MARKET'
        key=(symbol,self.settings['interval'])
        if key in self._pending:return 'CHECKING…'
        health,observed=self._market_health(symbol)
        if health=='stale':return 'STALE '+observed.strftime('%Y-%m-%d')
        if health in ('undated','future'):return 'UNVERIFIED DATE'
        if health=='recent':return 'WITH DATA'
        if key in self._errors:
            text=status_for_error(self._errors[key],symbol)
            return SHORT_STATUS.get(text,text)
        if self.offline:return 'OFFLINE'
        return 'QUEUED'

    def _manage_watchlist(self):
        """Editing controls live in a small dialog rather than crushing the list."""
        dialog=tk.Toplevel(self)
        dialog.title('AUGURSPEX · MANAGE MARKETS')
        dialog.configure(bg=self.p['panel'])
        dialog.geometry('520x475')
        dialog.minsize(430,420)
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        self._label(dialog,'MANAGE WATCHLIST','accent',15,True,anchor='w').pack(fill='x',padx=18,pady=(14,8))
        self._label(dialog,'Select a market in the left list to edit or favourite it.','muted',11,
                    anchor='w').pack(fill='x',padx=18,pady=(0,8))
        self._label(dialog,'ADD TICKER (AAPL / BTC-USD / FX:EURUSD)','muted',10,True,
                    anchor='w').pack(fill='x',padx=18)
        edit=self._entry(dialog,self.symbol_input)
        edit.pack(fill='x',padx=18,pady=(4,12))
        actions=tk.Frame(dialog,bg=self.p['panel'])
        actions.pack(fill='x',padx=16)
        for caption,call in (('+ ADD',self._add_symbol),('☆ FAVOURITE',self._toggle_favorite),
                             ('REMOVE',self._remove_selected),('CLOSE',dialog.destroy)):
            self._button(actions,caption,call).pack(side='left',padx=2,expand=True,fill='x')
        opt_frame=tk.Frame(dialog,bg=self.p['panel'])
        opt_frame.pack(fill='x',padx=16,pady=(15,2))
        self._button(opt_frame,'CONNECT API KEY',self._stock_key_setup).pack(side='left',fill='x',expand=True,padx=2)
        self._button(opt_frame,'IMPORT STOCK CSV',self._import_stock_csv).pack(side='left',fill='x',expand=True,padx=2)
        self._button(dialog,'STOCK FEED GUIDE / CURRENT ROUTES',self._stock_feed_guide).pack(fill='x',padx=18,pady=(6,2))
        self._button(dialog,'OPTIONAL UNOFFICIAL STOCK ROUTES: ON / OFF',self._toggle_unofficial).pack(fill='x',padx=18,pady=(7,2))
        self._button(dialog,'REMOVE IMPORTED CSV FOR ACTIVE STOCK',self._clear_imported_csv).pack(fill='x',padx=18,pady=(2,2))
        self._label(dialog,'Stooq now needs a free key; other stock APIs usually need free keys too.','muted',10,
                    anchor='w').pack(fill='x',padx=18,pady=2)
        edit.focus_set()

    def _stock_key_setup(self):
        """Enter personal provider credentials in memory for this session.

        They are never written to Marble Oracle settings, exported or logged.
        """
        dialog=tk.Toplevel(self)
        dialog.title('AUGURSPEX · CONNECT STOCK DATA')
        dialog.configure(bg=self.p['panel'])
        dialog.geometry('560x540')
        dialog.minsize(450,500)
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        self._label(dialog,'CONNECT HISTORICAL STOCK FEEDS','accent',15,True,anchor='w').pack(
            fill='x',padx=17,pady=(12,5))
        self._label(dialog,'Keys are used only this session and are not saved in the ZIP or settings.',
                    'muted',10,anchor='w').pack(fill='x',padx=17,pady=(0,8))
        fields=[('Stooq key (US, ASX, Tokyo, indices)','AUGURSPEX_STOOQ_KEY'),
                ('EODHD key (US, ASX, Tokyo, Korea, indices)','AUGURSPEX_EODHD_KEY'),
                ('Tiingo key (US)','AUGURSPEX_TIINGO_KEY'),
                ('Twelve Data key (US on free plan)','AUGURSPEX_TWELVE_DATA_KEY'),
                ('Alpha Vantage key (US)','AUGURSPEX_ALPHA_VANTAGE_KEY'),
                ('Alpaca API key ID (US)','AUGURSPEX_ALPACA_KEY_ID'),
                ('Alpaca secret key','AUGURSPEX_ALPACA_SECRET_KEY'),
                ('data.go.kr service key (Korea)','AUGURSPEX_DATA_GO_KR_KEY')]
        entries={}
        for label,key in fields:
            row=tk.Frame(dialog,bg=self.p['panel'])
            row.pack(fill='x',padx=17,pady=3)
            self._label(row,label,'muted',10,True,anchor='w').pack(side='left',padx=(0,8))
            entry=tk.Entry(row,show='●',bg=self.p['inset'],fg=self.p['ink'],
                           insertbackground=self.p['accent'],relief='flat',width=24)
            entry.pack(side='right',fill='x',expand=True)
            entries[key]=entry
        def apply():
            count=0
            for key,entry in entries.items():
                value=entry.get().strip()
                if value:
                    os.environ[key]=value
                    count+=1
                entry.delete(0,'end')
            if count:
                # Never put credentials into UI text or exception traces.
                if hasattr(self.router,'credentials_changed'):self.router.credentials_changed()
                self._force_refresh()
                self.status.set('STOCK API CREDENTIALS ACTIVE FOR THIS SESSION · REFRESHING')
            dialog.destroy()
        actions=tk.Frame(dialog,bg=self.p['panel'])
        actions.pack(fill='x',padx=17,pady=(12,4))
        self._button(actions,'APPLY + REFRESH',apply).pack(side='left',expand=True,fill='x',padx=(0,4))
        self._button(actions,'CANCEL',dialog.destroy).pack(side='left',expand=True,fill='x')
        for help_line in ('Free keys from: eodhd.com, tiingo.com, twelvedata.com, alphavantage.co, alpaca.markets, data.go.kr',
                          'Stooq: open stooq.com/q/d/?s=aapl.us&get_apikey in a browser, pass the captcha, copy the key.'):
            help_label=self._label(dialog,help_line,'weak',9,anchor='w')
            # Two lines rather than a sentence cut off at the dialog edge.
            help_label.configure(wraplength=510,justify='left')
            help_label.pack(fill='x',padx=17,pady=3)
        self._label(dialog,'Free plans and exchange permissions vary; do not share keys in chat or screenshots.',
                    'weak',9,anchor='w').pack(fill='x',padx=17,pady=3)

    def _stock_feed_guide(self):
        routes=self.router._routes('AAPL','auto','D') if isinstance(self.router,MarketRouter) else []
        active=', '.join(str(r).upper() for r in routes) or 'NONE'
        # Never display user keys or persist them in the portable application.
        keys={
            'Stooq':'AUGURSPEX_STOOQ_KEY',
            'EODHD':'AUGURSPEX_EODHD_KEY',
            'Tiingo':'AUGURSPEX_TIINGO_KEY',
            'Twelve Data':'AUGURSPEX_TWELVE_DATA_KEY',
            'Alpaca IEX':'AUGURSPEX_ALPACA_KEY_ID + AUGURSPEX_ALPACA_SECRET_KEY',
            'Alpha Vantage':'AUGURSPEX_ALPHA_VANTAGE_KEY',
            'FMP':'AUGURSPEX_FMP_KEY',
            'Massive':'AUGURSPEX_MASSIVE_KEY',
        }
        configured=[]
        for title,env in keys.items():
            envs=env.split(' + ')
            configured.append(title+': '+('CONFIGURED' if all(os.environ.get(e,'').strip() for e in envs) else 'NO KEY'))
        messagebox.showinfo('AUGURSPEX · STOCK FEED GUIDE',
            'US stock routes presently available: '+active+'\n\n'
            'STRASMORE: documented no-key US EOD demo (500 rows / about one year).\n'
            'STOOQ: daily history for US, ASX, Tokyo and indices. Since 2026 it\n'
            'asks for a free personal key (captcha on stooq.com); without one it\n'
            'answers with a "get your key" page and the chart says KEY NEEDED.\n'
            'EODHD: free key, about one year of daily bars, 20 calls a day.\n'
            'Other stock providers need an individual account/API key.\n'
            'Use MANAGE LIST → CONNECT API KEY to enter a key temporarily,\n'
            'or set environment variables before launching Marble Oracle.\n\n'
            + '\n'.join(configured) + '\n\n'
            'Free / trial access varies. Alpaca IEX covers a single US exchange only.\n'
            'A free API key does not guarantee full exchange history.\n\n'
            'To display existing licensed historical CSV files, select a stock and\n'
            'click IMPORT STOCK CSV. Imported observations are labelled UNVERIFIED\n'
            'and are never reported as live.\n\n'
            'Optional Yahoo/Nasdaq website routes may be restricted and are not\n'
            'official open APIs; they remain user-controlled rather than default.',
            parent=self)

    def _import_stock_csv(self):
        # The active chart's true market identity is used, even after auto-fill.
        plan=self._space_plan()
        symbol=(plan[self.active][0] if self.active<len(plan) else None) or self._selected()
        if not symbol or market_category(symbol)!='stocks':
            messagebox.showinfo('AUGURSPEX · IMPORT STOCK DATA',
                'Select a stock or ETF chart first, then choose a CSV containing its actual historical prices.',
                parent=self)
            return
        location=filedialog.askopenfilename(parent=self,title=f'Import historical CSV for {symbol}',
            filetypes=[('CSV market history','*.csv')])
        if not location:return
        try:
            original=Path(location)
            if original.stat().st_size > LOCAL_IMPORT_LIMIT:
                raise ValueError('CSV exceeds 2 MB safety limit')
            validated=read_local_stock_csv(original,symbol,'D')
            directory=app_folder(self.home)/'imported-history'
            target=local_stock_path(directory,symbol)
            if target is None:raise ValueError('Invalid ticker for local import')
            directory.mkdir(parents=True,exist_ok=True,mode=0o700)
            temporary=target.with_name(target.name+'.'+str(os.getpid())+'.tmp')
            try:
                temporary.write_bytes(original.read_bytes())
                os.chmod(temporary,0o600)
                os.replace(temporary,target)
            finally:
                try:temporary.unlink()
                except FileNotFoundError:pass
            if isinstance(self.router,MarketRouter):
                self.router.import_dir=directory
            self._force_refresh()
            self.status.set(f'USER CSV IMPORT · {symbol} · {len(validated["candles"])} OBSERVATIONS · SOURCE UNVERIFIED')
        except (OSError,ValueError,TypeError) as exc:
            messagebox.showerror('AUGURSPEX · IMPORT FAILED',str(exc)[:230],parent=self)
        except Exception as exc:
            # ProviderError is a ValueError-like user input failure but does
            # not subclass ValueError. Show its safe diagnostic to the user.
            messagebox.showerror('AUGURSPEX · IMPORT FAILED',str(exc)[:230],parent=self)

    def _clear_imported_csv(self):
        plan=self._space_plan()
        symbol=(plan[self.active][0] if self.active<len(plan) else None) or self._selected()
        if not symbol or market_category(symbol)!='stocks':return
        target=local_stock_path(app_folder(self.home)/'imported-history',symbol)
        if target and target.is_file() and messagebox.askyesno('AUGURSPEX',
                f'Delete the locally imported CSV history for {symbol}?',parent=self):
            try:target.unlink()
            except OSError as exc:
                messagebox.showerror('AUGURSPEX',str(exc),parent=self)
                return
            self._force_refresh()

    def _toggle_unofficial(self):
        """Opt-in to known, explicitly labelled undocumented stock-history routes.

        Never bypass credentials, authorisation, rate limits or provider blocks.
        """
        enabled=not bool(self.settings.get('unofficial_sources',False))
        self.settings['unofficial_sources']=enabled
        if hasattr(self.router,'allow_unofficial') or isinstance(self.router,MarketRouter):
            self.router.allow_unofficial=enabled
        self._save()
        self._audit_completed.clear();self._audit_queue.clear();self._audit_queued.clear()
        self._errors.clear();self._failed_at.clear()
        self.status.set('UNOFFICIAL STOCK FALLBACK '+('ENABLED' if enabled else 'DISABLED')+
                        ' · THIS DOES NOT GUARANTEE DATA')
        self._prepare_audit();self._refresh_watch();self._refresh_charts()

    def _load_watchlist(self):
        self.watchlist,_=merge_watchlists(self.home,DEFAULT_FILE,self.settings)
        self._names={x['symbol']:x['name'] for x in self.watchlist}

    def _refresh_watch(self):
        if not hasattr(self,'watch'):return
        old=self._selected()
        term=self.search.get().strip().lower()
        filt=self.settings.get('watch_filter','all')
        fav=set(self.settings.get('favorites',[]))
        self.rows=[row for row in self.watchlist if
                   (not self.sourced_only or self.offline or self._market_verified(row['symbol'])) and
                   (filt!='favorites' or row['symbol'] in fav) and
                   (filt not in ('crypto','stocks','fx') or market_category(row['symbol'])==filt) and
                   (not term or term in (row['symbol']+' '+row['name']).lower())]
        self.watch.delete(0,'end')
        self._watch_full=[]
        self._watch_font=FontMeasure(self,(FAMILY,13,'bold')) if not hasattr(self,'_watch_font') else self._watch_font
        for i,item in enumerate(self.rows):
            tag='★ ' if item['symbol'] in fav else '  '
            kind=market_category(item['symbol'])
            display=tag+({'fx':'FX  ', 'crypto':'₿  ', 'stocks':'STK '}[kind])+item['symbol']
            if item['name'] and item['name']!=item['symbol']:
                display+='  '+item['name']
            fitted=fit_text_pixels(display,self._watch_font,max(120,self.watch.winfo_width()-16))
            self._watch_full.append(display if fitted!=display else '')
            self.watch.insert('end',fitted)
            category_colour=MARKET_COLORS[kind]
            try:self.watch.itemconfig(i,foreground=category_colour)
            except tk.TclError:pass
            if item['symbol']==old:self.watch.selection_set(i)
        self._source_summary()
        for key,button in self.filters.items():
            on=key==filt
            rest=MARKET_COLORS.get(key,self.p['ink'])
            button.configure(bg=self.p['active'] if on else self.p['control'],
                             fg=self.p['accent'] if on and key not in MARKET_COLORS else rest,
                             highlightbackground=self.p['accent'] if on else self.p['border'])

    def _watch_resize(self):
        current_width=self.watch.winfo_width()
        if current_width<50 or current_width==getattr(self,'_watch_last_width',None):return
        self._watch_last_width=current_width
        self._refresh_watch()

    def _selected_market_label(self):
        if not hasattr(self,'selected_market'):return
        index=min(self.active,len(self.settings.get('symbols',[]))-1)
        sym=self.settings['symbols'][index] if index>=0 else ''
        plan=self._space_plan() if hasattr(self,'cards') and self.cards else []
        shown,auto=plan[index] if 0<=index<len(plan) else (sym,False)
        label=self._names.get(shown,shown) if shown else 'Choose a market from the list'
        if auto:label+='  · AUTO-FILLED'
        self._selected_text=label
        self._fit(self.selected_market,label)

    def _selected(self):
        if not hasattr(self,'watch'):return None
        sel=self.watch.curselection()
        return self.rows[sel[0]]['symbol'] if sel and sel[0]<len(self.rows) else None

    def _choose_from_list(self):
        sym=self._selected()
        if sym:self.settings['symbols'][self.active]=sym;self._save();self._refresh_charts()

    def _set_filter(self,name):
        self.settings['watch_filter']=name;self._save();self._refresh_watch()

    def _toggle_favorite(self):
        sym=self._selected()
        if not sym:return
        fav=set(self.settings['favorites'])
        if sym in fav:fav.remove(sym)
        else:fav.add(sym)
        self.settings['favorites']=sorted(fav);self._save();self._refresh_watch()

    def _add_symbol(self):
        sym=self.symbol_input.get().strip().upper()
        item=clean_item({'symbol':sym,'name':sym})
        if item is None:
            self.status.set('UNRECOGNISED TICKER · include the exchange, e.g. NASDAQ:AMD')
            return
        try:
            update_watchlist(self.home,DEFAULT_FILE,self.settings,[item],mode='merge')
        except (OSError,ValueError) as exc:
            self.status.set('WATCHLIST SAVE FAILED: '+str(exc)[:100]);return
        self._load_watchlist();self.symbol_input.set('');self._refresh_watch();self._prepare_audit()
        self.settings['symbols'][self.active]=sym;self._save();self._refresh_charts()
        self.status.set('ADDED '+sym+' · SAVED LOCALLY')

    def _remove_selected(self):
        sym=self._selected()
        if not sym:return
        if not messagebox.askyesno('AUGURSPEX','Remove '+sym+' from your watchlist?',parent=self):return
        self.watchlist=[x for x in self.watchlist if x['symbol']!=sym]
        try:update_watchlist(self.home,DEFAULT_FILE,self.settings,self.watchlist,mode='replace',confirm_empty=True)
        except (OSError,ValueError) as exc:
            self._load_watchlist();self.status.set('REMOVE FAILED: '+str(exc)[:120]);return
        self.settings['favorites']=[x for x in self.settings['favorites'] if x!=sym]
        self.settings['symbols']=[x if x!=sym else '' for x in self.settings['symbols']]
        self._save();self._refresh_watch();self._refresh_charts()
        self.status.set('REMOVED '+sym+' · CHART SLOTS CLEARED')

    def _select_chart(self,i):
        self.active=i;self._refresh_charts()
        plan=self._space_plan()
        symbol=plan[i][0] if i<len(plan) else self.settings['symbols'][i]
        key=(symbol,self.settings['interval'])
        err=self._errors.get(key)
        if err:self.status.set(f'{symbol} · {err}'[:230])
        elif symbol and key in self._data:
            data=self._data[key]
            self.status.set(f"{symbol} · {data.get('source','source unknown')} · {data.get('warning') or data.get('note','')}"[:230])

    def _change_workspace(self,value):
        # The previous workspace retains its chart slots and settings.
        old=self.settings['workspace']
        self.settings['workspaces'][old]=self._snapshot()
        target=self.settings['workspaces'].get(value)
        self.settings['workspace']=value
        if target:
            for key in ('symbols','layout','interval','style','slot_styles'):
                value=target.get(key,['']*9 if key=='slot_styles' else None)
                if value is None:continue
                self.settings[key]=list(value) if key in ('symbols','slot_styles') else value
        self.layout_var.set(str(self.settings['layout']))
        self.interval_var.set(self.settings['interval'])
        self.style_var.set('CANDLES' if self.settings['style']=='1' else 'LINE')
        self.active=0;self._render_grid();self._save();self._refresh_charts()

    def _snapshot(self):
        return {key:list(self.settings.get(key) or ['']*9) if key in ('symbols','slot_styles') else self.settings[key]
                for key in ('layout','interval','style','symbols','slot_styles')}

    def _change_layout(self,value):
        self.settings['layout']=int(value);self.active=min(self.active,int(value)-1)
        self.layout_var.set(str(self.settings['layout']))
        self._render_grid();self._save();self._refresh_charts()

    def _change_interval(self,value):
        self.settings['interval']=value;self._save();self._refresh_charts();self._prepare_audit()

    def _change_view_bars(self,value):
        window=str(value).split()[0]
        if window not in ('30','90','MAX'):return
        self.settings['view_bars']=window
        self.view_bars_var.set(window+' BARS')
        self._save()
        self._refresh_charts()

    def _slot_style(self,i):
        styles=self.settings.get('slot_styles') or []
        return (styles[i] if i<len(styles) else '') or self.settings['style']

    def _set_slot_style(self,i,code):
        """Per-chart LINE/CANDLES toggle; remembered per slot and workspace."""
        styles=(list(self.settings.get('slot_styles') or [])+['']*9)[:9]
        styles[i]=code
        self.settings['slot_styles']=styles
        self._save();self._refresh_charts()

    def _change_style(self,value):
        # DISPLAY applies to every chart; per-chart choices reset to follow it.
        self.settings['style']='1' if value=='CANDLES' else '2'
        self.settings['slot_styles']=['']*9
        self._save();self._refresh_charts()

    def _save(self):
        self.settings['workspaces'][self.settings['workspace']]=self._snapshot()
        try:self.settings=save_settings(self.home,self.settings)
        except OSError as exc:self.status.set('SETTINGS NOT SAVED: '+str(exc)[:100])

    def _scroll_charts(self,event):
        if self.chart_canvas.winfo_height() < self.grid_frame.winfo_height():
            if getattr(event,'num',0)==4:delta=-2
            elif getattr(event,'num',0)==5:delta=2
            else:delta=-int(event.delta/120)*2 if event.delta else 0
            if delta:self.chart_canvas.yview_scroll(delta,'units')
        return 'break'

    def _sync_chart_scrollregion(self,_event=None):
        self.chart_canvas.configure(scrollregion=self.chart_canvas.bbox('all'))

    def _resize_chart_view(self,event=None):
        width=max(1,self.chart_canvas.winfo_width())
        height=max(1,self.chart_canvas.winfo_height())
        self.chart_canvas.itemconfigure(self._grid_window,width=width)
        if (width,height)!=self._view_size:
            self._view_size=(width,height)
            self._schedule_layout()
        self._sync_chart_scrollregion()

    def _schedule_layout(self):
        # Debounced: several <Configure> events in one geometry pass give one
        # relayout, so the grid cannot oscillate.
        if self._layout_job is None:
            try:self._layout_job=self.after_idle(self._apply_layout)
            except tk.TclError:self._layout_job=None

    def _layout_chart_cards(self,_columns=None):
        self._schedule_layout()

    def _update_count_badge(self,charts):
        n=self.settings['layout'];period=self.settings['interval']
        plan=self._space_plan()
        own=sum(1 for symbol,auto in plan if not auto and symbol and self._market_verified(symbol,period))
        auto=sum(1 for _symbol,a in plan if a)
        rest=[i for i,(symbol,a) in enumerate(plan) if not a and not (symbol and self._market_verified(symbol,period))]
        checking=sum(1 for i in rest if self._slot_status(i) in ('CHECKING…','QUEUED'))
        no_data=len(rest)-checking
        text=f'CHARTS: {n} REQUESTED · {len(plan)} SHOWN · {own} YOURS'
        if auto:text+=f' · {auto} AUTO-FILLED'
        if checking:text+=f' · {checking} CHECKING'
        if no_data:text+=f' · {no_data} NO DATA'
        if not self.sourced_only or self.offline:
            text=f'CHARTS: {n} REQUESTED · {len(plan)} SHOWN · {own} WITH DATA · ALL MARKETS MODE'
        self._badge_text=text
        self._fit(self.count_badge,text)

    def _update_chips(self,chips):
        width=max(1,self.chart_port.winfo_width())
        per_row=max(1,min(4,width//175))
        limit=per_row*2
        statuses=tuple((i,self.settings['symbols'][i],self._slot_status(i)) for i in chips)
        sig=(statuses,self.active,per_row)
        self._chip_slots=list(chips)
        if sig==self._chip_sig:return
        self._chip_sig=sig
        for child in self.chip_strip.winfo_children():child.destroy()
        self.chip_widgets=[]
        if not chips:
            self.chip_strip.pack_forget();return
        if not self.chip_strip.winfo_ismapped():
            self.chip_strip.pack(side='top',fill='x',before=self.chart_scroll,pady=(0,4))
        shown=chips if len(chips)<=limit else chips[:limit-1]
        font=(FAMILY,10,'bold')
        cell=max(60,width//per_row-10)
        for k,i in enumerate(shown):
            symbol=self.settings['symbols'][i] or 'EMPTY'
            active=i==self.active
            chip=tk.Label(self.chip_strip,text='',anchor='w',font=font,padx=6,pady=3,cursor='hand2',
                          bg=self.p['active'] if active else self.p['control'],
                          fg=self.p['accent'] if active else self.p['muted'],
                          highlightthickness=1,highlightbackground=self.p['accent'] if active else self.p['border'])
            chip.grid(row=k//per_row,column=k%per_row,sticky='ew',padx=2,pady=2)
            # The status is the point of the tab: keep it whole, shorten the name.
            status=' · '+self._slot_status(i)
            measure=FontMeasure(self,chip.cget('font'))
            room=cell-2*6-4-measure.measure(status)
            name=fit_text_pixels(f'{i+1:02d} {symbol}',measure,max(measure.measure(f'{i+1:02d}…'),room))
            self._fit(chip,name+status,cell)
            chip.bind('<Button-1>',lambda _e,n=i:self._select_chart(n))
            self.chip_widgets.append(chip)
        if len(shown)<len(chips):
            more=tk.Label(self.chip_strip,text='',anchor='w',font=font,padx=6,pady=3,cursor='hand2',
                          bg=self.p['control'],fg=self.p['accent'],highlightthickness=1,
                          highlightbackground=self.p['border'])
            k=len(shown)
            more.grid(row=k//per_row,column=k%per_row,sticky='ew',padx=2,pady=2)
            self._fit(more,f'+{len(chips)-len(shown)} MORE · SHOW ALL',cell)
            more.bind('<Button-1>',lambda _e:self._toggle_sourced())
            self.chip_widgets.append(more)
        for c in range(4):
            self.chip_strip.columnconfigure(c,weight=1 if c<per_row else 0,uniform='chips' if c<per_row else '')

    def _apply_layout(self):
        self._layout_job=None
        if self._stopped or not hasattr(self,'cards'):return
        charts,chips=self._display_slots()
        # Spaces with real history first; spaces still checking or without
        # data go to the end, so dead cards never sit between live charts.
        with_data=set(self._chart_indices())
        charts=[i for i in charts if i in with_data]+[i for i in charts if i not in with_data]
        self._update_chips(chips)
        self._update_count_badge(charts)
        width=max(1,self.chart_canvas.winfo_width())
        height=max(1,self.chart_canvas.winfo_height())
        plan=chart_grid_plan(len(charts),width,height)
        sig=(tuple(charts),plan['cols'],plan['rows'],plan['card_w'],plan['card_h'],width,height,len(self.cards))
        if sig==self._layout_sig:return
        self._layout_sig=sig
        cols=max(1,plan['cols'])
        self._chart_columns=cols
        for card in self.cards:card.grid_forget()
        for i in range(3):
            self.grid_frame.columnconfigure(i,weight=1 if i<cols else 0,minsize=0,uniform='cards' if i<cols else '')
        for i in range(9):
            self.grid_frame.rowconfigure(i,weight=0,minsize=plan['card_h']+CARD_GAP if i<plan['rows'] else 0,uniform='')
        for position,index in enumerate(charts):
            card=self.cards[index]
            card.grid(row=position//cols,column=position%cols,sticky='nsew',
                      padx=CARD_GAP//2,pady=CARD_GAP//2)
            self._bind_chart_scroll(card)
        self.chart_canvas.itemconfigure(self._grid_window,width=width,
                                        height=plan['total_h'] if charts else height)
        if charts:
            self.empty_notice.place_forget()
        else:
            self.empty_notice.place(relx=.5,rely=.6,anchor='center')
        if not plan['scroll']:self.chart_canvas.yview_moveto(0)
        self.chart_canvas.after_idle(self._sync_chart_scrollregion)

    def _bind_chart_scroll(self,widget):
        widget.bind('<MouseWheel>',self._scroll_charts,add='+')
        widget.bind('<Button-4>',self._scroll_charts,add='+')
        widget.bind('<Button-5>',self._scroll_charts,add='+')
        for child in widget.winfo_children():
            self._bind_chart_scroll(child)

    def _render_grid(self):
        for child in self.grid_frame.winfo_children():child.destroy()
        count=self.settings['layout']
        self.cards=[PriceChart(self.grid_frame,self.p,i,self._select_chart,self._set_slot_style) for i in range(count)]
        self._chart_columns=0;self._layout_sig=None;self._chip_sig=None
        self._resize_chart_view()
        self._schedule_layout()
        self.chart_canvas.yview_moveto(0)

    def _refresh_charts(self):
        self._selected_market_label()
        plan=self._space_plan()
        for i,card in enumerate(self.cards):
            symbol=self.settings['symbols'][i]
            period=self.settings['interval']
            key=(symbol,period)
            shown,auto=plan[i] if i<len(plan) else (symbol,False)
            shown_key=(shown,period)
            data=self._data.get(shown_key);error=self._errors.get(shown_key)
            if self.offline and shown and data is None and not self._has_local_stock(shown,period):error='NETWORK DISABLED'
            note=(f'slot market {symbol or "empty"}: {self._slot_status(i)}' if auto else '')
            card.display(shown,self._names.get(shown,shown),data,error,
                         shown_key in self._pending,self._slot_style(i),i==self.active,note,period,
                         self.settings.get('view_bars','MAX'))
            if symbol and data is None and error is None and key not in self._pending:
                if not self._eligible_sources(symbol,period) and not self.offline:
                    self._errors[key]='NO ELIGIBLE SOURCE WITH CURRENT PERMISSIONS'
                    self._audit_completed.add(key)
                else:self._request(symbol,period)
        self._source_summary()
        self._resize_chart_view()
        self._schedule_layout()

    def _has_local_stock(self,symbol,period):
        if period not in ('D','W','M') or market_category(symbol)!='stocks':return False
        local=local_stock_path(app_folder(self.home)/'imported-history',symbol)
        return bool(local and local.is_file() and isinstance(self.router,MarketRouter))

    def _request(self,symbol,period,force=False):
        if (self.offline and not self._has_local_stock(symbol,period)) or self._stopped or not self._visible:return
        key=(symbol,period)
        with self._lock:
            if key in self._pending:return
            self._pending.add(key)
        def work():
            try:result=self.router.fetch(symbol,period)
            except Exception as exc:self._results.put((key,None,str(exc)[:1200]))
            else:self._results.put((key,result,None))
        self._pool.submit(work)

    def _poll(self):
        self._after=None
        if self._stopped or not self._visible:return
        changed=False
        while True:
            try:key,data,error=self._results.get_nowait()
            except queue.Empty:break
            with self._lock:self._pending.discard(key)
            if self._valid_history(data):
                self._data[key]=data;self._errors.pop(key,None)
                self._failed_at.pop(key,None)
            else:
                self._errors[key]=error or 'Provider returned no usable historical observations'
                self._failed_at[key]=time.monotonic()
            self._audit_completed.add(key)
            if key==self._audit_active:self._audit_active=None
            changed=True
        # Retry failed visible charts after 15 minutes, never every refresh
        # tick. The router also honours each upstream provider's cooldown.
        if not self.offline:
            now=time.monotonic()
            for key,failed in list(self._failed_at.items()):
                if now-failed>=900:
                    self._failed_at.pop(key,None)
                    self._errors.pop(key,None)
                    self._audit_completed.discard(key)
                    changed=True
        if changed:
            self._refresh_watch()
            self._refresh_charts()
            self._prepare_audit()
        self._audit_next()
        self._after=self.after(250,self._poll)

    def _show_market_atlas(self):
        from oracle_augurspex_insights import show_market_atlas
        return show_market_atlas(self)

    def _show_observation_table(self):
        from oracle_augurspex_insights import show_observation_table
        return show_observation_table(self)

    def _show_shortcuts(self):
        messagebox.showinfo('AUGURSPEX · SHORTCUTS',
            'SELECT a chart to focus it.\n'
            'LEFT / RIGHT — inspect previous / next observation.\n'
            'HOME / END — inspect earliest / latest visible observation.\n'
            'MARKET ATLAS — inspect all watchlist data and compare percentage changes.\n'
            'OBSERVATION TABLE — keyboard-scrollable dated price records.\n'
            'CSV — export real provider observations for the selected chart.\n'
            'F1 — suite-wide field guide with six workspaces.\n\n'
            'Prices are historical; provider and exchange delays may apply.', parent=self)

    def _source_details_text(self):
        """Untruncated provider diagnosis for currently selected graph.

        Never includes URLs, API keys or arbitrary upstream HTML bodies.
        """
        index=min(self.active,len(self.cards)-1)
        if index<0:return 'No chart is visible.'
        saved=self.settings['symbols'][index]
        plan=self._space_plan()
        symbol,auto=plan[index] if index<len(plan) else (saved,False)
        period=self.settings['interval']
        if not symbol:return 'No market assigned to the selected chart.'
        key=(symbol,period)
        details=[f'Market: {symbol}', 'Name: '+self._names.get(symbol,symbol), f'Period: {period}',
                 'This screen uses historical data; not a live exchange quote.']
        if auto:
            details.append('AUTO-FILLED: current chart displays another verified market.')
            details.append('Saved target for this slot: '+(saved or '(blank)'))
        if self.offline:
            details.append('Status: network disabled for this run.')
            return '\n'.join(details)
        # Router reports its real configured order, which may include an
        # optional documented provider when a user configured credentials.
        try:
            routes=self.router._routes(symbol,'auto',period)
        except (AttributeError,ValueError):
            routes=[]
        if routes:details.append('Provider order: '+', '.join(routes))
        if hasattr(self.router,'provider_plan'):
            summary=self.router.provider_plan(symbol,period)
            if summary:
                details.append('Source alternatives (configured does NOT guarantee live access):')
                for option in summary[:8]:
                    details.append('  '+option['name']+' — '+option['status'])
        else:
            details.append('No eligible provider configured for this market and interval.')
            details.append('Optional documented sources (requires your own key and access):')
            if symbol.endswith('.AX') or symbol.startswith('ASX:'):
                details.append('  ASX: a free Stooq key (AUGURSPEX_STOOQ_KEY) or EODHD key (AUGURSPEX_EODHD_KEY); Twelve Data needs a paid plan.')
            elif symbol.endswith('.T') or symbol.startswith('TSE:'):
                details.append('  Tokyo: a free Stooq or EODHD key, or J-Quants v2 (AUGURSPEX_JQUANTS_KEY; free plan is 12 weeks delayed).')
            elif symbol.endswith(('.KS','.KQ')) or symbol.startswith(('KRX:','KOSDAQ:')):
                details.append('  Korea: data.go.kr (AUGURSPEX_DATA_GO_KR_KEY), EODHD, or the KRX approved service (AUGURSPEX_KRX_KEY).')
            elif market_category(symbol)=='fx':
                details.append('  FX: Frankfurter v2 provides keyless daily reference history (not trading quotes).')
            elif symbol.startswith('^'):
                details.append('  US indices: a free Stooq or EODHD key for daily candles; FRED (AUGURSPEX_FRED_KEY) is close only.')
            else:
                details.append('  US stocks: Massive, Alpaca IEX, Twelve Data, FMP or Alpha Vantage (personal keys required); Stooq is best-effort.')
            details.append('See Application/Documentation/MARKET_DATA.md.')
        data=self._data.get(key)
        if data:
            health,observed=self._market_health(symbol,period)
            details.append('History freshness: '+health.upper() +
                           (' · last observed '+observed.strftime('%Y-%m-%d') if observed else ' · observation date unavailable'))
            details.extend(['Source: '+str(data.get('source','not reported')),
                            'Observation: '+str(data.get('latest_observation','not reported')),
                            'Cache: '+str(data.get('cache','not reported')),
                            'Currency: '+str(data.get('currency','not reported'))])
            if data.get('aggregated_market'):details.append('PRICE TYPE: MULTI-EXCHANGE AGGREGATE (NOT A SINGLE VENUE QUOTE)')
            if data.get('note'):details.append('Note: '+str(data['note'])[:400])
            if data.get('warning'):details.append('Warning: '+str(data['warning'])[:400])
            failures=data.get('provider_attempts') or []
            if failures:
                details.append('Previous attempts:')
                details.extend('  '+str(item)[:180] for item in failures[:8])
            return '\n'.join(details)
        failed=self._errors.get(key)
        if failed:
            details.append('Status: '+status_for_error(failed,symbol))
            details.append('Source attempts:')
            details.extend('  '+s[:170] for s in str(failed).split(' | ')[:8])
            when=self._failed_at.get(key)
            if when is not None:
                remaining=max(0,round(900-(time.monotonic()-when)))
                details.append('Automatic retry in approximately '+str(remaining)+' seconds.')
        elif key in self._pending:
            details.append('Status: request in progress.')
        else:
            details.append('Status: awaiting first request or retry.')
        if market_category(symbol)=='fx':
            details.append('FX source order: Frankfurter → ECB SDMX → Bank of Canada Valet. Daily reference data; NOT live forex quotes.')
        if market_category(symbol)=='stocks':
            details.append('Manage List → STOCK FEED GUIDE gives setup/credential status.')
            details.append('Manage List → IMPORT STOCK CSV uses your actual dated data offline.')
            details.append('Strasmore no-key demo: delayed US daily bars, limited to one year/500 rows.')
            details.append('Stooq asks for a free personal key since 2026 (AUGURSPEX_STOOQ_KEY).')
            details.append('Documented additional sources require personal API keys:')
            details.append('  US: AUGURSPEX_TIINGO_KEY, AUGURSPEX_EODHD_KEY, AUGURSPEX_MASSIVE_KEY, AUGURSPEX_FMP_KEY, AUGURSPEX_ALPHA_VANTAGE_KEY')
            details.append('  US alternative: AUGURSPEX_ALPACA_KEY_ID + AUGURSPEX_ALPACA_SECRET_KEY; Twelve Data.')
            details.append('  ASX / Tokyo / indices: AUGURSPEX_STOOQ_KEY or AUGURSPEX_EODHD_KEY.')
            details.append('  Tokyo: AUGURSPEX_JQUANTS_KEY; Korea: AUGURSPEX_DATA_GO_KR_KEY or AUGURSPEX_KRX_KEY.')
        details.append('Data providers may limit requests or exchange licensing.')
        return '\n'.join(details)

    def _show_market_signals(self):
        """Calculation-only analytics: no speculative values, no extra requests."""
        from oracle_augurspex_signals import market_signal_report
        plan=self._space_plan()
        if self.active>=len(plan):return
        symbol=plan[self.active][0]
        interval=self.settings['interval']
        data=self._data.get((symbol,interval)) or {}
        summary=market_signal_report(symbol,data)
        messagebox.showinfo('AUGURSPEX · OBSERVED SIGNALS',summary,parent=self)

    def _show_source_details(self):
        messagebox.showinfo('AUGURSPEX · DATA SOURCES',
                            self._source_details_text(),parent=self)

    def _export_chart_csv(self):
        """Export only received observations for the currently displayed market.

        Unlike a rendered screenshot, CSV exposes exact dates and values.
        Never fetches on export, guesses missing fields or emits API credentials.
        """
        plan=self._space_plan()
        if self.active >= len(plan):return
        symbol=plan[self.active][0]
        data=self._data.get((symbol,self.settings['interval']))
        rows=_plotted_candles((data or {}).get('candles') or [],limit=None)
        if not rows:
            messagebox.showinfo('AUGURSPEX CSV','This chart has no valid historical observations to export.',parent=self)
            return
        safe=re.sub(r'[^A-Za-z0-9_.-]+','_',symbol)[:64]
        target=filedialog.asksaveasfilename(parent=self,title='Export AUGURSPEX historical observations',
            initialfile=f'{safe}_{self.settings["interval"]}.csv',defaultextension='.csv',
            filetypes=[('CSV historical observations','*.csv')])
        if not target:return
        try:
            with open(target,'w',newline='',encoding='utf-8') as file:
                writer=csv.writer(file)
                writer.writerow(['symbol','timestamp','open','high','low','close','volume','close_only','source','currency'])
                for row in rows:
                    writer.writerow([csv_safe(value) for value in
                                     (symbol,row.get('time',''),
                                      '' if row.get('close_only') else row.get('open',''),
                                      '' if row.get('close_only') else row.get('high',''),
                                      '' if row.get('close_only') else row.get('low',''),
                                      row.get('close',''),row.get('volume',''),
                                      bool(row.get('close_only')),data.get('source',''),data.get('currency',''))])
        except OSError as exc:
            messagebox.showerror('AUGURSPEX CSV','Export failed: '+str(exc)[:180],parent=self)
            return
        self.status.set(f'CSV EXPORTED · {symbol} · {len(rows)} REAL OBSERVATIONS')

    def _force_refresh(self):
        # Re-check failed markets, but the provider router still respects its
        # upstream TTL and cooldown. Do not discard the user's saved list.
        self._audit_completed.clear()
        self._audit_queue.clear();self._audit_queued.clear()
        for entry in self.watchlist:
            key=(entry['symbol'],self.settings['interval'])
            self._errors.pop(key,None);self._failed_at.pop(key,None)
        for key in [(s,self.settings['interval']) for s in self.settings['symbols'][:self.settings['layout']] if s]:
            self._data.pop(key,None)
        self._prepare_audit();self._refresh_charts();self.status.set('REFRESHING · PROVIDER CACHE AND RATE LIMITS APPLY')

    def retheme(self, theme):
        """Track the suite's current GRADE palette without resetting market state."""
        new=palette(theme)
        if new==self.p:return
        replacements={old:new[key] for key,old in self.p.items() if old!=new[key]}
        self.p.update(new)
        def recolor(widget):
            for field in ('background','foreground','activebackground','activeforeground',
                          'highlightbackground','insertbackground','selectbackground',
                          'selectforeground'):
                try:
                    old=widget.cget(field)
                    if old in replacements:widget.configure(**{field:replacements[old]})
                except (tk.TclError,AttributeError):pass
            if isinstance(widget, tk.OptionMenu):
                try:recolor(widget['menu'])
                except (tk.TclError,AttributeError):pass
            for child in widget.winfo_children():recolor(child)
        recolor(self)
        for card in self.cards:card.p=self.p
        self._refresh_watch();self._refresh_charts()

    def resume_panel(self):
        if self._stopped:return
        self._visible=True
        # Refresh watchlist even when changed in the companion or on HOME.
        self._load_watchlist();self._refresh_charts();self._prepare_audit();self._refresh_watch()
        if self._after is None:self._after=self.after(250,self._poll)

    def suspend(self):
        self._visible=False
        if self._after is not None:
            try:self.after_cancel(self._after)
            except tk.TclError:pass
            self._after=None

    def shutdown(self):
        self.suspend();self._stopped=True
        self._pool.shutdown(wait=False,cancel_futures=True)
        return True


class EmbeddedAugurspex:
    """Canvas-anchored frame matching the existing EmbeddedEidolith lifecycle."""
    def __init__(self,canvas,on_home,theme=None,home=None,router=None,offline=False):
        self.canvas=canvas
        self.frame=AugurspexPanel(canvas,on_home,theme=theme,home=home,router=router,offline=offline)
        self.window=canvas.create_window(0,0,anchor='nw',window=self.frame,tags=('augwin','augurspex-tab'))

    def layout(self,box):
        x0,y0,x1,y1=box
        if not self.canvas.type(self.window):
            self.window=self.canvas.create_window(0,0,anchor='nw',window=self.frame,tags=('augwin','augurspex-tab'))
        self.canvas.coords(self.window,x0,y0)
        self.canvas.itemconfigure(self.window,width=max(100,x1-x0),height=max(100,y1-y0),state='normal')
        self.canvas.tag_raise(self.window)
        self.frame.resume_panel()

    def clear(self):
        self.frame.suspend()
        if self.canvas.type(self.window):self.canvas.itemconfigure(self.window,state='hidden')

    def shutdown(self):return self.frame.shutdown()

    def key(self,keysym,char=''):
        if keysym.lower() in ('escape','esc'):return 'close'
        return None
