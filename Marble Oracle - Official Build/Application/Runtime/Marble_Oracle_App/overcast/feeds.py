"""No-login RSS/Atom ingestion. Fetches metadata/excerpts, never full-page scraping."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from html import unescape
import re
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

from . import __version__
from .store import utc_now

SOURCES = (
    ('ABC Australia', 'https://www.abc.net.au/news/feed/51120/rss.xml', 'australia'),
    ('WTO News', 'https://www.wto.org/library/rss/latest_news_e.xml', 'trade'),
    ('European Central Bank', 'https://www.ecb.europa.eu/rss/press.html', 'business'),
    ('Federal Reserve', 'https://www.federalreserve.gov/feeds/press_all.xml', 'business'),
    ('BBC World', 'https://feeds.bbci.co.uk/news/world/rss.xml', 'world'),
    ('BBC Business', 'https://feeds.bbci.co.uk/news/business/rss.xml', 'business'),
    ('Guardian World', 'https://www.theguardian.com/world/rss', 'world'),
    ('NPR World', 'https://feeds.npr.org/1004/rss.xml', 'world'),
    ('Deutsche Welle', 'https://rss.dw.com/rdf/rss-en-top', 'world'),
    ('Al Jazeera English', 'https://www.aljazeera.com/xml/rss/all.xml', 'world'),
    ('UN News', 'https://news.un.org/feed/subscribe/en/news/all/rss.xml', 'world'),
    # Early-warning and official sources added in OVERCAST 1.0 (each verified live on
    # 23 Nov 2026). Research breadth is the largest accuracy lever for AI forecasters.
    ('UN Meetings Coverage', 'https://press.un.org/en/rss.xml', 'world'),
    ('Crisis Group', 'https://www.crisisgroup.org/rss', 'crisis'),
    ('GDACS Disaster Alerts', 'https://www.gdacs.org/xml/rss.xml', 'crisis'),
    ('Bank of England', 'https://www.bankofengland.co.uk/rss/news', 'business'),
)
# Per-source item filters, applied before the per-feed item cap. GDACS publishes many
# low-impact "Green" notifications; only Orange and Red alerts are decision-relevant.
ITEM_FILTERS = {
    'GDACS Disaster Alerts': lambda item: not item['title'].lower().startswith('green'),
}
MAX_FEED_BYTES = 2_000_000
MAX_ITEMS_PER_FEED = 80


def clean_text(s, max_chars=1200):
    s = re.sub(r'<[^>]+>', ' ', s or '')
    s = unescape(s)
    # Some feeds double-escape their HTML (&amp;lt;p&amp;gt;); strip tags revealed by unescaping.
    s = re.sub(r'<[^>]+>', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()[:max_chars]


def normalize_url(url):
    p = urlsplit((url or '').strip())
    if p.scheme.lower() not in ('http','https') or not p.hostname:
        return ''
    query = [(k,v) for k,v in parse_qsl(p.query,keep_blank_values=True)
             if not k.lower().startswith('utm_') and k.lower() not in ('fbclid','gclid','mc_cid','mc_eid')]
    return urlunsplit((p.scheme.lower(),p.netloc.lower(),p.path.rstrip('/') or '/',urlencode(query),''))


def _date(value):
    if not value:
        return ''
    try:
        dt = parsedate_to_datetime(value)
    except (ValueError,TypeError,IndexError):
        try:
            dt = datetime.fromisoformat(value.strip().replace('Z','+00:00'))
        except ValueError:
            # Crisis Group style: "Friday, November 13, 2026 - 15:32" (no zone: treated as UTC)
            try:
                dt = datetime.strptime(' '.join(value.split()), '%A, %B %d, %Y - %H:%M')
            except ValueError:
                return ''
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat(timespec='seconds')


def _child_text(node, names):
    """First NON-EMPTY child text by local name. An empty <atom:link rel="self"/>
    preceding the RSS <link>URL</link> must not hide the real link."""
    for name in names:
        for child in node:
            if child.tag.rsplit('}',1)[-1].lower() == name.lower() and (child.text or '').strip():
                return child.text.strip()
    return ''


def parse_feed(xml_data, source, category='general', keep=None):
    """Return normalized RSS and Atom items; reject DTD/entities."""
    if len(xml_data) > MAX_FEED_BYTES:
        raise ValueError('Feed exceeds maximum size')
    if re.search(br'<!\s*(DOCTYPE|ENTITY)', xml_data, flags=re.IGNORECASE):
        raise ValueError('Feed declares disallowed XML entities')
    root = ET.fromstring(xml_data)
    items=[]
    for node in root.iter():
        if node.tag.rsplit('}',1)[-1].lower() not in ('item','entry'):
            continue
        title = clean_text(_child_text(node,['title']),300)
        desc = clean_text(_child_text(node,['description','summary','content']),1500)
        link = _child_text(node,['link'])
        if not link:
            for child in node:
                if child.tag.rsplit('}',1)[-1].lower() == 'link':
                    if child.attrib.get('rel','alternate') == 'alternate':
                        link = child.attrib.get('href','')
                        break
        url = normalize_url(link)
        if not title or not url:
            continue
        published = _date(_child_text(node,['pubDate','published','updated','date']))
        item = {'title':title,'summary':desc,'url':url,'source':source,
                'category':category,'published':published,'collected':utc_now()}
        if keep is not None and not keep(item):
            continue
        items.append(item)
        if len(items)>=MAX_ITEMS_PER_FEED:
            break
    return items


def fetch_rss(url, source, category='general', timeout=12, keep=None):
    if not url.startswith('https://'):
        raise ValueError('RSS feeds must use HTTPS.')
    request = Request(url,headers={'User-Agent':f'MarbleOracle-Signal/{__version__} (RSS reader)',
                                   'Accept':'application/rss+xml, application/atom+xml, application/xml, text/xml'})
    with urlopen(request,timeout=timeout) as resp:
        data=resp.read(MAX_FEED_BYTES+1)
    return parse_feed(data, source, category, keep=keep)


def _collect_one(source):
    name,url,category=source[:3]
    try:
        keep=ITEM_FILTERS.get(name)
        fetched=fetch_rss(url,name,category,keep=keep) if keep else fetch_rss(url,name,category)
        dates=[datetime.fromisoformat(a['published']) for a in fetched if a['published']]
        newest=max(dates).astimezone(timezone.utc) if dates else None
        stale=(datetime.now(timezone.utc)-newest > timedelta(days=3)) if newest else None
        return fetched,{'source':name,'fetched':len(fetched),'error':None,
                        'newest_published':newest.isoformat() if newest else None,'stale':stale}
    except Exception as exc:
        return [],{'source':name,'fetched':0,'error':str(exc)[:250],
                   'newest_published':None,'stale':None}


def collect_feeds(sources=SOURCES, max_workers=6):
    """Fetch feeds concurrently (bounded); results keep the configured source order."""
    sources=tuple(sources)
    items=[]; report=[]
    if not sources:
        return items,report
    with ThreadPoolExecutor(max_workers=max(1,min(max_workers,len(sources))),
                            thread_name_prefix='overcast-rss') as pool:
        for fetched,entry in pool.map(_collect_one,sources):
            items.extend(fetched)
            report.append(entry)
    return items,report
