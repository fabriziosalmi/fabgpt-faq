#!/usr/bin/env python3
"""ZeroGPT / Engine – Agnostic Static Site & AEO Compiler.

Reads any valid faq.json and compiles:
- Static Q&A pages with FAQPage JSON-LD schema -> /q/<slug>/index.html
- Directory index of all questions -> /q/index.html
- Answer Engine Optimization files: llms.txt & llms-full.txt
- SEO files: sitemap.xml & robots.txt
- 404 error page

Usage:
  python3 build.py [path_to_dir_with_faq_json]
"""
import argparse
import html
import json
import os
import re
import shutil
import sys
from pathlib import Path

def inline_md(s: str) -> str:
    codes = []
    def _stash(m):
        codes.append(m.group(1))
        return f"@@@CODESPAN_{len(codes) - 1}@@@"

    s = re.sub(r"`([^`]+)`", _stash, s)
    s = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2" target="_blank" rel="noopener">\1</a>', s)
    s = re.sub(r"\[([^\]]+)\]\((mailto:[^)\s]+)\)", r'<a href="\2">\1</a>', s)
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
    s = re.sub(r"```[a-zA-Z0-9_-]*\n([\s\S]*?)```", r"\1", text)
    s = re.sub(r"\[([^\]]+)\]\((?:https?|mailto):[^)\s]+\)", r"\1", s)
    s = re.sub(r"[*`]", "", s)
    s = re.sub(r"^\s*-\s+", "", s, flags=re.M)
    return re.sub(r"\s+", " ", s).strip()


def meta_description(text: str, limit: int = 158) -> str:
    plain = md_to_plain(text)
    if len(plain) <= limit:
        return plain
    return plain[: limit - 1].rsplit(" ", 1)[0] + "…"


def build_site(target_dir: Path) -> None:
    faq_path = target_dir / "faq.json"
    if not faq_path.exists():
        print(f"Error: {faq_path} not found.")
        sys.exit(1)

    db = json.loads(faq_path.read_text(encoding="utf-8"))
    cfg = db.get("config", {})
    site = cfg.get("siteUrl", "https://example.com").rstrip("/")
    bot_name = cfg.get("botName", "ZeroGPT")
    author_name = cfg.get("authorName", "Team")
    author_url = cfg.get("authorUrl", site)
    repo_url = cfg.get("githubUrl", "")

    entries = db.get("entries", [])
    entry_count = len(entries)
    by_slug = {e["slug"]: e for e in entries if "slug" in e}
    by_id = {e["id"]: e for e in entries if "id" in e}
    verticals = {v["id"]: v["label"] for v in db.get("verticals", [])}

    out_q = target_dir / "q"
    out_q.mkdir(parents=True, exist_ok=True)

    print(f"==> Compiling {bot_name} ({entry_count} entries) in {target_dir}")

    # 1. Compile individual question pages
    for e in entries:
        slug = e.get("slug")
        if not slug:
            continue
        q_dir = out_q / slug
        q_dir.mkdir(parents=True, exist_ok=True)

        question = e.get("question", "")
        raw_answer = e["answers"][0] if e.get("answers") else ""
        answer = raw_answer.replace("{n}", str(entry_count))
        mdesc = meta_description(answer)
        canon = f"{site}/q/{slug}/"
        vert_id = e.get("vertical", "")
        vert_label = verticals.get(vert_id, "Guida")

        # Suggestion chips
        chips_html = []
        for s in e.get("suggest", []):
            se = by_slug.get(s)
            if se:
                chips_html.append(f'<a href="../{s}/" class="chip">{html.escape(se["question"])}</a>')
        chips_section = f'<div class="chips-box"><h3>Domande collegate:</h3><div class="chips-list">{"".join(chips_html)}</div></div>' if chips_html else ""

        # FAQPage JSON-LD schema
        schema = {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [{
                "@type": "Question",
                "name": question,
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": md_to_plain(answer)
                }
            }]
        }

        page_html = f"""<!DOCTYPE html>
<html lang="it">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{html.escape(question)} | {html.escape(bot_name)}</title>
  <meta name="description" content="{html.escape(mdesc)}">
  <link rel="canonical" href="{canon}">
  <meta property="og:title" content="{html.escape(question)}">
  <meta property="og:description" content="{html.escape(mdesc)}">
  <meta property="og:url" content="{canon}">
  <meta property="og:type" content="article">
  <script type="application/ld+json">
{json.dumps(schema, ensure_ascii=False, indent=2)}
  </script>
  <style>
    :root {{
      --bg: #ffffff;
      --text: #0f172a;
      --muted: #64748b;
      --border: #e2e8f0;
      --primary: #0284c7;
      --card-bg: #f8fafc;
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      line-height: 1.6;
    }}
    @media (prefers-color-scheme: dark) {{
      :root {{
        --bg: #0f172a;
        --text: #f8fafc;
        --muted: #94a3b8;
        --border: #334155;
        --card-bg: #1e293b;
      }}
    }}
    body {{
      margin: 0;
      padding: 0;
      background: var(--bg);
      color: var(--text);
      display: flex;
      flex-direction: column;
      min-height: 100vh;
    }}
    header {{
      border-bottom: 1px solid var(--border);
      padding: 16px 24px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }}
    header a {{
      color: var(--primary);
      text-decoration: none;
      font-weight: 600;
    }}
    main {{
      max-width: 800px;
      margin: 40px auto;
      padding: 0 20px;
      flex: 1;
    }}
    .badge {{
      display: inline-block;
      padding: 4px 10px;
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 20px;
      font-size: 12px;
      color: var(--muted);
      margin-bottom: 12px;
    }}
    h1 {{
      font-size: 2rem;
      margin-top: 0;
      line-height: 1.25;
    }}
    .answer-box {{
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 24px;
      margin: 24px 0;
    }}
    .chips-box {{
      margin-top: 32px;
    }}
    .chips-list {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 10px;
    }}
    .chip {{
      display: inline-block;
      padding: 8px 14px;
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 20px;
      font-size: 13px;
      color: var(--text);
      text-decoration: none;
      transition: border-color 0.15s;
    }}
    .chip:hover {{
      border-color: var(--primary);
      color: var(--primary);
    }}
    footer {{
      border-top: 1px solid var(--border);
      padding: 24px;
      text-align: center;
      font-size: 13px;
      color: var(--muted);
    }}
  </style>
</head>
<body>
  <header>
    <a href="../../">← Torna all'assistente {html.escape(bot_name)}</a>
    <span style="font-size:13px; color:var(--muted);">{html.escape(vert_label)}</span>
  </header>
  <main>
    <span class="badge">Risposta verificata · Zero allucinazioni</span>
    <h1>{html.escape(question)}</h1>
    <div class="answer-box">
      {render_md(answer)}
    </div>
    {chips_section}
  </main>
  <footer>
    <p>Generato da <strong>{html.escape(bot_name)}</strong> · Nessun modello generativo · Risposte verificate e deterministiche.</p>
  </footer>
</body>
</html>"""
        (q_dir / "index.html").write_text(page_html, encoding="utf-8")

    # 2. Compile /q/index.html (Index of questions)
    q_index_items = []
    for e in entries:
        slug = e.get("slug")
        if slug:
            q_index_items.append(f'<li><a href="{slug}/">{html.escape(e["question"])}</a></li>')

    q_index_html = f"""<!DOCTYPE html>
<html lang="it">
<head>
  <meta charset="UTF-8">
  <title>Indice delle Domande | {html.escape(bot_name)}</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    body {{ font-family: system-ui, sans-serif; max-width: 800px; margin: 40px auto; padding: 0 20px; line-height: 1.6; }}
    ul {{ padding-left: 20px; }}
    li {{ margin-bottom: 8px; }}
    a {{ color: #0284c7; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
  </style>
</head>
<body>
  <p><a href="../">← Torna alla Chat</a></p>
  <h1>Indice delle {entry_count} Domande Verificate</h1>
  <ul>{"".join(q_index_items)}</ul>
</body>
</html>"""
    (out_q / "index.html").write_text(q_index_html, encoding="utf-8")

    # 3. Generate sitemap.xml
    sitemap_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
        f'  <url><loc>{site}/</loc><changefreq>weekly</changefreq><priority>1.0</priority></url>',
        f'  <url><loc>{site}/q/</loc><changefreq>weekly</changefreq><priority>0.9</priority></url>'
    ]
    for e in entries:
        slug = e.get("slug")
        if slug:
            sitemap_lines.append(f'  <url><loc>{site}/q/{slug}/</loc><changefreq>monthly</changefreq><priority>0.8</priority></url>')
    sitemap_lines.append('</urlset>')
    (target_dir / "sitemap.xml").write_text("\n".join(sitemap_lines), encoding="utf-8")

    # 4. Generate robots.txt
    robots_txt = f"""User-agent: *
Allow: /

Sitemap: {site}/sitemap.xml
"""
    (target_dir / "robots.txt").write_text(robots_txt, encoding="utf-8")

    # 5. Generate llms.txt & llms-full.txt (Answer Engine Optimization)
    llms_txt = [
        f"# {bot_name}",
        f"> {cfg.get('description', 'Domande e risposte verificate con zero allucinazioni.')}",
        f"> Live: {site}",
        "",
        "## Domande frequenti",
        ""
    ]
    for e in entries:
        slug = e.get("slug")
        if slug:
            llms_txt.append(f"- [{e['question']}]({site}/q/{slug}/): {meta_description(e['answers'][0] if e.get('answers') else '')}")
    (target_dir / "llms.txt").write_text("\n".join(llms_txt), encoding="utf-8")

    llms_full = [
        f"# {bot_name} (Full Knowledge Base)",
        f"> Generated from verified human sources. Zero hallucinations.",
        ""
    ]
    for e in entries:
        slug = e.get("slug")
        if slug:
            ans = (e['answers'][0] if e.get('answers') else '').replace("{n}", str(entry_count))
            llms_full.append(f"## {e['question']}\n\n{ans}\n\nURL: {site}/q/{slug}/\n\n---\n")
    (target_dir / "llms-full.txt").write_text("\n".join(llms_full), encoding="utf-8")

    print(f"✓ Created {entry_count} static pages in /q/")
    print(f"✓ Generated sitemap.xml, robots.txt, llms.txt, llms-full.txt")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ZeroGPT Static Builder")
    parser.add_argument("dir", nargs="?", default=".", help="Target directory containing faq.json")
    args = parser.parse_args()
    build_site(Path(args.dir).resolve())
