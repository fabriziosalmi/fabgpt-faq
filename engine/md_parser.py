#!/usr/bin/env python3
"""ZeroGPT / Engine – Markdown to faq.json Compiler.

Reads a directory of .md files (with or without YAML frontmatter)
and compiles them into a validated faq.json file.

Usage:
  python3 engine/md_parser.py <markdown_dir> <output_faq_json>
"""
import argparse
import json
import re
import sys
from pathlib import Path

STOPWORDS = set((
    "il lo la i gli le un uno una di a da in con su per tra fra e o ma se che chi cosa come dove quando quanto "
    "perche non mi ti si ci vi ne del della dei delle dello degli al allo alla ai agli alle sul sullo sulla sui sugli sulle nel nella nei "
    "sono sei e siamo siete ho hai ha abbiamo avete hanno posso puoi puo vorrei voglio sapere dimmi parlami spiegami raccontami esiste esistono "
    "c e ce cos cose cioe questo questa questi queste quello quella mio mia tuo tua suo sua piu meno molto poco anche ancora gia solo cose roba "
    "the a an of to is are was were be been what who how why when where and or me my your tell about does do can could would please"
).split())


def slugify(text: str) -> str:
    s = text.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_-]+", "-", s)
    return s.strip("-")


def extract_keywords_auto(text: str, top_n: int = 8) -> list:
    words = re.findall(r"\b[a-zA-Z0-9àèéìòùÀÈÉÌÒÙ-]{4,}\b", text.lower())
    freq = {}
    for w in words:
        if w not in STOPWORDS:
            freq[w] = freq.get(w, 0) + 1
    sorted_words = sorted(freq.items(), key=lambda x: x[1], reverse=True)
    return [w for w, _ in sorted_words[:top_n]]


def parse_frontmatter(content: str):
    frontmatter = {}
    body = content
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, re.DOTALL)
    if match:
        raw_meta, body = match.group(1), match.group(2)
        for line in raw_meta.split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" in line:
                k, v = line.split(":", 1)
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                if v.startswith("[") and v.endswith("]"):
                    items = [x.strip().strip('"').strip("'") for x in v[1:-1].split(",") if x.strip()]
                    frontmatter[k] = items
                else:
                    frontmatter[k] = v
    return frontmatter, body.strip()


def compile_markdown_dir(md_dir: Path, output_file: Path, bot_name: str = "ZeroGPT", site_url: str = "https://example.com") -> None:
    entries = []
    for md_file in sorted(md_dir.glob("*.md")):
        if md_file.name.startswith(("_", ".")):
            continue
        text = md_file.read_text(encoding="utf-8")
        meta, body = parse_frontmatter(text)

        # Question from frontmatter or first H1
        question = meta.get("question")
        if not question:
            h1_match = re.search(r"^#\s+(.+)$", body, re.M)
            if h1_match:
                question = h1_match.group(1).strip()
                body = re.sub(r"^#\s+.+\n", "", body, count=1).strip()
            else:
                question = md_file.stem.replace("-", " ").capitalize()

        slug = meta.get("slug") or slugify(question)
        entry_id = meta.get("id") or slug

        # Keywords from frontmatter or auto-extracted
        keywords = meta.get("keywords")
        if not keywords:
            keywords = [slug.replace("-", " ")] + extract_keywords_auto(question + " " + body)

        entry = {
            "id": entry_id,
            "slug": slug,
            "question": question,
            "vertical": meta.get("vertical", "general"),
            "keywords": keywords,
            "answers": [body],
            "suggest": meta.get("suggest", [])
        }
        entries.append(entry)

    # Base config
    data = {
        "config": {
            "botName": bot_name,
            "siteUrl": site_url,
            "welcome": f"Benvenuto nell'assistente **{bot_name}**.",
            "placeholder": "Fai una domanda...",
            "matchThreshold": 0.75,
            "suggest": [e["slug"] for e in entries[:4]]
        },
        "verticals": [
            {"id": "general", "label": "Generale"}
        ],
        "entries": entries,
        "smalltalk": [
            {"id": "st-saluto", "keywords": ["ciao", "salve", "buongiorno"], "answers": [f"Ciao! Come posso aiutarti con {bot_name}?"]}
        ],
        "fallbacks": ["Non ho trovato una risposta verificata per questa domanda."]
    }

    output_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✓ Compilati {len(entries)} file Markdown in {output_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert Markdown files to faq.json")
    parser.add_argument("md_dir", help="Directory containing .md files")
    parser.add_argument("output", help="Path to output faq.json")
    parser.add_argument("--bot-name", default="ZeroGPT", help="Name of the bot")
    parser.add_argument("--site-url", default="https://example.com", help="Canonical site URL")
    args = parser.parse_args()

    compile_markdown_dir(Path(args.md_dir), Path(args.output), args.bot_name, args.site_url)
