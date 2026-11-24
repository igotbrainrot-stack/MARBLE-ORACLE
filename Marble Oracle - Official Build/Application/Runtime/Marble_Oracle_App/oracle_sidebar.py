"""The Dark / Light suite chrome (0.5.1): a left sidebar instead of the tab strip, in OVERCAST's design.

Drawn on the HOME canvas like the rest of the chrome, so it shares the hit areas, hover and keyboard ring of
HOME (oracle_home_focus) and the window's move/resize handling. Icons are drawn from canvas shapes, not
symbol characters, so they look the same on every platform and font.

Layout (canvas pixels): the sidebar spans the full height at the left; a header row (the open workspace's
name and what it is for, and the window controls) and the footer status line span the rest. Workspaces open
in the box between them (Scene.overlay_box), so every workspace moves right of the sidebar automatically.
"""
from __future__ import annotations

import oracle_appearance

# action, name, what it is for, icon
WORKSPACES = (
    ('tab_home', 'Home', 'The oracle dashboard', 'home'),
    ('tab_oggcultist', 'Oggcultist', 'Music library and player', 'note'),
    ('tab_eidolith', 'Eidolith', 'Video player and converter', 'film'),
    ('tab_augurspex', 'Augurspex', 'Market history charts', 'chart'),
    ('tab_overcast', 'Overcast', 'News forecasting desk', 'cloud'),
    ('tab_passphrase', 'Passphrase', 'Strong, memorable passphrases', 'key'),
    ('tab_touch_type', 'Touch Type', 'Typing practice', 'keys'),
)
EXTRAS = (
    ('guide', 'Welcome guide', 'help'),
    ('appearance', 'Appearance', 'sliders'),
)


RAIL = 60          # below 1100 px the sidebar is an icon rail, so the workspaces keep their width


def sidebar_width(width):
    """Sidebar width in canvas pixels for a canvas `width` pixels wide."""
    return 212 if width >= 1200 else (184 if width >= 1100 else RAIL)


def round_rect(canvas, x0, y0, x1, y1, r, **kw):
    """A rounded rectangle as a smoothed polygon (Tk's canvas has none)."""
    r = max(0, min(r, (x1 - x0) / 2, (y1 - y0) / 2))
    pts = (x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r, x1, y1 - r, x1, y1, x1 - r, y1, x0 + r, y1, x0, y1,
           x0, y1 - r, x0, y0 + r, x0, y0)
    return canvas.create_polygon(pts, smooth=True, splinesteps=12, **kw)


def draw_icon(canvas, kind, cx, cy, s, colour, tags):
    """A 16-unit line icon centred on (cx, cy), `s` pixels per unit / 8 (s = icon size in pixels)."""
    u = s / 16.0
    w = max(1.0, 1.6 * u)
    ids = []

    def line(*pts, **kw):
        coords = [cx + (x - 8) * u if i % 2 == 0 else cy + (x - 8) * u for i, x in enumerate(pts)]
        ids.append(canvas.create_line(*coords, fill=colour, width=w, capstyle='round', joinstyle='round',
                                      tags=tags, **kw))

    def oval(x0, y0, x1, y1, fill=''):
        ids.append(canvas.create_oval(cx + (x0 - 8) * u, cy + (y0 - 8) * u, cx + (x1 - 8) * u, cy + (y1 - 8) * u,
                                      outline=colour, width=w, fill=fill, tags=tags))

    def rect(x0, y0, x1, y1):
        ids.append(canvas.create_rectangle(cx + (x0 - 8) * u, cy + (y0 - 8) * u, cx + (x1 - 8) * u,
                                           cy + (y1 - 8) * u, outline=colour, width=w, tags=tags))

    if kind == 'home':
        line(2, 8, 8, 2.5, 14, 8)
        line(3.5, 7, 3.5, 14, 12.5, 14, 12.5, 7)
        line(6.5, 14, 6.5, 10, 9.5, 10, 9.5, 14)
    elif kind == 'note':
        line(6, 12, 6, 3, 13, 2, 13, 11)
        oval(2.5, 10, 6.5, 14, fill=colour)
        oval(9.5, 9, 13.5, 13, fill=colour)
    elif kind == 'film':
        rect(2, 3, 14, 13)
        line(6.5, 6, 10.5, 8, 6.5, 10, 6.5, 6)
    elif kind == 'chart':
        line(2, 2, 2, 14, 14, 14)
        line(4, 11, 7, 7, 10, 9, 14, 4)
    elif kind == 'cloud':
        line(4.5, 12.5, 12, 12.5)
        ids.append(canvas.create_arc(cx - 6.5 * u, cy - 1 * u, cx - 1.5 * u, cy + 4.5 * u, start=90, extent=180,
                                     style='arc', outline=colour, width=w, tags=tags))
        ids.append(canvas.create_arc(cx - 4 * u, cy - 5.5 * u, cx + 3.5 * u, cy + 2 * u, start=20, extent=150,
                                     style='arc', outline=colour, width=w, tags=tags))
        ids.append(canvas.create_arc(cx + 0.5 * u, cy - 2.5 * u, cx + 6.5 * u, cy + 4.5 * u, start=-90, extent=180,
                                     style='arc', outline=colour, width=w, tags=tags))
    elif kind == 'key':
        oval(2, 4, 8, 10)
        line(8, 7, 14, 7, 14, 10)
        line(11.5, 7, 11.5, 9.5)
    elif kind == 'keys':
        rect(1.5, 4, 14.5, 12)
        for x in (4.5, 7, 9.5, 12):
            line(x, 7, x + 0.01, 7)
        line(5, 9.5, 11, 9.5)
    elif kind == 'help':
        oval(2, 2, 14, 14)
        line(6.2, 6.3, 6.6, 5.2, 8, 4.6, 9.4, 5.2, 9.8, 6.4, 8, 8, 8, 9.4)
        line(8, 11.6, 8.01, 11.6)
    elif kind == 'sliders':
        for y, x in ((4.5, 10), (8, 5), (11.5, 11)):
            line(2, y, 14, y)
            oval(x - 1.6, y - 1.6, x + 1.6, y + 1.6, fill=colour)
    return ids


class SidebarMixin:
    """Mixed into Scene. Needs: c, k, W, H, rect, hot, T(), font(), _win_glyphs(), case_on(), integrated()."""

    def modern_chrome(self):
        return (oracle_appearance.modern() and getattr(self, 'integrated', lambda: False)()
                and not getattr(self, 'case_on', lambda: False)())

    def _chrome_modern(self):
        from oracle_skin import px
        p = oracle_appearance.palette()
        c, k = self.c, self.k
        sx0, sy0, sx1, sy1 = self.rect['side']
        hx0, hy0, hx1, hy1 = self.rect['menu']
        fx0, fy0, fx1, fy1 = self.rect['status']
        self.menu_bg = p['bg']
        import oracle_ogg_texture
        pumice = oracle_ogg_texture.MODE == 'pumice'
        # Sidebar surface and its hairline (0.5.2: pumice-textured, like the page).
        c.create_rectangle(0, 0, sx1, self.H, fill=p['side'], outline='', tags='chrome')
        if pumice:
            self.put(oracle_ogg_texture.png_bytes('side'), 0, 0, 'chrome', w=sx1, h=self.H)
        c.create_line(sx1, 0, sx1, self.H, fill=p['line'], tags='chrome')
        # Header and footer on the page background.
        c.create_rectangle(sx1 + 1, hy0, hx1, hy1, fill=p['bg'], outline='', tags='chrome')
        c.create_rectangle(sx1 + 1, fy0, fx1, fy1, fill=p['bg'], outline='', tags='chrome')
        if pumice:
            for y0_, y1_ in ((hy0, hy1), (fy0, fy1)):
                if y1_ > y0_ and hx1 > sx1 + 1:
                    self.put(oracle_ogg_texture.png_bytes('page'), sx1 + 1, y0_, 'chrome', w=hx1 - sx1 - 1, h=y1_ - y0_)
        c.create_line(sx1 + 1, fy0, fx1, fy0, fill=p['line'], tags='chrome')
        pad = px(14, k)
        rail = sx1 - sx0 <= RAIL + 1
        self._side_rail = rail
        # Brand.
        y = px(16, k)
        if rail:
            mark = round_rect(c, sx0 + 12, y, sx1 - 12, y + (sx1 - sx0 - 24), 9, fill=p['accent'], outline='',
                              tags='chrome')
            bx0, by0, bx1, by1 = c.bbox(mark)
            c.create_text((bx0 + bx1) / 2.0, (by0 + by1) / 2.0, text='MO', font=self.font(12, True, False),
                          fill=p['on_accent'], tags='chrome')
            y = by1 + px(18, k)
        else:
            y = self._side_brand(c, p, sx0, pad, y, k, px)
        row = max(28, px(36, k))
        self.nav_tabs = {}
        self._side_rows = {}
        for action, name, _blurb, icon in WORKSPACES:
            self._side_row(action, name, icon, sx0 + px(8, k), y, sx1 - px(8, k), y + row - px(2, k), p, rail=rail)
            y += row
        # Extras at the bottom.
        y = fy0 - px(10, k) - row * len(EXTRAS)
        for action, name, icon in EXTRAS:
            self._side_row(action, name, icon, sx0 + px(8, k), y, sx1 - px(8, k), y + row - px(2, k), p,
                           nav=False, rail=rail)
            y += row
        self._chrome_modern_rest(c, p, k, px, sx1, hx1, hy0, hy1, fx0, fy0, fx1, fy1)

    def _side_brand(self, c, p, sx0, pad, y, k, px):
        brand = c.create_text(sx0 + pad + px(4, k), y, text='Marble Oracle', anchor='nw',
                              font=self.font(16, True, False), fill=p['ink'], tags='chrome')
        y = c.bbox(brand)[3] + px(2, k)
        from oracle_version import SUITE_VERSION
        c.create_text(sx0 + pad + px(4, k), y, text=f'Version {SUITE_VERSION}', anchor='nw',
                      font=self.font(9, False, False), fill=p['dim'], tags='chrome')
        y = c.bbox(c.find_all()[-1])[3] + max(10, px(20, k))
        c.create_text(sx0 + pad + px(4, k), y, text='Workspaces', anchor='nw', font=self.font(9, True, False),
                      fill=p['faint'] if p['appearance'] == 'dark' else p['dim'], tags='chrome')
        y += px(18, k)
        return y

    def _chrome_modern_rest(self, c, p, k, px, sx1, hx1, hy0, hy1, fx0, fy0, fx1, fy1):
        # Header: the open workspace's name and what it is for; the window controls.
        self._hdr_title = c.create_text(sx1 + px(20, k), (hy0 + hy1) / 2.0, text='', anchor='w',
                                        font=self.font(15, True, False), fill=p['ink'], tags='chrome')
        self._hdr_blurb = c.create_text(sx1 + px(20, k), (hy0 + hy1) / 2.0, text='', anchor='w',
                                        font=self.font(10, False, False), fill=p['dim'], tags='chrome')
        if self.host is None or getattr(self.host, 'borderless', True):   # an OS title bar has its own buttons
            self._win_glyphs(hx1 - px(4, k), hy0, hy1, p['dim'])
        # Footer status line (the same item ids the other chromes provide).
        fy = (fy0 + fy1) / 2.0
        x = sx1 + px(20, k)
        self.hold_id = self.T(x, fy, '', 12, p['ink'], 'w', 'chrome', True, False)
        self.stat_id = self.T(x, fy, '', 11, p['dim'], 'w', 'chrome', False, False)
        self.mono_w = max(1.0, self.font(11, False, False).measure('M'))
        self.tick_n = max(10, int((fx1 - x - px(120, k)) / self.mono_w))
        self.tick_id = self.T(x, fy, '', 11, p['dim'], 'w', 'chrome', False, False)
        self.tick_full = ''
        self._update_primary_tab_state()

    def _side_row(self, action, name, icon, x0, y0, x1, y1, p, nav=True, rail=False):
        from oracle_skin import px
        c, k = self.c, self.k
        pill = round_rect(c, x0, y0, x1, y1, px(7, k), fill='', outline='', tags='chrome')
        size = max(14 if rail else 12, px(17, k))
        icon_x = (x0 + x1) / 2.0 if rail else x0 + px(12, k) + size / 2.0
        cy = (y0 + y1) / 2.0
        icon_tag = ('chrome', f'sideicon-{action}')
        draw_icon(c, icon, icon_x, cy, size, p['dim'], icon_tag)
        # On the rail the name is not drawn (the header names the open workspace; the hover ring shows where).
        text = c.create_text(icon_x + size / 2.0 + px(10, k), cy, text='' if rail else name, anchor='w',
                             font=self.font(12, False, False), fill=p['ink'], tags='chrome')
        self.hot.append((x0, y0, x1, y1, action))
        self._side_rows[action] = (pill, text, f'sideicon-{action}')
        if nav:
            self.nav_tabs[action] = (pill, text)

    def _update_modern_state(self, active):
        p = oracle_appearance.palette()
        c = self.c
        for action, (pill, text, icon_tag) in getattr(self, '_side_rows', {}).items():
            on = action == active
            try:
                c.itemconfigure(pill, fill=p['select_side'] if on else '')
                c.itemconfigure(text, font=self.font(12, on, False))
                for item in c.find_withtag(icon_tag):
                    kind = c.type(item)
                    colour = p['accent_text'] if on else p['dim']
                    if kind in ('line',):
                        c.itemconfigure(item, fill=colour)
                    else:
                        c.itemconfigure(item, outline=colour)
                        if c.itemcget(item, 'fill'):
                            c.itemconfigure(item, fill=colour)
            except Exception:
                pass
        for action, name, blurb, _icon in WORKSPACES:
            if action == active:
                try:
                    c.itemconfigure(self._hdr_title, text=name)
                    bbox = c.bbox(self._hdr_title)
                    c.coords(self._hdr_blurb, bbox[2] + self.font(10, False, False).measure('  '), c.coords(self._hdr_title)[1])
                    c.itemconfigure(self._hdr_blurb, text=blurb)
                except Exception:
                    pass
