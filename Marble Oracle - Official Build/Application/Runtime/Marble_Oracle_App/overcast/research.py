"""Deterministic, explainable retrieval and event grouping for RSS excerpts.

No network, embedding service, external dependencies, or model calls.
Grouping means topical similarity, never factual corroboration.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone, timedelta
from functools import lru_cache
import math
import re
from urllib.parse import urlsplit

STOP = set('''a an and are as at be been being by can could did do does for from has have
in into is it its may might more new no not of on or our over said say says some than
that the their there these this those to today tomorrow under up was were what when
where which who will with would world after before about amid update latest report
reports news live briefing first last now year years day days week weeks month months
plans plan set official government governments country countries people person according
'''.split())
TOKEN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)?", re.I)
MAX_POOL = 500


@lru_cache(maxsize=16384)
def _tokens(text):
    return tuple(TOKEN.findall(text.lower()))


@lru_cache(maxsize=16384)
def _word_set(text):
    return frozenset(t for t in _tokens(text) if len(t) >= 3 and t not in STOP)


def words(text):
    """Content words (cached: retrieval compares the same headlines many times)."""
    return set(_word_set(text or ''))


def publisher_key(article):
    """Count publishers by host, not number of headlines or RSS subscriptions.

    A distinct domain does NOT prove independent reporting, especially wire copies.
    """
    host=(urlsplit(article.get('url','')).hostname or '').lower()
    if host.startswith('www.'):
        host=host[4:]
    return host or 'unknown'


def _timestamp(article):
    s=article.get('published') or article.get('collected') or ''
    try:
        val=datetime.fromisoformat(s.replace('Z','+00:00'))
        if not val.tzinfo:val=val.replace(tzinfo=timezone.utc)
        return val.astimezone(timezone.utc)
    except ValueError:
        return None


def eligible(article, *, as_of=None, max_age_days=14):
    """Point-in-time safety: both publication AND first observation precede as_of."""
    now=as_of or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError('as_of must have a timezone')
    for key in ('published','collected'):
        s=article.get(key)
        if s:
            try:
                stamp=datetime.fromisoformat(s.replace('Z','+00:00'))
                if stamp.tzinfo is None:stamp=stamp.replace(tzinfo=timezone.utc)
                if stamp > now: return False
            except ValueError:
                return False
    stamp=_timestamp(article)
    return bool(stamp and now - timedelta(days=max_age_days) <= stamp <= now)


def _weights(rows):
    df=Counter()
    for row in rows:
        df.update(words(row.get('title','')))
    size=len(rows)
    return {w:1 + math.log((size+1)/(freq+1)) for w,freq in df.items()}


def similarity(a, b, weights=None):
    """Weighted headline Jaccard + shared bigrams; favors specific entities."""
    aw,bw=_word_set(a.get('title') or ''),_word_set(b.get('title') or '')
    common=aw & bw
    if not common:return 0.0
    # Require specific overlap; one generic token is not enough.
    if len(common)<2 and min(len(aw),len(bw))>2:return 0.0
    weights=weights or {}
    shared=sum(weights.get(w,1) for w in common)
    all_=sum(weights.get(w,1) for w in aw|bw)
    jaccard=shared/all_ if all_ else 0.0
    seq_a=_tokens(a.get('title') or '')
    seq_b=_tokens(b.get('title') or '')
    bigrams_a=set(zip(seq_a,seq_a[1:]))
    bigrams_b=set(zip(seq_b,seq_b[1:]))
    bonus=0.12 if bigrams_a & bigrams_b else 0.0
    return min(1.0,jaccard+bonus)


def _sort_recent(row):
    return (_timestamp(row) or datetime.min.replace(tzinfo=timezone.utc),int(row.get('id',0)))


def find_related(seeds, pool, *, as_of=None, days=14, max_items=18, threshold=0.32):
    """Expand user-selected stories with similar cached reports, no future web search.

    Never silently replace the user's selected evidence; selected items remain first.
    Diversifies by publisher while retaining a maximum of two per publisher in expansion.
    """
    selected={int(s['id']):s for s in seeds}
    pool=[p for p in pool if eligible(p,as_of=as_of,max_age_days=days)]
    weights=_weights(pool)
    others=[]
    for row in pool:
        if row['id'] in selected:continue
        best=max((similarity(row,s,weights) for s in seeds),default=0.0)
        if best>=threshold:others.append((best,row))
    others.sort(key=lambda sr:(-sr[0],-(_timestamp(sr[1]) or datetime.min.replace(tzinfo=timezone.utc)).timestamp()))
    picked=list(selected.values())
    per_publisher=Counter(publisher_key(p) for p in picked)
    for _,row in others:
        if len(picked)>=max_items:break
        key=publisher_key(row)
        if per_publisher[key]>=2:continue
        picked.append(row);per_publisher[key]+=1
    return picked


def news_events(rows, *, as_of=None, days=14, max_events=100):
    """Transparent event candidates for UI: greedy grouping, not entity resolution."""
    usable=[r for r in rows[:MAX_POOL] if eligible(r,as_of=as_of,max_age_days=days)]
    usable.sort(key=_sort_recent,reverse=True)
    unseen={r['id'] for r in usable}; groups=[]
    weights=_weights(usable)
    for seed in usable:
        if seed['id'] not in unseen:continue
        unseen.remove(seed['id']);members=[seed]
        for other in usable:
            if other['id'] in unseen and any(similarity(other,m,weights)>=0.36 for m in members[:6]):
                unseen.remove(other['id']);members.append(other)
        members.sort(key=_sort_recent,reverse=True)
        publishers=sorted(set(publisher_key(m) for m in members))
        groups.append({'event_id':seed['id'],'title':seed['title'],
            'article_ids':[m['id'] for m in members], 'articles':len(members),
            'publishers':publishers,'publisher_count':len(publishers),
            'newest':(_timestamp(members[0]) or datetime.now(timezone.utc)).isoformat()})
        if len(groups)>=max_events:break
    return groups


EXCERPT_STEPS=(850,600,420,280,160)


def dossier(rows, *, as_of=None, max_chars=27000):
    """Bounded sourced packet for the local model with repeat-coverage caveats.

    When the packet would exceed the context budget, RSS excerpts are shortened
    step by step (every article is kept, headlines are never cut) and the
    truncation is recorded as a caution. Only if even the shortest excerpts do
    not fit is the request rejected.
    """
    rows=list(rows)
    if not rows:raise ValueError('No evidence supplied.')
    publishers=sorted({publisher_key(r) for r in rows})
    weights=_weights(rows)
    repeats=[]
    for i,a in enumerate(rows):
        for b in rows[i+1:]:
            if similarity(a,b,weights)>0.84:
                repeats.append([a['id'],b['id']])
    import json
    lines=packet=None
    excerpt_chars=EXCERPT_STEPS[0]
    for excerpt_chars in EXCERPT_STEPS:
        lines=[]
        for row in rows:
            date=row.get('published') or 'publication date unknown'
            lines.append({'id':row['id'],'publisher':row['source'],'domain':publisher_key(row),
                 'title':row['title'],'published_utc':date,
                 'rss_excerpt':(row.get('summary') or '')[:excerpt_chars],
                 'url':row['url'],'first_seen_utc':row.get('collected','')})
        packet=json.dumps(lines,ensure_ascii=False)
        if len(packet)<=max_chars:
            break
    if len(packet)>max_chars:
        raise ValueError(f'Evidence packet ({len(rows)} items) exceeds the local context budget even with '
                         'shortened excerpts. Select fewer headlines or raise MODEL CONTEXT.')
    trimmed=excerpt_chars<EXCERPT_STEPS[0] and any(len(r.get('summary') or '')>excerpt_chars for r in rows)
    cautions=[]
    if trimmed:
        cautions.append(f'RSS excerpts shortened to {excerpt_chars} characters to fit the local model context budget.')
    if len(publishers)<2:cautions.append('ONE PUBLISHER ONLY; no cross-outlet reporting.')
    if repeats:cautions.append('Near-duplicate headlines may be syndicated; do not count as independent confirmation.')
    if any(not r.get('published') for r in rows):cautions.append('Some RSS items lack publication dates.')
    if any(not r.get('summary') for r in rows):cautions.append('Some reports only contain headlines, not article context.')
    cautions.append('Different publisher domains are NOT proof of independent evidence or factual accuracy.')
    return {'articles':lines,'text':packet,'article_ids':[r['id'] for r in rows],
            'publisher_domains':publishers,'publisher_count':len(publishers),
            'near_duplicate_pairs':repeats,'cautions':cautions,'excerpt_chars':excerpt_chars,
            'as_of_utc':(as_of or datetime.now(timezone.utc)).isoformat()}


def cross_sector_bridges(seeds, pool, already, *, as_of=None, days=14, max_items=4):
    """Suggest cached related-but-not-duplicated stories from other risk sectors.

    Transparent lexical overlap is only a retrieval hint. A shared actor/entity
    is neither proof of a financial link nor evidence of coordination. Any
    resulting causal explanation must be explicitly labeled a hypothesis.
    """
    from .risk import focus_tags
    excluded = {int(r['id']) for r in already}
    seed_words = set().union(*(words(s.get('title', '')) for s in seeds))
    seed_tags = set().union(*(focus_tags(s) for s in seeds))
    results = []
    for candidate in pool:
        if candidate['id'] in excluded or not eligible(candidate,as_of=as_of,max_age_days=days):
            continue
        tags = set(focus_tags(candidate))
        if not tags or not (tags-seed_tags):
            continue
        overlap = seed_words & words(candidate.get('title',''))
        # Do not connect arbitrary stories based on general macroeconomic words.
        overlap -= {'trade', 'market', 'world', 'rate', 'rates', 'bank', 'news', 'growth',
                    'economic', 'policy', 'global', 'crisis', 'business', 'markets', 'price'}
        if not overlap:
            continue
        results.append((len(overlap), candidate, sorted(overlap)[:4], sorted(tags - seed_tags)))
    results.sort(key=lambda x:(-x[0],-(_timestamp(x[1]) or datetime.min.replace(tzinfo=timezone.utc)).timestamp()))
    seen_publishers=Counter()
    picked=[]
    for score, row, overlap, new_tags in results:
        host=publisher_key(row)
        if seen_publishers[host]>=1:continue
        picked.append({'article':row, 'shared_terms':overlap, 'new_focus':new_tags,
                       'warning':'Shared headline terms are retrieval clues, NOT evidence of causal connection.'})
        seen_publishers[host]+=1
        if len(picked)>=max_items:break
    return picked
