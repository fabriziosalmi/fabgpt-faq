#!/usr/bin/env python3
"""Author theme-aware concept diagrams as inline SVG -> diagrams.json (id -> svg).

SVGs use CSS variables from style.css so they inherit light/dark automatically
in both the chat and the static pages. Flow connectors carry class `dg-flow`,
animated only under prefers-reduced-motion: no-preference (rules live in style.css).
"""
import json

FONT = "font-family='-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Helvetica,Arial,sans-serif'"


def svg(w, h, body):
    return (f"<svg class='diagram-svg' viewBox='0 0 {w} {h}' width='100%' "
            f"role='img' xmlns='http://www.w3.org/2000/svg' {FONT}>"
            f"<defs><marker id='ah' markerWidth='8' markerHeight='8' refX='6' refY='3' "
            f"orient='auto'><path d='M0,0 L6,3 L0,6 Z' fill='var(--text-dim)'/></marker></defs>"
            f"{body}</svg>")


def box(x, y, w, h, label, accent=False, muted=False):
    stroke = "var(--accent)" if accent else "var(--border)"
    fill = "var(--bg-soft)"
    tcol = "var(--text-dim)" if muted else "var(--text)"
    sw = 2 if accent else 1.3
    lines = label.split("\n")
    line_h = 16
    ty0 = y + (h - (len(lines) - 1) * line_h) / 2 + 4
    txt = "".join(
        f"<text x='{x + w/2}' y='{ty0 + i*line_h}' text-anchor='middle' font-size='13' "
        f"font-weight='{600 if accent and i==0 else 500}' fill='{tcol}'>{l}</text>"
        for i, l in enumerate(lines))
    return (f"<rect x='{x}' y='{y}' width='{w}' height='{h}' rx='8' fill='{fill}' "
            f"stroke='{stroke}' stroke-width='{sw}'/>{txt}")


def arrow(x1, y1, x2, y2, flow=False, label=None):
    cls = " class='dg-flow'" if flow else ""
    dash = " stroke-dasharray='6 5'" if flow else ""
    lab = ""
    if label:
        mx = (x1 + x2) / 2
        my = min(y1, y2) - 8
        lab = (f"<text x='{mx}' y='{my}' text-anchor='middle' font-size='11' "
               f"fill='var(--text-dim)'>{label}</text>")
    return (f"<line x1='{x1}' y1='{y1}' x2='{x2}' y2='{y2}' stroke='var(--text-dim)' "
            f"stroke-width='1.5'{dash}{cls} marker-end='url(#ah)'/>{lab}")


def cap(x, y, text, w=640):
    return (f"<text x='{x}' y='{y}' font-size='12' fill='var(--text-dim)' "
            f"text-anchor='middle'>{text}</text>")


def timeline(steps, caption=None, h=170):
    """Horizontal numbered-step timeline with an animated progress line."""
    n = len(steps)
    m, y = 56, 62
    span = 640 - 2 * m
    xs = [m + (span * i / (n - 1) if n > 1 else 0) for i in range(n)]
    parts = [f"<line x1='{m}' y1='{y}' x2='{640-m}' y2='{y}' stroke='var(--border)' stroke-width='2'/>",
             f"<line x1='{m}' y1='{y}' x2='{640-m}' y2='{y}' stroke='var(--accent)' stroke-width='2' "
             f"stroke-dasharray='6 5' class='dg-flow'/>"]
    for i, (x, step) in enumerate(zip(xs, steps)):
        label = step if isinstance(step, str) else step[0]
        sub = "" if isinstance(step, str) else step[1]
        parts.append(f"<circle cx='{x}' cy='{y}' r='14' fill='var(--accent)'/>"
                     f"<text x='{x}' y='{y+5}' text-anchor='middle' font-size='13' "
                     f"font-weight='700' fill='#fff'>{i+1}</text>")
        for j, ln in enumerate(label.split("\n")):
            parts.append(f"<text x='{x}' y='{y+32+j*15}' text-anchor='middle' font-size='12.5' "
                         f"font-weight='600' fill='var(--text)'>{ln}</text>")
        if sub:
            parts.append(f"<text x='{x}' y='{y-22}' text-anchor='middle' font-size='11' "
                         f"fill='var(--text-dim)'>{sub}</text>")
    if caption:
        parts.append(cap(320, h - 8, caption))
    return svg(640, h, "".join(parts))


D = {}

# 1. WAF: request -> filter -> app
D["cos-e-un-waf"] = svg(640, 200,
    box(20, 70, 110, 56, "Richieste\nHTTP/S") +
    box(250, 65, 140, 66, "WAF Engine\nOWASP CRS", accent=True) +
    box(510, 70, 110, 56, "Applicazione\nBackend") +
    arrow(130, 98, 248, 98, flow=True) +
    arrow(390, 98, 508, 98, flow=True, label="traffico pulito") +
    "<text x='320' y='42' text-anchor='middle' font-size='12.5' fill='var(--accent)' font-weight='600'>ispezione euristica e regex a livello 7</text>" +
    box(250, 150, 140, 36, "SQLi · XSS · BadBot", muted=True) +
    arrow(320, 131, 320, 148) +
    "<text x='425' y='172' font-size='11.5' fill='var(--text-dim)'>403 Forbidden</text>")

D["caddy-waf"] = D["cos-e-un-waf"]
D["patterns"] = svg(640, 200,
    box(20, 70, 110, 56, "OWASP CRS\nUpstream Feed") +
    box(200, 60, 160, 76, "Patterns Pipeline\nDaily Auto-Compiler", accent=True) +
    box(440, 25, 160, 38, "Nginx (map/if)") +
    box(440, 70, 160, 38, "Apache (SecRule)") +
    box(440, 115, 160, 38, "Traefik (middleware)") +
    box(440, 160, 160, 38, "HAProxy (ACLs)") +
    arrow(130, 98, 198, 98, flow=True) +
    arrow(360, 80, 438, 44, flow=True) +
    arrow(360, 95, 438, 89, flow=True) +
    arrow(360, 105, 438, 134, flow=True) +
    arrow(360, 120, 438, 179, flow=True) +
    cap(320, 195, "regole WAF native e anti-bot compilate e rilasciate quotidianamente su GitHub"))

# 2. Reverse proxy & Edge
D["cos-e-un-reverse-proxy"] = svg(640, 220,
    box(20, 84, 100, 52, "Client\nInternet") +
    box(210, 55, 170, 110, "Reverse Proxy\nTLS · Cache · LB\nHeader rewrite", accent=True) +
    box(490, 25, 120, 44, "Microservizio A") +
    box(490, 85, 120, 44, "Microservizio B") +
    box(490, 145, 120, 44, "Microservizio C") +
    arrow(120, 110, 208, 110, flow=True) +
    arrow(380, 85, 488, 47, flow=True) +
    arrow(380, 110, 488, 107, flow=True) +
    arrow(380, 135, 488, 167, flow=True) +
    cap(320, 205, "un unico punto di ingresso sicuro che distribuisce il traffico ai backend"))

D["zion"] = svg(640, 200,
    box(20, 74, 110, 52, "Client Web") +
    box(210, 60, 210, 80, "Zion (Rust Single Binary)\nTLS 1.3 · RAM Cache · WAF", accent=True) +
    box(500, 74, 120, 52, "Backend App") +
    arrow(130, 100, 208, 100, flow=True) +
    arrow(420, 100, 498, 100, flow=True, label="zero-copy") +
    cap(320, 180, "binario statico singolo in Rust con memoria sicura, cache in RAM e SLSA L3"))

# 3. Secure Proxy Manager (Outbound SWG)
D["secure-proxy-manager"] = svg(640, 210,
    box(15, 75, 100, 54, "Client LAN\n/ Server Egress") +
    box(160, 50, 130, 94, "Squid Proxy\n(Port 3128)\nEgress Gate", accent=True) +
    box(340, 25, 130, 65, "WAF (ICAP)\n21 Categories\nFN=0 Gated", accent=True) +
    box(340, 105, 130, 65, "dnsmasq\nDNS Sinkhole\nMalware Block") +
    box(520, 75, 105, 54, "Internet / Cloud\n(Destinazione)") +
    arrow(115, 100, 158, 100, flow=True) +
    arrow(290, 75, 338, 55, flow=True, label="ICAP") +
    arrow(290, 115, 338, 135, flow=True) +
    arrow(470, 60, 518, 90, flow=True) +
    cap(320, 195, "Secure Web Gateway self-hosted: controllo egress default-deny, WAF ICAP e DNS sinkhole"))

# 4. LLM Security Gateway & Proxy
D["llm-security"] = svg(640, 210,
    box(15, 75, 100, 54, "App / Agent\n(OpenAI API)") +
    box(155, 45, 175, 105, "LLMProxy Gateway\nASGI Firewall · PII Mask\nFinOps Budget Router", accent=True) +
    box(390, 20, 120, 36, "OpenAI / Claude") +
    box(390, 62, 120, 36, "Ollama Locale") +
    box(390, 104, 120, 36, "DeepSeek / Groq") +
    box(390, 146, 120, 36, "20+ Providers...") +
    arrow(115, 100, 153, 100, flow=True) +
    arrow(330, 70, 388, 38, flow=True) +
    arrow(330, 90, 388, 80, flow=True) +
    arrow(330, 110, 388, 122, flow=True) +
    arrow(330, 130, 388, 164, flow=True) +
    cap(320, 198, "security gateway LLM: 24 provider, difesa 6 layer, failover automatico e budget control"))

# 5. NIS2 Continuous Posture & Compliance
D["nis2-public"] = svg(640, 200,
    box(15, 65, 110, 64, "Infrastruttura\nHost · Cloud · Web") +
    box(170, 50, 165, 94, "NIS2 Platform Engine\nArt. 21 Technical Audit\nGovernance 30-Checklist", accent=True) +
    box(380, 50, 125, 94, "Remediation\nPlaybook & SOAR\nArt. 23 Incident") +
    box(545, 65, 80, 64, "Report PDF/A\n& Audit Log") +
    arrow(125, 97, 168, 97, flow=True) +
    arrow(335, 97, 378, 97, flow=True) +
    arrow(505, 97, 543, 97, flow=True) +
    cap(320, 182, "posture management continuo NIS2 (EU 2022/2555 & D.Lgs 138/2024) self-hosted on-premise"))

# 6. TCP handshake
D["tcp-handshake"] = svg(640, 210,
    box(40, 20, 140, 44, "Client") +
    box(460, 20, 140, 44, "Server") +
    "<line x1='110' y1='64' x2='110' y2='200' stroke='var(--border)' stroke-width='1.2'/>" +
    "<line x1='530' y1='64' x2='530' y2='200' stroke='var(--border)' stroke-width='1.2'/>" +
    arrow(112, 92, 528, 108, label="SYN") +
    arrow(528, 132, 112, 148, label="SYN-ACK") +
    arrow(112, 172, 528, 188, label="ACK") +
    cap(320, 208, "tre vie: stabilita la connessione, i dati applicativi fluiscono"))

# 7. RAG
D["cos-e-rag"] = svg(640, 200,
    box(16, 74, 96, 52, "Domanda") +
    box(150, 74, 120, 52, "Ricerca\nsemantica", accent=True) +
    box(300, 30, 90, 40, "doc chunk") +
    box(300, 108, 90, 40, "doc chunk") +
    box(430, 74, 96, 52, "LLM", accent=True) +
    box(548, 74, 84, 52, "Risposta\ncitata") +
    arrow(112, 100, 148, 100, flow=True) +
    arrow(270, 88, 300, 62, flow=True) +
    arrow(270, 112, 300, 128, flow=True) +
    arrow(390, 60, 428, 92, flow=True) +
    arrow(390, 128, 428, 108, flow=True) +
    arrow(526, 100, 546, 100, flow=True))

D["rag-security"] = svg(640, 200,
    box(15, 74, 105, 52, "Documento / Query") +
    box(160, 58, 150, 84, "Scanner BACS\nVerifica ACL e PII", accent=True) +
    box(355, 58, 120, 84, "Vector DB\nIsolato (Sandboxed)") +
    box(520, 74, 105, 52, "LLM Shield") +
    arrow(120, 100, 158, 100, flow=True) +
    arrow(310, 100, 353, 100, flow=True, label="filtrato") +
    arrow(475, 100, 518, 100, flow=True) +
    cap(320, 180, "prevenzione di vector poisoning e prompt injection indirette nel RAG"))

# 8. Backup 3-2-1
D["backup-321"] = svg(640, 190,
    "<text x='320' y='30' text-anchor='middle' font-size='13.5' fill='var(--accent)' font-weight='600'>Regola 3-2-1</text>" +
    box(30, 60, 170, 85, "3 copie\ndei dati", accent=True) +
    box(235, 60, 170, 85, "2 supporti\ndiversi") +
    box(440, 60, 170, 85, "1 fuori sede\n(offline/immutabile)") +
    cap(320, 175, "piu un restore provato regolarmente: un backup mai testato e solo una speranza"))

D["borgmatic-client-encryption"] = svg(640, 200,
    box(15, 74, 110, 52, "Dati Server") +
    box(165, 58, 160, 84, "Borgmatic\nCifratura lato client", accent=True) +
    box(365, 74, 105, 52, "Tunnel SSH") +
    box(515, 74, 110, 52, "Repo S3 / Remote\n(Ciphertext)") +
    arrow(125, 100, 163, 100, flow=True) +
    arrow(325, 100, 363, 100, flow=True, label="cifrato") +
    arrow(470, 100, 513, 100, flow=True) +
    cap(320, 180, "deduplicazione e crittografia client-side: il server remoto riceve solo ciphertext"))

# 9. Zero Trust & Hardening
D["zero-trust"] = svg(640, 200,
    box(20, 80, 110, 52, "Richiesta") +
    box(200, 60, 175, 90, "Verifica Continua\nidentita · device\ncontesto · permessi", accent=True) +
    box(470, 40, 140, 44, "Consenti App X") +
    box(470, 115, 140, 44, "Nega / MFA step-up") +
    arrow(130, 105, 198, 105, flow=True) +
    arrow(375, 88, 468, 62, label="verificato") +
    arrow(375, 122, 468, 137, label="anomalo") +
    cap(320, 188, "nessuna fiducia implicita perimetrale · principio del minimo privilegio"))

D["agssh"] = svg(640, 200,
    box(15, 72, 125, 56, "Chiave Hardware\n(ED25519-SK)", accent=True) +
    box(180, 72, 120, 56, "Client SSH\n~/.ssh/config") +
    box(340, 58, 140, 84, "Host nftables\nDefault Drop Port\nRate Limiting") +
    box(520, 72, 105, 56, "Host PVE\nHardened") +
    arrow(140, 100, 178, 100, flow=True, label="FIDO2") +
    arrow(300, 100, 338, 100, flow=True) +
    arrow(480, 100, 518, 100, flow=True) +
    cap(320, 180, "autenticazione a chiave hardware e firewalling rigoroso senza password SSH"))

# 10. SIEM & SOAR
D["cos-e-siem-soar"] = svg(640, 210,
    box(20, 40, 96, 36, "log host") +
    box(20, 88, 96, 36, "log rete") +
    box(20, 136, 96, 36, "log app") +
    box(170, 60, 160, 90, "SIEM Platform\nCorrelazione eventi", accent=True) +
    box(390, 60, 220, 90, "SOAR Playbook\nAutomazione risposta\n(isola host · banna IP · notifica)", accent=True) +
    arrow(116, 58, 168, 84, flow=True) +
    arrow(116, 106, 168, 106, flow=True) +
    arrow(116, 154, 168, 128, flow=True) +
    arrow(330, 106, 388, 106, flow=True) +
    cap(320, 196, "dal rumore dei log all'incidente correlato, dall'incidente all'azione automatica"))

D["wildbox"] = svg(640, 200,
    box(15, 72, 110, 56, "Log / Telemetria\n50+ Threat Feeds") +
    box(165, 56, 165, 88, "Wildbox SecOps\nRegole Sigma · Euristiche\nThreat Analysis LLM", accent=True) +
    box(370, 56, 135, 88, "SOAR Automator\nnftables / WAF Block\nPlaybook YAML") +
    box(545, 72, 80, 56, "SOC Alert\n& Action") +
    arrow(125, 100, 163, 100, flow=True) +
    arrow(330, 100, 368, 100, flow=True, label="minaccia") +
    arrow(505, 100, 543, 100, flow=True) +
    cap(320, 180, "piattaforma unificata SIEM/SOAR self-hosted per rilevamento e contenimento istantaneo"))

# 11. Defense in depth
D["defense-in-depth"] = svg(640, 260,
    "".join(
        f"<circle cx='320' cy='130' r='{r}' fill='none' stroke='var(--accent)' "
        f"stroke-width='1.6' opacity='{op}'/>"
        for r, op in [(118, 0.35), (94, 0.5), (70, 0.7), (46, 0.9)]) +
    "<circle cx='320' cy='130' r='24' fill='var(--accent)'/>" +
    "<text x='320' y='134' text-anchor='middle' font-size='12' fill='#fff' font-weight='600'>dati</text>" +
    "<text x='320' y='40' text-anchor='middle' font-size='12' fill='var(--text-dim)'>firewall</text>" +
    "<text x='320' y='60' text-anchor='middle' font-size='12' fill='var(--text-dim)'>WAF · rate limit</text>" +
    "<text x='320' y='84' text-anchor='middle' font-size='12' fill='var(--text-dim)'>MFA · privilegi minimi</text>" +
    "<text x='320' y='108' text-anchor='middle' font-size='12' fill='var(--text-dim)'>backup</text>" +
    cap(320, 250, "ogni difesa puo fallire: mettile in serie affinche una singola breccia non sia letale"))

# 12. CDN
D["cos-e-cdn"] = svg(640, 220,
    box(270, 88, 100, 44, "Origine", accent=True) +
    "".join(box(x, y, 84, 38, lbl)
            for x, y, lbl in [(30, 20, "edge"), (30, 162, "edge"), (526, 20, "edge"),
                              (526, 162, "edge"), (30, 91, "edge"), (526, 91, "edge")]) +
    arrow(270, 100, 116, 41, flow=True) + arrow(270, 110, 116, 110, flow=True) +
    arrow(270, 120, 116, 179, flow=True) + arrow(370, 100, 524, 41, flow=True) +
    arrow(370, 110, 524, 110, flow=True) + arrow(370, 120, 524, 179, flow=True) +
    cap(320, 208, "stessi contenuti distribuiti vicino a ogni utente (Anycast caching)"))

# 13. AI Agent Loop & MCP
D["ai-agent"] = svg(640, 220,
    box(255, 20, 130, 46, "Osserva", accent=True) +
    box(455, 90, 130, 46, "Agisci\n(chiama tool)", accent=True) +
    box(255, 158, 130, 46, "Legge il\nrisultato") +
    box(55, 90, 130, 46, "Pianifica /\nDecide") +
    arrow(385, 46, 470, 88, flow=True) +
    arrow(520, 136, 400, 172, flow=True) +
    arrow(255, 176, 130, 138, flow=True) +
    arrow(120, 88, 280, 66, flow=True) +
    cap(320, 214, "il ciclo che trasforma il ragionamento del modello in azioni deterministiche"))

D["creare-mcp-server"] = svg(640, 200,
    box(15, 74, 110, 52, "Client AI\n(Claude/Agent)") +
    box(170, 60, 150, 80, "Protocollo MCP\nJSON-RPC 2.0 (Stdio)", accent=True) +
    box(365, 60, 130, 80, "Server MCP\nPython / Node SDK") +
    box(535, 74, 90, 52, "DB / File / API\nRisorse") +
    arrow(125, 100, 168, 100, flow=True) +
    arrow(320, 100, 363, 100, flow=True) +
    arrow(495, 100, 533, 100, flow=True) +
    cap(320, 180, "standard aperto per esporre tool e risorse locali a modelli linguistici con sicurezza"))

D["nanocode"] = svg(640, 200,
    box(15, 74, 115, 52, "Sviluppatore\n(Terminale)") +
    box(175, 60, 145, 80, "Nanocode CLI\nMicro Agent Rust/Go", accent=True) +
    box(365, 60, 125, 80, "L0 Compressor\nContext Pruning") +
    box(530, 74, 95, 52, "LLM Locale\n(Ollama/Local)") +
    arrow(130, 100, 173, 100, flow=True) +
    arrow(320, 100, 363, 100, flow=True) +
    arrow(490, 100, 528, 100, flow=True) +
    cap(320, 180, "coding assistant minimale per shell Unix: zero bloat, zero telemetria e token compressi"))

# 14. Proxmox Cockpit & Autoscaling (Clean non-overlapping layout!)
D["proxxx"] = svg(640, 200,
    box(15, 74, 110, 52, "Terminale\nAdmin SSH") +
    box(165, 58, 160, 84, "proxxx TUI\nAsync Rust Binary", accent=True) +
    box(370, 28, 120, 42, "PVE Cluster") +
    box(370, 80, 120, 42, "ZFS Pools") +
    box(370, 132, 120, 42, "PBS Storage") +
    box(530, 80, 95, 42, "25+ Strumenti\nIntegrati") +
    arrow(125, 100, 163, 100, flow=True) +
    arrow(325, 80, 368, 49, flow=True) +
    arrow(325, 100, 368, 101, flow=True) +
    arrow(325, 120, 368, 153, flow=True) +
    arrow(490, 101, 528, 101, flow=True) +
    cap(320, 192, "cockpit TUI in Rust per il monitoraggio e la gestione completa dell'infrastruttura Proxmox"))

D["proxmox-autoscale"] = svg(640, 200,
    box(15, 65, 115, 60, "VM / LXC\nCarico PVE") +
    box(175, 52, 165, 86, "proxmox-autoscale\nDaemon monitor", accent=True) +
    box(385, 52, 135, 86, "QEMU Agent\nCPU/RAM Hotplug") +
    box(550, 65, 75, 60, "Nodo\nPVE") +
    arrow(130, 95, 173, 95, flow=True) +
    arrow(340, 95, 383, 95, flow=True) +
    arrow(520, 95, 548, 95, flow=True) +
    cap(320, 180, "ridimensionamento dinamico CPU/RAM su Proxmox VE per azzerare crash OOM"))

D["pegaprox"] = svg(640, 200,
    box(15, 68, 115, 56, "Admin / Utente\nLingua IT") +
    box(175, 54, 165, 84, "Pegaprox\nInterfaccia & Traduzione IT", accent=True) +
    box(380, 54, 130, 84, "Template LXC\ne Script Tweak") +
    box(545, 68, 80, 56, "Proxmox VE\nOttimizzato") +
    arrow(130, 96, 173, 96, flow=True) +
    arrow(340, 96, 378, 96, flow=True) +
    arrow(510, 96, 543, 96, flow=True) +
    cap(320, 180, "localizzazione e workflow semplificato per Proxmox curato da Fabrizio Salmi"))

# 15. Storage, Audio & Data encoding
D["b2v"] = svg(640, 200,
    box(15, 74, 110, 52, "File Binario\n(Backup/Tar)") +
    box(170, 58, 150, 84, "b2v Encoder\nMatrice RGB 1080p", accent=True) +
    box(365, 74, 115, 52, "Video MP4\n(Stream Video)") +
    box(525, 74, 100, 52, "Archivio Cold\nIllimitato") +
    arrow(125, 100, 168, 100, flow=True) +
    arrow(320, 100, 363, 100, flow=True) +
    arrow(480, 100, 523, 100, flow=True) +
    cap(320, 180, "codifica di archivi binari in stream video standard per conservazione offline"))

D["mixi"] = svg(640, 200,
    box(15, 72, 120, 56, "Giradischi / DVS\nVinile Timecode") +
    box(180, 56, 155, 88, "MIXI Browser DAW\nWebAudio & WASM", accent=True) +
    box(380, 56, 125, 88, "Sintesi Modulare\ne Mixer 4ch") +
    box(545, 72, 80, 56, "Uscita Audio\n< 5 ms") +
    arrow(135, 100, 178, 100, flow=True, label="1kHz signal") +
    arrow(335, 100, 378, 100, flow=True) +
    arrow(505, 100, 543, 100, flow=True) +
    cap(320, 180, "workstation audio deterministica browser-native a bassissima latenza"))

# 16. Token compression & MLX
D["l0-compressor"] = svg(640, 200,
    box(15, 74, 110, 52, "Prompt / Log\n(10k tokens)") +
    box(170, 58, 160, 84, "L0 Compressor\nToken Pruning & Summary", accent=True) +
    box(375, 74, 115, 52, "Prompt Snello\n(4k tokens)") +
    box(530, 74, 95, 52, "LLM Engine\n-60% Costi") +
    arrow(125, 100, 168, 100, flow=True) +
    arrow(330, 100, 373, 100, flow=True, label="compresso") +
    arrow(490, 100, 528, 100, flow=True) +
    cap(320, 180, "riduzione dei token e preservazione del contesto semantico per loop agentici"))

D["silicondev"] = svg(640, 200,
    box(15, 74, 115, 52, "Dataset JSONL\nPersonalizzato") +
    box(175, 58, 155, 84, "Apple MLX Framework\nLoRA on Metal / MPS", accent=True) +
    box(375, 74, 115, 52, "Adattatori LoRA\n(Pesi Delta)") +
    box(530, 74, 95, 52, "Modello Fuso\nGGUF / FP16") +
    arrow(130, 100, 173, 100, flow=True) +
    arrow(330, 100, 373, 100, flow=True) +
    arrow(490, 100, 528, 100, flow=True) +
    cap(320, 180, "fine-tuning nativo ad altissima velocità su memoria unificata Apple Silicon"))

# ---------- Timelines ----------

D["dmarc-rollout"] = timeline(
    [("p=none", "osserva"), ("p=quarantine\npct 25%", "a tappe"), ("p=reject", "quando pulito")],
    "rollout graduale: prima osservi coi report, poi stringi le policy di rifiuto")

D["nist-ir-lifecycle"] = timeline(
    ["Preparazione", "Detection\n& Analysis", "Contenimento", "Eradicazione", "Recovery", "Lessons\nlearned"],
    "un ciclo, non una retta: si torna indietro quando serve per contenere la minaccia", h=176)

D["flareover"] = timeline(
    ["assess", "prepare", "present", "execute", "guard"],
    "migrazione deterministica: zero configurazioni che cambiano comportamento in silenzio")

D["come-funziona-acme"] = timeline(
    [("Richiesta", "certmate/ACME"), ("Challenge", "http-01 / dns-01"), ("Verifica", "controllo dominio"),
     ("Certificato", "valido 90 giorni"), ("Rinnovo", "automatico")],
    "il rinnovo va automatizzato: i certificati a 90 giorni non sono un optional")

D["certmate"] = D["come-funziona-acme"]

D["vmware-migrazione"] = timeline(
    [("Assess", "MAC e rete"), ("VirtIO", "driver guest"), ("Import", "diretto da ESXi"),
     ("A ondate", "prima VM test")],
    "dal PVE 8.2 l'import da ESXi e integrato e diretto")

D["incident-response"] = timeline(
    [("Contieni", "isola, non spegnere"), ("Preserva", "RAM e log"), ("Capisci", "estensione prima"),
     ("Comunica", "fuori banda")],
    "le prime ore decidono se e un incidente gestito o un disastro operativo")

json.dump(D, open("/Users/fab/Documents/git/fabgpt-faq/diagrams.json", "w"),
          ensure_ascii=False, indent=1)
print(f"diagrams.json: {len(D)} diagrams generated.")
