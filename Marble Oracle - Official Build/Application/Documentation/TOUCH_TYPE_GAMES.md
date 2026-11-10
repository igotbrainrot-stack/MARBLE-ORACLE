# TOUCH TYPE — Learn touch typing inside Marble Oracle

Version: first release. Added as the fourth top-level tab after HOME, PASSPHRASE and OGGCULTIST. No external services, accounts, new dependencies, or terminal are needed.

## Four games

1. **HOME ROW** — Seven four-key sequences per round, separated by spaces. The lesson selector progresses through F/J, D/K, S/L, A/semicolon, and all home-row letters. The next physical key is highlighted on the visual QWERTY keyboard, and the app labels the finger to use.
2. **WORD SPRINT** — Type as many words as possible in one 60-second round. Press Space after each word. View completed words, WPM and accuracy live.
3. **KEYFALL** — Type each descending word before it reaches the bottom. Four misses end the round, or clear twelve words to win. The descent gradually speeds up.
4. **SENTENCE LAB** — Finish three short lowercase sentences with punctuation. Mistyped keys do not advance the text; correct the mistake by striking the indicated key.

## Controls

- Select TOUCH TYPE from the top navigation bar.
- Select a game from the left sidebar, then choose **START GAME**.
- Type using your physical keyboard in the highlighted input field. Correct keys advance the highlighted prompt; errors stay on that key until corrected.
- The SPACE key is shown as a middle dot (·) in the practice text.
- PAUSE/RESUME temporarily stops the timer. RESET resets the current game.
- Escape or BACK TO ORACLE returns to HOME.
- Changing tabs automatically pauses the round; reopening TOUCH TYPE resumes the same session in PAUSED state until you choose RESUME.

## Progress and privacy

- Live accuracy = correctly entered keystrokes ÷ all attempted printable keystrokes.
- WPM = correct characters ÷ 5 ÷ elapsed minutes (conventional five-character word).
- After each completed round, best WPM, accuracy and score are stored in the user's Marble Oracle state directory as `touch_type_scores.json`.
- No typed personal data or practice keystroke history is saved. Only aggregate best scores and session totals are stored.
- No internet connection is required.

## Implementation

- `Application/Runtime/Marble_Oracle_App/oracle_touch_type.py`: portable Tk panel plus testable game engine.
- `Application/Tests/test_touch_type.py`: engine, native keyboard events, overlay navigation, pause/resume and sizing tests.
- Uses the existing Oggcultist Ember design tokens (`oggcultist_design_system.COLOR`) and Uberata Clear.
