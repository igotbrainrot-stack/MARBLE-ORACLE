"""oracle_latin.py -- classical and ecclesiastical Latin for Marble_Oracle (stdlib only; no network, no data files).

Written by another agent from the owner's brief and taken in at build 0955 with its logic untouched; this header is the only change.

    ipa(text, ecclesiastical=False)   IPA for a word or a short line.  False = classical, True = ecclesiastical.
    pair(text)                        (classical IPA, ecclesiastical IPA)
    respell(lemma, ecclesiastical)    ASCII for the formant synthesiser (oracle_audio.synth_wav); same signature as the old toy
    gloss(word)                       English, or "" if unknown (never None); -que is read as "and ..."
    meanings(text)                    [(spelling, english, classical IPA, ecclesiastical IPA)] for each word of a line

    pair("caelum")           -> ("\u02c8ka\u026a.l\u028am", "\u02c8t\u0283e.lum")
    respell("caelum", False) -> "keyelum"          respell("caelum", True) -> "chelum"
    gloss("caelum")          -> "sky; heaven"      gloss("virumque")       -> "and the man"

How the host uses it (build 0955):
  * oracle_audio.respell uses it, so a lemma with no recorded clip is spoken from a real respelling instead of the old toy one.
  * marble_oracle.lexicon_ipa(lemma) asks it for IPA only when the lemma is not one of the fifty in LATIN.  The fifty keep their
    hand-written IPA and their recorded clips (data/latin_voices.zip); this module is the fallback, never the replacement.
  * Both places fall back quietly (the old toy respelling, a "~" respelling row) if this file is missing or raises.

Church Latin here does not hold vowel length, does not elide, softens c/g before e i ae oe y, says v as v, ae/oe as e, gn as ny,
sc as sh, ti+vowel as tsee (not after s, t, x, and not when the i is long).  s stays s.  h is silent except mihi and nihil, which use k.
Classical Latin holds length (the macron table _PATTERNS; unmarked vowels are short) and elides between words (Gallia est).

Changing a pronunciation: change data, not the call shape.  Lengths are in _PATTERNS, glosses in _GLOSS_SRC (a lexical -que / -ne word
that would otherwise be peeled needs its own line there, above the peel).  Add a check to the __main__ block for anything you change.
`python oracle_latin.py` is the acceptance test: it prints "oracle_latin ok" and exits 0, or it raises.
"""

import re
import unicodedata

_MAC = {"\u0101": "a", "\u0113": "e", "\u012b": "i", "\u014d": "o", "\u016b": "u", "\u0233": "y",
        "\u0103": "a", "\u0115": "e", "\u012d": "i", "\u014f": "o", "\u016d": "u",
        "\u00e4": "a", "\u00eb": "e", "\u00ef": "i", "\u00f6": "o", "\u00fc": "u", "\u00ff": "y"}
_LONGM = {"\u0101": "a", "\u0113": "e", "\u012b": "i", "\u014d": "o", "\u016b": "u", "\u0233": "y"}
_BREVE = {"\u0103": "a", "\u0115": "e", "\u012d": "i", "\u014f": "o", "\u016d": "u"}
_DIA = {"\u00e4": "a", "\u00eb": "e", "\u00ef": "i", "\u00f6": "o", "\u00fc": "u", "\u00ff": "y"}
_SHOW = {"a": "\u0101", "e": "\u0113", "i": "\u012b", "o": "\u014d", "u": "\u016b", "y": "\u0233"}
_VOW = set("aeiouy")
_SHORT_O = set("ego modo cito duo".split())
_PRO = set("et sed at ac nec in ab ad ex ob sub cum de e per pro si ut ne seu neu aut".split())
_PRE = set("ab ad con in ob sub re de e ex dis pro per prae se trans".split())
_EU = set("heu eheu seu ceu neu neuter neutra neutrum".split())
_STOP = set("pbtdckg")
_LIQ = set("lr")
_LAB = set("pbmw")
_VEL = set("kg")
_CSHORT = {"a": "a", "e": "\u025b", "i": "\u026a", "o": "\u0254", "u": "\u028a", "y": "y"}
_CLONG = {"a": "a\u02d0", "e": "e\u02d0", "i": "i\u02d0", "o": "o\u02d0", "u": "u\u02d0", "y": "y\u02d0"}
_DIPH = {"ae": "a\u026a", "oe": "\u0254\u026a", "au": "a\u028a", "eu": "\u025b\u028a", "ui": "\u028a\u026a"}
_EVOW = {"a": "a", "e": "e", "i": "i", "o": "o", "u": "u", "y": "i"}

# Macronised spellings. Unmarked vowels are short; only the longs need to be listed.
_PATTERNS = """
vīta cīvis vēritās lūx pāx glōria fortūna senātus sānctus spīritus vōx fidēs grātia
īra lūna sōl rēx cēna virtūs canō trōiae quī prīmus ōrīs partēs excelsīs
antīquus poēta
fīlius fīlia frāter rēgīna amīcus inimīcus mīles nāvis flūmen flōs pānis vīnum nōmen diēs hōra lēx iūs
victōria lībertās rēgnum Rōma fātum beātus pecūnia spēs imāgō ōrāculum sacerdōs prōvincia nātūra fēlix
"""
# Build 0963: the line above was added from a length-by-length comparison of the 150-word table with the engine (every word whose vowel lengths
# or stress differed).  The lengths are the standard dictionary ones, written from memory and NOT checked against a copy of Lewis & Short or Allen
# on the build machine: UNVERIFIED, though in every case but nātūra the table's own IPA agreed with the macron.  Not added, on purpose, because
# the two sources disagree or the length is unsure: the i of fēlix (the package has it long, here it is short: its ē is long in both), and consul
# (the engine has the long ō of cōnsul, the package a short o).  nātūra is here with both long vowels; the package has a short first a.  See docs/LATIN_LEDGER.md.

# oe/ae here are two syllables, not diphthongs. poeta only: verified (Allen). Others not guessed.
_HIATUS = {"poeta"}


def _key(s):
    out = []
    for ch in unicodedata.normalize("NFC", s).lower():
        if ch in _MAC:
            out.append(_MAC[ch])
        elif ch.isalpha():
            out.append("i" if ch == "j" else ch)
    return "".join(out)


def _prep(raw):
    s = unicodedata.normalize("NFC", raw)
    return s.replace("\u00e6", "ae").replace("\u00c6", "Ae").replace("\u0153", "oe").replace("\u0152", "Oe").replace("j", "i").replace("J", "I")


class G:
    __slots__ = ("base", "kind", "ipa", "ln", "known", "explicit", "coda", "light", "nasal")

    def __init__(self, base, kind, ipa="", ln="short", known=True, explicit=False, coda=False, light=False):
        self.base, self.kind, self.ipa = base, kind, ipa
        self.ln, self.known, self.explicit = ln, known, explicit
        self.coda, self.light, self.nasal = coda, light, False


def _vowel_at(chars, i):
    if i >= len(chars):
        return None
    ch = chars[i]
    if ch in _LONGM:
        base, ln, explicit = _LONGM[ch], "long", True
    elif ch in _BREVE:
        base, ln, explicit = _BREVE[ch], "short", True
    elif ch in _DIA:
        base, ln, explicit = _DIA[ch], "unknown", False
    elif ch in _VOW:
        base, ln, explicit = ch, "unknown", False
    else:
        return None
    nxt = i + 1
    if nxt < len(chars) and chars[nxt] == "\u0308":
        nxt += 1
    elif nxt < len(chars) and chars[nxt] in ("\u0304", "\u0306"):
        ln, explicit = ("long", True) if chars[nxt] == "\u0304" else ("short", True)
        nxt += 1
    return base, ln, explicit, nxt


def _cons_ipa(base):
    if base in ("c", "k", "q"):
        return "k"
    if base == "x":
        return "ks"
    if base == "v":
        return "w"
    if base == "ph":
        return "p\u02b0"   # classical aspirate; ecclesiastical overwrites to f
    if base == "th":
        return "t\u02b0"
    if base == "ch":
        return "k\u02b0"
    return "j" if base == "j" else base


def _eu(key):
    return key in _EU or key.startswith("eur") or key.startswith("neu")


def _parse(spelling, key, known_short):
    chars = list(unicodedata.normalize("NFC", spelling).lower())
    out = []
    ui = key in ("cui", "huic", "cuius", "huius")
    i = 0
    while i < len(chars):
        ch = chars[i]
        n1 = chars[i + 1] if i + 1 < len(chars) else ""
        if ch == "q" and (n1 in ("u", "v") or _LONGM.get(n1) == "u"):
            out.append(G("qu", "c", "kw", coda=False))
            i += 2
            continue
        if ch in "ptc" and n1 == "h":
            base = ch + "h"
            out.append(G(base, "c", _cons_ipa(base), light=(base == "h")))
            i += 2
            continue
        if ch not in _VOW and ch not in _LONGM and ch not in _BREVE and ch not in _DIA and ch not in "\u00e6\u0153":
            if ch in "bcdfghklmnpqrstvwxz":
                base = "j" if ch == "j" else ch
                out.append(G(base, "c", _cons_ipa(base), coda=(base == "x"), light=(base == "h")))
            i += 1
            continue
        a = _vowel_at(chars, i)
        if not a:
            i += 1
            continue
        b = _vowel_at(chars, a[3])
        pair = (a[0] + b[0]) if b else ""
        # poeta is po-ē-ta (hiatus), not the diphthong oe. Allen, Vox Latina. Do not extend this set by guess.
        diph = b and not a[2] and not b[2] and key not in _HIATUS and (
            pair in ("ae", "oe", "au") or (pair == "eu" and _eu(key)) or (pair == "ui" and ui))
        if diph:
            out.append(G(pair, "d", _DIPH[pair], "diph"))
            i = b[3]
            continue
        prev = out[-1] if out else None
        nxt_v = b is not None or _vowel_at(chars, a[3]) is not None
        sofar = "".join(g.base for g in out)
        if a[0] == "i" and nxt_v and (not out or prev.kind in ("v", "d") or sofar in _PRE):
            out.append(G("j", "c", "j"))
            i = a[3]
            continue
        glide_u = a[0] == "u" and nxt_v and (
            (prev and prev.base == "g" and len(out) >= 2 and out[-2].base == "n")
            or (prev and prev.base == "s" and key.startswith(("suav", "suad", "suesc")))
            or key.startswith(("dissuad", "assu", "consu")))
        if glide_u:
            out.append(G("w", "c", "w"))
            i = a[3]
            continue
        ln, explicit = a[1], a[2]
        if known_short and ln == "unknown":
            ln = "short"
        out.append(G(a[0], "v", "", ln, known_short or explicit, explicit))
        i = a[3]
    return out


def _build_longs():
    table = {}
    for raw in _PATTERNS.split():
        key = _key(raw)
        gs = _parse(_prep(raw), key, True)
        table[key] = set(n for n, g in enumerate(g for g in gs if g.kind != "c") if g.ln == "long")
    return table


_LONGS = _build_longs()


def _apply_longs(gs, key):
    want = _LONGS.get(key)
    if not want:
        return
    n = 0
    for g in gs:
        if g.kind == "c":
            continue
        if n in want and g.kind == "v" and not g.explicit:
            g.ln, g.known = "long", True
        n += 1


def _rules(gs, key):
    for i, g in enumerate(gs):
        if g.kind != "v" or g.known:
            continue
        n1 = gs[i + 1] if i + 1 < len(gs) else None
        n2 = gs[i + 2] if i + 2 < len(gs) else None
        if n1 and n1.base == "n" and n2 and n2.base in ("s", "f"):
            g.ln, g.known = "long", True
    for i, g in enumerate(gs):
        if g.kind != "v" or g.known:
            continue
        n1 = gs[i + 1] if i + 1 < len(gs) else None
        if n1 and n1.kind != "c":
            g.ln, g.known = "short", True
    if key.endswith("tas"):
        for g in reversed(gs):
            if g.kind == "v" and g.base == "a" and not g.known:
                g.ln, g.known = "long", True
                break
    if key.endswith("o") and key not in _SHORT_O:
        for g in reversed(gs):
            if g.kind == "v":
                if g.base == "o" and not g.known:
                    g.ln, g.known = "long", True
                break


def _front(g):
    if not g:
        return False
    if g.kind == "d":
        return g.base in ("ae", "oe")
    return g.kind == "v" and g.base in "eiy"


def _realize(gs, key, ecc):
    if not ecc:
        for i, g in enumerate(gs):
            n = gs[i + 1] if i + 1 < len(gs) else None
            if not n:
                continue
            if g.base == "g" and n.base == "n":
                g.ipa = "\u014b"
            if g.base == "n" and (n.ipa == "k" or n.base in ("g", "c", "q", "qu")):
                g.ipa = "\u014b"
            if g.base == "b" and n.base in ("s", "t"):
                g.ipa = "p"
        return
    if key in ("mihi", "nihil"):
        for g in gs:
            if g.base == "h":
                g.ipa = "k"
    else:
        for g in gs:
            if g.base == "h":
                g.ipa = ""
    for g in gs:
        if g.base == "v":
            g.ipa = "v"
        elif g.base == "ph":
            g.ipa = "f"
        elif g.base == "th":
            g.ipa = "t"
        elif g.base == "ch":
            g.ipa = "k"
        elif g.base == "z":
            g.ipa = "dz"
    for i, g in enumerate(gs):
        n = gs[i + 1] if i + 1 < len(gs) else None
        if g.base == "c" and _front(n):
            g.ipa = "t\u0283"
        if g.base == "g" and _front(n):
            g.ipa = "d\u0292"
    for i in range(len(gs) - 1):
        if gs[i].base == "g" and gs[i + 1].base == "n":
            gs[i].ipa, gs[i + 1].ipa = "", "\u0272"
    for i in range(len(gs) - 1):
        g, n = gs[i], gs[i + 1]
        if g.base == "s" and n.ipa == "t\u0283":
            g.ipa, n.ipa = "", "\u0283"
        elif g.base == "x" and n.base == "c" and n.ipa == "t\u0283":
            g.ipa, n.ipa = "k", "\u0283"
        elif g.base == "c" and n.ipa == "t\u0283":
            g.ipa = "t"
        elif g.base == "g" and n.ipa == "d\u0292":
            g.ipa = "d"
    for i, g in enumerate(gs):
        prev = gs[i - 1] if i else None
        nxt = gs[i + 1] if i + 1 < len(gs) else None
        if g.base == "x" and g.ipa == "ks" and prev and prev.kind != "c" and nxt and nxt.kind != "c":
            g.ipa = "gz"
    for i in range(len(gs) - 2):
        t, vow, nxt = gs[i], gs[i + 1], gs[i + 2]
        prev = gs[i - 1] if i else None
        if t.base == "t" and t.ipa == "t" and vow.kind == "v" and vow.base == "i" and vow.ln != "long" and nxt.kind != "c":
            if not (prev and prev.base in ("s", "x", "t")):
                t.ipa = "ts"
    for i in range(len(gs) - 1):
        g, n = gs[i], gs[i + 1]
        if g.base == "n" and g.ipa != "\u0272" and (n.ipa in ("k", "g") or n.base == "qu"):
            g.ipa = "\u014b"


def _onset(cluster):
    n = len(cluster)
    if not n:
        return 0
    start = 0
    for i, g in enumerate(cluster):
        if g.coda:
            start = i + 1
    avail = n - start
    if avail >= 2 and (
        (cluster[-2].base in _STOP and cluster[-1].base in _LIQ)
        or (cluster[-2].base in "gcq" and (cluster[-1].base == "w" or cluster[-1].ipa == "w"))):
        return 2
    return 1 if avail >= 1 else 0


def _syllables(gs):
    nuclei = [i for i, g in enumerate(gs) if g.kind != "c"]
    if not nuclei:
        return [gs] if gs else []
    out, cursor = [], 0
    for s, nuc in enumerate(nuclei):
        nxt = nuclei[s + 1] if s + 1 < len(nuclei) else None
        if nxt is None:
            end = len(gs)
        else:
            end = nxt - _onset(gs[nuc + 1:nxt])
        out.append(gs[cursor:end])
        cursor = end
    return out


def _heavy(syl):
    seen = False
    coda = False
    for g in syl:
        if g.kind != "c":
            if g.kind == "d" or g.ln == "long":
                return True
            seen, coda = True, False
        elif seen and not g.light:
            coda = True
    return coda


def _stress_at(parts, key, enc):
    if key in _PRO and not enc:
        return -1
    n = len(parts)
    if n <= 1:
        return 0 if n == 1 and key not in _PRO else -1
    if enc:
        return n - 2
    if n == 2:
        return 0
    return n - 2 if _heavy(parts[-2]) else n - 3


def _nucleus(g, nasal, ecc):
    if ecc:
        if g.kind == "d":
            ipa = "e" if g.base in ("ae", "oe") else ("au" if g.base == "au" else g.base)
        else:
            ipa = _EVOW.get(g.base, g.base)
    elif g.kind == "d":
        ipa = g.ipa
    elif g.ln == "long":
        ipa = _CLONG.get(g.base, g.base + "\u02d0")
    else:
        ipa = _CSHORT.get(g.base, g.base)
    return ipa + "\u0303" if nasal else ipa


def _paint(parts, stress, ecc):
    bits = []
    for i, syl in enumerate(parts):
        nasal = any(g.nasal for g in syl)
        nuc_at = next((k for k, g in enumerate(syl) if g.kind != "c"), -1) if nasal else -1
        s = "\u02c8" if i == stress else ""
        for k, g in enumerate(syl):
            if g.kind == "c":
                if g.ipa:
                    s += g.ipa
            else:
                s += _nucleus(g, k == nuc_at, ecc)
        bits.append(s)
    ipa = ""
    for s in bits:
        if not ipa:
            ipa = s
        elif s.startswith("\u02c8"):
            ipa += s
        else:
            ipa += "." + s
    return ipa


def _spell(parts, ecc):
    flat = [g for syl in parts for g in syl]
    out = []
    i = 0
    while i < len(flat):
        g = flat[i]
        if g.kind == "d":
            if ecc and g.base in ("ae", "oe"):
                out.append("e")
            elif g.base == "ae":
                out.append("eye")
            elif g.base == "oe":
                out.append("oy")
            elif g.base == "au":
                out.append("aw")
            else:
                out.append("e" if ecc else g.base)
        elif g.kind == "v":
            ch = "i" if ecc and g.base == "y" else g.base
            if not ecc and g.ln == "long":
                ch *= 2
            out.append(ch)
        else:
            ipa = g.ipa
            nxt = flat[i + 1] if i + 1 < len(flat) else None
            if ipa == "\u014b" and nxt and nxt.ipa == "n":
                out.append("ng")
                i += 2
                continue
            out.append({"": "", "w": "w", "v": "v", "k": "k", "kw": "kw", "ks": "ks", "gz": "gz",
                        "t\u0283": "ch", "d\u0292": "j", "\u0283": "sh", "ts": "ts", "\u0272": "ny",
                        "\u014b": "ng", "j": "y", "p": "p", "t": "t", "f": "f", "dz": "dz", "g": "g",
                        "n": "n", "m": "m", "l": "l", "r": "r", "s": "s", "b": "b", "d": "d", "h": "h",
                        # classical aspirates (build 0963): the synth has no aspirate, so it says the plain stop, as it did before the IPA gained the mark
                        "p\u02b0": "p", "t\u02b0": "t", "k\u02b0": "k"}.get(ipa, ipa))
        i += 1
    return "".join(out)


def _enclitic(key):
    if len(key) > 3 and key.endswith("que") and _key(key[:-3]):
        return "que"
    return None


def _word(raw, ecc):
    spelling = _prep(raw)
    key = _key(spelling)
    if key not in _LONGS and key.startswith("u") and len(key) > 1 and key[1] in _VOW and ("v" + key[1:]) in _LONGS:
        key = "v" + key[1:]
    enc = _enclitic(key)
    core = key[:-len(enc)] if enc else key
    gs = _parse(spelling, key, False)
    _apply_longs(gs, key)
    if enc:
        _apply_longs(gs, core)
    _rules(gs, core)
    _realize(gs, core, ecc)
    parts = _syllables(gs)
    stress = _stress_at(parts, key, bool(enc) and len(parts) >= 2)
    return parts, stress, gs


def _starts_vowel(gs):
    if not gs:
        return False
    return gs[0].kind != "c" or gs[0].base == "h"


def _sandhi(words, ecc):
    """words: list of (parts, stress, gs). Mutates ipa / marks elision. Returns list of (ipa, tie)."""
    out = []
    for i, (parts, stress, gs) in enumerate(words):
        tie = False
        if i + 1 < len(words):
            nxt = words[i + 1][2]
            if not ecc and _starts_vowel(nxt):
                last = parts[-1] if parts else []
                vowel_end = bool(last) and last[-1].kind != "c"
                coda_m = next((g for g in reversed(last) if g.kind == "c" and g.ipa), None)
                if (coda_m and coda_m.base == "m" and not vowel_end) or vowel_end:
                    tie = True
                    if coda_m and coda_m.base == "m" and not vowel_end:
                        coda_m.ipa = ""
                        for g in last:
                            g.nasal = True
                    for g in last:
                        if g.kind == "v" and g.ln == "long":
                            g.ln = "short"
            elif not _starts_vowel(nxt):
                last = next((g for g in reversed(gs) if g.kind == "c" and g.ipa), None)
                first = next((g for g in nxt if g.kind == "c" and g.base != "h"), None)
                if last and first:
                    lab = first.base in _LAB or first.base == "v" or first.ipa in ("w", "v")
                    if last.base == "m":
                        if lab:
                            last.ipa = "m"
                        elif first.ipa in _VEL or first.base in _VEL or first.base in ("c", "qu"):
                            last.ipa = "\u014b"
                        else:
                            last.ipa = "n"
                    elif last.base == "n" and lab:
                        last.ipa = "m"
        out.append((_paint(parts, stress, ecc), tie))
    return out


_WORD = re.compile(r"[A-Za-z\u0100-\u0177\u00c4\u00e4\u00cb\u00eb\u00cf\u00ef\u00d6\u00f6\u00dc\u00fc\u00ff\u00c6\u00e6\u0152\u0153]+")


def _runs(text, ecc):
    src = unicodedata.normalize("NFC", text)
    tokens = []
    last = 0
    for m in _WORD.finditer(src):
        gap = src[last:m.start()]
        if tokens and re.search(r"[.,;:!?]", gap):
            tokens.append(None)
        tokens.append(_word(m.group(), ecc))
        last = m.end()
    cur = []
    rendered = []
    for t in tokens:
        if t is None:
            rendered.extend(_sandhi(cur, ecc))
            cur = []
        else:
            cur.append(t)
    rendered.extend(_sandhi(cur, ecc))
    ipa, prev_tie = "", False
    for word_ipa, tie in rendered:
        if not ipa:
            ipa = word_ipa
        else:
            ipa += ("\u203f" if prev_tie else " ") + word_ipa
        prev_tie = tie
    return ipa


def ipa(text, ecclesiastical=False):
    """IPA for a word or a short line. ecclesiastical=False is classical."""
    return _runs(text or "", bool(ecclesiastical))


def pair(text):
    """(classical IPA, ecclesiastical IPA)."""
    return ipa(text, False), ipa(text, True)


def respell(lemma, ecclesiastical):
    """ASCII respelling for synth_wav. Second arg matches the old oracle_audio.respell."""
    ecc = bool(ecclesiastical)
    src = unicodedata.normalize("NFC", lemma or "")
    bits = []
    for m in _WORD.finditer(src):
        parts, _stress, _gs = _word(m.group(), ecc)
        # sandhi is for the IPA line; a single lexicon word has none
        bits.append(_spell(parts, ecc))
    return " ".join(b for b in bits if b)


_GLOSS_SRC = """
vita life; way of living
caelum sky; heaven
civis citizen
caesar Caesar; emperor
magnus great; large
veritas truth
lux light
pax peace
amor love
mors death
tempus time; season
excelsis in the highest (places)
gloria glory; renown
angelus messenger; angel
bellum war
deus god
terra earth; land
aqua water
ignis fire
rex king
nox night
sol sun
luna moon
cor heart
manus hand; band of men
virtus courage; excellence
fortuna fortune; chance
imperium command; empire
senatus the senate
gladius sword
aeternus eternal; everlasting
sanctus holy; sacred
spiritus breath; spirit
dominus lord; master
vox voice
fides faith; trust
memoria memory; recollection
gratia grace; favour; thanks
scientia knowledge
silva forest
mare sea
stella star
umbra shadow
ira anger
labor toil; hardship
somnus sleep
ferrum iron; a sword
aurum gold
populus a people; the public
cena dinner
oraculum oracle
marmor marble
argentum silver
pecunia money
lucrum profit
damnum loss
spes hope
timor fear
somnium dream
machina machine
imago image
verbum word
mens mind
anima soul
corpus body
via road
porta gate
finis end
initium beginning
silentium silence
gaudium joy
ridiculum the ridiculous
carpe seize
diem the day
dies day
arma arms; weapons
vir man
virum the man
cano I sing
troia Troy
troiae of Troy
qui who
primus first
ora shore
oris from the shores
gallia Gaul
est is
omnis the whole
divisa divided
partes parts
tres three
romanus Roman
amicus friend
puella girl
puer boy
homo a human being
urbs a city
hora hour
non not
liberat sets free
libertas freedom
ego I
tu you
ille that
hic this
multum much
ab from
ad to
ex out of
cum with
de down from; about
per through
pro for
si if
ut so that
aut or
nec nor
ne not
atque and
neque nor; and not
quoque also
itaque and so
denique finally
usque as far as
utique certainly
quisque each
uterque each of the two
undique from every side
sine without
et and
sed but
at but
iam already
enim for
autem but
tamen yet
ergo therefore
sum I am
sunt are
esse to be
in in; into
"""

_GLOSS = {}
for _line in _GLOSS_SRC.splitlines():
    _t = _line.strip()
    if not _t:
        continue
    _i = _t.find(" ")
    _GLOSS[_key(_t[:_i])] = _t[_i + 1:].strip()


def _gloss_key(key):
    hit = _GLOSS.get(key)
    if hit:
        return hit
    for enc, prefix in (("que", "and "), ("ve", "or ")):
        if len(key) > len(enc) + 1 and key.endswith(enc):
            stem = _GLOSS.get(key[:-len(enc)])
            if stem:
                return prefix + stem.split(";")[0].strip()
    if len(key) > 3 and key.endswith("ne"):
        stem = _GLOSS.get(key[:-2])
        if stem:
            return stem.split(";")[0].strip() + "?"
    return ""


def gloss(word):
    """English of one Latin word. Empty string if it is not in the list."""
    m = _WORD.search(word or "")
    return _gloss_key(_key(m.group())) if m else ""


def meanings(text):
    """Each word as (spelling, english, classical IPA, ecclesiastical IPA)."""
    out = []
    for m in _WORD.finditer(unicodedata.normalize("NFC", text or "")):
        w = m.group()
        out.append((w, gloss(w), ipa(w, False), ipa(w, True)))
    return out


if __name__ == "__main__":
    checks = [
        ("vita", False, "\u02c8wi\u02d0.ta"),
        ("caelum", False, "\u02c8ka\u026a.l\u028am"),
        ("Caesar", False, "\u02c8ka\u026a.sar"),
        ("magnus", False, "\u02c8ma\u014b.n\u028as"),
        ("Gallia est", False, "\u02c8gal.l\u026a.a\u203f\u02c8\u025bst"),
        ("in partes", False, "\u026am \u02c8par.te\u02d0s"),
        ("caelum", True, "\u02c8t\u0283e.lum"),
        ("scientia", True, "\u0283i\u02c8en.tsi.a"),
        ("excelsis", True, "ek\u02c8\u0283el.sis"),
        ("mihi", True, "\u02c8mi.ki"),
        ("poeta", False, "p\u0254\u02c8e\u02d0.ta"),
        ("antiquus", False, "an\u02c8ti\u02d0.kw\u028as"),
        ("pulcher", False, "\u02c8p\u028al.k\u02b0\u025br"),
    ]
    bad = []
    for text, ecc, want in checks:
        got = ipa(text, ecc)
        if want and got != want:
            bad.append("%s ecc=%s got %s want %s" % (text, ecc, got, want))
    c, e = pair("caelum")
    if respell("caelum", False) != "keyelum" or respell("caelum", True) != "chelum":
        bad.append("respell %s / %s" % (respell("caelum", False), respell("caelum", True)))
    if gloss("caelum") != "sky; heaven" or gloss("virumque") != "and the man" or gloss("liberat") != "sets free":
        bad.append("gloss %s | %s | %s" % (gloss("caelum"), gloss("virumque"), gloss("liberat")))
    if gloss("atque") != "and" or gloss("sine") != "without" or gloss("estne") != "is?":
        bad.append("gloss2 %s | %s | %s" % (gloss("atque"), gloss("sine"), gloss("estne")))
    line = meanings("Carpe diem.")
    if [g for _, g, _, _ in line] != ["seize", "the day"]:
        bad.append("meanings %s" % (line,))
    if bad:
        raise SystemExit("\n".join(bad))
    print("oracle_latin ok", c, e)
