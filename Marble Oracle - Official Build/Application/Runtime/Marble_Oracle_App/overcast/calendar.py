"""Forecast calendar: model-estimated windows, deadlines, and reported scheduled dates.

All-day DATE values carry no fabricated timezone or clock time. No estimated
window is ever silently presented as a confirmed schedule.
"""
from __future__ import annotations
from datetime import date, datetime, timedelta, timezone
from calendar import monthrange
import re

TYPES = {
    'forecast_window': 'MODEL-ESTIMATED WINDOW',
    'forecast_deadline': 'FORECAST RESOLUTION DEADLINE',
    'forecast_timing_bucket': 'MODEL-ESTIMATED PROBABILITY BUCKET',
    'reported_schedule': 'USER-RECORDED SCHEDULE (UNVERIFIED)',
}


def iso_day(s):
    if not isinstance(s, str):
        raise ValueError('Date must be a YYYY-MM-DD string.')
    try:
        if not re.fullmatch(r'\d{4}-\d\d-\d\d', s):
            raise ValueError()
        return date.fromisoformat(s)
    except ValueError as exc:
        raise ValueError('Date must be a valid YYYY-MM-DD day.') from exc


def validate_window(start, end, *, earliest, deadline):
    """Dates suggested by a model are bounded to (as-of, forecast deadline]."""
    if start is None and end is None:
        return None
    if not start or not end:
        raise ValueError('Both window start and end are required when estimating timing.')
    a, b = iso_day(start), iso_day(end)
    if not (earliest < a <= b <= deadline):
        raise ValueError('Estimated window must be after as-of, ordered and before deadline.')
    return {'window_start': start, 'window_end': end}


def calendar_entries(forecasts, schedules, audits_by_id=None):
    """Generate dated records without modifying the permanent forecast ledger."""
    audits_by_id = audits_by_id or {}
    result = []
    for f in forecasts:
        fid = int(f['id'])
        deadline = iso_day(f['target_date'])
        question = f['question']
        audit = audits_by_id.get(fid) or {}
        q = audit.get('question') or {}
        start, end = q.get('window_start'), q.get('window_end')
        if start and end:
            try:
                a, b = iso_day(start), iso_day(end)
            except ValueError:
                a = b = None
            if a and a <= b <= deadline:
                result.append({'id': f'window-{fid}', 'forecast_id': fid, 'kind': 'forecast_window',
                               'start_date': start, 'end_date': end, 'title': question,
                               'probability': f['probability'], 'source_url': '',
                               'timing_basis': q.get('timing_basis') or 'Unspecified model estimate',
                               'notes': 'Estimated timing, not a verified announced date.'})
        # Conditional timing output is a sequence of model-estimated buckets,
        # not announced event dates or verified day-specific forecasts.
        curve=audit.get('conditional_timing') or {}
        previous=None
        try:
            previous=iso_day((audit.get('created_as_of_utc') or f['created'])[:10])
            for i,bucket in enumerate(curve.get('checkpoints',[])):
                end=iso_day(bucket['end_date'])
                first=previous+timedelta(days=1)
                mass=float(bucket['unconditional_event_bucket'])
                if not 0 <= mass <= 1 or not first<=end<=deadline:
                    raise ValueError('Invalid stored timing bucket.')
                if mass>0:
                    result.append({'id':f'timing-{fid}-{i}', 'forecast_id':fid,
                       'kind':'forecast_timing_bucket','start_date':first.isoformat(),
                       'end_date':end.isoformat(),'title':question,'probability':f['probability'],
                       'bucket_probability':mass,'source_url':'',
                       'timing_basis':curve.get('reasoning') or 'Subjective local-model estimate',
                       'notes':'Estimated unconditional chance of event in this INTERVAL, not each individual day. Not calibrated.'})
                previous=end
        except (ValueError,KeyError,TypeError):
            pass   # Old records and damaged optional model timing metadata remain safe.
        result.append({'id': f'deadline-{fid}', 'forecast_id': fid, 'kind': 'forecast_deadline',
                       'start_date': deadline.isoformat(), 'end_date': deadline.isoformat(),
                       'title': question, 'probability': f['probability'], 'source_url': '',
                       'timing_basis': 'Objective outcome must resolve by this deadline.', 'notes': ''})
    for s in schedules:
        result.append({'id': f"schedule-{int(s['id'])}", 'forecast_id': None,
                       'kind': 'reported_schedule', 'start_date': s['start_date'],
                       'end_date': s['end_date'], 'title': s['title'], 'probability': None,
                       'source_url': s['source_url'], 'timing_basis': s['source_note'],
                       'notes': 'User-recorded reported schedule, not independently verified by OVERCAST.'})
    return sorted(result, key=lambda x: (x['start_date'], x['kind'], x['id']))


def in_month(items, year, month):
    first = date(year, month, 1)
    last = date(year, month, monthrange(year, month)[1])
    return [x for x in items if iso_day(x['start_date']) <= last and iso_day(x['end_date']) >= first]


def on_day(items, day):
    day = iso_day(day) if isinstance(day, str) else day
    return [x for x in items if iso_day(x['start_date']) <= day <= iso_day(x['end_date'])]


def escape_ics(text):
    # RFC 5545 string escapes for hand-built stdlib ICS; all content treated as data.
    return str(text).replace('\\', '\\\\').replace('\r', '').replace('\n', '\\n').replace(';', '\\;').replace(',', '\\,')


def export_ics(items):
    """All-day VCALENDAR; stable UIDs; distinguishing forecast window from deadline."""
    from . import __version__
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')  # RFC 5545: DTSTAMP is required
    lines = ['BEGIN:VCALENDAR', 'VERSION:2.0', f'PRODID:-//Marble Oracle//OVERCAST {__version__}//EN',
             'CALSCALE:GREGORIAN', 'METHOD:PUBLISH', 'X-WR-CALNAME:OVERCAST Forecast Calendar']
    for entry in items:
        start = iso_day(entry['start_date'])
        end_exclusive = iso_day(entry['end_date']) + timedelta(days=1)
        label = TYPES[entry['kind']]
        desc = (f'{label}; {entry.get("timing_basis") or "No timing rationale."} '
                f'{entry.get("notes") or ""}')
        if entry.get('probability') is not None:
            desc += f' Original forecast P(YES): {entry["probability"]:.0%}; not a measured date likelihood.'
        if entry.get('bucket_probability') is not None:
            desc += f' Model-estimated occurrence probability DURING ENTIRE INTERVAL: {entry["bucket_probability"]:.1%}; uncalibrated.'
        if entry.get('source_url'):
            desc += ' Source URL: ' + entry['source_url']
        lines += ['BEGIN:VEVENT', f'UID:{entry["id"]}@signal.marble-oracle.local', f'DTSTAMP:{stamp}',
                  f'DTSTART;VALUE=DATE:{start:%Y%m%d}',
                  f'DTEND;VALUE=DATE:{end_exclusive:%Y%m%d}',
                  'SUMMARY:' + escape_ics(label + ': ' + entry['title']),
                  'DESCRIPTION:' + escape_ics(desc), 'TRANSP:TRANSPARENT', 'END:VEVENT']
    lines.append('END:VCALENDAR')
    # Fold at 75 UTF-8 octets (RFC 5545) without splitting multibyte characters.
    folded = []
    for line in lines:
        current = ''
        for char in line:
            if len((current + char).encode('utf-8')) > 75:
                folded.append(current)
                current = ' ' + char
            else:
                current += char
        folded.append(current)
    return '\r\n'.join(folded) + '\r\n'
