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
    # Code spans first, as placeholders: bold/italic must never eat the
    # asterisks inside a backtick span (cron expressions, globs, chmod).
    codes = []

    def _stash(m):
        codes.append(m.group(1))
        return f"@@@CODESPAN_{len(codes) - 1}@@@"

    s = re.sub(r"`([^`]+)`", _stash, s)
    s = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2" target="_blank" rel="noopener">\1</a>', s)
    # internal links: scheme-less relative paths (convention: "q/<slug>/")
    s = re.sub(r"\[([^\]]+)\]\(([^):\s]+)\)", r'<a href="\2">\1</a>', s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"\*([^*\n]+)\*", r"<em>\1</em>", s)
    s = re.sub(r"@@@CODESPAN_(\d+)@@@", lambda m: "<code>" + codes[int(m.group(1))] + "</code>", s)
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


# Feather-style stroke icons (match the vertical glyphs): UI chrome only, no emoji.
_ICON_PATHS = {
    "compass": '<circle cx="12" cy="12" r="10"/><polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76"/>',
    "terminal": '<polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/>',
    "wrench": '<path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/>',
    "plug": '<path d="M12 22v-5"/><path d="M9 8V2"/><path d="M15 8V2"/><path d="M18 8v5a4 4 0 0 1-4 4h-4a4 4 0 0 1-4-4V8Z"/>',
    "chat": '<path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/>',
    "clock": '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
    "check": '<polyline points="20 6 9 17 4 12"/>',
    "book": '<path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>',
    "calc": '<rect x="4" y="2" width="16" height="20" rx="2"/><line x1="8" y1="6" x2="16" y2="6"/><line x1="16" y1="14" x2="16" y2="18"/><line x1="8" y1="10" x2="8" y2="10"/><line x1="12" y1="10" x2="12" y2="10"/><line x1="16" y1="10" x2="16" y2="10"/><line x1="8" y1="14" x2="8" y2="14"/><line x1="12" y1="14" x2="12" y2="14"/><line x1="8" y1="18" x2="8" y2="18"/><line x1="12" y1="18" x2="12" y2="18"/>',
    "lock": '<rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>',
    "key": '<path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4"/>',
    "ticket": '<path d="M2 9a3 3 0 0 1 0 6v2a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-2a3 3 0 0 1 0-6V7a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2z"/><line x1="13" y1="5" x2="13" y2="7"/><line x1="13" y1="11" x2="13" y2="13"/><line x1="13" y1="17" x2="13" y2="19"/>',
    "history": '<path d="M3 3v5h5"/><path d="M3.05 13A9 9 0 1 0 6 5.3L3 8"/><path d="M12 7v5l4 2"/>',
    "globe": '<circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>',
}


def icon(name: str, size: int = 14) -> str:
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" '
            f'style="vertical-align:-2px">{_ICON_PATHS[name]}</svg>')


def section_bar(base: str, active: str = "") -> str:
    items = [("percorsi/", "compass", "Percorsi"), ("comandi/", "terminal", "Comandi"),
             ("tools/", "wrench", "Tools"), ("porta/", "plug", "Porte"), ("q/", "book", "Tutte le domande")]
    links = "".join(
        f'<a href="{base}{href}" title="{label}" aria-label="{label}"'
        + (' class="on" aria-current="page"' if href == active else "")
        + f'>{icon(name, 16)}</a>'
        for href, name, label in items
    )
    return f'<div class="statbar"><nav class="statnav" aria-label="Sezioni">{links}</nav></div>'


def footer(base: str) -> str:
    links = "".join(
        f'<a href="{base}{href}">{label}</a>'
        for href, label in [("", "Chat"), ("percorsi/", "Percorsi"), ("comandi/", "Comandi"),
                            ("tools/", "Tools"), ("porta/", "Porte"), ("q/", "Tutte le domande")]
    )
    return (
        '<footer class="sitefoot"><div class="sitefoot-in">'
        '<span class="sitefoot-brand"><span class="foot-dot">F</span>FabGPT-FAQ '
        '<span class="sitefoot-dim">· risposte verificate, zero allucinazioni</span></span>'
        f'<nav class="sitefoot-nav" aria-label="Mappa del sito">{links}'
        '<a href="https://github.com/fabriziosalmi" target="_blank" rel="noopener">GitHub</a></nav>'
        "</div></footer>"
    )


def close_page(base: str) -> str:
    return "</main>\n" + footer(base) + "\n</body>\n</html>\n"


def path_head(**kw):
    if "sbar" not in kw:
        # the first known section segment in the canonical marks the active pill
        # (robust to the site living at a sub-path or at a bare domain)
        parts = kw["canonical"].split("://", 1)[-1].split("/")
        known = {"percorsi", "comandi", "tools", "porta", "q"}
        active = next((p + "/" for p in parts if p in known), "")
        kw["sbar"] = section_bar(kw["base"], active)
    return PATH_HEAD.format(**kw)


THEME_META = ('<meta name="theme-color" content="#ffffff" media="(prefers-color-scheme: light)">\n'
              '<meta name="theme-color" content="#212121" media="(prefers-color-scheme: dark)">')

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
<meta name="theme-color" content="#ffffff" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#212121" media="(prefers-color-scheme: dark)">
<script type="application/ld+json">{jsonld}</script>
<style>
  .page {{ max-width: 768px; margin: 0 auto; padding: 24px 16px 48px; }}
  .page h1 {{ font-size: clamp(22px, 4.5vw, 27px); line-height: 1.25; letter-spacing: -0.01em; margin: 6px 0 10px; }}
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
  .page .ask {{ display: inline-block; background: var(--accent); color: var(--accent-text); border-radius: 999px; padding: 8px 16px; text-decoration: none; font-weight: 600; font-size: 13px; transition: background var(--t); }}
  .page .ask:hover {{ background: var(--link); }}
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
  <nav class="topnav"><a href="{base}" title="Chat interattiva" aria-label="Chat interattiva"><svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/></svg></a></nav>
</header>
{sbar}
<main class="page">
  <article itemscope itemtype="https://schema.org/TechArticle">
    <nav class="crumbs" aria-label="Percorso"><a href="{base}">FabGPT-FAQ</a> › <a href="{base}q/">Tutte le domande</a> › <span itemprop="articleSection">{vertical}</span></nav>
    <h1 id="page-question" itemprop="headline">{question}</h1>
    <div class="page-meta">
      <span class="page-meta-badge vert">{glyph_svg} <span>{vertical}</span></span>
      <span class="page-meta-badge">{ic_clock} {reading_time} min lettura</span>
      <span class="page-meta-badge">{ic_check} Runbook verificato</span>
    </div>
    {toolbanner}
    <div class="answer" id="page-answer" itemprop="articleBody">{answer}</div>
    <div class="qa-actions">
      <button type="button" class="copy-qa-btn" id="copy-page-btn" aria-label="Copia domanda e risposta">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
        <span>Copia Q&A</span>
      </button>
      <a class="ask" href="{base}?q={id}">{ic_chat} Apri nella chat interattiva</a>
    </div>
    {page_nav}
    <section class="ask-box">
      <div class="ask-box-header">
        <span class="ask-box-icon" aria-hidden="true"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/></svg></span>
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
{foot}
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
<meta name="theme-color" content="#ffffff" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#212121" media="(prefers-color-scheme: dark)">
<script type="application/ld+json">{jsonld}</script>
<style>
  .page {{ max-width: 768px; margin: 0 auto; padding: 24px 16px 48px; }}
  .page h1 {{ font-size: clamp(22px, 4.5vw, 27px); letter-spacing: -0.01em; margin: 8px 0 8px; }}
  .page h2 {{ font-size: 15px; color: var(--text-dim); text-transform: uppercase; letter-spacing: 0.06em; margin: 28px 0 8px; }}
  .page a {{ color: var(--link); text-decoration: none; }}
  .page a:hover {{ text-decoration: underline; }}
  .page li {{ margin: 7px 0; }}
  .page .intro {{ color: var(--text-dim); margin-bottom: 12px; }}
  .page h2 {{ display: flex; align-items: center; gap: 8px; }}
  .page h2 .glyph {{ flex: 0 0 auto; }}

  @media (prefers-reduced-motion: no-preference) {{ .glyph {{ animation: glyph-in .5s ease both; }} }}
  @keyframes glyph-in {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}
  .paths-strip {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 10px; margin: 4px 0 20px; }}
  .path-card {{ display: block; border: 1px solid var(--border); border-radius: var(--r-md); background: var(--bg-raised); box-shadow: var(--elev); padding: 12px 14px; text-decoration: none; color: inherit; transition: border-color var(--t); }}
  .path-card:hover {{ border-color: var(--accent); text-decoration: none; }}
  .path-card b {{ color: var(--link); }}
  .path-card p {{ margin: 4px 0 0; font-size: 13px; color: var(--text-dim); }}
  .path-card .n {{ font-size: 11px; color: var(--text-dim); text-transform: uppercase; letter-spacing: .05em; }}
</style>
</head>
<body>
<header class="topbar">
  <a class="brand" href="../" style="text-decoration:none;color:inherit">
    <span class="brand-dot">F</span>
    <span class="brand-name">FabGPT-FAQ</span>
  </a>
  <nav class="topnav"><a href="../" title="Chat interattiva" aria-label="Chat interattiva"><svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/></svg></a></nav>
</header>
{sbar}
<main class="page">
  <h1>Tutte le domande</h1>
  <p class="intro">La knowledge base completa di FabGPT-FAQ: cybersecurity, AI, Proxmox, Cloudflare e i progetti open source di Fabrizio Salmi. Cerca in tempo reale o <a href="../">chiedi in chat</a>.</p>
  {percorsi}
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
{foot}
<script>
(function(){{
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


PATH_HEAD = """<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} – FabGPT-FAQ</title>
<meta name="description" content="{description}">
<meta name="robots" content="index,follow,max-image-preview:large">
<link rel="canonical" href="{canonical}">
<meta property="og:type" content="article">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{description}">
<meta property="og:url" content="{canonical}">
<meta property="og:image" content="{site}/og.svg">
<meta property="og:site_name" content="FabGPT-FAQ">
<meta property="og:locale" content="it_IT">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:image" content="{site}/og.svg">
<link rel="stylesheet" href="{base}style.css">
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><circle cx='50' cy='50' r='45' fill='%2310a37f'/><text x='50' y='68' font-size='52' text-anchor='middle' fill='white' font-family='sans-serif'>F</text></svg>">
<meta name="theme-color" content="#ffffff" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#212121" media="(prefers-color-scheme: dark)">
<script type="application/ld+json">{jsonld}</script>
<style>
  .page {{ max-width: 768px; margin: 0 auto; padding: 24px 16px 48px; }}
  .page h1 {{ font-size: clamp(22px, 4.5vw, 27px); line-height: 1.25; letter-spacing: -0.01em; margin: 6px 0 10px; }}
  .crumbs {{ font-size: 13px; color: var(--text-dim); margin-bottom: 6px; }}
  .crumbs a {{ color: var(--text-dim); text-decoration: none; }}
  .crumbs a:hover {{ color: var(--text); }}
  .page .intro {{ color: var(--text-dim); margin-bottom: 20px; }}
  .steps {{ list-style: none; counter-reset: step; padding: 0; margin: 0; }}
  .steps li {{ counter-increment: step; position: relative; padding: 14px 16px 14px 56px; border: 1px solid var(--border); border-radius: var(--r-md); background: var(--bg-raised); box-shadow: var(--elev); margin: 10px 0; }}
  .steps li::before {{ content: counter(step); position: absolute; left: 16px; top: 16px; width: 26px; height: 26px; border-radius: 50%; background: var(--accent); color: var(--accent-text); font-weight: 700; font-size: 13px; display: flex; align-items: center; justify-content: center; }}
  .steps a {{ color: var(--link); text-decoration: none; font-weight: 600; }}
  .steps a:hover {{ text-decoration: underline; }}
  .steps p {{ margin: 4px 0 0; font-size: 14px; color: var(--text-dim); }}
  .step-check {{ position: absolute; right: 14px; top: 16px; width: 18px; height: 18px; accent-color: var(--accent); cursor: pointer; }}
  .steps li {{ padding-right: 44px; }}
  .steps li.done {{ opacity: .55; }}
  .steps li.done a {{ text-decoration: line-through; }}
  .prog {{ display: flex; align-items: center; gap: 12px; margin: 4px 0 16px; }}
  .prog-track {{ flex: 1; height: 6px; border-radius: 999px; background: var(--bg-soft); border: 1px solid var(--border); overflow: hidden; }}
  .prog-fill {{ display: block; height: 100%; width: 0; background: var(--accent); border-radius: 999px; transition: width .25s ease; }}
  .prog-txt {{ font-size: 13px; color: var(--text-dim); white-space: nowrap; }}
  .prog-reset {{ font-size: 12px; color: var(--text-dim); background: none; border: none; cursor: pointer; text-decoration: underline; padding: 0; }}
  .path-prog {{ margin: 6px 0 0 !important; font-size: 12.5px !important; color: var(--accent) !important; font-weight: 600; }}
  .path-card {{ display: block; border: 1px solid var(--border); border-radius: var(--r-md); background: var(--bg-raised); box-shadow: var(--elev); padding: 16px 18px; margin: 12px 0; text-decoration: none; color: inherit; transition: border-color var(--t); }}
  .path-card:hover {{ border-color: var(--accent); }}
  .path-card b {{ color: var(--link); font-size: 17px; }}
  .path-card p {{ margin: 6px 0 0; font-size: 14px; color: var(--text-dim); }}
  .path-card .n {{ font-size: 12px; color: var(--text-dim); text-transform: uppercase; letter-spacing: .05em; }}
  .page .ask {{ display: inline-block; background: var(--accent); color: var(--accent-text); border-radius: 999px; padding: 8px 16px; text-decoration: none; font-weight: 600; font-size: 13px; margin-top: 20px; transition: background var(--t); }}
  .page .ask:hover {{ background: var(--link); }}
</style>
</head>
<body>
<header class="topbar">
  <a class="brand" href="{base}" style="text-decoration:none;color:inherit">
    <span class="brand-dot">F</span>
    <span class="brand-name">FabGPT-FAQ</span>
  </a>
  <nav class="topnav"><a href="{base}" title="Chat interattiva" aria-label="Chat interattiva"><svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/></svg></a></nav>
</header>
{sbar}
<main class="page">
"""

PATH_FOOT = """</main>
</body>
</html>
"""


def build_paths(db, entries, site) -> list:
    """Render /percorsi/ (index + one page per guided path). Returns URLs added."""
    pfile = ROOT / "paths.json"
    if not pfile.exists():
        return []
    paths = json.loads(pfile.read_text(encoding="utf-8"))["paths"]
    by_id = {e["id"]: e for e in entries}
    for p in paths:
        for s in p["steps"]:
            assert s["entry"] in by_id, f"paths.json: unknown entry id '{s['entry']}'"

    urls = [f"{site}/percorsi/"]
    # per-path pages
    for p in paths:
        steps_html = ""
        for s in p["steps"]:
            e = by_id[s["entry"]]
            steps_html += (
                f'<li data-slug="{e["slug"]}">'
                f'<input type="checkbox" class="step-check" aria-label="Segna tappa completata">'
                f'<a href="../../q/{e["slug"]}/">{html.escape(e["question"])}</a>'
                f"<p>{inline_md(html.escape(s['why']))}</p></li>\n"
            )
        jsonld = [
            {
                "@context": "https://schema.org",
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {"@type": "ListItem", "position": 1, "name": "FabGPT-FAQ", "item": f"{site}/"},
                    {"@type": "ListItem", "position": 2, "name": "Percorsi", "item": f"{site}/percorsi/"},
                    {"@type": "ListItem", "position": 3, "name": p["title"], "item": f"{site}/percorsi/{p['slug']}/"},
                ],
            },
            {
                "@context": "https://schema.org",
                "@type": "ItemList",
                "name": p["title"],
                "description": p["tagline"],
                "itemListOrder": "https://schema.org/ItemListOrderAscending",
                "itemListElement": [
                    {
                        "@type": "ListItem",
                        "position": i + 1,
                        "name": by_id[s["entry"]]["question"],
                        "url": f"{site}/q/{by_id[s['entry']]['slug']}/",
                    }
                    for i, s in enumerate(p["steps"])
                ],
            },
        ]
        page = path_head(
            title=html.escape(p["title"]),
            description=html.escape(p["tagline"]),
            canonical=f"{site}/percorsi/{p['slug']}/",
            site=site,
            base="../../",
            jsonld=json.dumps(jsonld, ensure_ascii=False),
        )
        page += (
            f'<nav class="crumbs" aria-label="Percorso"><a href="../../">FabGPT-FAQ</a> › '
            f'<a href="../">Percorsi</a> › <span>{html.escape(p["title"])}</span></nav>\n'
            f"<h1>{html.escape(p['title'])}</h1>\n"
            f'<p class="intro">{inline_md(html.escape(p["intro"]))}</p>\n'
            f'<div class="prog" hidden><div class="prog-track"><span class="prog-fill" id="prog-fill"></span></div>'
            f'<span class="prog-txt" id="prog-txt"></span>'
            f'<button type="button" id="prog-reset" class="prog-reset" aria-label="Azzera il progresso">azzera</button></div>\n'
            f'<ol class="steps" id="steps">\n{steps_html}</ol>\n'
            f'<a class="ask" href="../../">{icon("chat")} Chiedi in chat</a>\n'
        )
        page += """<script>
(function () {
  var KEY = 'fabgpt-percorso-""" + p["slug"] + """';
  var items = Array.prototype.slice.call(document.querySelectorAll('#steps li'));
  var wrap = document.querySelector('.prog');
  var done;
  try { done = new Set(JSON.parse(localStorage.getItem(KEY) || '[]')); } catch (e) { return; }
  wrap.hidden = false;
  function save() {
    try { localStorage.setItem(KEY, JSON.stringify(Array.from(done))); } catch (e) {}
  }
  function render() {
    items.forEach(function (li) {
      var on = done.has(li.getAttribute('data-slug'));
      li.querySelector('.step-check').checked = on;
      li.classList.toggle('done', on);
    });
    var n = items.filter(function (li) { return done.has(li.getAttribute('data-slug')); }).length;
    document.getElementById('prog-fill').style.width = (100 * n / items.length) + '%';
    document.getElementById('prog-txt').textContent = n + '/' + items.length + ' tappe' + (n === items.length ? ' – percorso completato!' : ' completate');
  }
  items.forEach(function (li) {
    li.querySelector('.step-check').addEventListener('change', function () {
      var slug = li.getAttribute('data-slug');
      if (this.checked) done.add(slug); else done.delete(slug);
      save(); render();
    });
  });
  document.getElementById('prog-reset').addEventListener('click', function () {
    if (!done.size) return;
    done.clear(); save(); render();
  });
  render();
})();
</script>
"""
        page += close_page("../../")
        d = ROOT / "percorsi" / p["slug"]
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(page, encoding="utf-8")
        urls.append(f"{site}/percorsi/{p['slug']}/")

    # percorsi index
    cards = ""
    for p in paths:
        cards += (
            f'<a class="path-card" href="{p["slug"]}/" data-slug="{p["slug"]}" data-steps="{len(p["steps"])}">'
            f'<span class="n">{len(p["steps"])} tappe</span><br>'
            f"<b>{html.escape(p['title'])}</b><p>{html.escape(p['tagline'])}</p>"
            f'<p class="path-prog" hidden></p></a>\n'
        )
    jsonld = {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "name": "Percorsi guidati FabGPT-FAQ",
        "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": p["title"], "url": f"{site}/percorsi/{p['slug']}/"}
            for i, p in enumerate(paths)
        ],
    }
    page = path_head(
        title="Percorsi guidati",
        description="Le guide di FabGPT-FAQ in sequenza: diventare sysadmin, mettere in sicurezza un server, self-hosting da zero.",
        canonical=f"{site}/percorsi/",
        site=site,
        base="../",
        jsonld=json.dumps(jsonld, ensure_ascii=False),
    )
    page += (
        '<nav class="crumbs" aria-label="Percorso"><a href="../">FabGPT-FAQ</a> › <span>Percorsi</span></nav>\n'
        "<h1>Percorsi guidati</h1>\n"
        '<p class="intro">Le stesse risposte verificate della knowledge base, messe in fila nell\'ordine giusto: ogni percorso è una strada completa, tappa per tappa. Il progresso resta salvato nel tuo browser.</p>\n'
        + cards
    )
    page += """<script>
(function () {
  document.querySelectorAll('.path-card').forEach(function (card) {
    var n;
    try { n = JSON.parse(localStorage.getItem('fabgpt-percorso-' + card.getAttribute('data-slug')) || '[]').length; }
    catch (e) { return; }
    if (!n) return;
    var tot = +card.getAttribute('data-steps');
    var el = card.querySelector('.path-prog');
    el.textContent = n >= tot ? '✓ Completato' : n + '/' + tot + ' tappe completate';
    el.hidden = false;
  });
})();
</script>
"""
    page += close_page("../")
    d = ROOT / "percorsi"
    d.mkdir(parents=True, exist_ok=True)
    (d / "index.html").write_text(page, encoding="utf-8")
    return urls


TOOL_MD_RENDERER = """
function miniMd(md) {
  var esc = md.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  var blocks = esc.split(/```(\\w*)\\n([\\s\\S]*?)```/g);
  var out = '';
  for (var i = 0; i < blocks.length; i += 3) {
    var t = blocks[i]
      .replace(/\\*\\*([^*]+)\\*\\*/g, '<b>$1</b>')
      .replace(/`([^`]+)`/g, '<code>$1</code>')
      .replace(/^- (.*)$/gm, '<li>$1</li>')
      .replace(/(<li>[\\s\\S]*<\\/li>)/, '<ul>$1</ul>')
      .replace(/\\n\\n/g, '<br><br>');
    out += t;
    if (i + 2 < blocks.length) out += '<pre><code>' + blocks[i + 2] + '</code></pre>';
  }
  return out;
}
"""

TOOLS = [
    {
        "slug": "calcolatore-subnet", "fn": "subnet", "icon": "calc",
        "title": "Calcolatore subnet / CIDR",
        "tagline": "Rete, broadcast, maschera e host usabili da una notazione CIDR. Calcolo esatto nel browser, niente server.",
        "placeholder": "192.168.1.0/26",
        "examples": ["192.168.1.0/24", "10.0.0.130/26", "172.16.0.0/12", "10.0.0.0/31"],
        "related": ["cos-e-il-subnetting-e-il-cidr", "segmentare-la-rete-con-vlan", "nat-statico-dinamico-e-pat", "differenza-ipv4-e-ipv6"],
    },
    {
        "slug": "spiega-cron", "fn": "cron", "icon": "clock",
        "title": "Spiega-cron",
        "tagline": "Incolla un'espressione cron e leggila in italiano, campo per campo, con le trappole segnalate.",
        "placeholder": "*/5 2 * * 1-5",
        "examples": ["*/5 * * * *", "0 3 * * *", "0 9 * * 1-5", "@reboot", "0 3 1 * 1"],
        "related": ["cron-la-sintassi-spiegata", "gestire-servizi-linux-con-systemctl", "bash-scripting-le-basi-che-servono"],
    },
    {
        "slug": "calcolatore-chmod", "fn": "chmod", "icon": "lock",
        "title": "Calcolatore chmod",
        "tagline": "Da ottale a rwx e ritorno, bit speciali inclusi. Con gli avvisi che contano (777, 600).",
        "placeholder": "754 oppure rwxr-xr--",
        "examples": ["755", "644", "600", "777", "4755", "rwxr-xr--"],
        "related": ["permessi-linux-chmod-chown-umask", "utenti-gruppi-e-sudo-su-linux", "come-funzionano-le-chiavi-ssh"],
    },
    {
        "slug": "decodifica-jwt", "fn": "jwt", "icon": "ticket",
        "title": "Decodifica JWT",
        "tagline": "Header e payload di un JSON Web Token, decodificati in locale: il token non lascia mai il tuo browser.",
        "placeholder": "eyJhbGciOi...",
        "examples": ["eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"],
        "related": ["oauth2-proxy-autenticazione-davanti-ai-servizi", "vulnerabilita-nei-redirect-oauth", "come-gestire-i-secrets"],
    },
    {
        "slug": "timestamp-unix", "fn": "epoch", "icon": "history",
        "title": "Convertitore timestamp Unix",
        "tagline": "Da epoch (secondi o millisecondi) a data leggibile, con i comandi da terminale equivalenti.",
        "placeholder": "1609459200",
        "examples": ["1609459200", "1725167999", "1609459200000"],
        "related": ["dove-sono-i-log-su-linux", "cron-la-sintassi-spiegata", "security-logging-fatto-bene"],
    },
    {
        "slug": "dns-lookup", "fn": "custom", "icon": "globe",
        "title": "Lookup DNS live",
        "tagline": "Interroga in parallelo i resolver DoH di Cloudflare e Google e confronta le risposte: il test di propagazione in un click.",
        "related": ["tipi-di-record-dns", "diagnosticare-la-propagazione-dns", "cos-e-il-ttl-dns", "come-funziona-la-risoluzione-dns", "cos-e-doh-dns-over-https"],
        "custom_html": """<div class="tool-box">
  <div style="display:flex;gap:8px;flex-wrap:wrap">
    <input id="dns-name" type="text" placeholder="example.com" autocomplete="off" spellcheck="false" style="flex:1;min-width:180px" aria-label="Dominio">
    <select id="dns-type" aria-label="Tipo di record">
      <option>A</option><option>AAAA</option><option>CNAME</option><option>MX</option><option>TXT</option><option>NS</option><option>SOA</option><option>CAA</option>
    </select>
    <button id="dns-go" class="ask" style="margin:0">Interroga</button>
  </div>
  <p class="tool-privacy">Le query partono dal <b>tuo browser</b> verso <code>cloudflare-dns.com</code> e <code>dns.google</code> in DNS-over-HTTPS: questo sito non vede né registra nulla.</p>
  <div id="tool-out" class="tool-out" aria-live="polite"><p class="tool-empty">Record, TTL e confronto tra i due resolver appaiono qui.</p></div>
</div>""",
        "custom_js": """(function () {
  var out = document.getElementById('tool-out');
  var nameEl = document.getElementById('dns-name');
  function esc(s) { return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
  async function ask(resolver, name, type) {
    var url = resolver === 'Cloudflare'
      ? 'https://cloudflare-dns.com/dns-query?name=' + encodeURIComponent(name) + '&type=' + type
      : 'https://dns.google/resolve?name=' + encodeURIComponent(name) + '&type=' + type;
    var opt = resolver === 'Cloudflare' ? { headers: { Accept: 'application/dns-json' } } : {};
    var r = await fetch(url, opt);
    if (!r.ok) throw new Error(resolver + ' HTTP ' + r.status);
    return r.json();
  }
  function block(resolver, data) {
    var h = '<h3>' + resolver + '</h3>';
    if (data.Status === 3) return h + '<p>NXDOMAIN – il dominio non esiste per questo resolver.</p>';
    if (data.Status !== 0) return h + '<p>Errore DNS (Status ' + esc(data.Status) + ').</p>';
    var ans = data.Answer || [];
    if (!ans.length) return h + '<p>Nessun record di questo tipo (NOERROR ma risposta vuota).</p>';
    return h + '<table><tr><th>Record</th><th>TTL</th><th>Valore</th></tr>' + ans.map(function (a) {
      return '<tr><td>' + esc(a.name) + '</td><td>' + esc(a.TTL) + 's</td><td><code>' + esc(a.data) + '</code></td></tr>';
    }).join('') + '</table>';
  }
  function values(data) {
    return (data.Answer || []).map(function (a) { return a.data; }).sort().join('|');
  }
  async function run() {
    var name = nameEl.value.trim().replace(/^https?:\\/\\//, '').replace(/\\/.*$/, '');
    var type = document.getElementById('dns-type').value;
    if (!name) return;
    out.innerHTML = '<p class="tool-wait">Interrogo Cloudflare e Google in parallelo…</p>';
    try {
      var res = await Promise.all([ask('Cloudflare', name, type), ask('Google', name, type)]);
      var same = values(res[0]) === values(res[1]);
      var badge = same
        ? '<p class="dns-ok">✓ I due resolver rispondono allo stesso modo.</p>'
        : '<p class="dns-diff">⚠️ Risposte diverse: propagazione in corso, oppure split DNS / geo-DNS.</p>';
      out.innerHTML = badge + block('Cloudflare (1.1.1.1)', res[0]) + block('Google (8.8.8.8)', res[1]);
    } catch (e) {
      out.innerHTML = '<p>Impossibile interrogare i resolver (' + esc(e.message) + '). Sei offline, o un firewall blocca il DoH.</p>';
    }
  }
  document.getElementById('dns-go').addEventListener('click', run);
  nameEl.addEventListener('keydown', function (e) { if (e.key === 'Enter') run(); });
})();""",
    },
    {
        "slug": "password-compromessa", "fn": "custom", "icon": "key",
        "title": "Check password compromessa",
        "tagline": "Verifica se una password è nei data breach noti (Have I Been Pwned) con k-anonymity: la password non lascia mai il browser.",
        "related": ["verificare-password-compromessa", "perche-usare-un-password-manager", "cosa-sono-le-passkey", "cos-e-autenticazione-due-fattori-mfa", "cos-e-un-infostealer"],
        "custom_html": """<div class="tool-box">
  <div style="display:flex;gap:8px;flex-wrap:wrap">
    <input id="pw-in" type="password" placeholder="La password da verificare" autocomplete="off" style="flex:1;min-width:200px" aria-label="Password da verificare">
    <button id="pw-go" class="ask" style="margin:0">Verifica</button>
  </div>
  <p class="tool-privacy">Come funziona (k-anonymity): il browser calcola l'hash SHA-1 in locale e invia a <code>api.pwnedpasswords.com</code> <b>solo i primi 5 caratteri</b> dell'hash. La risposta contiene centinaia di suffissi e il confronto avviene qui: né la password né il suo hash completo lasciano mai il tuo computer.</p>
  <div id="tool-out" class="tool-out" aria-live="polite"><p class="tool-empty">Il verdetto appare qui: la password non lascia mai questo browser.</p></div>
</div>""",
        "custom_js": """(function () {
  var out = document.getElementById('tool-out');
  var inEl = document.getElementById('pw-in');
  async function run() {
    var pw = inEl.value;
    if (!pw) return;
    if (!window.crypto || !crypto.subtle) {
      out.innerHTML = '<p>Il browser non espone WebCrypto (serve HTTPS o localhost).</p>';
      return;
    }
    out.innerHTML = '<p class="tool-wait">Hash SHA-1 calcolato in locale, interrogo HIBP col prefisso…</p>';
    try {
      var buf = await crypto.subtle.digest('SHA-1', new TextEncoder().encode(pw));
      var hex = Array.from(new Uint8Array(buf)).map(function (b) { return b.toString(16).padStart(2, '0'); }).join('').toUpperCase();
      var prefix = hex.slice(0, 5), suffix = hex.slice(5);
      var r = await fetch('https://api.pwnedpasswords.com/range/' + prefix, { headers: { 'Add-Padding': 'true' } });
      if (!r.ok) throw new Error('HTTP ' + r.status);
      var count = 0;
      r.headers && null;
      (await r.text()).split('\\n').some(function (line) {
        var p = line.trim().split(':');
        if (p[0] === suffix) { count = parseInt(p[1], 10) || 0; return true; }
        return false;
      });
      if (count > 0) {
        out.innerHTML = '<p class="dns-diff">⚠️ <b>Compromessa</b>: questa password compare <b>' + count.toLocaleString('it-IT') +
          '</b> volte nei data breach noti. Va cambiata OVUNQUE tu la usi, subito – e mai più riusata.</p>' +
          '<p>Il passo giusto: una password unica per servizio dentro un password manager, e MFA dove possibile.</p>';
      } else {
        out.innerHTML = '<p class="dns-ok">✓ Non presente nei breach noti a Have I Been Pwned.</p>' +
          '<p>Non significa "sicura per sempre": significa solo che non è ancora in una lista pubblica. Le regole non cambiano: unica per servizio, lunga, in un password manager.</p>';
      }
    } catch (e) {
      out.innerHTML = '<p>Verifica non riuscita (' + String(e.message).replace(/</g, '&lt;') + '). Sei offline?</p>';
    }
  }
  document.getElementById('pw-go').addEventListener('click', run);
  inEl.addEventListener('keydown', function (e) { if (e.key === 'Enter') run(); });
})();""",
    },
]

# entry id -> (relative url from q/<slug>/, banner label)
TOOL_BANNERS = {
    "subnetting-cidr": ("../../tools/calcolatore-subnet/", "calc", "Prova il calcolatore subnet interattivo"),
    "cron-sintassi": ("../../tools/spiega-cron/", "clock", "Incolla la tua espressione nello spiega-cron"),
    "permessi-linux": ("../../tools/calcolatore-chmod/", "lock", "Prova il calcolatore chmod interattivo"),
    "porte-tcp-udp": ("../../porta/", "plug", "Le porte well-known, una per una: rischi e comandi"),
    "dhcp": ("../../tools/calcolatore-subnet/", "calc", "Calcola le tue subnet col calcolatore CIDR"),
    "log-linux": ("../../tools/timestamp-unix/", "history", "Converti un timestamp Unix dei log"),
}


def build_tools(db, entries, site) -> list:
    """Render /tools/ (index + one interactive page per micro-tool)."""
    by_id = {e["id"]: e for e in entries}
    urls = [f"{site}/tools/"]
    for t in TOOLS:
        for r in t["related"]:
            assert any(e["slug"] == r for e in entries), f"tools: unknown slug {r}"
    for t in TOOLS:
        related = "".join(
            f'<li><a href="../../q/{r}/">{html.escape(next(e["question"] for e in entries if e["slug"] == r))}</a></li>'
            for r in t["related"]
        )
        examples = "".join(
            f'<button type="button" class="ex" data-v="{html.escape(x)}">{html.escape(x if len(x) < 28 else x[:25] + "…")}</button>'
            for x in t.get("examples", [])
        )
        jsonld = [
            {
                "@context": "https://schema.org",
                "@type": "WebApplication",
                "name": t["title"],
                "url": f"{site}/tools/{t['slug']}/",
                "applicationCategory": "DeveloperApplication",
                "operatingSystem": "Any (browser)",
                "description": t["tagline"],
                "offers": {"@type": "Offer", "price": "0", "priceCurrency": "EUR"},
            },
            {
                "@context": "https://schema.org",
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {"@type": "ListItem", "position": 1, "name": "FabGPT-FAQ", "item": f"{site}/"},
                    {"@type": "ListItem", "position": 2, "name": "Tools", "item": f"{site}/tools/"},
                    {"@type": "ListItem", "position": 3, "name": t["title"], "item": f"{site}/tools/{t['slug']}/"},
                ],
            },
        ]
        page = path_head(
            title=html.escape(t["title"]),
            description=html.escape(t["tagline"]),
            canonical=f"{site}/tools/{t['slug']}/",
            site=site,
            base="../../",
            jsonld=json.dumps(jsonld, ensure_ascii=False),
        )
        if "custom_html" in t:
            intro = html.escape(t["tagline"])
            body = t["custom_html"]
            script = "<script>\n" + t["custom_js"] + "\n</script>"
        else:
            intro = html.escape(t["tagline"]) + " Tutto gira in locale: <b>nessun dato lascia il browser</b>."
            body = f"""<div class="tool-box">
  <input id="tool-in" type="text" placeholder="{html.escape(t["placeholder"])}" autocomplete="off" spellcheck="false" aria-label="Input dello strumento">
  <div class="tool-ex">{examples}</div>
  <div id="tool-out" class="tool-out" aria-live="polite"><p class="tool-empty">Il risultato appare qui, calcolato in locale – digita o tocca un esempio.</p></div>
</div>"""
            script = f"""<script src="../../tools.js"></script>
<script>
{TOOL_MD_RENDERER}
(function () {{
  var input = document.getElementById('tool-in');
  var out = document.getElementById('tool-out');
  var FN = '{t["fn"]}';
  function run() {{
    var v = input.value.trim();
    if (!v) {{ out.innerHTML = '<p class="tool-empty">Il risultato appare qui, calcolato in locale – digita o tocca un esempio.</p>'; return; }}
    var md = null;
    try {{
      if (FN === 'subnet') {{
        var m = v.match(/^(\\d{{1,3}}(?:\\.\\d{{1,3}}){{3}})\\/(\\d{{1,2}})$/);
        if (m) {{ var i = FabTools.subnetInfo(m[1], +m[2]); md = i && FabTools.subnetMd(i); }}
      }} else if (FN === 'cron') md = FabTools.explainCron(v);
      else if (FN === 'chmod') md = FabTools.explainChmod(v);
      else if (FN === 'jwt') md = FabTools.decodeJwt(v);
      else if (FN === 'epoch') md = FabTools.explainEpoch(v);
    }} catch (e) {{ md = null; }}
    out.innerHTML = md ? miniMd(md) : '<p style="color:var(--text-dim)">Input non riconosciuto: prova uno degli esempi qui sopra.</p>';
  }}
  input.addEventListener('input', run);
  document.querySelectorAll('.tool-ex .ex').forEach(function (b) {{
    b.addEventListener('click', function () {{ input.value = b.getAttribute('data-v'); run(); input.focus(); }});
  }});
}})();
</script>"""
        page += f"""<nav class="crumbs" aria-label="Percorso"><a href="../../">FabGPT-FAQ</a> › <a href="../">Tools</a> › <span>{html.escape(t["title"])}</span></nav>
<h1>{icon(t["icon"], 20)} {html.escape(t["title"])}</h1>
<p class="intro">{intro}</p>
{body}
<div class="related"><h2>Guide correlate</h2><ul>{related}</ul></div>
<a class="ask" href="../../">{icon("chat")} Chiedi in chat</a>
<style>
  .tool-box {{ border: 1px solid var(--border); border-radius: var(--r-md); background: var(--bg-raised); box-shadow: var(--elev); padding: 16px; }}
  .tool-box input {{ width: 100%; box-sizing: border-box; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 15px; padding: 10px 12px; border: 1px solid var(--border); border-radius: var(--r-sm); background: var(--bg); color: var(--text); transition: border-color var(--t), box-shadow var(--t); }}
  .tool-box input:focus {{ outline: none; border-color: var(--accent); box-shadow: var(--ring); }}
  .tool-ex {{ margin-top: 10px; display: flex; flex-wrap: wrap; gap: 6px; }}
  .tool-ex .ex {{ font-family: ui-monospace, Menlo, monospace; font-size: 12px; padding: 4px 10px; border: 1px solid var(--border); border-radius: 999px; background: var(--bg); color: var(--text-dim); cursor: pointer; }}
  .tool-ex .ex:hover {{ border-color: var(--accent); color: var(--text); }}
  .tool-out {{ margin-top: 14px; font-size: 14.5px; line-height: 1.55; }}
  .tool-out:empty {{ display: none; }}
  .tool-out code {{ background: var(--code-bg); border-radius: 5px; padding: 1px 5px; font-family: ui-monospace, Menlo, monospace; font-size: .9em; }}
  .tool-out pre {{ background: var(--code-bg); border-radius: 8px; padding: 10px 12px; overflow-x: auto; }}
  .tool-out ul {{ padding-left: 20px; }}
  .related {{ margin-top: 28px; border-top: 1px solid var(--border); padding-top: 16px; }}
  .related h2 {{ font-size: 16px; margin-bottom: 10px; }}
  .related a {{ color: var(--link); text-decoration: none; }}
  .related a:hover {{ text-decoration: underline; }}
  .tool-box select, .tool-box button.ask {{ font-family: inherit; font-size: 14px; padding: 8px 14px; border: 1px solid var(--border); border-radius: 8px; background: var(--bg); color: var(--text); cursor: pointer; }}
  .tool-box button.ask {{ background: var(--accent); color: var(--accent-text); border-color: var(--accent); font-weight: 600; }}
  .tool-privacy {{ font-size: 12.5px; color: var(--text-dim); margin: 10px 0 0; }}
  .tool-privacy code {{ background: var(--code-bg); border-radius: 4px; padding: 0 4px; }}
  .tool-out h3 {{ font-size: 15px; margin: 14px 0 6px; }}
  .tool-out table {{ border-collapse: collapse; width: 100%; font-size: 13.5px; }}
  .tool-out th, .tool-out td {{ text-align: left; padding: 5px 8px; border-bottom: 1px solid var(--border); overflow-wrap: anywhere; }}
  .dns-ok {{ color: var(--accent); font-weight: 600; }}
  .dns-diff {{ font-weight: 600; }}
</style>
{script}
"""
        page += close_page("../../")
        d = ROOT / "tools" / t["slug"]
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(page, encoding="utf-8")
        urls.append(f"{site}/tools/{t['slug']}/")

    # tools index
    cards = "".join(
        f'<a class="path-card" href="{t["slug"]}/"><b>{icon(t["icon"])} {html.escape(t["title"])}</b>'
        f"<p>{html.escape(t['tagline'])}</p></a>\n"
        for t in TOOLS
    )
    page = path_head(
        title="Tools deterministici",
        description="Micro-strumenti che calcolano nel browser, senza server e senza AI: subnet, cron, chmod, JWT, timestamp.",
        canonical=f"{site}/tools/",
        site=site,
        base="../",
        jsonld=json.dumps({
            "@context": "https://schema.org", "@type": "ItemList",
            "name": "Tools FabGPT-FAQ",
            "itemListElement": [
                {"@type": "ListItem", "position": i + 1, "name": t["title"], "url": f"{site}/tools/{t['slug']}/"}
                for i, t in enumerate(TOOLS)
            ],
        }, ensure_ascii=False),
    )
    page += (
        '<nav class="crumbs" aria-label="Percorso"><a href="../">FabGPT-FAQ</a> › <span>Tools</span></nav>\n'
        "<h1>Tools deterministici</h1>\n"
        '<p class="intro">Strumenti che <b>calcolano</b>, non generano: il risultato è esatto per costruzione, gira nel tuo browser e non tocca nessun server. Gli stessi motori rispondono anche in <a href="../">chat</a>: incolla una CIDR, un cron o un JWT e vedi.</p>\n'
        + cards
    )
    page += close_page("../")
    (ROOT / "tools").mkdir(parents=True, exist_ok=True)
    (ROOT / "tools" / "index.html").write_text(page, encoding="utf-8")
    return urls


def build_ports(db, entries, site) -> list:
    """Render /porta/ (index + one page per well-known port from ports.json)."""
    pfile = ROOT / "ports.json"
    if not pfile.exists():
        return []
    ports = json.loads(pfile.read_text(encoding="utf-8"))["ports"]
    by_slug = {e["slug"]: e for e in entries}
    for p in ports.values():
        for s in p["suggest"]:
            assert s in by_slug, f"ports.json: unknown slug {s}"
    ordered = sorted(ports.values(), key=lambda p: p["port"])
    urls = [f"{site}/porta/"]
    for p in ordered:
        n = p["port"]
        proto = "TCP e UDP" if p["proto"] == "both" else p["proto"].upper()
        title = f"Porta {n} ({p['service']}): a cosa serve e come si protegge"
        related = "".join(
            f'<li><a href="../../q/{s}/">{html.escape(by_slug[s]["question"])}</a></li>'
            for s in p["suggest"]
        )
        flag = "-u" if p["proto"] == "udp" else "-t"
        jsonld = [
            {
                "@context": "https://schema.org",
                "@type": "TechArticle",
                "headline": title,
                "inLanguage": "it",
                "url": f"{site}/porta/{n}/",
                "description": meta_description(p["desc"]),
            },
            {
                "@context": "https://schema.org",
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {"@type": "ListItem", "position": 1, "name": "FabGPT-FAQ", "item": f"{site}/"},
                    {"@type": "ListItem", "position": 2, "name": "Porte", "item": f"{site}/porta/"},
                    {"@type": "ListItem", "position": 3, "name": f"Porta {n}", "item": f"{site}/porta/{n}/"},
                ],
            },
        ]
        idx = ordered.index(p)
        nav = ""
        if idx > 0:
            q = ordered[idx - 1]
            nav += f'<a href="../{q["port"]}/">← Porta {q["port"]} ({html.escape(q["service"])})</a>'
        if idx < len(ordered) - 1:
            q = ordered[idx + 1]
            nav += f'<a href="../{q["port"]}/" style="float:right">Porta {q["port"]} ({html.escape(q["service"])}) →</a>'
        page = path_head(
            title=html.escape(title),
            description=html.escape(meta_description(p["desc"])),
            canonical=f"{site}/porta/{n}/",
            site=site,
            base="../../",
            jsonld=json.dumps(jsonld, ensure_ascii=False),
        )
        page += f"""<nav class="crumbs" aria-label="Percorso"><a href="../../">FabGPT-FAQ</a> › <a href="../">Porte</a> › <span>Porta {n}</span></nav>
<h1>Porta {n}/{html.escape(p["proto"] if p["proto"] != "both" else "tcp+udp")} – {html.escape(p["service"])}</h1>
<p class="intro">Protocollo: <b>{proto}</b></p>
<div class="answer">{render_md(p["desc"])}
<h2 style="font-size:17px;margin:20px 0 8px">Nota di sicurezza</h2>{render_md(p["risk"])}
<h2 style="font-size:17px;margin:20px 0 8px">Verifica al volo</h2>
<p>È in ascolto sul tuo server?</p>
<pre><code>ss {flag}lnp | grep :{n}</code></pre>
<p>È raggiungibile da fuori? (dal tuo client)</p>
<pre><code>nc -z{"u" if p["proto"] == "udp" else ""}v tuo-host {n}</code></pre>
</div>
<div class="related"><h2>Guide correlate</h2><ul>{related}</ul></div>
<div class="crumbs" style="margin-top:24px;overflow:hidden">{nav}</div>
<a class="ask" href="../../?q=porta {n}">{icon("chat")} Chiedi in chat</a>
<style>
  .answer {{ line-height: 1.6; }}
  .answer code {{ background: var(--code-bg); border-radius: 5px; padding: 1px 5px; font-family: ui-monospace, Menlo, monospace; font-size: .9em; }}
  .answer pre {{ background: var(--code-bg); border-radius: 8px; padding: 10px 12px; overflow-x: auto; }}
  .related {{ margin-top: 28px; border-top: 1px solid var(--border); padding-top: 16px; }}
  .related h2 {{ font-size: 16px; margin-bottom: 10px; }}
  .related a {{ color: var(--link); text-decoration: none; }}
  .related a:hover {{ text-decoration: underline; }}
</style>
"""
        page += close_page("../../")
        d = ROOT / "porta" / str(n)
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(page, encoding="utf-8")
        urls.append(f"{site}/porta/{n}/")

    # ports index
    rows = "".join(
        f'<li><a href="{p["port"]}/"><b>{p["port"]}</b>/{html.escape(p["proto"] if p["proto"] != "both" else "tcp+udp")} – {html.escape(p["service"])}</a>'
        f' <span style="color:var(--text-dim)">{html.escape(meta_description(p["desc"], 90))}</span></li>'
        for p in ordered
    )
    page = path_head(
        title="Porte well-known",
        description=f"Le {len(ordered)} porte che un sysadmin incontra davvero: a cosa servono, i rischi e i comandi per verificarle.",
        canonical=f"{site}/porta/",
        site=site,
        base="../",
        jsonld=json.dumps({
            "@context": "https://schema.org", "@type": "ItemList",
            "name": "Porte well-known",
            "itemListElement": [
                {"@type": "ListItem", "position": i + 1, "name": f"Porta {p['port']} – {p['service']}", "url": f"{site}/porta/{p['port']}/"}
                for i, p in enumerate(ordered)
            ],
        }, ensure_ascii=False),
    )
    page += (
        '<nav class="crumbs" aria-label="Percorso"><a href="../">FabGPT-FAQ</a> › <span>Porte</span></nav>\n'
        "<h1>Porte well-known, una per una</h1>\n"
        f'<p class="intro">Le {len(ordered)} porte che si incontrano davvero: servizio, rischi e comandi di verifica. '
        'La <a href="../q/porte-tcp-e-udp-quali-conoscere/">guida generale alle porte</a> spiega il quadro.</p>\n'
        f'<ul style="list-style:none;padding:0;line-height:1.9">{rows}</ul>\n'
    )
    page += close_page("../")
    (ROOT / "porta").mkdir(parents=True, exist_ok=True)
    (ROOT / "porta" / "index.html").write_text(page, encoding="utf-8")
    return urls


def build_commands(db, entries, site) -> list:
    """Render /comandi/ (index + one cheat-sheet page per group from commands.json)."""
    cfile = ROOT / "commands.json"
    if not cfile.exists():
        return []
    data = json.loads(cfile.read_text(encoding="utf-8"))
    groups, cards = data["groups"], data["cards"]
    by_slug = {e["slug"]: e for e in entries}
    urls = [f"{site}/comandi/"]
    for g in groups:
        gcards = [c for c in cards if c["group"] == g["slug"]]
        if not gcards:
            continue
        toc = "".join(
            f'<li><a href="#{c["id"]}">{html.escape(c["q"])}</a></li>' for c in gcards
        )
        body = ""
        for c in gcards:
            rel = "".join(
                f'<a href="../../q/{s}/">{html.escape(by_slug[s]["question"])}</a>'
                for s in c.get("related", [])
            )
            body += f"""<section class="cmd-card" id="{c["id"]}">
<h2><a class="anchor" href="#{c["id"]}">#</a> {html.escape(c["q"])}</h2>
<pre><code>{html.escape(c["cmd"])}</code></pre>
<p class="cmd-note">{inline_md(html.escape(c["note"]))}</p>
{f'<p class="cmd-rel">Approfondisci: {rel}</p>' if rel else ''}
</section>
"""
        jsonld = [
            {
                "@context": "https://schema.org",
                "@type": "FAQPage",
                "mainEntity": [
                    {
                        "@type": "Question",
                        "name": c["q"],
                        "acceptedAnswer": {"@type": "Answer", "text": c["cmd"] + "\n" + md_to_plain(c["note"])},
                    }
                    for c in gcards
                ],
            },
            {
                "@context": "https://schema.org",
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {"@type": "ListItem", "position": 1, "name": "FabGPT-FAQ", "item": f"{site}/"},
                    {"@type": "ListItem", "position": 2, "name": "Comandi", "item": f"{site}/comandi/"},
                    {"@type": "ListItem", "position": 3, "name": g["title"], "item": f"{site}/comandi/{g['slug']}/"},
                ],
            },
        ]
        page = path_head(
            title=html.escape(g["title"]) + " – comandi",
            description=html.escape(g["tagline"]),
            canonical=f"{site}/comandi/{g['slug']}/",
            site=site,
            base="../../",
            jsonld=json.dumps(jsonld, ensure_ascii=False),
        )
        page += f"""<nav class="crumbs" aria-label="Percorso"><a href="../../">FabGPT-FAQ</a> › <a href="../">Comandi</a> › <span>{html.escape(g["title"])}</span></nav>
<h1>{html.escape(g["title"])}</h1>
<p class="intro">{html.escape(g["tagline"])} Ogni comando è verificato e copiabile; in <a href="../../">chat</a> basta descrivere cosa vuoi fare.</p>
<details class="toc"><summary>{len(gcards)} comandi in questa pagina</summary><ul>{toc}</ul></details>
{body}
<a class="ask" href="../../">{icon("chat")} Chiedi in chat</a>
<style>
  .toc {{ border: 1px solid var(--border); border-radius: var(--r-md); background: var(--bg-raised); box-shadow: var(--elev); padding: 10px 14px; margin-bottom: 8px; }}
  .toc summary {{ cursor: pointer; font-weight: 600; }}
  .toc a {{ color: var(--link); text-decoration: none; }}
  .cmd-card {{ border: 1px solid var(--border); border-radius: var(--r-md); background: var(--bg-raised); box-shadow: var(--elev); padding: 14px 16px; margin: 12px 0; }}
  .cmd-card h2 {{ font-size: 16px; margin: 0 0 8px; }}
  .cmd-card .anchor {{ color: var(--text-dim); text-decoration: none; margin-right: 2px; }}
  .cmd-card pre {{ background: var(--code-bg); border-radius: 8px; padding: 10px 12px; overflow-x: auto; margin: 0 0 8px; cursor: pointer; }}
  .cmd-card code {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 13px; }}
  .cmd-note {{ font-size: 14px; margin: 0 0 6px; }}
  .cmd-note code {{ background: var(--code-bg); border-radius: 5px; padding: 1px 5px; overflow-wrap: anywhere; }}
  .cmd-note {{ overflow-wrap: anywhere; }}
  .cmd-rel {{ font-size: 13px; color: var(--text-dim); margin: 0; }}
  .cmd-rel a {{ color: var(--link); text-decoration: none; margin-right: 10px; }}
  .cmd-card:target {{ border-color: var(--accent); }}
</style>
<script>
document.addEventListener('click', function (e) {{
  var pre = e.target.closest('.cmd-card pre');
  if (!pre || !navigator.clipboard) return;
  navigator.clipboard.writeText(pre.innerText).then(function () {{
    pre.style.borderLeft = '3px solid var(--accent)';
    setTimeout(function () {{ pre.style.borderLeft = ''; }}, 800);
  }});
}});
</script>
"""
        page += close_page("../../")
        d = ROOT / "comandi" / g["slug"]
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(page, encoding="utf-8")
        urls.append(f"{site}/comandi/{g['slug']}/")

    # comandi index
    cardsidx = "".join(
        f'<a class="path-card" href="{g["slug"]}/"><span class="n">{sum(1 for c in cards if c["group"] == g["slug"])} comandi</span><br>'
        f"<b>{html.escape(g['title'])}</b><p>{html.escape(g['tagline'])}</p></a>\n"
        for g in groups if any(c["group"] == g["slug"] for c in cards)
    )
    page = path_head(
        title="Comandi verificati",
        description="Cheat-sheet operativi: il comando giusto, il suo gotcha e la guida di contesto. Anche in chat: descrivi cosa vuoi fare.",
        canonical=f"{site}/comandi/",
        site=site,
        base="../",
        jsonld=json.dumps({
            "@context": "https://schema.org", "@type": "ItemList",
            "name": "Comandi FabGPT-FAQ",
            "itemListElement": [
                {"@type": "ListItem", "position": i + 1, "name": g["title"], "url": f"{site}/comandi/{g['slug']}/"}
                for i, g in enumerate(groups)
            ],
        }, ensure_ascii=False),
    )
    page += (
        '<nav class="crumbs" aria-label="Percorso"><a href="../">FabGPT-FAQ</a> › <span>Comandi</span></nav>\n'
        "<h1>Comandi verificati</h1>\n"
        '<p class="intro">Il comando giusto con il suo gotcha, per schede tematiche. Gli stessi comandi rispondono in <a href="../">chat</a>: descrivi cosa vuoi fare ("come sbanno un IP?", "il container si riavvia") e arriva la riga pronta.</p>\n'
        + cardsidx
    )
    page += close_page("../")
    (ROOT / "comandi").mkdir(parents=True, exist_ok=True)
    (ROOT / "comandi" / "index.html").write_text(page, encoding="utf-8")
    return urls


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
            sbar=section_bar("../../", "q/"),
            foot=footer("../../"),
            ic_clock=icon("clock"),
            ic_check=icon("check"),
            ic_chat=icon("chat"),
            toolbanner=(
                f'<a class="ask" style="margin:10px 0 4px;display:inline-block" href="{TOOL_BANNERS[e["id"]][0]}">{icon(TOOL_BANNERS[e["id"]][1])} {TOOL_BANNERS[e["id"]][2]}</a>'
                if e["id"] in TOOL_BANNERS else ""
            ),
            question=html.escape(e["question"]),
            answer=render_md(answer_md).replace('href="q/', 'href="../') + figure,
            id=e["id"],
            page_nav=page_nav,
            related=related,
        )
        (d / "index.html").write_text(page, encoding="utf-8")

    # --- index page with full FAQPage JSON-LD, instant search & vertical chips ---


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
    # --- percorsi (guided paths), tools, porte ---
    path_urls = build_paths(db, entries, site)
    path_urls += build_tools(db, entries, site)
    path_urls += build_ports(db, entries, site)
    path_urls += build_commands(db, entries, site)
    paths_meta = (
        json.loads((ROOT / "paths.json").read_text(encoding="utf-8"))["paths"]
        if (ROOT / "paths.json").exists() else []
    )
    percorsi_strip = ""
    if paths_meta:
        cards = "".join(
            f'<a class="path-card" href="../percorsi/{p["slug"]}/">'
            f'<span class="n">{len(p["steps"])} tappe</span><br><b>{html.escape(p["title"])}</b>'
            f"<p>{html.escape(p['tagline'])}</p></a>"
            for p in paths_meta
        )
        percorsi_strip = f'<div class="paths-strip">{cards}</div>'

    (OUT / "index.html").write_text(
        INDEX.format(
            description="Tutte le domande e risposte di FabGPT-FAQ: cybersecurity, AI, Proxmox, Cloudflare e i progetti open source di Fabrizio Salmi.",
            canonical=f"{site}/q/",
            site=site,
            total=len(entries),
            sbar=section_bar("../", "q/"),
            foot=footer("../"),
            percorsi=percorsi_strip,
            chips=chips_html,
            jsonld=json.dumps(index_jsonld, ensure_ascii=False),
            sections=sections,
        ),
        encoding="utf-8",
    )

    # --- sitemap.xml + robots.txt ---
    urls = [f"{site}/", f"{site}/q/"] + path_urls + [f"{site}/q/{e['slug']}/" for e in entries]
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
    if paths_meta:
        lt.append("\n## Percorsi guidati\n")
        for p in paths_meta:
            lt.append(f"- [{p['title']}]({site}/percorsi/{p['slug']}/): {p['tagline']}")
    if (ROOT / "commands.json").exists():
        _cd = json.loads((ROOT / "commands.json").read_text(encoding="utf-8"))
        lt.append("\n## Comandi verificati\n")
        for g in _cd["groups"]:
            n = sum(1 for c in _cd["cards"] if c["group"] == g["slug"])
            if n:
                lt.append(f"- [{g['title']}]({site}/comandi/{g['slug']}/): {g['tagline']} ({n} comandi)")
    lt.append("\n## Tools deterministici\n")
    for t in TOOLS:
        lt.append(f"- [{t['title']}]({site}/tools/{t['slug']}/): {t['tagline']}")
    if (ROOT / "ports.json").exists():
        _ports = json.loads((ROOT / "ports.json").read_text(encoding="utf-8"))["ports"]
        lt.append("\n## Porte well-known\n")
        for p in sorted(_ports.values(), key=lambda x: x["port"]):
            lt.append(f"- [Porta {p['port']} – {p['service']}]({site}/porta/{p['port']}/): {meta_description(p['desc'], 110)}")
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
"""+footer("./")+"""
</body>
</html>
"""
    (ROOT / "404.html").write_text(notfound, encoding="utf-8")

    print(f"Built {len(entries)} pages + {len(paths_meta)} percorsi + index + sitemap ({len(urls)} URLs) + llms.txt + llms-full.txt + 404.")


if __name__ == "__main__":
    build()
