# Marble Oracle 0.4.8.0 — AUGURSPEX high-contrast chart update

Date: 13 November 2026

## Changes

AUGURSPEX native chart workspace:

- Adds a rectangular graph boundary and distinct **horizontal and vertical grid lines**, drawn beneath price data. Grid colour follows the existing dark Oggcultist palette.
- In **LINE** mode, increases the coloured line to **4.4 Tk canvas units** and adds a dark **7.4-unit outer outline** to improve contrast with the textured chart background. The final observation marker is enlarged and outlined.
- In **CANDLES** mode, uses thicker **2.8-unit coloured wicks** with **5-unit dark outlines**, plus high-contrast filled candle bodies with 2-unit outlines and light top-edge highlights on larger bodies.
- On small chart cards, candle mode displays the most recent actual OHLC observations that can fit at approximately six pixels per bar. This limits visual crowding without fabricating or aggregating records. A note identifies how many real observations are visible out of the available history. LINE mode still displays the full available history.
- Retains actual date labels along the lower axis and price ticks along the right axis; adds more bottom clearance so the data-count note does not crowd the dates.

HOME's rotating AUGURSPEX chart:

- Adds a visible framed grid with three interior horizontal and three interior vertical guides.
- Uses a dark outer price-line stroke and a thicker contrasting inner stroke, with an outlined latest-price marker.

## Scope and preservation

- No changes to market-data providers, the watchlist or user settings.
- No changes to the EIDOLITH converter or other suite workspaces.
- Retains the tab order **HOME / OGGCULTIST / EIDOLITH / AUGURSPEX / PASSPHRASE / TOUCH TYPE**.
- Retains the original Oggcultist textures, dark colours, no-news footer and non-fabrication policy for chart data.

## Verification

- `Tests/test_augurspex_grid_contrast_0480.py`: PASSED under Xvfb, including both drawing styles and adaptive candle visibility.
- `Tests/test_augurspex_chart_axes_and_history.py`: PASSED under Xvfb.
- `Tests/test_augurspex_native_tab.py`: PASSED under Xvfb.
- `Tests/test_augurspex_home_gui.py`: PASSED under Xvfb after fixing the fixture to include the reception timestamp required by existing stale-cache safeguards.
- `Tests/test_no_news_or_markets.py`: PASSED under Xvfb after disabling network for this layout-only test.
- `Tests/test_augurspex_source_details_gui_0478.py`: PASSED under Xvfb.
- `Tests/test_augurspex_home_carousel.py`: four tests passed.
- `Tests/test_tab_layout.py`: standard/retro/flat passed in an earlier isolated run. A later combined run timed out; no claim of complete full-suite coverage.
- Visual review: inspected a locally rendered synthetic test dataset in both line and candle modes. This data is not bundled or used in production.

## Remaining limits

Live market-provider reliability still depends on third-party services and exchange licensing. Actual Windows and physical Linux Mint desktop testing were not performed for this point release. The FFmpeg conversion regression was not rerun because no converter source was changed.
