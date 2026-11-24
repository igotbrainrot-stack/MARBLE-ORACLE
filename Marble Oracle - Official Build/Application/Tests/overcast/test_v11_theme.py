"""OVERCAST 1.1 visual system: palettes, contrast, artwork and the wider retrieval window."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'Runtime' / 'Marble_Oracle_App'))
from overcast import theme as T


class Palettes(unittest.TestCase):
    def test_every_palette_has_every_token(self):
        keys = set(T.palette('dark', 'Amber'))
        for appearance in T.APPEARANCES:
            for accent in T.ACCENTS:
                self.assertEqual(set(T.palette(appearance, accent)), keys)

    def test_text_tokens_meet_wcag_aa(self):
        for appearance in T.APPEARANCES:
            for accent in T.ACCENTS:
                p = T.palette(appearance, accent)
                for surface in ('bg', 'card', 'side'):
                    self.assertGreaterEqual(T.contrast(p['ink'], p[surface]), 7.0)
                    self.assertGreaterEqual(T.contrast(p['dim'], p[surface]), 4.5, (appearance, surface))
                    self.assertGreaterEqual(T.contrast(p['accent_text'], p[surface]), 4.5, (appearance, accent, surface))
                self.assertGreaterEqual(T.contrast(p['on_accent'], p['accent']), 3.0, (appearance, accent))

    def test_unknown_names_fall_back(self):
        p = T.palette('neon', 'Plaid')
        self.assertEqual((p['appearance'], p['accent_name']), (T.DEFAULT_APPEARANCE, T.DEFAULT_ACCENT))

    def test_readable_darkens_on_light_and_lightens_on_dark(self):
        self.assertLess(T.luminance(T.readable('#FF9500', ('#FFFFFF',))), T.luminance('#FF9500'))
        self.assertGreater(T.luminance(T.readable('#0040A0', ('#000000',))), T.luminance('#0040A0'))


class Artwork(unittest.TestCase):
    def test_rounded_tile_fill_corners_and_symmetry(self):
        tile = T.rounded_tile(9, '#FF9F0A', '#1C1C1E')
        size = len(tile)
        self.assertEqual(size, 22)
        self.assertEqual(tile[size // 2][size // 2], '#FF9F0A', 'centre is exact fill')
        self.assertEqual(tile[0][0], '#1C1C1E', 'outer corner is pure background (pre-blended)')
        for row in tile:
            self.assertEqual(list(row), list(reversed(row)), 'horizontally symmetric')
        self.assertEqual([list(r) for r in tile], [list(r) for r in reversed(tile)], 'vertically symmetric')
        blended = {c for row in tile for c in row} - {'#FF9F0A', '#1C1C1E'}
        self.assertGreaterEqual(len(blended), 4, 'curved edge pixels are blended (anti-aliased)')

    def test_fast_path_matches_full_supersampling(self):
        shapes = [('rrect', 0, 0, 40, 24, 12, '#30D158'), ('circle', 28, 12, 9.5, '#FFFFFF')]
        fast = T.render(40, 24, shapes, '#2C2C2E')
        bg = T.hex_rgb('#2C2C2E')
        for y in (0, 5, 12, 23):
            for x in (0, 3, 18, 28, 39):
                acc = [0, 0, 0]
                for j in range(4):
                    for i in range(4):
                        colour = bg
                        for shape in shapes:
                            if T._inside(shape, x + (i + .5) / 4, y + (j + .5) / 4):
                                colour = T.hex_rgb(shape[-1])
                        acc = [a + c for a, c in zip(acc, colour)]
                self.assertEqual(fast[y][x], T.rgb_hex([a / 16 for a in acc]), (x, y))

    def test_switch_knob_moves_and_photo_data_format(self):
        p = T.palette()
        on, off = T.switch(True, p, p['card']), T.switch(False, p, p['card'])
        self.assertEqual(on[12][28], p['knob'].upper())
        self.assertEqual(off[12][12], p['knob'].upper())
        self.assertEqual(on[12][6], p['accent'].upper())
        data = T.to_photo_data([['#000000', '#FFFFFF'], ['#FFFFFF', '#000000']])
        self.assertEqual(data, '{#000000 #FFFFFF} {#FFFFFF #000000}')

    def test_style_names_cover_every_surface(self):
        theme = T.Theme('light', 'Blue')
        self.assertEqual(theme.button('accent', 'card'), 'O.accent.card.TButton')
        self.assertEqual(theme.surface_colour('side'), theme.p['side'])
        self.assertEqual(theme.fonts['title'][1], 22)


class RetrievalWindow(unittest.TestCase):
    def test_coverage_sees_whole_fortnight_not_newest_500(self):
        from overcast.engine import NewsOracleEngine
        now = datetime.now(timezone.utc)
        with tempfile.TemporaryDirectory() as d:
            e = NewsOracleEngine(state_dir=d, model_client=object())
            try:
                rows = [{'title': f'Arcadia tariff ruling update {i}', 'summary': 'Tariffs and trade.',
                         'url': f'https://p{i % 12}.example/{i}', 'source': f'P{i % 12}',
                         'published': (now - timedelta(minutes=i * 3)).isoformat(timespec='seconds'),
                         'collected': now.isoformat(timespec='seconds'), 'category': 'trade'} for i in range(1200)]
                rows.append({'title': 'Old tariff story', 'summary': 'Tariffs.', 'url': 'https://old.example/1',
                             'source': 'Old', 'published': (now - timedelta(days=30)).isoformat(timespec='seconds'),
                             'collected': (now - timedelta(days=30)).isoformat(timespec='seconds'), 'category': 'trade'})
                e.store.save_articles(rows)
                self.assertEqual(e.coverage('TRADE & SUPPLY CHAINS')['fresh_count'], 1200)
                self.assertEqual(len(e.store.recent_articles(15)), 1200, 'the 30-day-old story is outside the window')
                self.assertEqual([r['title'] for r in e.store.articles(5, '50%')], [])
            finally:
                e.close()


if __name__ == '__main__':
    unittest.main()
