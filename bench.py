#!/usr/bin/env python3
"""Draconian benchmark for the FabGPT-FAQ matcher and knowledge base.

Run:  python3 bench.py          (exit 0 only if every gate passes)
      python3 bench.py -v       (also list per-case results)

Gates (all hard, in order):
  G1 integrity    – no duplicate normalized keywords inside an entry, no em-dash
                    anywhere, every internal "q/<slug>/" link resolves.
  G2 canonical    – every entry's own question retrieves that entry: 100%.
  G3 typo         – each canonical question with two deterministic typos still
                    retrieves its entry: >= 90%.
  G4 battery      – tests.json: 100%.
  G5 negatives    – junk/off-domain queries must NOT hit the knowledge base
                    (fallback or smalltalk are both acceptable): 100%.

Also reports (non-blocking): fragile entries, i.e. canonical-question margin
(top1 minus top2 score) below 0.5 – prime targets for keyword hardening.

ACCEPT maps adjudicated equivalences: canonical questions whose best match is a
sibling entry that answers them just as well. Keep it short and deliberate.
"""
import hashlib
import json
import sys

from qa import match, norm, pool, score_entry, tokens

ROOT = __file__.rsplit("/", 1)[0]
VERBOSE = "-v" in sys.argv

# canonical question -> additionally accepted entry ids (adjudicated)
ACCEPT = {
    "proxmox-vm-autoscale": {"proxmox-autoscale"},
    "proxmox-lxc-autoscale": {"proxmox-autoscale"},
}

NEGATIVES = [
    "qwerty uiop zxcvb",
    "il gatto miagola sul divano",
    "vendimi una macchina usata",
    "quanto costa un chilo di pane a milano",
    "mia suocera arriva domenica",
    "dove parcheggio in centro a genova",
    "il senso della vita in una frase",
    "numeri del lotto di stasera",
    "oroscopo del giorno bilancia",
    "come si pota un ulivo",
]


def top2(db, text):
    input_norm = norm(text)
    input_tokens = tokens(text)
    scored = sorted(
        ((score_entry(e, input_norm, input_tokens), e["id"]) for e in pool(db)),
        key=lambda x: -x[0],
    )
    return scored[0], (scored[1] if len(scored) > 1 else (0.0, None))


def typo_variant(text, seed):
    """Two deterministic typos: swap adjacent chars in one long word, drop a char in another."""
    words = text.split(" ")
    long_idx = [i for i, w in enumerate(words) if len(w) >= 5 and w.isalpha()]
    if len(long_idx) < 2:
        return None
    h = hashlib.md5(seed.encode()).digest()
    i1 = long_idx[h[0] % len(long_idx)]
    i2 = long_idx[h[1] % len(long_idx)]
    if i2 == i1:
        i2 = long_idx[(h[1] + 1) % len(long_idx)]
    w1 = list(words[i1])
    p = 1 + h[2] % (len(w1) - 2)
    w1[p], w1[p + 1] = w1[p + 1], w1[p]
    words[i1] = "".join(w1)
    if i2 != i1:
        w2 = words[i2]
        p2 = 1 + h[3] % (len(w2) - 2)
        words[i2] = w2[:p2] + w2[p2 + 1:]
    return " ".join(words)


def gate(name, passed, total, required):
    pct = 100.0 * passed / total if total else 100.0
    ok = pct >= required
    print(f"{'PASS' if ok else 'FAIL'}  {name}: {passed}/{total} ({pct:.1f}%, required {required:.0f}%)")
    return ok


def main():
    db = json.load(open(f"{ROOT}/faq.json"))
    entries = db["entries"]
    all_ok = True

    # ---- G1: integrity -------------------------------------------------
    problems = []
    slugs = {e["slug"] for e in entries}
    raw = json.dumps(db, ensure_ascii=False)
    if "—" in raw:
        problems.append("em-dash found in faq.json")
    from qa import STOPWORDS
    for e in pool(db):
        seen = set()
        seen_sets = set()
        for k in e["keywords"]:
            nk = norm(k)
            if nk in seen:
                problems.append(f"{e['id']}: duplicate normalized keyword '{nk}'")
            seen.add(nk)
            ws = frozenset(w for w in nk.split() if len(w) > 1 and w not in STOPWORDS)
            if len(ws) >= 2:
                if ws in seen_sets:
                    problems.append(f"{e['id']}: phrase '{nk}' duplicates another keyword's word-set")
                seen_sets.add(ws)
        for a in e["answers"]:
            for part in a.split("](q/")[1:]:
                slug = part.split(")")[0].rstrip("/").split("/")[0]
                if slug and slug not in slugs:
                    problems.append(f"{e['id']}: broken internal link q/{slug}/")
    for p in problems:
        print(f"  G1: {p}")
    ok = gate("G1 integrity", len(problems) == 0 and 1 or 0, 1, 100)
    all_ok &= ok

    # ---- G2: canonical questions --------------------------------------
    fails, fragile = [], []
    for e in entries:
        got, _ = match(db, e["question"])
        got_id = got["id"] if got else None
        accepted = {e["id"]} | ACCEPT.get(e["id"], set())
        if got_id not in accepted:
            fails.append((e["id"], e["question"], got_id))
        (s1, id1), (s2, _) = top2(db, e["question"])
        if id1 == e["id"] and s1 - s2 < 0.5:
            fragile.append((round(s1 - s2, 2), e["id"]))
    for eid, q, got in fails:
        print(f"  G2: {eid} lost its own question to {got}: {q!r}")
    all_ok &= gate("G2 canonical", len(entries) - len(fails), len(entries), 100)

    # ---- G3: typo robustness ------------------------------------------
    t_total, t_pass = 0, 0
    t_fails = []
    for e in entries:
        v = typo_variant(e["question"], e["id"])
        if not v:
            continue
        t_total += 1
        got, _ = match(db, v)
        got_id = got["id"] if got else None
        if got_id in {e["id"]} | ACCEPT.get(e["id"], set()):
            t_pass += 1
        else:
            t_fails.append((e["id"], v, got_id))
    if VERBOSE:
        for eid, v, got in t_fails:
            print(f"  G3: {eid} failed on {v!r} -> {got}")
    all_ok &= gate("G3 typo", t_pass, t_total, 90)

    # ---- G4: curated battery ------------------------------------------
    tests = json.load(open(f"{ROOT}/tests.json"))
    b_fails = []
    for t in tests:
        got, _ = match(db, t["q"])
        got_id = got["id"] if got else None
        if got_id != t["expect"]:
            b_fails.append((t["q"], t["expect"], got_id))
    for q, want, got in b_fails:
        print(f"  G4: {q!r}: want {want}, got {got}")
    all_ok &= gate("G4 battery", len(tests) - len(b_fails), len(tests), 100)

    # ---- G5: negatives -------------------------------------------------
    kb_ids = {e["id"] for e in entries}
    n_fails = []
    for q in NEGATIVES:
        got, score = match(db, q)
        if got and got["id"] in kb_ids:
            n_fails.append((q, got["id"], score))
    for q, got, score in n_fails:
        print(f"  G5: {q!r} wrongly hit KB entry {got} ({score:.2f})")
    all_ok &= gate("G5 negatives", len(NEGATIVES) - len(n_fails), len(NEGATIVES), 100)

    # ---- fragility report (non-blocking) -------------------------------
    if fragile:
        fragile.sort()
        show = fragile if VERBOSE else fragile[:10]
        print(f"fragile canonical margins (<0.5, {len(fragile)} total, hardening candidates):")
        for margin, eid in show:
            print(f"  {margin:.2f}  {eid}")

    print("BENCH:", "PASS" if all_ok else "FAIL")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
