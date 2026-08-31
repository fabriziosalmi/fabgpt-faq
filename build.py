#!/usr/bin/env python3
"""Build static HTML pages for every Q&A entry -> /q/<slug>/index.html,
plus the /q/ index, sitemap.xml, robots.txt, llms.txt, llms-full.txt and 404.html.

Designed for SEO, AI engine citations (GEO), and zero-friction developer experience.
"""
import html
import json
import math
import os
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).parent
OUT = ROOT / "q"


def inline_md(s: str) -> str:
    s = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2" target="_blank" rel="noopener">\1</a>', s)
    # internal links: scheme-less relative paths (convention: "q/<slug>/")
    s = re.sub(r"\[([^\]]+)\]\(([^):\s]+)\)", r'<a href="\2">\1</a>', s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"\*([^*\n]+)\*", r"<em>\1</em>", s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    return s


def render_md(text: str) -> str:
    code_blocks = []

    def _cb(m):
        idx = len(code_blocks)
        lang = m.group(1).strip()
        code = m.group(2).strip()
        clang = f' class="language-{html.escape(lang)}"' if lang else ""
        header_lang = html.escape(lang.upper() if lang else "CODE")
        block_html = (
            f'<div class="code-block">'
            f'<div class="code-header"><span class="code-lang">{header_lang}</span>'
            f'<button type="button" class="copy-code-btn" aria-label="Copia codice">'
            f'<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>'
            f'<span>Copia</span></button></div>'
            f'<pre><code{clang}>{html.escape(code)}</code></pre>'
            f'</div>'
        )
        code_blocks.append(block_html)
        return f"\n\n@@@CODEBLOCK_{idx}@@@\n\n"

    processed = re.sub(r"```([a-zA-Z0-9_-]*)\n([\s\S]*?)```", _cb, text)
    out = []
    for block in re.split(r"\n\n+", processed):
        b = block.strip()
        if not b:
            continue
        if re.match(r"^@@@CODEBLOCK_\d+@@@$", b):
            idx = int(re.sub(r"\D", "", b))
            out.append(code_blocks[idx])
        elif all(re.match(r"^\s*-\s+", l) for l in b.split("\n")):
            stripped = [re.sub(r"^\s*-\s+", "", l) for l in b.split("\n")]
            items = "".join("<li>" + inline_md(html.escape(l)) + "</li>" for l in stripped)
            out.append(f"<ul>{items}</ul>")
        else:
            p_content = inline_md(html.escape(b)).replace("\n", "<br>")
            p_content = re.sub(r"@@@CODEBLOCK_(\d+)@@@", lambda m: code_blocks[int(m.group(1))], p_content)
            out.append(f"<p>{p_content}</p>")
    return "".join(out)


def md_to_plain(text: str) -> str:
    """Markdown -> plain text, for meta descriptions and JSON-LD answers."""
    s = re.sub(r"```[a-zA-Z0-9_-]*\n([\s\S]*?)```", r"\1", text)
    s = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r"\1", s)
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
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        lines.append(cur)
    return lines


def glyph(vid: str) -> str:
    """Small theme-aware SVG glyph per vertical, drawn with the accent stroke."""
    inner = {
        "security": "<path d='M12 3l7 3v5c0 4-3 7-7 8-4-1-7-4-7-8V6z'/>",  # shield
        "ai": "<circle cx='12' cy='12' r='3'/><path d='M12 3v3M12 18v3M3 12h3M18 12h3M6 6l2 2M16 16l2 2M18 6l-2 2M8 16l-2 2'/>",  # spark/node
        "proxmox": "<rect x='4' y='5' width='16' height='4' rx='1'/><rect x='4' y='11' width='16' height='4' rx='1'/><path d='M8 7h.01M8 13h.01'/>",  # server stack
        "cloudflare": "<path d='M7 17h10a3 3 0 000-6 5 5 0 00-9.6-1.3A3.5 3.5 0 007 17z'/>",  # cloud
        "tools": "<path d='M14 6a3 3 0 00-4 4l-6 6 2 2 6-6a3 3 0 004-4l-2 2-2-.5L11.5 8z'/>",  # wrench
        "creative": "<path d='M9 18V6l10-2v12'/><circle cx='7' cy='18' r='2'/><circle cx='17' cy='16' r='2'/>",  # music note
        "meta": "<path d='M4 5h16v10H9l-4 4v-4H4z'/>",  # chat bubble
    }.get(vid, "<circle cx='12' cy='12' r='7'/>")
    return (
        f"<svg class='glyph' viewBox='0 0 24 24' width='22' height='22' aria-hidden='true' "
        f"fill='none' stroke='var(--accent)' stroke-width='1.7' stroke-linecap='round' "
        f"stroke-linejoin='round'>{inner}</svg>"
    )


def og_card(question: str, diagram_svg: str) -> str:
    """A 1200x630 branded OG card: the question + the concept diagram, in the
    dark brand palette (fixed, since OG images are viewed outside the site)."""
    q = html.escape(question)
    title_lines = _wrap(q, 42)[:3]
    title = "".join(
        f"<text x='80' y='{150 + i*64}' font-size='52' font-weight='700' "
        f"fill='#ececec' font-family='-apple-system,Segoe UI,Roboto,Arial,sans-serif'>{l}</text>"
        for i, l in enumerate(title_lines)
    )
    # recolor the theme-var diagram to fixed dark-card colors
    d = (
        diagram_svg.replace("var(--accent)", "#10a37f")
        .replace("var(--text-dim)", "#8b8f9a")
        .replace("var(--text)", "#d7d9de")
        .replace("var(--border)", "#3a3d46")
        .replace("var(--bg-soft)", "#1a1d24")
    )
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
        f"</svg>\n"
    )


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
  .page h1 {{ font-size: 26px; line-height: 1.3; margin: 6px 0 10px; }}
  .crumbs {{ font-size: 13px; color: var(--text-dim); margin-bottom: 6px; }}
  .crumbs a {{ color: var(--text-dim); text-decoration: none; }}
  .crumbs a:hover {{ color: var(--text); }}
  .page .answer a {{ color: var(--link); }}
  .page .answer ul {{ padding-left: 22px; }}
  .page .answer code {{ background: var(--code-bg); border-radius: 5px; padding: 1px 5px; font-size: 0.9em; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }}
  .qa-actions {{ display: flex; align-items: center; gap: 12px; margin-top: 24px; flex-wrap: wrap; }}
  .copy-qa-btn {{ display: inline-flex; align-items: center; gap: 6px; background: var(--bg-soft); color: var(--text-dim); border: 1px solid var(--border); border-radius: 6px; padding: 6px 12px; font-size: 13px; font-family: inherit; font-weight: 500; cursor: pointer; transition: all .15s ease; }}
  .copy-qa-btn:hover {{ background: var(--border); color: var(--text); }}
  .copy-qa-btn.copied {{ background: rgba(16, 163, 127, 0.15); color: var(--accent); border-color: var(--accent); }}
  .page .ask {{ display: inline-block; background: var(--accent); color: var(--accent-text); border-radius: 999px; padding: 8px 16px; text-decoration: none; font-weight: 600; font-size: 13px; }}
  .page .related {{ margin-top: 36px; border-top: 1px solid var(--border); padding-top: 20px; }}
  .page .related h2 {{ font-size: 16px; margin-bottom: 12px; }}
  .page .related a {{ color: var(--link); text-decoration: none; }}
  .page .related a:hover {{ text-decoration: underline; }}
  .page .related li {{ margin: 8px 0; }}
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
  <nav class="topnav"><a href="{base}q/">Tutte le domande</a></nav>
</header>
<main class="page">
  <article itemscope itemtype="https://schema.org/TechArticle">
    <nav class="crumbs" aria-label="Percorso"><a href="{base}">FabGPT-FAQ</a> › <a href="{base}q/">Tutte le domande</a> › <span itemprop="articleSection">{vertical}</span></nav>
    <h1 id="page-question" itemprop="headline">{question}</h1>
    <div class="page-meta">
      <span class="page-meta-badge vert">{glyph_svg} <span>{vertical}</span></span>
      <span class="page-meta-badge">⏱️ {reading_time} min lettura</span>
      <span class="page-meta-badge">✓ Runbook verificato</span>
    </div>
    <div class="answer" id="page-answer" itemprop="articleBody">{answer}</div>
    <div class="qa-actions">
      <button type="button" class="copy-qa-btn" id="copy-page-btn" aria-label="Copia domanda e risposta">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
        <span>Copia Q&A</span>
      </button>
      <a class="ask" href="{base}?q={id}">Apri nella chat interattiva 💬</a>
    </div>
    {page_nav}
    <section class="ask-box">
      <div class="ask-box-header">
        <span class="ask-box-icon">💬</span>
        <div>
          <h3>Hai una domanda specifica su questo tema?</h3>
          <p>Interroga direttamente il motore FabGPT-FAQ con risposta in tempo reale a zero allucinazioni.</p>
        </div>
      </div>
      <form class="ask-box-form" action="{base}" method="get">
        <input type="text" name="q" value="{question}" placeholder="Chiedi qualcosa a FabGPT-FAQ…" aria-label="Chiedi qualcosa" autocomplete="off">
        <button type="submit">Chiedi in chat →</button>
      </form>
    </section>
    <div class="related">
      <h2>Domande correlate</h2>
      <ul>{related}</ul>
    </div>
  </article>
</main>
<script>
document.addEventListener('click',function(e){{
  var copyCodeBtn = e.target.closest('.copy-code-btn');
  if (copyCodeBtn) {{
    var block = copyCodeBtn.closest('.code-block');
    var code = block ? block.querySelector('code')?.textContent : '';
    if (code && navigator.clipboard) {{
      navigator.clipboard.writeText(code).then(function(){{
        copyCodeBtn.classList.add('copied');
        copyCodeBtn.querySelector('span').textContent = 'Copiato!';
        setTimeout(function(){{
          copyCodeBtn.classList.remove('copied');
          copyCodeBtn.querySelector('span').textContent = 'Copia';
        }}, 1500);
      }});
    }}
    return;
  }}
  var c=e.target.closest('code:not(pre code)'); if(!c)return;
  navigator.clipboard&&navigator.clipboard.writeText(c.textContent).then(function(){{
    c.classList.add('copied'); setTimeout(function(){{c.classList.remove('copied')}},900);
  }});
}});
document.getElementById('copy-page-btn')?.addEventListener('click', function(){{
  var btn = this;
  var q = document.getElementById('page-question')?.innerText.trim() || '';
  var a = document.getElementById('page-answer')?.innerText.trim() || '';
  var formatted = "Q: " + q + "\\n\\nA:\\n" + a;
  if(navigator.clipboard){{
    navigator.clipboard.writeText(formatted).then(function(){{
      btn.classList.add('copied');
      btn.querySelector('span').textContent = 'Copiato!';
      setTimeout(function(){{
        btn.classList.remove('copied');
        btn.querySelector('span').textContent = 'Copia Q&A';
      }}, 1500);
    }});
  }}
}});
document.querySelectorAll('.copy-diagram-btn').forEach(function(btn){{
  btn.addEventListener('click', function(e){{
    e.stopPropagation();
    var fig = btn.closest('.diagram');
    var svg = fig ? fig.querySelector('svg:not(.copy-diagram-btn svg)') : null;
    if(!svg) return;
    if(navigator.clipboard){{
      navigator.clipboard.writeText(svg.outerHTML).then(function(){{
        btn.classList.add('copied');
        btn.querySelector('span').textContent = 'Copiato!';
        setTimeout(function(){{
          btn.classList.remove('copied');
          btn.querySelector('span').textContent = 'SVG';
        }}, 1500);
      }});
    }}
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
  .page .intro {{ color: var(--text-dim); margin-bottom: 12px; }}
  .page h2 {{ display: flex; align-items: center; gap: 8px; }}
  .page h2 .glyph {{ flex: 0 0 auto; }}
  .stats {{ display: flex; flex-wrap: wrap; gap: 10px 28px; margin: 16px 0 20px; padding: 16px 18px; border: 1px solid var(--border); border-radius: 12px; background: var(--bg-soft); }}
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
  <nav class="topnav"><a href="../">Chat interattiva 💬</a></nav>
</header>
<main class="page">
  <h1>Tutte le domande</h1>
  <p class="intro">La knowledge base completa di FabGPT-FAQ: cybersecurity, AI, Proxmox, Cloudflare e i progetti open source di Fabrizio Salmi. Cerca in tempo reale o <a href="../">chiedi in chat</a>.</p>
  {stats}
  <div class="filter-wrap">
    <div class="search-box">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
      <input id="q-filter" type="search" placeholder="Filtra tra {total} domande per parola chiave..." autocomplete="off" aria-label="Filtra domande">
      <span id="filter-count" class="filter-count"></span>
    </div>
    <div class="filter-chips" id="v-chips" role="tablist">
      <button type="button" class="filter-chip active" data-v="all">Tutti ({total})</button>
      {chips}
    </div>
  </div>
  <div id="q-list">
    {sections}
  </div>
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

  // Live Instant Search & Vertical Filter
  var input = document.getElementById('q-filter');
  var countEl = document.getElementById('filter-count');
  var chips = document.querySelectorAll('#v-chips .filter-chip');
  var sections = document.querySelectorAll('#q-list .v-sec');
  var currentV = 'all';

  function filter() {{
    var query = input.value.trim().toLowerCase();
    var visibleTotal = 0;

    sections.forEach(function(sec){{
      var secV = sec.getAttribute('data-v');
      var matchesV = currentV === 'all' || currentV === secV;
      var items = sec.querySelectorAll('li');
      var secVisible = 0;

      if (!matchesV) {{
        sec.style.display = 'none';
        return;
      }}

      items.forEach(function(item){{
        var text = item.textContent.toLowerCase();
        var match = !query || text.indexOf(query) !== -1;
        item.style.display = match ? '' : 'none';
        if (match) {{ secVisible++; visibleTotal++; }}
      }});

      sec.style.display = secVisible > 0 ? '' : 'none';
    }});

    if (query || currentV !== 'all') {{
      countEl.textContent = visibleTotal + ' risposte';
    }} else {{
      countEl.textContent = '';
    }}
  }}

  input.addEventListener('input', filter);

  chips.forEach(function(chip){{
    chip.addEventListener('click', function(){{
      chips.forEach(function(c){{ c.classList.remove('active'); }});
      chip.classList.add('active');
      currentV = chip.getAttribute('data-v');
      filter();
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
        words = len(md_to_plain(answer_md).split())
        reading_time = max(1, math.ceil(words / 140))

        # Prev / Next in same vertical
        same_vert = [x for x in entries if x["vertical"] == e["vertical"]]
        try:
            curr_idx = next(i for i, x in enumerate(same_vert) if x["id"] == e["id"])
            prev_entry = same_vert[curr_idx - 1] if curr_idx > 0 else None
            next_entry = same_vert[curr_idx + 1] if curr_idx < len(same_vert) - 1 else None
        except StopIteration:
            prev_entry = None
            next_entry = None

        page_nav_parts = ['<nav class="page-nav" aria-label="Navigazione tra domande">']
        if prev_entry:
            page_nav_parts.append(
                f'<a class="page-nav-card prev" href="../{prev_entry["slug"]}/">'
                f'<span class="nav-dir">← Precedente</span>'
                f'<span class="nav-title">{html.escape(prev_entry["question"])}</span></a>'
            )
        else:
            page_nav_parts.append('<div class="page-nav-card placeholder"></div>')
        if next_entry:
            page_nav_parts.append(
                f'<a class="page-nav-card next" href="../{next_entry["slug"]}/">'
                f'<span class="nav-dir">Successiva →</span>'
                f'<span class="nav-title">{html.escape(next_entry["question"])}</span></a>'
            )
        else:
            page_nav_parts.append('<div class="page-nav-card placeholder"></div>')
        page_nav_parts.append("</nav>")
        page_nav = "".join(page_nav_parts)

        # Related = the curated `suggest` cross-references first, then same-vertical, then others, up to 6.
        seen = {e["slug"]}
        others = []
        for slug in e.get("suggest", []):
            o = by_slug.get(slug)
            if o and o["slug"] not in seen:
                others.append(o)
                seen.add(o["slug"])
        for o in entries:
            if o["slug"] not in seen and o["vertical"] == e["vertical"]:
                others.append(o)
                seen.add(o["slug"])
        for o in entries:
            if o["slug"] not in seen:
                others.append(o)
                seen.add(o["slug"])
        related = "".join(
            f'<li><a href="../{o["slug"]}/">{html.escape(o["question"])}</a></li>' for o in others[:6]
        )
        vlabel = verticals.get(e["vertical"], "")
        jsonld = [
            {
                "@context": "https://schema.org",
                "@type": "TechArticle",
                "headline": e["question"],
                "description": meta_description(answer_md),
                "author": {
                    "@type": "Person",
                    "name": "Fabrizio Salmi",
                    "url": "https://github.com/fabriziosalmi",
                },
                "publisher": {
                    "@type": "Organization",
                    "name": "FabGPT-FAQ",
                    "url": f"{site}/",
                },
                "inLanguage": "it",
                "articleSection": vlabel,
            },
            {
                "@context": "https://schema.org",
                "@type": "FAQPage",
                "mainEntity": [
                    {
                        "@type": "Question",
                        "name": e["question"],
                        "acceptedAnswer": {"@type": "Answer", "text": md_to_plain(answer_md)},
                    }
                ],
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
        d.mkdir(parents=True, exist_ok=True)
        # concept diagram (inline SVG) after the answer, in a <figure>
        dg = diagrams.get(e["id"], "")
        figure = (
            (
                f'<figure class="diagram" aria-label="Schema: {html.escape(e["question"])}">'
                f'<button type="button" class="copy-diagram-btn" aria-label="Copia codice SVG dello schema">'
                f'<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>'
                f"<span>SVG</span></button>"
                f"{dg}</figure>"
            )
            if dg
            else ""
        )
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
            glyph_svg=glyph(e["vertical"]),
            reading_time=reading_time,
            question=html.escape(e["question"]),
            answer=render_md(answer_md).replace('href="q/', 'href="../') + figure,
            id=e["id"],
            page_nav=page_nav,
            related=related,
        )
        (d / "index.html").write_text(page, encoding="utf-8")

    # --- index page with full FAQPage JSON-LD, instant search & vertical chips ---
    n_vert = sum(1 for v in verticals if any(e["vertical"] == v for e in entries))
    stat = (
        '<div class="stats" aria-label="Statistiche">'
        f'<div class="stat"><b data-to="{len(entries)}">0</b><span>risposte</span></div>'
        '<div class="stat"><b>0</b><span>allucinazioni</span></div>'
        '<div class="stat"><b>&euro;0</b><span>al mese</span></div>'
        f'<div class="stat"><b data-to="{n_vert}">0</b><span>temi</span></div>'
        "</div>"
    )

    chips_html = ""
    for vid, label in verticals.items():
        vcount = sum(1 for e in entries if e["vertical"] == vid)
        if vcount:
            chips_html += f'<button type="button" class="filter-chip" data-v="{vid}">{html.escape(label)} ({vcount})</button>'

    sections = ""
    for vid, label in verticals.items():
        ventries = [e for e in entries if e["vertical"] == vid]
        if not ventries:
            continue
        items = "".join(
            f'<li><a href="{e["slug"]}/">{html.escape(e["question"])}</a></li>'
            for e in ventries
        )
        sections += (
            f'<div class="v-sec" data-v="{vid}">\n'
            f'<h2>{glyph(vid)}<span>{html.escape(label)}</span></h2>\n'
            f"<ul>{items}</ul>\n"
            f"</div>\n"
        )

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
            total=len(entries),
            stats=stat,
            chips=chips_html,
            jsonld=json.dumps(index_jsonld, ensure_ascii=False),
            sections=sections,
        ),
        encoding="utf-8",
    )

    # --- sitemap.xml + robots.txt ---
    urls = [f"{site}/", f"{site}/q/"] + [f"{site}/q/{e['slug']}/" for e in entries]
    sitemap = (
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    )
    sitemap += "".join(f"  <url><loc>{u}</loc></url>\n" for u in urls)
    sitemap += "</urlset>\n"
    (ROOT / "sitemap.xml").write_text(sitemap, encoding="utf-8")
    (ROOT / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\n\nSitemap: {site}/sitemap.xml\n", encoding="utf-8"
    )

    # --- llms.txt: concise map for answer engines (title + url, per vertical) ---
    lt = [
        "# FabGPT-FAQ\n",
        "> FAQ interattiva su cybersecurity, AI, Proxmox, Cloudflare e i progetti "
        "open source di Fabrizio Salmi. Risposte pre-scritte e verificate, ogni "
        "domanda anche come pagina statica citabile.\n",
        f"Chat: {site}/  ·  Indice: {site}/q/\n",
    ]
    for vid, label in verticals.items():
        ventries = [e for e in entries if e["vertical"] == vid]
        if not ventries:
            continue
        lt.append(f"\n## {label}\n")
        for e in ventries:
            lt.append(
                f"- [{e['question']}]({site}/q/{e['slug']}/): {meta_description(e['answers'][0], 120)}"
            )
    (ROOT / "llms.txt").write_text("\n".join(lt) + "\n", encoding="utf-8")

    # --- llms-full.txt: every Q&A as plain text (full corpus for citation) ---
    lf = [
        "# FabGPT-FAQ — knowledge base completa\n",
        "Domande e risposte verificate. Fonte: https://github.com/fabriziosalmi\n",
    ]
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
  .nf { max-width: 620px; margin: 12vh auto; padding: 0 16px; text-align: center; }
  .nf h1 { font-size: 64px; margin: 0; color: var(--accent); }
  .nf p { color: var(--text-dim); }
  .nf a { color: var(--link); text-decoration: none; }
  .nf .actions { margin-top: 24px; display: flex; gap: 12px; justify-content: center; flex-wrap: wrap; }
  .nf .btn { background: var(--accent); color: var(--accent-text); border-radius: 999px; padding: 9px 18px; font-weight: 600; }
  .nf .btn.ghost { background: transparent; color: var(--link); border: 1px solid var(--border); }
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
