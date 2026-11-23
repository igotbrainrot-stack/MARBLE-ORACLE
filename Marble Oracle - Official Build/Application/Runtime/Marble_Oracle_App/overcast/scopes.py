"""Transparent, bounded selection of cached news for broad intelligence requests.

This does not scrape the web or imply complete world-market coverage. It returns
representative *cached* RSS evidence; publisher domains are not independent facts.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

from .research import eligible, publisher_key, words
from .risk import focus_tags

SCOPES = (
    'SELECTED HEADLINES',
    'GLOBAL EVENTS',
    'WORLD POLITICS',
    'GLOBAL MARKETS',
    'TRADE & SUPPLY CHAINS',
    'CRISES & DISASTERS',
    'GEOPOLITICS + MARKETS',
    'ALL CACHED NEWS',
    'CUSTOM SUBJECT',
)


def _match(row, scope, query):
    tags = set(focus_tags(row))
    if scope == 'GLOBAL EVENTS':
        return bool(tags & {'WORLD POLITICS', 'TRADE', 'MARKETS', 'CRISES'}) or row.get('category') in ('world', 'australia', 'crisis')
    if scope == 'WORLD POLITICS':
        return 'WORLD POLITICS' in tags
    if scope == 'GLOBAL MARKETS':
        return 'MARKETS' in tags
    if scope == 'TRADE & SUPPLY CHAINS':
        return 'TRADE' in tags
    if scope == 'CRISES & DISASTERS':
        return 'CRISES' in tags
    if scope == 'GEOPOLITICS + MARKETS':
        return bool(tags & {'WORLD POLITICS', 'MARKETS', 'TRADE'})
    if scope == 'ALL CACHED NEWS':
        return True
    if scope == 'CUSTOM SUBJECT':
        terms = words(query)
        return bool(terms) and bool(terms & words(' '.join((row.get('title',''),row.get('summary','')))))
    raise ValueError('Choose a valid coverage scope.')


def _sort_key(row):
    val=row.get('published') or row.get('collected') or ''
    try:
        parsed=datetime.fromisoformat(val.replace('Z','+00:00'))
        if parsed.tzinfo is None: parsed=parsed.replace(tzinfo=timezone.utc)
        return (parsed.astimezone(timezone.utc),int(row['id']))
    except (ValueError,KeyError):
        return (datetime.min.replace(tzinfo=timezone.utc),int(row.get('id',0)))


def select_coverage(rows, scope, *, query='', limit=16, as_of=None):
    """Deduplicate near-identical headlines and diversify cached publisher domains.

    The cap is intentional because the local model has finite context. Return
    all population counts alongside selected IDs so summaries cannot masquerade
    as comprehensive global coverage.
    """
    if scope not in SCOPES or scope == 'SELECTED HEADLINES':
        raise ValueError('Select a broad coverage scope, not individual headlines.')
    if scope == 'CUSTOM SUBJECT' and not words(query):
        raise ValueError('Enter a meaningful subject for the CUSTOM SUBJECT scope.')
    limit=max(1,min(int(limit),24))
    cutoff=as_of or datetime.now(timezone.utc)
    matched=[row for row in rows if _match(row,scope,query)]
    current=[row for row in matched if eligible(row,as_of=cutoff,max_age_days=14)]
    current.sort(key=_sort_key,reverse=True)
    by_domain=Counter()
    chosen=[]
    seen_titles=set()
    # Two passes: first maximize outlet diversity, then allow a few more
    # articles from each outlet if there is remaining room.
    for cap in (2,5,limit):
        for row in current:
            if len(chosen)>=limit: break
            if row in chosen: continue
            host=publisher_key(row)
            if by_domain[host]>=cap:continue
            heading=' '.join((row.get('title') or '').lower().split())
            if heading in seen_titles:  # exact headline repeat, never independent evidence
                continue
            chosen.append(row)
            seen_titles.add(heading)
            by_domain[host]+=1
        if len(chosen)>=limit:break
    return {
        'scope':scope, 'query':query.strip(), 'matched_count':len(matched),
        'fresh_count':len(current), 'skipped_old_or_future':len(matched)-len(current),
        'selected_count':len(chosen), 'article_ids':[row['id'] for row in chosen],
        'publisher_count':len({publisher_key(row) for row in chosen}),
        'selected_domains':sorted({publisher_key(row) for row in chosen}),
        'coverage_warning':('Limited to cached RSS excerpts collected within 14 days. '
                            'This is not comprehensive coverage of world events or financial markets. '
                            'Domain counts do not prove independent reporting.'),
    }
