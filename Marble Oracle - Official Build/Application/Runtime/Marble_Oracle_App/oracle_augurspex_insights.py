"""AUGURSPEX Market Atlas: factual comparison and accessible observation table.

Only displays previously retrieved provider observations. Never constructs prices,
substitutes securities, contacts an endpoint, or assumes a market is trading.
"""
from __future__ import annotations

import csv
from datetime import datetime, timezone
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from oracle_augurspex_tab import _plotted_candles, history_health, format_price, csv_safe
from marble_uberata import FAMILY

COLORS = {'stocks': '#FFB667', 'crypto': '#CCAAFF', 'fx': '#77DCC2'}


def market_rows(watchlist, stored, errors, period='D', view_bars='MAX', now=None):
    """Pure, deterministic per-symbol summary; never compares different currencies as money.

    Percentage change is within each instrument's *own visible history window*.
    Unavailable instruments retain blank price/change rather than a fake zero.
    """
    from Augurspex.augurspex.core import market_category
    result = []
    for item in watchlist:
        symbol = item['symbol']
        data = stored.get((symbol, period))
        bars = _plotted_candles((data or {}).get('candles') or [], limit=None)
        visible = bars[-int(view_bars):] if str(view_bars) in ('30', '90') else bars
        status, observed = history_health(data, symbol, period, now=now)
        first = float(visible[0]['close']) if visible else None
        last = float(visible[-1]['close']) if visible else None
        change = ((last / first - 1) * 100) if first is not None and first > 0 else None
        # Unknown timestamps do not become 'current' merely because they were cached recently.
        result.append({
            'symbol': symbol,
            'name': item.get('name') or symbol,
            'category': market_category(symbol),
            'status': status.upper() if bars else ('SOURCE ERROR' if errors.get((symbol, period)) else 'NOT LOADED'),
            'last': last,
            'change': change,
            'observed': observed.strftime('%Y-%m-%d %H:%M UTC') if observed else '—',
            'source': str((data or {}).get('source') or '—')[:110],
            'currency': str((data or {}).get('currency') or '—')[:15],
            'count': len(bars),
            'warning': str((data or {}).get('warning') or errors.get((symbol, period)) or '')[:350],
            'close_only': bool(bars and any(b.get('close_only') for b in bars)),
        })
    return result


def observation_cells(bars):
    """Table/CSV cells: never pretend close-only records contain open/high/low."""
    for bar in _plotted_candles(bars, limit=None):
        close_only = bool(bar.get('close_only'))
        yield (
            str(bar.get('time') or ''),
            '' if close_only else bar.get('open', ''),
            '' if close_only else bar.get('high', ''),
            '' if close_only else bar.get('low', ''),
            bar['close'],
            bar.get('volume', ''),
        )


def _dialog(parent, title, palette, width=1000, height=660):
    host = parent.winfo_toplevel()
    win = tk.Toplevel(host)
    win.title(title)
    win.configure(bg=palette['bg'])
    sw, sh = max(520, host.winfo_screenwidth()), max(440, host.winfo_screenheight())
    w, h = min(width, sw - 70), min(height, sh - 95)
    win.geometry(f'{max(500,w)}x{max(400,h)}')
    win.transient(host)
    win.bind('<Escape>', lambda _e: win.destroy())
    return win


def _tree(parent, colours, columns, widths):
    name = f'Augurspex{abs(id(parent))}'
    style = ttk.Style(parent)
    style.configure(name+'.Treeview', background=colours['inset'], foreground=colours['ink'],
                    fieldbackground=colours['inset'], borderwidth=0, rowheight=31,
                    font=(FAMILY, 11))
    style.configure(name+'.Treeview.Heading', background=colours['control'], foreground=colours['accent'],
                    font=(FAMILY, 11, 'bold'), relief='flat')
    style.map(name+'.Treeview', background=[('selected', colours['active'])],
              foreground=[('selected', colours['ink'])])
    tree = ttk.Treeview(parent, columns=columns, show='headings', selectmode='browse', style=name+'.Treeview')
    for col, width in zip(columns, widths):
        tree.heading(col, text=col.upper())
        tree.column(col, width=width, stretch=True, anchor='w')
    sy = ttk.Scrollbar(parent, orient='vertical', command=tree.yview)
    sx = ttk.Scrollbar(parent, orient='horizontal', command=tree.xview)
    tree.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)
    tree.grid(row=0, column=0, sticky='nsew')
    sy.grid(row=0, column=1, sticky='ns')
    sx.grid(row=1, column=0, sticky='ew')
    parent.grid_rowconfigure(0, weight=1)
    parent.grid_columnconfigure(0, weight=1)
    return tree


def _action(parent, colours, text, fn):
    button = tk.Button(parent, text=text, command=fn, font=(FAMILY, 11, 'bold'),
                       bg=colours['control'], fg=colours['ink'], activebackground=colours['active'],
                       activeforeground=colours['accent'], bd=0, padx=13, pady=8, cursor='hand2')
    button.pack(side='left', padx=(0, 8))
    return button


def show_market_atlas(panel):
    """Full-watchlist comparison based on data ALREADY in memory."""
    p = panel.p
    rows = market_rows(panel.watchlist, panel._data, panel._errors,
                       panel.settings['interval'], panel.settings.get('view_bars', 'MAX'))
    win = _dialog(panel, 'AUGURSPEX · MARKET ATLAS', p)
    heading = tk.Frame(win, bg=p['bg']); heading.pack(fill='x', padx=18, pady=(15, 5))
    tk.Label(heading, text='MARKET ATLAS', bg=p['bg'], fg=p['accent'],
             font=(FAMILY, 20, 'bold')).pack(side='left')
    ok = sum(r['status'] == 'RECENT' for r in rows)
    tk.Label(heading, text=f'{ok} RECENT · {len(rows)} WATCHED · {panel.settings["interval"]} BARS',
             bg=p['bg'], fg=p['muted'], font=(FAMILY, 11, 'bold')).pack(side='right')
    tk.Label(win, text='Changes use the chosen observation range (30 / 90 / MAX); compact candle plots may show fewer bars. Not live.',
             bg=p['bg'], fg=p['muted'], font=(FAMILY, 11), anchor='w').pack(fill='x', padx=18, pady=(0, 10))
    search = tk.StringVar()
    tk.Entry(win, textvariable=search, bg=p['inset'], fg=p['ink'], insertbackground=p['accent'],
             relief='flat', font=(FAMILY, 12)).pack(fill='x', padx=18, pady=(0, 10), ipady=4)
    area = tk.Frame(win, bg=p['bg']); area.pack(fill='both', expand=True, padx=18)
    cols = ('MARKET', 'CLASS', 'STATUS', 'LAST', 'WINDOW %', 'DATE', 'PROVIDER')
    tree = _tree(area, p, cols, (130, 84, 118, 110, 120, 170, 190))
    tree.tag_configure('positive', foreground=p['green'])
    tree.tag_configure('negative', foreground=p['red'])
    tree.tag_configure('unavailable', foreground=p['muted'])
    rows_by_symbol = {r['symbol']: r for r in rows}
    sort_col, reverse = ['symbol'], [False]

    def render(*_args):
        term = search.get().strip().lower()
        choice = tree.selection()[0] if tree.selection() else None
        for child in tree.get_children():tree.delete(child)
        key = sort_col[0]
        ordered = sorted(rows, key=lambda r: (r.get(key) is None, r.get(key) if r.get(key) is not None else ''),
                         reverse=reverse[0])
        for r in ordered:
            if term and term not in (r['symbol']+' '+r['name']+' '+r['category']+' '+r['status']).lower():continue
            tag = 'positive' if (r['change'] is not None and r['change'] >= 0) else 'negative' if r['change'] is not None else 'unavailable'
            vals = (r['symbol'], r['category'].upper(), r['status'],
                    format_price(r['last']) if r['last'] is not None else '—',
                    f'{r["change"]:+.2f}%' if r['change'] is not None else '—',
                    r['observed'], r['source'])
            tree.insert('', 'end', iid=r['symbol'], values=vals, tags=(tag,))
        if choice in tree.get_children():tree.selection_set(choice)

    for title, key in zip(cols, ('symbol', 'category', 'status', 'last', 'change', 'observed', 'source')):
        def do_sort(k=key):
            reverse[0] = not reverse[0] if sort_col[0] == k else False
            sort_col[0] = k; render()
        tree.heading(title, text=title+' ⇅', command=do_sort)
    search.trace_add('write', render)
    render()
    detail = tk.StringVar(value='Select a market for full provenance and source status.')
    tk.Label(win, textvariable=detail, bg=p['bg'], fg=p['ink'], font=(FAMILY, 10),
             anchor='w', wraplength=860, justify='left').pack(fill='x', padx=18, pady=(8, 7))
    def on_select(_e=None):
        if tree.selection():
            r=rows_by_symbol[tree.selection()[0]]
            detail.set(f'{r["symbol"]} · {r["name"]} · {r["count"]} validated observations · '
                       f'{"close-only price history" if r["close_only"] else "OHLC history"} · {r["warning"] or "No additional warning"}')
    tree.bind('<<TreeviewSelect>>', on_select)
    commands = tk.Frame(win, bg=p['bg']); commands.pack(fill='x', padx=18, pady=(2, 15))
    def show_selected():
        if not tree.selection():return
        sym=tree.selection()[0]
        panel.settings['symbols'][panel.active]=sym
        panel._save();panel._refresh_charts();panel._select_chart(panel.active)
        win.destroy()
    def export_summary():
        target=filedialog.asksaveasfilename(parent=win, title='Export Market Atlas',
                                            initialfile='augurspex-market-atlas.csv', defaultextension='.csv',
                                            filetypes=[('CSV files','*.csv')])
        if not target:return
        try:
            with open(target,'w',newline='',encoding='utf-8') as out:
                writer=csv.writer(out)
                writer.writerow(['symbol','name','type','status','last_price','currency','visible_change_percent',
                                 'last_observation_utc','source','validated_bars','warning'])
                for r in rows:
                    writer.writerow([csv_safe(x) for x in (r['symbol'],r['name'],r['category'],r['status'],
                                     r['last'] if r['last'] is not None else '',r['currency'],
                                     round(r['change'],5) if r['change'] is not None else '',
                                     r['observed'],r['source'],r['count'],r['warning'])])
        except OSError as exc:
            messagebox.showerror('MARKET ATLAS',str(exc)[:160],parent=win)
    _action(commands,p,'OPEN IN ACTIVE CHART',show_selected)
    _action(commands,p,'EXPORT SUMMARY CSV',export_summary)
    _action(commands,p,'CLOSE',win.destroy)
    return win


def show_observation_table(panel):
    """Keyboard-scrollable text alternative for a plotted series."""
    plan = panel._space_plan()
    if panel.active >= len(plan):return None
    symbol=plan[panel.active][0]
    data=panel._data.get((symbol,panel.settings['interval']))
    bars=list(observation_cells((data or {}).get('candles') or []))
    if not bars:
        messagebox.showinfo('AUGURSPEX · OBSERVATIONS',
                            'No validated observations for the selected chart.',parent=panel)
        return None
    p=panel.p
    win=_dialog(panel,f'AUGURSPEX · {symbol} OBSERVATIONS',p,width=940,height=610)
    tk.Label(win,text=f'OBSERVATIONS · {symbol}',bg=p['bg'],fg=p['accent'],
             font=(FAMILY,19,'bold'),anchor='w').pack(fill='x',padx=18,pady=(14,4))
    source=str((data or {}).get('source') or 'Unknown source')
    close_only=any(r.get('close_only') for r in _plotted_candles((data or {}).get('candles') or [],limit=None))
    tk.Label(win,text=f'{len(bars)} validated records · {source} · '
             f'{"CLOSE-ONLY · NO OBSERVED OHLC" if close_only else "PROVIDER OHLC"} · HISTORICAL',
             bg=p['bg'],fg=p['muted'],font=(FAMILY,10,'bold'),anchor='w').pack(fill='x',padx=18,pady=(0,10))
    area=tk.Frame(win,bg=p['bg']); area.pack(fill='both',expand=True,padx=18)
    cols=('DATE / TIME','OPEN','HIGH','LOW','CLOSE','VOLUME')
    tree=_tree(area,p,cols,(210,120,120,120,120,120))
    for i, row in enumerate(reversed(bars)):
        values=[row[0]] + [format_price(v) if isinstance(v,(int,float)) else str(v) for v in row[1:]]
        tree.insert('', 'end', iid=str(i), values=values)
    info=tk.Frame(win,bg=p['bg']);info.pack(fill='x',padx=18,pady=14)
    _action(info,p,'CLOSE',win.destroy)
    return win
