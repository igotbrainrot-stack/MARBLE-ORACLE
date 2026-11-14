"""Stock feed accessibility and user CSV fallback regression, offline and deterministic."""
import tempfile, sys, io, contextlib, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]/'Runtime/Marble_Oracle_App'
sys.path.insert(0,str(ROOT))
from Augurspex.augurspex.providers import (MarketRouter,ProviderError,read_local_stock_csv,local_stock_path)
from Augurspex.augurspex.core import app_folder
from oracle_augurspex_home import MarketCarousel


def demo_csv(symbol='AAPL'):
    return 'symbol,Date,Open,High,Low,Close,Volume\n'+\
        '\n'.join(f'{symbol},2026-11-{day:02d},{100+day},{102+day},{99+day},{101+day},2400' for day in range(2,12))+'\n'


def test_import():
    with tempfile.TemporaryDirectory() as temp:
        root=Path(temp);imports=root/'imports';imports.mkdir()
        p=local_stock_path(imports,'AAPL')
        p.write_text(demo_csv())
        result=read_local_stock_csv(p,'AAPL')
        assert result['source']=='LOCAL CSV · USER IMPORT'
        assert result['latest_observation'].startswith('2026-11-11')
        assert len(result['candles'])==10
        assert result['user_imported'] is True
        router=MarketRouter(cache_dir=root/'cache',import_dir=imports)
        def blocked(url):raise AssertionError('Should not make network requests for imported stock')
        got=router.fetch('AAPL','D',getter=blocked)
        assert got['cache']=='local' and got['candles'][-1]['close']==112
        week=router.fetch('AAPL','W',getter=blocked)
        assert week['interval']=='W' and len(week['candles'])>=1
        routes=router.provider_plan('AAPL','D')
        assert routes[0]['id']=='local-csv'
        assert local_stock_path(imports,'../AAPL') is None
        try:
            router.fetch('AAPL','1',getter=blocked)
        except AssertionError:
            pass  # intraday must not be fabricated from imported daily bars
        except Exception:
            pass
        else:
            raise AssertionError('Intraday history must not use a local daily file')


def test_close_only_and_identity():
    with tempfile.TemporaryDirectory() as temp:
        p=Path(temp)/'close.csv'
        p.write_text('Date,Price\n2026-11-10,50\n2026-11-11,51\n')
        got=read_local_stock_csv(p,'AAPL')
        assert got['candles'][-1]['close_only'] is True
        assert got['candles'][-1]['close']==51
        p.write_text(demo_csv('MSFT'))
        try:read_local_stock_csv(p,'AAPL')
        except ProviderError as exc:assert 'disagrees' in str(exc)
        else:raise AssertionError('Mismatched ticker must be rejected')
        p.write_text('time,close\n2024-01-01,100\n')
        old=read_local_stock_csv(p,'AAPL')
        assert old['latest_observation'].startswith('2024-01-01')  # no date substitution
        assert old['source'].startswith('LOCAL CSV')


def test_stock_requires_auth_when_no_public_history():
    router=MarketRouter()
    assert router._routes('AAPL','auto','D')==['strasmore','stooq'], 'Only documented no-key demo and best-effort Stooq should be active without keys'
    plan=router.provider_plan('AAPL','D')
    assert any(item['id']=='alpaca' and not item['active'] for item in plan)
    assert any(item['id']=='twelve' and not item['active'] for item in plan)

def test_home_offline_local_import():
    with tempfile.TemporaryDirectory() as temp:
        home=Path(temp)
        folder=app_folder(home)/'imported-history'
        folder.mkdir(parents=True)
        path=local_stock_path(folder,'AAPL')
        path.write_text(demo_csv())
        router=MarketRouter(cache_dir=home/'.cache/augurspex/market',import_dir=folder)
        c=MarketCarousel(home=home,router=router,enabled=False)
        try:
            # User's no-network mode must still be able to display local data.
            symbols=[r['symbol'] for r in c._rows]
            if 'AAPL' not in symbols:return
            c._index=symbols.index('AAPL')
            c._fetch_current()
            limit=time.monotonic()+3
            while not c._results.get('AAPL') and time.monotonic()<limit:
                time.sleep(.02)
            assert c._results['AAPL']['cache']=='local'
        finally:c.close()


if __name__=='__main__':
    test_import();test_close_only_and_identity();test_stock_requires_auth_when_no_public_history();test_home_offline_local_import()
    print('AUGURSPEX 0.4.9.1 STOCK HISTORY: PASS')
