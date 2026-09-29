# Novità v1.1.1

## Core Engine Disaccoppiato (engine/)
- matcher.js: modulo puro di matching fuzzy (Sørensen-Dice, Damerau-1, contesto multi-turn) e renderer Markdown, privo di dipendenze esterne.
- tools.js: calcoli deterministici veloci (CIDR, cron, chmod, JWT, epoch, porte) con registry estendibile (registerTool).
- widget.js: widget di chat embeddabile drop-in con isolamento completo tramite Shadow DOM.
- app.js e style.css: interfaccia chat standalone con design system pulito e reattivo.
- build.py: compilatore statico agnostico per la generazione di pagine Q&A con schema JSON-LD FAQPage, mappa e file llms.txt.
- md_parser.py: compilatore da directory di file Markdown a faq.json.

## Esempio di Declinazione Verticale (examples/)
- examples/nis2/: implementazione di riferimento per la conformità alla Direttiva NIS2 (D.Lgs. 138/2024), con dashboard aziendale data-driven, calcolatori di settore e widget integrato.
