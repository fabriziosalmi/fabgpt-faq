#!/usr/bin/env python3
"""Dialogue acts (dialog.json) - Python mirror of the act layer in app.js.

An act is a short follow-up that works on the CURRENT thread instead of
starting a new one: "riassumi", "fammi un esempio", "e poi?", "fonte?",
"torna indietro", "perché?". It fires only when the WHOLE normalized input
is one of its triggers (optionally after a filler word), and only while a
thread is active, so it can never steal a real question from the layers
below. Every answer is derived from content already verified in the KB:
first sentence, first code block, linked card, suggest graph, cited links.
"""
import json
import re

from qa import norm

ROOT = __file__.rsplit("/", 1)[0]


def load_dialog(root=None):
    try:
        return json.load(open(f"{root or ROOT}/dialog.json"))
    except FileNotFoundError:
        return None


def detect_act(dialog, text):
    """Act id for an input, or None. Whole-input match, one filler allowed."""
    if not dialog:
        return None
    n = norm(text)
    cands = [n]
    head, _, rest = n.partition(" ")
    if rest and head in dialog["fillers"]:
        cands.append(rest)
    for act in dialog["acts"]:
        for c in cands:
            if c in act["triggers"]:
                return act["id"]
    return None


_SKIP = ("```", "- ", "|", "#", "*Te l", "1. ", "[")
_CODE = re.compile(r"```[a-z0-9]*\n.*?\n```", re.S)
_TITLE = re.compile(r"^\*\*[^*]+\*\*$")


def first_sentence(md):
    """The opening sentence of an answer, markdown kept, never splitting **bold**.
    Code blocks, lists, links-only and title-only paragraphs are skipped."""
    for para in _CODE.sub("\n\n", md).split("\n\n"):
        p = para.strip()
        if not p or p.startswith(_SKIP) or _TITLE.match(p):
            continue
        p = " ".join(p.split())
        parts = re.split(r"(?<=[.!?])\s+", p)
        out = ""
        for s in parts:
            out = (out + " " + s).strip()
            if out.count("**") % 2 == 0 and out.count("`") % 2 == 0 and len(out) >= 40:
                break
        if out.endswith(":"):
            out = out[:-1] + "."
        return out
    return None


_EXT = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")


def first_code(entry, idx):
    ans = entry["answers"]
    for a in [ans[idx % len(ans)]] + ans:
        m = _CODE.search(a)
        if m:
            return m.group(0)
    return None


def ext_links(entry, cap=4):
    seen, out = set(), []
    for a in entry["answers"]:
        for label, url in _EXT.findall(a):
            if url not in seen:
                seen.add(url)
                out.append(f"- [{label}]({url})")
    return out[:cap]


def fill(tpl, **kw):
    for k, v in kw.items():
        tpl = tpl.replace("{" + k + "}", str(v))
    return tpl


def act_entry(act_id, answer, suggest):
    return {"id": "act/" + act_id, "question": act_id, "answers": [answer],
            "suggest": suggest, "kind": "act"}
