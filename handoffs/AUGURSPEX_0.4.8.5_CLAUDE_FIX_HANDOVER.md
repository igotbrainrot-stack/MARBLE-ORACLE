# Claude handover — Marble Oracle AUGURSPEX 0.4.8.5

**Branch:** `fix/augurspex-chart-layout-0485-20261113`

**Base:** GitHub's existing `handover/augurspex-0484-layout-20261113` draft PR #2. Never merge PR #2 as if it were the fix. The 0.4.8.4 source snapshot is in that handover branch's `handoffs/augurspex-0.4.8.4/` folder. The repaired portable 0.4.8.5 ZIP is delivered through the ChatGPT artifact link separately. The source snapshot by itself lacks many binary suite assets.

## Previously blocking user reports

- Text overlap/clipping, especially date/price labels and status strips.
- CHARTS 1/2/4/6/9 selector appeared not to work when `sourced_only` was enabled.
- Chart height remained ~405px even with a single market.

## Fixes included

- `oracle_augurspex_tab.py`: `chart_grid_plan` pure layout model; `CHART_PAD_R/B` reserved bands; measured date label intersection rejection; observation note removed from chart canvas; Close-only history message kept in footer.
- `AugurspexPanel._chart_slots()`: sourced display draws from all nine persistent assignments, not just the first N. Limits display to selected count, but never deletes slots or market data.
- `_display_slots` maps current card position to the persisted slot index. `_select_chart` uses that mapping so a market displayed in card 0 can legitimately be saved as slot 8. `_source_details_text()` continues using the saved active slot.
- `_layout_chart_cards` derives row height from true viewport and visible count; adaptive one/two columns; scroll only as required. `_layout_signature` suppresses redundant grid rebuilding during `Configure` cascades.
- New indicator `X DISPLAYED / Y REQUESTED` explains why nine requested charts may show one when only one source is verified. A transient failure hides a card rather than deleting the saved selection.
- `_fit_status_strips` shortens the visible status/footer at narrower widths without losing full diagnostic text in state and SOURCE DETAILS.

## Acceptance evidence

- `Application/Tests/test_augurspex_chart_repair_0485.py` uses deterministic local fixture observations and asserts actual pixel dimensions, no date/price label bounding-box overlap, proper chart-count behavior, persisted slot-9 visibility at CHARTS=1, and scrolling at 900×580.
- At 1400×870: single = 1046×496 px; four = 508×218; nine = 508×215. At 900×580: single = 546×237; nine = 546×229, with vertical scroll.
- Screenshot PNGs named `MARBLE_ORACLE_AUGURSPEX_0485_*_CH_TEST.png` are **synthetic test data, not live market prices**.
- The suite remains entirely native Tk and retains the darker Oggcultist texture, thick grid/candle/line strokes, six-tab order HOME–OGGCULTIST–EIDOLITH–AUGURSPEX–PASSPHRASE–TOUCH TYPE, and HOME watchlist carousel.

## Next steps for Claude

1. Check out the 0.4.8.5 fix branch. Restore the full original 0.4.8.4 source snapshot first if necessary, then overlay the source and test changes from the fix branch/patch. Do not accidentally replace newer contributors' work.
2. Reproduce with actual Linux Mint GTK session, Windows 11 Tk, and different DPI/font scaling. Use the 900×580 and 1400×870 screenshots to compare.
3. Test long translated company names, extremely large/small index price levels, very narrow chart canvases, and different Tk font fallback behavior. Address any remaining display clipping.
4. Verify keyboard accessibility to the OptionMenu, scroll wheel, and show-all/show-sourced toggle. Implement a clear market-assignment UI for an empty sourced-only view if necessary.
5. Run the 0.4.8.5 regression plus previous test suite. Recheck EIDOLITH queue/full conversion and physical FFmpeg hardware where possible; those components were not changed here.
6. Do not claim unavailable exchanges are fixed by the layout repair. API keys, exchange entitlements, and free provider outages still apply. Do not fabricate OHLC bars or proxy an unrelated stock.
7. Leave the new PR unmerged for user review. Do not commit API keys, `~/.config/augurspex`, provider caches, or quoted price data.

## Verification limitations

Automated tests are Linux Xvfb synthetic fixtures. No physical Windows/Linux Mint graphical session or live-provider check was run for this fix. `verify_release.py` checks packaging hashes/assets, not real-world UI correctness. Screenshot visual checks supplement, rather than replace, automated bounds tests.
