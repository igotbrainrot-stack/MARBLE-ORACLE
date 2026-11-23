"""BROAD OUTLOOK: question-cluster forecasting for broad strategic questions.

Method (see RESEARCH_METHODS.md, v0.6 section):
- A broad strategic question cannot be scored directly, so it is DECOMPOSED into
  drivers and specific, resolvable SIGNPOST questions (Good Judgment question
  clusters; RAND Forecasting Initiative issue decomposition).
- The broad picture is RECOMPOSED two ways: (1) a set of mutually exclusive,
  exhaustive SCENARIOS with probabilities that must sum to 100%, and (2) a
  weighted STRESS INDEX on -100..+100 built from signpost forecasts (after
  Metaculus Indexes). Both are computed in code, never by the model.
- Several INDEPENDENT RUNS (different temperature and evidence order) are
  aggregated numerically; LLM-written aggregation is avoided because it
  overweights outliers (AIA Forecaster technical report, 2025).

Nothing here is calibrated until signposts and scenarios are resolved and scored.
"""
from __future__ import annotations

from datetime import date
import json
import re
import math
import random
import statistics

OUTLOOK_METHOD = 'broad-outlook-question-cluster-v2-risk'
OUTLOOK_PROMPT_VERSION = 'overcast-v1.0-outlook'
SIGNPOST_PROMPT_VERSION = 'overcast-v1.0-outlook-signpost'
# Earlier versions, kept so old ledger rows are still recognised as signposts.
LEGACY_SIGNPOST_PROMPT_VERSIONS = ('signal-v6.0-outlook-signpost',)
SIGNPOST_PROMPT_VERSIONS = (SIGNPOST_PROMPT_VERSION,) + LEGACY_SIGNPOST_PROMPT_VERSIONS
SCENARIO_LETTERS = 'ABCD'
SCENARIO_KINDS = ('adverse', 'tail_risk', 'status_quo', 'stabilising')
ADVERSE_KINDS = ('adverse', 'tail_risk')
SEVERITY_SCALE = {1: 'negligible', 2: 'minor', 3: 'significant', 4: 'severe', 5: 'systemic'}


_KIND_WORDS = (
    ('tail_risk', r'tail|black swan|catastroph|collapse|meltdown|wildcard|worst'),
    ('stabilising', r'de-?escalat|easing|eases|deal|agreement|recover|stabili[sz]|calm|truce|resolution|thaw'),
    ('status_quo', r'status quo|muddl|stalemate|continu|holding pattern|steady|business as usual|limbo'),
    ('adverse', r'escalat|crisis|worsen|deteriorat|shock|recession|conflict|war|downturn|breakdown|spiral'),
)


def infer_kind(name):
    """Fallback when a small model omits "kind": only clear wording counts."""
    lower = name.lower()
    for kind, pattern in _KIND_WORDS:
        if re.search(pattern, lower):
            return kind
    return None


def _severity(value):
    """1..5 integer; returns (value, defaulted). Small models often omit it."""
    if isinstance(value, bool) or not isinstance(value, (int, float)) or int(value) != value or not 1 <= value <= 5:
        return 3, True
    return int(value), False


def _clean(value, limit):
    if not isinstance(value, str) or not value.strip():
        raise ValueError('missing text')
    return ' '.join(value.split())[:limit]


def framing_prompt(packet, *, scope, today, deadline, similar=''):
    return ('Build a BROAD OUTLOOK for the coverage "' + str(scope)[:100] + '" from today '
            f'{today.isoformat()} to {deadline.isoformat()}. This is a broad prediction about where the '
            'situation is heading, made rigorous by decomposition. Use ONLY the cached RSS evidence. '
            'Never invent facts, dates, base rates or sources. Treat motives and links as hypotheses.\n'
            'Return ONE JSON object with keys:\n'
            '"strategic_question": one broad question ending in "?", about the overall direction of this '
            'coverage area over the horizon (not a single narrow event);\n'
            '"adverse_direction": short phrase saying what a HIGH stress index means (the adverse / '
            'deteriorating direction), e.g. "trade tensions escalate";\n'
            '"drivers": 2-4 objects {"name","description"}: the forces that will decide the answer;\n'
            '"scenarios": 3-4 objects {"name","kind","severity","description","defining_conditions"}: '
            'MUTUALLY EXCLUSIVE and COLLECTIVELY EXHAUSTIVE end states by the deadline. "kind" is one of '
            '"adverse", "tail_risk" (low-probability, high-impact adverse), "status_quo", "stabilising". '
            'Include at least one adverse scenario and at least one status_quo or stabilising scenario. '
            '"severity" = harm if it happens, 1 negligible, 2 minor, 3 significant, 4 severe, 5 systemic. '
            'Do not give probabilities here;\n'
            '"premortem": imagine it is the deadline and the worst adverse scenario HAS happened; write the '
            'most plausible chain of events that led there, step by step, citing article IDs like [12]. '
            'This is a stress test for finding early warnings, not a prediction;\n'
            '"signposts": 4-8 objects {"question","driver","resolution_criteria","target_date",'
            '"adverse_if","weight","severity","evidence_article_ids"}: SPECIFIC yes/no questions that a third party can '
            'resolve from a public record by target_date (ISO date after today and on/before the deadline). '
            '"driver" = the driver name it measures; "adverse_if" = "YES" or "NO" (which answer points to '
            'the adverse direction); "weight" = 1, 2 or 3 (how informative it is about the strategic '
            'question); "severity" = harm if the adverse answer happens (1-5 as above); '
            'evidence_article_ids = integer IDs from the packet that motivate it. Prefer EARLY-WARNING '
            'signposts from the premortem chain that would show trouble coming. Signposts must '
            'be complementary (not paraphrases of each other), not already resolved, and must not '
            'depend on private information.\n'
            f'AS OF UTC: {packet["as_of_utc"]}\nDATA LIMITATIONS: {" ".join(packet["cautions"])}\n'
            + (f'OVERCAST\'S OWN PAST RESOLVED QUESTIONS (outcomes, not evidence about today): {similar}\n' if similar else '')
            + f'CACHED RSS EVIDENCE: {packet["text"]}')


def validate_framing(raw, *, allowed_ids, today, deadline):
    """Strict structure; individually broken signposts are dropped and reported."""
    if not isinstance(raw, dict):
        raise ValueError('Outlook framing must be a JSON object.')
    try:
        question = _clean(raw.get('strategic_question'), 400)
        adverse = _clean(raw.get('adverse_direction'), 160)
    except ValueError:
        raise ValueError('Outlook framing is missing the strategic question or adverse direction.') from None
    if not question.endswith('?'):
        raise ValueError('The strategic question must end with "?".')
    drivers = []
    for item in raw.get('drivers') or []:
        if isinstance(item, dict):
            try:
                drivers.append({'name': _clean(item.get('name'), 120),
                                'description': _clean(item.get('description'), 600)})
            except ValueError:
                continue
    if not 2 <= len(drivers) <= 4:
        raise ValueError('Outlook needs 2 to 4 drivers.')
    scenarios = []
    for item in raw.get('scenarios') or []:
        if isinstance(item, dict):
            try:
                kind = str(item.get('kind') or '').strip().lower().replace('-', '_').replace(' ', '_')
                if kind == 'stabilizing': kind = 'stabilising'
                inferred = False
                if kind not in SCENARIO_KINDS:
                    kind = infer_kind(str(item.get('name') or ''))
                    inferred = True
                    if kind is None:
                        raise ValueError('unknown kind')
                severity, defaulted = _severity(item.get('severity'))
                scenarios.append({'name': _clean(item.get('name'), 120), 'kind': kind, 'kind_inferred': inferred,
                                  'severity': severity, 'severity_defaulted': defaulted,
                                  'description': _clean(item.get('description'), 900),
                                  'defining_conditions': _clean(item.get('defining_conditions'), 700)})
            except ValueError:
                continue
    scenarios = scenarios[:4]
    if not 3 <= len(scenarios) <= 4:
        raise ValueError('Outlook needs 3 or 4 mutually exclusive scenarios, each with a valid kind.')
    if not any(s['kind'] in ADVERSE_KINDS for s in scenarios):
        raise ValueError('Outlook needs at least one adverse or tail-risk scenario.')
    if all(s['kind'] in ADVERSE_KINDS for s in scenarios):
        raise ValueError('Outlook needs at least one status-quo or stabilising scenario (no one-sided doom).')
    for letter, scenario in zip(SCENARIO_LETTERS, scenarios):
        scenario['id'] = letter
    driver_names = {d['name'].casefold(): d['name'] for d in drivers}
    signposts, dropped, seen = [], [], set()
    for item in raw.get('signposts') or []:
        try:
            if not isinstance(item, dict):
                raise ValueError('not an object')
            q = _clean(item.get('question'), 400)
            if not q.endswith('?'):
                raise ValueError('question must end with ?')
            key = ' '.join(sorted(set(q.casefold().split())))
            if key in seen:
                raise ValueError('duplicate signpost')
            target = date.fromisoformat(_clean(item.get('target_date'), 10))
            if not today < target <= deadline:
                raise ValueError('target date outside horizon')
            adverse_if = str(item.get('adverse_if') or '').strip().upper()
            if adverse_if not in ('YES', 'NO'):
                raise ValueError('adverse_if must be YES or NO')
            weight = item.get('weight')
            if isinstance(weight, bool) or not isinstance(weight, (int, float)) or int(weight) != weight or not 1 <= weight <= 3:
                raise ValueError('weight must be 1, 2 or 3')
            ids = item.get('evidence_article_ids')
            if not isinstance(ids, list) or not ids or any(type(i) is not int or i not in allowed_ids for i in ids):
                raise ValueError('cites unavailable evidence')
            driver = driver_names.get(str(item.get('driver') or '').strip().casefold())
            if driver is None:
                raise ValueError('unknown driver')
            severity, sev_default = _severity(item.get('severity'))
            signposts.append({'question': q, 'driver': driver, 'severity': severity,
                              'severity_defaulted': sev_default,
                              'resolution_criteria': _clean(item.get('resolution_criteria'), 900),
                              'target_date': target.isoformat(), 'adverse_if_yes': adverse_if == 'YES',
                              'weight': int(weight), 'evidence_article_ids': list(dict.fromkeys(ids))})
            seen.add(key)
        except (ValueError, TypeError) as exc:
            dropped.append({'question': str((item or {}).get('question') if isinstance(item, dict) else item)[:200],
                            'reason': str(exc)[:120]})
        if len(signposts) >= 8:
            break
    if len(signposts) < 3:
        raise ValueError(f'Only {len(signposts)} usable signpost questions (need at least 3). '
                         'Try a narrower scope or a stronger local model.')
    for index, s in enumerate(signposts, 1):
        s['id'] = f'S{index}'
    premortem = ' '.join(str(raw.get('premortem') or '').split())[:1600]
    return {'strategic_question': question, 'adverse_direction': adverse, 'drivers': drivers,
            'scenarios': scenarios, 'signposts': signposts, 'dropped_signposts': dropped,
            'premortem': premortem}


def shuffled_packet_text(packet, seed):
    """Same evidence in a different order: decorrelates repeated runs (position bias)."""
    rows = json.loads(packet['text'])
    random.Random(seed).shuffle(rows)
    return json.dumps(rows, ensure_ascii=False)


def run_prompt(frame, packet_text, packet, *, similar=''):
    signposts = [{'id': s['id'], 'question': s['question'], 'resolves_by': s['target_date'],
                  'resolution_criteria': s['resolution_criteria']} for s in frame['signposts']]
    scenarios = [{'id': s['id'], 'name': s['name'], 'defining_conditions': s['defining_conditions']}
                 for s in frame['scenarios']]
    return ('Forecast every item below independently and honestly. Method: for each item FIRST state '
            'to yourself how often comparable things happen over a horizon this long (outside view; the '
            'status quo usually persists over short horizons), THEN adjust for the specific evidence '
            '(inside view). Do not inflate adverse outcomes to sound cautious; a downside lens is not a '
            'probability multiplier. Do not treat any item as already resolved.\n'
            'Return ONE JSON object: "signposts": array of {"id","probability_percent" (1..99 = chance '
            'the answer is YES),"rationale" (max 2 sentences)} covering EVERY signpost id exactly once; '
            '"scenarios": array of {"id","probability_percent"} covering EVERY scenario id, summing to 100 '
            '(they are mutually exclusive and exhaustive); "cited_article_ids": integer IDs you relied on; '
            '"key_uncertainty": one sentence.\n'
            f'STRATEGIC QUESTION: {frame["strategic_question"]}\n'
            f'SCENARIOS: {json.dumps(scenarios, ensure_ascii=False)}\n'
            f'SIGNPOSTS: {json.dumps(signposts, ensure_ascii=False)}\n'
            f'AS OF UTC: {packet["as_of_utc"]}\nDATA LIMITATIONS: {" ".join(packet["cautions"])}\n'
            + (f'OVERCAST\'S OWN PAST RESOLVED QUESTIONS (reference outcomes only): {similar}\n' if similar else '')
            + f'CACHED RSS EVIDENCE: {packet_text}')


def validate_run(raw, frame, allowed_ids):
    if not isinstance(raw, dict):
        raise ValueError('Run output must be a JSON object.')
    expected = {s['id'] for s in frame['signposts']}
    probs, rationales = {}, {}
    for item in raw.get('signposts') or []:
        if not isinstance(item, dict) or item.get('id') not in expected or item['id'] in probs:
            raise ValueError('Run returned an unknown or duplicate signpost id.')
        p = item.get('probability_percent')
        if isinstance(p, bool) or not isinstance(p, (int, float)) or not math.isfinite(p) or not 1 <= p <= 99:
            raise ValueError('Signpost probability must be 1..99.')
        probs[item['id']] = float(p)
        rationales[item['id']] = ' '.join(str(item.get('rationale') or '').split())[:400]
    if set(probs) != expected:
        raise ValueError('Run did not forecast every signpost.')
    scenario_ids = [s['id'] for s in frame['scenarios']]
    raw_scen = {}
    for item in raw.get('scenarios') or []:
        if not isinstance(item, dict) or item.get('id') not in scenario_ids or item['id'] in raw_scen:
            raise ValueError('Run returned an unknown or duplicate scenario id.')
        p = item.get('probability_percent')
        if isinstance(p, bool) or not isinstance(p, (int, float)) or not math.isfinite(p) or not 0 <= p <= 100:
            raise ValueError('Scenario probability must be 0..100.')
        raw_scen[item['id']] = float(p)
    if set(raw_scen) != set(scenario_ids):
        raise ValueError('Run did not give every scenario a probability.')
    total = sum(raw_scen.values())
    # Coherence check (a partition must sum to 100%). Small rounding drift is
    # normalised; larger violations make the run invalid rather than "fixed".
    if not 90 <= total <= 110:
        raise ValueError(f'Scenario probabilities sum to {total:.0f}%, not 100% (incoherent run).')
    scenarios = {k: v / total for k, v in raw_scen.items()}
    ids = raw.get('cited_article_ids')
    if not isinstance(ids, list) or not ids or any(type(i) is not int or i not in allowed_ids for i in ids):
        raise ValueError('Run cited unavailable evidence.')
    return {'signposts': probs, 'rationales': rationales, 'scenarios': scenarios,
            'scenario_sum_reported': round(total, 2), 'cited_article_ids': list(dict.fromkeys(ids)),
            'key_uncertainty': ' '.join(str(raw.get('key_uncertainty') or '').split())[:400]}


def ensemble(values):
    """Median for up to 3 values, trimmed mean (drop min and max) for 4+.

    Halawi et al. (2024) used a trimmed mean; the AIA report found mean, median and
    trimmed mean within ~0.0004 Brier of each other, all beating a single run.
    """
    values = sorted(float(v) for v in values)
    if not values:
        raise ValueError('No values to aggregate.')
    if len(values) <= 3:
        return statistics.median(values)
    return statistics.fmean(values[1:-1])


def ensemble_rule(n):
    return 'median' if n <= 3 else 'trimmed-mean(drop min,max)'


def stress_index(signposts, probabilities):
    """Weighted expected index on -100..+100; +100 = every signpost lands adverse.

    index = 100 * sum(w * d * (2p - 1)) / sum(w), d = +1 if YES is adverse else -1.
    When every signpost resolves, the same formula with p in {0,1} gives the
    realised index, so the broad forecast itself becomes checkable.
    """
    total = sum(s['weight'] for s in signposts)
    value = sum(s['weight'] * (1 if s['adverse_if_yes'] else -1) * (2 * probabilities[s['id']] - 1)
                for s in signposts)
    return round(100 * value / total, 1)


def aggregate_runs(frame, runs):
    signpost_p = {s['id']: ensemble([r['signposts'][s['id']] for r in runs]) / 100 for s in frame['signposts']}
    spreads = {s['id']: round(max(r['signposts'][s['id']] for r in runs) - min(r['signposts'][s['id']] for r in runs), 1)
               for s in frame['signposts']}
    # Linear opinion pool keeps the scenario partition coherent (sums to 1).
    scen = {s['id']: statistics.fmean(r['scenarios'][s['id']] for r in runs) for s in frame['scenarios']}
    norm = sum(scen.values()) or 1.0
    scen = {k: v / norm for k, v in scen.items()}
    per_run_index = [stress_index(frame['signposts'], {k: v / 100 for k, v in r['signposts'].items()}) for r in runs]
    kinds = {s['id']: s.get('kind') for s in frame['scenarios']}
    severity = {s['id']: s.get('severity', 3) for s in frame['scenarios']}
    p_adverse = sum(v for k, v in scen.items() if kinds.get(k) in ADVERSE_KINDS)
    expected_severity = sum(v * severity[k] for k, v in scen.items())
    return {'signpost_probability': {k: round(v, 4) for k, v in signpost_p.items()},
            'p_adverse_scenarios': round(p_adverse, 4) if any(kinds.values()) else None,
            # Only meaningful when the model actually rated severity (defaults are not assessments).
            'expected_severity': (round(expected_severity, 2) if any(kinds.values()) and
                                  not all(s.get('severity_defaulted', True) for s in frame['scenarios']) else None),
            'signpost_spread_points': spreads,
            'scenario_probability': {k: round(v, 4) for k, v in scen.items()},
            'stress_index': stress_index(frame['signposts'], signpost_p),
            'stress_index_range': [min(per_run_index), max(per_run_index)],
            'rule': ensemble_rule(len(runs)), 'valid_runs': len(runs)}


def adverse_probability(probability, adverse_if_yes):
    """P(the adverse side of a yes/no question happens)."""
    return probability if adverse_if_yes else 1 - probability


def risk_score(probability, adverse_if_yes, severity):
    """Expected harm on 0..5: P(adverse) x severity. Ranks risks; never changes a probability."""
    return round(adverse_probability(probability, adverse_if_yes) * severity, 3)


def index_label(value):
    if value >= 40: return 'Strongly adverse'
    if value >= 15: return 'Leaning adverse'
    if value > -15: return 'Mixed'
    if value > -40: return 'Leaning stabilising'
    return 'Strongly stabilising'


def bar(fraction, width=24):
    filled = max(0, min(width, round(fraction * width)))
    return '█' * filled + '░' * (width - filled)


def index_bar(value, width=24):
    """Centre-anchored text gauge for -100..+100."""
    half = width // 2
    pos = round((value + 100) / 200 * width)
    cells = ['─'] * width
    cells[half] = '┼'
    cells[max(0, min(width - 1, pos))] = '●'
    return 'stabilising ' + ''.join(cells) + ' adverse'


def report_sections(item, calibrated=None):
    """Human-readable outlook as [(heading, body, style)], bad news first.

    style is '' or 'muted' (or 'adverse' / 'good' for emphasis). item is
    Store.outlook(id). calibrated maps forecast_id -> calibrated_probability().
    """
    audit = item.get('audit') or {}
    agg = audit.get('aggregation') or {}
    frame = audit.get('frame') or {}
    idx = float(item['stress_index'])
    lo, hi = (agg.get('stress_index_range') or [idx, idx])
    revision = f"  ·  revision of #{item['revision_of']}" if item.get('revision_of') else ''
    out = [(item['strategic_question'],
            f"Broad outlook #{item['id']}{revision}  ·  {item['scope'].title()}{(' — ' + item['query']) if item.get('query') else ''}  ·  "
            f"horizon to {item['deadline']}\n"
            f"Created {item['created']}  ·  model {item['model_id']}  ·  {agg.get('valid_runs', '?')} independent runs "
            f"({agg.get('rule', '?')})", 'muted')]
    # 1. Bad news first.
    p_adv = agg.get('p_adverse_scenarios')
    sps = item.get('signposts', [])
    open_risks = sorted((sp for sp in sps if sp['outcome'] is None), key=lambda sp: -sp.get('risk_score', 0))[:3]
    lines = []
    if p_adv is not None:
        lines.append(f"Chance things go badly (adverse + tail-risk scenarios): {p_adv:.0%}  {bar(p_adv)}")
        if agg.get('expected_severity') is not None:
            lines.append(f"Expected severity: {agg['expected_severity']:.1f} / 5 ({SEVERITY_SCALE[max(1, min(5, round(agg['expected_severity'])))]}).")
    lines.append(f"Gloom index {idx:+.0f} · {index_label(idx)}   {index_bar(idx)}")
    lines.append(f"High = {item['adverse_direction']}. Range across runs {lo:+.0f} to {hi:+.0f}.")
    if open_risks:
        lines.append('Top open risks (chance of the bad answer × severity):')
        for sp in open_risks:
            lines.append(f"  • {sp['p_adverse']:.0%} × severity {sp.get('severity', 3)} — {sp['question']}")
    lines.append(f"Realised index (all signposts resolved): {item['realised_index']:+.0f}"
                 if item.get('realised_index') is not None else
                 f"{item.get('signposts_resolved', 0)} of {len(sps)} signposts resolved.")
    out.append(('Bad news first', '\n'.join(lines), 'adverse' if (p_adv or 0) >= 0.5 or idx >= 15 else ''))
    # 2. Scenarios, adverse first.
    order = {k: i for i, k in enumerate(SCENARIO_KINDS)}
    scen_lines = []
    for s_ in sorted(item['scenarios'], key=lambda x: (order.get(x.get('kind'), 9), x['id'])):
        mark = '  ← HAPPENED' if item.get('resolved_scenario') == s_['id'] else ''
        kind = s_.get('kind')
        tag = f" [{kind.replace('_', ' ').capitalize()}{' ?' if s_.get('kind_inferred') else ''}" \
              f"{', severity ' + str(s_['severity']) if s_.get('severity') and not s_.get('severity_defaulted') else ''}]" if kind else ''
        scen_lines.append(f"{s_['id']}. {s_['name']}{tag}  {s_['probability']:.0%}  {bar(s_['probability'])}{mark}\n"
                          f"   {s_['description']}\n   Defined by: {s_['defining_conditions']}")
    out.append(('Scenarios (mutually exclusive; they sum to 100%)', '\n\n'.join(scen_lines), ''))
    if frame.get('premortem'):
        out.append(('Pre-mortem: how it goes wrong (a stress test, not a prediction)', frame['premortem'], ''))
    # 3. Drivers and their signposts.
    frame_sp = {f_['id']: f_ for f_ in frame.get('signposts', [])}
    by_driver = {}
    for sp in sps:
        by_driver.setdefault(sp['driver'], []).append(sp)
    for d in item['drivers']:
        rows = []
        for sp in by_driver.get(d['name'], []):
            status = 'open' if sp['outcome'] is None else ('resolved YES' if sp['outcome'] else 'resolved NO')
            cal = (calibrated or {}).get(sp['forecast_id'])
            cal_text = f"  (calibrated {cal['probability']:.0%})" if cal else ''
            spread = (agg.get('signpost_spread_points') or {}).get(sp['signpost_key'])
            rows.append(f"[{sp['signpost_key']} · ledger #{sp['forecast_id']}] P(yes) {sp['probability']:.0%}{cal_text}  "
                        f"{bar(sp['probability'], 12)}  by {sp['target_date']}  · {status}\n"
                        f"   {sp['question']}\n"
                        f"   Bad news if {'YES' if sp['adverse_if_yes'] else 'NO'} · severity {sp.get('severity', 3)}"
                        f"{'?' if frame_sp.get(sp['signpost_key'], {}).get('severity_defaulted') else ''} · "
                        f"weight {sp['weight']}" + (f" · run spread {spread:.0f} pts" if spread is not None else ''))
        out.append(('Driver: ' + d['name'], d['description'] + '\n\n' + ('\n\n'.join(rows) or 'No open signposts in this revision.'), ''))
    uncertainties = [r.get('key_uncertainty') for r in audit.get('runs', []) if r.get('key_uncertainty')]
    if uncertainties:
        out.append(('Key uncertainties (from each run)', '\n'.join('• ' + u for u in dict.fromkeys(uncertainties)), ''))
    history = audit.get('similar_history') or []
    if history:
        out.append(('Similar past OVERCAST questions used as reference',
                    '\n'.join(f"• {h['question']} — forecast {h['signal_forecast']}, resolved {h['outcome']}" for h in history),
                    'muted'))
    notes = list(audit.get('cautions') or [])
    if audit.get('failed_runs'):
        notes.append(f"{len(audit['failed_runs'])} run(s) failed validation and were excluded.")
    dropped = frame.get('dropped_signposts') or []
    if dropped:
        notes.append(f'{len(dropped)} proposed signpost(s) were rejected (vague, out of horizon, duplicate or uncited).')
    if any(s_.get('kind_inferred') for s_ in item['scenarios']):
        notes.append('Scenario types marked "?" were inferred from their names because the model omitted them.')
    notes += ['The pessimistic lens decides what gets examined (adverse scenarios, pre-mortem, risk ranking); '
              'it never inflates a probability.',
              'Runs of one local model are correlated samples, not independent experts.',
              'Probabilities are uncalibrated until signposts and the scenario are resolved and scored.',
              'Resolve signposts in the Ledger, and the scenario on the Outlooks page after the horizon ends.']
    out.append(('Method and limits', '\n'.join(notes), 'muted'))
    return out
