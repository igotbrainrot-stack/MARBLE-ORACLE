#!/usr/bin/env python3
"""Ask every no-key source for every starter-watchlist market, once, and report what came back.

This is the only check in the project that talks to the real providers. It
answers "which markets can actually show a chart without an API key, today,
from this network?" - something the offline tests cannot know.

For each market it calls each source the router would try, one at a time, and
prints: the outcome (OK or the failure kind), how many validated observations
arrived, and the date of the newest one. It prints no prices, stores nothing
in the repository and uses a throw-away cache folder.

    python3 Application/Tools/probe_providers.py                # daily history
    python3 Application/Tools/probe_providers.py --period 60    # hourly
    python3 Application/Tools/probe_providers.py --markdown out.md --json out.json

A source that answers here may still refuse another network (some providers
block data-centre or home addresses differently); the report states where and
when it ran so nobody mistakes it for a guarantee.
"""
from __future__ import annotations

import argparse
import json
import platform
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / 'Runtime' / 'Marble_Oracle_App'
sys.path.insert(0, str(APP))

from Augurspex.augurspex import providers  # noqa: E402
from Augurspex.augurspex.providers import MarketRouter, ProviderError  # noqa: E402


def starter_markets() -> list[dict]:
    data = json.loads((APP / 'Augurspex' / 'augurspex' / 'default_watchlist.json').read_text(encoding='utf-8'))
    return [row for row in data['stocks'] if isinstance(row, dict) and row.get('symbol')]


def age_days(stamp: str, now: datetime) -> float | None:
    try:
        when = datetime.fromisoformat(str(stamp).replace('Z', '+00:00'))
    except ValueError:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return (now - when).total_seconds() / 86400


def probe(period: str) -> list[dict]:
    now = datetime.now(timezone.utc)
    rows = []
    with tempfile.TemporaryDirectory(prefix='augurspex-probe-') as cache:
        router = MarketRouter(cache_dir=cache)
        for market in starter_markets():
            symbol = market['symbol']
            routes = router._routes(symbol, 'auto', period)
            if not routes:
                rows.append({'symbol': symbol, 'sector': market.get('sector', ''), 'source': '-',
                             'outcome': 'not_configured', 'bars': 0, 'latest': '', 'age_days': None,
                             'close_only': None, 'seconds': 0.0,
                             'detail': 'no source without a key supports this market at this interval'})
                continue
            for source in routes:
                started = time.monotonic()
                row = {'symbol': symbol, 'sector': market.get('sector', ''), 'source': source}
                try:
                    result = router.fetch(symbol, period, source)
                    candles = result.get('candles') or []
                    latest = str(result.get('latest_observation') or '')
                    row.update(outcome='ok', bars=len(candles), latest=latest[:19], age_days=age_days(latest, now),
                               close_only=bool(candles and candles[-1].get('close_only')), detail='')
                except ProviderError as error:
                    row.update(outcome=error.kind or 'provider_failure', bars=0, latest='', age_days=None,
                               close_only=None, detail=str(error)[:140])
                row['seconds'] = round(time.monotonic() - started, 1)
                rows.append(row)
                print(f"{symbol:10s} {source:20s} {row['outcome']:17s} bars={row['bars']:<4d} "
                      f"latest={row['latest'] or '-':19s} {row['detail']}", flush=True)
    return rows


def summarise(rows: list[dict]) -> list[dict]:
    """One line per market: the first source (in router order) that answered."""
    summary = []
    for symbol in dict.fromkeys(row['symbol'] for row in rows):
        mine = [row for row in rows if row['symbol'] == symbol]
        working = [row for row in mine if row['outcome'] == 'ok']
        summary.append({
            'symbol': symbol, 'sector': mine[0]['sector'],
            'chart_without_key': bool(working),
            'first_working_source': working[0]['source'] if working else '',
            'working_sources': [row['source'] for row in working],
            'failed_sources': {row['source']: row['outcome'] for row in mine if row['outcome'] != 'ok'},
            'newest_observation': max((row['latest'] for row in working), default=''),
        })
    return summary


def markdown(rows: list[dict], summary: list[dict], period: str) -> str:
    stamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    good = sum(1 for row in summary if row['chart_without_key'])
    out = [f'# AUGURSPEX live provider probe - interval {period}', '',
           f'Run {stamp} on {platform.system()} ({platform.node() or "unknown host"}). '
           f'No API keys were configured. No prices are recorded here.', '',
           f'**{good} of {len(summary)} starter markets returned validated history from at least one no-key source.**', '',
           '## Per market', '',
           '| Market | Type | Chart without a key | First source that answered | Also answered | Failed (kind) | Newest observation |',
           '|---|---|---|---|---|---|---|']
    for row in summary:
        failed = ', '.join(f'{name} ({kind})' for name, kind in row['failed_sources'].items()) or '-'
        out.append(f"| {row['symbol']} | {row['sector']} | {'yes' if row['chart_without_key'] else '**no**'} | "
                   f"{row['first_working_source'] or '-'} | {', '.join(row['working_sources'][1:]) or '-'} | "
                   f"{failed} | {row['newest_observation'] or '-'} |")
    out += ['', '## Per source', '', '| Source | Markets asked | Answered | Failure kinds |', '|---|---|---|---|']
    for source in dict.fromkeys(row['source'] for row in rows):
        mine = [row for row in rows if row['source'] == source]
        kinds: dict[str, int] = {}
        for row in mine:
            if row['outcome'] != 'ok':
                kinds[row['outcome']] = kinds.get(row['outcome'], 0) + 1
        name = providers.SOURCE_INFO.get(source, {}).get('name', source)
        out.append(f"| {name} (`{source}`) | {len(mine)} | {sum(1 for row in mine if row['outcome'] == 'ok')} | "
                   f"{', '.join(f'{kind} x{count}' for kind, count in kinds.items()) or '-'} |")
    out += ['', 'A source that answered here can still refuse a different network or a later request. '
                'Treat this as evidence for the date above, not as a guarantee.', '']
    return '\n'.join(out)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--period', default='D', help='interval code (D, W, M, 60, ...). Default D')
    parser.add_argument('--json', type=Path)
    parser.add_argument('--markdown', type=Path)
    args = parser.parse_args()
    rows = probe(args.period.upper())
    summary = summarise(rows)
    report = markdown(rows, summary, args.period.upper())
    print('\n' + report)
    if args.markdown:
        args.markdown.write_text(report, encoding='utf-8')
    if args.json:
        args.json.write_text(json.dumps({'period': args.period.upper(), 'rows': rows, 'summary': summary}, indent=1),
                             encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
