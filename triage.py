#!/usr/bin/env python3
"""Coverage triage: score a list of candidate questions against the KB.

    python3 triage.py questions.txt      # one question per line
    python3 triage.py                     # reads .triage400.json (Noted export)

Buckets each question as covered (>=2.5) / partial (0.75-2.5) / gap (<0.75),
so a content pass can target the terms that still lack a dedicated entry.
"""
import json, re, sys
from qa import match

ROOT = __file__.rsplit("/", 1)[0]
db = json.load(open(f"{ROOT}/faq.json"))

if len(sys.argv) > 1:
    qs = [l.strip() for l in open(sys.argv[1]) if l.strip().endswith("?")]
    items = [{"theme": None, "q": q} for q in qs]
else:
    items = json.load(open(f"{ROOT}/.triage400.json"))

cov = par = gap = 0
for o in items:
    got, score = match(db, o["q"])
    o["hit"], o["score"] = (got["id"] if got else None), round(score, 2)
    if score >= 2.5: cov += 1
    elif score >= 0.75: par += 1
    else: gap += 1
print(f"{len(items)} questions: {cov} covered, {par} partial, {gap} gap")
for o in items:
    if o["score"] < 0.75:
        print(f"  GAP  ({o['score']:.2f}) {o['q'][:100]}")
