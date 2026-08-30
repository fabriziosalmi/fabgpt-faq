#!/usr/bin/env python3
"""Phase 2: derive a `suggest` field (related entry slugs) for every entry.

Source of truth = the internal links already hand-written in each answer
(q/<slug>/), which ARE the curated cross-references. Order preserved, deduped,
self excluded, capped. If an entry has fewer than MIN links, pad with
same-vertical neighbours (nearest by position). Smalltalk suggest is left as-is.
Also adds config.suggest (starter chips shown after the welcome message).
"""
import json
import re

FAQ = "/Users/fab/Documents/git/fabgpt-faq/faq.json"
CAP = 4      # store up to 4 (UI shows 3, keeps a spare for thread-history filtering)
MIN = 3      # pad to at least this many

db = json.load(open(FAQ))
entries = db["entries"]
slugs = {e["slug"] for e in entries}
by_vertical = {}
for i, e in enumerate(entries):
    by_vertical.setdefault(e["vertical"], []).append((i, e["slug"]))

LINK = re.compile(r"\]\(q/([a-z0-9-]+)/\)")

for idx, e in enumerate(entries):
    # links from the primary answer, in order
    found = []
    for m in LINK.finditer(e["answers"][0]):
        s = m.group(1)
        if s in slugs and s != e["slug"] and s not in found:
            found.append(s)
    # pad with same-vertical neighbours (closest by position) if too few
    if len(found) < MIN:
        sibs = sorted(by_vertical.get(e["vertical"], []), key=lambda t: abs(t[0] - idx))
        for _, s in sibs:
            if s != e["slug"] and s not in found:
                found.append(s)
            if len(found) >= MIN:
                break
    e["suggest"] = found[:CAP]

# --- orphan elimination: guarantee in-degree >= 1 so every entry is reachable
# by clicking a chip *somewhere*. Insert each orphan into a nearby same-vertical
# entry's suggest, in a shown position (top 3), capping at CAP.
by_idx = {e["slug"]: i for i, e in enumerate(entries)}
for _ in range(4):  # a few passes; converges fast
    indeg = {e["slug"]: 0 for e in entries}
    for e in entries:
        for s in e["suggest"]:
            indeg[s] = indeg.get(s, 0) + 1
    orphans = [e for e in entries if indeg[e["slug"]] == 0]
    if not orphans:
        break
    for o in orphans:
        # nearest same-vertical host that doesn't already suggest it and isn't itself
        cands = sorted(by_vertical.get(o["vertical"], []), key=lambda t: abs(t[0] - by_idx[o["slug"]]))
        for hi, hslug in cands:
            if hslug == o["slug"]:
                continue
            host = entries[hi]
            if o["slug"] in host["suggest"]:
                continue
            host["suggest"].insert(min(2, len(host["suggest"])), o["slug"])
            host["suggest"] = host["suggest"][:CAP]
            break

# starter chips after the welcome: a broad, inviting cross-vertical sample
HUBS = [
    "cos-e-un-waf-web-application-firewall",
    "cosa-prevede-ai-act",
    "autoscaling-vm-lxc-proxmox",
    "cos-e-ai-overview-e-come-finirci",
]
db["config"]["suggest"] = HUBS

# --- connectivity pass: no user should get trapped in a tiny cluster while
# clicking chips. For any entry whose chip-reachable set is small, append a
# cross-vertical hub (surfaces in the UI exactly when the local chips run out).
BRIDGE_CAP = 5       # allow a 5th slot for the escape-hatch bridge
TARGET_REACH = 30

def reach_size(start, adj):
    seen = {start}; frontier = [start]
    while frontier:
        nxt = []
        for s in frontier:
            for t in adj.get(s, []):
                if t not in seen:
                    seen.add(t); nxt.append(t)
        frontier = nxt
    return len(seen) - 1

for _ in range(4):
    adj = {e["slug"]: [s for s in e["suggest"] if s in slugs] for e in entries}
    small = [e for e in entries if reach_size(e["slug"], adj) < TARGET_REACH]
    if not small:
        break
    for e in small:
        bridge = next((h for h in HUBS if h != e["slug"] and h not in e["suggest"]), None)
        if bridge:
            e["suggest"] = (e["suggest"] + [bridge])[:BRIDGE_CAP]

# integrity: every suggest slug must resolve
for e in entries:
    for s in e["suggest"]:
        assert s in slugs, f"{e['id']}: dangling suggest slug {s}"
for s in db["config"]["suggest"]:
    assert s in slugs, f"config.suggest dangling {s}"

json.dump(db, open(FAQ, "w"), ensure_ascii=False, indent=2)
open(FAQ, "a").write("\n")
n_padded = sum(1 for e in entries if len(e["suggest"]) < MIN)
print(f"suggest added to {len(entries)} entries (avg {sum(len(e['suggest']) for e in entries)/len(entries):.1f} each, {n_padded} under {MIN})")
