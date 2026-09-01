#!/usr/bin/env python3
"""Draconian MULTI-TURN / trajectory gate for FabGPT-FAQ.

bench.py stresses single queries; this stresses the *conversation*: the chip
navigation graph and scripted multi-turn sessions. Mirrors app.js runtime state
(lastEntryId variant rotation, fallback rotation, askedSlugs chip history).

    python3 traj.py        # exit 0 only if every gate passes
    python3 traj.py -v     # also list per-case detail

Gates:
  T1 graph integrity   – every suggest slug resolves, no self-suggest, every
                         entry offers >= MIN_DEGREE suggestions.
  T2 no orphans        – every entry is suggested by at least one other (in-degree
                         >= 1): no entry is discoverable only by typing. 100%.
                         Also reports chip-reachability from the starter set.
  T3 no trap pockets   – the chip-reachable set (BFS over suggests) from EVERY
                         entry must include >= REACH_MIN others, so no user is
                         trapped clicking inside a tiny cluster.
  T4 scripted sessions – trajectories.json: multi-turn sessions with running
                         state. Supports expect=<id>|"fallback", and per-turn
                         flags: variant (answer must differ from the prior same
                         entry) and new_fallback (must differ from prior fallback).
                         100% required.
  T5 contextual sessions – trajectories.json sessions flagged "context": true:
                         elliptical follow-ups resolved via the previous entry's
                         tokens and "approfondisci" variant rotation. 100%.
"""
import json
import sys

from qa import match, pool, fastpath, load_ground

ROOT = __file__.rsplit("/", 1)[0]
VERBOSE = "-v" in sys.argv
MIN_DEGREE = 2     # every entry should offer at least this many chips
REACH_MIN = 30     # chip-reachable set from every entry must be at least this big


def gate(name, passed, total, required, unit="%"):
    pct = 100.0 * passed / total if total else 100.0
    ok = pct >= required
    print(f"{'PASS' if ok else 'FAIL'}  {name}: {passed}/{total} ({pct:.1f}{unit}, need {required:.0f}{unit})")
    return ok


# ---- app.js runtime mirror (variant + fallback rotation, chip history) ----

class Runtime:
    def __init__(self, db, commands=None, ports=None, ground=None):
        self.db = db
        self.commands = commands or []
        self.ports = ports or {}
        self.ground = ground or []
        self.cursor = {}
        self.last = None
        self.fb = -1
        self.asked = set()
        self.served = {}  # entry id -> times served (reprise when variants run out)
        self.ctx = None   # last KB/card entry served (smalltalk excluded), persists

    def ask(self, text):
        # deterministic fast-path first, exactly like app.js ask()
        fp = fastpath(text, self.ports)
        if fp:
            kind, signature = fp
            return {"id": "fp/" + kind, "question": text, "answers": [signature],
                    "suggest": [], "kind": "fastpath"}, signature
        entry, _ = match(self.db, text, self.ctx, self.commands, self.ground)
        # "approfondisci" on an active thread serves the next variant of the
        # last KB entry instead of the generic smalltalk reply (mirrors app.js).
        if (entry is not None and entry["id"] == "st-approfondisci"
                and self.ctx is not None and len(self.ctx["answers"]) > 1):
            entry = self.ctx
            n = len(entry["answers"])
            idx = (self.cursor.get(entry["id"], 0) + 1) % n
            self.cursor[entry["id"]] = idx
            self.served[entry["id"]] = self.served.get(entry["id"], 0) + 1
            self.last = entry["id"]
            self.asked.add(entry["slug"])
            ans = entry["answers"][idx]
            if self.served[entry["id"]] > n:
                ans = "*Te l'avevo già raccontata – eccola di nuovo:*\n\n" + ans
            return entry, ans
        if entry is None:
            self.fb = (self.fb + 1) % len(self.db["fallbacks"])
            self.last = None
            return None, self.db["fallbacks"][self.fb]
        n = len(entry["answers"])
        seen = entry["id"] in self.cursor           # already answered in this session
        idx = self.cursor.get(entry["id"], 0)
        if seen and n > 1:
            idx = (idx + 1) % n                     # re-asked (anywhere) -> next variant
        self.cursor[entry["id"]] = idx
        self.served[entry["id"]] = self.served.get(entry["id"], 0) + 1
        self.last = entry["id"]
        if entry.get("slug") or entry.get("kind") in ("command", "ground"):
            if entry.get("slug"):
                self.asked.add(entry["slug"])
            self.ctx = entry                        # cards and ground carry context too
        ans = entry["answers"][idx % n]
        # variants exhausted (or single answer): acknowledge instead of parroting
        if seen and self.served[entry["id"]] > n and (entry.get("slug") or entry.get("kind") in ("command", "ground")):
            ans = "*Te l'avevo già raccontata – eccola di nuovo:*\n\n" + ans
        return entry, ans


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
    entries = db["entries"]
    by_slug = {e["slug"]: e for e in entries}
    all_ok = True

    # ---- T1: graph integrity -------------------------------------------
    problems = []
    low_degree = 0
    for e in entries:
        sug = e.get("suggest", [])
        for s in sug:
            if s not in by_slug:
                problems.append(f"{e['id']}: dangling suggest '{s}'")
            if s == e["slug"]:
                problems.append(f"{e['id']}: self-suggest")
        if len(set(sug)) < MIN_DEGREE:
            low_degree += 1
            problems.append(f"{e['id']}: only {len(set(sug))} suggestions (< {MIN_DEGREE})")
    for p in problems[:20]:
        print(f"  T1: {p}")
    all_ok &= gate("T1 graph integrity", len(entries) - len({p.split(':')[0] for p in problems}),
                   len(entries), 100)

    # ---- T2: no orphans (in-degree >= 1) -------------------------------
    indeg = {e["slug"]: 0 for e in entries}
    for e in entries:
        for s in e.get("suggest", []):
            if s in indeg:
                indeg[s] += 1
    orphans = [e["slug"] for e in entries if indeg[e["slug"]] == 0]
    if orphans:
        print(f"  T2 orphans ({len(orphans)}): {', '.join(orphans[:30])}")
    # informational: chip-reachability from the starter set
    starters = [s for s in db.get("config", {}).get("suggest", []) if s in by_slug]
    seen = set(starters)
    frontier = list(starters)
    while frontier:
        nxt = []
        for slug in frontier:
            for s in by_slug[slug].get("suggest", []):
                if s in by_slug and s not in seen:
                    seen.add(s); nxt.append(s)
        frontier = nxt
    print(f"       (chip-reachable from {len(starters)} starters: "
          f"{len(seen)}/{len(entries)} = {100*len(seen)/len(entries):.0f}%)")
    all_ok &= gate("T2 no orphans", len(entries) - len(orphans), len(entries), 100)

    # ---- T3: no trap pockets (BFS reachable-set size per node) ---------
    def reach_size(start):
        seen = {start}; frontier = [start]
        while frontier:
            nxt = []
            for s in frontier:
                for t in by_slug[s].get("suggest", []):
                    if t in by_slug and t not in seen:
                        seen.add(t); nxt.append(t)
            frontier = nxt
        return len(seen) - 1
    reaches = sorted(((reach_size(e["slug"]), e["slug"]) for e in entries))
    bad = [r for r in reaches if r[0] < REACH_MIN]
    if bad and VERBOSE:
        for sz, slug in bad[:20]:
            print(f"  T3 trap pocket (reach {sz}): {slug}")
    all_ok &= gate("T3 no trap pockets", len(entries) - len(bad), len(entries), 100)

    # ---- T4/T5: scripted multi-turn sessions ---------------------------
    # T4 = classic full-question sessions; T5 = contextual sessions
    # ("context": true) with elliptical follow-ups and "approfondisci".
    sessions = json.load(open(f"{ROOT}/trajectories.json"))

    def run_sessions(label, batch):
        turns = fails = 0
        for sess in batch:
            rt = Runtime(db, commands, ports, ground)
            prev_ans = {}   # entry id -> last answer text seen (for variant checks)
            prev_fb = None
            for t in sess["turns"]:
                turns += 1
                entry, ans = rt.ask(t["q"])
                got = entry["id"] if entry else "fallback"
                exp = t["expect"]
                ok = (got == exp)
                if ok and t.get("variant"):
                    if entry and prev_ans.get(entry["id"]) == ans:
                        ok = False  # expected a rotated (different) variant
                if ok and t.get("new_fallback"):
                    if entry is None and prev_fb == ans:
                        ok = False  # expected a different fallback than last time
                if entry:
                    prev_ans[entry["id"]] = ans
                else:
                    prev_fb = ans
                if not ok:
                    fails += 1
                    print(f"  {label} [{sess['name']}] {t['q']!r}: want {exp}"
                          f"{' (variant)' if t.get('variant') else ''}"
                          f"{' (new_fallback)' if t.get('new_fallback') else ''}, got {got}")
        return turns, fails

    turns, fails = run_sessions("T4", [s for s in sessions if not s.get("context")])
    all_ok &= gate("T4 scripted sessions", turns - fails, turns, 100)
    turns5, fails5 = run_sessions("T5", [s for s in sessions if s.get("context")])
    all_ok &= gate("T5 contextual sessions", turns5 - fails5, turns5, 100)

    print("TRAJ:", "PASS" if all_ok else "FAIL")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
