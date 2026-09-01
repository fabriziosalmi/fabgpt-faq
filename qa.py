#!/usr/bin/env python3
"""QA harness for the FabGPT-FAQ matcher.

Mirrors the scoring logic of app.js exactly, so hundreds of entries can be
validated without a browser:

    python3 qa.py            # run tests.json, report failures + keyword collisions
    python3 qa.py "query"    # explain: score breakdown for one query

Keep tests.json growing: at least one query per entry.
"""
import json
import sys
import unicodedata
import re
from collections import defaultdict

ROOT = __file__.rsplit("/", 1)[0]

STOPWORDS = set(("il lo la i gli le un uno una di a da in con su per tra fra e o ma se che chi cosa come dove quando quanto "
    "perche non mi ti si ci vi ne del della dei delle dello degli al allo alla ai agli alle sul sullo sulla sui sugli sulle nel nella nei "
    "sono sei e siamo siete ho hai ha abbiamo avete hanno posso puoi puo vorrei voglio sapere dimmi parlami spiegami raccontami esiste esistono "
    "c è ce cos cose cioe questo questa questi queste quello quella mio mia tuo tua suo sua piu meno molto poco anche ancora gia solo cose roba "
    "the a an of to is are was were be been what who how why when where and or me my your tell about does do can could would please").split())


def norm(s):
    s = s.lower()
    s = "".join(c for c in unicodedata.normalize("NFD", s) if not ("̀" <= c <= "ͯ"))
    s = re.sub(r"[^a-z0-9\s-]", " ", s)
    s = re.sub(r"[-\s]+", " ", s)
    return s.strip()


def tokens(s):
    return [t for t in norm(s).split(" ") if len(t) > 1 and t not in STOPWORDS]


def bigrams(w):
    return [w[i:i + 2] for i in range(len(w) - 1)]


def dice(a, b):
    if a == b:
        return 1.0
    if len(a) < 2 or len(b) < 2:
        return 0.0
    B = defaultdict(int)
    for g in bigrams(b):
        B[g] += 1
    hits = 0
    for g in bigrams(a):
        if B[g] > 0:
            hits += 1
            B[g] -= 1
    return 2 * hits / (len(a) - 1 + len(b) - 1)


def damerau1(a, b):
    """True if a and b are within one edit (incl. adjacent transposition)."""
    if a == b:
        return True
    la, lb = len(a), len(b)
    if abs(la - lb) > 1:
        return False
    if la == lb:
        diffs = [k for k in range(la) if a[k] != b[k]]
        if len(diffs) == 1:
            return True
        return (len(diffs) == 2 and diffs[1] == diffs[0] + 1
                and a[diffs[0]] == b[diffs[1]] and a[diffs[1]] == b[diffs[0]])
    if la > lb:
        a, b, la, lb = b, a, lb, la
    i = 0
    while i < la and a[i] == b[i]:
        i += 1
    return a[i:] == b[i + 1:]


def word_best(w, input_tokens):
    """Best fuzzy match of one keyword word against the input tokens."""
    best = 0.0
    for t in input_tokens:
        if t == w:
            return 1.0
        if len(t) > 3 and len(w) > 3 and abs(len(t) - len(w)) <= 3:
            sim = dice(t, w)
            if sim >= 0.7:
                best = max(best, sim * 0.95)
        # short-word typos that bigram similarity misses (toen -> token);
        # first char must match: bash!=hash are different words, not typos
        if best < 0.8 and len(t) >= 4 and len(w) >= 4 and abs(len(t) - len(w)) <= 1 and t[0] == w[0] and damerau1(t, w):
            best = 0.8
    return best


def score_entry(entry, input_norm, input_tokens, explain=None):
    score = 0.0
    for raw in entry["keywords"]:
        kw = norm(raw)
        if not kw:
            continue
        if " " in kw:
            # Multi-word keyword: exact substring wins; otherwise every unique
            # content word must be present (any order, typo-tolerant).
            if kw in input_norm:
                score += 2
                if explain is not None:
                    explain.append(f"  +2.00 phrase '{kw}'")
                continue
            words = list(dict.fromkeys(w for w in kw.split(" ") if len(w) > 1 and w not in STOPWORDS))
            if len(words) < 2:
                continue
            total, all_found = 0.0, True
            for w in words:
                b = word_best(w, input_tokens)
                if not b:
                    all_found = False
                    break
                total += b
            if all_found:
                gain = 2 * (total / len(words))
                score += gain
                if explain is not None:
                    explain.append(f"  +{gain:.2f} fuzzy-phrase '{kw}'")
            continue
        best = word_best(kw, input_tokens)
        if best:
            score += best
            if explain is not None:
                explain.append(f"  +{best:.2f} '{kw}'")
    return score


def pool(db):
    # Smalltalk goes last so knowledge-base entries win ties (mirrors app.js).
    return db["entries"] + db.get("smalltalk", [])


CTX_CONFIDENT = 2.0   # pass-1 score at/above which context is never consulted
CTX_MIN = 2.0         # a contextual candidate must reach this combined score
CTX_CAP = 24          # max context tokens carried from the previous entry
CTX_MAX_TOKENS = 2    # context applies only to elliptical inputs (<= this many content words)


def ctx_tokens(entry, cap=CTX_CAP):
    """Content words of the previous entry (question + keywords), deduped."""
    seen = []
    for src in [entry["question"]] + entry["keywords"]:
        for t in tokens(src):
            if t not in seen:
                seen.append(t)
    return seen[:cap]


CMD_MIN = 2.0         # a command card must reach this score AND strictly beat the KB


def command_md(card):
    """Render a command card as chat markdown (app.js mirrors this shape)."""
    md = "**" + card["q"] + "**\n\n```bash\n" + card["cmd"] + "\n```\n" + card["note"]
    md += f"\n\n[Scheda completa dei comandi →](comandi/{card['group']}/#{card['id']})"
    return md


def command_entry(card):
    """Wrap a card as a pseudo-entry so the runtime treats it like an answer."""
    return {
        "id": "cmd/" + card["id"],
        "question": card["q"],
        "answers": [command_md(card)],
        "suggest": card.get("related", []),
        "kind": "command",
    }


def match(db, text, ctx=None, commands=None):
    """ctx = the previously matched KB entry (or None). Mirrors app.js:
    a weak direct match is retried with the previous entry's tokens added,
    but a contextual candidate counts only if the NEW input contributed
    (combined score > score from context tokens alone). commands = the
    command-card pool (commands.json): consulted after the KB, and a card
    wins only if it reaches CMD_MIN and STRICTLY beats the KB score, so
    every KB canonical keeps routing to its entry (ties favor the KB)."""
    input_norm = norm(text)
    input_tokens = tokens(text)
    best, best_score = None, 0.0
    for entry in pool(db):
        s = score_entry(entry, input_norm, input_tokens)
        if s > best_score:
            best_score, best = s, entry
    if ctx is not None and best_score < CTX_CONFIDENT and len(input_tokens) <= CTX_MAX_TOKENS:
        extra = [t for t in ctx_tokens(ctx) if t not in input_tokens]
        if extra:
            combined = input_tokens + extra
            b2, s2 = None, 0.0
            for entry in db["entries"]:
                if entry["id"] == ctx["id"]:
                    continue
                comb = score_entry(entry, input_norm, combined)
                if comb <= s2 or comb < CTX_MIN:
                    continue
                if comb > score_entry(entry, "", extra):  # new input contributed
                    b2, s2 = entry, comb
            if b2 is not None and s2 > best_score:
                return b2, s2
    if commands:
        bc, sc = None, 0.0
        for card in commands:
            s = score_entry(card, input_norm, input_tokens)
            if s > sc:
                sc, bc = s, card
        if bc is not None and sc >= CMD_MIN and sc > best_score:
            return command_entry(bc), sc
    if best and best_score >= db["config"]["matchThreshold"]:
        return best, best_score
    return None, best_score


def explain_query(db, text):
    input_norm = norm(text)
    input_tokens = tokens(text)
    scored = []
    for entry in pool(db):
        detail = []
        s = score_entry(entry, input_norm, input_tokens, detail)
        if s > 0:
            scored.append((s, entry["id"], detail))
    scored.sort(key=lambda x: -x[0])
    print(f"query: {text!r}  ->  tokens {input_tokens}")
    for s, eid, detail in scored[:8]:
        print(f"{s:5.2f}  {eid}")
        for line in detail:
            print(line)


def run_tests(db):
    tests = json.load(open(f"{ROOT}/tests.json"))
    ids = {e["id"] for e in pool(db)}
    bad_refs = [t for t in tests if t["expect"] is not None and t["expect"] not in ids]
    failures = []
    for t in tests:
        got, score = match(db, t["q"])
        got_id = got["id"] if got else None
        if got_id != t["expect"]:
            failures.append((t["q"], t["expect"], got_id, score))
    print(f"tests: {len(tests) - len(failures)}/{len(tests)} passed")
    for q, want, got_id, score in failures:
        print(f"  FAIL {q!r}: want {want}, got {got_id} ({score:.2f})")
    for t in bad_refs:
        print(f"  BAD REF: test {t['q']!r} expects unknown id {t['expect']!r}")

    # entries with no test coverage
    covered = {t["expect"] for t in tests}
    uncovered = [e["id"] for e in pool(db) if e["id"] not in covered]
    if uncovered:
        print(f"untested entries ({len(uncovered)}): {', '.join(uncovered)}")

    # keyword collisions: same normalized keyword owned by several entries
    owners = defaultdict(list)
    for e in pool(db):
        for k in e["keywords"]:
            owners[norm(k)].append(e["id"])
    shared = {k: v for k, v in owners.items() if len(v) > 1}
    if shared:
        print(f"shared keywords ({len(shared)}) – earliest entry wins bare-keyword ties:")
        for k, v in sorted(shared.items()):
            print(f"  '{k}': {', '.join(v)}")
    return 1 if failures or bad_refs else 0


if __name__ == "__main__":
    db = json.load(open(f"{ROOT}/faq.json"))
    if len(sys.argv) > 1:
        explain_query(db, " ".join(sys.argv[1:]))
    else:
        sys.exit(run_tests(db))
