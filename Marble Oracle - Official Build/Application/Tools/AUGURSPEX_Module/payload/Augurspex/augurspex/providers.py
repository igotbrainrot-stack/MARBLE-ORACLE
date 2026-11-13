"""Public, no-login market history. Every source is explicit, cached and timestamped.

Only known HTTPS hosts are requested; no arbitrary URLs, private network fetches,
accounts, tokens or Yahoo Finance. Exchange restrictions always take precedence.
"""
from __future__ import annotations
import csv
import hashlib
import os
import io
import json
import math
import re
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

SOURCE_INFO = {
    'kraken': {'name':'Kraken', 'coverage':'Crypto OHLC + public WebSocket', 'timeliness':'Trades in real time; OHLC provider interval', 'credentials':False},
    'coinbase': {'name':'Coinbase Exchange', 'coverage':'Crypto OHLC + public WebSocket', 'timeliness':'Trades in real time; OHLC provider interval', 'credentials':False},
    'stooq': {'name':'Stooq', 'coverage':'Daily stock history (US best supported; AU/JP best effort)', 'timeliness':'End-of-day; never live', 'credentials':False},
    'naver': {'name':'Naver Finance', 'coverage':'KRX/KOSDAQ daily history', 'timeliness':'End-of-day; not live', 'credentials':False},
    'frankfurter': {'name':'Frankfurter', 'coverage':'Currency reference rates', 'timeliness':'Central-bank reference; not live', 'credentials':False},
    'tradingview': {'name':'TradingView widgets', 'coverage':'Embedded public charts for permitted exchanges', 'timeliness':'Stocks delayed / crypto live per widget rules', 'credentials':False},
}
CRYPTO = {'BTC-USD': ('XBTUSD','BTC-USD'), 'ETH-USD': ('ETHUSD','ETH-USD'),
          'SOL-USD': ('SOLUSD','SOL-USD'), 'XRP-USD': ('XRPUSD','XRP-USD')}
US = re.compile(r'^(?:NASDAQ|NYSE|AMEX|NYSEARCA|CBOE):([A-Z0-9.\-]{1,15})$')
STOCK = re.compile(r'^([A-Z0-9.\-]{1,15})\.(AX|T|KS|KQ)$')
URL_KRAKEN = 'https://api.kraken.com/0/public/OHLC'
URL_COINBASE = 'https://api.exchange.coinbase.com/products/'
URL_STOOQ = 'https://stooq.com/q/d/l/'
URL_NAVER = 'https://api.finance.naver.com/siseJson.naver'
URL_FRANKFURTER = 'https://api.frankfurter.dev/v2/rates'
INTERVALS = {'1':(1,60),'5':(5,300),'15':(15,900),'60':(60,3600),'240':(240,21600),
             'D':(1440,86400),'W':(1440,86400),'M':(1440,86400)}
CACHE_TTL = {'kraken':50,'coinbase':50,'stooq':6*3600,'naver':25*60,'frankfurter':3600}
MAX_BODY = 2_000_000

class ProviderError(Exception):
    pass

def get_bytes(url, timeout=9):
    # This method accepts only URLs hard-coded in this module's provider functions.
    headers={'User-Agent':'AUGURSPEX/1.1 (+local no-login market observatory)', 'Accept':'application/json,text/csv,text/plain,*/*'}
    req=Request(url,headers=headers)
    try:
        with urlopen(req,timeout=timeout) as response:
            data=response.read(MAX_BODY+1)
        if len(data)>MAX_BODY: raise ProviderError('Response exceeded safety limit')
        return data
    except HTTPError as exc:
        raise ProviderError(f'HTTP {exc.code}; provider refused the request') from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise ProviderError(f'Network problem: {str(exc)[:130]}') from exc

def as_number(value):
    try:
        num=float(str(value).replace(',',''))
        return num if math.isfinite(num) and num>=0 else None
    except (ValueError, TypeError):return None

def candle(t,o,h,l,c,v=0):
    numbers=[as_number(x) for x in (o,h,l,c,v)]
    if any(x is None for x in numbers[:4]):return None
    if numbers[1]<numbers[2] or numbers[1]<max(numbers[0],numbers[3]) or numbers[2]>min(numbers[0],numbers[3]):return None
    return {'time':t,'open':numbers[0],'high':numbers[1],'low':numbers[2],'close':numbers[3],'volume':numbers[4] or 0}

def finish(rows, source, currency, interval, asset, note):
    seen={r['time']:r for r in rows if r is not None}
    result=[seen[k] for k in sorted(seen)][-320:]
    if not result:raise ProviderError(source+' supplied no usable candles')
    return {'source':source,'currency':currency,'interval':interval,'asset':asset,'note':note,
            'candles':result,'latest_observation':result[-1]['time'], 'received_at':datetime.now(timezone.utc).isoformat()}

def read_kraken(symbol, period, getter=get_bytes):
    if symbol not in CRYPTO:raise ProviderError('Kraken only supports configured USD crypto pairs')
    minutes,_=INTERVALS[period]
    url=URL_KRAKEN+'?'+urlencode({'pair':CRYPTO[symbol][0],'interval':minutes})
    data=json.loads(getter(url).decode('utf-8'))
    if data.get('error'):raise ProviderError('Kraken: '+str(data['error'])[:180])
    rows=data.get('result',{});market=next((v for k,v in rows.items() if k!='last'),None)
    if not isinstance(market,list):raise ProviderError('Kraken returned no OHLC rows')
    candles=[]
    for row in market:
        if not isinstance(row,list) or len(row)<7:continue
        try:t=datetime.fromtimestamp(int(row[0]),timezone.utc).isoformat()
        except (TypeError,ValueError,OverflowError):continue
        candles.append(candle(t,row[1],row[2],row[3],row[4],row[6]))
    return finish(candles,'Kraken','USD',period,'crypto','Public spot OHLC. Current candle can still be forming.')

def read_coinbase(symbol, period, getter=get_bytes):
    if symbol not in CRYPTO:raise ProviderError('Coinbase only supports configured USD crypto pairs')
    seconds=INTERVALS[period][1];end=datetime.now(timezone.utc)
    start=end-timedelta(seconds=seconds*250)
    # 250 buckets (< 300 request limit); must remain literal allowed crypto pair.
    url=URL_COINBASE+CRYPTO[symbol][1]+'/candles?'+urlencode({'granularity':seconds,
         'start':start.isoformat().replace('+00:00','Z'),'end':end.isoformat().replace('+00:00','Z')})
    data=json.loads(getter(url).decode('utf-8'))
    if not isinstance(data,list):raise ProviderError('Coinbase candle response unavailable')
    rows=[]
    for x in data:
        if not isinstance(x,list) or len(x)<6:continue
        try:t=datetime.fromtimestamp(int(x[0]),timezone.utc).isoformat()
        except (TypeError,ValueError,OverflowError):continue
        rows.append(candle(t,x[3],x[2],x[1],x[4],x[5]))
    return finish(rows,'Coinbase Exchange','USD',period,'crypto','Public spot OHLC; per-exchange prices can differ.')

def stooq_code(symbol):
    s=symbol.upper()
    if s in ('SPY','EWY','QQQ','AAPL','MSFT','NVDA'):return s.lower()+'.us','USD'
    match=US.fullmatch(s)
    if match:return match.group(1).lower()+'.us','USD'
    if s in ('^GSPC','^IXIC','^DJI'):return None,None
    match=STOCK.fullmatch(s)
    if match:
        code,ex=match.groups()
        if ex=='AX':return code.lower()+'.au','AUD'
        if ex=='T':return code.lower()+'.jp','JPY'
    if s.startswith('ASX:'):return s[4:].lower()+'.au','AUD'
    if s.startswith('TSE:'):return s[4:].lower()+'.jp','JPY'
    return None,None

def read_stooq(symbol, period, getter=get_bytes):
    code,currency=stooq_code(symbol)
    if not code:raise ProviderError('Stooq mapping unavailable for this listing')
    end=datetime.now(timezone.utc).date()
    lookback=730 if period in ('M','W') else 420
    begin=end-timedelta(days=lookback)
    url=URL_STOOQ+'?'+urlencode({'s':code,'d1':begin.strftime('%Y%m%d'), 'd2':end.strftime('%Y%m%d'),'i':'d'})
    raw=getter(url).decode('utf-8-sig',errors='replace').strip()
    if raw.startswith('<') or raw.startswith('Exceeded') or raw.startswith('N/D'):
        raise ProviderError('Stooq returned no CSV (blocked, quota, or symbol unavailable)')
    records=csv.DictReader(io.StringIO(raw))
    if not records.fieldnames or not {'Date','Open','High','Low','Close'}.issubset(records.fieldnames):
        raise ProviderError('Stooq did not return valid daily OHLC CSV')
    rows=[]
    for d in records:
        try:t=datetime.strptime(d['Date'],'%Y-%m-%d').replace(tzinfo=timezone.utc).isoformat()
        except (ValueError,TypeError):continue
        rows.append(candle(t,d['Open'],d['High'],d['Low'],d['Close'],d.get('Volume',0)))
    return finish(rows,'Stooq',currency,'D','equity','Daily historical candles, not live. Non-US coverage is best effort.')

_NAVER_ROW=re.compile(r'\[\s*[\'\"]?(\d{8})[\'\"]?\s*,\s*([\d.,]+)\s*,\s*([\d.,]+)\s*,\s*([\d.,]+)\s*,\s*([\d.,]+)\s*,\s*([\d.,]+)')

def read_naver(symbol, period, getter=get_bytes):
    s=symbol.upper()
    m=re.fullmatch(r'(\d{6})\.(KS|KQ)',s)
    if not m:m=re.fullmatch(r'(?:KRX|KOSDAQ):(\d{6})',s)
    if not m:raise ProviderError('Naver requires a 6-digit Korean listing')
    code=m.group(1)
    end=datetime.now(timezone.utc).date()
    begin=end-timedelta(days=740)
    url=URL_NAVER+'?'+urlencode({'symbol':code,'requestType':1,
        'startTime':begin.strftime('%Y%m%d'),'endTime':end.strftime('%Y%m%d'),'timeframe':'day'})
    raw=getter(url)
    # Legacy service may encode Korean response in EUC-KR. Decode BEFORE parsing.
    txt=raw.decode('euc-kr',errors='replace')
    rows=[]
    for d,o,h,l,c,v in _NAVER_ROW.findall(txt):
        try:t=datetime.strptime(d,'%Y%m%d').replace(tzinfo=timezone.utc).isoformat()
        except ValueError:continue
        rows.append(candle(t,o,h,l,c,v))
    return finish(rows,'Naver Finance','KRW','D','equity','Daily KRX/KOSDAQ candles. Unofficial public endpoint; may change.')

def read_frankfurter(base='AUD',quote='USD',getter=get_bytes):
    allowed={'AUD','USD','EUR','GBP','JPY','KRW','CHF','CAD','NZD'}
    base=base.upper();quote=quote.upper()
    if base not in allowed or quote not in allowed or base==quote:raise ProviderError('Unsupported currency pair')
    url=URL_FRANKFURTER+'?'+urlencode({'base':base,'quotes':quote})
    data=json.loads(getter(url).decode('utf-8'))
    if not isinstance(data,list):raise ProviderError('Frankfurter returned unexpected data')
    entries=[r for r in data if isinstance(r,dict) and r.get('base','').upper()==base and r.get('quote','').upper()==quote]
    if not entries:raise ProviderError('FX reference rate unavailable')
    d=max(entries,key=lambda r:r.get('date',''))
    rate=as_number(d.get('rate'))
    if not rate:raise ProviderError('FX rate invalid')
    return {'source':'Frankfurter (central bank reference)', 'base':base,'quote':quote,'rate':rate,
            'observation_date':d.get('date'), 'received_at':datetime.now(timezone.utc).isoformat(),
            'note':'Reference rate published by central banks; not live FX trading data'}

class MarketRouter:
    """Thread-safe local cache, single-flight-ish cooldown. Never makes calls for bad symbols."""
    def __init__(self,clock=time.time,cache_dir=None):
        self.clock=clock;self.lock=threading.RLock();self.cache={};self.blocked={};self.last_call={}
        self.cache_dir=Path(cache_dir) if cache_dir else None
    def _file(self,key):
        digest=hashlib.sha256(repr(key).encode('utf-8')).hexdigest()
        return self.cache_dir / ('history-'+digest+'.json')
    def _cached(self,key):
        if key in self.cache:return self.cache[key]
        if not self.cache_dir:return None
        try:
            target=self._file(key)
            if target.stat().st_size>250000: return None
            item=json.loads(target.read_text(encoding='utf-8'))
            if isinstance(item,dict) and isinstance(item.get('at'),(int,float)) and isinstance(item.get('value'),dict):
                self.cache[key]=item;return item
        except (OSError,ValueError,TypeError,KeyError):pass
        return None
    def _save(self,key,at,value):
        item={'at':at,'value':value};self.cache[key]=item
        if not self.cache_dir:return
        try:
            self.cache_dir.mkdir(parents=True,exist_ok=True,mode=0o700)
            target=self._file(key);temp=target.with_name(target.name+'.'+str(os.getpid())+'.tmp')
            temp.write_text(json.dumps(item,ensure_ascii=False),encoding='utf-8')
            os.chmod(temp,0o600);os.replace(temp,target)
        except OSError:pass
    def _routes(self,symbol,source):
        symbol=symbol.upper()
        if source not in ('auto','coinbase','kraken','stooq','naver'):raise ProviderError('Unknown source')
        if source!='auto':return [source]
        if symbol in CRYPTO:return ['coinbase','kraken']
        if re.fullmatch(r'\d{6}\.(KS|KQ)',symbol) or re.fullmatch(r'(?:KRX|KOSDAQ):\d{6}',symbol):return ['naver']
        return ['stooq']
    def fetch(self,symbol,period='D',source='auto',getter=get_bytes):
        symbol=str(symbol).upper().strip();period=str(period).upper()
        if period not in INTERVALS:raise ProviderError('Unsupported interval')
        routes=self._routes(symbol,source);errors=[]
        for provider in routes:
            if provider not in ('kraken','coinbase','stooq','naver'):continue
            key=(symbol,period,provider);now=self.clock()
            with self.lock:
                hit=self._cached(key)
                if hit and now-hit['at']<CACHE_TTL[provider]:return {**hit['value'],'cache':'fresh'}
                if now<self.blocked.get(provider,0):
                    if hit:return {**hit['value'],'cache':'stale', 'warning':'Provider cooling down after rejection'}
                    errors.append(f'{provider}: temporarily cooling down');continue
                # Reserve a spaced request slot instead of rejecting parallel
                # chart panels. Distinct stock cards load sequentially from one
                # public provider, but all remain eligible to receive a chart.
                gap=now-self.last_call.get(provider,-1000)
                wait=max(0.0,1.4-gap)
                self.last_call[provider]=now+wait
            if wait:time.sleep(wait)
            try:
                fn={'kraken':read_kraken,'coinbase':read_coinbase,'stooq':read_stooq,'naver':read_naver}[provider]
                value=fn(symbol,period,getter)
                with self.lock:self._save(key,now,value);self.blocked.pop(provider,None)
                return {**value,'cache':'network'}
            except (ProviderError,ValueError,KeyError,TypeError,UnicodeError,json.JSONDecodeError) as exc:
                err=str(exc)[:220];errors.append(f'{provider}: {err}')
                if 'HTTP 429' in err or 'HTTP 403' in err or 'quota' in err.lower():
                    with self.lock:self.blocked[provider]=now+900
                if hit:return {**hit['value'],'cache':'stale','warning':err}
        raise ProviderError(' | '.join(errors) or 'No public source supports this market')
    def fx(self,base,quote,getter=get_bytes):
        key=('fx',base,quote);now=self.clock()
        with self.lock:
            hit=self._cached(key)
            if hit and now-hit['at']<CACHE_TTL['frankfurter']:return {**hit['value'],'cache':'fresh'}
        try:
            value=read_frankfurter(base,quote,getter)
            with self.lock:self._save(key,now,value)
            return {**value,'cache':'network'}
        except (ProviderError,ValueError,TypeError,KeyError,json.JSONDecodeError) as exc:
            if hit:return {**hit['value'],'cache':'stale','warning':str(exc)}
            raise
