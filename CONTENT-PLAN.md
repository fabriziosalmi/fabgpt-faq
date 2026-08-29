# Content plan – the 10x knowledge base

Target: ~600-700 entries, grown in deliberate batches. Each entry: Aranzulla-style
question title, accurate 80-140 word answer, funnel link to a fabriziosalmi tool
where natural, keywords designed against collisions (`python3 qa.py` must stay green,
one test per entry in `tests.json`).

Status legend: no mark = backlog · **[B1]** … **[Bn]** = shipped in batch n · existing
entries from the first 68 are not repeated here.

Quality loop (autonomous iteration):

- `python3 qa.py` – curated battery (tests.json, one test per entry) + collision report;
  `python3 qa.py "query"` explains any single match.
- `python3 bench.py` – the draconian gate: G1 integrity (dup keywords, word-set dup
  phrases, em-dashes, broken internal links), G2 canonical questions 100%, G3
  typo-mutated questions >= 90%, G4 battery 100%, G5 negatives 100%. Non-blocking
  fragility report = the standing hardening backlog. Nothing ships on a red bench.

Conversational layer: `faq.json` has a `smalltalk` array (22 intents – greetings,
thanks, capabilities, out-of-domain tasks, emotional turns…) grounded in the
distribution of Italian/English conversational datasets (OASST1 it-split sampled
live, LMSYS/ShareGPT taxonomies). Matched after the KB (ties favor knowledge),
never rendered as static pages. Extend it when real users surface new intents.

Working rules (learned so far):

- Concept entries own bare nouns; repo entries own names + phrases. Earliest entry
  wins ties, so order = broad before narrow.
- En dash (–) for asides, never em dash.
- Answers may admit limits (alpha status, honest trade-offs): credibility is the moat.
- Every batch ends with: `python3 qa.py` + `python3 bench.py` green → `python3 build.py` → commit.
- Phrase keywords match exact-substring first, then all-content-words fuzzy (any
  order, typo-tolerant, Damerau distance 1 recovery): near-duplicate phrase
  variants are harmful (they double count) – G1 flags them.

## Cybersecurity

### Concepts

- [B1] Che differenza c'è tra HTTP e HTTPS (e cos'è TLS)?
- [B1] Cos'è un attacco DDoS e come ci si difende?
- [B1] Cos'è la OWASP Top 10?
- [B1] Cos'è la SQL injection e come si previene?
- [B1] Cos'è il cross-site scripting (XSS)?
- [B1] Cos'è il modello Zero Trust?
- [B1] Cos'è l'autenticazione a più fattori (MFA/2FA)?
- Cos'è il phishing (e lo spear phishing)?
- Cos'è un ransomware e come ci si prepara?
- Cos'è un honeypot?
- Cos'è un SOC (Security Operations Center)?
- EDR, XDR, antivirus: che differenza c'è?
- Cos'è la threat intelligence?
- Cos'è una CVE (e il punteggio CVSS)?
- Vulnerability assessment vs penetration test: differenze
- Cos'è un bug bounty (e come funziona HackerOne)?
- Cos'è l'OSINT?
- Firewall di rete vs WAF: che differenza c'è?
- VPN vs proxy: cosa cambia?
- Cos'è il principio del minimo privilegio?
- Cosa sono IDS e IPS?
- Cos'è la defense in depth?
- Cos'è un attacco man-in-the-middle?
- Cos'è il DNS spoofing/poisoning?
- Cos'è un attacco brute force (e il credential stuffing)?
- Cos'è una botnet?
- Cos'è il typosquatting (e il domain squatting)?
- Cosa sono i data breach più famosi e cosa insegnano?
- Password manager: perché usarne uno
- Passkey: la fine delle password?
- Cos'è la crittografia end-to-end?
- Crittografia simmetrica vs asimmetrica
- Cos'è l'hashing (e perché bcrypt/argon2)?
- Cos'è un certificato wildcard (e i SAN)?
- Cos'è mTLS (mutual TLS)?
- Cos'è HSTS e il preload?
- Cos'è DNSSEC?
- Cos'è DNS-over-HTTPS (DoH) / DNS-over-TLS?
- Cos'è un air gap?
- Cos'è la steganografia?
- Sicurezza fisica dei server: le basi

### How-to / hardening

- [B1] Come si mette in sicurezza SSH su un server esposto?
- [B1] Quali security header HTTP servono davvero?
- [B1] Come si bloccano i crawler AI (GPTBot & co.)?
- Come si fa l'hardening di un server Linux appena installato?
- Come si configura HTTPS su Nginx?
- Come si configura HTTPS su Caddy (automatico)?
- Come si difende un sito dallo scraping?
- Come si limita l'accesso a un'area admin (IP allowlist, auth)?
- Come si gestiscono i secrets (e perché non in git)?
- Come si fa un backup 3-2-1?
- Come si verifica se una password è stata compromessa?
- Come si segmenta una rete domestica/aziendale (VLAN)?
- Come si espone un servizio self-hosted senza aprire porte (tunnel)?
- Come si controlla cosa esce dalla propria rete (egress)?
- Come si firma il codice (e perché)?
- Come si fa security logging fatto bene?
- Come si risponde a un incidente: le prime ore
- Come si scrive un piano di disaster recovery minimo

### Errors & troubleshooting

- [B1] Errore ERR_CERT_AUTHORITY_INVALID: cosa significa?
- [B1] Errore 502 Bad Gateway: cause e soluzioni
- [B1] Errore 429 Too Many Requests: cosa fare?
- [B1] Cos'è il mixed content e come si risolve?
- Errore 403 Forbidden: le cause tipiche
- Errore SSL_ERROR_NO_CYPHER_OVERLAP / handshake failure
- ERR_TOO_MANY_REDIRECTS: il loop di redirect
- Il sito è lento solo per alcuni: come si diagnostica
- "Sito ingannevole in vista": come uscire dalla blocklist Google Safe Browsing

### Normative & compliance

- [B1] Cos'è il Cyber Resilience Act (CRA)?
- [B1] Per quanto tempo si possono conservare i log secondo il GDPR?
- Cos'è DORA (settore finanziario)?
- GDPR: cosa serve davvero a un sito web (cookie, privacy policy)
- Cos'è un DPO e quando è obbligatorio?
- Registro dei trattamenti: chi deve tenerlo?
- Data breach: entro quanto va notificato al Garante?
- Cos'è ISO 27001 (e come si lega a NIS2)?
- Cos'è SOC 2?
- Trasferimento dati extra-UE: cosa dice Schrems II
- Fatturazione elettronica e conservazione sostitutiva: le basi

### Tool comparisons

- [B1] Fail2ban: cos'è e quali alternative esistono?
- ModSecurity è morto? Le alternative moderne
- Pi-hole vs AdGuard Home
- Cloudflare vs self-hosted: il confronto onesto
- Nginx vs Caddy vs Traefik: quale scegliere
- Wazuh vs Wildbox vs ELK per il monitoraggio sicurezza
- CrowdSec vs fail2ban vs caddy-mib

## AI e LLM

### Concepts

- [B1] Cos'è un LLM (Large Language Model)?
- [B1] Cosa sono i token e la context window?
- [B1] Cos'è la temperatura di un LLM?
- [B1] Cos'è la quantizzazione di un modello (GGUF, 4-bit)?
- [B1] Meglio fine-tuning o RAG?
- [B1] Cos'è un agente AI?
- [B1] Cos'è il function calling / tool use?
- [B1] Cosa sono i guardrail per LLM?
- [B1] Cos'è un system prompt?
- [B1] Cosa sono gli embeddings?
- Cos'è l'inferenza (e perché costa)?
- Parametri di un modello: 7B, 70B – cosa significano?
- Cos'è il pretraining (e il post-training)?
- Cos'è RLHF?
- Cos'è la distillazione di un modello?
- Cos'è un modello open-weights (vs open source)?
- Cos'è un vector database?
- Chunking: come si spezzano i documenti per il RAG
- Cos'è il reranking?
- Cos'è la finestra di attenzione / KV cache?
- Cos'è lo streaming delle risposte?
- Cos'è il prompt caching?
- Batch API e inference asincrona: quando usarle
- Cos'è un eval (e perché i benchmark mentono)?
- Cos'è la contaminazione dei benchmark?
- Cos'è il grounding?
- Cos'è la moderazione dei contenuti automatica?
- Multimodalità: testo, immagini, audio nello stesso modello
- Cos'è lo speculative decoding?
- Mixture of Experts (MoE): come funziona
- Cos'è il test-time compute / reasoning?

### Local AI / pratica

- [B1] Come si fa girare un LLM in locale (e che hardware serve)?
- [B1] Cos'è Ollama e come si usa?
- LM Studio vs Ollama vs llama.cpp
- Quanta RAM/VRAM serve per un modello 7B/13B/70B?
- Apple Silicon vs GPU NVIDIA per l'AI locale
- Come si sceglie il modello giusto per un compito
- Come si riducono le allucinazioni in pratica
- Come si scrive un buon prompt (prompt engineering essenziale)
- Come si valuta la qualità delle risposte di un LLM
- Whisper e la trascrizione audio locale
- Generazione di immagini in locale (Stable Diffusion, Flux)
- Come si costruisce un chatbot su documenti aziendali

### AI engineering & agents

- Cos'è l'orchestrazione multi-agente?
- Memoria a breve vs lungo termine negli agenti
- Cos'è il sandboxing per agenti AI?
- Come si limita cosa può fare un agente (permessi, HITL)
- Cos'è l'observability per LLM (tracing, costi)?
- Come si testano le applicazioni LLM?
- Structured output e JSON mode
- Cos'è un MCP server (approfondimento pratico)?

### AI e sicurezza / normative

- [B1] Cosa prevede l'AI Act europeo (e da quando si applica)?
- [B1] Cos'è la shadow AI in azienda?
- Data leakage via LLM: i casi reali
- Gli LLM e il copyright: dove siamo
- Cos'è il watermarking dei contenuti AI?
- Deepfake: come riconoscerli
- Si può usare ChatGPT con dati personali? (GDPR)
- Come si scrive una AI policy aziendale

## Proxmox e self-hosting

### Concepts

- [B1] Come funziona un cluster Proxmox (e cos'è il quorum)?
- [B1] Perché usare ZFS su Proxmox?
- [B1] Che differenza c'è tra snapshot e backup?
- [B1] Cos'è Proxmox Backup Server?
- Cos'è Ceph (e quando ha senso)?
- Cos'è l'alta disponibilità (HA) su Proxmox?
- Storage locale vs condiviso: LVM, ZFS, NFS, Ceph
- Cos'è SDN in Proxmox?
- Cos'è un hypervisor di tipo 1 vs tipo 2?
- Cos'è la paravirtualizzazione (VirtIO)?
- Nested virtualization: quando serve

### How-to

- [B1] Come si fa il passthrough GPU su Proxmox?
- [B1] Come si aggiorna Proxmox senza subscription?
- [B1] Come si usano template e cloud-init su Proxmox?
- [B1] Come si migra da VMware a Proxmox?
- Come si dimensiona un nodo Proxmox (CPU, RAM, dischi)
- Come si configurano i backup automatici verso PBS
- Come si monta uno storage NFS/SMB
- Container privilegiati vs non privilegiati
- Come si passa un disco USB a una VM
- Come si fa la migrazione live tra nodi
- Come si mette Proxmox dietro un reverse proxy
- Home Assistant su Proxmox: la via pulita
- TrueNAS dentro Proxmox: pro e contro
- Come si vira un homelab su low-power (mini PC)

### Troubleshooting

- La VM non parte: i controlli in ordine
- Nodo con la X rossa: quorum perso
- Storage pieno: come liberare spazio senza disastri
- I/O delay alto: capire da dove viene
- La migrazione fallisce: cause tipiche

## Cloudflare e web

### Concepts

- [B1] Cos'è una CDN e quando serve?
- [B1] Quali sono i tipi di record DNS (A, CNAME, MX, TXT)?
- [B1] Cos'è il TTL dei record DNS?
- [B1] Cosa fa la nuvoletta arancione di Cloudflare?
- [B1] Cosa sono i Cloudflare Workers?
- [B1] Cos'è Cloudflare Turnstile?
- [B1] Cosa sono SPF, DKIM e DMARC?
- Cos'è un registrar (e il transfer di un dominio)?
- Cos'è l'anycast?
- Cache HIT, MISS, BYPASS: leggere le risposte di una CDN
- Cos'è un load balancer?
- Cos'è il rate limiting a livello edge?
- Cos'è mTLS per le API (Cloudflare Access)?
- Cos'è R2 (e l'egress gratuito)?
- Pages vs Workers vs Functions: quale usare

### How-to / email

- [B1] Perché le mie email finiscono in spam?
- Come si configura un dominio su Cloudflare da zero
- Come si configura l'email routing di Cloudflare
- Come si imposta DMARC senza rompere la posta
- Come si fa un redirect www → apex (e viceversa)
- Come si serve un sito statico gratis (Pages/GitHub Pages)
- Come si protegge un'origine dietro Cloudflare (IP nascosto)
- Come si diagnostica la propagazione DNS

## Strumenti, web ops e SEO tecnica

- [B1] Cosa sono i Core Web Vitals (LCP, INP, CLS)?
- [B1] Come funziona il file robots.txt?
- [B1] Cos'è il file llms.txt?
- [B1] Cos'è JSON-LD / schema.org e a cosa serve?
- [B1] A cosa serve la sitemap.xml?
- [B1] Quali formati di favicon servono nel 2026?
- Cos'è l'AI Overview di Google (e come ci si finisce)?
- SEO tecnica: il checklist minimo di un sito
- Canonical URL: quando e perché
- Cos'è l'hreflang?
- Open Graph e Twitter Card: le anteprime social
- Cos'è IndexNow?
- Lighthouse e PageSpeed: come leggerli
- Compressione: gzip vs brotli vs zstd
- WebP vs AVIF: formati immagine moderni
- Font web: performance e privacy (self-hosting)
- Cos'è un service worker (e la PWA)?
- Markdown: la sintassi essenziale
- Cos'è un site generator statico (SSG)?
- Git: i comandi che usi davvero
- Cos'è Docker Compose?
- Cron: la sintassi spiegata
- Regex: le basi che servono a tutti

## Musica e creatività

- [B1] Cos'è una DAW?
- [B1] Cosa sono i plugin VST?
- [B1] Come funziona il vinile timecode (DVS)?
- Cos'è il BPM (e come si fa il beatmatching)?
- Cos'è la sidechain compression?
- Latenza audio: perché conta e come si riduce
- Cos'è il mastering (vs mixing)?
- Sample rate e bit depth spiegati
- Cos'è la sintesi sottrattiva/FM?
- Web Audio API: fare musica nel browser
- Come si organizza uno streaming musicale live
- Storia della free tekno in due paragrafi

## Meta / FabGPT-FAQ

- Come aggiungo la mia FAQ a questo motore? (guida al fork)
- Quanto costa far girare FabGPT-FAQ? (zero: la dimostrazione)
- Perché le risposte pre-scritte battono l'AI su domini ristretti
