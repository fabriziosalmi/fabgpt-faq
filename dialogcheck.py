#!/usr/bin/env python3
"""Gate T10: dialogue acts (dialog.json) - follow-ups on the active thread.

  D1 integrita    - every act has triggers and its templates, triggers are
                    already normalized, unique across acts, no em dash.
  D2 no-steal     - no real question (KB canonical, tests.json, convos,
                    trajectories, ground canonical, card question) is an act
                    trigger: an act can only fire on a bare follow-up.
  D3 sessioni     - scripted multi-turn sessions route 100% as expected
                    (act ids "act/<id>", or the entry id for "e poi").
  D4 solo verificato - over every KB entry, card and ground entry, what an
                    act extracts (sentence, code, links) is verbatim content
                    of that entry: acts derive, they never generate.
  D5 parita JS    - the act block in app.js, run under node, returns the
                    same detectAct / firstSentence / firstCode as dialog.py
                    over every trigger and every answer.

Run: python3 dialogcheck.py [-v]
"""
import json
import re
import subprocess
import sys

from dialog import load_dialog, detect_act, first_sentence, first_code, ext_links
from qa import norm, load_ground, command_entry
from traj import Runtime

ROOT = __file__.rsplit("/", 1)[0]
VERBOSE = "-v" in sys.argv

TEMPLATES = {
    "breve": ["breve", "breveNone", "breveLink"],
    "esempio": ["esempioCode", "esempioCard", "esempioNone"],
    "dopo": ["dopo", "dopoNone"],
    "fonte": ["fontePage", "fonteCard", "fonteGround", "fonteLinks"],
    "indietro": ["indietro", "indietroNone"],
    "perche": ["perche"],
}

SESSIONS = [
    {"name": "proxmox-in-profondita", "turns": [
        ("riassumi", "fallback"),                       # no thread yet: act inactive
        ("cos'è proxmox?", "cos-e-proxmox"),
        ("riassumi", "act/breve"),
        ("fammi un esempio", "act/esempio"),
        ("fonte?", "act/fonte"),
        ("e poi?", "lxc-vs-vm"),
        ("perché?", "act/perche"),
        ("in breve", "act/breve"),
        ("torna indietro", "act/indietro"),
        ("ok, e poi", "act/dopo-or-entry"),
    ]},
    {"name": "comando-e-cultura", "turns": [
        ("come aggiorno le immagini dello stack compose?", "cmd/docker_compose_update"),
        ("esempio", "act/esempio"),
        ("fonte", "act/fonte"),
        ("tl;dr", "act/breve"),
        ("cos'è certmate?", "certmate"),
        ("fammi un esempio", "act/esempio"),
        ("indietro", "act/indietro"),
        ("indietro", "act/indietro"),
        ("di cosa parlavamo?", "act/indietro"),
    ]},
]


def gate(name, passed, total):
    pct = 100.0 * passed / total if total else 100.0
    ok = passed == total
    print(f"{'PASS' if ok else 'FAIL'}  {name}: {passed}/{total} ({pct:.1f}%, need 100%)")
    return ok


def flat(s):
    return " ".join(s.split())


def main():
    dialog = load_dialog()
    db = json.load(open(f"{ROOT}/faq.json"))
    cards = json.load(open(f"{ROOT}/commands.json"))["cards"]
    ports = json.load(open(f"{ROOT}/ports.json"))["ports"]
    ground = load_ground(ROOT)
    all_ok = True

    # ---- D1 integrita ---------------------------------------------------
    bad = []
    owner = {}
    for a in dialog["acts"]:
        if not a["triggers"]:
            bad.append(f"{a['id']}: nessun trigger")
        for k in TEMPLATES.get(a["id"], [None]):
            if k is None or k not in dialog["templates"]:
                bad.append(f"{a['id']}: template mancante {k}")
        for t in a["triggers"]:
            if norm(t) != t:
                bad.append(f"{a['id']}: trigger non normalizzato {t!r}")
            if t in owner:
                bad.append(f"trigger {t!r} in {owner[t]} e {a['id']}")
            owner[t] = a["id"]
    if "—" in json.dumps(dialog, ensure_ascii=False):
        bad.append("em dash in dialog.json")
    for b in bad:
        print(f"  D1: {b}")
    all_ok &= gate("D1 integrita", len(TEMPLATES) + len(owner) - len(bad), len(TEMPLATES) + len(owner))

    # ---- D2 no-steal ----------------------------------------------------
    qs = [e["question"] for e in db["entries"]] + [g["question"] for g in ground]
    qs += [c["q"] for c in cards]
    qs += [t["q"] for t in json.load(open(f"{ROOT}/tests.json"))]
    for sess in json.load(open(f"{ROOT}/convos.json")):
        qs += [t["q"] for t in sess["turns"]]
    for tr in json.load(open(f"{ROOT}/trajectories.json")):
        qs += [t["q"] for t in tr.get("turns", tr.get("steps", [])) if isinstance(t, dict) and "q" in t]
    steals = [q for q in qs if detect_act(dialog, q)]
    for q in steals[:10]:
        print(f"  D2: {q!r} -> act/{detect_act(dialog, q)}")
    all_ok &= gate("D2 no-steal", len(qs) - len(steals), len(qs))

    # ---- D3 sessioni ----------------------------------------------------
    tot = fail = 0
    for sess in SESSIONS:
        rt = Runtime(db, cards, ports, ground, dialog)
        for q, exp in sess["turns"]:
            tot += 1
            entry, _ = rt.ask(q)
            got = entry["id"] if entry else "fallback"
            ok = got == exp or (exp == "act/dopo-or-entry" and (got == "act/dopo" or not got.startswith(("act/", "st-", "fallback"))))
            if not ok:
                fail += 1
                print(f"  D3 [{sess['name']}] {q!r}: want {exp}, got {got}")
            elif VERBOSE:
                print(f"       [{sess['name']}] {q!r} -> {got}")
    all_ok &= gate("D3 sessioni", tot - fail, tot)

    # ---- D4 solo verificato --------------------------------------------
    pool = db["entries"] + [command_entry(c) for c in cards] + ground
    tot = fail = 0
    for e in pool:
        for i, a in enumerate(e["answers"]):
            tot += 1
            s = first_sentence(a)
            if s is not None and flat(s) not in flat(a):
                fail += 1
                print(f"  D4 {e['id']}[{i}]: frase non verbatim {s[:60]!r}")
        code = first_code(e, 0)
        tot += 1
        if code is not None and not any(code in a for a in e["answers"]):
            fail += 1
            print(f"  D4 {e['id']}: codice non verbatim")
        for ln in ext_links(e):
            tot += 1
            url = ln[ln.rindex("(") + 1:-1]
            if not any(url in a for a in e["answers"]):
                fail += 1
                print(f"  D4 {e['id']}: link non verbatim {url}")
    all_ok &= gate("D4 solo verificato", tot - fail, tot)

    # ---- D5 parita JS ---------------------------------------------------
    src = open(f"{ROOT}/app.js").read()
    a = src.index("/* ---------- text normalization")
    b = src.index("  function bigrams")
    c = src.index("/* ---------- dialogue acts")
    d = src.index("/* ---------- minimal markdown")
    probes = sorted(owner) + ["e " + t for t in list(owner)[:20]] + qs[:300]
    answers = [x for e in pool for x in e["answers"]]
    payload = {"probes": probes, "answers": answers, "dialog": dialog}
    js = ("let DIALOG, COMMANDS=[], ctxEntry=null;\n" + src[a:b] + src[c:d] +
          "const P=JSON.parse(require('fs').readFileSync(0,'utf8'));DIALOG=P.dialog;"
          "process.stdout.write(JSON.stringify({act:P.probes.map(detectAct),"
          "sent:P.answers.map(firstSentence),"
          "code:P.answers.map(x=>firstCode({answers:[x]},0))}));")
    try:
        out = subprocess.run(["node", "-e", js], input=json.dumps(payload),
                             capture_output=True, text=True, check=True).stdout
        got = json.loads(out)
        want_act = [detect_act(dialog, p) for p in probes]
        want_sent = [first_sentence(x) for x in answers]
        want_code = [first_code({"answers": [x]}, 0) for x in answers]
        diffs = [("act", p, g, w) for p, g, w in zip(probes, got["act"], want_act) if g != w]
        diffs += [("sent", x[:50], g, w) for x, g, w in zip(answers, got["sent"], want_sent) if g != w]
        diffs += [("code", x[:50], g, w) for x, g, w in zip(answers, got["code"], want_code) if g != w]
        for k, x, g, w in diffs[:10]:
            print(f"  D5 {k} {x!r}: js={str(g)[:60]!r} py={str(w)[:60]!r}")
        n = len(probes) + 2 * len(answers)
        all_ok &= gate("D5 parita JS", n - len(diffs), n)
    except (OSError, subprocess.CalledProcessError) as err:
        print(f"  D5: node non eseguibile: {getattr(err, 'stderr', err)}")
        all_ok &= gate("D5 parita JS", 0, 1)

    print("DIALOGCHECK:", "PASS" if all_ok else "FAIL")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
