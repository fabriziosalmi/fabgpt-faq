# fabgpt-faq

A FAQ disguised as an AI chat – and an answer-engine-optimization play.

**Live:** https://fabriziosalmi.github.io/fabgpt-faq/

The interface looks like ChatGPT: free-text input, streaming typewriter answers,
the familiar layout. But there is no model behind it. Every answer is
**pre-written, human-verified** and selected by a deterministic, dependency-free
engine with typo tolerance. A maze of hand-crafted answers, simulated as AI –
which makes it structurally incapable of hallucinating.

The same knowledge base is also compiled into **static, crawlable pages** – one
URL per question, with `FAQPage` JSON-LD, a sitemap and question-shaped titles –
the format search engines and AI answer engines (Google AI Overview & co.)
actually cite.

Everything is static: no backend, no build toolchain, no runtime dependencies.

## How a message is answered

The chat resolves every input through four layers, in order. Each layer can
only answer when the previous ones decline, and the whole pipeline is mirrored
in Python so it can be gated without a browser:

1. **Deterministic fast-path** (`tools.js`) – inputs that should be *computed*,
   not matched: JWT decode, CIDR math, `chmod` masks, cron expressions,
   well-known ports, Unix timestamps, arithmetic, date/time. Zero guessing.
2. **Knowledge base** (`faq.json`) – fuzzy keyword matching over the curated
   entries and the conversational smalltalk layer, with multi-turn context:
   elliptical follow-ups ("e i backup?") are resolved against the previous
   entry's tokens. Answer variants rotate on re-asks.
3. **Command cards** (`commands.json`) – operational one-liners grouped into
   cheat-sheets. A card answers only if it clearly beats the KB score.
4. **Ground-truth layer** (`ground.json`) – the classic day-one questions
   people throw at an "AI" to test it (benchmark staples, myths, riddles,
   base culture). Chat-only – no pages, no sitemap – and it can never steal
   a query from the layers above.

Below all four, curated fallbacks rotate, always offering a way back in.

## Surfaces

| Surface | Path | Source |
|---|---|---|
| Chat (with live search-as-you-type) | `/` | `index.html` + `app.js` + `tools.js` |
| Q&A pages (FAQPage JSON-LD) | `/q/<slug>/` | generated from `faq.json` |
| Guided paths with local progress | `/percorsi/<slug>/` | `paths.json` |
| Deterministic + live tools | `/tools/<slug>/` | `build.py` (`TOOLS`) |
| Well-known ports, one page each | `/porta/<n>/` | `ports.json` |
| Command cheat-sheets | `/comandi/<group>/` | `commands.json` |
| Transparency & privacy | `/trasparenza/` | `build.py` |
| Answer-engine maps | `/llms.txt`, `/llms-full.txt`, `/sitemap.xml` | generated |

Concept diagrams live in `diagrams.json` (entry id → inline theme-aware SVG);
they render in both chat and static pages and become each page's OG card.
Inline `code` is click-to-copy everywhere.

## Quality gates

Nothing ships on a red gate. The suite mirrors the full JS pipeline in Python:

| Gate | Command | Guards |
|---|---|---|
| Battery | `python3 qa.py` | one curated test per entry, keyword-collision report |
| G1–G5 | `python3 bench.py` | integrity (dup keywords, em-dash, homoglyphs, broken links), canonical questions 100%, typo-mutated ≥ 90%, battery 100%, negatives 100% |
| T1–T5 | `python3 traj.py` | chip-graph integrity, no orphans, no trap pockets, scripted multi-turn and contextual sessions |
| T6 | `node tools_test.mjs` | the deterministic fast-path tools |
| T7 | `python3 cmdcheck.py` | command cards: integrity, no-steal, routing, battery fidelity |
| T8 | `python3 convcheck.py` | conversation marathons up to 23 turns: routing 100%, the bot never repeats itself, every fallback fresh, always a live chip |
| T9 | `python3 groundcheck.py` | ground-truth layer: integrity + canonical routing through the full pipeline |

Every gate loads every dataset, so a layer stealing queries from another turns
some gate red by construction.

Editing pipeline: edit content → `python3 gen_suggest.py` (suggestion graph) →
run the gates → `python3 build.py` → commit. The build content-hashes
`style.css` / `app.js` / `tools.js` into every URL (`?v=<hash>`), so deploys
are cache-safe with no manual versioning.

Content rules: en dash only (no em dash), no emoji, no hardcoded counts –
live numbers use the `{n}` template, resolved at render time in both chat and
build. External metrics (stars, provider counts) are stated qualitatively.

## Run locally

```bash
python3 -m http.server 8123
```

Then open http://localhost:8123. (A plain `file://` open won't load `faq.json`.)

## Edit the knowledge base

All chat content lives in [`faq.json`](faq.json):

```jsonc
{
  "config": {
    "botName": "FabGPT-FAQ",
    "siteUrl": "https://example.github.io/fabgpt-faq",  // canonical URLs + sitemap
    "welcome": "…",              // first streamed message ({n} = entry count)
    "placeholder": "…",          // input placeholder (fallback)
    "placeholders": ["…"],       // rotating placeholders, deterministic by day
    "footerNote": "…",           // line under the composer (inline markdown)
    "matchThreshold": 0.75,      // minimum score before falling back
    "typing": { "minDelay": 18, "maxDelay": 55, "wordsPerTick": 2 }
  },
  "verticals": [ { "id": "security", "label": "Cybersecurity" } ],
  "entries": [
    {
      "id": "certmate",                 // stable id, also /?q=<id> deep links
      "slug": "cos-e-certmate",         // URL of the generated static page
      "question": "Cos'è CertMate?",    // canonical question: H1, <title>, JSON-LD
      "vertical": "security",
      "keywords": ["certmate", "tls", "ca privata"],
      "answers": ["Markdown answer…", "Variant served on re-asks…"],
      "suggest": ["slug-1", "slug-2"]   // follow-up chips (gen_suggest.py fills gaps)
    }
  ],
  "smalltalk": [ { "id": "st-saluto", "keywords": ["ciao"], "answers": ["…"] } ],
  "fallbacks": ["Rotated when nothing scores above the threshold…"]
}
```

Matching semantics (mirrored one-to-one in `qa.py`):

- Input is lowercased, de-accented and tokenized; stopwords (IT + EN) drop.
- Single-word keywords match exactly, via Sørensen–Dice bigram similarity
  (≥ 0.7) for typos, or via Damerau distance 1 with a first-letter guard.
- Multi-word keywords match as exact substrings (≥ 5 chars, score 2) or as
  fuzzy all-words-present phrases.
- Highest score wins; ties favor the earliest entry, and the KB beats
  smalltalk, cards and ground on equal footing.

Answers support minimal markdown: `**bold**`, `*italic*`, `` `code` ``,
fenced code blocks, `[link](https://…)` / `[link](mailto:…)` / relative
`[link](q/slug/)`, `- ` lists and blank-line paragraphs.

`/?q=<id-or-slug>` deep-links the chat: after the welcome, the bot is asked
that entry's canonical question (this is what "Chiedilo a FabGPT-FAQ" on every
static page does).

## Deploy

Any static host works. For GitHub Pages: enable Pages (deploy from branch,
root), set `config.siteUrl`, run `python3 build.py`, push. The `.nojekyll`
file is required so Pages serves the tree as-is.

## Reuse it

The engine is generic: swap `faq.json` (and optionally `commands.json`,
`ports.json`, `paths.json`, `ground.json`) and you have a verified-answers
fake-AI FAQ for anything else, with the whole gate suite ready to keep it
honest.

## License

[MIT](LICENSE)
