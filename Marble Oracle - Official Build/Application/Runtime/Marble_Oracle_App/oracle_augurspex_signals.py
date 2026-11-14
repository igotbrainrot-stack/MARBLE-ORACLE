"""Conservative, observation-only statistics for AUGURSPEX market charts."""
from __future__ import annotations
import math
from datetime import datetime


def valid_closes(candles):
    series = []
    for row in candles or []:
        if not isinstance(row,dict):continue
        try:
            price=float(row.get('close'))
            timestamp=str(row.get('time',''))
            # Never infer fabricated calendar dates from series positions.
            datetime.fromisoformat(timestamp.replace('Z','+00:00'))
            if not math.isfinite(price) or price<=0:continue
        except (ValueError,TypeError,OverflowError):continue
        series.append((timestamp,price))
    # A source correction for an existing time replaces that observation;
    # repeated timestamps must not inflate averages or RSI.
    by_time={time:close for time,close in series}
    return sorted(by_time.items())


def sma(prices, window):
    if len(prices)<window:return None
    return sum(prices[-window:])/window


def rsi(prices, window=14):
    if len(prices)<=window:return None
    tail=prices[-(window+1):]
    changes=[b-a for a,b in zip(tail,tail[1:])]
    gains=sum(max(0,v) for v in changes)/window
    losses=sum(max(0,-v) for v in changes)/window
    if losses==0:return 100. if gains else 50.
    return 100. - 100./(1.+gains/losses)


def market_signal_report(symbol,data):
    if not isinstance(data,dict):data={}
    series=valid_closes(data.get('candles'))
    if not series:
        return f'{symbol}\nNo valid observations available. No indicators calculated.'
    prices=[r[1] for r in series]
    last=prices[-1]
    def fmt(v):return 'not enough observations' if v is None else f'{v:,.4f}'
    trend=(prices[-1]/prices[0]-1)*100 if len(prices)>1 else None
    percent='not enough observations' if trend is None else f'{trend:+.2f}%'
    lines=[f'{symbol} · Historical observations only',
           f'Source: {data.get("source","unknown")}',
           f'Latest observation: {series[-1][0]}',
           f'Values: {len(prices)} · {data.get("currency","")}',
           f'Latest recorded close: {last:,.4f}',
           f'Change across retrieved observations: {percent}',
           f'20-observation mean: {fmt(sma(prices,20))}',
           f'50-observation mean: {fmt(sma(prices,50))}',
           f'RSI(14) over latest closes: {fmt(rsi(prices,14))}',
           '',
           'Values are observations, not predictions or investment advice.',
           'Reference FX rates and aggregate crypto closes are not live trades.',
           'Check observation date and provider provenance before use.']
    return '\n'.join(lines)
