"""oracle_feeds.py -- Marble_Oracle's background feeds (stdlib only): MarketFeed (wraps the optional marketdata
module; SIM when it is absent or offline) and WireFeed (world headlines from public RSS on a daemon thread, refreshed
every 10 minutes; empty when offline, which the ticker shows as NEWS FEED OFFLINE).  Split out of marble_oracle.py
unchanged (build 0929)."""
import threading
import time


class MarketFeed:
    """Thin wrapper: absent module / --no-markets => empty snapshot (panel shows a message)."""
    def __init__(self, enabled=True, allow_net=True):
        self.md = None
        if enabled:
            try:
                import marketdata
                self.md = marketdata.MarketData(allow_net=allow_net)
                self.fmt_price, self.fmt_pct = marketdata.fmt_price, marketdata.fmt_pct
                self.md.start()
            except Exception:
                self.md = None

    def snapshot(self):
        try:
            return self.md.snapshot() if self.md else {}
        except Exception:
            return {}

    def any_sim(self):
        try:
            return self.md.any_sim() if self.md else True
        except Exception:
            return True

    def stop(self):
        try:
            if self.md:
                self.md.stop()
        except Exception:
            pass


NEWS_FEEDS = (("BBC", "https://feeds.bbci.co.uk/news/world/rss.xml"),
              ("GUARDIAN", "https://www.theguardian.com/world/rss"),
              ("AL JAZEERA", "https://www.aljazeera.com/xml/rss/all.xml"),
              ("NPR", "https://feeds.npr.org/1004/rss.xml"))


def parse_headlines(xml, tag, n=5):
    """RSS/Atom text -> ['TAG: headline', ...] in plain ASCII (the ticker face is a bitmap font)."""
    import html
    import re
    import unicodedata
    items = re.findall(r"<(?:item|entry)[\s>].*?</(?:item|entry)>", xml, re.S) or [xml]
    out = []
    for it in items:
        m = re.search(r"<title[^>]*>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", it, re.S)
        if not m:
            continue
        t = html.unescape(re.sub(r"<[^>]+>", "", m.group(1)))
        t = t.translate({0x2018: "'", 0x2019: "'", 0x201c: '"', 0x201d: '"', 0x2013: "-", 0x2014: "-", 0x2026: "..."})
        t = " ".join(unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode().split())
        if len(t) >= 12 and t.lower() not in ("world news", "world"):
            out.append("%s: %s" % (tag, t[:110]))
        if len(out) >= n:
            break
    return out


class WireFeed:
    """Current world-news headlines for the ticker (background thread; BBC / Guardian / Al Jazeera / NPR RSS, or the one
    URL given with --wire).  Off with --no-network; a feed that fails is skipped; with none the ticker says so."""
    def __init__(self, url=None, enabled=True):
        self.lines = []
        self.feeds = (("WIRE", url),) if url else NEWS_FEEDS
        self.enabled = bool(enabled)
        self.stamp = 0.0
        if self.enabled:
            threading.Thread(target=self._run, daemon=True).start()

    def fetch(self, opener=None):
        import urllib.request
        got = []
        for tag, u in self.feeds:
            try:
                req = urllib.request.Request(u, headers={"User-Agent": "Marble_Oracle"})
                with (opener or urllib.request.urlopen)(req, timeout=8) as r:      # 1029: the response is closed
                    t = r.read().decode("utf-8", "replace")
                got.append(parse_headlines(t, tag))
            except Exception:
                pass
        lines = []
        for k in range(6):                                  # interleave sources so no one outlet owns the ticker
            for g in got:
                if k < len(g):
                    lines.append(g[k])
        return lines

    def _run(self):
        while True:
            wait = 60
            try:
                ls = self.fetch()
                if ls:
                    self.lines, self.stamp, wait = ls, time.time(), 600
            except Exception:
                pass
            time.sleep(wait)
