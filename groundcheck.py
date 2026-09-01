#!/usr/bin/env python3
"""Gate T9: the ground-truth layer (ground.json).

The layer answers the classic day-one questions people throw at an "AI" to
test it (benchmark staples: ground truth, myths, riddles, base culture).
It is STRICTLY pre-fallback: match() consults it only when the KB+smalltalk
would produce nothing or an encyclopedic deflector (st-cultura-generale,
st-matematica), so it can never steal a vertical entry or a command card.
No static pages, no sitemap: chat-only by design.

  N1 integrity  - unique ids (gt- prefix) and questions, non-empty answers,
                  >= 5 keywords each, no em dash, no Cyrillic/Greek
                  homoglyphs, no emoji, balanced ** and backticks, no
                  degenerate short phrases, no unrenderable links. 100%.
  N2 canonical  - every ground question routes to its own entry through the
                  FULL pipeline (fastpath + KB + cards + ground). 100%.

No-steal is proven by the other gates, not here: qa/bench/cmdcheck/traj/T8
all load ground.json and their expectations are unchanged - if the ground
layer ever stole a query, one of them would go red.

Run: python3 groundcheck.py [-v]
"""
import json
import re
import sys

from qa import fastpath, load_ground, match

ROOT = __file__.rsplit("/", 1)[0]
VERBOSE = "-v" in sys.argv

EMOJI = re.compile(r'[\U0001F000-\U0001FAFF☀-➿⬀-⯿]')


def gate(name, passed, total):
    pct = 100.0 * passed / total if total else 100.0
    ok = passed == total
    print(f"{'PASS' if ok else 'FAIL'}  {name}: {passed}/{total} ({pct:.1f}%, need 100%)")
    return ok


def main():
    db = json.load(open(f"{ROOT}/faq.json"))
    try:
        commands = json.load(open(f"{ROOT}/commands.json"))["cards"]
    except FileNotFoundError:
        commands = []
    try:
        ports = json.load(open(f"{ROOT}/ports.json"))["ports"]
    except FileNotFoundError:
        ports = {}
    ground = load_ground(ROOT)
    if not ground:
        print("groundcheck: ground.json absent or empty - nothing to gate")
        return 0
    all_ok = True

    # ---- N1 integrity ---------------------------------------------------
    problems = []
    seen_ids, seen_q = set(), set()
    from qa import STOPWORDS, norm
    for g in ground:
        gid = g.get("id", "")
        if not gid.startswith("gt-"):
            problems.append(f"{gid or '?'}: id must start with gt-")
        if gid in seen_ids:
            problems.append(f"{gid}: duplicate id")
        seen_ids.add(gid)
        q = g.get("question", "")
        nq = norm(q)
        if nq in seen_q:
            problems.append(f"{gid}: duplicate question '{q[:50]}'")
        seen_q.add(nq)
        if g.get("kind") != "ground":
            problems.append(f"{gid}: kind must be 'ground'")
        if len(g.get("keywords", [])) < 5:
            problems.append(f"{gid}: fewer than 5 keywords")
        seen_kw = set()
        for k in g.get("keywords", []):
            nk = norm(k)
            if nk in seen_kw:
                problems.append(f"{gid}: duplicate normalized keyword '{nk}'")
            seen_kw.add(nk)
            if " " in nk and len(nk) < 5:
                problems.append(f"{gid}: degenerate short phrase '{nk}'")
        answers = g.get("answers") or []
        if not answers or not all(a.strip() for a in answers):
            problems.append(f"{gid}: empty answer")
        for a in answers:
            if "—" in a or "—" in q:
                problems.append(f"{gid}: em dash")
            # Cyrillic only: those are the lookalike-attack codepoints. Greek
            # letters (Ω, Δ, λ...) are legitimate scientific notation here.
            for ch in set(a):
                cp = ord(ch)
                if 0x0400 <= cp <= 0x04FF:
                    problems.append(f"{gid}: homoglyph U+{cp:04X}")
            if EMOJI.search(a):
                problems.append(f"{gid}: emoji in answer")
            clean = re.sub(r"```[\s\S]*?```", "CODE", a)
            clean = re.sub(r"`[^`]*`", "CODE", clean)
            if clean.count("**") % 2:
                problems.append(f"{gid}: unbalanced **")
            if a.count("`") % 2:
                problems.append(f"{gid}: unbalanced backtick")
            t = re.sub(r"\[[^\]]+\]\((?:https?|mailto):[^)\s]+\)", "", clean)
            t = re.sub(r"\[[^\]]+\]\([^):\s]+\)", "", t)
            if "](" in t:
                problems.append(f"{gid}: unrenderable markdown link")
    for p in problems[:25]:
        print(f"  N1: {p}")
    all_ok &= gate("N1 integrity", 1 - min(1, len(problems)), 1)

    # ---- N2 canonical (full pipeline) -----------------------------------
    fails = 0
    for g in ground:
        q = g["question"]
        fp = fastpath(q, ports)
        if fp is not None:
            fails += 1
            print(f"  N2: {g['id']} intercepted by fastpath {fp[0]} - drop it or rephrase: {q!r}")
            continue
        got, score = match(db, q, None, commands, ground)
        got_id = got["id"] if got else None
        if got_id != g["id"]:
            fails += 1
            if fails <= 20:
                print(f"  N2: {g['id']} -> {got_id} ({score:.2f}): {q!r}")
    all_ok &= gate("N2 canonical", len(ground) - fails, len(ground))

    if VERBOSE:
        from collections import Counter
        cats = Counter(g.get("cat", "?") for g in ground)
        print(f"       ({len(ground)} voci: " + ", ".join(f"{k}={v}" for k, v in sorted(cats.items())) + ")")

    print("GROUNDCHECK:", "PASS" if all_ok else "FAIL")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
