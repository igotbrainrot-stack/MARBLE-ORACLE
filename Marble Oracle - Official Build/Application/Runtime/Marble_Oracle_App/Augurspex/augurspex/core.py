"""Local, account-free dashboard state. Never fetches Yahoo data or writes Merkato's files."""
from __future__ import annotations
import json
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

SYMBOL_RE = re.compile(r"^[A-Z0-9^.=+:\-]{1,48}$")
MAX_ITEMS = 300
LAYOUTS = (1, 2, 4, 6, 9)
INTERVALS = ('1', '5', '15', '60', '240', 'D', 'W', 'M')
CHART_TYPES = ('1', '2')  # TradingView: candles, line
DEFAULT_STYLE = '2'        # 0.4.8.5: line graphs by default; CANDLES stays selectable
DEFAULT_SLOTS = ['BTC-USD', 'ETH-USD', 'FX:EURUSD', 'FX:AUDUSD', 'SOL-USD',
                 'XRP-USD', 'FX:GBPUSD', 'FX:USDJPY', 'AAPL']

# Explicit symbol mappings matter: US ticker names are NOT globally unique.
KNOWN = {
    'AAPL': 'NASDAQ:AAPL', 'MSFT': 'NASDAQ:MSFT', 'NVDA': 'NASDAQ:NVDA',
    'QQQ': 'NASDAQ:QQQ', 'SPY': 'AMEX:SPY', 'EWY': 'AMEX:EWY',
    '^GSPC': 'SP:SPX', '^IXIC': 'NASDAQ:IXIC', '^DJI': 'DJ:DJI',
    'BTC-USD': 'KRAKEN:BTCUSD', 'ETH-USD': 'KRAKEN:ETHUSD',
    'SOL-USD': 'KRAKEN:SOLUSD', 'XRP-USD': 'KRAKEN:XRPUSD',
    'BNB-USD': 'COINGECKO:BNB', 'DOGE-USD': 'COINGECKO:DOGE',
    'AMZN': 'NASDAQ:AMZN', 'TSLA': 'NASDAQ:TSLA',
    'META': 'NASDAQ:META', 'GOOG': 'NASDAQ:GOOG', 'AMD': 'NASDAQ:AMD',
}


def tv_symbol(symbol: str) -> str:
    """Map a Yahoo-style saved watchlist ticker to a TradingView exchange symbol."""
    if not isinstance(symbol, str):
        return ''
    s = symbol.strip().upper()
    if not SYMBOL_RE.fullmatch(s):
        return ''
    if s in KNOWN:
        return KNOWN[s]
    if re.fullmatch(r'FX:[A-Z]{6}',s) and s[3:6] != s[6:]:
        return s
    if ':' in s:
        ex, code = s.split(':', 1)
        return s if ex and code and re.fullmatch(r'[A-Z0-9_]+', ex) and re.fullmatch(r'[A-Z0-9.\-]+', code) else ''
    for suffix, exchange in [('.AX', 'ASX'), ('.T', 'TSE'), ('.KS', 'KRX'), ('.KQ', 'KOSDAQ'), ('.L', 'LSE')]:
        if s.endswith(suffix) and s[:-len(suffix)]:
            return f'{exchange}:{s[:-len(suffix)]}'
    # Reject ambiguous symbols, rather than silently opening a different company.
    return ''


def read_json(path: Path, fallback=None):
    try:
        obj = json.loads(path.read_text(encoding='utf-8'))
        return obj
    except (OSError, UnicodeError, ValueError):
        return fallback


def app_folder(home: Path) -> Path:
    config_home = os.environ.get('XDG_CONFIG_HOME') if home.resolve() == Path.home().resolve() else None
    return Path(config_home or (home / '.config')) / 'augurspex'


def legacy_settings_path(home: Path) -> Path:
    """Former Marketboard settings; read for migration, never write here."""
    return app_folder(home).parent / 'merkato-marketboard' / 'settings.json'


def watchlist_paths(home: Path):
    return [home / '.var/app/com.ekonomikas.merkato/config/merkato/watchlist.json',
            home / '.config/merkato/watchlist.json']


def old_chart_state_paths(home: Path):
    return [home / '.var/app/com.ekonomikas.merkato/config/merkato/multi_charts.json',
            home / '.config/merkato/multi_charts.json']


def clean_item(item):
    if not isinstance(item, dict):
        return None
    symbol = str(item.get('symbol') or '').strip().upper()
    if not tv_symbol(symbol):
        return None
    name = item.get('long_name') or item.get('name') or symbol
    name = str(name).strip()[:110] or symbol
    return {'symbol': symbol, 'name': name, 'tv': tv_symbol(symbol)}


def merge_watchlists(home: Path, default_path: Path, settings: dict):
    """Use the actual Merkato list if present; starter assets only when absent."""
    result = {}
    found = None
    # The user's native AUGURSPEX list is authoritative once created.
    # Earlier Merkato files are never edited, and deleted entries do not reappear.
    own = app_folder(home) / 'watchlist.json'
    obj = read_json(own)
    if isinstance(obj, dict) and isinstance(obj.get('markets'), list):
        for raw in obj['markets']:
            item = clean_item(raw)
            if item: result[item['symbol']] = item
        return list(result.values())[:MAX_ITEMS], str(own)
    for path in watchlist_paths(home):
        obj = read_json(path, {})
        if isinstance(obj, dict) and isinstance(obj.get('stocks'), list):
            found = path
            for raw in obj['stocks']:
                item = clean_item(raw)
                if item: result[item['symbol']] = item
            break
    if found is None:
        default = read_json(default_path, {})
        for raw in (default.get('stocks', []) if isinstance(default, dict) else []):
            item = clean_item(raw)
            if item: result[item['symbol']] = item
    for raw in settings.get('added', []):
        item = clean_item(raw)
        if item: result[item['symbol']] = item
    hidden = set(settings.get('hidden', []))
    rows = [item for key, item in result.items() if key not in hidden][:MAX_ITEMS]
    return rows, str(found) if found else None


WORKSPACES = ('Overview', 'Healthcare', 'Crypto')
CHART_SIZES = ('comfortable', 'large')
DATA_MODES = ('auto', 'hosted', 'public')
QUOTE_PROVIDERS = ('auto', 'kraken', 'coinbase')
FILTERS = ('all', 'favorites', 'crypto', 'stocks', 'fx')


def clean_snapshot(raw):
    """Validate a workspace snapshot without recursion or arbitrary JSON."""
    if not isinstance(raw, dict):
        return None
    layout = raw.get('layout', 2)
    if type(layout) is not int or layout not in LAYOUTS: layout = 2
    interval = str(raw.get('interval', 'D')).upper()
    if interval not in INTERVALS: interval = 'D'
    style = str(raw.get('style', DEFAULT_STYLE))
    if style not in CHART_TYPES: style = DEFAULT_STYLE
    symbols = raw.get('symbols', [])
    if not isinstance(symbols, list): symbols = []
    symbols = [str(s).strip().upper() if isinstance(s, str) else '' for s in symbols[:9]]
    symbols = [s if tv_symbol(s) else '' for s in symbols]
    # Per-chart LINE/CANDLES choice ('' = follow the workspace style).
    slot_styles = raw.get('slot_styles', [])
    if not isinstance(slot_styles, list): slot_styles = []
    slot_styles = [str(v) if str(v) in CHART_TYPES else '' for v in slot_styles[:9]]
    return {'layout': layout, 'interval': interval, 'style': style,
            'symbols': (symbols + [''] * 9)[:9], 'slot_styles': (slot_styles + [''] * 9)[:9]}


def sanitize_settings(raw):
    if not isinstance(raw, dict): raw = {}
    snapshot = clean_snapshot(raw)
    added = raw.get('added', [])
    if not isinstance(added, list): added = []
    added_clean = [v for v in (clean_item(x) for x in added[:MAX_ITEMS]) if v]
    hidden = raw.get('hidden', [])
    if not isinstance(hidden, list): hidden = []
    hidden_clean = [str(s).upper() for s in hidden[:MAX_ITEMS] if isinstance(s, str) and tv_symbol(s)]
    favorites = raw.get('favorites', [])
    if not isinstance(favorites, list): favorites = []
    favorites = list(dict.fromkeys(str(s).upper() for s in favorites[:MAX_ITEMS]
                                   if isinstance(s, str) and tv_symbol(s)))
    workspaces = raw.get('workspaces', {})
    if not isinstance(workspaces, dict): workspaces = {}
    workspaces = {key:clean_snapshot(workspaces[key]) for key in WORKSPACES
                  if key in workspaces and clean_snapshot(workspaces[key]) is not None}
    # Respect explicitly saved LINE/CANDLES choices on upgrade. Older builds
    # sometimes saved CANDLES as a default, but that is indistinguishable from
    # a user's deliberate setting. Do not overwrite their preference.
    # For a genuinely new profile, clean_snapshot already uses DEFAULT_STYLE.
    workspace = raw.get('workspace', 'Overview')
    if workspace not in WORKSPACES: workspace = 'Overview'
    chart_size = raw.get('chart_size', 'comfortable')
    if chart_size not in CHART_SIZES: chart_size = 'comfortable'
    watch_filter = raw.get('watch_filter', 'all')
    if watch_filter not in FILTERS: watch_filter = 'all'
    view_bars = str(raw.get('view_bars', 'MAX'))
    if view_bars not in ('30','90','MAX'): view_bars = 'MAX'
    return {**snapshot, 'added': added_clean, 'hidden': hidden_clean, 'favorites': favorites,
            'workspaces': workspaces, 'workspace': workspace, 'line_default_0485': True,
            'chart_size': chart_size, 'watch_filter': watch_filter, 'view_bars': view_bars,
            'unofficial_sources': raw.get('unofficial_sources') is True,
            'sidebar_collapsed': raw.get('sidebar_collapsed', False) is True,
            'chart_provider': raw.get('chart_provider') if raw.get('chart_provider') in DATA_MODES else 'auto',
            'quote_provider': raw.get('quote_provider') if raw.get('quote_provider') in QUOTE_PROVIDERS else 'auto'}


def read_settings(home: Path):
    path = app_folder(home) / 'settings.json'
    raw = read_json(path)
    if raw is None:
        raw = read_json(legacy_settings_path(home))
    if raw is None:
        raw = {}
        for legacy_path in old_chart_state_paths(home):
            legacy = read_json(legacy_path)
            if isinstance(legacy, dict):
                raw.update({'layout': legacy.get('layout'), 'symbols': legacy.get('symbols', [])})
                break
    settings = sanitize_settings(raw)
    # Keep all user selections in their exact slots (including intentionally blank).
    # For initial installs only, use the known nine preferred market symbols.
    if raw == {}:
        settings['symbols'] = DEFAULT_SLOTS[:]
    settings['symbols'] = (settings['symbols'] + [''] * 9)[:9]
    return settings


def save_settings(home: Path, data):
    config = app_folder(home)
    config.mkdir(mode=0o700, parents=True, exist_ok=True)
    target = config / 'settings.json'
    temporary = config / f'.settings.{os.getpid()}.tmp'
    try:
        temporary.write_text(json.dumps(sanitize_settings(data), indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        os.chmod(temporary, 0o600)
        os.replace(temporary, target)
    finally:
        try: temporary.unlink()
        except FileNotFoundError: pass
    return sanitize_settings(data)


def update_watchlist(home: Path, default_path: Path, settings: dict, incoming, mode='merge', confirm_empty=False):
    """Validate and atomically persist the independent AUGURSPEX market list.

    Existing original Merkato watchlists and settings.json are never changed.
    Explicit exchange is required for tickers not in the built-in safe mappings.
    """
    import time
    if mode not in ('merge', 'replace'):
        raise ValueError('Mode must be merge or replace')
    if not isinstance(incoming, list) or len(incoming) > MAX_ITEMS:
        raise ValueError(f'Market list must contain at most {MAX_ITEMS} entries')
    new_rows = []
    invalid = []
    seen = set()
    for i, raw in enumerate(incoming):
        item = clean_item(raw if isinstance(raw, dict) else {'symbol': raw} if isinstance(raw, str) else None)
        if item is None:
            invalid.append(i + 1)
            continue
        if item['symbol'] not in seen:
            new_rows.append(item)
            seen.add(item['symbol'])
    if not new_rows and not confirm_empty:
        raise ValueError('No valid market symbols supplied; existing list not changed')
    if invalid:
        # Reject malformed payload instead of reporting partial, potentially dangerous replacement.
        raise ValueError('Invalid symbols at rows: ' + ', '.join(map(str, invalid[:12])))
    current, _ = merge_watchlists(home, default_path, settings)
    if mode == 'merge':
        updated = {v['symbol']: v for v in current}
        updated.update({v['symbol']: v for v in new_rows})
        final = list(updated.values())
    else:
        final = new_rows
    if len(final) > MAX_ITEMS:
        raise ValueError(f'Too many markets; maximum is {MAX_ITEMS}')
    location = app_folder(home)
    location.mkdir(parents=True, exist_ok=True, mode=0o700)
    destination = location / 'watchlist.json'
    if destination.exists():
        backups = location / 'watchlist-backups'
        backups.mkdir(mode=0o700, exist_ok=True)
        previous = backups / f'watchlist-{time.time_ns()}.json'
        previous.write_bytes(destination.read_bytes())
        previous.chmod(0o600)
        for outdated in sorted(backups.glob('watchlist-*.json'))[:-10]:
            outdated.unlink(missing_ok=True)
    temporary = location / f'.watchlist.{os.getpid()}.{time.time_ns()}.tmp'
    try:
        temporary.write_text(json.dumps({'version': 1, 'markets': final}, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        os.chmod(temporary, 0o600)
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    return {'items': final, 'count': len(final), 'imported': len(new_rows), 'mode': mode, 'source': str(destination)}



CURATED_MARKETS_VERSION = 'popular-markets-2026-11-13'


def market_category(symbol):
    """Category used by the watchlist, never guessed from the company name."""
    s=str(symbol).upper()
    if re.fullmatch(r'FX:[A-Z]{6}',s):return 'fx'
    if s in ('BTC-USD','ETH-USD','SOL-USD','XRP-USD','BNB-USD','DOGE-USD'):return 'crypto'
    return 'stocks'


def reset_to_popular_markets_once(home: Path, default_path: Path):
    """Explicit 0.4.8.8 curated-list migration. Never touch legacy Merkato files.

    This is a one-time user-requested replacement, not a recurring reset.
    A complete, timestamped backup of *both* personal settings and the user's
    saved watchlist is written before either existing file is changed. The
    marker prevents the same operation on future launches. Fail closed if a
    backup cannot be written. Test with an injected temporary HOME.
    """
    folder=app_folder(Path(home))
    marker=folder/'.popular-markets-20261113-done.json'
    if marker.exists():return False
    default=read_json(Path(default_path),{})
    entries=[clean_item(item) for item in default.get('stocks',[]) if isinstance(item,dict)]
    entries=[item for item in entries if item is not None]
    if len(entries)<12:raise ValueError('Curated market list incomplete; existing list left unchanged')
    folder.mkdir(parents=True,exist_ok=True,mode=0o700)
    existing=[p for p in (folder/'settings.json',folder/'watchlist.json') if p.is_file()]
    if existing:
        backup=folder/'watchlist-backups'/('popular-reset-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
        backup.mkdir(parents=True,exist_ok=True,mode=0o700)
        for path in existing:
            target=backup/path.name
            shutil.copy2(path,target)
            target.chmod(0o600)
            if target.read_bytes()!=path.read_bytes():raise OSError('Backup verification failed')
    settings=sanitize_settings(read_json(folder/'settings.json',{}))
    settings.update({'symbols':DEFAULT_SLOTS[:], 'layout':2, 'workspace':'Overview',
                     'workspaces':{},'added':[],'hidden':[],'favorites':[],
                     'watch_filter':'all','slot_styles':['']*9})
    settings=save_settings(home,settings)
    target=folder/'watchlist.json'
    temporary=folder/('.popular-watchlist-'+str(os.getpid())+'.tmp')
    try:
        temporary.write_text(json.dumps({'version':1,'markets':entries},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        temporary.chmod(0o600)
        os.replace(temporary,target)
    finally:
        temporary.unlink(missing_ok=True)
    marktemp=folder/('.popular-reset-'+str(os.getpid())+'.tmp')
    try:
        marktemp.write_text(json.dumps({'version':CURATED_MARKETS_VERSION,
                                         'backup_created':bool(existing),'date':datetime.now(timezone.utc).isoformat()})+'\n',encoding='utf-8')
        marktemp.chmod(0o600)
        os.replace(marktemp,marker)
    finally:
        marktemp.unlink(missing_ok=True)
    return True
