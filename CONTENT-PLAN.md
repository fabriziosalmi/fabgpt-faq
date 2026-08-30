# Content plan – the 10x knowledge base

**PASS 1 COMPLETE (2026-08-29): every backlog line below is shipped ([B1]-[B6]) or
explicitly merged. KB at 303 entries, 305 URLs, bench green. Next: Fase 2.**

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
- [B2] Cos'è il phishing (e lo spear phishing)?
- [B2] Cos'è un ransomware e come ci si prepara?
- [B2] Cos'è un honeypot?
- [B2] Cos'è un SOC (Security Operations Center)?
- [B2] EDR, XDR, antivirus: che differenza c'è?
- [B2] Cos'è la threat intelligence?
- [B2] Cos'è una CVE (e il punteggio CVSS)?
- [B2] Vulnerability assessment vs penetration test: differenze
- [B2] Cos'è un bug bounty (e come funziona HackerOne)?
- [B2] Cos'è l'OSINT?
- [B2] Firewall di rete vs WAF: che differenza c'è?
- [B2] VPN vs proxy: cosa cambia?
- [B2] Cos'è il principio del minimo privilegio?
- [B2] Cosa sono IDS e IPS?
- [B2] Cos'è la defense in depth?
- [B2] Cos'è un attacco man-in-the-middle?
- [B2] Cos'è il DNS spoofing/poisoning?
- [B2] Cos'è un attacco brute force (e il credential stuffing)?
- [B2] Cos'è una botnet?
- [B2] Cos'è il typosquatting (e il domain squatting)?
- [B6] Cosa sono i data breach più famosi e cosa insegnano?
- [B2] Password manager: perché usarne uno
- [B2] Passkey: la fine delle password?
- [B2] Cos'è la crittografia end-to-end?
- [B2] Crittografia simmetrica vs asimmetrica
- [B2] Cos'è l'hashing (e perché bcrypt/argon2)?
- [B2] Cos'è un certificato wildcard (e i SAN)?
- [B2] Cos'è mTLS (mutual TLS)?
- [B2] Cos'è HSTS e il preload?
- [B2] Cos'è DNSSEC?
- [B2] Cos'è DNS-over-HTTPS (DoH) / DNS-over-TLS?
- [B2] Cos'è un air gap?
- [B2] Cos'è la steganografia?
- [B6] Sicurezza fisica dei server: le basi

### How-to / hardening

- [B1] Come si mette in sicurezza SSH su un server esposto?
- [B1] Quali security header HTTP servono davvero?
- [B1] Come si bloccano i crawler AI (GPTBot & co.)?
- [B2] Come si fa l'hardening di un server Linux appena installato?
- [B2] Come si configura HTTPS su Nginx?
- [B2] Come si configura HTTPS su Caddy (automatico)?
- [B2] Come si difende un sito dallo scraping?
- [B6] Come si limita l'accesso a un'area admin (IP allowlist, auth)?
- [B2] Come si gestiscono i secrets (e perché non in git)?
- [B2] Come si fa un backup 3-2-1?
- [B2] Come si verifica se una password è stata compromessa?
- [B2] Come si segmenta una rete domestica/aziendale (VLAN)?
- [B2] Come si espone un servizio self-hosted senza aprire porte (tunnel)?
- [merged: coperto da secure-web-gateway in B1] Come si controlla cosa esce dalla propria rete (egress)?
- [B2] Come si firma il codice (e perché)?
- [B2] Come si fa security logging fatto bene?
- [B2] Come si risponde a un incidente: le prime ore
- [B2] Come si scrive un piano di disaster recovery minimo

### Errors & troubleshooting

- [B1] Errore ERR_CERT_AUTHORITY_INVALID: cosa significa?
- [B1] Errore 502 Bad Gateway: cause e soluzioni
- [B1] Errore 429 Too Many Requests: cosa fare?
- [B1] Cos'è il mixed content e come si risolve?
- [B2] Errore 403 Forbidden: le cause tipiche
- [B2] Errore SSL_ERROR_NO_CYPHER_OVERLAP / handshake failure
- [B2] ERR_TOO_MANY_REDIRECTS: il loop di redirect
- [B2] Il sito è lento solo per alcuni: come si diagnostica
- [B2] "Sito ingannevole in vista": come uscire dalla blocklist Google Safe Browsing

### Normative & compliance

- [B1] Cos'è il Cyber Resilience Act (CRA)?
- [B1] Per quanto tempo si possono conservare i log secondo il GDPR?
- [B2] Cos'è DORA (settore finanziario)?
- [B2] GDPR: cosa serve davvero a un sito web (cookie, privacy policy)
- [B2] Cos'è un DPO e quando è obbligatorio?
- [B2] Registro dei trattamenti: chi deve tenerlo?
- [B2] Data breach: entro quanto va notificato al Garante?
- [B2] Cos'è ISO 27001 (e come si lega a NIS2)?
- [B2] Cos'è SOC 2?
- [B2] Trasferimento dati extra-UE: cosa dice Schrems II
- [B6] Fatturazione elettronica e conservazione sostitutiva: le basi

### Tool comparisons

- [B1] Fail2ban: cos'è e quali alternative esistono?
- [B2] ModSecurity è morto? Le alternative moderne
- [B2] Pi-hole vs AdGuard Home
- [B2] Cloudflare vs self-hosted: il confronto onesto
- [B2] Nginx vs Caddy vs Traefik: quale scegliere
- [B2] Wazuh vs Wildbox vs ELK per il monitoraggio sicurezza
- [merged: coperto da fail2ban-e-alternative in B2] CrowdSec vs fail2ban vs caddy-mib

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
- [B3] Cos'è l'inferenza (e perché costa)?
- [B3] Parametri di un modello: 7B, 70B – cosa significano?
- [B3] Cos'è il pretraining (e il post-training)?
- [B3] Cos'è RLHF?
- [B3] Cos'è la distillazione di un modello?
- [B3] Cos'è un modello open-weights (vs open source)?
- [B3] Cos'è un vector database?
- [B3] Chunking: come si spezzano i documenti per il RAG
- [B3] Cos'è il reranking?
- [B3] Cos'è la finestra di attenzione / KV cache?
- [B3] Cos'è lo streaming delle risposte?
- [B3] Cos'è il prompt caching?
- [B3] Batch API e inference asincrona: quando usarle
- [B3] Cos'è un eval (e perché i benchmark mentono)?
- [B3] Cos'è la contaminazione dei benchmark?
- [B3] Cos'è il grounding?
- [B3] Cos'è la moderazione dei contenuti automatica?
- [B3] Multimodalità: testo, immagini, audio nello stesso modello
- [B3] Cos'è lo speculative decoding?
- [B3] Mixture of Experts (MoE): come funziona
- [B3] Cos'è il test-time compute / reasoning?

### Local AI / pratica

- [B1] Come si fa girare un LLM in locale (e che hardware serve)?
- [B1] Cos'è Ollama e come si usa?
- [B3] LM Studio vs Ollama vs llama.cpp
- [B3] Quanta RAM/VRAM serve per un modello 7B/13B/70B?
- [B3] Apple Silicon vs GPU NVIDIA per l'AI locale
- [B3] Come si sceglie il modello giusto per un compito
- [B3] Come si riducono le allucinazioni in pratica
- [B3] Come si scrive un buon prompt (prompt engineering essenziale)
- [B3] Come si valuta la qualità delle risposte di un LLM
- [B3] Whisper e la trascrizione audio locale
- [B3] Generazione di immagini in locale (Stable Diffusion, Flux)
- [B3] Come si costruisce un chatbot su documenti aziendali

### AI engineering & agents

- [B3] Cos'è l'orchestrazione multi-agente?
- [B3] Memoria a breve vs lungo termine negli agenti
- [B3] Cos'è il sandboxing per agenti AI?
- [B3] Come si limita cosa può fare un agente (permessi, HITL)
- [B3] Cos'è l'observability per LLM (tracing, costi)?
- [B3] Come si testano le applicazioni LLM?
- [B3] Structured output e JSON mode
- [B3] Cos'è un MCP server (approfondimento pratico)?

### AI e sicurezza / normative

- [B1] Cosa prevede l'AI Act europeo (e da quando si applica)?
- [B1] Cos'è la shadow AI in azienda?
- [B3] Data leakage via LLM: i casi reali
- [B3] Gli LLM e il copyright: dove siamo
- [B3] Cos'è il watermarking dei contenuti AI?
- [B3] Deepfake: come riconoscerli
- [B3] Si può usare ChatGPT con dati personali? (GDPR)
- [B3] Come si scrive una AI policy aziendale

## Proxmox e self-hosting

### Concepts

- [B1] Come funziona un cluster Proxmox (e cos'è il quorum)?
- [B1] Perché usare ZFS su Proxmox?
- [B1] Che differenza c'è tra snapshot e backup?
- [B1] Cos'è Proxmox Backup Server?
- [B4] Cos'è Ceph (e quando ha senso)?
- [B4] Cos'è l'alta disponibilità (HA) su Proxmox?
- [B4] Storage locale vs condiviso: LVM, ZFS, NFS, Ceph
- [B4] Cos'è SDN in Proxmox?
- [B4] Cos'è un hypervisor di tipo 1 vs tipo 2?
- [B4] Cos'è la paravirtualizzazione (VirtIO)?
- [B4] Nested virtualization: quando serve

### How-to

- [B1] Come si fa il passthrough GPU su Proxmox?
- [B1] Come si aggiorna Proxmox senza subscription?
- [B1] Come si usano template e cloud-init su Proxmox?
- [B1] Come si migra da VMware a Proxmox?
- [B4] Come si dimensiona un nodo Proxmox (CPU, RAM, dischi)
- [B4] Come si configurano i backup automatici verso PBS
- [B4] Come si monta uno storage NFS/SMB
- [B4] Container privilegiati vs non privilegiati
- [B4] Come si passa un disco USB a una VM
- [B4] Come si fa la migrazione live tra nodi
- [B4] Come si mette Proxmox dietro un reverse proxy
- [B4] Home Assistant su Proxmox: la via pulita
- [B4] TrueNAS dentro Proxmox: pro e contro
- [B4] Come si vira un homelab su low-power (mini PC)
- [B4] Come si installa e configura LXC AutoScale? (guida)
- [B4] Come si installa e configura VM Autoscale? (guida)
- [B4] Come si usa proxxx: installazione e primi comandi (guida)

### Troubleshooting

- [B4] La VM non parte: i controlli in ordine
- [B4] Nodo con la X rossa: quorum perso
- [B4] Storage pieno: come liberare spazio senza disastri
- [B4] I/O delay alto: capire da dove viene
- [B4] La migrazione fallisce: cause tipiche

## Cloudflare e web

### Concepts

- [B1] Cos'è una CDN e quando serve?
- [B1] Quali sono i tipi di record DNS (A, CNAME, MX, TXT)?
- [B1] Cos'è il TTL dei record DNS?
- [B1] Cosa fa la nuvoletta arancione di Cloudflare?
- [B1] Cosa sono i Cloudflare Workers?
- [B1] Cos'è Cloudflare Turnstile?
- [B1] Cosa sono SPF, DKIM e DMARC?
- [B5] Cos'è un registrar (e il transfer di un dominio)?
- [B5] Cos'è l'anycast?
- [B5] Cache HIT, MISS, BYPASS: leggere le risposte di una CDN
- [B5] Cos'è un load balancer?
- [merged: coperto da limits + errore-429] Cos'è il rate limiting a livello edge?
- [merged: coperto da mTLS in B2] Cos'è mTLS per le API (Cloudflare Access)?
- [B5] Cos'è R2 (e l'egress gratuito)?
- [B5] Pages vs Workers vs Functions: quale usare

### How-to / email

- [B1] Perché le mie email finiscono in spam?
- [B5] Come si configura un dominio su Cloudflare da zero
- [B5] Come si configura l'email routing di Cloudflare
- [B5] Come si imposta DMARC senza rompere la posta
- [B5] Come si fa un redirect www → apex (e viceversa)
- [B5] Come si serve un sito statico gratis (Pages/GitHub Pages)
- [B5] Come si protegge un'origine dietro Cloudflare (IP nascosto)
- [B5] Come si diagnostica la propagazione DNS

## Strumenti, web ops e SEO tecnica

- [B1] Cosa sono i Core Web Vitals (LCP, INP, CLS)?
- [B1] Come funziona il file robots.txt?
- [B1] Cos'è il file llms.txt?
- [B1] Cos'è JSON-LD / schema.org e a cosa serve?
- [B1] A cosa serve la sitemap.xml?
- [B1] Quali formati di favicon servono nel 2026?
- [B5] Cos'è l'AI Overview di Google (e come ci si finisce)?
- [B5] SEO tecnica: il checklist minimo di un sito
- [B5] Canonical URL: quando e perché
- [B5] Cos'è l'hreflang?
- [B5] Open Graph e Twitter Card: le anteprime social
- [B5] Cos'è IndexNow?
- [B5] Lighthouse e PageSpeed: come leggerli
- [B5] Compressione: gzip vs brotli vs zstd
- [B5] WebP vs AVIF: formati immagine moderni
- [B5] Font web: performance e privacy (self-hosting)
- [B5] Cos'è un service worker (e la PWA)?
- [B5] Markdown: la sintassi essenziale
- [B5] Cos'è un site generator statico (SSG)?
- [B5] Git: i comandi che usi davvero
- [B5] Cos'è Docker Compose?
- [B5] Cron: la sintassi spiegata
- [B5] Regex: le basi che servono a tutti

## Musica e creatività

- [B1] Cos'è una DAW?
- [B1] Cosa sono i plugin VST?
- [B1] Come funziona il vinile timecode (DVS)?
- [B6] Cos'è il BPM (e come si fa il beatmatching)?
- [B6] Cos'è la sidechain compression?
- [B6] Latenza audio: perché conta e come si riduce
- [B6] Cos'è il mastering (vs mixing)?
- [B6] Sample rate e bit depth spiegati
- [B6] Cos'è la sintesi sottrattiva/FM?
- [B6] Web Audio API: fare musica nel browser
- [B6] Come si organizza uno streaming musicale live
- [B6] Storia della free tekno in due paragrafi

## Massa utile — programma glossario (dalle 400 domande in Noted)

Fonte: nota "fabgpt-faq altre domande" (400 domande, 40 temi cyber/AI/self-host
2026-2027). Tooling: `python3 triage.py` (o `triage.py questions.txt`) scora ogni
domanda contro la KB e la classa covered(>=2.5)/partial/gap. La nota grezza è in
`.triage400.json`. Obiettivo dichiarato da Fab: **per ogni termine una voce KB
corretta e utile** — quindi i "partial" (agganciano una voce vicina ma il termine
non ha pagina propria) sono lavoro, non copertura.

- Baseline (pre-B7): 127 covered, 249 partial, 24 gap.
- **B7 (mass #1, 37 voci)**: coperti tutti i 24 gap netti + i concetti-cardine più
  densi (rete/OSI/NAT/NGFW/BGP/IPsec/WireGuard, IAM/SAML-OAuth-OIDC/PAM/YubiKey,
  crypto/PQC/HNDL, threat/infostealer/hunting/detection, appsec/SSRF/container/
  CNAPP/DevSecOps, AI-agentic security/MCP/guardrail/RAG-sec/AIBOM/observability,
  privacy/deGoogle/immutable-OS/Matrix/kill-switch). Post-B7: 166 covered, 228
  partial, 6 gap.
- **B8 (mass #2, 34 voci)**: macro-blocco **self-hosting sovrano & privacy** —
  cloud personale (Nextcloud/Immich/Jellyfin/Vaultwarden/Syncthing), domotica
  locale (Zigbee/Matter/Zigbee2MQTT/ESPHome/Frigate/Node-RED), backup avanzati
  (Restic-Borg/DB consistenti), AI self-host (Open WebUI/ChatGPT privato), email
  indipendente (self-host/MTA-STS-DANE/ARC/Rspamd/alias/PGP-SMIME), privacy &
  anonimato (Tails-Whonix/VeraCrypt/MAT2/offuscamento-censura), sovranità UE
  (cloud provider EU/Proton-Tuta/SearXNG/DMA-DSA-DataAct/fediverso), messaggistica
  sovrana (VoIP/team-chat). Post-B8: 199 covered, 197 partial, 4 gap.
- **B9 (mass #3, 36 voci)**: blocco **threat/malware/forensics + endpoint hardening**.
  Threat/malware (Living-off-the-Land, process injection/DLL sideloading, MITRE
  ATT&CK, AD attacks/Kerberoasting, Pass-the-Hash, dependency confusion, insider
  threat, rootkit/bootkit, malware polimorfico). SOC ops (SIEM/SOAR/XDR, alert
  fatigue, NDR, MTTD/MTTR, playbook SOAR). Forensics/IR (fasi NIST, chain of
  custody, memory forensics, artefatti Windows, tabletop exercise, DC compromesso,
  crisis communication). Endpoint/kernel hardening (Secure Boot, USBGuard/BadUSB,
  eBPF, sandbox app Flatpak/Snap, MTE, security baselines CIS/Ansible, impianti
  hardware/firmware, NFC/RFID). AI security (Direct vs Indirect injection, model
  inversion/membership inference, NIST AI RMF, UEBA, runaway agent, seccomp/gVisor,
  agent exfiltration via Markdown). Post-B9: 228 covered, 170 partial, 2 gap.
- **B10 (mass #4, 35 voci)**: **storage/NAS + networking pro + IAM avanzato +
  crypto avanzata + appsec authz**. Storage/NAS (OpenZFS, RAM ECC, RAID/RAIDZ,
  cifratura a riposo LUKS/ZFS, SMART monitoring). Networking pro (WireGuard vs
  OpenVPN, Headscale, Multi-WAN, mDNS reflector, BGP+BFD, GeoIP filtering, switch
  L2/L3, PCAP over SSH, MTU/MSS). Homelab (Raspberry/SBC, UPS/NUT, Prometheus/
  Grafana). IAM avanzato (ZTNA, AiTM, conditional access, CAE, RBAC/ABAC/PBAC,
  shared responsibility). Container/cloud (K8s security, container breakout).
  Crypto avanzata (TLS 1.3, FHE, crypto-agility). Appsec authz (IDOR/BOLA, mass
  assignment, cookie flags, insecure deserialization, OAuth redirect, OAuth2-Proxy/
  Authelia, DB bind localhost). Post-B10: 257 covered, 142 partial, 1 gap.
- Prossimi giri di massa: convertire i ~142 partial in voci dedicate a blocchi
  tematici (ogni giro riesegue `triage.py` per misurare l'avanzamento).

## Giro 2 – rifinitura & answer-engine optimization (DONE 2026-08-30)

Non nuovi argomenti (quelli erano i lotti di massa) ma polish sulla base esistente,
mirato all'obiettivo AI Overview + ai gap "predica bene e razzola male":

- **Open Graph + Twitter Card** su ogni pagina statica e sulla chat (il sito
  insegnava OG e non li aveva); immagine social condivisa `og.svg`.
- **llms.txt** (mappa concisa) + **llms-full.txt** (corpus completo, ~512KB) — il
  sito predicava llms.txt e ora ce l'ha.
- **JSON-LD arricchito**: FAQPage + **BreadcrumbList** per pagina, **WebSite +
  Organization** + FAQPage sull'indice; breadcrumb visivo in cima alle pagine.
- **404.html** branded; `robots` meta con max-image-preview.
- **Contenuti**: fallback da 3 a 7 (più vari e utili), varianti di risposta
  "in una riga" su 11 pilastri (WAF, reverse proxy, LLM, RAG, agente, Proxmox,
  Zero Trust, LLM locale, backup 3-2-1, AI Overview, Zion) per il repeat-ask.
- bench G1 esteso: valida gli slug di `suggest` (entries + config).

## Fase 2 – "livello super" (dopo il primo giro di contenuti)

Richieste di Fab, in ordine:

- **[FATTA 2026-08-29] Domande suggerite in relazione al thread**: dopo ogni
  risposta 2-3 chip cliccabili con domande correlate. Fonte dati: campo `suggest`
  (slug) su OGNI voce, derivato dai link interni `q/<slug>/` gia scritti nelle
  risposte (le cross-reference curate a mano) + padding con vicini di verticale;
  generato da scripts/gen_suggest.py, validato da bench G1. UI in app.js:
  renderChips() dopo lo streaming, filtra le voci gia chieste (askedSlugs =
  thread history), click = ask(question canonica). Chip iniziali dopo il welcome
  da config.suggest. Anche gli intenti smalltalk con `suggest` mostrano chip.
  build.py usa gli stessi suggest per "Altre domande" delle pagine statiche.
- Altre risposte "pronte" contestuali al filo del discorso (follow-up naturali
  per ogni voce, es. variante "approfondisci" / "esempio pratico").

**Smalltalk v2 DONE (2026-08-29)**: 22 -> 33 intenti, piu varianti per intento,
risposte che instradano con percorsi suggeriti, e campo `suggest` (slug delle
voci correlate) su 14 intenti — gia pronto come sorgente dati per i chip della
Fase 2. Intenti nuovi: prezzo, privacy, come-funzioni, contatto-fab, progetti-
suggerisci, noia, sei-umano, scusa, approfondisci, perche-italiano, buon-lavoro.

## Meta / FabGPT-FAQ

- [B6] Come aggiungo la mia FAQ a questo motore? (guida al fork)
- [B6] Quanto costa far girare FabGPT-FAQ? (zero: la dimostrazione)
- [B6] Perché le risposte pre-scritte battono l'AI su domini ristretti
