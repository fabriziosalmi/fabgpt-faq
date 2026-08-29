#!/usr/bin/env python3
"""FabGPT static page generator.

Reads faq.json and emits crawlable pages for search engines and AI answer
engines (Google AI Overview & co.): one page per question with FAQPage
JSON-LD, a full index page, sitemap.xml and robots.txt.

Zero dependencies. Run after every faq.json edit:

    python3 build.py
"""
import json
import html
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).parent
OUT = ROOT / "q"


# ---------- minimal markdown, mirroring app.js renderMd() ----------

def inline_md(s: str) -> str:
    s = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2" target="_blank" rel="noopener">\1</a>', s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"\*([^*\n]+)\*", r"<em>\1</em>", s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    return s


def render_md(text: str) -> str:
    out = []
    for block in re.split(r"\n\n+", text):
        lines = block.split("\n")
        if all(re.match(r"^\s*-\s+", l) for l in lines):
            stripped = [re.sub(r"^\s*-\s+", "", l) for l in lines]
            items = "".join("<li>" + inline_md(html.escape(l)) + "</li>" for l in stripped)
            out.append(f"<ul>{items}</ul>")
        else:
            out.append("<p>" + inline_md(html.escape(block)).replace("\n", "<br>") + "</p>")
    return "".join(out)


def md_to_plain(text: str) -> str:
    """Markdown -> plain text, for meta descriptions and JSON-LD answers."""
    s = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r"\1", text)
    s = re.sub(r"[*`]", "", s)
    s = re.sub(r"^\s*-\s+", "", s, flags=re.M)
    return re.sub(r"\s+", " ", s).strip()


def meta_description(text: str, limit: int = 158) -> str:
    plain = md_to_plain(text)
    if len(plain) <= limit:
        return plain
    return plain[: limit - 1].rsplit(" ", 1)[0] + "…"


# ---------- page templates ----------

PAGE = """<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<meta name="description" content="{description}">
<link rel="canonical" href="{canonical}">
<link rel="stylesheet" href="{base}style.css">
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><circle cx='50' cy='50' r='45' fill='%2310a37f'/><text x='50' y='68' font-size='52' text-anchor='middle' fill='white' font-family='sans-serif'>F</text></svg>">
<script type="application/ld+json">{jsonld}</script>
<style>
  .page {{ max-width: 768px; margin: 0 auto; padding: 24px 16px 48px; }}
  .page h1 {{ font-size: 26px; line-height: 1.3; margin: 8px 0 20px; }}
  .page .answer a {{ color: var(--link); }}
  .page .vertical {{ font-size: 13px; color: var(--text-dim); text-transform: uppercase; letter-spacing: 0.06em; }}
  .page .answer ul {{ padding-left: 22px; }}
  .page .answer code {{ background: var(--code-bg); border-radius: 5px; padding: 1px 5px; font-size: 0.9em; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }}
  .page .ask {{ display: inline-block; margin-top: 24px; background: var(--accent); color: var(--accent-text); border-radius: 999px; padding: 9px 18px; text-decoration: none; font-weight: 600; }}
  .page .related {{ margin-top: 36px; border-top: 1px solid var(--border); padding-top: 18px; }}
  .page .related h2 {{ font-size: 16px; }}
  .page .related a {{ color: var(--link); text-decoration: none; }}
  .page .related a:hover {{ text-decoration: underline; }}
  .page .related li {{ margin: 6px 0; }}
</style>
</head>
<body>
<header class="topbar">
  <a class="brand" href="{base}" style="text-decoration:none;color:inherit">
    <span class="brand-dot">F</span>
    <span class="brand-name">FabGPT</span>
    <span class="brand-tag">faq</span>
  </a>
</header>
<main class="page">
  <div class="vertical">{vertical}</div>
  <h1>{question}</h1>
  <div class="answer">{answer}</div>
  <a class="ask" href="{base}?q={id}">Chiedilo a FabGPT →</a>
  <div class="related">
    <h2>Altre domande</h2>
    <ul>{related}</ul>
  </div>
</main>
</body>
</html>
"""

INDEX = """<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Tutte le domande — FabGPT</title>
<meta name="description" content="{description}">
<link rel="canonical" href="{canonical}">
<link rel="stylesheet" href="../style.css">
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><circle cx='50' cy='50' r='45' fill='%2310a37f'/><text x='50' y='68' font-size='52' text-anchor='middle' fill='white' font-family='sans-serif'>F</text></svg>">
<script type="application/ld+json">{jsonld}</script>
<style>
  .page {{ max-width: 768px; margin: 0 auto; padding: 24px 16px 48px; }}
  .page h1 {{ font-size: 26px; margin: 8px 0 8px; }}
  .page h2 {{ font-size: 15px; color: var(--text-dim); text-transform: uppercase; letter-spacing: 0.06em; margin: 28px 0 8px; }}
  .page a {{ color: var(--link); text-decoration: none; }}
  .page a:hover {{ text-decoration: underline; }}
  .page li {{ margin: 7px 0; }}
  .page .intro {{ color: var(--text-dim); }}
</style>
</head>
<body>
<header class="topbar">
  <a class="brand" href="../" style="text-decoration:none;color:inherit">
    <span class="brand-dot">F</span>
    <span class="brand-name">FabGPT</span>
    <span class="brand-tag">faq</span>
  </a>
</header>
<main class="page">
  <h1>Tutte le domande</h1>
  <p class="intro">La knowledge base completa di FabGPT: cybersecurity, AI, Proxmox, Cloudflare e i progetti open source di Fabrizio Salmi. Oppure <a href="../">chiedi in chat</a>.</p>
  {sections}
</main>
</body>
</html>
"""


def build() -> None:
    db = json.loads((ROOT / "faq.json").read_text(encoding="utf-8"))
    site = db["config"]["siteUrl"].rstrip("/")
    entries = db["entries"]
    verticals = {v["id"]: v["label"] for v in db.get("verticals", [])}

    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()

    # --- one page per question ---
    for e in entries:
        answer_md = e["answers"][0]
        others = [o for o in entries if o["id"] != e["id"] and o["vertical"] == e["vertical"]]
        others += [o for o in entries if o["id"] != e["id"] and o["vertical"] != e["vertical"]]
        related = "".join(
            f'<li><a href="../{o["slug"]}/">{html.escape(o["question"])}</a></li>' for o in others[:6]
        )
        jsonld = {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [{
                "@type": "Question",
                "name": e["question"],
                "acceptedAnswer": {"@type": "Answer", "text": md_to_plain(answer_md)},
            }],
        }
        page = PAGE.format(
            title=html.escape(e["question"]) + " — FabGPT",
            description=html.escape(meta_description(answer_md)),
            canonical=f"{site}/q/{e['slug']}/",
            base="../../",
            jsonld=json.dumps(jsonld, ensure_ascii=False),
            vertical=html.escape(verticals.get(e["vertical"], "")),
            question=html.escape(e["question"]),
            answer=render_md(answer_md),
            id=e["id"],
            related=related,
        )
        d = OUT / e["slug"]
        d.mkdir()
        (d / "index.html").write_text(page, encoding="utf-8")

    # --- index page with full FAQPage JSON-LD ---
    sections = ""
    for vid, label in verticals.items():
        ventries = [e for e in entries if e["vertical"] == vid]
        if not ventries:
            continue
        items = "".join(f'<li><a href="{e["slug"]}/">{html.escape(e["question"])}</a></li>' for e in ventries)
        sections += f"<h2>{html.escape(label)}</h2>\n<ul>{items}</ul>\n"
    index_jsonld = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": e["question"],
                "acceptedAnswer": {"@type": "Answer", "text": md_to_plain(e["answers"][0])},
            }
            for e in entries
        ],
    }
    (OUT / "index.html").write_text(
        INDEX.format(
            description="Tutte le domande e risposte di FabGPT: cybersecurity, AI, Proxmox, Cloudflare e i progetti open source di Fabrizio Salmi.",
            canonical=f"{site}/q/",
            jsonld=json.dumps(index_jsonld, ensure_ascii=False),
            sections=sections,
        ),
        encoding="utf-8",
    )

    # --- sitemap.xml + robots.txt ---
    urls = [f"{site}/", f"{site}/q/"] + [f"{site}/q/{e['slug']}/" for e in entries]
    sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    sitemap += "".join(f"  <url><loc>{u}</loc></url>\n" for u in urls)
    sitemap += "</urlset>\n"
    (ROOT / "sitemap.xml").write_text(sitemap, encoding="utf-8")
    (ROOT / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {site}/sitemap.xml\n", encoding="utf-8")

    print(f"Built {len(entries)} question pages + index + sitemap ({len(urls)} URLs).")


if __name__ == "__main__":
    build()
