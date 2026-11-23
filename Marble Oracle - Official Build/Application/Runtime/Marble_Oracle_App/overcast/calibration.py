"""Empirical recalibration learned ONLY from the user's own resolved forecasts.

Platt scaling q = sigmoid(a * logit(p) + b), fitted by regularised maximum
likelihood (shrunk toward the identity a=1, b=0). Metaculus found Platt scaling
gave small but significant Brier gains on bot forecasts; the AIA Forecaster
used it to undo LLM hedging toward 50%. Blind, unfitted extremising was
negatively associated with score in the Spring 2026 FutureEval survey, so
OVERCAST never extremises without data:

- nothing is offered below MIN_RESOLVED resolved forecasts;
- the fit is judged by 10-fold cross-validated Brier score, and only offered
  when it beats the raw forecasts out of sample;
- raw ledger probabilities are never modified; the calibrated figure is a
  separately labelled display value.
"""
from __future__ import annotations

import math

MIN_RESOLVED = 40
CLIP = 1e-3


def _logit(p):
    p = min(max(float(p), CLIP), 1 - CLIP)
    return math.log(p / (1 - p))


def _sigmoid(x):
    if x >= 0:
        return 1 / (1 + math.exp(-x))
    e = math.exp(x)
    return e / (1 + e)


def fit_platt(probs, outcomes, *, l2=2.0, iterations=40):
    """Return (a, b). Newton's method on a 2-parameter penalised logistic model."""
    z = [_logit(p) for p in probs]
    a, b = 1.0, 0.0
    for _ in range(iterations):
        ga = 2 * l2 * (a - 1); gb = 2 * l2 * b
        haa = hbb = 2 * l2; hab = 0.0
        for zi, yi in zip(z, outcomes):
            q = _sigmoid(a * zi + b)
            r = q - yi
            w = q * (1 - q)
            ga += r * zi; gb += r
            haa += w * zi * zi; hab += w * zi; hbb += w
        det = haa * hbb - hab * hab
        if det <= 1e-12:
            break
        da = (hbb * ga - hab * gb) / det
        db = (haa * gb - hab * ga) / det
        a -= da; b -= db
        if abs(da) < 1e-9 and abs(db) < 1e-9:
            break
    return a, b


def apply(p, a, b):
    return _sigmoid(a * _logit(p) + b)


def _brier(pairs):
    return sum((p - y) ** 2 for p, y in pairs) / len(pairs)


def recalibration(probs, outcomes, folds=10):
    probs = [float(p) for p in probs]
    outcomes = [int(y) for y in outcomes]
    n = len(probs)
    base = {'available': False, 'resolved': n, 'min_required': MIN_RESOLVED,
            'method': 'platt-scaling-l2-to-identity, 10-fold CV'}
    if n < MIN_RESOLVED or len(set(outcomes)) < 2:
        base['note'] = (f'Needs at least {MIN_RESOLVED} resolved forecasts with both YES and NO outcomes '
                        f'({n} resolved so far). Raw forecasts are shown unadjusted.')
        return base
    raw_cv, cal_cv = [], []
    for k in range(folds):
        train = [(p, y) for i, (p, y) in enumerate(zip(probs, outcomes)) if i % folds != k]
        test = [(p, y) for i, (p, y) in enumerate(zip(probs, outcomes)) if i % folds == k]
        if not test or len({y for _, y in train}) < 2:
            continue
        a, b = fit_platt([p for p, _ in train], [y for _, y in train])
        raw_cv += test
        cal_cv += [(apply(p, a, b), y) for p, y in test]
    a, b = fit_platt(probs, outcomes)
    raw_score, cal_score = _brier(raw_cv), _brier(cal_cv)
    return {**base, 'available': True, 'a': round(a, 4), 'b': round(b, 4),
            'cv_brier_raw': round(raw_score, 5), 'cv_brier_recalibrated': round(cal_score, 5),
            'recommended': cal_score < raw_score,
            'interpretation': ('a > 1 means your forecasts have been too timid (hedged toward 50%); '
                               'a < 1 means too extreme. b shifts everything toward YES (+) or NO (-).'),
            'note': ('Recalibration beats raw forecasts on held-out data; shown as a separate figure.'
                     if cal_score < raw_score else
                     'Recalibration does not beat raw forecasts out of sample; not applied.')}
