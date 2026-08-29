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

# starter chips after the welcome: a broad, inviting cross-vertical sample
db["config"]["suggest"] = [
    "cos-e-un-waf-web-application-firewall",
    "cosa-prevede-ai-act",
    "autoscaling-vm-lxc-proxmox",
    "cos-e-ai-overview-e-come-finirci",
]

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
