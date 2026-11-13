"""Local-first market history with explicit source provenance and intervals.

Public sites can refuse requests; optionally configured documented APIs provide
additional entitled exchange coverage. No credentials are bundled, logged or
persisted, and no unrelated market is substituted for a missing listing.
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
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen

SOURCE_INFO = {
    'kraken': {'name':'Kraken', 'coverage':'Crypto OHLC + public WebSocket', 'timeliness':'Trades in real time; OHLC provider interval', 'credentials':False},
    'coinbase': {'name':'Coinbase Exchange', 'coverage':'Crypto OHLC + public WebSocket', 'timeliness':'Trades in real time; OHLC provider interval', 'credentials':False},
    'stooq': {'name':'Stooq', 'coverage':'Daily stock history (US best supported; AU/JP best effort)', 'timeliness':'End-of-day; never live', 'credentials':False},
    'nasdaq': {'name':'Nasdaq.com historical (unofficial endpoint)', 'coverage':'US equity/ETF daily history; website feed may restrict access', 'timeliness':'Delayed historical, not a licensed live API', 'credentials':False},
    'alpha': {'name':'Alpha Vantage official API (optional)', 'coverage':'US equities daily/weekly/monthly history when a personal API key is configured', 'timeliness':'Historical; rate-limited free tier', 'credentials':True},
    'twelve': {'name':'Twelve Data API (optional)', 'coverage':'Documented stock/ETF OHLC subject to provider plan and exchange permissions', 'timeliness':'Historical or provider-delayed; exchange-specific licensing applies', 'credentials':True},
    'yahoo': {'name':'Yahoo Finance Chart (unofficial)', 'coverage':'Public chart history, including US, AU, JP and indices; may be blocked', 'timeliness':'Delayed / historical; not a licensed live feed', 'credentials':False},
    'naver': {'name':'Naver Finance', 'coverage':'KRX/KOSDAQ daily history', 'timeliness':'End-of-day; not live', 'credentials':False},
    'fred': {'name':'FRED published daily index closes', 'coverage':'S&P 500 / Nasdaq Composite / Dow Jones close-only series with own key', 'timeliness':'Daily reference, not live', 'credentials':True},
    'massive': {'name':'Massive (documented stocks API)', 'coverage':'US equity/ETF daily OHLC with a configured key', 'timeliness':'EOD on free plans', 'credentials':True},
    'jquants': {'name':'JPX J-Quants v2', 'coverage':'Tokyo Stock Exchange daily OHLC with personal API key', 'timeliness':'Plan-dependent publication delay', 'credentials':True},
    'krx': {'name':'Korea Exchange Open API', 'coverage':'Daily Korean equity OHLC, approved key and service required', 'timeliness':'Daily, not live', 'credentials':True},
    'coingecko': {'name':'CoinGecko aggregated prices', 'coverage':'USD crypto historical market prices, close only', 'timeliness':'Aggregate, provider delayed', 'credentials':False},
    'coinpaprika': {'name':'CoinPaprika aggregated prices', 'coverage':'USD crypto daily historical price observations, close only', 'timeliness':'Aggregate, provider delayed', 'credentials':False},
    'frankfurter': {'name':'Frankfurter', 'coverage':'Currency reference rates', 'timeliness':'Central-bank reference; not live', 'credentials':False},
    'tradingview': {'name':'TradingView widgets (standalone browser module only)', 'coverage':'Hosted JS chart widget, not an API for native Tk OHLC history', 'timeliness':'Exchange permissions and delays vary', 'credentials':False},
}
CRYPTO = {'BTC-USD': ('XBTUSD','BTC-USD'), 'ETH-USD': ('ETHUSD','ETH-USD'),
          'SOL-USD': ('SOLUSD','SOL-USD'), 'XRP-USD': ('XRPUSD','XRP-USD')}
US = re.compile(r'^(?:NASDAQ|NYSE|AMEX|NYSEARCA|CBOE):([A-Z0-9.\-]{1,15})$')
STOCK = re.compile(r'^([A-Z0-9.\-]{1,15})\.(AX|T|KS|KQ)$')
URL_KRAKEN = 'https://api.kraken.com/0/public/OHLC'
URL_COINBASE = 'https://api.exchange.coinbase.com/products/'
URL_STOOQ = 'https://stooq.com/q/d/l/'
URL_YAHOO_CHART = 'https://query1.finance.yahoo.com/v8/finance/chart/'
URL_NASDAQ = 'https://api.nasdaq.com/api/quote/'
URL_ALPHA = 'https://www.alphavantage.co/query'
URL_TWELVE = 'https://api.twelvedata.com/time_series'
URL_NAVER = 'https://api.finance.naver.com/siseJson.naver'
URL_FRANKFURTER = 'https://api.frankfurter.dev/v2/rates'
URL_FRED = 'https://api.stlouisfed.org/fred/series/observations'
URL_MASSIVE = 'https://api.massive.com/v2/aggs/ticker/'
URL_JQUANTS = 'https://api.jquants.com/v2/equities/bars/daily'
URL_KRX = 'https://data-dbg.krx.co.kr/svc/apis/sto/'
URL_COINGECKO = 'https://api.coingecko.com/api/v3/coins/'
URL_COINPAPRIKA = 'https://api.coinpaprika.com/v1/tickers/'
COIN_IDENTITIES = {
    'BTC-USD': ('bitcoin','btc-bitcoin'), 'ETH-USD': ('ethereum','eth-ethereum'),
    'SOL-USD': ('solana','sol-solana'), 'XRP-USD': ('ripple','xrp-xrp'),
}
INTERVALS = {'1':(1,60),'5':(5,300),'15':(15,900),'60':(60,3600),'240':(240,3600),
             'D':(1440,86400),'W':(1440,86400),'M':(1440,86400)}
CACHE_TTL = {'kraken':50,'coinbase':50,'stooq':6*3600,'yahoo':25*60,'nasdaq':30*60,'alpha':12*3600,'twelve':20*60,'naver':25*60,'frankfurter':3600, 'fred':24*3600,'massive':12*3600, 'jquants':24*3600, 'krx':24*3600,
             'coingecko':10*60, 'coinpaprika':30*60}
MAX_BODY = 2_000_000

class ProviderError(Exception):
    pass

def get_bytes(url, timeout=9, extra_headers=None):
    # This method accepts only URLs hard-coded in this module's provider functions.
    # Yahoo's undocumented public chart endpoint often rejects custom UAs.
    # Only fixed first-party provider hosts can be constructed by callers.
    user_agent=('Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/122 Safari/537.36'
                if url.startswith((URL_YAHOO_CHART,URL_NASDAQ)) else
                'AUGURSPEX/1.1 (+local no-login market observatory)')
    headers={'User-Agent':user_agent, 'Accept':'application/json,text/csv,text/plain,*/*'}
    if url.startswith(URL_NASDAQ):
        headers.update({'Origin':'https://www.nasdaq.com','Referer':'https://www.nasdaq.com/'})
    if extra_headers is not None:
        allowed={'x-api-key','AUTH_KEY'}
        if any(k not in allowed for k in extra_headers):
            raise ProviderError('Unsupported custom provider header')
        headers.update(extra_headers)
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


def _aggregate_candles(rows, period):
    """Build genuine weekly/monthly/4-hour OHLC from finer real observations.

    A provider's daily candles must not be presented as user-selected minute
    candles. Group boundaries are UTC and bars are dated by last observation.
    """
    if period in ('1','5','15','60','D'):
        return rows
    if period not in ('240','W','M'):
        raise ProviderError('Aggregation interval unsupported')
    groups={}
    for row in rows:
        if not isinstance(row,dict):continue
        try:dt=datetime.fromisoformat(str(row['time']).replace('Z','+00:00'))
        except (ValueError,TypeError,KeyError):continue
        if dt.tzinfo is None:dt=dt.replace(tzinfo=timezone.utc)
        dt=dt.astimezone(timezone.utc)
        if period=='240':bucket=(dt.year,dt.month,dt.day,dt.hour//4)
        elif period=='W':
            week=dt.isocalendar();bucket=(week.year,week.week)
        else:bucket=(dt.year,dt.month)
        groups.setdefault(bucket,[]).append(row)
    result=[]
    for bucket,series in sorted(groups.items()):
        series.sort(key=lambda x:x['time'])
        first,last=series[0],series[-1]
        try:
            new=candle(last['time'], first['open'],
                       max(float(b['high']) for b in series),
                       min(float(b['low']) for b in series),
                       last['close'],sum(float(b.get('volume') or 0) for b in series))
        except (KeyError,ValueError,TypeError):continue
        if new is not None:
            if any(b.get('close_only') for b in series):new['close_only']=True
            result.append(new)
    return result


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
    return finish(_aggregate_candles(candles,period),'Kraken','USD',period,'crypto','Public spot OHLC. Current candle can still be forming.')

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
    return finish(_aggregate_candles(rows,period),'Coinbase Exchange','USD',period,'crypto','Public spot OHLC; per-exchange prices can differ.')

def stooq_code(symbol):
    s=symbol.upper()
    if s in ('SPY','EWY','QQQ','AAPL','MSFT','NVDA'):return s.lower()+'.us','USD'
    match=US.fullmatch(s)
    if match:return match.group(1).lower()+'.us','USD'
    # Index aliases are public Stooq instruments, not an unrelated stock proxy.
    if s=='^GSPC':return ('^spx','^spx.us'),'USD'
    if s=='^IXIC':return ('^ndq','^ndq.us'),'USD'
    if s=='^DJI':return ('^dji','^dji.us'),'USD'
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
    if period not in ('D','W','M'):
        raise ProviderError('Stooq offers daily history only; not suitable for minute candles')
    end=datetime.now(timezone.utc).date()
    lookback=730 if period in ('M','W') else 420
    begin=end-timedelta(days=lookback)
    codes=code if isinstance(code,(list,tuple)) else (code,)
    failures=[]
    for candidate in codes:
        url=URL_STOOQ+'?'+urlencode({'s':candidate,'d1':begin.strftime('%Y%m%d'), 'd2':end.strftime('%Y%m%d'),'i':'d'})
        raw=getter(url).decode('utf-8-sig',errors='replace').strip()
        if raw.startswith('<') or raw.startswith('Exceeded'):
            raise ProviderError('Stooq quota or HTML challenge; automated history temporarily blocked')
        if raw.startswith('N/D') or not raw:
            failures.append(candidate+': no CSV');continue
        records=csv.DictReader(io.StringIO(raw))
        if not records.fieldnames or not {'Date','Open','High','Low','Close'}.issubset(records.fieldnames):
            failures.append(candidate+': invalid CSV');continue
        rows=[]
        for d in records:
            try:t=datetime.strptime(d['Date'],'%Y-%m-%d').replace(tzinfo=timezone.utc).isoformat()
            except (ValueError,TypeError):continue
            rows.append(candle(t,d['Open'],d['High'],d['Low'],d['Close'],d.get('Volume',0)))
        if rows:
            note='Daily historical candles, not live. Non-US coverage is best effort.'
            if len(codes)>1:note+=' Index aliases checked: '+', '.join(codes)+'.'
            return finish(_aggregate_candles(rows,period),'Stooq',currency,period,'equity',note)
        failures.append(candidate+': no usable candles')
    raise ProviderError('Stooq returned no history for this listing'+(': '+'; '.join(failures[:4]) if failures else ''))


def yahoo_symbol(symbol):
    """Return the *same listing* in the chart provider's naming scheme.

    Do not guess an exchange from an ambiguous symbol or substitute an ETF
    for an index. Unknown explicit exchanges are unsupported.
    """
    s=str(symbol).strip().upper()
    if s in CRYPTO:
        return None  # crypto is handled by the venue-native feeds
    m=re.fullmatch(r'(?:NASDAQ|NYSE|AMEX|NYSEARCA|CBOE):([A-Z0-9.\-]{1,15})',s)
    if m:return m.group(1)
    for prefix, suffix in (('ASX:','.AX'),('TSE:','.T'),('KRX:','.KS'),('KOSDAQ:','.KQ'),('LSE:','.L')):
        if s.startswith(prefix) and re.fullmatch(r'[A-Z0-9.\-]{1,15}',s[len(prefix):]):
            return s[len(prefix):]+suffix
    if re.fullmatch(r'\^[A-Z0-9]{2,8}',s):return s
    if re.fullmatch(r'[A-Z0-9.\-]{1,15}\.(AX|T|KS|KQ|L)',s):return s
    if re.fullmatch(r'[A-Z][A-Z0-9.\-]{0,14}',s):return s
    return None

def read_yahoo(symbol, period, getter=get_bytes):
    """Daily/intraday history from Yahoo's *unofficial* public chart endpoint.

    This is a best-effort fallback, not a licensed market data subscription.
    It is never silently substituted for another ticker, and timestamps
    and provider identity are shown beside the graph.
    """
    actual=yahoo_symbol(symbol)
    if not actual:raise ProviderError('Yahoo chart mapping unavailable for this listing')
    # Request a safe, bounded window. Some intervals are not offered on Yahoo.
    granularity={'1':'1m','5':'5m','15':'15m','60':'60m','240':'60m',
                 'D':'1d','W':'1wk','M':'1mo'}[period]
    window={'1':'5d','5':'1mo','15':'1mo','60':'1mo','240':'1mo',
            'D':'1y','W':'2y','M':'5y'}[period]
    url=URL_YAHOO_CHART+quote(actual,safe='')+'?'+urlencode({'range':window,'interval':granularity})
    payload=json.loads(getter(url).decode('utf-8'))
    response=payload.get('chart') if isinstance(payload,dict) else None
    if not isinstance(response,dict):raise ProviderError('Yahoo chart returned invalid JSON')
    errors=response.get('error')
    if errors:raise ProviderError('Yahoo chart rejected request: '+str(errors)[:140])
    entries=response.get('result')
    if not isinstance(entries,list) or not entries or not isinstance(entries[0],dict):
        raise ProviderError('Yahoo chart returned no result')
    data=entries[0]
    ticks=data.get('timestamp') or []
    indicators=data.get('indicators') or {}
    quote_list=indicators.get('quote') or []
    if not isinstance(ticks,list) or not isinstance(quote_list,list) or not quote_list or not isinstance(quote_list[0],dict):
        raise ProviderError('Yahoo chart returned no candles')
    q=quote_list[0]
    meta=data.get('meta') or {}
    # Reject accidental ticker misidentification; do not draw a different market.
    response_symbol=str(meta.get('symbol') or '').upper()
    if response_symbol and response_symbol != actual:
        raise ProviderError('Yahoo chart returned a different listing')
    rows=[]
    opens=q.get('open') or [];highs=q.get('high') or []
    lows=q.get('low') or [];closes=q.get('close') or [];volumes=q.get('volume') or []
    close_only_count=0
    for i, unix_stamp in enumerate(ticks[:1200]):
        try:
            when=datetime.fromtimestamp(int(unix_stamp),timezone.utc).isoformat()
        except (ValueError,TypeError,OverflowError):
            continue
        # Many historical Yahoo responses include a valid closing price but
        # have a null OHLC component (thinly traded listings or partial days).
        # Preserve *only* the genuine close; mark the observation so the Tk
        # chart draws a line instead of pretending to know missing candles.
        closing=as_number(closes[i]) if i < len(closes) else None
        if closing is None:continue
        o=opens[i] if i<len(opens) else None
        h=highs[i] if i<len(highs) else None
        l=lows[i] if i<len(lows) else None
        v=volumes[i] if i<len(volumes) else 0
        full=candle(when,o,h,l,closing,v)
        if full is not None:
            rows.append(full)
            continue
        rows.append({'time':when,'open':closing,'high':closing,'low':closing,
                     'close':closing,'volume':as_number(v) or 0,
                     'close_only':True})
        close_only_count+=1
    currency=str(meta.get('currency') or '?')[:8]
    note='Unofficial public Yahoo Finance chart (fallback). Quotes may be delayed, missing or blocked.'
    if close_only_count:note+=f' {close_only_count} closing-price observations lack complete OHLC and are rendered as a line.'
    if period=='240':note+=' Four-hour bars aggregated from provider hourly observations.'
    result=finish(_aggregate_candles(rows,period),'Yahoo Finance (unofficial)',currency,
                  period, 'equity',note)
    if close_only_count:result['close_only_observations']=close_only_count
    return result



def _us_listing(symbol):
    """Return same US security ticker, not an unrelated stock proxy."""
    s=str(symbol).strip().upper()
    if s in CRYPTO or s.startswith('^') or s.endswith(('.AX','.T','.KS','.KQ','.L')):
        return None
    match=US.fullmatch(s)
    if match:return match.group(1)
    if re.fullmatch(r'[A-Z][A-Z0-9.\-]{0,14}',s):return s
    return None


def _nasdaq_number(value):
    if value is None:return None
    return as_number(str(value).replace('$','').replace(' ','').replace('—',''))


def read_nasdaq(symbol, period, getter=get_bytes):
    """Best-effort *same ticker* historical table published by nasdaq.com.

    This is a website endpoint, not a guaranteed official public API. Only
    route to US stocks/ETFs and label daily end-of-day data explicitly.
    """
    actual=_us_listing(symbol)
    if not actual:raise ProviderError('Nasdaq website only supports US stock/ETF listings')
    if period not in ('D','W','M'):
        raise ProviderError('Nasdaq website supplies daily history, not intraday')
    end=datetime.now(timezone.utc).date()
    begin=end-timedelta(days=820 if period in ('W','M') else 425)
    asset_class='etf' if actual in ('SPY','QQQ','EWY','IWM','DIA','VOO','VTI') else 'stocks'
    url=(URL_NASDAQ+quote(actual,safe='')+'/historical?'+urlencode({
        'assetclass':asset_class,'fromdate':begin.isoformat(),
        'todate':end.isoformat(),'limit':300}))
    try:data=json.loads(getter(url).decode('utf-8'))
    except (ValueError,UnicodeError) as exc:raise ProviderError('Nasdaq website response not valid JSON') from exc
    body=(data or {}).get('data') if isinstance(data,dict) else None
    if not isinstance(body,dict):raise ProviderError('Nasdaq website returned no historical table')
    table=body.get('tradesTable') or {}
    rows=table.get('rows') if isinstance(table,dict) else None
    if not isinstance(rows,list) or not rows:raise ProviderError('Nasdaq website returned no history for this listing')
    out=[]
    for row in rows:
        if not isinstance(row,dict):continue
        try:t=datetime.strptime(str(row.get('date') or ''),'%m/%d/%Y').replace(tzinfo=timezone.utc).isoformat()
        except ValueError:continue
        out.append(candle(t,*(_nasdaq_number(row.get(k)) for k in ('open','high','low','close')),
                          _nasdaq_number(row.get('volume')) or 0))
    result=finish(_aggregate_candles(out,period),'Nasdaq.com (website history)','USD',period,'equity',
                  'US website daily historical OHLC; unofficial endpoint, may be blocked or delayed.')
    return result


def read_alpha(symbol, period, getter=get_bytes):
    """Optional documented Alpha Vantage daily history, only when a key exists.

    Never hardcode, persist, log, or display the API key. Reuse the same
    per-provider cooldown and cache policy as the public feeds.
    """
    key=os.environ.get('AUGURSPEX_ALPHA_VANTAGE_KEY','').strip()
    if not key:raise ProviderError('Alpha Vantage not configured (optional)')
    actual=_us_listing(symbol)
    if not actual:raise ProviderError('Alpha Vantage mapping not verified for this exchange')
    if period not in ('D','W','M'):
        raise ProviderError('Alpha Vantage free daily history cannot supply intraday bars')
    fn={'D':'TIME_SERIES_DAILY','W':'TIME_SERIES_WEEKLY','M':'TIME_SERIES_MONTHLY'}[period]
    url=URL_ALPHA+'?'+urlencode({'function':fn,'symbol':actual,'outputsize':'compact','apikey':key})
    try:data=json.loads(getter(url).decode('utf-8'))
    except (ValueError,UnicodeError) as exc:raise ProviderError('Alpha Vantage invalid response') from exc
    if not isinstance(data,dict):raise ProviderError('Alpha Vantage invalid response')
    if 'Note' in data or 'Information' in data:raise ProviderError('Alpha Vantage rate or plan limit')
    if 'Error Message' in data:raise ProviderError('Alpha Vantage rejected ticker')
    raw=next((v for k,v in data.items() if str(k).lower().startswith(('time series (daily)','weekly time series','monthly time series')) and isinstance(v,dict)),None)
    if raw is None:raise ProviderError('Alpha Vantage returned no time series')
    rows=[]
    for day,values in raw.items():
        if not isinstance(values,dict):continue
        try:t=datetime.strptime(day,'%Y-%m-%d').replace(tzinfo=timezone.utc).isoformat()
        except ValueError:continue
        rows.append(candle(t,*(values.get(k) for k in ('1. open','2. high','3. low','4. close')),
                           values.get('5. volume')))
    return finish(rows,'Alpha Vantage (official API)','USD',period,'equity',
                  'Documented daily/weekly/monthly historical API. Free-tier rate limits apply.')


def twelve_listing(symbol):
    """Return the same security and its explicit exchange MIC when known.

    A ticker with a recognized suffix is never treated as a US security.
    Reject ambiguous prefixes instead of guessing a new listing.
    """
    symbol=str(symbol).upper().strip()
    if symbol in CRYPTO or symbol.startswith('^'):
        return None
    mic={'AX':'XASX','T':'XJPX','KS':'XKRX','KQ':'XKOS','L':'XLON'}
    for prefix, suffix in [('ASX','AX'),('TSE','T'),('KRX','KS'),('KOSDAQ','KQ'),('LSE','L')]:
        m=re.fullmatch(re.escape(prefix)+r':([A-Z0-9.\-]{1,15})',symbol)
        if m:return m.group(1),mic[suffix]
    m=re.fullmatch(r'([A-Z0-9.\-]{1,15})\.(AX|T|KS|KQ|L)',symbol)
    if m:return m.group(1),mic[m.group(2)]
    us=_us_listing(symbol)
    return (us,None) if us else None


def read_twelve(symbol,period,getter=get_bytes):
    """Optional documented Twelve Data /time_series endpoint.

    A key is opt-in. Exchange data is not presumed free: Twelve Data explicitly
    gates ASX, Japan and Korea by plan/add-on. No key or entitlement is bundled.
    """
    key=os.environ.get('AUGURSPEX_TWELVE_DATA_KEY','').strip()
    if not key:raise ProviderError('Twelve Data not configured (optional)')
    identity=twelve_listing(symbol)
    if not identity:raise ProviderError('Twelve Data mapping unavailable for this listing')
    ticker,mic=identity
    intervals={'1':'1min','5':'5min','15':'15min','60':'1h','240':'4h',
               'D':'1day','W':'1week','M':'1month'}
    if period not in intervals:raise ProviderError('Twelve Data unsupported interval')
    query={'symbol':ticker,'interval':intervals[period],'outputsize':160,
           'timezone':'UTC','apikey':key}
    if mic:query['mic_code']=mic
    url=URL_TWELVE+'?'+urlencode(query)
    try:doc=json.loads(getter(url).decode('utf-8'))
    except (ValueError,UnicodeError) as exc:raise ProviderError('Twelve Data returned invalid JSON') from exc
    if not isinstance(doc,dict):raise ProviderError('Twelve Data returned invalid response')
    if doc.get('status')=='error' or doc.get('code'):
        status=str(doc.get('code') or '')
        # Do not log provider messages verbatim: an API might echo an input key.
        if status in ('429','403'):
            raise ProviderError('Twelve Data HTTP '+status+'; provider rate or plan limit')
        if status=='401':
            raise ProviderError('Twelve Data credential denied (code 401)')
        raise ProviderError('Twelve Data subscription, symbol or interval unavailable (code '+status[:5]+')')
    meta=doc.get('meta') or {}
    if not isinstance(meta,dict):raise ProviderError('Twelve Data returned invalid metadata')
    returned=str(meta.get('symbol') or '').upper().strip()
    if returned and returned!=ticker:
        raise ProviderError('Twelve Data returned a different security')
    returned_mic=str(meta.get('mic_code') or '').upper().strip()
    if mic and returned_mic and mic!=returned_mic:
        raise ProviderError('Twelve Data returned a different exchange')
    values=doc.get('values')
    if not isinstance(values,list):raise ProviderError('Twelve Data returned no historical candles')
    rows=[]
    for row in values:
        if not isinstance(row,dict):continue
        try:
            stamp=str(row.get('datetime') or '').strip()
            moment=datetime.fromisoformat(stamp.replace('Z','+00:00'))
            # Daily timestamps are exchange calendar dates (provider-local).
            # Intraday requests use timezone=UTC; mark unsuffixed times UTC.
            if moment.tzinfo is None and period in ('1','5','15','60','240'):
                moment=moment.replace(tzinfo=timezone.utc)
            when=moment.isoformat()
        except (ValueError,OverflowError,TypeError):continue
        rows.append(candle(when,row.get('open'),row.get('high'),row.get('low'),
                           row.get('close'),row.get('volume') or 0))
    currency=str(meta.get('currency') or '?')[:8]
    return finish(rows,'Twelve Data (documented API)',currency,period,'equity',
        'Same-listing market history. Access and delays depend on paid exchange permissions; '
        'intraday timestamps UTC, daily dates are exchange-local.')


_NAVER_ROW=re.compile(r'\[\s*[\'\"]?(\d{8})[\'\"]?\s*,\s*([\d.,]+)\s*,\s*([\d.,]+)\s*,\s*([\d.,]+)\s*,\s*([\d.,]+)\s*,\s*([\d.,]+)')

def read_naver(symbol, period, getter=get_bytes):
    s=symbol.upper()
    m=re.fullmatch(r'(\d{6})\.(KS|KQ)',s)
    if not m:m=re.fullmatch(r'(?:KRX|KOSDAQ):(\d{6})',s)
    if not m:raise ProviderError('Naver requires a 6-digit Korean listing')
    code=m.group(1)
    if period not in ('D','W','M'):
        raise ProviderError('Naver offers daily history only; not suitable for minute candles')
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
    return finish(_aggregate_candles(rows,period),'Naver Finance','KRW',period,'equity','Daily KRX/KOSDAQ candles. Unofficial public endpoint; may change.')

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

def _with_headers(getter,url,headers):
    """Credential-bearing calls never put J-Quants / KRX keys in URLs."""
    if getter is get_bytes:
        return get_bytes(url,extra_headers=headers)
    # Injectable test transport: header-aware to test credential isolation.
    return getter(url,headers)


def read_fred(symbol,period,getter=get_bytes):
    """Published, daily *index closes*, not simulated intra-period OHLC bars."""
    key=os.environ.get('AUGURSPEX_FRED_KEY','').strip()
    if not key:raise ProviderError('FRED API key not configured')
    series={'^GSPC':'SP500','^IXIC':'NASDAQCOM','^DJI':'DJIA'}.get(symbol)
    if not series:raise ProviderError('FRED series not mapped for this index')
    if period not in ('D','W','M'):raise ProviderError('FRED series supplies daily index closing levels only')
    today=datetime.now(timezone.utc).date()
    since=today-timedelta(days=750 if period in ('W','M') else 420)
    url=URL_FRED+'?'+urlencode({'series_id':series,'api_key':key,'file_type':'json',
                                'observation_start':since.isoformat(),'observation_end':today.isoformat()})
    data=json.loads(getter(url).decode('utf-8'))
    if not isinstance(data,dict) or not isinstance(data.get('observations'),list):
        raise ProviderError('FRED returned no authorized index series')
    rows=[]
    for v in data['observations']:
        if not isinstance(v,dict):continue
        try:date=datetime.fromisoformat(v['date']).replace(tzinfo=timezone.utc).isoformat()
        except (TypeError,ValueError,KeyError):continue
        value=as_number(v.get('value'))
        if value is not None:
            rows.append({'time':date,'open':value,'high':value,'low':value,
                         'close':value,'volume':0,'close_only':True})
    result=finish(_aggregate_candles(rows,period),'FRED ('+series+' daily index close)','USD',period,'index',
        'Published daily index closing observations only; rights and data delays depend on the underlying index licensor.')
    result['close_only_observations']=len(result['candles'])
    return result


def read_massive(symbol,period,getter=get_bytes):
    """Documented, opt-in US shares/ETFs daily history (Massive/Polygon)."""
    key=os.environ.get('AUGURSPEX_MASSIVE_KEY','').strip()
    if not key:raise ProviderError('Massive API key not configured')
    ticker=_us_listing(symbol)
    if ticker is None:raise ProviderError('Massive provider only mapped to US equity/ETF')
    if period not in ('D','W','M'):raise ProviderError('Massive free historical lane is daily only')
    today=datetime.now(timezone.utc).date()
    start=today-timedelta(days=720 if period in ('W','M') else 420)
    url=(URL_MASSIVE+quote(ticker,safe='')+'/range/1/day/'+start.isoformat()+'/'+today.isoformat()+'?'+
         urlencode({'adjusted':'false','sort':'asc','limit':50000,'apiKey':key}))
    result=json.loads(getter(url).decode('utf-8'))
    if not isinstance(result,dict):raise ProviderError('Massive returned invalid JSON')
    if result.get('ticker') and str(result['ticker']).upper()!=ticker:
        raise ProviderError('Massive returned a different ticker')
    if str(result.get('status') or '').upper() not in ('OK','DELAYED',''):
        raise ProviderError('Massive denied request or plan entitlement')
    values=result.get('results')
    if not isinstance(values,list) or not values:
        raise ProviderError('Massive returned no daily OHLC for ticker (check free-plan history cutoff)')
    rows=[]
    for row in values:
        if not isinstance(row,dict):continue
        try:when=datetime.fromtimestamp(int(row['t'])/1000,timezone.utc).isoformat()
        except (KeyError,ValueError,OverflowError,TypeError):continue
        rows.append(candle(when,row.get('o'),row.get('h'),row.get('l'),row.get('c'),row.get('v',0)))
    return finish(_aggregate_candles(rows,period),'Massive (documented US API)','USD',period,'equity',
                  'US exchange historical OHLC; API subscription determines delay and accessible history.')


def _tse_code(symbol):
    sym=str(symbol).upper().strip()
    found=re.fullmatch(r'(?:TSE:)?([0-9]{4,5}|[0-9]{3}[A-Z])(?:\.T)?',sym)
    return found.group(1) if found else None


def read_jquants(symbol,period,getter=get_bytes):
    """Official JPX v2 per-instrument equity bars, with account delay disclosed."""
    key=os.environ.get('AUGURSPEX_JQUANTS_KEY','').strip()
    if not key:raise ProviderError('J-Quants v2 API key not configured')
    code=_tse_code(symbol)
    if code is None:raise ProviderError('J-Quants only maps explicit Tokyo listings')
    if period not in ('D','W','M'):raise ProviderError('J-Quants free API daily bars only')
    end=datetime.now(timezone.utc).date()
    start=end-timedelta(days=700 if period in ('W','M') else 410)
    params={'code':code,'from':start.isoformat(),'to':end.isoformat()}
    records=[];seen_tokens=set();cursor=None
    for _ in range(4):  # bounded pagination to protect personal free-plan quotas
        query=dict(params)
        if cursor:query['pagination_key']=cursor
        url=URL_JQUANTS+'?'+urlencode(query)
        payload=json.loads(_with_headers(getter,url,{'x-api-key':key}).decode('utf-8'))
        if not isinstance(payload,dict) or not isinstance(payload.get('data'),list):
            raise ProviderError('J-Quants v2 returned no authorized data')
        records.extend(payload['data'])
        cursor=payload.get('pagination_key')
        if not cursor:break
        if cursor in seen_tokens:raise ProviderError('J-Quants repeating pagination token')
        seen_tokens.add(cursor)
    if cursor:raise ProviderError('J-Quants response exceeded safe pagination limit')
    rows=[]
    for x in records:
        if not isinstance(x,dict):continue
        returned=str(x.get('Code') or '')
        if returned and returned!=code and not (len(code)==4 and returned==code+'0'):
            continue
        try:t=datetime.fromisoformat(str(x.get('Date'))).replace(tzinfo=timezone.utc).isoformat()
        except (TypeError,ValueError):continue
        rows.append(candle(t,x.get('O'),x.get('H'),x.get('L'),x.get('C'),x.get('Vo',0)))
    value=finish(_aggregate_candles(rows,period),'JPX J-Quants v2 (official)','JPY',period,'equity',
        'Tokyo equity daily history, permission and publishing delay vary by J-Quants plan; NOT a live quote.')
    value['exchange']='XJPX'
    return value


def _krx_code(symbol):
    sym=str(symbol).upper().strip()
    m=re.fullmatch(r'([0-9]{6})\.(KS|KQ)',sym)
    if m:return m.group(1),m.group(2)
    m=re.fullmatch(r'(KRX|KOSDAQ):([0-9]{6})',sym)
    if m:return m.group(2),'KS' if m.group(1)=='KRX' else 'KQ'
    return None


def read_krx(symbol,period,getter=get_bytes):
    """Official KRX API: daily bulk exchange records, filter exact issue code."""
    key=os.environ.get('AUGURSPEX_KRX_KEY','').strip()
    if not key:raise ProviderError('KRX approved API key not configured')
    identity=_krx_code(symbol)
    if identity is None:raise ProviderError('KRX requires six-digit Korean issue code')
    if period!='D':raise ProviderError('KRX daily endpoint currently supports D chart only')
    code,exchange=identity
    endpoint='stk_bydd_trd' if exchange=='KS' else 'ksq_bydd_trd'
    # The official API is date-scoped, not symbol-scoped: 14 calendar days
    # keeps network traffic bounded; do not claim it provides 1y with one call.
    today=datetime.now(timezone.utc).date();rows=[]
    for offset in range(1,18):
        date=today-timedelta(days=offset)
        if date.weekday()>=5:continue
        url=URL_KRX+endpoint+'?'+urlencode({'basDd':date.strftime('%Y%m%d')})
        doc=json.loads(_with_headers(getter,url,{'AUTH_KEY':key}).decode('utf-8'))
        if not isinstance(doc,dict):raise ProviderError('KRX returned invalid JSON')
        if doc.get('error') or doc.get('ERROR') or doc.get('code') in ('401','403','429'):
            raise ProviderError('KRX authentication, approval or rate limit denied')
        records=doc.get('OutBlock_1')
        if not isinstance(records,list):
            raise ProviderError('KRX endpoint unavailable or service not approved')
        for item in records:
            if not isinstance(item,dict) or str(item.get('ISU_CD') or '').zfill(6)!=code:continue
            stamp=str(item.get('BAS_DD') or date.strftime('%Y%m%d'))
            try:t=datetime.strptime(stamp,'%Y%m%d').replace(tzinfo=timezone.utc).isoformat()
            except ValueError:continue
            rows.append(candle(t,item.get('TDD_OPNPRC'),item.get('TDD_HGPRC'),
                              item.get('TDD_LWPRC'),item.get('TDD_CLSPRC'),item.get('ACC_TRDVOL',0)))
    result=finish(rows,'KRX Open API (official)','KRW','D','equity',
       'Official exchange daily historical records, recent 17 calendar days only; approved key and each service approval required.')
    result['exchange']='XKRX' if exchange=='KS' else 'XKOS'
    return result


def _aggregate_closes(points,source,period,note):
    rows=[]
    for stamp,price in points:
        try:
            ts=datetime.fromtimestamp(float(stamp)/1000,timezone.utc).isoformat() if isinstance(stamp,(int,float)) else str(stamp)
            value=as_number(price)
            if value is None:continue
        except (OverflowError,ValueError,TypeError):continue
        rows.append({'time':ts,'open':value,'high':value,'low':value,'close':value,
                     'volume':0,'close_only':True})
    bars=_aggregate_candles(rows,period)
    result=finish(bars,source,'USD',period,'crypto',note)
    result['aggregated_market']=True
    result['close_only_observations']=len(bars)
    return result


def read_coingecko(symbol,period,getter=get_bytes):
    """Public USD aggregate-market price observations, *not* exchange OHLC."""
    ident=COIN_IDENTITIES.get(symbol)
    if not ident:raise ProviderError('CoinGecko identity not verified for this coin')
    # Public API chooses granularity; never call minute buckets requested as if exact.
    if period not in ('60','240','D','W','M'):
        raise ProviderError('CoinGecko free public API cannot guarantee this minute interval')
    days=7 if period in ('60','240') else 90
    url=URL_COINGECKO+quote(ident[0],safe='')+'/market_chart?'+urlencode({'vs_currency':'usd','days':days})
    data=json.loads(getter(url).decode('utf-8'))
    if not isinstance(data,dict) or not isinstance(data.get('prices'),list):
        raise ProviderError('CoinGecko returned no historical prices')
    return _aggregate_closes(data['prices'],'CoinGecko (aggregated market)',period,
                  'Multi-exchange aggregated USD price observations; CLOSE ONLY, not venue candles or tradable exchange quotes.')


def read_coinpaprika(symbol,period,getter=get_bytes):
    """A second independent aggregated USD coin price-history source."""
    ident=COIN_IDENTITIES.get(symbol)
    if not ident:raise ProviderError('CoinPaprika identity not verified for this coin')
    if period not in ('60','240','D','W','M'):
        raise ProviderError('CoinPaprika free plan cannot supply short intraday history')
    start=(datetime.now(timezone.utc)-timedelta(hours=22 if period in ('60','240') else 175*24)).isoformat()
    interval='1h' if period in ('60','240') else '1d'
    url=URL_COINPAPRIKA+quote(ident[1],safe='')+'/historical?'+urlencode({'start':start,'interval':interval,'quote':'USD'})
    obj=json.loads(getter(url).decode('utf-8'))
    if not isinstance(obj,list):raise ProviderError('CoinPaprika returned no price series')
    points=[]
    for item in obj:
        if not isinstance(item,dict):continue
        try:
            dt=datetime.fromisoformat(str(item.get('timestamp')).replace('Z','+00:00'))
            points.append((dt.timestamp()*1000,item.get('price')))
        except (ValueError,TypeError,OverflowError):continue
    return _aggregate_closes(points,'CoinPaprika (aggregated market)',period,
                  'Volume-weighted aggregated historical USD prices, CLOSE ONLY. Not exchange candles.')


class MarketRouter:
    """Thread-safe local cache, single-flight-ish cooldown. Never makes calls for bad symbols."""
    def __init__(self,clock=time.time,cache_dir=None):
        self.clock=clock;self.lock=threading.RLock();self.cache={};self.blocked={};self.last_call={};self._flights={}
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
            if (isinstance(item,dict) and type(item.get('at')) in (int,float)
                    and math.isfinite(item['at']) and isinstance(item.get('value'),dict)
                    and ((isinstance(item['value'].get('candles'),list)
                          and len(item['value']['candles'])>0)
                         or (isinstance(key,tuple) and key[0]=='fx'
                             and isinstance(item['value'].get('rate'),(int,float))))):
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
    def _routes(self,symbol,source,period='D'):
        symbol=symbol.upper()
        allowed=('auto','coinbase','kraken','stooq','naver','yahoo','nasdaq','alpha','twelve',
                 'massive','jquants','krx','coingecko','coinpaprika','fred')
        if source not in allowed:raise ProviderError('Unknown source')
        if source!='auto':return [source]
        unofficial=os.environ.get('AUGURSPEX_ALLOW_UNOFFICIAL_SOURCES','').strip()=='1'
        has=lambda name: bool(os.environ.get(name,'').strip())
        if symbol in CRYPTO:
            # Same currency pair for venue bars first; then labelled aggregated
            # USD markets where there is enough real resolution for this period.
            result=['coinbase','kraken']
            if period in ('60','240','D','W','M'):
                result+=['coingecko','coinpaprika']
            return result
        if _krx_code(symbol):
            choices=['krx'] if has('AUGURSPEX_KRX_KEY') and period=='D' else []
            if has('AUGURSPEX_TWELVE_DATA_KEY'):choices.append('twelve')
            if unofficial:choices+=['naver','yahoo'] if period in ('D','W','M') else ['yahoo']
            return choices
        if _tse_code(symbol):
            choices=['twelve'] if has('AUGURSPEX_TWELVE_DATA_KEY') else []
            if has('AUGURSPEX_JQUANTS_KEY') and period in ('D','W','M'):choices.append('jquants')
            if unofficial:choices+=['yahoo','stooq'] if period in ('D','W','M') else ['yahoo']
            return choices
        if symbol.endswith('.AX') or symbol.startswith('ASX:'):
            choices=['twelve'] if has('AUGURSPEX_TWELVE_DATA_KEY') else []
            if unofficial:choices+=['yahoo','stooq'] if period in ('D','W','M') else ['yahoo']
            return choices
        if symbol in ('^GSPC','^IXIC','^DJI'):
            choices=['fred'] if has('AUGURSPEX_FRED_KEY') and period in ('D','W','M') else []
            if unofficial:choices+=['yahoo','stooq'] if period in ('D','W','M') else ['yahoo']
            return choices
        if _us_listing(symbol):
            choices=[]
            if period in ('D','W','M'):
                if has('AUGURSPEX_TWELVE_DATA_KEY'):choices.append('twelve')
                if has('AUGURSPEX_MASSIVE_KEY'):choices.append('massive')
                if has('AUGURSPEX_ALPHA_VANTAGE_KEY'):choices.append('alpha')
                choices.append('stooq')
                if unofficial:choices+=['nasdaq','yahoo']
            else:
                if has('AUGURSPEX_TWELVE_DATA_KEY'):choices.append('twelve')
                if unofficial:choices.append('yahoo')
            return choices
        choices=['twelve'] if has('AUGURSPEX_TWELVE_DATA_KEY') and twelve_listing(symbol) else []
        if unofficial:choices+=['yahoo','stooq'] if period in ('D','W','M') else ['yahoo']
        return choices

    def fetch(self,symbol,period='D',source='auto',getter=get_bytes):
        """Coalesce identical concurrent market requests within the suite process."""
        k=(str(symbol).upper().strip(),str(period).upper(),str(source))
        with self.lock:
            flight=self._flights.get(k)
            if flight is None:
                flight={'event':threading.Event(),'result':None,'error':None}
                self._flights[k]=flight
                owner=True
            else:
                owner=False
        if not owner:
            if not flight['event'].wait(65):
                raise ProviderError('Existing provider request still in progress')
            if flight['error'] is not None:
                raise ProviderError(str(flight['error']))
            return dict(flight['result'])
        try:
            result=self._fetch_impl(symbol,period,source,getter)
            flight['result']=result
            return result
        except Exception as exc:
            # Wake other callers on failure, too, without holding any lock
            # through provider calls or sleeping under an interpreter lock.
            flight['error']=exc
            raise
        finally:
            with self.lock:
                self._flights.pop(k,None)
                flight['event'].set()

    def _fetch_impl(self,symbol,period='D',source='auto',getter=get_bytes):
        symbol=str(symbol).upper().strip();period=str(period).upper()
        if period not in INTERVALS:raise ProviderError('Unsupported interval')
        routes=self._routes(symbol,source,period)
        if not routes:
            raise ProviderError('NO ELIGIBLE PROVIDER: This market needs a configured exchange-entitled API key or explicit personal-use unofficial fallback (AUGURSPEX_ALLOW_UNOFFICIAL_SOURCES=1)')
        # Source-specific entries are intentionally distinct to make cache
        # provenance truthful even when the first provider is unavailable.
        with self.lock:
            now=self.clock();fresh_hits=[]
            for index,provider in enumerate(routes):
                key=(symbol,period,provider)
                hit=self._cached(key)
                if hit and 0 <= now-hit['at'] < CACHE_TTL[provider]:
                    # Prefer the latest actual observation, not merely the most
                    # recently *downloaded* file. Retain provider priority as
                    # a tie-breaker and never manufacture an observation date.
                    obs=str(hit['value'].get('latest_observation') or '')
                    fresh_hits.append((obs,-index,hit['value']))
            if fresh_hits:
                winner=max(fresh_hits,key=lambda x:(x[0],x[1]))
                return {**winner[2],'cache':'fresh'}
        failures=[];stale=[]
        functions={'kraken':read_kraken,'coinbase':read_coinbase,
                   'stooq':read_stooq,'naver':read_naver,'yahoo':read_yahoo,
                   'nasdaq':read_nasdaq,'alpha':read_alpha,'twelve':read_twelve,
                   'massive':read_massive,'jquants':read_jquants,'krx':read_krx,'fred':read_fred,
                   'coingecko':read_coingecko,'coinpaprika':read_coinpaprika}
        for provider in routes:
            key=(symbol,period,provider)
            now=self.clock()
            with self.lock:
                hit=self._cached(key)
                if hit and 0 <= now-hit['at'] < CACHE_TTL[provider]:
                    return {**hit['value'],'cache':'fresh'}
                # Limited fresh data may still be better than none, but do not
                # immediately stop: another provider may have fresh history.
                if hit and 0 <= now-hit['at'] < 7*86400:
                    stale.append((hit['at'],provider,hit['value']))
                blocked_until=self.blocked.get(provider,0)
                if now < blocked_until:
                    failures.append(f'{provider}: cooling down (retry in {max(1,int(blocked_until-now))}s)')
                    continue
                gap={'massive':12.5,'jquants':12.5,'coingecko':10.0,'coinpaprika':2.0,
                     'krx':1.5,'alpha':8.0,'fred':2.0}.get(provider,1.4)
                wait=max(0.0,self.last_call.get(provider,now-gap)+gap-now)
                self.last_call[provider]=now+wait
            if wait:time.sleep(wait)
            try:
                value=functions[provider](symbol,period,getter)
                with self.lock:
                    self._save(key,self.clock(),value)
                    self.blocked.pop(provider,None)
                if failures:
                    value={**value,'provider_attempts':failures[:8]}
                return {**value,'cache':'network'}
            except (ProviderError,ValueError,KeyError,TypeError,UnicodeError,json.JSONDecodeError) as exc:
                err=str(exc)
                for secret in (os.environ.get('AUGURSPEX_ALPHA_VANTAGE_KEY','').strip(),
                               os.environ.get('AUGURSPEX_TWELVE_DATA_KEY','').strip(),
                               os.environ.get('AUGURSPEX_MASSIVE_KEY','').strip(),
                               os.environ.get('AUGURSPEX_JQUANTS_KEY','').strip(),
                               os.environ.get('AUGURSPEX_KRX_KEY','').strip(),
                               os.environ.get('AUGURSPEX_FRED_KEY','').strip()):
                    if secret:err=err.replace(secret,'[REDACTED]')
                err=err[:160]
                failures.append(f'{provider}: {err}')
                # Real rate limits are respected, not bypassed or retried
                # aggressively. A global provider block prevents a 9-panel
                # dashboard from hammering the same service on failure.
                if any(x in err.lower() for x in ('http 429','http 403','quota','rate or plan limit','html challenge','daily hits limit','credential denied','authentication','not approved','entitlement')):
                    with self.lock:self.blocked[provider]=self.clock()+900
        if stale:
            at,provider,value=max(stale,key=lambda row:row[0])
            return {**value,'cache':'stale','warning':'All current feeds failed: '+' | '.join(failures[:4]),
                    'provider_attempts':failures[:8]}
        raise ProviderError(' | '.join(failures[:8]) or 'No configured historical source supports this market')

    def fx(self,base,quote,getter=get_bytes):
        key=('fx',base,quote);now=self.clock()
        with self.lock:
            hit=self._cached(key)
            if hit and 0 <= now-hit['at'] < CACHE_TTL['frankfurter']:return {**hit['value'],'cache':'fresh'}
        try:
            value=read_frankfurter(base,quote,getter)
            with self.lock:self._save(key,now,value)
            return {**value,'cache':'network'}
        except (ProviderError,ValueError,TypeError,KeyError,json.JSONDecodeError) as exc:
            if hit:return {**hit['value'],'cache':'stale','warning':str(exc)}
            raise


# The native AUGURSPEX tab and HOME carousel must not maintain independent
# rate-limit/cooldown state. They intentionally share one router per local
# cache location in the suite process; standalone server processes remain
# independently rate limited. User-supplied test routers are unaffected.
_SHARED_ROUTERS = {}
_SHARED_LOCK = threading.Lock()

def shared_market_router(cache_dir):
    path = Path(cache_dir).expanduser().resolve()
    with _SHARED_LOCK:
        router = _SHARED_ROUTERS.get(path)
        if router is None:
            router = MarketRouter(cache_dir=path)
            _SHARED_ROUTERS[path] = router
        return router
