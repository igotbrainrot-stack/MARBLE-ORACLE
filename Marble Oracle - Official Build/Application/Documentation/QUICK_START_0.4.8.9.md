# MARBLE ORACLE — Quick start and field guide (0.4.8.9)

1. Extract the full ZIP to a persistent folder.
2. On Windows, launch **START MARBLE ORACLE - WINDOWS.vbs**. On Linux Mint, launch **START MARBLE ORACLE - LINUX.sh**. Do not run the script from inside the compressed ZIP.
3. Press **F1** at any time inside the suite to see the six workspaces and open one immediately.

## AUGURSPEX — Market Observatory

**FIND MARKET** searches your saved watchlist. Choose **STOCKS**, **CURRENCIES**, **CRYPTO**, or **★ SAVED** for category filters. Select a chart, then select a market to assign it. **MANAGE LIST** changes your watchlist.

**CHARTS** sets the number of chart spaces; **PERIOD** changes the requested historical interval; **VISIBLE** controls how many real observations are shown. **LINE/CANDLES** is the shared style; each card can override it. No fake intraday series is built from daily candles.

**◈ MARKET ATLAS** displays all watchlist instruments in a sortable table. A missing source is blank, never zero. Select an instrument and use **OPEN IN ACTIVE CHART**, or **EXPORT SUMMARY CSV** for an offline record.

**▤ OBSERVATION TABLE** shows exact downloaded historical rows from the selected chart. It is particularly useful for users who need text instead of a graph.

**Keyboard chart inspection:** Click a chart to focus its graph, then use **Left/Right** for each historical point and **Home/End** to jump to the first/last point. Keyboard focus has a visible outline.

**CSV** exports the selected chart. On close-only datasets, the open, high, and low columns are blank by design. **SOURCE DETAILS** explains the actual provider and what it returned.

**F1** opens the app-wide guide. **Escape** closes the guide or the AUGURSPEX workspace when it has focus.

## A note on data accuracy

AUGURSPEX charts are historical observations from their named providers. US stocks may be delayed or unavailable; crypto can come from venue OHLC or labelled multi-venue aggregations; FX reference rates are not live executable exchange quotes. Some international exchanges require a key or entitlement. Source restrictions cannot be solved by changing the appearance of the charts.

All user settings are stored locally; this release does not change the existing watchlist-reset migration. The screenshot preview bundled with this release is synthetic **test data**, not live market pricing.
