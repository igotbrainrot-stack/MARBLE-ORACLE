"""AUGURSPEX 0.4.8.1 readability and compact-window regression.

Run with: xvfb-run -a /usr/bin/python3 Application/Tests/test_augurspex_readability_0481.py
All displayed candles are simulated for UI testing; no external market calls.
"""
import sys
import tempfile
import tkinter as tk
from tkinter import font as tkfont
from pathlib import Path

APP=Path(__file__).resolve().parents[1]/'Runtime'/'Marble_Oracle_App'
sys.path.insert(0,str(APP))
from oracle_augurspex_tab import EmbeddedAugurspex,PriceChart,fit_text_pixels


def test_readability():
    with tempfile.TemporaryDirectory() as tmp:
        root=tk.Tk();root.geometry('1400x870+0+0');root.update()
        canvas=tk.Canvas(root,bg='#130f0d');canvas.pack(fill='both',expand=True)
        tab=EmbeddedAugurspex(canvas,on_home=lambda:None,offline=True,home=tmp)
        tab.layout((0,0,1400,870));root.update()
        panel=tab.frame
        assert panel.rail_shell.winfo_width()>=290
        assert int(tkfont.Font(font=panel.watch.cget('font')).cget('size'))>=13
        assert len(panel.cards)==4
        card=panel.cards[0]
        assert tkfont.Font(font=card.title.cget('font')).cget('size')>=15
        assert tkfont.Font(font=card.price.cget('font')).cget('size')>=14
        assert tkfont.Font(font=card.company.cget('font')).cget('size')>=11
        assert tkfont.Font(font=card.info.cget('font')).cget('size')>=10
        assert len(panel.watchlist)>=20
        assert 'Bitcoin' in panel.selected_market.cget('text')
        assert panel.watch.size()>15
        panel.search.set('NVDA');root.update()
        assert panel.watch.size()==1
        panel.watch.selection_clear(0,'end')
        panel.watch.selection_set(0)
        panel._choose_from_list();root.update()
        assert panel.settings['symbols'][0]=='NVDA'
        assert 'NVIDIA' in panel.selected_market.cget('text')
        assert card._company_text==panel._names['NVDA']
        assert card.company.cget('text').startswith('NVIDIA')
        assert 'Name: NVIDIA' in panel._source_details_text()
        panel.search.set('');root.update()
        for w,h in ((1400,870),(1000,650),(900,580)):
            root.geometry(f'{w}x{h}+0+0');root.update()
            tab.layout((0,0,w,h));root.update()
            assert panel.rail_shell.winfo_width()>=290
            assert panel.watch.winfo_width()>=220
            assert panel.watch.winfo_height()>60
            assert panel.selected_market.winfo_ismapped()
            assert panel.status_label.winfo_ismapped()
            assert panel.option_parts[-1].winfo_ismapped(),(w,h)
            assert panel.option_parts[-1].winfo_rootx()+panel.option_parts[-1].winfo_width() <= panel.work.winfo_rootx()+panel.work.winfo_width()+3,(w,h)
            for widget in (panel.selected_market,panel.watch):
                assert widget.winfo_rootx()+widget.winfo_width() <= root.winfo_rootx()+root.winfo_width()+2,(w,h)
        for n in ('6','9','2','1','4'):
            panel._change_layout(n)
            root.update()
            assert len(panel.cards)==int(n)
            assert panel.cards[0].title.cget('text').startswith('01  NVDA')
        panel._change_layout('4')
        root.update()
        too_long='VERY LONG COMPANY NAME WITH A SPECIAL LISTING ++++++' \
                 ' AND ADDITIONAL DESCRIPTION THAT SHOULD NOT OVERFLOW'
        card=panel.cards[0]
        card.display('NVDA',too_long,None,'NETWORK DISABLED',False,'2',True)
        root.update()
        assert tkfont.Font(font=card.company.cget('font')).measure(card.company.cget('text')) <= card.winfo_width()-12
        assert fit_text_pixels('XYZ',tkfont.Font(font=card.title.cget('font')),100).startswith('XYZ')
        assert tab.shutdown() is True
        root.destroy()


if __name__=='__main__':
    test_readability()
    print('AUGURSPEX READABILITY + RESPONSIVE LAYOUT: PASS')
