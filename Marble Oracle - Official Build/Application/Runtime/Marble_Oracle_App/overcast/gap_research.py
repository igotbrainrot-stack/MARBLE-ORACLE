"""Evidence-gap identification and bounded, point-in-time safe *cached* retrieval.

No autonomous URL browsing, no external search keys, no scraping. Retrieved
articles can only come from the already cached and timestamp-eligible corpus.
"""
from __future__ import annotations

from collections import Counter
from .research import words, publisher_key, eligible


def planner_prompt(question, packet):
    import json
    return ('Inspect this prediction and RSS packet for crucial missing or CONFLICTING information. '
            'Produce JSON only with: "gaps" (1..3 short testable evidence questions), '
            '"support_terms" (1..6 specific search terms), '
            '"disconfirm_terms" (1..6 specific search terms arguing AGAINST the forecast). '
            'Use precise named entities and processes, not generic words like news or politics. '
            'Do not invent sources or imply a search has happened. This will search ONLY the local cached RSS database. '
            f'Question: {json.dumps(question,ensure_ascii=False)}\nAvailable evidence: {packet["text"]}')


def validate_plan(plan):
    if not isinstance(plan,dict):raise ValueError('Gap plan must be JSON object.')
    out={}
    for key,limit in [('gaps',3),('support_terms',6),('disconfirm_terms',6)]:
        values=plan.get(key)
        if not isinstance(values,list) or len(values)>limit or (key=='gaps' and not values):
            raise ValueError('Gap research plan missing or exceeds allowed '+key)
        if any(not isinstance(v,str) or not v.strip() or len(v)>120 for v in values):
            raise ValueError('Gap research plan contains invalid '+key)
        out[key]=[' '.join(v.split()) for v in values]
    if not out['disconfirm_terms']:
        raise ValueError('Gap search must seek at least one disconfirming lead.')
    return out


def retrieve_gap_evidence(plan, pool, current_ids, *, as_of, max_items=6, max_age_days=14):
    """Approximate term matches; does not certify contradictory evidence exists."""
    excluded=set(current_ids)
    positive=[words(t) for t in plan['support_terms']]
    negative=[words(t) for t in plan['disconfirm_terms']]
    candidates=[]
    for row in pool:
        if row['id'] in excluded or not eligible(row,as_of=as_of,max_age_days=max_age_days):continue
        tokens=words(row.get('title','')+' '+row.get('summary',''))
        pos=sum(min(3,len(tokens & terms)) for terms in positive)
        neg=sum(min(3,len(tokens & terms)) for terms in negative)
        if not (pos or neg):continue
        candidates.append((neg,pos,row))
    # Favor disconfirming terms first, then support leads; diversifies publishers.
    candidates.sort(key=lambda c:(-bool(c[0]),-max(c[0],c[1]),-c[0],-c[1],c[2]['id']))
    used=Counter(); selected=[]
    for neg,pos,row in candidates:
        source=publisher_key(row)
        if used[source]>=2:continue
        selected.append({'article':row,'matched_disconfirm_terms':bool(neg),
                         'warning':'Keyword match is a lead, NOT verified supporting or contrary evidence.'})
        used[source]+=1
        if len(selected)>=max_items:break
    return selected
