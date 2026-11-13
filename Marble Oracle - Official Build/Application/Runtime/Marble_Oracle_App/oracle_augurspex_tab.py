"""AUGURSPEX as a native Marble Oracle workspace (no browser/server process).

Uses AUGURSPEX's original state, watchlist validation and rate-limited public
market providers. Tk owns the UI; blocking provider calls run on worker threads.
There is no fabricated quote, alternate ticker substitution, or login.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
import queue
import threading
import time
import tkinter as tk
from tkinter import messagebox
from tkinter import font as tkfont  # noqa: F401  (kept for importers)
from oracle_ogg_texture import frame as ogg_frame, FILES as OGG_TEXTURE_FILES
from concurrent.futures import ThreadPoolExecutor
from collections import deque
from pathlib import Path

from Augurspex.augurspex.core import (
    LAYOUTS, WORKSPACES, INTERVALS, CHART_TYPES, FILTERS, read_settings,
    save_settings, merge_watchlists, update_watchlist, clean_item,
)
from Augurspex.augurspex.providers import MarketRouter, shared_market_router
from marble_uberata import FAMILY

DEFAULT_FILE = Path(__file__).resolve().parent / 'Augurspex' / 'augurspex' / 'default_watchlist.json'


def _rgb(value):
    value=str(value).strip().lstrip('#')
    try:
        return tuple(int(value[i:i+2],16) for i in (0,2,4))
    except (TypeError,ValueError):
        return (29,23,20)


def _darken(value, amount):
    return '#%02x%02x%02x' % tuple(round(v*(1-amount)) for v in _rgb(value))


def _parent_bg(widget, fallback):
    return getattr(widget,'_oracle_bg',fallback)


def palette(theme=None):
    """Darker Oggcultist-inspired base with current suite's accent colours."""
    if theme is None:
        from oggcultist_design_system import COLOR as C
        return dict(bg=_darken(C['canvas'],0.18), panel=_darken(C['raised'],0.13),
                    inset=C['sunken'], rail=_darken(C['sidebar'],0.1),
                    border=C['line'], control=C['control'], active=C['accent_soft'],
                    accent=C['accent'], ink=C['text'], muted=C['text_2'],
                    weak=C['text_3'], green=C['done'], red=C['failed'])
    return dict(bg=_darken(theme.get('bg','#1D1714'),0.18),
                panel=_darken(theme.get('panel','#261F1B'),0.12),
                inset='#16110F', rail=_darken(theme.get('panel','#130F0D'),0.24),
                border=theme.get('edge','#3A2E27'),
                control=_darken(theme.get('edge2','#2F2620'),0.10),
                active=theme.get('edge2','#4A2C18'), accent=theme.get('cyan','#FB8E22'),
                ink=theme.get('txt','#F2E8DE'), muted=theme.get('marble','#B9A99B'),
                weak=theme.get('dim','#928174'), green=theme.get('lime','#93CC7F'),
                red=theme.get('red','#FF6A55'))


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


def fit_text_pixels(text, font, max_width):
    """Fit a single line in measured pixels; preserve recognisable ticker prefixes.

    Tk label and list rows never truncate blindly by character count, since
    Uberata Clear has variable-width glyphs and can change with font scaling.
    """
    text=str(text or '')
    if max_width<=0:return ''
    if font.measure(text)<=max_width:return text
    ellipsis='…'
    if font.measure(ellipsis)>max_width:return ''
    low,high=0,len(text)
    while low<high:
        mid=(low+high+1)//2
        if font.measure(text[:mid]+ellipsis)<=max_width:low=mid
        else:high=mid-1
    return text[:low].rstrip()+ellipsis


def chart_geometry(n):
    """Stable grid dimensions, suited to the narrow CRT viewport."""
    return {1:(1,1),2:(1,2),4:(2,2),6:(2,3),9:(3,3)}[n]


# Chart grid geometry (0.4.8.5). One chart fills the chart area; more charts
# share it; vertical scrolling is used only when the legible minimum card size
# cannot fit. Kept free of Tk so it can be tested directly.
CARD_GAP = 12
MIN_CARD_W, MIN_CARD_H = 360, 280
CARD_CHROME_W, CARD_CHROME_H = 100, 160   # header, info strip and axes inside a card


def chart_grid_plan(count, view_w, view_h):
    """Columns, rows and card size for `count` charts in a view_w x view_h area."""
    count = max(0, int(count))
    view_w, view_h = max(1, int(view_w)), max(1, int(view_h))
    if count == 0:
        return dict(cols=0, rows=0, card_w=0, card_h=0, scroll=False, total_h=view_h)
    best = None
    for cols in range(1, min(3, count) + 1):
        rows = -(-count // cols)
        card_w = view_w // cols - CARD_GAP
        if cols > 1 and card_w < MIN_CARD_W:
            continue
        fit_h = view_h // rows - CARD_GAP
        scroll = fit_h < MIN_CARD_H
        card_h = max(MIN_CARD_H, fit_h)
        # Charts are time series: score the drawable plot, valuing width up to
        # about twice the height, so 2 charts sit side by side when roomy.
        score = min(card_w - CARD_CHROME_W, 2.2 * (card_h - CARD_CHROME_H))
        # Prefer no scrolling; then the larger plot (or, when scrolling, fewer
        # rows); then an even grid (4 -> 2x2, not 3+1); then fewer columns.
        key = (0 if scroll else 1, -rows if scroll else score, count % cols == 0, -cols)
        if best is None or key > best[0]:
            best = (key, dict(cols=cols, rows=rows, card_w=max(1, card_w), card_h=card_h, scroll=scroll,
                              total_h=max(view_h, rows * (card_h + CARD_GAP))))
    return best[1]


SHORT_STATUS = {'DATA SOURCE LIMITED': 'LIMITED', 'NETWORK ISSUE': 'NETWORK',
                'LISTING NOT SUPPORTED': 'UNSUPPORTED', 'NO HISTORY FROM PROVIDER': 'NO HISTORY',
                'MARKET DATA UNAVAILABLE': 'UNAVAILABLE', 'DATA SOURCE SETUP NEEDED': 'NEEDS SETUP',
                'NETWORK DISABLED': 'OFFLINE', 'AWAITING DATA': 'WAITING'}


# Reserve a real date axis along the bottom and price tick labels on the
# right. The same geometry is used by the candles/lines, ticks and grid.
CHART_PAD_L, CHART_PAD_T, CHART_PAD_R, CHART_PAD_B = 13, 16, 74, 51


def _plotted_candles(candles):
    valid=[]
    for row in candles[-120:]:
        if not isinstance(row, dict):continue
        try:
            o,h,l,cl=(float(row[x]) for x in ('open','high','low','close'))
            if not all(math.isfinite(x) and x >= 0 for x in (o,h,l,cl)):continue
            if h < max(o,cl) or l > min(o,cl):continue
        except (KeyError,TypeError,ValueError):continue
        valid.append(row)
    return valid


def plot_points(candles, width, height, style='1'):
    """Scale real provider values into the chart viewport, retaining API shape."""
    bars=_plotted_candles(candles)
    if not bars:return [], None
    lo=min(float(v['low']) for v in bars)
    hi=max(float(v['high']) for v in bars)
    if hi==lo:
        hi+=max(hi*.01,.01)
        lo=max(0,lo-max(lo*.01,.01))
    w=max(1,width-CHART_PAD_L-CHART_PAD_R)
    h=max(1,height-CHART_PAD_T-CHART_PAD_B)
    points=[]
    for i,row in enumerate(bars):
        x=CHART_PAD_L+(i+.5)*w/len(bars)
        def yy(v):return CHART_PAD_T+(hi-float(v))*h/(hi-lo)
        points.append((x,yy(row['open']),yy(row['high']),yy(row['low']),yy(row['close'])))
    return points,(lo,hi)


def chart_date_ticks(candles, width, max_ticks=5):
    """Choose spaced, truthful date labels from provider timestamp strings.

    Narrow multi-chart panels show fewer dates; ranges crossing years include
    the year. No clock-derived or synthesized dates are displayed.
    """
    bars=_plotted_candles(candles)
    if not bars:return []
    dated=[]
    for i,row in enumerate(bars):
        raw=str(row.get('time') or '').strip()
        try:moment=datetime.fromisoformat(raw.replace('Z','+00:00'))
        except (ValueError,OverflowError):continue
        dated.append((i,moment))
    if not dated:return []
    span=(dated[-1][1]-dated[0][1]).total_seconds()/86400
    if span<1:
        fmt='%d %b %H:%M'
    elif span<75:
        fmt='%d %b'
    elif span<900:
        fmt="%b '%y"
    else:
        fmt='%Y'
    # Do not crowd the labels on 2x3 or 3x3 cards.
    count=min(max_ticks,len(dated),max(2,int(max(0,width-CHART_PAD_R)/82)))
    picks=sorted(set(round(k*(len(dated)-1)/(count-1)) for k in range(count))) if count>1 else [0]
    w=max(1,width-CHART_PAD_L-CHART_PAD_R)
    ticks=[]
    for j in picks:
        i,moment=dated[j]
        x=CHART_PAD_L+(i+.5)*w/len(bars)
        label=moment.strftime(fmt).upper()
        if ticks and ticks[-1][1]==label:continue
        ticks.append((x,label))
    return ticks


def chart_display_bars(candles, width, style='1'):
    """Show recent *real* OHLC bars at a readable density on small cards.

    Candle mode limits the visible window rather than synthesising or averaging
    quotes. The date axis and prices use precisely the same visible records.
    Line mode retains the full available history.
    """
    bars=_plotted_candles(candles)
    if style != '1' or any(bar.get('close_only') for bar in bars):
        return bars
    plot_width=max(1,width-CHART_PAD_L-CHART_PAD_R)
    max_bars=max(8,int(plot_width//6.0))
    return bars[-max_bars:]


def _blend(colour, other, fraction):
    a=_rgb(colour);b=_rgb(other)
    return '#%02x%02x%02x' % tuple(round(a[i]*(1-fraction)+b[i]*fraction) for i in range(3))


def format_price(value):
    """Right-axis price labels preserve useful decimals for low-price assets."""
    v=float(value)
    if abs(v)>=1000:return f'{v:,.0f}'
    if abs(v)>=10:return f'{v:,.2f}'
    if abs(v)>=1:return f'{v:,.3f}'
    return f'{v:,.4f}'


class PriceChart(tk.Frame):
    """A chart card, rendered entirely by Tk Canvas in the suite palette."""
    def __init__(self, master, colours, index, click, on_style=None):
        self.p=colours;self.index=index;self.symbol='';self.name='';self.result=None
        self.on_style=on_style
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
        self.info.configure(text=fit_text_pixels(self._info_text,self._info_font,width))

    def _message_for_error(self, error):
        text=str(error or '').lower()
        if not text:return 'AWAITING DATA'
        if 'network disabled' in text:return 'NETWORK DISABLED'
        if 'no eligible provider' in text:return 'DATA SOURCE SETUP NEEDED'
        # Composite errors include every attempted public source. A 429 or
        # network failure from the last source is more informative than an
        # earlier Stooq N/D and should not be hidden under NO HISTORY.
        if ('http 429' in text or 'http 403' in text or 'cooling down' in text
                or 'quota' in text or 'html challenge' in text or 'rate or plan limit' in text):
            return 'DATA SOURCE LIMITED'
        if ('network problem' in text or 'name resolution' in text
                or 'timeout' in text or 'temporary failure' in text):
            return 'NETWORK ISSUE'
        if ('mapping unavailable' in text or 'supports this market' in text
                or 'requires a 6-digit korean listing' in text):
            return 'LISTING NOT SUPPORTED'
        if ('no usable candles' in text or 'no ohlc' in text or 'no csv' in text
                or 'returned no history' in text or 'returned no candles' in text):
            return 'NO HISTORY FROM PROVIDER'
        return 'MARKET DATA UNAVAILABLE'

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
        if not error:return ''
        pieces=[]
        for raw in str(error).split(' | '):
            prefix,sep,rest=raw.partition(':')
            if not sep:continue
            name=prefix.strip().upper()
            if name not in ('YAHOO','NASDAQ','STOOQ','NAVER','ALPHA','TWELVE','COINBASE','KRAKEN',
                            'MASSIVE','JQUANTS','KRX','FRED','COINGECKO','COINPAPRIKA'):
                continue
            low=rest.lower()
            if any(tag in low for tag in ('http 429','http 403','quota','cooling down','plan limit')):
                status='LIMITED'
            elif 'network problem' in low or 'timeout' in low or 'name resolution' in low:
                status='NETWORK'
            elif ('mapping unavailable' in low or 'unsupported' in low
                  or 'subscription' in low or 'entitlement' in low):
                status='UNSUPPORTED/PLAN'
            elif 'no history' in low or 'no csv' in low or 'no usable candles' in low or 'no candles' in low:
                status='NO HISTORY'
            else:
                status='ERROR'
            pieces.append(name+' '+status)
        return ' · '.join(pieces[:5])

    def display(self,symbol,name,data,error,loading,style,selected,auto_note=''):
        self.symbol=symbol;self.name=name;self.result=data;self.error=error;self.auto_note=auto_note
        self.loading=loading;self.style=style;self.selected=selected
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
            last=candles[-1]['close'];first=candles[0]['close'];change=((last/first)-1)*100 if first else 0
            self.price.configure(text=f'{last:,.4f}' if last<1 else f'{last:,.2f}',
                                 fg=self.p['green'] if change>=0 else self.p['red'])
            src=data.get('source','');cur=data.get('currency','');obs=data.get('latest_observation','')[:10]
            self._info_text=(f'{src} · {cur} · {obs} · {change:+.2f}%'
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
        width,height=max(40,c.winfo_width()),max(40,c.winfo_height())
        self._draw_texture(width,height)
        candles=(self.result or {}).get('candles',[])
        # Draw the latest *real* observations at a minimum useful candle width.
        # Never manufacture OHLC values, compress dates or rename intervals.
        close_only=any(row.get('close_only') for row in _plotted_candles(candles))
        render_as_candles=self.style=='1' and not close_only
        display_style='1' if render_as_candles else '2'
        visible=chart_display_bars(candles,width,display_style)
        points,bounds=plot_points(visible,width,height,display_style)
        if not points:
            txt=('NO MARKET SELECTED' if not self.symbol else
                 self._message_for_error(self.error) if self.error else
                 'LOADING' if self.loading else 'AWAITING DATA')
            c.create_text(width/2,height/2,text=txt,fill=self.p['muted'],font=(FAMILY,12,'bold'))
            return
        mn,mx=bounds
        plot_right=max(CHART_PAD_L+1,width-CHART_PAD_R)
        plot_bottom=max(CHART_PAD_T+1,height-CHART_PAD_B)
        grid_minor=_blend(self.p['inset'],self.p['muted'],0.26)
        grid_major=_blend(self.p['inset'],self.p['muted'],0.49)
        graph_outline=_blend(self.p['inset'],'#000000',0.70)
        # Clear rectangle outline and vertical guides make trends readable
        # without competing with the chart or its axis labels.
        c.create_rectangle(CHART_PAD_L,CHART_PAD_T,plot_right,plot_bottom,
                           outline=grid_major,width=1.2,tags=('plot-frame',))
        tick_count=5 if height>=250 else 4 if height>=180 else 3
        axis_size=11 if width>=370 else 9
        for k in range(tick_count):
            f=k/(tick_count-1)
            yy=CHART_PAD_T+(plot_bottom-CHART_PAD_T)*f
            price=mx-(mx-mn)*f
            c.create_line(CHART_PAD_L,yy,plot_right,yy,
                          fill=grid_major if k in (0,tick_count-1) else grid_minor,
                          dash=() if k in (0,tick_count-1) else (3,4),
                          width=1.2 if k in (0,tick_count-1) else 1,
                          tags=('chart-grid','horizontal-grid'))
            c.create_line(plot_right,yy,plot_right+5,yy,
                          fill=grid_major,width=1.3)
            c.create_text(plot_right+8,yy,text=format_price(price),
                          fill=self.p['ink'],font=(FAMILY,axis_size,'bold'),anchor='w')
        dates=chart_date_ticks(visible,width)
        for j,(x,label) in enumerate(dates):
            if j not in (0,len(dates)-1):
                c.create_line(x,CHART_PAD_T,x,plot_bottom,
                              fill=grid_minor,dash=(3,5),width=1.1,
                              tags=('chart-grid','vertical-grid'))
            c.create_line(x,plot_bottom,x,plot_bottom+5,fill=grid_major,width=1.3)
            anchor=('nw' if j==0 else 'ne' if j==len(dates)-1 else 'n')
            c.create_text(x,plot_bottom+8,text=label,anchor=anchor,
                          fill=self.p['ink'],font=(FAMILY,axis_size,'bold'))
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
        count=len(_plotted_candles(candles))
        note=('CLOSE-ONLY HISTORY · line chart' if close_only else
              f'LAST {len(points)} OF {count} REAL BARS' if len(points)<count else
              f'{count} observations · historical / provider delay')
        # In compact cards, an extra note beneath the date axis would
        # collide with both date labels and the card's source/status footer.
        # The full note remains available on larger canvas sizes.
        if height >= 180:
            c.create_text(CHART_PAD_L,height-3,text=note,
                          fill=self.p['muted'],font=(FAMILY,10),anchor='sw')


class AugurspexPanel(tk.Frame):
    """Full featured, native watchlist/multi-chart AUGURSPEX tab."""
    def __init__(self,master,on_home,theme=None,home=None,router=None,offline=False):
        self.p=palette(theme);self.home=Path(home) if home else Path.home()
        self.on_home=on_home;self.offline=offline
        self.router=router if router is not None else shared_market_router(self.home/'.cache/augurspex/market')
        self.settings=read_settings(self.home)
        self.watchlist=[];self.rows=[];self.active=0;self.cards=[];self._visible=False
        self._errors={};self._data={};self._requests={};self._pending=set();self._failed_at={}
        # Only charts with real returned observations are shown by default.
        # We never remove a user's saved selections on a transient outage.
        self.sourced_only=not offline
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
        self.status=tk.StringVar(value='MULTI-SOURCE HISTORY · LICENSED STOCK DATA MAY REQUIRE A PERSONAL API KEY')
        self._build_ui()
        self._refresh_watch();self._refresh_charts()

    def _label(self,parent,text,fg='ink',size=10,bold=False,**kw):
        return tk.Label(parent,text=text,bg=_parent_bg(parent,self.p['bg']),fg=self.p[fg],
                        font=(FAMILY,size,'bold' if bold else 'normal'),**kw)

    def _button(self,parent,text,callback,active=False):
        return tk.Button(parent,text=text,command=callback,relief='flat',bd=0,cursor='hand2',
                         bg=self.p['active'] if active else self.p['control'],
                         activebackground=self.p['active'],activeforeground=self.p['ink'],
                         fg=self.p['accent'] if active else self.p['ink'],
                         highlightthickness=1,highlightbackground=self.p['border'],
                         font=(FAMILY,11,'bold'),padx=9,pady=6)

    def _entry(self,parent,variable):
        return tk.Entry(parent,textvariable=variable,relief='flat',bd=0,
                        bg=self.p['inset'],fg=self.p['ink'],insertbackground=self.p['accent'],
                        highlightthickness=1,highlightbackground=self.p['border'],font=(FAMILY,12))

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

    def _build_ui(self):
        # Native layout matches the palette and proportions of EIDOLITH/Oggcultist.
        # A *Tk* shell holds the rail width. The textured ttk child alone
        # may collapse to a tiny image-element width on some Linux Tk themes.
        self.rail_shell=tk.Frame(self,bg=self.p['rail'],width=292)
        self.rail_shell.pack(side='left',fill='y')
        self.rail_shell.pack_propagate(False)
        self.rail=ogg_frame(self.rail_shell,bg='#130F0D')
        self.rail._oracle_bg=self.p['rail']
        self.rail.pack(fill='both',expand=True)
        tk.Frame(self,bg=self.p['border'],width=1).pack(side='left',fill='y')
        self.work=ogg_frame(self,bg='#1D1714');self.work._oracle_bg=self.p['bg'];self.work.pack(side='left',fill='both',expand=True)
        self._label(self.rail,'AUGURSPEX','accent',19,True,anchor='w').pack(fill='x',padx=12,pady=(12,1))
        self._label(self.rail,'MARKET OBSERVATORY','muted',11,anchor='w').pack(fill='x',padx=12,pady=(0,12))
        self._label(self.rail,'FIND MARKET','muted',11,True,anchor='w').pack(fill='x',padx=12)
        self._entry(self.rail,self.search).pack(fill='x',padx=12,pady=(2,5))
        filt=ogg_frame(self.rail,bg='#130F0D');filt._oracle_bg=self.p['rail'];filt.pack(fill='x',padx=10,pady=(0,6))
        self.filters={}
        for text,name in [('ALL','all'),('★','favorites'),('₿','crypto'),('STK','stocks')]:
            btn=self._button(filt,text,lambda n=name:self._set_filter(n));btn.pack(side='left',padx=1,expand=True,fill='x')
            self.filters[name]=btn
        sourcing=ogg_frame(self.rail,bg='#130F0D');sourcing._oracle_bg=self.p['rail']
        sourcing.pack(fill='x',padx=10,pady=(0,5))
        self.sourced_button=self._button(sourcing,'SHOW ALL MARKETS',self._toggle_sourced)
        self.sourced_button.pack(side='left',fill='x',expand=True)
        self.source_count=self._label(self.rail,'VERIFYING DATA SOURCES','muted',10,True,anchor='w')
        self.source_count.pack(fill='x',padx=11,pady=(0,5))
        # Bottom controls are packed first so they remain visible in the CRT's
        # shallow aperture. The watchlist alone shrinks/scrolls as necessary.
        bottom=ogg_frame(self.rail,bg='#130F0D');bottom._oracle_bg=self.p['rail']
        bottom.pack(side='bottom',fill='x',padx=10,pady=(3,6))
        self._button(bottom,'BACK TO HOME',self.on_home).pack(side='bottom',fill='x',pady=(4,0))
        self._label(bottom,'e.g. RMD.AX / NASDAQ:AMD','muted',10,anchor='w').pack(side='bottom',fill='x',pady=(2,0))
        self._button(bottom,'+ ADD TICKER',self._add_symbol).pack(side='bottom',fill='x',pady=(3,0))
        self._entry(bottom,self.symbol_input).pack(side='bottom',fill='x',pady=(3,0))
        watch_act=ogg_frame(bottom,bg='#130F0D');watch_act._oracle_bg=self.p['rail'];watch_act.pack(side='bottom',fill='x',pady=(3,3))
        self._button(watch_act,'☆ FAVOURITE',self._toggle_favorite).pack(side='left',expand=True,fill='x',padx=1)
        self._button(watch_act,'REMOVE',self._remove_selected).pack(side='left',expand=True,fill='x',padx=1)
        lst=ogg_frame(self.rail,bg='#130F0D');lst._oracle_bg=self.p['rail'];lst.pack(fill='both',expand=True,padx=10)
        self.watch=tk.Listbox(lst,selectmode='browse',exportselection=False,
                              bg=self.p['inset'],fg=self.p['ink'],selectbackground=self.p['active'],
                              selectforeground=self.p['accent'],relief='flat',bd=0,
                              highlightthickness=1,highlightbackground=self.p['border'],
                              activestyle='none',font=(FAMILY,13,'bold'))
        sb=tk.Scrollbar(lst,orient='vertical',command=self.watch.yview)
        self.watch.configure(yscrollcommand=sb.set)
        self.watch.pack(side='left',fill='both',expand=True);sb.pack(side='right',fill='y')
        self.watch.bind('<<ListboxSelect>>',lambda _e:self._choose_from_list())
        self.watch.bind('<Configure>',lambda _e:self._watch_resize(),add='+')

        header=ogg_frame(self.work,bg='#261F1B');header._oracle_bg=self.p['panel'];header.pack(fill='x',padx=8,pady=(8,4))
        self._label(header,'MARKET CHARTS','ink',16,True).pack(side='left',padx=8,pady=5)
        self._button(header,'REFRESH',self._force_refresh).pack(side='right',padx=4)
        self._button(header,'SOURCE DETAILS',self._show_source_details).pack(side='right',padx=4)
        selected_box=ogg_frame(self.work,bg='#261F1B')
        selected_box._oracle_bg=self.p['panel']
        selected_box.pack(fill='x',padx=10,pady=(0,5))
        self._label(selected_box,'ACTIVE CHART MARKET','muted',10,True,anchor='w').pack(fill='x')
        self.selected_market=tk.Label(selected_box,text='Choose a market',bg=self.p['panel'],
                                      fg=self.p['ink'],font=(FAMILY,12,'bold'),anchor='w',
                                      wraplength=660,justify='left')
        self.selected_market.pack(fill='x',pady=(3,0))
        selected_box.bind('<Configure>',lambda e:self.selected_market.configure(wraplength=max(160,e.width-8)),add='+')
        opts=ogg_frame(self.work,bg='#1D1714');opts._oracle_bg=self.p['bg'];opts.pack(fill='x',padx=8,pady=(0,4))
        self.workspace_var=tk.StringVar(value=self.settings['workspace'])
        self.layout_var=tk.StringVar(value=str(self.settings['layout']))
        self.interval_var=tk.StringVar(value=self.settings['interval'])
        self.style_var=tk.StringVar(value='CANDLES' if self.settings['style']=='1' else 'LINE')
        self.option_parts=[]
        self._option_columns=0
        for label,var,items,fn in [
            ('WORKSPACE',self.workspace_var,WORKSPACES,self._change_workspace),
            ('CHARTS',self.layout_var,tuple(map(str,LAYOUTS)),self._change_layout),
            ('PERIOD',self.interval_var,INTERVALS,self._change_interval),
            ('ALL CHARTS',self.style_var,('LINE','CANDLES'),self._change_style),
        ]:
            part=ogg_frame(opts,bg='#1D1714');part._oracle_bg=self.p['bg']
            self._label(part,label,'muted',11,True).pack(side='left',padx=(0,3))
            self._option(part,var,items,fn).pack(side='left')
            self.option_parts.append(part)
        # At narrow widths, two compact rows keep the DISPLAY option visible
        # instead of losing it behind the right side of the CRT viewport.
        opts.bind('<Configure>',lambda e:self._reflow_options(e.width),add='+')
        self._reflow_options(1000)  # initial geometry; updates after layout
        # Requested chart spaces vs slots with real data, always stated.
        self.count_badge=tk.Label(self.work,text='',anchor='w',bg=self.p['bg'],fg=self.p['muted'],
                                  font=(FAMILY,10,'bold'))
        self.count_badge.pack(fill='x',padx=12,pady=(0,2))
        self._badge_text=''
        self.count_badge.bind('<Configure>',lambda _e:self._fit(self.count_badge,self._badge_text),add='+')
        # A 9-chart layout cannot physically fit in some embedded CRT apertures.
        # Keep all saved chart slots, give each a real minimum plot area, and
        # scroll through rows rather than reducing Tk canvases to 1x1 pixels.
        self.chart_port=tk.Frame(self.work,bg=self.p['bg'])
        self.chart_port.pack(fill='both',expand=True,padx=8,pady=4)
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
        footer=ogg_frame(self.work,bg='#261F1B');footer._oracle_bg=self.p['panel'];footer.pack(fill='x',side='bottom',padx=8,pady=(0,7))
        footer_tag=self._label(footer,'LOCAL · NO LOGIN', 'accent',11,True)
        footer_tag.pack(side='left',padx=8,pady=5)
        self.footer_note=self._label(footer,'', 'muted',10,anchor='w')
        self.footer_note.pack(side='left',padx=4,fill='x',expand=True)
        footer_text='STOCKS: DELAYED / EOD · CRYPTO: VENUE PRICES · SEE SOURCE DETAILS'
        footer.bind('<Configure>',lambda e:self._fit(self.footer_note,footer_text,
                    e.width-footer_tag.winfo_reqwidth()-32),add='+')
        status_row=ogg_frame(self.work,bg='#1D1714');status_row._oracle_bg=self.p['bg']
        status_row.pack(side='bottom',fill='x',padx=11,pady=2)
        self.status_label=tk.Label(status_row,text='',anchor='w',bg=self.p['bg'],fg=self.p['weak'],font=(FAMILY,11))
        self.status_label.pack(fill='x')
        # Fitted to measured pixels: a long status was cropped on both sides.
        self.status.trace_add('write',lambda *_:self._fit(self.status_label,self.status.get()))
        self.status_label.bind('<Configure>',lambda _e:self._fit(self.status_label,self.status.get()),add='+')
        # Reserve footer/status before allocating the expandable chart grid;
        # otherwise smaller application windows can clip these controls.
        self.chart_port.pack_forget()
        self.chart_port.pack(fill='both',expand=True,padx=8,pady=4)
        self._render_grid()

    def _reflow_options(self,width):
        columns=4 if width>=850 else 2 if width>=440 else 1
        if columns==self._option_columns:return
        self._option_columns=columns
        for i,part in enumerate(self.option_parts):
            part.grid_forget()
            part.grid(row=i//columns,column=i%columns,sticky='w',
                      padx=(2,8),pady=(0,2))

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

    def _market_verified(self,symbol,period=None):
        return self._valid_history(self._data.get((symbol,period or self.settings['interval'])))

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
        if key in self._errors:
            text=PriceChart._message_for_error(None,self._errors[key])
            return SHORT_STATUS.get(text,text)
        if self.offline:return 'OFFLINE'
        return 'QUEUED'

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
                   (filt!='crypto' or row['symbol'].endswith('-USD')) and
                   (filt!='stocks' or not row['symbol'].endswith('-USD')) and
                   (not term or term in (row['symbol']+' '+row['name']).lower())]
        self.watch.delete(0,'end')
        self._watch_font=FontMeasure(self,(FAMILY,13,'bold')) if not hasattr(self,'_watch_font') else self._watch_font
        for i,item in enumerate(self.rows):
            tag='★ ' if item['symbol'] in fav else '  '
            display=tag+item['symbol']
            if item['name'] and item['name']!=item['symbol']:
                display+='  '+item['name']
            display=fit_text_pixels(display,self._watch_font,max(120,self.watch.winfo_width()-16))
            self.watch.insert('end',display)
            if item['symbol']==old:self.watch.selection_set(i)
        self._source_summary()
        for key,button in self.filters.items():
            on=key==filt
            button.configure(bg=self.p['active'] if on else self.p['control'],
                             fg=self.p['accent'] if on else self.p['ink'])

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
        self.selected_market.configure(text=label)

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
            if self.offline and shown and data is None:error='NETWORK DISABLED'
            note=(f'slot market {symbol or "empty"}: {self._slot_status(i)}' if auto else '')
            card.display(shown,self._names.get(shown,shown),data,error,
                         shown_key in self._pending,self._slot_style(i),i==self.active,note)
            if symbol and data is None and error is None and key not in self._pending:
                if not self._eligible_sources(symbol,period) and not self.offline:
                    self._errors[key]='NO ELIGIBLE SOURCE WITH CURRENT PERMISSIONS'
                    self._audit_completed.add(key)
                else:self._request(symbol,period)
        self._source_summary()
        self._resize_chart_view()
        self._schedule_layout()

    def _request(self,symbol,period,force=False):
        if self.offline or self._stopped or not self._visible:return
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

    def _source_details_text(self):
        """Untruncated provider diagnosis for currently selected graph.

        Never includes URLs, API keys or arbitrary upstream HTML bodies.
        """
        index=min(self.active,len(self.cards)-1)
        if index<0:return 'No chart is visible.'
        symbol=self.settings['symbols'][index]
        period=self.settings['interval']
        if not symbol:return 'No market assigned to the selected chart.'
        key=(symbol,period)
        details=[f'Market: {symbol}', 'Name: '+self._names.get(symbol,symbol), f'Period: {period}',
                 'This screen uses historical data; not a live exchange quote.']
        if self.offline:
            details.append('Status: network disabled for this run.')
            return '\n'.join(details)
        # Router reports its real configured order, which may include an
        # optional documented provider when a user configured credentials.
        try:
            routes=self.router._routes(symbol,'auto',period)
        except (AttributeError,ValueError) as exc:
            routes=[]
        if routes:details.append('Provider order: '+', '.join(routes))
        else:
            details.append('No eligible provider configured for this market and interval.')
            details.append('Optional documented sources (requires your own key and access):')
            if symbol.endswith('.AX') or symbol.startswith('ASX:'):
                details.append('  ASX: Twelve Data with appropriate XASX entitlement; free unrestricted ASX history is not available.')
            elif symbol.endswith('.T') or symbol.startswith('TSE:'):
                details.append('  Tokyo: J-Quants v2 (AUGURSPEX_JQUANTS_KEY) or Twelve Data with exchange access.')
            elif symbol.endswith(('.KS','.KQ')) or symbol.startswith(('KRX:','KOSDAQ:')):
                details.append('  Korea: KRX approved service (AUGURSPEX_KRX_KEY) or Twelve Data with access.')
            elif symbol.startswith('^'):
                details.append('  US index closes: FRED (AUGURSPEX_FRED_KEY), daily close only.')
            else:
                details.append('  US stocks: Alpha Vantage, Massive or Twelve Data (API key required).')
            details.append('See Application/Documentation/AUGURSPEX_PROVIDER_RESEARCH_IMPLEMENTATION_0.4.8.2.md.')
        data=self._data.get(key)
        if data:
            details.extend(['Source: '+str(data.get('source','not reported')),
                            'Observation: '+str(data.get('latest_observation','not reported')),
                            'Cache: '+str(data.get('cache','not reported')),
                            'Currency: '+str(data.get('currency','not reported'))])
            if data.get('aggregated_market'):details.append('PRICE TYPE: AGGREGATED MULTI-EXCHANGE CLOSES (NOT VENUE OHLC)')
            if data.get('note'):details.append('Note: '+str(data['note'])[:400])
            if data.get('warning'):details.append('Warning: '+str(data['warning'])[:400])
            failures=data.get('provider_attempts') or []
            if failures:
                details.append('Previous attempts:')
                details.extend('  '+str(item)[:180] for item in failures[:8])
            return '\n'.join(details)
        failed=self._errors.get(key)
        if failed:
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
        if not (symbol in ('BTC-USD','ETH-USD','SOL-USD','XRP-USD')):
            details.append('Documented additional sources require personal API keys:')
            details.append('  US: AUGURSPEX_ALPHA_VANTAGE_KEY or AUGURSPEX_MASSIVE_KEY')
            details.append('  Other supported exchanges: AUGURSPEX_TWELVE_DATA_KEY; verify exchange entitlement.')
            details.append('  Tokyo: AUGURSPEX_JQUANTS_KEY; Korea: AUGURSPEX_KRX_KEY.')
        details.append('Data providers may limit requests or exchange licensing.')
        return '\n'.join(details)

    def _show_source_details(self):
        messagebox.showinfo('AUGURSPEX · DATA SOURCES',
                            self._source_details_text(),parent=self)

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
