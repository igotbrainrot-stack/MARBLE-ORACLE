"""AUGURSPEX known-index history alias fallback, without network dependency."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Runtime' / 'Marble_Oracle_App'))
from Augurspex.augurspex.providers import stooq_code, read_stooq


def test_index_aliases_and_fallback():
    assert stooq_code('^GSPC')[0][0]=='^spx'
    assert stooq_code('^IXIC')[0][0]=='^ndq'
    assert stooq_code('^DJI')[0][0]=='^dji'
    calls=[]
    def getter(url):
        calls.append(url)
        if 's=%5Espx&' in url:return b'N/D'
        return (b'Date,Open,High,Low,Close,Volume\n'
                b'2026-11-10,6000,6100,5900,6050,0\n'
                b'2026-11-11,6050,6120,6020,6110,0\n')
    result=read_stooq('^GSPC','D',getter=getter)
    assert result['source']=='Stooq'
    assert len(result['candles'])==2
    assert result['candles'][-1]['close']==6110
    assert len(calls)==2
    assert 's=%5Espx.us&' in calls[-1]

if __name__=='__main__':
    test_index_aliases_and_fallback()
    print('AUGURSPEX PROVIDER MAPPINGS: PASS')
