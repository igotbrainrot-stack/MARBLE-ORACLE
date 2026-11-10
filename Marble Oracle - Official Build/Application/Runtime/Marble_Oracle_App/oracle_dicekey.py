"""oracle_dicekey.py -- DICEKEY, the passphrase roller.  Stdlib only, no network, nothing is stored.

A roll is four tokens:   word word word DDs      e.g.  calm copper rinse 93+
  * three words from the EFF long list (7,776 words), each with at least four letters (only a-z count; hyphens are
    dropped before counting, so "drop-down" is allowed);
  * the first two share a first letter (spelling, not sound: "phone" pairs with "forest", "knee" not with "night");
  * the third is any other eligible word, never a repeat of word one or two;
  * a tail of two digits (00-99) and one symbol from SYMBOLS, no space inside it.
Randomness is the `secrets` module (os.urandom, with rejection sampling inside randbelow); never `random`.

Since build 0997 each part can be re-rolled on its own (reroll()): word 1, word 2, word 3, the two digits, the symbol.  A re-roll draws uniformly from what the rules still allow and never
returns the value it replaces, so pressing it always changes the part.  Word 1 and word 2 are re-rolled inside the bucket of the other one, so the pair keeps its shared first letter;
when no other word with that letter exists, the pair is re-rolled together with a different letter and the note says so.  The pattern entropy figure is for a roll accepted as it
comes: re-rolling a part because you dislike it makes the phrase a little easier to guess (the view says so once a part has been re-rolled).

The word list is data/eff_large.txt: the EFF long list, dice code and word per line (credit and licence in
data/eff_large_CREDITS.txt).  It is found by the shared asset search (MARBLE_ORACLE_ASSETS, then data/, then a flat
copy beside this file).  Without it, make() returns None and the host leaves the tab out.
PATTERN_BITS is computed from the list actually loaded, by the handover's formula:
    log2(|first pool|) + mean over first-pool words of log2(bucket - 1) + log2(|eligible| - 2) + log2(100) + log2(|symbols|)
With the EFF list it is 44.33 bits.  It is the entropy of this method, not a crack time.

The module has two halves: the engine (Dicekey, no Tk) and Session, the canvas view the host's tab uses (the overlay
seam every tab shares).  The view draws with canvas items only and holds the phrase in memory only while the tab is
open.  COPY is the one way out, and only when the person presses it.
"""
import math
import os
import re
import secrets

import oracle_assets

SYMBOLS = "#?!@$%&*+"
PARTS = ("w1", "w2", "w3", "digits", "symbol")            # the five things a phrase is made of, in reading order
PART_NAMES = {"w1": "WORD 1", "w2": "WORD 2", "w3": "WORD 3", "digits": "NUMBER", "symbol": "SYMBOL"}
MIN_LETTERS = 4
_here = os.path.dirname(os.path.abspath(__file__))
FILES = ("eff_large.txt",)
TAIL_RE = re.compile(r"^[0-9]{2}[#?!@$%&*+]$")


class NoWords(Exception):
    """No word list could be read."""


def letters(word):
    """Only a-z count: 'drop-down' has eight letters."""
    return re.sub(r"[^a-z]", "", word)


def initial(word):
    """Alliteration key (grapheme initial): the first letter, hyphens ignored."""
    s = letters(word)
    return s[:1]


def parse(text):
    """Word list text -> words in order.  Accepts 'word', '11111<tab/space>word' lines; skips blanks, comments, dupes."""
    out, seen = [], set()
    for line in text.splitlines():
        parts = line.strip().lower().split()
        if not parts or parts[0].startswith("#"):
            continue
        w = parts[-1]
        if re.fullmatch(r"[a-z-]+", w) and w not in seen:
            seen.add(w)
            out.append(w)
    return out


def load_words(dirs=None):
    """(words, source filename). `dirs` is an explicit list of folders. Otherwise the shared asset search
    (MARBLE_ORACLE_ASSETS, then data/ beside this file, then a flat copy beside this file)."""
    paths = []
    if dirs:
        for d in dirs:
            for name in FILES:
                paths.append(os.path.join(d, name))
    else:
        for name in FILES:
            p = oracle_assets.asset(name, _here)
            if p:
                paths.append(p)
    for p in paths:
        try:
            with open(p, encoding="utf-8", errors="ignore") as f:
                words = parse(f.read())
        except OSError:
            continue
        if len(words) >= 100:
            return words, os.path.basename(p)
    raise NoWords("no word list")


def randint(n):
    """Uniform 0..n-1 (secrets.randbelow: rejection sampling over os.urandom)."""
    return secrets.randbelow(n)


class Dicekey:
    def __init__(self, words=None, source="given"):
        if words is None:
            words, source = load_words()
        self.source = source
        self.size = len(words)
        self.index = {w: i for i, w in enumerate(words)}          # position in the list, for the dice code
        self.eligible = [w for w in words if len(letters(w)) >= MIN_LETTERS]
        if len(self.eligible) < 100:
            raise NoWords("word list too short")
        self.buckets = {}
        for w in self.eligible:
            self.buckets.setdefault(initial(w), []).append(w)
        self.first_pool = [w for w in self.eligible if len(self.buckets[initial(w)]) >= 2]
        n1 = len(self.first_pool)
        mean_b = sum(math.log2(len(self.buckets[initial(w)]) - 1) for w in self.first_pool) / n1
        self.bits = (math.log2(n1) + mean_b + math.log2(len(self.eligible) - 2) + math.log2(100)
                     + math.log2(len(SYMBOLS)))

    def roll(self):
        """One passphrase string: 'word word word DDs'."""
        w1 = self.first_pool[randint(len(self.first_pool))]
        b = self.buckets[initial(w1)]
        w2 = w1
        while w2 == w1:                                   # uniform over the other words in the bucket
            w2 = b[randint(len(b))]
        w3 = w1
        while w3 in (w1, w2):                             # rejection sample: uniform over the rest
            w3 = self.eligible[randint(len(self.eligible))]
        tail = "%02d%s" % (randint(100), SYMBOLS[randint(len(SYMBOLS))])
        return "%s %s %s %s" % (w1, w2, w3, tail)

    def split(self, phrase):
        """(w1, w2, w3, digits, symbol) of a phrase of the right shape, else None."""
        p = (phrase or "").split(" ")
        if len(p) != 4 or not TAIL_RE.match(p[3]):
            return None
        return p[0], p[1], p[2], p[3][:2], p[3][2]

    def reroll(self, phrase, part):
        """(new phrase, note): the phrase with ONE part drawn again.  The new value is never the one it replaces and every other part is untouched.
        `note` is '' normally; it says so when a word could not be re-rolled inside its pair and the pair was re-rolled together instead; when nothing else is possible
        the phrase comes back unchanged with a note.  Raises ValueError for an unknown part or a phrase that is not one of ours."""
        parts = self.split(phrase)
        if parts is None or part not in PARTS:
            raise ValueError("cannot re-roll %r of %r" % (part, phrase))
        w1, w2, w3, digits, symbol = parts
        note = ""
        if part in ("w1", "w2"):
            other = w2 if part == "w1" else w1
            pool = [w for w in self.buckets.get(initial(other), ()) if w not in (w1, w2, w3)]
            if pool:
                new = pool[randint(len(pool))]
                w1, w2 = (new, w2) if part == "w1" else (w1, new)
            else:                                           # no other word with this first letter: draw the pair again, with another letter
                firsts = [w for w in self.first_pool if w != w3 and initial(w) != initial(other)
                          and any(x not in (w, w3) for x in self.buckets[initial(w)])]
                if not firsts:
                    return phrase, "NOTHING ELSE TO ROLL"
                a = firsts[randint(len(firsts))]
                rest = [x for x in self.buckets[initial(a)] if x not in (a, w3)]
                w1, w2 = a, rest[randint(len(rest))]
                note = "NO OTHER WORD STARTS WITH %s: THE PAIR WAS RE-ROLLED" % initial(other).upper()
        elif part == "w3":
            new = w3
            while new in (w1, w2, w3):                      # rejection sampling, uniform over the rest
                new = self.eligible[randint(len(self.eligible))]
            w3 = new
        elif part == "digits":
            n = randint(99)                                 # uniform over the 99 other numbers
            n += 1 if n >= int(digits) else 0
            digits = "%02d" % n
        else:
            k = randint(len(SYMBOLS) - 1)                   # uniform over the other symbols
            k += 1 if k >= SYMBOLS.index(symbol) else 0
            symbol = SYMBOLS[k]
        return "%s %s %s %s%s" % (w1, w2, w3, digits, symbol), note

    def swap_first_two(self, phrase):
        """Exchange the first two words without changing entropy or other tokens."""
        if not self.check(phrase):
            raise ValueError("invalid passphrase")
        w1, w2, w3, tail = phrase.split(" ")
        return "%s %s %s %s" % (w2, w1, w3, tail)

    def dice(self, word):
        """The five-dice code of a word (11111 is the first word of the list, 66666 the last), or '' for a list that is
        not the full 7,776 words."""
        i = self.index.get(word)
        if i is None or self.size != 7776:
            return ""
        digits = []
        for _ in range(5):
            digits.append(str(i % 6 + 1))
            i //= 6
        return "".join(reversed(digits))

    def check(self, phrase):
        """True if `phrase` has the shape a roll can produce (used by the tests and the host's selftest)."""
        p = phrase.split(" ")
        if len(p) != 4 or phrase != " ".join(p) or not TAIL_RE.match(p[3]):
            return False
        w1, w2, w3 = p[:3]
        return (all(len(letters(w)) >= MIN_LETTERS for w in (w1, w2, w3)) and initial(w1) == initial(w2)
                and len({w1, w2, w3}) == 3)


def make(words=None):
    """The host's entry point: a Dicekey, or None when there is no word list (the tab is then left out)."""
    try:
        return Dicekey(words)
    except Exception:
        return None


def running():
    return None


def shutdown():
    pass


# ---------------------------------------------------------------------------------------------------------------------
# The canvas view (the overlay seam: layout / draw / clear / key / key_up / click / release / tick / busy / cover)
# ---------------------------------------------------------------------------------------------------------------------
try:
    import oracle_vhs as _vhs                        # the 90s infomercial look (build 0958); optional: without it the card is the flat one
except Exception:
    _vhs = None

TAG = "dkwin"
THEME = dict(bg="#06060d", panel="#0a0c18", edge="#17415a", edge2="#0f2233", cyan="#19e6ff", mag="#ff2bd6",
             gold="#ffd23f", lime="#7cff6b", red="#ff4d5e", txt="#c9d4e8", dim="#5d6d8a")
SIZES = (40, 36, 32, 28, 25, 22, 20, 18, 16, 14, 12)          # whole-pixel sizes for the phrase, largest that fits wins
COPIED_SECS = 1.6
KEYPARTS = {"1": "w1", "2": "w2", "3": "w3", "4": "digits", "5": "symbol",
            "KP_1": "w1", "KP_2": "w2", "KP_3": "w3", "KP_4": "digits", "KP_5": "symbol"}


# The old canvas Session UI was replaced by marble_passphrase_tab.PassphrasePanel.
