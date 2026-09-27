#!/usr/bin/env python3
"""Gate T12: no long dashes in any user-visible text.

Run:  python3 dashcheck.py          (exit 0 only if every text is clean)

Every form in the table below is forbidden in prose shown to the user
(chat answers, static pages, titles, tool outputs, llms.txt). The only
admitted use of U+2013 is a numeric/date range with no spaces
(2020-2024 written with an en dash, 10-20 GB likewise).

Excluded from the check (and from replacement): fenced/inline code spans,
URLs, command-line flags (--fix), and U+2212 MINUS SIGN (math in ground.json).

Usage as a library (bench.py G1 reuses the same control on the data files):
    from dashcheck import scan_data_files, violations_in_text
"""
import json
import os
import re
import sys

ROOT = __file__.rsplit("/", 1)[0]

# (label, checker-kind) -- single chars are counted literally, the rest by regex
SINGLE_FORMS = {
    "em-dash U+2014": "\u2014",
    "horizontal-bar U+2015": "\u2015",
    "two-em U+2E3A": "\u2e3a",
    "three-em U+2E3B": "\u2e3b",
    "small-em U+FE58": "\ufe58",
    "presentation-vertical U+FE31": "\ufe31",
    "presentation-vertical U+FE32": "\ufe32",
    "figure-dash U+2012": "\u2012",
}
FORM_ORDER = list(SINGLE_FORMS) + [
    "en-dash U+2013 (not digit-digit)",
    "entity mdash/ndash",
    "escape \\u2013/\\u2014",
    "ascii --/--- in prose",
]

ENTITY_RE = re.compile(r"&(?:mdash|ndash);|&#(?:8212|8211);|&#x(?:2014|2013);", re.IGNORECASE)
# literal backslash-u escapes as they appear in JS/Python sources
ESCAPE_RE = re.compile(r"\\u(?:2012|2013|2014|2015|2e3a|2e3b|fe58|fe31|fe32)", re.IGNORECASE)
FENCED_RE = re.compile(r"```[\s\S]*?```")
INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
MD_LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)]*)\)")
BARE_URL_RE = re.compile(r"(?:https?://|mailto:)[^\s)\"'<>]+")
# CLI flags (--fix, --type-check) are not prose dashes
FLAG_RE = re.compile(r"--[A-Za-z0-9][\w.-]*")
# `--` as end-of-options separator (lsof +f -- /path), not a prose dash
ENDOPTS_RE = re.compile(r"--(?=\s*(?:/[^\s]*|$))")
# chmod symbolic notation (rwxr-xr--) is not a prose dash
# (lookarounds, not \b: a trailing "-" is a non-word char)
CHMOD_RE = re.compile(r"(?<![\w-])[rwx-]{9}(?![\w-])")
# markdown thematic break on its own line renders as <hr>, not as a dash
HR_LINE_RE = re.compile(r"(?m)^\s*---+\s*$")
ASCII_DASH_RE = re.compile(r"--+")


def strip_nondisplay(text):
    """Drop code spans/blocks, keep link text, drop URLs: what remains is prose."""
    t = FENCED_RE.sub(" ", text)
    t = INLINE_CODE_RE.sub(" ", t)
    t = MD_LINK_RE.sub(r"\1", t)
    t = BARE_URL_RE.sub(" ", t)
    return t


def violations_in_text(text):
    """Return {form-label: count} for one prose string.

    Code spans/blocks, URLs, CLI flags, end-of-options `--`, chmod notation
    and markdown `---` rules are stripped first: the gate only sees prose.
    """
    out = {}
    for label, ch in SINGLE_FORMS.items():
        n = text.count(ch)
        if n:
            out[label] = n
    prose = strip_nondisplay(text)
    for label, ch in SINGLE_FORMS.items():
        n = prose.count(ch)
        if n:
            out[label + " [prose]"] = n
    # en dash: admitted only between two digits, no spaces
    n_bad_prose = 0
    for m in re.finditer("\u2013", prose):
        i = m.start()
        before = prose[i - 1] if i > 0 else ""
        after = prose[i + 1] if i + 1 < len(prose) else ""
        if not (before.isdigit() and after.isdigit()):
            n_bad_prose += 1
    if n_bad_prose:
        out["en-dash U+2013 (not digit-digit)"] = n_bad_prose
    n = len(ENTITY_RE.findall(prose))
    if n:
        out["entity mdash/ndash"] = n
    n = len(ESCAPE_RE.findall(prose))
    if n:
        out["escape \\u2013/\\u2014"] = n
    ascii_probe = prose.replace("\\n", "\n")
    ascii_probe = HR_LINE_RE.sub(" ", ascii_probe)
    ascii_probe = FLAG_RE.sub(" ", ascii_probe)
    ascii_probe = ENDOPTS_RE.sub(" ", ascii_probe)
    ascii_probe = CHMOD_RE.sub(" ", ascii_probe)
    n = len(ASCII_DASH_RE.findall(ascii_probe))
    if n:
        out["ascii --/--- in prose"] = n
    return out


def walk_strings(node, path=""):
    """Yield (field-path, string) for every string in a JSON structure."""
    if isinstance(node, dict):
        for k, v in node.items():
            yield from walk_strings(v, f"{path}.{k}" if path else str(k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from walk_strings(v, f"{path}[{i}]")
    elif isinstance(node, str):
        yield path, node


DATA_FILES = [
    "faq.json",
    "ground.json",
    "commands.json",
    "ports.json",
    "paths.json",
    "dialog.json",
    "guard.json",
    "diagrams.json",
]

SOURCE_FILES = ["app.js", "tools.js", "build.py", "build_diagrams.py"]

# string literals in JS/Python sources: '...' "..." `...` '''...''' """..."""
LITERAL_RE = re.compile(
    r"'''(?P<sq3>[\s\S]*?)'''"
    r"|\"\"\"(?P<dq3>[\s\S]*?)\"\"\""
    r"|(?P<tq>`(?:\\.|[^`\\])*(?:\$\{(?:[^{}]|\{[^{}]*\})*\}(?:\\.|[^`\\])*)*`)"
    r"|'(?P<sq>(?:\\.|[^'\\\n])*)'"
    r'|"(?P<dq>(?:\\.|[^"\\\n])*)"',
)

HTML_DIRS = ["q", "comandi", "porta", "percorsi", "tools", "trasparenza"]
HTML_TOP = ["index.html", "404.html"]
TEXT_ARTIFACTS = ["llms.txt", "llms-full.txt"]


def scan_data_files(root=ROOT):
    """Check every string of the JSON data files. Returns list of
    (file, field, form, count)."""
    hits = []
    for f in DATA_FILES:
        p = os.path.join(root, f)
        if not os.path.exists(p):
            continue
        try:
            data = json.load(open(p, encoding="utf-8"))
        except Exception as e:
            hits.append((f, "<file>", f"unparseable ({e})", 1))
            continue
        for field, s in walk_strings(data):
            for form, n in violations_in_text(s).items():
                if "[prose]" in form or form in SINGLE_FORMS:
                    continue  # raw counts below subsume prose ones for JSON
                hits.append((f, field, form, n))
        # raw (pre-strip) sweep catches dashes hidden inside code spans too,
        # reported separately so replacements stay out of code
        raw = json.dumps(data, ensure_ascii=False)
        for label, ch in SINGLE_FORMS.items():
            n = raw.count(ch)
            if n:
                hits.append((f, "<raw>", label + " (incl. code spans)", n))
    return hits


def scan_source_file(path):
    """Check string literals of a JS/Python source file."""
    hits = []
    fname = os.path.basename(path)
    try:
        text = open(path, encoding="utf-8").read()
    except FileNotFoundError:
        return hits
    n = len(ESCAPE_RE.findall(text))
    if n:
        hits.append((fname, "<raw>", "escape \\u2013/\\u2014", n))
    for m in LITERAL_RE.finditer(text):
        lit = next(g for g in m.groups() if g is not None)
        lineno = text.count("\n", 0, m.start()) + 1
        for form, count in violations_in_text(lit).items():
            if "[prose]" in form or form in SINGLE_FORMS:
                continue
            hits.append((fname, f"line {lineno}", form, count))
    return hits


def scan_html_file(path, root=ROOT):
    """Check a generated HTML page (tags/comments stripped, text kept)."""
    hits = []
    rel = os.path.relpath(path, root)
    try:
        text = open(path, encoding="utf-8").read()
    except FileNotFoundError:
        return hits
    prose_hits = violations_in_text(re.sub(r"<!--[\s\S]*?-->", " ", text))
    for form, n in prose_hits.items():
        if "[prose]" in form or form in SINGLE_FORMS:
            continue
        if form.startswith("en-dash"):
            continue  # counted once below on rendered text
        hits.append((rel, "<page>", form, n))
    body = re.sub(r"<!--[\s\S]*?-->", " ", text)
    body = re.sub(r"<[^>]*>", " ", body)
    for form, n in violations_in_text(body).items():
        if "[prose]" not in form and not form.startswith("en-dash"):
            continue
        hits.append((rel, "<rendered-text>", form.replace(" [prose]", ""), n))
    return hits


def scan_text_artifact(path, root=ROOT):
    hits = []
    rel = os.path.basename(path)
    try:
        text = open(path, encoding="utf-8").read()
    except FileNotFoundError:
        return hits
    for form, n in violations_in_text(text).items():
        if "[prose]" in form or form in SINGLE_FORMS:
            continue
        hits.append((rel, "<text>", form, n))
    return hits


def main():
    hits = []
    hits += scan_data_files()
    for f in SOURCE_FILES:
        hits += scan_source_file(os.path.join(ROOT, f))
    for f in HTML_TOP:
        hits += scan_html_file(os.path.join(ROOT, f))
    for d in HTML_DIRS:
        dd = os.path.join(ROOT, d)
        if not os.path.isdir(dd):
            continue
        for dirpath, _, filenames in os.walk(dd):
            for fn in sorted(filenames):
                if fn.endswith(".html"):
                    hits += scan_html_file(os.path.join(dirpath, fn))
    for f in TEXT_ARTIFACTS:
        hits += scan_text_artifact(os.path.join(ROOT, f))

    by_form, by_file = {}, {}
    for f, field, form, n in hits:
        base = form.replace(" [prose]", "").replace(" (incl. code spans)", "")
        by_form[base] = by_form.get(base, 0) + n
        by_file[f] = by_file.get(f, 0) + n

    print("dashcheck T12: long dashes in user-visible text")
    print(f"  violations: {len(hits)} locations")
    print("  by form:")
    for form in FORM_ORDER:
        if form in by_form:
            print(f"    {by_form[form]:6d}  {form}")
    for form in sorted(set(by_form) - set(FORM_ORDER)):
        print(f"    {by_form[form]:6d}  {form}")
    print("  by file:")
    for f, n in sorted(by_file.items(), key=lambda x: -x[1]):
        print(f"    {n:6d}  {f}")
    detail = "-v" in sys.argv
    if detail:
        for f, field, form, n in hits:
            print(f"    {f} {field}: {form} x{n}")
    total = sum(by_form.values())
    print(f"  TOTAL: {total}")
    print("DASHCHECK:", "PASS" if total == 0 else "FAIL")
    return 0 if total == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
