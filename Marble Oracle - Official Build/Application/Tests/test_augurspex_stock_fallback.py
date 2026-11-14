"""AUGURSPEX offline provider fixtures + sidebar/nav regression.

No internet or real stock data is needed for this test.
"""
from __future__ import annotations

import json
import os
from unittest.mock import patch
import sys
import tempfile
import time
import tkinter as tk
from pathlib import Path
from urllib.parse import unquote

APP = Path(__file__).resolve().parents[1] / 'Runtime' / 'Marble_Oracle_App'
sys.path.insert(0, str(APP))
from Augurspex.augurspex.providers import (MarketRouter, read_yahoo,
                                           yahoo_symbol, ProviderError)
from oracle_augurspex_tab import EmbeddedAugurspex
from marble_oracle import WindowApp, parse


def chart_payload(symbol, price=115.5):
    return json.dumps({'chart': {'result': [{
        'meta': {'symbol': symbol, 'currency': 'AUD' if symbol.endswith('.AX') else 'USD'},
        'timestamp': [1794182400, 1794268800, 1794355200],
        'indicators': {'quote': [{
            'open': [price - 2, price, price + 1],
            'high': [price + 1, price + 2, price + 3],
            'low': [price - 3, price - 1, price],
            'close': [price, price + 1, price + 2],
            'volume': [1000, 1100, 1200],
        }]}
    }], 'error': None}}).encode()


@patch.dict(os.environ,{"AUGURSPEX_ALLOW_UNOFFICIAL_SOURCES":"1"})
def test_stock_routes_and_safe_mapping():
    assert yahoo_symbol('NVDA') == 'NVDA'
    assert yahoo_symbol('COH.AX') == 'COH.AX'
    assert yahoo_symbol('ASX:COH') == 'COH.AX'
    assert yahoo_symbol('^GSPC') == '^GSPC'
    assert yahoo_symbol('NASDAQ:AMD') == 'AMD'
    assert yahoo_symbol('BTC-USD') is None
    assert yahoo_symbol('FAKE:COH') is None
    r = MarketRouter(clock=lambda: 100.0)
    assert r._routes('NVDA', 'auto') == ['strasmore', 'stooq', 'nasdaq', 'yahoo']
    assert r._routes('COH.AX', 'auto') == ['yahoo', 'stooq']
    assert r._routes('ETH-USD', 'auto') == ['coinbase', 'kraken', 'gemini', 'coingecko', 'coinpaprika', 'cryptocompare']
    assert r._routes('005930.KS', 'auto') == ['naver', 'yahoo']


@patch.dict(os.environ,{"AUGURSPEX_ALLOW_UNOFFICIAL_SOURCES":"1"})
def test_fallback_when_stooq_has_no_history():
    for symbol in ('NVDA', 'COH.AX', '^GSPC'):
        calls = []
        def getter(url):
            calls.append(url)
            if 'ai.strasmore.com' in url:
                raise ProviderError('No demo rows')
            if 'stooq.com' in url:
                return b'N/D'
            if 'api.nasdaq.com' in url:
                raise ProviderError('Nasdaq returned no history')
            assert 'query1.finance.yahoo.com/v8/finance/chart/' in url
            assert unquote(url.split('/chart/')[1].split('?')[0]) == symbol
            return chart_payload(symbol)
        r = MarketRouter(clock=lambda: 100.0)
        result = r.fetch(symbol, 'D', getter=getter)
        assert result['source'] == 'Yahoo Finance (unofficial)'
        assert result['currency'] == ('AUD' if symbol.endswith('.AX') else 'USD')
        assert len(result['candles']) == 3
        assert result['candles'][0]['close'] < result['candles'][2]['close']
        assert result['cache'] == 'network'
        assert any('finance.yahoo.com' in url for url in calls)
        assert any('finance.yahoo.com' in url for url in calls), 'Unsuccessful earlier sources must be bypassed'
        # Fresh cache preserves exactly the data from the provider.
        cached = r.fetch(symbol, 'D', getter=lambda url: (_ for _ in ()).throw(AssertionError(url)))
        assert cached['cache'] == 'fresh'
    # An unrelated response symbol must never be displayed as the requested market.
    try:
        read_yahoo('COH.AX', 'D', getter=lambda _: chart_payload('RMD.AX'))
    except ProviderError as exc:
        assert 'different listing' in str(exc)
    else:
        raise AssertionError('Accepted incorrect symbol')


def test_native_sidebar_and_active_tab():
    options = vars(parse(['--selftest', '--no-network', '--no-markets', '--no-bezel', '--os-frame']))
    app = WindowApp(options)
    try:
        root = app.root
        scene = app.scene
        root.update()
        scene.resized(1216, 848)
        root.update()
        scene.act('tab_augurspex')
        for _ in range(3):root.update()
        panel = scene.aug.frame
        assert panel.rail_shell.winfo_width() >= 245, panel.rail_shell.winfo_width()
        assert panel.rail.winfo_width() >= 245, panel.rail.winfo_width()
        assert panel.watch.winfo_width() >= 170, panel.watch.winfo_width()
        assert scene._which_overlay() == 'aug'
        nav = scene.nav_tabs
        assert scene.c.itemcget(nav['tab_augurspex'][0], 'fill') != scene.c.itemcget(nav['tab_home'][0], 'fill'), 'AUGURSPEX tab should be highlighted'
        scene.act('tab_home')
        root.update()
        assert scene._which_overlay() is None
        assert scene.c.itemcget(nav['tab_home'][0], 'fill') != scene.c.itemcget(nav['tab_augurspex'][0], 'fill'), 'HOME highlight should return'
    finally:
        app.quit()


if __name__ == '__main__':
    test_stock_routes_and_safe_mapping()
    print('STOCK SYMBOL MAPPING OK')
    test_fallback_when_stooq_has_no_history()
    print('STOOQ -> YAHOO FIXTURE FALLBACK OK')
    test_native_sidebar_and_active_tab()
    print('NATIVE SIDEBAR + TAB HIGHLIGHT OK')
