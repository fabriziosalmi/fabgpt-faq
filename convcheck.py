#!/usr/bin/env python3
"""Gate T8: the marathon gate - long Italian conversations (convos.json).

bench stresses single turns, traj stresses short trajectories; this gate
stresses SUSTAINED conversation up to 23 turns, with invariants that hold
at the conversation level, not per turn:

  M1 struttura   - >= 8 sessions, each 12..23 turns (23 is a hard cap),
                   >= 140 turns total.
  M2 routing     - every turn lands where scripted: entry id, "fallback",
                   "fp/<kind>" (fast-path) or "cmd/<id>" (command card). 100%.
  M3 mai ripetersi - no bot answer text served twice in a session: variants,
                   reprise and fallback rotation must keep the bot fresh.
  M4 fallback vivo - every fallback must differ from the previous fallback
                   in the session (automatic, no flag needed).
  M5 sempre un appiglio - every KB/card turn (and smalltalk with suggest)
                   must offer at least one chip not yet visited.
  M6 copertura   - the suite must exercise the whole brain: fast-path
                   (>=4 turns, >=2 kinds), command cards (>=5), smalltalk
                   (>=5), hub (>=1), fallback (>=4), variant re-asks (>=4),
                   elliptical context turns flagged "ctx" (>=4).

Per-turn flags: "variant" (answer must differ from the previous answer of
the same entry), "ctx" (accounting for M6: elliptical turn resolved by
conversational context). Run: python3 convcheck.py [-v]
"""
import json
import sys

from traj import Runtime
from qa import load_ground

ROOT = __file__.rsplit("/", 1)[0]
VERBOSE = "-v" in sys.argv

CAP = 23
MIN_TURNS = 12
MIN_SESSIONS = 8
MIN_TOTAL = 140


def gate(name, passed, total):
    pct = 100.0 * passed / total if total else 100.0
    ok = passed == total
    print(f"{'PASS' if ok else 'FAIL'}  {name}: {passed}/{total} ({pct:.1f}%, need 100%)")
    return ok


def main():
    db = json.load(open(f"{ROOT}/faq.json"))
    commands = json.load(open(f"{ROOT}/commands.json"))["cards"]
    ports = json.load(open(f"{ROOT}/ports.json"))["ports"]
    ground = load_ground(ROOT)
    sessions = json.load(open(f"{ROOT}/convos.json"))
    by_slug = {e["slug"]: e for e in db["entries"]}
    all_ok = True

    # ---- M1 struttura --------------------------------------------------
    struct_bad = []
    if len(sessions) < MIN_SESSIONS:
        struct_bad.append(f"solo {len(sessions)} sessioni (< {MIN_SESSIONS})")
    total_turns = sum(len(s["turns"]) for s in sessions)
    if total_turns < MIN_TOTAL:
        struct_bad.append(f"solo {total_turns} turni totali (< {MIN_TOTAL})")
    for s in sessions:
        n = len(s["turns"])
        if n > CAP:
            struct_bad.append(f"{s['name']}: {n} turni (> cap {CAP})")
        if n < MIN_TURNS:
            struct_bad.append(f"{s['name']}: {n} turni (< {MIN_TURNS})")
    for b in struct_bad:
        print(f"  M1: {b}")
    all_ok &= gate("M1 struttura", 1 - min(1, len(struct_bad)), 1)

    # ---- M2..M5 per session --------------------------------------------
    m2_fail = m3_fail = m4_fail = m5_fail = 0
    m2_tot = total_turns
    m3_tot = m4_tot = m5_tot = 0
    counts = {"fp": 0, "fp_kinds": set(), "cmd": 0, "st": 0, "hub": 0,
              "fallback": 0, "variant": 0, "ctx": 0}

    for sess in sessions:
        rt = Runtime(db, commands, ports, ground)
        served = set()      # M3: exact bot texts already used in this session
        prev_fb = None
        prev_ans = {}
        for t in sess["turns"]:
            entry, ans = rt.ask(t["q"])
            got = entry["id"] if entry else "fallback"
            exp = t["expect"]

            # M2 routing
            if got != exp:
                m2_fail += 1
                if m2_fail <= 20:
                    print(f"  M2 [{sess['name']}] {t['q']!r}: want {exp}, got {got}")
            else:
                if got.startswith("fp/"):
                    counts["fp"] += 1
                    counts["fp_kinds"].add(got)
                elif got.startswith("cmd/"):
                    counts["cmd"] += 1
                elif got == "st-hub-sicurezza":
                    counts["hub"] += 1
                    counts["st"] += 1
                elif got.startswith("st-"):
                    counts["st"] += 1
                elif got == "fallback":
                    counts["fallback"] += 1
                if t.get("variant"):
                    counts["variant"] += 1
                if t.get("ctx"):
                    counts["ctx"] += 1

            # M3 mai ripetersi
            m3_tot += 1
            if ans in served:
                m3_fail += 1
                if m3_fail <= 10:
                    print(f"  M3 [{sess['name']}] risposta ripetuta al turno {t['q']!r}")
            served.add(ans)

            # variant flag: differ from previous answer of the same entry
            if t.get("variant") and entry is not None and prev_ans.get(entry["id"]) == ans:
                m2_fail += 1
                print(f"  M2 [{sess['name']}] {t['q']!r}: variante attesa, testo identico")
            if entry is not None:
                prev_ans[entry["id"]] = ans

            # M4 fallback vivo
            if entry is None:
                m4_tot += 1
                if prev_fb is not None and ans == prev_fb:
                    m4_fail += 1
                    print(f"  M4 [{sess['name']}] fallback ripetuto: {t['q']!r}")
                prev_fb = ans

            # M5 sempre un appiglio
            if entry is not None and not entry["id"].startswith("fp/"):
                sug = entry.get("suggest") or []
                if sug or entry.get("slug"):
                    m5_tot += 1
                    alive = [x for x in sug if x in by_slug and x not in rt.asked]
                    if not alive:
                        m5_fail += 1
                        if m5_fail <= 10:
                            print(f"  M5 [{sess['name']}] nessun chip nuovo dopo {t['q']!r} ({got})")

    all_ok &= gate("M2 routing", m2_tot - m2_fail, m2_tot)
    all_ok &= gate("M3 mai ripetersi", m3_tot - m3_fail, m3_tot)
    all_ok &= gate("M4 fallback vivo", m4_tot - m4_fail, m4_tot)
    all_ok &= gate("M5 sempre un appiglio", m5_tot - m5_fail, m5_tot)

    # ---- M6 copertura ---------------------------------------------------
    need = [
        ("fast-path >= 4", counts["fp"] >= 4),
        ("fast-path kinds >= 2", len(counts["fp_kinds"]) >= 2),
        ("command card >= 5", counts["cmd"] >= 5),
        ("smalltalk >= 5", counts["st"] >= 5),
        ("hub >= 1", counts["hub"] >= 1),
        ("fallback >= 4", counts["fallback"] >= 4),
        ("varianti >= 4", counts["variant"] >= 4),
        ("turni contestuali >= 4", counts["ctx"] >= 4),
    ]
    miss = [n for n, ok in need if not ok]
    for n in miss:
        print(f"  M6 copertura mancante: {n}")
    if VERBOSE:
        print(f"       (fp={counts['fp']} kinds={sorted(counts['fp_kinds'])} cmd={counts['cmd']} "
              f"st={counts['st']} hub={counts['hub']} fb={counts['fallback']} "
              f"var={counts['variant']} ctx={counts['ctx']}; {len(sessions)} sessioni, {total_turns} turni)")
    all_ok &= gate("M6 copertura", len(need) - len(miss), len(need))

    print("CONVCHECK:", "PASS" if all_ok else "FAIL")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
