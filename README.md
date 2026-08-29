# fabgpt-faq

A FAQ disguised as an AI chat — and an answer-engine-optimization play.

The interface looks like ChatGPT: free-text input, streaming typewriter answers, the
familiar layout. But there is no model behind it. Every answer is **pre-written and
verified**, stored in a JSON knowledge base and selected by a dependency-free keyword
matcher with typo tolerance. A maze of hand-crafted answers, simulated as AI.

The same knowledge base is also compiled into **static, crawlable pages** — one URL per
question, with `FAQPage` JSON-LD, a sitemap and question-shaped titles — the format
search engines and AI answer engines (Google AI Overview & co.) actually cite.

Two layers, one source of truth:

| Layer | For | Files |
|---|---|---|
| Chat | humans | `index.html` + `app.js` + `style.css` |
| Static Q&A pages | crawlers / answer engines | `q/<slug>/index.html` + `sitemap.xml` (generated) |

Everything is static. No backend, no build toolchain, no dependencies.

## Run locally

```bash
python3 -m http.server 8437
```

Then open http://localhost:8437. (A plain `file://` open won't load `faq.json`.)

## Edit the knowledge base

All content lives in [`faq.json`](faq.json):

```jsonc
{
  "config": {
    "botName": "FabGPT",
    "siteUrl": "https://example.github.io/fabgpt-faq",  // used for canonical URLs + sitemap
    "welcome": "…",              // first streamed message (markdown)
    "placeholder": "…",          // input placeholder
    "footerNote": "…",           // line under the composer
    "matchThreshold": 0.75,      // minimum score before falling back
    "typing": { "minDelay": 18, "maxDelay": 55, "wordsPerTick": 2 }
  },
  "verticals": [ { "id": "security", "label": "Cybersecurity" } ],
  "entries": [
    {
      "id": "certmate",                          // stable id, also used by /?q=<id> deep links
      "slug": "cos-e-certmate",                  // URL of the generated static page
      "question": "Cos'è CertMate?",             // canonical question: H1, <title>, JSON-LD
      "vertical": "security",
      "keywords": ["certmate", "tls", "ca privata"],  // single words match fuzzily (typo-tolerant);
                                                      // multi-word keywords match as phrases and score double
      "answers": ["Long markdown answer…", "Shorter variant…"]
      // answers[0] feeds the static page; extra variants rotate in chat when
      // the same question is asked twice in a row.
    }
  ],
  "fallbacks": ["Shown when nothing scores above the threshold…"]
}
```

Answers support minimal markdown: `**bold**`, `*italic*`, `` `code` ``, `[link](https://…)`,
`- ` lists and blank-line paragraphs.

After editing, regenerate the static layer:

```bash
python3 build.py
```

This rewrites `q/` (one page per entry + an all-questions index), `sitemap.xml` and
`robots.txt`. Commit the generated files — the site is served as-is.

## Deploy

Any static host works. For GitHub Pages: enable Pages on the repository (deploy from
branch, root), set `config.siteUrl` in `faq.json` to the public URL, run
`python3 build.py`, push.

## Reuse it

The engine is generic: replace `faq.json` with your own content and you have a fake-AI
FAQ for anything else. Matching notes:

- Input is lowercased, de-accented and tokenized; stopwords (IT + EN) are dropped.
- Single-word keywords match exactly, or fuzzily via Sørensen–Dice bigram similarity
  (threshold 0.7) to absorb typos.
- Multi-word keywords match as substrings of the whole normalized input and score 2.
- Highest total score wins; ties go to the earliest entry in `entries`, so put
  broader entries before narrower ones that share keywords.
- Below `matchThreshold`, fallbacks rotate.

`/?q=<id-or-slug>` deep-links the chat: after the welcome message, the bot is asked
that entry's canonical question automatically (this is what the "Chiedilo a FabGPT"
button on every static page does).

## License

MIT
