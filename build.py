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
    # internal links: scheme-less relative paths (convention: "q/<slug>/")
    s = re.sub(r"\[([^\]]+)\]\(([^):\s]+)\)", r'<a href="\2">\1</a>', s)
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


def _wrap(text: str, width: int) -> list:
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width and cur:
            lines.append(cur); cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        lines.append(cur)
    return lines


def glyph(vid: str) -> str:
    """Small theme-aware SVG glyph per vertical, drawn with the accent stroke."""
    inner = {
        "security": "<path d='M12 3l7 3v5c0 4-3 7-7 8-4-1-7-4-7-8V6z'/>",   # shield
        "ai": "<circle cx='12' cy='12' r='3'/><path d='M12 3v3M12 18v3M3 12h3M18 12h3M6 6l2 2M16 16l2 2M18 6l-2 2M8 16l-2 2'/>",  # spark/node
        "proxmox": "<rect x='4' y='5' width='16' height='4' rx='1'/><rect x='4' y='11' width='16' height='4' rx='1'/><path d='M8 7h.01M8 13h.01'/>",  # server stack
        "cloudflare": "<path d='M7 17h10a3 3 0 000-6 5 5 0 00-9.6-1.3A3.5 3.5 0 007 17z'/>",  # cloud
        "tools": "<path d='M14 6a3 3 0 00-4 4l-6 6 2 2 6-6a3 3 0 004-4l-2 2-2-.5L11.5 8z'/>",  # wrench
        "creative": "<path d='M9 18V6l10-2v12'/><circle cx='7' cy='18' r='2'/><circle cx='17' cy='16' r='2'/>",  # music note
        "meta": "<path d='M4 5h16v10H9l-4 4v-4H4z'/>",   # chat bubble
    }.get(vid, "<circle cx='12' cy='12' r='7'/>")
    return (f"<svg class='glyph' viewBox='0 0 24 24' width='22' height='22' aria-hidden='true' "
            f"fill='none' stroke='var(--accent)' stroke-width='1.7' stroke-linecap='round' "
            f"stroke-linejoin='round'>{inner}</svg>")


def og_card(question: str, diagram_svg: str) -> str:
    """A 1200x630 branded OG card: the question + the concept diagram, in the
    dark brand palette (fixed, since OG images are viewed outside the site)."""
    q = html.escape(question)
    title_lines = _wrap(q, 42)[:3]
    title = "".join(
        f"<text x='80' y='{150 + i*64}' font-size='52' font-weight='700' "
        f"fill='#ececec' font-family='-apple-system,Segoe UI,Roboto,Arial,sans-serif'>{l}</text>"
        for i, l in enumerate(title_lines))
    # recolor the theme-var diagram to fixed dark-card colors
    d = (diagram_svg
         .replace("var(--accent)", "#10a37f").replace("var(--text-dim)", "#8b8f9a")
         .replace("var(--text)", "#d7d9de").replace("var(--border)", "#3a3d46")
         .replace("var(--bg-soft)", "#1a1d24"))
    d = re.sub(r"width='100%'", "width='560'", d, count=1)
    return (
        f"<svg xmlns='http://www.w3.org/2000/svg' width='1200' height='630' viewBox='0 0 1200 630'>"
        f"<rect width='1200' height='630' fill='#0f1117'/>"
        f"<rect width='1200' height='10' fill='#10a37f'/>"
        f"<circle cx='108' cy='72' r='30' fill='#10a37f'/>"
        f"<text x='108' y='86' font-size='34' font-weight='700' text-anchor='middle' fill='#fff' font-family='-apple-system,Segoe UI,Roboto,Arial,sans-serif'>F</text>"
        f"<text x='150' y='84' font-size='30' font-weight='700' fill='#ececec' font-family='-apple-system,Segoe UI,Roboto,Arial,sans-serif'>FabGPT-FAQ</text>"
        f"{title}"
        f"<g transform='translate(600 350)'>{d}</g>"
        f"</svg>\n")


# ---------- page templates ----------

PAGE = """<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<meta name="description" content="{description}">
<meta name="robots" content="index,follow,max-image-preview:large">
<link rel="canonical" href="{canonical}">
<meta property="og:type" content="article">
<meta property="og:title" content="{ogtitle}">
<meta property="og:description" content="{description}">
<meta property="og:url" content="{canonical}">
<meta property="og:image" content="{ogimg}">
<meta property="og:site_name" content="FabGPT-FAQ">
<meta property="og:locale" content="it_IT">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{ogtitle}">
<meta name="twitter:description" content="{description}">
<meta name="twitter:image" content="{ogimg}">
<link rel="stylesheet" href="{base}style.css">
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><circle cx='50' cy='50' r='45' fill='%2310a37f'/><text x='50' y='68' font-size='52' text-anchor='middle' fill='white' font-family='sans-serif'>F</text></svg>">
<script type="application/ld+json">{jsonld}</script>
<style>
  .page {{ max-width: 768px; margin: 0 auto; padding: 24px 16px 48px; }}
  .page h1 {{ font-size: 26px; line-height: 1.3; margin: 6px 0 20px; }}
  .crumbs {{ font-size: 13px; color: var(--text-dim); margin-bottom: 4px; }}
  .crumbs a {{ color: var(--text-dim); text-decoration: none; }}
  .crumbs a:hover {{ color: var(--text); }}
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
  .diagram {{ margin: 24px 0 8px; padding: 14px; border: 1px solid var(--border); border-radius: 12px; background: var(--bg-soft); }}
  .diagram svg {{ display: block; max-width: 100%; height: auto; }}
  .answer code {{ cursor: pointer; }}
  .answer code:hover {{ outline: 1px solid var(--border); }}
  .answer code.copied {{ outline: 1px solid var(--accent); color: var(--accent); }}
</style>
</head>
<body>
<header class="topbar">
  <a class="brand" href="{base}" style="text-decoration:none;color:inherit">
    <span class="brand-dot">F</span>
    <span class="brand-name">FabGPT-FAQ</span>
  </a>
</header>
<main class="page">
  <nav class="crumbs"><a href="{base}">FabGPT-FAQ</a> › <a href="{base}q/">Tutte le domande</a> › {vertical}</nav>
  <h1>{question}</h1>
  <div class="answer">{answer}</div>
  <a class="ask" href="{base}?q={id}">Chiedilo a FabGPT-FAQ →</a>
  <div class="related">
    <h2>Altre domande</h2>
    <ul>{related}</ul>
  </div>
</main>
<script>
document.addEventListener('click',function(e){{
  var c=e.target.closest('code'); if(!c)return;
  navigator.clipboard&&navigator.clipboard.writeText(c.textContent).then(function(){{
    c.classList.add('copied'); setTimeout(function(){{c.classList.remove('copied')}},900);
  }});
}});
</script>
</body>
</html>
"""

INDEX = """<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Tutte le domande – FabGPT-FAQ</title>
<meta name="description" content="{description}">
<meta name="robots" content="index,follow,max-image-preview:large">
<link rel="canonical" href="{canonical}">
<meta property="og:type" content="website">
<meta property="og:title" content="Tutte le domande – FabGPT-FAQ">
<meta property="og:description" content="{description}">
<meta property="og:url" content="{canonical}">
<meta property="og:image" content="{site}/og.svg">
<meta property="og:site_name" content="FabGPT-FAQ">
<meta property="og:locale" content="it_IT">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:image" content="{site}/og.svg">
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
  .page h2 {{ display: flex; align-items: center; gap: 8px; }}
  .page h2 .glyph {{ flex: 0 0 auto; }}
  .stats {{ display: flex; flex-wrap: wrap; gap: 10px 28px; margin: 20px 0 8px; padding: 16px 18px; border: 1px solid var(--border); border-radius: 12px; background: var(--bg-soft); }}
  .stat {{ display: flex; flex-direction: column; }}
  .stat b {{ font-size: 26px; color: var(--accent); font-variant-numeric: tabular-nums; }}
  .stat span {{ font-size: 12px; color: var(--text-dim); text-transform: uppercase; letter-spacing: 0.05em; }}
  @media (prefers-reduced-motion: no-preference) {{ .glyph {{ animation: glyph-in .5s ease both; }} }}
  @keyframes glyph-in {{ from {{ opacity: 0; transform: translateY(3px) scale(.9); }} to {{ opacity: 1; transform: none; }} }}
</style>
</head>
<body>
<header class="topbar">
  <a class="brand" href="../" style="text-decoration:none;color:inherit">
    <span class="brand-dot">F</span>
    <span class="brand-name">FabGPT-FAQ</span>
  </a>
</header>
<main class="page">
  <h1>Tutte le domande</h1>
  <p class="intro">La knowledge base completa di FabGPT-FAQ: cybersecurity, AI, Proxmox, Cloudflare e i progetti open source di Fabrizio Salmi. Oppure <a href="../">chiedi in chat</a>.</p>
  {sections}
</main>
<script>
(function(){{
  var reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  document.querySelectorAll('.stat b[data-to]').forEach(function(el){{
    var to = +el.getAttribute('data-to');
    if (reduce) {{ el.textContent = to; return; }}
    var t0 = null, dur = 900;
    requestAnimationFrame(function step(t){{
      if (!t0) t0 = t;
      var p = Math.min(1, (t - t0) / dur);
      el.textContent = Math.round(to * (1 - Math.pow(1 - p, 3)));
      if (p < 1) requestAnimationFrame(step);
    }});
  }});
}})();
</script>
</body>
</html>
"""


def build() -> None:
    db = json.loads((ROOT / "faq.json").read_text(encoding="utf-8"))
    site = db["config"]["siteUrl"].rstrip("/")
    entries = db["entries"]
    verticals = {v["id"]: v["label"] for v in db.get("verticals", [])}
    dpath = ROOT / "diagrams.json"
    diagrams = json.loads(dpath.read_text(encoding="utf-8")) if dpath.exists() else {}

    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()

    # --- one page per question ---
    by_slug = {e["slug"]: e for e in entries}
    for e in entries:
        answer_md = e["answers"][0]
        # Related = the curated `suggest` cross-references first (same data that
        # drives the chat chips), then same-vertical, then others, up to 6.
        seen = {e["slug"]}
        others = []
        for slug in e.get("suggest", []):
            o = by_slug.get(slug)
            if o and o["slug"] not in seen:
                others.append(o); seen.add(o["slug"])
        for o in entries:
            if o["slug"] not in seen and o["vertical"] == e["vertical"]:
                others.append(o); seen.add(o["slug"])
        for o in entries:
            if o["slug"] not in seen:
                others.append(o); seen.add(o["slug"])
        related = "".join(
            f'<li><a href="../{o["slug"]}/">{html.escape(o["question"])}</a></li>' for o in others[:6]
        )
        vlabel = verticals.get(e["vertical"], "")
        jsonld = [
            {
                "@context": "https://schema.org",
                "@type": "FAQPage",
                "mainEntity": [{
                    "@type": "Question",
                    "name": e["question"],
                    "acceptedAnswer": {"@type": "Answer", "text": md_to_plain(answer_md)},
                }],
            },
            {
                "@context": "https://schema.org",
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {"@type": "ListItem", "position": 1, "name": "FabGPT-FAQ", "item": f"{site}/"},
                    {"@type": "ListItem", "position": 2, "name": "Tutte le domande", "item": f"{site}/q/"},
                    {"@type": "ListItem", "position": 3, "name": vlabel, "item": f"{site}/q/{e['slug']}/"},
                ],
            },
        ]
        d = OUT / e["slug"]
        d.mkdir()
        # concept diagram (inline SVG) after the answer, in a <figure>
        dg = diagrams.get(e["id"], "")
        figure = (f'<figure class="diagram" aria-label="Schema: {html.escape(e["question"])}">'
                  f'{dg}</figure>') if dg else ""
        # entries with a diagram get a tailored OG card (the diagram on a branded canvas)
        if dg:
            (d / "og.svg").write_text(og_card(e["question"], dg), encoding="utf-8")
            ogimg = f"{site}/q/{e['slug']}/og.svg"
        else:
            ogimg = f"{site}/og.svg"
        page = PAGE.format(
            title=html.escape(e["question"]) + " – FabGPT-FAQ",
            ogtitle=html.escape(e["question"]),
            description=html.escape(meta_description(answer_md)),
            canonical=f"{site}/q/{e['slug']}/",
            base="../../",
            site=site,
            ogimg=ogimg,
            jsonld=json.dumps(jsonld, ensure_ascii=False),
            vertical=html.escape(vlabel),
            question=html.escape(e["question"]),
            answer=render_md(answer_md).replace('href="q/', 'href="../') + figure,
            id=e["id"],
            related=related,
        )
        (d / "index.html").write_text(page, encoding="utf-8")

    # --- index page with full FAQPage JSON-LD ---
    n_vert = sum(1 for v in verticals if any(e["vertical"] == v for e in entries))
    stat = (
        '<div class="stats" aria-label="Statistiche">'
        f'<div class="stat"><b data-to="{len(entries)}">0</b><span>risposte</span></div>'
        '<div class="stat"><b>0</b><span>allucinazioni</span></div>'
        '<div class="stat"><b>&euro;0</b><span>al mese</span></div>'
        f'<div class="stat"><b data-to="{n_vert}">0</b><span>temi</span></div>'
        '</div>')
    sections = stat
    for vid, label in verticals.items():
        ventries = [e for e in entries if e["vertical"] == vid]
        if not ventries:
            continue
        items = "".join(f'<li><a href="{e["slug"]}/">{html.escape(e["question"])}</a></li>' for e in ventries)
        sections += f'<h2>{glyph(vid)}<span>{html.escape(label)}</span></h2>\n<ul>{items}</ul>\n'
    index_jsonld = [
        {
            "@context": "https://schema.org",
            "@type": "WebSite",
            "name": "FabGPT-FAQ",
            "url": f"{site}/",
            "inLanguage": "it",
            "description": "FAQ interattiva su cybersecurity, AI, Proxmox, Cloudflare e i progetti open source di Fabrizio Salmi.",
        },
        {
            "@context": "https://schema.org",
            "@type": "Organization",
            "name": "Fabrizio Salmi",
            "url": "https://github.com/fabriziosalmi",
        },
        {
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
        },
    ]
    (OUT / "index.html").write_text(
        INDEX.format(
            description="Tutte le domande e risposte di FabGPT-FAQ: cybersecurity, AI, Proxmox, Cloudflare e i progetti open source di Fabrizio Salmi.",
            canonical=f"{site}/q/",
            site=site,
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
    (ROOT / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\n\nSitemap: {site}/sitemap.xml\n", encoding="utf-8")

    # --- llms.txt: concise map for answer engines (title + url, per vertical) ---
    lt = ["# FabGPT-FAQ\n",
          "> FAQ interattiva su cybersecurity, AI, Proxmox, Cloudflare e i progetti "
          "open source di Fabrizio Salmi. Risposte pre-scritte e verificate, ogni "
          "domanda anche come pagina statica citabile.\n",
          f"Chat: {site}/  ·  Indice: {site}/q/\n"]
    for vid, label in verticals.items():
        ventries = [e for e in entries if e["vertical"] == vid]
        if not ventries:
            continue
        lt.append(f"\n## {label}\n")
        for e in ventries:
            lt.append(f"- [{e['question']}]({site}/q/{e['slug']}/): {meta_description(e['answers'][0], 120)}")
    (ROOT / "llms.txt").write_text("\n".join(lt) + "\n", encoding="utf-8")

    # --- llms-full.txt: every Q&A as plain text (full corpus for citation) ---
    lf = ["# FabGPT-FAQ — knowledge base completa\n",
          "Domande e risposte verificate. Fonte: https://github.com/fabriziosalmi\n"]
    for vid, label in verticals.items():
        ventries = [e for e in entries if e["vertical"] == vid]
        if not ventries:
            continue
        lf.append(f"\n\n# {label}")
        for e in ventries:
            lf.append(f"\n\n## {e['question']}\n{site}/q/{e['slug']}/\n\n{md_to_plain(e['answers'][0])}")
    (ROOT / "llms-full.txt").write_text("".join(lf) + "\n", encoding="utf-8")

    # --- 404 page ---
    notfound = """<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Pagina non trovata – FabGPT-FAQ</title>
<meta name="robots" content="noindex">
<link rel="stylesheet" href="/style.css">
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><circle cx='50' cy='50' r='45' fill='%2310a37f'/><text x='50' y='68' font-size='52' text-anchor='middle' fill='white' font-family='sans-serif'>F</text></svg>">
<style>
  .nf {{ max-width: 620px; margin: 12vh auto; padding: 0 16px; text-align: center; }}
  .nf h1 {{ font-size: 64px; margin: 0; color: var(--accent); }}
  .nf p {{ color: var(--text-dim); }}
  .nf a {{ color: var(--link); text-decoration: none; }}
  .nf .actions {{ margin-top: 24px; display: flex; gap: 12px; justify-content: center; flex-wrap: wrap; }}
  .nf .btn {{ background: var(--accent); color: var(--accent-text); border-radius: 999px; padding: 9px 18px; font-weight: 600; }}
  .nf .btn.ghost {{ background: transparent; color: var(--link); border: 1px solid var(--border); }}
</style>
</head>
<body>
<main class="nf">
  <h1>404</h1>
  <p>Questa pagina si è persa nel labirinto. Ma la risposta che cerchi è probabilmente qui.</p>
  <div class="actions">
    <a class="btn" href="/">Chiedi in chat</a>
    <a class="btn ghost" href="/q/">Tutte le domande</a>
  </div>
</main>
</body>
</html>
"""
    (ROOT / "404.html").write_text(notfound, encoding="utf-8")

    print(f"Built {len(entries)} pages + index + sitemap ({len(urls)} URLs) + llms.txt + llms-full.txt + 404.")


if __name__ == "__main__":
    build()
