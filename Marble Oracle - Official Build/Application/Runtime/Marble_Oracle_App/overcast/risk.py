"""Bounded investigation and topic focus. No inference about secret motives is treated as fact.

Keyword tagging is a transparent, deterministic navigation aid, NOT a source-quality
score, article classifier trained on data, or a probability adjustment.
"""
from __future__ import annotations
from functools import lru_cache
import re

TOPICS = {
    'TRADE': ('tariff', 'tariffs', 'imports', 'exports', 'sanction', 'sanctions', 'export control', 'export controls', 'import duty', 'supply chain',
              'trade agreement', 'trade deal', 'wto', 'trade deficit', 'shipping lane',
              'container ship', 'semiconductor ban', 'critical mineral', 'critical minerals', 'trade war',
              'export ban', 'embargo', 'customs'),
    'MARKETS': ('interest rate', 'central bank', 'stock market', 'bond yield', 'inflation',
                'federal reserve', 'ecb', 'rba', 'exchange rate', 'recession', 'oil price',
                'currency', 'gdp', 'unemployment', 'equities', 'market selloff',
                'debt', 'commodity', 'economic growth', 'banking'),
    'CRISES': ('earthquake', 'flood', 'floods', 'cyclone', 'hurricane', 'typhoon', 'wildfire',
               'tsunami', 'volcano', 'drought', 'famine', 'outbreak', 'epidemic', 'pandemic',
               'humanitarian', 'refugees', 'displaced', 'displacement', 'coup', 'insurgency',
               'civil war', 'airstrike', 'airstrikes', 'missile', 'massacre', 'evacuation',
               'state of emergency', 'blackout', 'cyberattack', 'debt default', 'sovereign default',
               'bank run'),
    'WORLD POLITICS': ('election', 'parliament', 'president', 'prime minister',
                       'government', 'diplomacy', 'security council', 'united nations',
                       'military', 'ceasefire', 'treaty', 'conflict', 'border', 'war',
                       'coalition', 'minister', 'geopolitic', 'foreign policy',
                       'legislation', 'summit', 'defence', 'defense'),
}


_TOPIC_PATTERNS = {category: re.compile(r'(?<!\w)(?:' + '|'.join(re.escape(t) for t in terms) + r')(?!\w)')
                   for category, terms in TOPICS.items()}


@lru_cache(maxsize=16384)
def _topic_hits(text):
    return tuple(category for category, pattern in _TOPIC_PATTERNS.items() if pattern.search(text))


def focus_tags(article):
    """Return matched focus areas for a cached headline/excerpt, with no causal assertions."""
    words = ' '.join((str(article.get('title') or ''), str(article.get('summary') or ''),
                      str(article.get('category') or ''))).lower()
    hits = list(_topic_hits(words))
    if not hits and article.get('category') == 'trade':
        return ['TRADE']
    if not hits and article.get('category') == 'business':
        return ['MARKETS']
    if not hits and article.get('category') == 'crisis':
        return ['CRISES']
    return hits


def investigation_prompt(dossier, question):
    """One local investigative pass after question selection; only provided RSS evidence."""
    return ('''Investigate competing explanations and potential strategic incentives for this
forecast. Use a PESSIMISTIC / DOWNSIDE risk lens, but do NOT automatically make the
outcome more likely. Consider power, economic interests, retaliation, bargaining,
trade dependence, supply chains, liquidity, market reaction, policy constraints,
and second-order effects ONLY where relevant to these supplied articles.

Challenge the public explanation with possible other incentives, but NEVER claim
an undisclosed motive is proven. Do not imply bribery, coordination, deception,
or criminal conspiracy without explicit credible evidence. A suspected link,
correlation or timing coincidence is NOT causation. Present an ordinary or benign
alternative for every motive/connection. Do not invent external actors, documents,
price data, prior history, or unpublished negotiations. Do not recommend trades.

Return exactly ONE JSON object with keys:
"actors": array of max 5 objects with keys "actor", "observed_action",
"possible_incentive", "alternative_explanation", "evidence_article_ids" (integers);
"connections": array of max 5 objects with keys "from", "to", "mechanism_hypothesis",
"noncausal_alternative", "disconfirming_signal", "evidence_article_ids" (integers);
"downside_path" (string, conditional chain, not asserted future fact),
"stabilising_path" (string, credible competing chain),
"watch_signals" (array of at most 6 public measurable signposts, strings).
Evidence IDs must be in the supplied article packet. Use empty arrays if no
credible actors or links can be proposed. A headline is not independent proof.

QUESTION: ''' + question['question'] + '\nCROSS-SECTOR RESEARCH LEADS (NOT causal evidence): ' +
            str(dossier.get('cross_sector_bridges', [])) + '\nAS-OF: ' + dossier['as_of_utc'] +
            '\nRSS EVIDENCE (only this):\n' + dossier['text'])


def _text(value, max_len=1000):
    if not isinstance(value, str):
        raise ValueError('Investigation field must be text.')
    return ' '.join(value.split())[:max_len]


def validate_investigation(raw, allowed_ids):
    """Reject fabricated evidence references and structurally invalid investigation."""
    if not isinstance(raw, dict):
        raise ValueError('Investigation must be a JSON object.')
    result = {}
    fields = {
        'actors': ('actor', 'observed_action', 'possible_incentive', 'alternative_explanation', 'evidence_article_ids'),
        'connections': ('from', 'to', 'mechanism_hypothesis', 'noncausal_alternative',
                        'disconfirming_signal', 'evidence_article_ids'),
    }
    for group, required in fields.items():
        rows = raw.get(group)
        if not isinstance(rows, list) or len(rows) > 5:
            raise ValueError(f'{group} must be an array of at most five items.')
        clean = []
        for item in rows:
            if not isinstance(item, dict):
                raise ValueError(f'Invalid {group} entry.')
            ids = item.get('evidence_article_ids')
            if not isinstance(ids, list) or not ids or any(type(v) is not int or v not in allowed_ids for v in ids):
                raise ValueError(f'{group} contains unsupported article IDs.')
            clean.append({k: list(dict.fromkeys(ids)) if k == 'evidence_article_ids'
                          else _text(item.get(k), 800) for k in required})
            if any(not clean[-1][key] for key in required if key != 'evidence_article_ids'):
                raise ValueError(f'{group} has an empty required field.')
        result[group] = clean
    for key in ('downside_path', 'stabilising_path'):
        result[key] = _text(raw.get(key), 1800)
        if not result[key]:
            raise ValueError(f'Missing {key}.')
    watch = raw.get('watch_signals')
    if not isinstance(watch, list) or len(watch) > 6 or any(not isinstance(x, str) for x in watch):
        raise ValueError('watch_signals must be an array of at most six strings.')
    result['watch_signals'] = [_text(x, 320) for x in watch if x.strip()]
    result['method_note'] = ('Evidence-limited speculative scenarios; incentives are hypotheses, '
                             'coincident news does not establish a causal connection.')
    return result
