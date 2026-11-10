"""Audit-fix regression tests for HOME network fetchers and the passphrase tab.

    xvfb-run -a python3 Application/Tests/test_audit_fixes.py

No network is used: fetchers are driven with fake responses.
"""
from pathlib import Path
import os
import sys
import tempfile
import time

os.environ['MARBLE_ORACLE_STATE'] = tempfile.mkdtemp(prefix='audit-fixes-state-')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Runtime' / 'Marble_Oracle_App'))

import marketdata  # noqa: E402
import oracle_feeds  # noqa: E402
import oracle_dicekey  # noqa: E402


class FakeResponse:
    def __init__(self, size):
        self.size, self.asked = size, None

    def read(self, n=-1):
        self.asked = n
        return b'x' * (self.size if n is None or n < 0 else min(n, self.size))

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def main():
    # News feed: downloads are capped and only http(s) is fetched.
    seen = []

    def opener(req, timeout=0):
        seen.append(req.full_url)
        response = FakeResponse(50 * 1024 * 1024)
        seen.append(response)
        return response
    feed = oracle_feeds.WireFeed(url='https://example.invalid/rss', enabled=False)
    feed.fetch(opener=opener)
    assert seen[1].asked == oracle_feeds.MAX_FEED_BYTES, seen[1].asked
    seen.clear()
    for bad in ('file:///etc/passwd', 'ftp://example.invalid/x', '/etc/passwd'):
        oracle_feeds.WireFeed(url=bad, enabled=False).fetch(opener=opener)
    assert not seen, 'non-http(s) feed URL was fetched'
    xml = '<rss><item><title>Example headline long enough to show</title></item></rss>'
    assert oracle_feeds.parse_headlines(xml, 'T') == ['T: Example headline long enough to show']

    # Market data: https only, response size capped.
    try:
        marketdata._get('file:///etc/passwd')
        raise AssertionError('file:// market URL accepted')
    except ValueError:
        pass
    real = marketdata.urllib.request.urlopen
    try:
        marketdata.urllib.request.urlopen = lambda req, timeout=0: FakeResponse(marketdata.MAX_BYTES + 10)
        try:
            marketdata._get('https://example.invalid/')
            raise AssertionError('oversized market response accepted')
        except ValueError as exc:
            assert 'too large' in str(exc)
    finally:
        marketdata.urllib.request.urlopen = real

    # Passphrase generator: secure source, expected shape, honest strength figure.
    engine = oracle_dicekey.Dicekey()
    phrases = {engine.roll() for _ in range(200)}
    assert len(phrases) == 200 and all(engine.split(p) for p in phrases)
    assert 40 < engine.bits < 50, engine.bits

    # Passphrase tab: a copied phrase is cleared from the clipboard; other content is left alone.
    import tkinter as tk
    import marble_passphrase_tab as tab
    tab.CLIPBOARD_CLEAR_MS = 300
    root = tk.Tk()
    panel = next(v for v in vars(tab).values()
                 if isinstance(v, type) and issubclass(v, tk.Widget) and hasattr(v, '_clear_clipboard'))(root, engine)
    panel.pack()

    def pump(seconds):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            root.update()
            time.sleep(0.02)
    pump(0.2)
    panel.copy()
    assert root.clipboard_get() == panel.phrase
    pump(0.8)
    try:
        left = root.clipboard_get()
    except tk.TclError:
        left = ''
    assert left == '', 'copied passphrase was not cleared'
    panel.copy()
    root.clipboard_clear()
    root.clipboard_append('something the user copied later')
    pump(0.8)
    assert root.clipboard_get() == 'something the user copied later'
    root.destroy()
    print('Audit fixes: feed/market caps and schemes, passphrase shape, clipboard clearing PASSED')


if __name__ == '__main__':
    main()
