# MARBLE ORACLE / AUGURSPEX — urgent Claude handover (13 Nov 2026)

**Status: BROKEN / NOT ACCEPTED.** This is a handover of the most recent runnable *but defective* local build, **Marble Oracle 0.4.8.4**. The user explicitly reports: **text overlaps, the CHARTS amount selector is broken, and chart dimensions remain essentially unchanged**. Do not repeat earlier claims that GUI regressions passed; the user's actual screenshots/desktop behavior supersedes those checks. The user asked for the current work on GitHub plus an actionable handover for Claude, **not another untested cosmetic patch**.

## Repository and exact input

- Repository: `https://github.com/igotbrainrot-stack/MARBLE-ORACLE`
- Upstream source branch known to exist: `claude/eidolith-reliability`. **Inspect current branch/PR state first; do not assume `main` has AUGURSPEX**.
- Supplied complete local application: `Marble-Oracle-EIDOLITH-0.4.8.4-AUGURSPEX-SPACIOUS-SOURCED-Windows-Linux.zip`, SHA-256: **9505949117c4ccd36d3ab6c73cb803f689dec42f4c192350b3048f604ddd1209**. **The full local application ZIP is the authoritative 0.4.8.4 code snapshot**, not GitHub's older 0.3/0.4.x tree and not the initial standalone AUGURSPEX 1.2 zip. Ask for the ZIP attachment if not present in Claude's environment.
- Unzip, then source root: `Marble Oracle - Official Build/Application/Runtime/Marble_Oracle_App/`.
- Main UI file to fix: `oracle_augurspex_tab.py` (~58 KB). Main launcher and integration: `marble_oracle.py`, `oracle_chrome.py`, `oracle_augurspex_home.py`, `Augurspex/augurspex/core.py`, `Augurspex/augurspex/providers.py`.
- Existing regression tests (in `Application/Tests/`): `test_augurspex_sourced_layout_0484.py`, `test_augurspex_scrollable_0483.py`, `test_augurspex_readability_0481.py`, `test_augurspex_grid_contrast_0480.py`, `test_augurspex_native_tab.py`, `test_augurspex_source_details_gui_0478.py`, `test_tab_layout.py`.

## User's stated expectations (priority order)

1. **Readable** AUGURSPEX: no colliding text, clipped legends, dates, price scales, labels, status strips or menu controls at practical window dimensions.
2. **Working CHARTS count selector:** choosing 1, 2, 4, 6 or 9 has an observable, predictable effect. It must correctly retain the intended chart slots, not silently change to a random filtered number. Distinguish 'requested slots' from 'verified-data slots'.
3. **Actual chart resizing:** selecting one chart should show a substantially larger graph than selecting multiple. Don't leave each card pinned to the same 405 px height while the rest of the panel is empty. Use available viewport width/height, with scrolling only when needed.
4. Keep the much darker Oggcultist film grain background, matching colour palette, larger legible fonts, strong chart grids, thick line/candle outlines, visible price/date axes, and native embedded tab.
5. Keep the 6-tab order: HOME, OGGCULTIST, EIDOLITH, AUGURSPEX, PASSPHRASE, TOUCH TYPE.
6. Remove or conceal assets that genuinely have **no usable actual provider data**, but do so non-destructively: **never delete the saved watchlist solely because of a provider timeout, cooldown or exchange-license restriction.** Expose 'Show all markets / retry' and clear count/status.
7. Preserve real source attribution, accurate timestamp/interval, rate limiting, and no fabricated candles/quote values. Do not take EIDOLITH/Oggcultist regression risk for an AUGURSPEX layout repair.

## Concrete defects confirmed by code inspection

### A. Chart-count selection is disconnected from displayed chart count

`AugurspexPanel._change_layout` (around line 807) updates `settings['layout']`, calls `_render_grid` and saves. `_render_grid` (around 876) creates `count=settings['layout']` cards. **BUT** `_chart_indices()` (around line 679) returns only cards whose saved slot is already verified by `_market_verified()` when `sourced_only` is true. `_layout_chart_cards` (around 843) then `grid_forget()`s all cards and only grids filtered indices. Thus choosing 9 can show exactly the same one or two cards as choosing 2; when the only verified assets are in later slots, choosing 1/2 may show **zero** cards. That's the likely root cause of the user's "broken selector" experience.

**Required design decision:** separate `requested_layout_count`, an ordered *visible sourced market* model, and *actual rendered cards*. Preserve full saved slots with stable identities. Choose a coherent policy for fewer sourced markets than slots (e.g., show actual sourced charts prominently with clear `2 sourced / 9 requested` badge and a way to manage blank/failed slots), then test each count against market data in positions 0, 3 and 8. Avoid hiding the only valid market because its assigned index exceeds the requested layout. Never imply there are nine usable charts if only two have history.

### B. Fixed minimum height makes graph sizes appear unchanged

`_layout_chart_cards` forces `rowconfigure(... minsize=405, uniform='cards')` for every row even when only one visible chart is on screen. `_resize_chart_view` chooses only `min(2, max(1, width//565), ...)` columns. As a result the one-chart and two-chart layouts frequently use similarly sized 405px-high rows; the chart can fail to expand into vertical space. The 292px rail plus window/bezel constrains viewport width. The 0.4.8.3 scrolling repair avoided 1x1 canvases but broke the intended relationship between chart count and chart size.

**Required:** derive card grid from requested count and available viewport dimensions, not a hard-coded 405px row for all modes. In 1-chart mode the plot should fill the viewport (allowing for visible header/footer), with larger plot than 4/9 mode. In dense mode, use a predictable 2- or 3-column grid with legible minimums and vertical scroll. The chart canvas should get true height/width after geometry settles; don't change grids on every `<Configure>` if that produces resize oscillation.

### C. Text and axis labels can still overlap

`PriceChart.redraw` draws date ticks at `plot_bottom + 8`, observation note at `height - 3`, prices at `plot_right + 8`, while `CHART_PAD_B = 51` and `CHART_PAD_R = 74`. Labels use a high-contrast 11px font. At smaller card dimensions, date labels and notes can collide (especially when `chart_date_ticks` places too many labels or thick text is variable width). `PriceChart._fit_card_labels` fits company/info text by width, but not all title/price elements and doesn't guarantee vertical height. The whole UI contains `tk.OptionMenu`s, a wrapped selected-market label, source footer/status, and a narrow embedded CRT viewport.

**Required:** write a clipping/layout test that inspects `Canvas.bbox` for all text items and their anchor regions, ensuring date labels, price axes, note and chart status do not intersect in rendered pixel coordinates, at 900x580 / 1000x650 / 1400x870 and with 1/2/4/6/9 charts. Measure actual font extents and omit minor tick labels on narrow charts rather than generating intersections. Reserve separate, non-overlapping axis and note bands; consider rendering the note in the status strip outside the plot canvas.

### D. Sourced-only filtering creates confusing empty states

`_refresh_watch` excludes all unverified symbols from the entire watchlist by default. Initial provider verification is asynchronous; with zero cached results the UI may appear empty or broken. `_prepare_audit` probes all symbols sequentially with slow providers; `sourced_only` is true by default. The user sees "not working" before asynchronous source probes have completed. Source verification must not remove navigation/selection controls, and a failed provider does **not** mean a market doesn't exist.

**Required:** show `verifying N/M` progress, last successful observation, state categories (`verifying`, `verified`, `temporarily unavailable`, `permission required`, `unsupported`), and a source-management panel with retry. Separate permanent unsupported symbols from timeouts/429/403 and avoid deleting settings.

## Reproduction/diagnostic plan (must run in the actual integrated app)

1. Extract authoritative 0.4.8.4 release to a clean directory; verify baseline with `python3 Application/Tools/verify_release.py` **before edits**. Don't alter release inventories until tests pass.
2. In a virtual display (Linux): `xvfb-run -a python3 Application/Tests/test_augurspex_native_tab.py` and `xvfb-run -a python3 Application/Tests/test_augurspex_sourced_layout_0484.py`. Existing tests passing is NOT sufficient; add failing tests first based on report.
3. Inject a deterministic fake router with **realistic but synthetic test fixtures, labelled TEST**. Make success only for slots 1, 5 and 9, fail others; repeat with success only for slots 4 and 8. No network is needed for layout tests.
4. Click CHARTS 1 / 2 / 4 / 6 / 9 via the actual `tk.OptionMenu` callbacks; check settings persistence, rendered `winfo_ismapped()` cards, `chart_canvas` and each `PriceChart.canvas` actual pixel widths/heights, scrollregion, and selection. Test restart and workspace switch.
5. Compare single-chart pixel area to multi-chart pixel area. Acceptance: in a 1400×870 window, one valid chart occupies clearly more area than when 4+ charts are visible. At 900×580, all controls remain reachable, with chart vertical scrolling as needed.
6. Use `Canvas.bbox(item)` to test date labels, axis levels, observation note, and explanatory text for collisions with each other or chart border. Generate and inspect screenshots at 900×580, 1000×650, 1400×870 for 1/2/4/6/9, varying theme/GRADE if needed.
7. Add explicit check for `SOURCE DETAILS`, side-list filters, bottom `BACK TO HOME`, chart interval selectors and HOME chart after layout modifications. Test app never launches a browser on AUGURSPEX tab click.
8. Confirm providers are not contacted on the Tk render thread; fake router only. Keep the real provider router untouched unless necessary. Run representative provider tests and EIDOLITH queue smoke tests after UI changes.
9. Once layout and behavior pass, regenerate `Application/Documentation/BUILD_MANIFEST.json` + `FILE_INVENTORY.json`, package full Windows/Linux ZIP, validate extraction and executable Linux `.sh`. Native Windows and real Linux desktop still require physical testing.

## Likely implementation approach (not a command to blindly implement)

- Build a view model of `ChartSlot` with stable `slot_id`, `symbol`, `provider_state`, `last_data`, `visible` and `selection` distinct from `settings['layout']`. Derive displayed cards from requested count consistently.
- Create a dedicated `ChartGridController.relayout(viewport_w, viewport_h, requested_count, verified_count)` pure function returning rows, columns, pixel minima and scroll requirement; test it without Tk. Use `after_idle` debounce for geometrical relayout and avoid nested forced Tk update loops.
- Guarantee a minimum internal plotting size for large charts (e.g. width >= 360, plot height >= 230) while allowing one chart to expand vertically. Compute height from visible viewport and rows, not global fixed minsize for all modes.
- Put the chart's observation note in its own footer or provide an explicit bottom band below the date axis; reject canvas text bounding-box overlaps, including right-axis collisions with points.
- Make `CHARTS` a semantic control: `1/2/4/6/9 requested`, show count of verified data and one-click market assignment. If there are fewer valid tickers than requested slots, do not silently render a misleading fixed count. Preserve all 9 saved entries across layout decreases.

## Critical constraints

- Do NOT remove EIDOLITH, OGGCULTIST, PASS, TOUCH TYPE, HOME, assets, launcher scripts or the photos/texture references.
- Do NOT place user API keys, watchlists, personal cache, secrets or live price dumps in Git. `~/.config/augurspex` is local user state and must stay local.
- Do NOT invent quotes/candles or silently substitute ETFs/indexes for an unavailable stock.
- Do NOT restore the old RSS ticker or fixed Bitcoin/gold pane. The HOME rotating chart should remain.
- Work on **one new branch**, open a PR for review, **do not merge** without user direction. Github currently may not contain 0.4.8.4 code; never overwrite another contributor's work with an old tree.

## Deliverables to user

1. Source branch/PR containing **real fix**, not just screenshots or a handover.
2. Before/after screenshots at two window sizes and chart counts 1/4/9, with simulated data clearly labelled.
3. Passing failing-first regression suite and actual chart dimensions reported.
4. Full portable ZIP with SHA-256 and verified Linux launcher.
5. Honest matrix: verified automated tests vs actual Windows/Linux hardware and live third-party data.

## Current handover packaging / state

The 0.4.8.4 full application ZIP is available separately in the ChatGPT conversation. A smaller source-only handover ZIP can accompany this document for Claude, but is **not a replacement for the full package's bundled art, textures, sounds, FFmpeg assets and launcher**. The GitHub repo presently has older baseline branches. Any handover-only branch/PR must be treated as a placeholder until Claude imports the 0.4.8.4 source and commits actual fixes.