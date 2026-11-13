"""Provider interval integrity: never present daily bars as intraday."""
import sys
import os
from unittest.mock import patch
from datetime import datetime,timezone,timedelta
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Runtime'/'Marble_Oracle_App'))
from Augurspex.augurspex.providers import (_aggregate_candles,MarketRouter,ProviderError,read_stooq,read_nasdaq,read_coinbase)


def sample(days=12):
    base=datetime(2026,10,29,tzinfo=timezone.utc)
    return [{'time':(base+timedelta(days=i)).isoformat(),
             'open':100+i,'high':103+i,'low':99+i,'close':102+i,'volume':10}
            for i in range(days)]


def test_grouping():
    rows=sample()
    weekly=_aggregate_candles(rows,'W')
    monthly=_aggregate_candles(rows,'M')
    assert len(weekly)==3, weekly
    assert len(monthly)==2, monthly
    assert weekly[-1]['close']==rows[-1]['close']
    assert weekly[0]['open']==rows[0]['open']
    assert monthly[0]['high']>=monthly[0]['close']
    # The precise UTC day boundary is used for 4-hour buckets.
    hour_rows=[]
    for hour in range(8):
        row=dict(rows[0]);row['time']=(datetime(2026,11,3,tzinfo=timezone.utc)+timedelta(hours=hour)).isoformat();row['open']=100+hour;row['close']=101+hour;row['high']=102+hour;row['low']=99+hour
        hour_rows.append(row)
    four=_aggregate_candles(hour_rows,'240')
    assert len(four)==2
    assert four[0]['close']==104 and four[1]['close']==108
    assert four[0]['high']==105 and four[1]['high']==109


@patch.dict(os.environ,{"AUGURSPEX_ALLOW_UNOFFICIAL_SOURCES":"1"})
def test_minute_equity_routing():
    r=MarketRouter(clock=lambda:100)
    for period in ('1','5','15','60','240'):
        assert r._routes('NVDA','auto',period)==['yahoo']
        assert r._routes('COH.AX','auto',period)==['yahoo']
    try:read_stooq('NVDA','5',getter=lambda _:b'')
    except ProviderError as ex:assert 'daily history only' in str(ex)
    else:raise AssertionError('stooq daily data was misrepresented as intraday')
    try:read_nasdaq('NVDA','5',getter=lambda _:b'')
    except ProviderError as ex:assert 'not intraday' in str(ex)
    else:raise AssertionError('Nasdaq daily data was misrepresented as intraday')


def test_coinbase_4_hour_is_aggregated_from_true_hourly_candles():
    got=[]
    def getter(url):
        got.append(url)
        start=int(datetime(2026,11,11,tzinfo=timezone.utc).timestamp())
        import json
        rows=[]
        for i in range(9):
            # [time, low, high, open, close, volume]
            rows.append([start+3600*i,90+i,110+i,100+i,105+i,20])
        return json.dumps(rows).encode()
    data=read_coinbase('BTC-USD','240',getter=getter)
    assert 'granularity=3600' in got[0],got
    assert data['interval']=='240'
    assert len(data['candles'])==3
    assert data['candles'][0]['close']==108 and data['candles'][1]['close']==112 and data['candles'][2]['close']==113

if __name__=='__main__':
    test_grouping()
    test_minute_equity_routing()
    test_coinbase_4_hour_is_aggregated_from_true_hourly_candles()
    print('AUGURSPEX INTERVAL INTEGRITY: PASS')
