#!/usr/bin/env python3
"""Gate T7: the command-card pool (commands.json).

  C1 integrity  – unique ids, valid group, valid related slugs, no em-dash,
                  no duplicate normalized keyword inside the pool.
  C2 no-steal   – every KB canonical question, matched WITH the command pool,
                  must still return its own entry (ties favor the KB by
                  construction; this catches accidental overshoot).
  C3 routing    – tests_commands.json: one colloquial query per card must
                  route to that card (id prefixed cmd/). 100% required.

Run: python3 cmdcheck.py
"""
import json
import sys

from qa import match, norm, load_ground

ROOT = __file__.rsplit("/", 1)[0]
GROUND = load_ground(ROOT)


def gate(name, passed, total):
    pct = 100.0 * passed / total if total else 100.0
    ok = passed == total
    print(f"{'PASS' if ok else 'FAIL'}  {name}: {passed}/{total} ({pct:.1f}%, need 100%)")
    return ok


def main():
    db = json.load(open(f"{ROOT}/faq.json"))
    data = json.load(open(f"{ROOT}/commands.json"))
    cards = data["cards"]
    groups = {g["slug"] for g in data["groups"]}
    slugs = {e["slug"] for e in db["entries"]}
    all_ok = True

    # ---- C1 integrity ----
    problems = []
    seen_ids, seen_kw = set(), {}
    for c in cards:
        if c["id"] in seen_ids:
            problems.append(f"dup id {c['id']}")
        seen_ids.add(c["id"])
        if c["group"] not in groups:
            problems.append(f"{c['id']}: unknown group {c['group']}")
        for s in c.get("related", []):
            if s not in slugs:
                problems.append(f"{c['id']}: unknown related slug {s}")
        for k in c["keywords"]:
            nk = norm(k)
            if nk in seen_kw:
                problems.append(f"{c['id']}: keyword '{k}' already on {seen_kw[nk]}")
            seen_kw[nk] = c["id"]
        for field in ("q", "cmd", "note"):
            if "—" in c[field]:
                problems.append(f"{c['id']}: em-dash in {field}")
    for p in problems[:15]:
        print(f"  C1: {p}")
    bad_cards = {p.split(":")[0].replace("dup id ", "") for p in problems}
    all_ok &= gate("C1 integrity", len(cards) - len(bad_cards), len(cards))

    # ---- C2 no-steal ----
    steals = 0
    for e in db["entries"]:
        got, _ = match(db, e["question"], None, cards, GROUND)
        if got is None or got["id"] != e["id"]:
            steals += 1
            if steals <= 10:
                print(f"  C2: {e['id']} lost its canonical to {got['id'] if got else 'fallback'}")
    all_ok &= gate("C2 no-steal", len(db["entries"]) - steals, len(db["entries"]))

    # ---- C3 routing ----
    tests = json.load(open(f"{ROOT}/tests_commands.json"))
    fails = 0
    tested = {t["expect"] for t in tests}
    missing = [c["id"] for c in cards if "cmd/" + c["id"] not in tested]
    if missing:
        print(f"  C3: {len(missing)} cards without a test: {', '.join(missing[:8])}…")
    for t in tests:
        got, score = match(db, t["q"], None, cards, GROUND)
        got_id = got["id"] if got else "fallback"
        if got_id != t["expect"]:
            fails += 1
            if fails <= 15:
                print(f"  C3: {t['q']!r}: want {t['expect']}, got {got_id} ({score:.2f})")
    all_ok &= gate("C3 routing", len(tests) - fails, len(tests) + len(missing))

    # ---- C4 battery fidelity: the full qa battery must be unchanged with the
    # pool active. One sanctioned exception: a card may take over a battery
    # query IF the expected KB entry is among the card's `related` slugs -
    # i.e. the card is a command-level refinement of that same topic, and the
    # user still reaches the entry via the card's link and chips. ----
    qtests = json.load(open(f"{ROOT}/tests.json"))
    entry_slug = {e["id"]: e["slug"] for e in db["entries"]}
    by_card_id = {"cmd/" + c["id"]: c for c in cards}
    bfails = refined = 0
    for t in qtests:
        got, score = match(db, t["q"], None, cards, GROUND)
        got_id = got["id"] if got else None
        if got_id == t["expect"]:
            continue
        card = by_card_id.get(got_id)
        if card and entry_slug.get(t["expect"]) in card.get("related", []):
            refined += 1
            continue
        bfails += 1
        if bfails <= 10:
            print(f"  C4: {t['q']!r}: want {t['expect']}, got {got_id} ({score:.2f})")
    if refined:
        print(f"       ({refined} batteria raffinate da card con la voce attesa nei related)")
    all_ok &= gate("C4 battery fidelity", len(qtests) - bfails, len(qtests))

    print("CMDCHECK:", "PASS" if all_ok else "FAIL")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
