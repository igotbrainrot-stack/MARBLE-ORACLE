# Design and layout review: Marble Oracle 0.5.4

**Date:** 25 November 2026
**Starting point:** 0.5.3

## How it was reviewed

**Screens captured:**
- Every workspace, in each of the three looks (Dark, Light and Classic), at five window sizes: 900×580, 1000×650, 1216×848 (the default), 1280×720 and 1920×1080. That is 231 screenshots.
- The welcome guide, the Appearance window and the setup window.
- Each screen was read by eye.

**Code checked for consistency:**
- hard-coded colours, fonts and buttons;
- the measured contrast of every text colour on every surface.

**How to read the issue list:**
- **Severity:**
  - **High:** wrong or unreadable.
  - **Medium:** looks unfinished or inconsistent.
  - **Low:** polish.
- **Status:** each issue is marked **Fixed**, **Partly** or **Open**.

## Issues found

| # | Severity | Where | Issue | Status |
|---|---|---|---|---|
| 1 | High | Light, AUGURSPEX | Market colours (stocks amber, FX teal, crypto lilac) were Dark's pastels: **1.5:1** on Light's white cards. Watchlist rows and filter chips were close to unreadable. | **Fixed.** Recomputed for each look's surfaces (≥4.5:1). |
| 2 | High | Dark and Light, everywhere | Secondary text (dim), green and red fell below WCAG AA on fields: 3.3–4.1:1, and below it on every Light surface. Text on Blue accent buttons in Dark was 3.6:1. | **Fixed.** OVERCAST 1.1.3's palette nudges each colour, keeping its hue, until it reads at 4.5:1 on the page, cards, sidebar and fields. Text on accent buttons takes the best available pairing. A test checks every look and accent. |
| 3 | High | AUGURSPEX | Selected chips and segments (All, Line/Candles, the selected watchlist row) put accent text on an accent-tinted fill: 3.5:1. | **Fixed.** Bright text on selections in Dark/Light; Classic is unchanged. |
| 4 | High | Touch Type (Dark/Light) | After 0.5.4's HOME change the workspace failed to open: a label was packed "before" a button that is no longer shown. | **Fixed** before release, and covered by the new test. |
| 5 | High | OVERCAST dashboard, below about 1000×650 | Card text was cut off mid-line with no way to reach the rest. | **Fixed.** A slim scroll bar appears only when a card's text overflows. |
| 6 | High | OVERCAST sidebar | "Model not connected" was clipped at a fixed 180 px wrap in the suite's narrower rail. | **Fixed.** It wraps to the rail's real width. |
| 7 | High | Eidolith, Convert | Settings below the fold (output naming, overrides) could only be reached by dragging a 10 px scroll bar, so they looked missing. | **Fixed.** The mouse wheel scrolls the column. This uses its own binding tag, so no application-wide binding is touched. |
| 8 | Medium | Every workspace (Dark/Light) | Workspaces written for Classic's capitals shouted in the sans-serif looks ("NO VIDEO LOADED", "SPEED / WPM", "SHOW DICE CODES", "MAX BARS…"), next to a sentence-case shell. | **Fixed** for every widget label: they pass through one rule on the way to Tk. Acronyms, market symbols, keys, key combinations and list numbers keep their capitals. Classic is unchanged. Canvas messages are converted where they are drawn. |
| 9 | Medium | Eidolith, AUGURSPEX, Passphrase, Touch Type, Oggcultist (Dark/Light) | Each workspace carried its own Home button, plus Eidolith's "Marble Oracle 0.5.x · local" line, duplicating the suite's sidebar. | **Fixed.** Left to the sidebar in Dark/Light. The buttons still exist for callers and keyboard use. Classic, which has no sidebar, keeps them. |
| 10 | Medium | Passphrase, Touch Type, AUGURSPEX, Eidolith | Text sat against the left edge of entry fields and text boxes. | **Fixed.** Inner padding on every field in Dark/Light. |
| 11 | Medium | AUGURSPEX rail | Labels drew flat slabs of colour over the textured rail. | **Fixed.** They are textured labels. |
| 12 | Medium | Passphrase, Eidolith, setup window | Tk's 9 px square check boxes, misaligned with their labels. | **Fixed.** Drawn, rounded check boxes in Dark/Light, including the setup window. |
| 13 | Medium | Eidolith player | Tk's square-thumbed sliders for seek and volume, with the volume number floating above. | **Fixed.** A rounded slider (click to jump, drag, arrow keys and wheel), with the volume value beside it. |
| 14 | Medium | Eidolith | Empty source, conversion and job lists looked broken. | **Fixed.** A quiet hint says what to do ("No videos yet. Choose Open or Folder…"). It goes as soon as a row appears. |
| 15 | Medium | Eidolith | Opening the workspace put keyboard focus on the empty file list, so it showed the accent focus ring as if it needed attention. | **Fixed.** Focus goes to the workspace; Tab reaches the list. |
| 16 | Medium | Eidolith viewer, 900×580 | "Choose a video and press PLAY" ran past both edges of the viewer. | **Fixed.** It wraps inside the viewer. |
| 17 | Medium | HOME, Dead tongue, 900×580 | The Voice label sat under the SPEAK button. | **Fixed.** It sits beside SPEAK, and steps aside when there is no room. |
| 18 | Medium | Touch Type, large windows | The keyboard was a strip of 57 px keys over an empty half page at 1920×1080. The finger hint sat far from it. | **Fixed.** The keyboard grows with the room (keys up to 84 px). The finger hint sits between the field and the keyboard. |
| 19 | Medium | Passphrase | Half of the page was empty. | **Fixed.** A "How strong is it" panel when there is room: each part's bits from the engine's own figures, and a plain statement that this is the strength of the method, not a crack time. |
| 20 | Medium | Classic, OVERCAST | The one workspace in its own grey Dark look and sans-serif face. | **Fixed.** Ember colours and the Classic serif in Classic. OVERCAST's own saved look is kept for standalone use. Before, a host's look overwrote it. |
| 21 | Low | Eidolith player | "−10 SEC" / "+10 SEC" | **Fixed** ("−10 sec"). |
| 22 | Low | AUGURSPEX | Dropdown values (LINE, MAX BARS) stay in capitals in Dark/Light. They are option values held in variables, not labels. | **Open.** Cosmetic. |
| 23 | Low | Eidolith, Passphrase, Touch Type, AUGURSPEX | The workspace name appears in the suite's top bar and again as the rail's title. | **Open, by choice.** The same pattern as OVERCAST and Oggcultist. The rail title anchors the workspace's own navigation. |
| 24 | Low | 1920×1080 | The suite's sidebar type grows with the window, but workspace type does not. | **Partly.** Touch Type now uses the room. Other workspaces keep fixed, readable type, and their lists and charts take the extra space. |
| 25 | Low | Eidolith, About | A plain text box with capitalised headings. | **Partly.** Padding added; headings are capitalised in the source text. |
| 26 | Low | Oggcultist player bar, 900×580 | The track title is shortened ("Nothing pl…"). | **Open.** Oggcultist's own layout. Full text on wider windows. |

## What was not checked

- **Hardware:** a physical Windows or Linux PC. Everything here ran under Xvfb and on GitHub's Windows runners.
- **Screen readers:** Tk exposes little to them on any platform.
- **High-DPI scaling** beyond Tk's own.
