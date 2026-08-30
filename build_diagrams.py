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
            f"<defs><marker id='ah' markerWidth='9' markerHeight='9' refX='7' refY='3' "
            f"orient='auto'><path d='M0,0 L7,3 L0,6 Z' fill='var(--text-dim)'/></marker></defs>"
            f"{body}</svg>")


def box(x, y, w, h, label, accent=False, muted=False):
    stroke = "var(--accent)" if accent else "var(--border)"
    fill = "var(--bg-soft)"
    tcol = "var(--text-dim)" if muted else "var(--text)"
    sw = 2 if accent else 1.4
    lines = label.split("\n")
    ty0 = y + h / 2 - (len(lines) - 1) * 9 + 5
    txt = "".join(
        f"<text x='{x + w/2}' y='{ty0 + i*18}' text-anchor='middle' font-size='15' "
        f"font-weight='{600 if accent and i==0 else 500}' fill='{tcol}'>{l}</text>"
        for i, l in enumerate(lines))
    return (f"<rect x='{x}' y='{y}' width='{w}' height='{h}' rx='10' fill='{fill}' "
            f"stroke='{stroke}' stroke-width='{sw}'/>{txt}")


def arrow(x1, y1, x2, y2, flow=False, label=None):
    cls = " class='dg-flow'" if flow else ""
    dash = " stroke-dasharray='6 5'" if flow else ""
    lab = ""
    if label:
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2 - 8
        lab = (f"<text x='{mx}' y='{my}' text-anchor='middle' font-size='12' "
               f"fill='var(--text-dim)'>{label}</text>")
    return (f"<line x1='{x1}' y1='{y1}' x2='{x2}' y2='{y2}' stroke='var(--text-dim)' "
            f"stroke-width='1.6'{dash}{cls} marker-end='url(#ah)'/>{lab}")


def cap(x, y, text, w=640):
    return (f"<text x='{x}' y='{y}' font-size='12.5' fill='var(--text-dim)' "
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
        parts.append(f"<circle cx='{x}' cy='{y}' r='15' fill='var(--accent)'/>"
                     f"<text x='{x}' y='{y+5}' text-anchor='middle' font-size='14' "
                     f"font-weight='700' fill='#fff'>{i+1}</text>")
        for j, ln in enumerate(label.split("\n")):
            parts.append(f"<text x='{x}' y='{y+34+j*16}' text-anchor='middle' font-size='13' "
                         f"font-weight='600' fill='var(--text)'>{ln}</text>")
        if sub:
            parts.append(f"<text x='{x}' y='{y-26}' text-anchor='middle' font-size='11.5' "
                         f"fill='var(--text-dim)'>{sub}</text>")
    if caption:
        parts.append(cap(320, h - 8, caption))
    return svg(640, h, "".join(parts))


D = {}

# 1. WAF: request -> filter -> app
D["cos-e-un-waf"] = svg(640, 200,
    box(20, 70, 120, 56, "Richieste") +
    box(260, 70, 120, 56, "WAF", accent=True) +
    box(500, 70, 120, 56, "App") +
    arrow(140, 98, 258, 98, flow=True) +
    arrow(382, 98, 498, 98, flow=True, label="pulite") +
    "<text x='320' y='45' text-anchor='middle' font-size='13' fill='var(--accent)' font-weight='600'>ispeziona ogni richiesta HTTP</text>" +
    box(260, 150, 120, 40, "SQLi · XSS · bot", muted=True) +
    arrow(320, 128, 320, 148) +
    "<text x='395' y='174' font-size='12' fill='var(--text-dim)'>bloccate</text>")

D["caddy-waf"] = D["cos-e-un-waf"]

# 2. Reverse proxy
D["cos-e-un-reverse-proxy"] = svg(640, 220,
    box(20, 84, 110, 52, "Client") +
    box(240, 60, 160, 100, "Reverse proxy\nTLS · cache · LB", accent=True) +
    box(520, 30, 100, 44, "app A") +
    box(520, 88, 100, 44, "app B") +
    box(520, 146, 100, 44, "app C") +
    arrow(130, 110, 238, 110, flow=True) +
    arrow(400, 90, 518, 52, flow=True) +
    arrow(400, 110, 518, 110, flow=True) +
    arrow(400, 130, 518, 168, flow=True))

D["zion"] = svg(640, 200,
    box(20, 74, 110, 52, "Client") +
    box(220, 60, 200, 80, "Zion (Rust Proxy)\nTLS 1.3 · RAM Cache · WAF", accent=True) +
    box(500, 74, 120, 52, "Backend App") +
    arrow(130, 100, 218, 100, flow=True) +
    arrow(420, 100, 498, 100, flow=True, label="zero latenza") +
    cap(320, 180, "binario statico singolo in Rust con memoria sicura e performance estreme"))

# 3. TCP handshake
D["tcp-handshake"] = svg(640, 210,
    box(40, 20, 140, 44, "Client") +
    box(460, 20, 140, 44, "Server") +
    "<line x1='110' y1='64' x2='110' y2='200' stroke='var(--border)' stroke-width='1.2'/>" +
    "<line x1='530' y1='64' x2='530' y2='200' stroke='var(--border)' stroke-width='1.2'/>" +
    arrow(112, 92, 528, 108, label="SYN") +
    arrow(528, 132, 112, 148, label="SYN-ACK") +
    arrow(112, 172, 528, 188, label="ACK") +
    cap(320, 210, "tre vie: poi i dati scorrono"))

# 4. RAG
D["cos-e-rag"] = svg(640, 200,
    box(16, 74, 96, 52, "Domanda") +
    box(150, 74, 120, 52, "Ricerca\nsemantica", accent=True) +
    box(300, 30, 90, 40, "doc") +
    box(300, 108, 90, 40, "doc") +
    box(430, 74, 96, 52, "LLM", accent=True) +
    box(548, 74, 84, 52, "Risposta\ncitata") +
    arrow(112, 100, 148, 100, flow=True) +
    arrow(270, 88, 300, 62, flow=True) +
    arrow(270, 112, 300, 128, flow=True) +
    arrow(390, 60, 428, 92, flow=True) +
    arrow(390, 128, 428, 108, flow=True) +
    arrow(526, 100, 546, 100, flow=True))

D["rag-security"] = svg(640, 200,
    box(20, 74, 110, 52, "Documento") +
    box(180, 60, 140, 80, "Scanner BACS\nVerifica ACL e PII", accent=True) +
    box(370, 60, 110, 80, "Vector DB\nIsolato") +
    box(530, 74, 90, 52, "LLM Shield") +
    arrow(130, 100, 178, 100, flow=True) +
    arrow(320, 100, 368, 100, flow=True, label="pulito") +
    arrow(480, 100, 528, 100, flow=True) +
    cap(320, 180, "prevenzione di vector poisoning e prompt injection indirette nel RAG"))

# 5. Backup 3-2-1
D["backup-321"] = svg(640, 190,
    "<text x='320' y='30' text-anchor='middle' font-size='14' fill='var(--accent)' font-weight='600'>Regola 3-2-1</text>" +
    box(30, 60, 170, 90, "3 copie\ndei dati", accent=True) +
    box(235, 60, 170, 90, "2 supporti\ndiversi") +
    box(440, 60, 170, 90, "1 fuori sede\n(offline/immutabile)") +
    cap(320, 178, "piu un restore provato: un backup mai ripristinato e una speranza"))

D["borgmatic-client-encryption"] = svg(640, 200,
    box(20, 74, 120, 52, "Dati Server") +
    box(190, 60, 160, 80, "Borgmatic\nCifratura lato client", accent=True) +
    box(400, 74, 100, 52, "Tunnel SSH") +
    box(540, 74, 80, 52, "Repo S3\nRemoto") +
    arrow(140, 100, 188, 100, flow=True) +
    arrow(350, 100, 398, 100, flow=True, label="cifrato") +
    arrow(500, 100, 538, 100, flow=True) +
    cap(320, 180, "deduplicazione e crittografia client-side: il server remoto vede solo ciphertext"))

# 6. Zero Trust & Hardening
D["zero-trust"] = svg(640, 200,
    box(20, 80, 120, 52, "Richiesta") +
    box(240, 62, 160, 88, "Verifica ogni volta\nidentita · device\ncontesto", accent=True) +
    box(500, 40, 120, 44, "Accesso\nall'app X") +
    box(500, 118, 120, 44, "Nega") +
    arrow(140, 106, 238, 106, flow=True) +
    arrow(400, 90, 498, 62, label="ok") +
    arrow(400, 120, 498, 140, label="rischio") +
    cap(320, 190, "nessuna fiducia implicita · minimo privilegio"))

D["agssh"] = svg(640, 200,
    box(20, 74, 120, 52, "YubiKey FIDO2\n(ED25519-SK)", accent=True) +
    box(200, 74, 120, 52, "Client SSH\n~/.ssh/config") +
    box(380, 60, 120, 80, "Firewall Host\nnftables default drop") +
    box(540, 74, 80, 52, "Host PVE\nHardened") +
    arrow(140, 100, 198, 100, flow=True, label="pin/touch") +
    arrow(320, 100, 378, 100, flow=True) +
    arrow(500, 100, 538, 100, flow=True) +
    cap(320, 180, "autenticazione a chiave hardware e porta SSH isolata senza password"))

# 7. SIEM & SOAR
D["cos-e-siem-soar"] = svg(640, 210,
    box(20, 40, 96, 36, "log host") +
    box(20, 88, 96, 36, "log rete") +
    box(20, 136, 96, 36, "log app") +
    box(190, 62, 150, 86, "SIEM\ncorrela gli eventi", accent=True) +
    box(410, 62, 210, 86, "SOAR\nautomatizza la risposta\n(blocca · isola · notifica)", accent=True) +
    arrow(116, 58, 188, 84, flow=True) +
    arrow(116, 106, 188, 106, flow=True) +
    arrow(116, 154, 188, 128, flow=True) +
    arrow(340, 106, 408, 106, flow=True) +
    cap(320, 196, "dal rumore all'incidente, dall'incidente all'azione"))

D["wildbox"] = svg(640, 200,
    box(20, 74, 110, 52, "Log / Eventi\n(Syslog/Agent)") +
    box(180, 60, 160, 80, "Wildbox Engine\nRegole Sigma · Euristiche", accent=True) +
    box(390, 60, 120, 80, "nftables / WAF\nBlocco IP automatico") +
    box(550, 74, 70, 52, "Alert\nAdmin") +
    arrow(130, 100, 178, 100, flow=True) +
    arrow(340, 100, 388, 100, flow=True, label="threat") +
    arrow(510, 100, 548, 100, flow=True) +
    cap(320, 180, "piattaforma unificata SIEM/SOAR self-hosted per rilevamento e contenimento istantaneo"))

# 8. Defense in depth
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
    cap(320, 250, "ogni difesa fallira: mettile in serie, il fallimento non e la partita"))

# 9. CDN
D["cos-e-cdn"] = svg(640, 220,
    box(270, 88, 100, 44, "Origine", accent=True) +
    "".join(box(x, y, 84, 38, lbl)
            for x, y, lbl in [(30, 20, "edge"), (30, 162, "edge"), (526, 20, "edge"),
                              (526, 162, "edge"), (30, 91, "edge"), (526, 91, "edge")]) +
    arrow(270, 100, 116, 41, flow=True) + arrow(270, 110, 116, 110, flow=True) +
    arrow(270, 120, 116, 179, flow=True) + arrow(370, 100, 524, 41, flow=True) +
    arrow(370, 110, 524, 110, flow=True) + arrow(370, 120, 524, 179, flow=True) +
    cap(320, 208, "stessi contenuti vicino a ogni utente (anycast)"))

# 10. AI Agent Loop & MCP
D["ai-agent"] = svg(640, 220,
    box(255, 20, 130, 46, "Osserva", accent=True) +
    box(455, 90, 130, 46, "Agisci\n(usa strumenti)", accent=True) +
    box(255, 158, 130, 46, "Legge il\nrisultato") +
    box(55, 90, 130, 46, "Decide") +
    arrow(385, 46, 470, 88, flow=True) +
    arrow(520, 136, 400, 172, flow=True) +
    arrow(255, 176, 130, 138, flow=True) +
    arrow(120, 88, 280, 66, flow=True) +
    cap(320, 214, "il ciclo che trasforma il testo in azione"))

D["creare-mcp-server"] = svg(640, 200,
    box(20, 74, 110, 52, "Agente AI\n(Client)") +
    box(180, 60, 150, 80, "Protocollo MCP\nJSON-RPC 2.0 Stdio/SSE", accent=True) +
    box(380, 60, 120, 80, "Server MCP\nPython / uvx / Node") +
    box(540, 74, 80, 52, "DB / File\nRisorse") +
    arrow(130, 100, 178, 100, flow=True) +
    arrow(330, 100, 378, 100, flow=True) +
    arrow(500, 100, 538, 100, flow=True) +
    cap(320, 180, "standard aperto per connettere modelli a strumenti ed API locali con sicurezza"))

D["nanocode"] = svg(640, 200,
    box(20, 74, 110, 52, "Sviluppatore\n(Terminale)") +
    box(180, 60, 140, 80, "Nanocode CLI\nMicro Agent Rust/Go", accent=True) +
    box(370, 60, 120, 80, "l0-compressor\nContext Pruning") +
    box(530, 74, 90, 52, "LLM Locale\n(Ollama)") +
    arrow(130, 100, 178, 100, flow=True) +
    arrow(320, 100, 368, 100, flow=True) +
    arrow(490, 100, 528, 100, flow=True) +
    cap(320, 180, "coding assistant minimale da shell Unix: zero bloat, zero telemetria e token compressi"))

# 11. Proxmox & Homelab Cockpit
D["proxxx"] = svg(640, 200,
    box(20, 74, 110, 52, "Terminale\n(Admin SSH)") +
    box(180, 60, 150, 80, "proxxx TUI\nAsync Rust Binary", accent=True) +
    box(380, 30, 110, 44, "PVE Cluster") +
    box(380, 86, 110, 44, "ZFS Pools") +
    box(380, 142, 110, 44, "PBS Storage") +
    arrow(130, 100, 178, 100, flow=True) +
    arrow(330, 80, 378, 52, flow=True) +
    arrow(330, 100, 378, 108, flow=True) +
    arrow(330, 120, 378, 164, flow=True) +
    cap(560, 105, "25+ tool") +
    cap(320, 195, "cockpit da terminale per monitoraggio e controllo completo di Proxmox"))

D["proxmox-autoscale"] = svg(640, 200,
    box(20, 74, 110, 52, "VM / LXC\nCarico Dinamico") +
    box(180, 60, 150, 80, "proxmox-autoscale\nDaemon di monitoraggio", accent=True) +
    box(380, 60, 120, 80, "QEMU Agent\nCPU/RAM Hotplug") +
    box(540, 74, 80, 52, "Nodo PVE\nOttimizzato") +
    arrow(130, 100, 178, 100, flow=True, label="metriche") +
    arrow(330, 100, 378, 100, flow=True, label="scale up/down") +
    arrow(500, 100, 538, 100, flow=True) +
    cap(320, 180, "ridimensionamento dinamico delle risorse per prevenire crash OOM ed eliminare sprechi"))

D["pegaprox"] = svg(640, 200,
    box(20, 74, 110, 52, "Admin / Utente\nItaliano") +
    box(180, 60, 160, 80, "Pegaprox\nInterfaccia & Traduzione IT", accent=True) +
    box(390, 60, 110, 80, "Template LXC\ne VM Rapide") +
    box(540, 74, 80, 52, "Storage\nZFS") +
    arrow(130, 100, 178, 100, flow=True) +
    arrow(340, 100, 388, 100, flow=True) +
    arrow(500, 100, 538, 100, flow=True) +
    cap(320, 180, "localizzazione e workflow semplificato per Proxmox curato da Fabrizio Salmi"))

# 12. Storage, Audio & Data encoding
D["b2v"] = svg(640, 200,
    box(20, 74, 110, 52, "File Binario\n(Backup/Tar)") +
    box(180, 60, 140, 80, "b2v Encoder\nMatrice RGB 1080p", accent=True) +
    box(370, 74, 110, 52, "Video MP4\n(Eternal-Stream)") +
    box(530, 74, 90, 52, "Archivio Cold\nIllimitato") +
    arrow(130, 100, 178, 100, flow=True) +
    arrow(320, 100, 368, 100, flow=True) +
    arrow(480, 100, 528, 100, flow=True) +
    cap(320, 180, "codifica di archivi binari in stream video standard per conservazione offline"))

D["mixi"] = svg(640, 200,
    box(20, 74, 110, 52, "Giradischi / DVS\nVinile Timecode") +
    box(180, 60, 150, 80, "MIXI Browser DAW\nWebAudio & WebAssembly", accent=True) +
    box(380, 60, 120, 80, "Sintesi Modulare\ne Mixer 4ch") +
    box(540, 74, 80, 52, "Uscita Audio\n< 5 ms") +
    arrow(130, 100, 178, 100, flow=True, label="1kHz signal") +
    arrow(330, 100, 378, 100, flow=True) +
    arrow(500, 100, 538, 100, flow=True) +
    cap(320, 180, "workstation audio deterministica browser-native a bassissima latenza"))

# 13. Token compression & MLX
D["l0-compressor"] = svg(640, 200,
    box(20, 74, 100, 52, "Prompt / Log\n(10k tokens)") +
    box(170, 60, 160, 80, "L0 Compressor\nToken Pruning & Summary", accent=True) +
    box(380, 74, 110, 52, "Prompt Snello\n(4k tokens)") +
    box(530, 74, 90, 52, "LLM Engine\n-60% Costi") +
    arrow(120, 100, 168, 100, flow=True) +
    arrow(330, 100, 378, 100, flow=True, label="compresso") +
    arrow(490, 100, 528, 100, flow=True) +
    cap(320, 180, "riduzione dei token e preservazione del contesto semantico per loop agentici"))

D["silicondev"] = svg(640, 200,
    box(20, 74, 110, 52, "Dataset JSONL\nPersonalizzato") +
    box(180, 60, 150, 80, "Apple MLX Framework\nLoRA on Metal / MPS", accent=True) +
    box(380, 74, 110, 52, "Adattatori\nLoRA Pesi") +
    box(530, 74, 90, 52, "Modello Fuso\nGGUF / FP16") +
    arrow(130, 100, 178, 100, flow=True) +
    arrow(330, 100, 378, 100, flow=True) +
    arrow(490, 100, 528, 100, flow=True) +
    cap(320, 180, "fine-tuning nativo ad altissima velocità su memoria unificata Apple Silicon"))

# ---------- Timelines ----------

D["dmarc-rollout"] = timeline(
    [("p=none", "osserva"), ("p=quarantine\npct 25%", "a tappe"), ("p=reject", "quando pulito")],
    "rollout graduale: prima osservi coi report, poi stringi")

D["nist-ir-lifecycle"] = timeline(
    ["Preparazione", "Detection\n& Analysis", "Contenimento", "Eradicazione", "Recovery", "Lessons\nlearned"],
    "un ciclo, non una retta: si torna indietro quando serve", h=176)

D["flareover"] = timeline(
    ["assess", "prepare", "present", "execute", "guard"],
    "migrazione deterministica: zero config che cambia comportamento in silenzio")

D["come-funziona-acme"] = timeline(
    [("Richiesta", "certmate/ACME"), ("Challenge", "http-01 / dns-01"), ("Verifica", "controlli il dominio"),
     ("Certificato", "valido 90 giorni"), ("Rinnovo", "automatico")],
    "il rinnovo va automatizzato: 90 giorni non sono un optional")

D["certmate"] = D["come-funziona-acme"]

D["vmware-migrazione"] = timeline(
    [("Assess", "annota MAC, rete"), ("VirtIO", "driver nelle guest"), ("Import", "diretto da ESXi"),
     ("A ondate", "prima le VM di test")],
    "dal PVE 8.2 l'import da ESXi e diretto")

D["incident-response"] = timeline(
    [("Contieni", "isola, non spegnere"), ("Preserva", "RAM e log"), ("Capisci", "l'estensione prima"),
     ("Comunica", "fuori banda")],
    "le prime ore decidono se e un brutto giorno o un disastro")

json.dump(D, open("/Users/fab/Documents/git/fabgpt-faq/diagrams.json", "w"),
          ensure_ascii=False, indent=1)
print(f"diagrams.json: {len(D)} diagrams generated.")
for k, v in D.items():
    assert v.startswith("<svg"), k
    assert "—" not in v, k
