"""Model-assisted *reported claim* extraction with exact-quote provenance.

No extracted item is automatically a confirmed fact or causal connection.
Every claim has one immutable RSS article ID and a verifiable excerpt span.
"""
from __future__ import annotations
from datetime import date
import re

KINDS={'reported_action','announced_intent','policy_change','trade_dependency',
       'financial_change','public_statement','reported_conflict','other'}


def extraction_prompt(packet):
    return ('''From the RSS titles and excerpts ONLY, extract 0..12 directly reported event CLAIMS.
Return one JSON object with "claims": list of objects with keys:
"article_id" (integer ID from evidence), "actor" (named actor), "action" (short verb phrase),
"target" (named entity, group or country; empty if unavailable), "location" (country/place or empty),
"event_date" (ISO YYYY-MM-DD ONLY if the excerpt explicitly reports it; otherwise null),
"kind" (one of reported_action, announced_intent, policy_change, trade_dependency,
financial_change, public_statement, reported_conflict, other),
"evidence_quote" (EXACT contiguous fragment of the supplied headline or RSS excerpt),
"claim_text" (short neutral paraphrase attributed to the source).
Never infer hidden motives or assert causation. Dates, identities, actions and quotes must
be grounded in that one article. An event may be planned or merely alleged.
The list may be empty. Return JSON only.
AS-OF: '''+packet['as_of_utc']+'\nARTICLES: '+packet['text'])


def validate_claims(raw, rows, *, as_of):
    by_id={r['id']:r for r in rows}
    claims=raw.get('claims')
    if not isinstance(claims,list) or len(claims)>12:
        raise ValueError('Event extraction returned invalid number of claims (max 12).')
    out=[]; seen=set()
    for claim in claims:
        if not isinstance(claim,dict) or type(claim.get('article_id')) is not int or claim['article_id'] not in by_id:
            raise ValueError('Event extraction cited an unknown article.')
        quote=claim.get('evidence_quote')
        if not isinstance(quote,str) or len(quote)<6 or len(quote)>300:
            raise ValueError('Event extraction must cite an exact short evidence quote.')
        article=by_id[claim['article_id']]
        # Ignore superficial spacing differences but DO NOT fuzzy-match or accept hallucinations.
        canonical=lambda s:re.sub(r'\s+',' ',s).strip().casefold()
        if not any(canonical(quote) in canonical(chunk) for chunk in (article['title'], article.get('summary') or '')):
            raise ValueError('Extracted quote was not present in its source article excerpt.')
        if claim.get('kind') not in KINDS:raise ValueError('Unsupported event claim kind.')
        obj={'article_id':claim['article_id'],'evidence_quote':quote.strip(),'kind':claim['kind']}
        for key,limit in [('actor',140),('action',160),('target',160),('location',140),('claim_text',480)]:
            v=claim.get(key)
            if not isinstance(v,str) or len(v)>limit or (key in ('actor','action','claim_text') and not v.strip()):
                raise ValueError('Missing or invalid event attribute '+key)
            obj[key]=' '.join(v.split())
        event_day=claim.get('event_date')
        if event_day is not None:
            if not isinstance(event_day,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',event_day):
                raise ValueError('Event date must be ISO or null.')
            try: parsed=date.fromisoformat(event_day)
            except ValueError as exc:raise ValueError('Invalid event date.') from exc
            # Date must appear explicitly somewhere in the cited local excerpt.
            # Conservative: reject relative dates or unstated inferred years.
            source=(article['title']+' '+(article.get('summary') or '')).casefold()
            representations=(event_day, f'{parsed.day} {parsed.strftime("%B")} {parsed.year}',
                             f'{parsed.strftime("%B")} {parsed.day}, {parsed.year}',
                             f'{parsed.strftime("%b")} {parsed.day}, {parsed.year}')
            if not any(stamp.casefold() in source for stamp in representations):
                raise ValueError('Event date is not explicit in its cited RSS excerpt.')
            # Future event dates can occur in announced plans, but are not verified actual occurrences.
            if parsed>as_of.date() and claim['kind'] not in ('announced_intent','public_statement'):
                raise ValueError('Future event date cannot be treated as an occurrence.')
        obj['event_date']=event_day
        obj['status']='unverified_reported_claim'
        k=(obj['article_id'],obj['evidence_quote'].casefold(),obj['actor'],obj['action'])
        if k not in seen:out.append(obj);seen.add(k)
    return out


def relationship_leads(claims, max_pairs=100):
    """Transparent shared-actor leads, never an inferred conspiracy or proved causation."""
    from .research import words
    pairs=[]
    for i,a in enumerate(claims):
        for b in claims[i+1:]:
            if a['article_id']==b['article_id']:continue
            shared=words(a['actor']) & words(b['actor'])
            if not shared:continue
            pairs.append({'from_claim':a['id'],'to_claim':b['id'],
                          'shared_actor_terms':sorted(shared),
                          'relation':'unverified_shared_actor',
                          'warning':'Named-actor overlap is not proof of a causal or coordinated relationship.'})
            if len(pairs)>=max_pairs:return pairs
    return pairs
