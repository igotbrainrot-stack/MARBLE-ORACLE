"""Transparent conditional occurrence-time distributions; never dates of certainty.

The event-YES probability is estimated elsewhere. This separate distribution
answers: *assuming the event occurs by the deadline*, when might it happen?
The model estimates are NOT calibrated; all checkpoints are software-selected.
"""
from __future__ import annotations

from datetime import date, timedelta
import math


def checkpoints(as_of: date, deadline: date, buckets: int = 5):
    days=(deadline-as_of).days
    if days < 1:
        raise ValueError('Deadline must be after as-of.')
    count=min(max(1,buckets),days)
    offsets=sorted({math.ceil(days*i/count) for i in range(1,count+1)})
    return [(as_of+timedelta(days=d)).isoformat() for d in offsets]


def timing_prompt(question, packet, dates):
    import json
    return ('You are estimating TIMING CONDITIONAL ON the YES event happening by the deadline. '
            'Do NOT revise the separate P(YES) estimate. Every checkpoint date is provided by software. '
            'Do not invent scheduled dates, sources, or precise event dates. Return one JSON object with keys: '
            '"checkpoints" (list of objects {"date": ISO date, "conditional_cumulative_percent": numeric 0..100}; '
            'exactly the supplied dates and order; final entry must equal 100), '
            '"timing_reasoning" (text), "evidence_article_ids" (actual article ID integers). '
            'Your subjective timing distribution is NOT historically calibrated. Be uncertain when evidence is sparse. '
            f'Question and resolution: {json.dumps(question,ensure_ascii=False)}\n'
            f'Checkpoints: {json.dumps(dates)}\n'
            f'As-of UTC: {packet["as_of_utc"]}\n'
            f'RSS excerpts only: {packet["text"]}')


def validate_timing(output, expected_dates, allowed_ids, event_probability):
    if isinstance(event_probability,bool) or not isinstance(event_probability,(int,float)) or not 0 <= event_probability <= 1:
        raise ValueError('Event probability must be a fraction 0..1.')
    raw=output.get('checkpoints')
    if not isinstance(raw,list) or len(raw)!=len(expected_dates):
        raise ValueError('Timing output needs exactly the supplied checkpoints.')
    last=0.0; entries=[]
    for i,(row,day) in enumerate(zip(raw,expected_dates)):
        if not isinstance(row,dict) or row.get('date')!=day:
            raise ValueError('Timing output changed checkpoint dates or order.')
        p=row.get('conditional_cumulative_percent')
        if isinstance(p,bool) or not isinstance(p,(int,float)) or not math.isfinite(p) or not last<=p<=100:
            raise ValueError('Conditional timing cumulative probabilities must be monotone 0..100.')
        if i==len(raw)-1 and abs(p-100)>1e-6:
            raise ValueError('Final conditional checkpoint must be exactly 100%.')
        conditional_bucket=(float(p)-last)/100
        entries.append({'end_date':day,'conditional_cdf':round(p/100,6),
                        'conditional_bucket':round(conditional_bucket,6),
                        'unconditional_event_bucket':round(conditional_bucket*event_probability,6)})
        last=float(p)
    ids=output.get('evidence_article_ids')
    if not isinstance(ids,list) or any(type(i) is not int or i not in allowed_ids for i in ids):
        raise ValueError('Timing evidence references unprovided article IDs.')
    explanation=output.get('timing_reasoning')
    if not isinstance(explanation,str) or not explanation.strip():
        raise ValueError('Timing reasoning is required.')
    return {'method':'subjective-conditional-cdf-v1', 'calibrated':False,
            'checkpoints':entries,'event_probability':event_probability,
            'non_occurrence_probability':round(1-event_probability,6),
            'reasoning':' '.join(explanation.split())[:1600],
            'cited_article_ids':list(dict.fromkeys(ids)),
            'warning':'Model-estimated timing conditional on event occurring, NOT a scheduled date or validated forecast.'}
