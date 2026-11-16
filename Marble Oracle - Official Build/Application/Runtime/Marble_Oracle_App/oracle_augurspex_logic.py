"""Tk-free logic for the AUGURSPEX workspace: chart geometry, validation of
received observations, date/price axis labels, freshness and status wording.

Nothing here creates a widget or contacts a provider, so every function can
be tested on any Python without a display. `oracle_augurspex_tab` imports
these names, and existing imports from that module keep working.

Rules that hold throughout: values and timestamps are only ever read from the
provider's own rows; nothing is interpolated, renamed or invented.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone

from Augurspex.augurspex.core import market_category
from Augurspex.augurspex.providers import classify_error_text, error_kind, split_attempts


def _rgb(value):
    value=str(value).strip().lstrip('#')
    try:
        return tuple(int(value[i:i+2],16) for i in (0,2,4))
    except (TypeError,ValueError):
        return (29,23,20)


def _darken(value, amount):
    return '#%02x%02x%02x' % tuple(round(v*(1-amount)) for v in _rgb(value))


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
# 0.4.9.6 design: 380x260 (was 420x320) so four charts form a 2x2 grid at the
# default 1216x848 window instead of one scrolling column.
MIN_CARD_W, MIN_CARD_H = 380, 260
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
        # When an embedded CRT has less vertical room than one minimum-height
        # card, give the single-chart view a *larger* scrollable canvas rather
        # than making it imperceptibly smaller than a four-chart card.
        if count == 1 and scroll:
            card_h = max(card_h, MIN_CARD_H + 48)
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


SHORT_STATUS = {'DATA SOURCE LIMITED': 'LIMITED', 'STOCK FEED LIMITED': 'LIMITED', 'NETWORK ISSUE': 'NETWORK',
                'LISTING NOT SUPPORTED': 'UNSUPPORTED', 'NO HISTORY FROM PROVIDER': 'NO HISTORY',
                'MARKET DATA UNAVAILABLE': 'UNAVAILABLE', 'DATA SOURCE SETUP NEEDED': 'NEEDS SETUP',
                'NETWORK DISABLED': 'OFFLINE', 'AWAITING DATA': 'WAITING',
                'API KEY OR PLAN REJECTED': 'KEY REJECTED', 'PROVIDER FAULT': 'PROVIDER FAULT',
                'PROVIDER REPLY REJECTED': 'BAD REPLY'}

# One wording per failure kind (providers.ERROR_KINDS), used by the chart
# message, the slot tabs and SOURCE DETAILS so they can never disagree.
_STATUS_BY_KIND = {
    'offline': 'NETWORK DISABLED',
    'not_configured': 'DATA SOURCE SETUP NEEDED',
    'rate_limited': 'DATA SOURCE LIMITED',
    'refused': 'DATA SOURCE LIMITED',
    'cooldown': 'DATA SOURCE LIMITED',
    'auth': 'API KEY OR PLAN REJECTED',
    'network': 'NETWORK ISSUE',
    'provider_failure': 'PROVIDER FAULT',
    'unsupported': 'LISTING NOT SUPPORTED',
    'no_data': 'NO HISTORY FROM PROVIDER',
    'invalid_response': 'PROVIDER REPLY REJECTED',
    'unknown': 'MARKET DATA UNAVAILABLE',
}
_DIAGNOSTIC_BY_KIND = {
    'rate_limited': 'LIMITED', 'refused': 'LIMITED', 'cooldown': 'LIMITED', 'auth': 'KEY/PLAN',
    'network': 'NETWORK', 'provider_failure': 'FAULT', 'unsupported': 'UNSUPPORTED/PLAN',
    'no_data': 'NO HISTORY', 'invalid_response': 'BAD REPLY', 'not_configured': 'NOT SET UP',
    'offline': 'OFFLINE', 'unknown': 'ERROR',
}


def status_for_error(error, symbol=''):
    """Headline shown in place of a chart when no history could be drawn."""
    text = str(error or '')
    if not text.strip():
        return 'AWAITING DATA'
    status = _STATUS_BY_KIND[error_kind(text)]
    if status == 'DATA SOURCE LIMITED' and market_category(symbol or '') == 'stocks':
        return 'STOCK FEED LIMITED'
    return status


def provider_diagnostics(error, limit=5):
    """'STRASMORE LIMITED · STOOQ NO HISTORY': one short state per source tried.

    Every source the router knows is recognised, so a failed first choice is
    never silently missing from the line.
    """
    pieces = []
    for name, message in split_attempts(error):
        if not name:
            continue
        pieces.append(name.upper() + ' ' + _DIAGNOSTIC_BY_KIND[classify_error_text(message)])
    return ' · '.join(pieces[:limit])


# Reserve a real date axis along the bottom and price tick labels on the
# right. The same geometry is used by the candles/lines, ticks and grid.
CHART_PAD_L, CHART_PAD_T, CHART_PAD_R, CHART_PAD_B = 13, 16, 74, 51


def _plotted_candles(candles, limit=120):
    """Validate actual provider OHLC without changing values or timestamps.

    Render callers may limit their window; CSV export and freshness checks
    must examine the *complete* received history, not just its last 120 rows.
    """
    valid=[]
    series=candles if limit is None else candles[-limit:]
    for row in series:
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
    bars=_plotted_candles(candles, limit=None)
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
    bars=_plotted_candles(candles, limit=None)
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
    picks=None
    if fmt in ("%b '%y",'%Y'):
        picks=_calendar_picks(dated,count,monthly=(fmt!='%Y'))
    if not picks:
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


def _calendar_picks(dated, count, monthly=True):
    """Ticks on the first plotted bar of a month (or year), at a steady step.

    Evenly spaced bar indices give uneven calendars (JUN AUG SEP NOV); this
    picks every 1st, 2nd, 3rd, 6th or 12th month (1, 2, 5, 10... years)
    counting back from the newest, so the gaps read the same across a card.
    The oldest period counts only if the data starts in its first week, so a
    label never sits half a period away from its neighbour. Returns indices
    into `dated`, or None when fewer than two boundaries are on screen.
    """
    def period(moment):return (moment.year, moment.month) if monthly else moment.year
    starts=[]
    for j,(_i,moment) in enumerate(dated):
        if j==0:
            early=moment.day<=7 if monthly else (moment.month==1 and moment.day<=7)
            if early:starts.append(j)
        elif period(moment)!=period(dated[j-1][1]):
            starts.append(j)
    if len(starts)<2 or count<2:return None
    steps=(1,2,3,6,12,24) if monthly else (1,2,5,10,20,50,100)
    step=next((k for k in steps if -(-len(starts)//k)<=count),steps[-1])
    chosen=starts[::-1][::step]
    return sorted(chosen) if len(chosen)>=2 else None


def fit_date_ticks(ticks, measure, gap=10):
    """Place date labels so that none overlap: [(x, label, anchor), …].

    `ticks` is chart_date_ticks() output and `measure(text)` returns a label's
    width in pixels for the axis font. The first label hangs to the right of
    its tick, the last to the left, the rest are centred. When two would
    touch, the older one is dropped: the newest date is always kept, and no
    label is moved away from the observation it names.
    """
    count = len(ticks)
    spans = []
    for j, (x, label) in enumerate(ticks):
        width = max(0, int(measure(label)))
        if j == 0:
            anchor, left, right = 'nw', x, x + width
        elif j == count - 1:
            anchor, left, right = 'ne', x - width, x
        else:
            anchor, left, right = 'n', x - width / 2, x + width / 2
        spans.append((left, right, x, label, anchor))
    kept = []
    boundary = None
    for left, right, x, label, anchor in reversed(spans):
        if boundary is None or right + gap <= boundary:
            kept.append((x, label, anchor))
            boundary = left
    kept.reverse()
    return kept



def axis_date_labels(candles, width, measure, gap=10):
    """Date labels that fit without dropping any: [(x, label, anchor), ...].

    fit_date_ticks() drops a label that would touch its newer neighbour,
    which leaves an uneven step (AUG, SEP, NOV). Ask for fewer labels
    instead, so the calendar step widens evenly, until every one fits.
    """
    placed=[]
    for max_ticks in (5,4,3,2):
        ticks=chart_date_ticks(candles, width, max_ticks=max_ticks)
        placed=fit_date_ticks(ticks, measure, gap=gap)
        if len(placed)==len(ticks):return placed
    return placed

def chart_display_bars(candles, width, style='1', view_bars='MAX'):
    """Show recent *real* OHLC bars at a readable density on small cards.

    Candle mode limits the visible window rather than synthesising or averaging
    quotes. The date axis and prices use precisely the same visible records.
    Line mode retains the full available history.
    """
    bars=_plotted_candles(candles, limit=None)
    # A BARS view is an observation-count window, not a claim about calendar
    # duration or the provider having supplied additional history.
    if str(view_bars) in ('30','90'):
        bars=bars[-int(view_bars):]
    if style != '1' or any(bar.get('close_only') for bar in bars):
        return bars
    plot_width=max(1,width-CHART_PAD_L-CHART_PAD_R)
    max_bars=max(8,int(plot_width//6.0))
    return bars[-max_bars:]


def _blend(colour, other, fraction):
    a=_rgb(colour);b=_rgb(other)
    return '#%02x%02x%02x' % tuple(round(a[i]*(1-fraction)+b[i]*fraction) for i in range(3))


def observed_at(data):
    """Best truthful observation timestamp; never use receipt time as a price date.

    The newest parseable candle timestamp takes precedence over inconsistent
    provider metadata. Fixtures with synthetic candle IDs may supply a valid
    latest_observation instead. Unknown timestamps do not imply fresh data.
    """
    if not isinstance(data, dict):return None
    samples=[]
    for item in _plotted_candles(data.get('candles') or [], limit=None):
        if item.get('time') is not None:
            samples.append(str(item['time']))
    values=[]
    for raw in samples[-320:]:
        try:
            dt=datetime.fromisoformat(raw.replace('Z','+00:00'))
            if dt.tzinfo is None:dt=dt.replace(tzinfo=timezone.utc)
            if dt.year>=1990:values.append(dt.astimezone(timezone.utc))
        except (ValueError,TypeError,OverflowError):pass
    if values:return max(values)
    try:
        dt=datetime.fromisoformat(str(data.get('latest_observation','')).replace('Z','+00:00'))
        if dt.tzinfo is None:dt=dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (ValueError,TypeError,OverflowError):return None


def csv_safe(value):
    """Stop formula injection if exported provider strings open in a spreadsheet."""
    if isinstance(value,str) and (value.startswith(('\t','\r','\n','\ufeff')) or value.lstrip().startswith(('=','+','-','@','＝','＋','－','＠'))):
        return "'"+value
    return value


def history_health(data, symbol, period='D', now=None):
    """Separate historical existence from freshness and source availability.

    Trading holidays/weekends are tolerated without claiming live coverage.
    Weekly/monthly series need wider thresholds. A future observation is
    suspicious, not a reason to call data current.
    """
    exists=bool(isinstance(data,dict) and _plotted_candles(data.get('candles') or []))
    date=observed_at(data) if exists else None
    if not exists:return 'missing', None
    if date is None:return 'undated', None
    now=now or datetime.now(timezone.utc)
    if now.tzinfo is None:now=now.replace(tzinfo=timezone.utc)
    days=(now.astimezone(timezone.utc)-date).total_seconds()/86400
    if days < -1:return 'future',date
    period=str(period).upper()
    if period=='M':allowed=48
    elif period=='W':allowed=17
    elif period=='D':allowed=3 if symbol.endswith('-USD') else 8
    else:allowed=3 if symbol.endswith('-USD') else 8
    return ('recent' if days<=allowed else 'stale'),date


def _small_decimals(v, significant):
    """Decimal places that show `significant` meaningful digits of |v| < 1."""
    return min(12, max(4, significant - 1 - math.floor(math.log10(abs(v)))))


def format_price(value):
    """Right-axis price labels preserve useful decimals for low-price assets.

    Below 0.01 the number of decimals grows so three significant digits stay
    visible; a sub-cent asset is never drawn as a column of '0.0000'.
    """
    v=float(value)
    if abs(v)>=1000:return f'{v:,.0f}'
    if abs(v)>=10:return f'{v:,.2f}'
    if abs(v)>=1:return f'{v:,.3f}'
    if v!=0 and abs(v)<0.01:return f'{v:.{_small_decimals(v,3)}f}'
    return f'{v:,.4f}'


def format_quote(value):
    """Latest-price readout in a chart header: two decimals, more below 1."""
    v=float(value)
    if abs(v)>=1:return f'{v:,.2f}'
    if v!=0 and abs(v)<0.01:return f'{v:.{_small_decimals(v,4)}f}'
    return f'{v:,.4f}'
