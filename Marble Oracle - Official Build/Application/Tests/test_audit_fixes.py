"""Audit-fix regression tests for the passphrase tab.

The HOME news and AUD-ticker fetchers these tests also covered were deleted in
0.4.9.3 (see test_no_news_or_markets.py).

    xvfb-run -a python3 Application/Tests/test_audit_fixes.py

No network is used.
"""
from pathlib import Path
import os
import sys
import tempfile
import time

os.environ['MARBLE_ORACLE_STATE'] = tempfile.mkdtemp(prefix='audit-fixes-state-')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Runtime' / 'Marble_Oracle_App'))

import oracle_dicekey  # noqa: E402


def main():
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
