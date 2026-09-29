# Esempi di Declinazione Verticale

Questa cartella raccoglie **esempi di riferimento e guide architetturali** che mostrano come prendere il motore deterministico disaccoppiato in `engine/` e applicarlo a domini verticali specifici (compliance, regolatorio, B2B, devops, pubblica amministrazione).

> **Nota di isolamento:** I contenuti in `examples/` servono esclusivamente come documentazione e template di riferimento all'interno del repository. Non fanno parte della knowledge base di FabGPT-FAQ e non vengono indicizzati né promossi sulla live page di produzione.

---

## Caso di Studio 1: Direttiva NIS2 (`examples/nis2/`)

La Direttiva NIS2 (recepita in Italia dal **D.Lgs. 138/2024**) è il contesto ideale per un'architettura deterministica:
- Le allucinazioni generative su articoli di legge, scadenze CSIRT o sanzioni per gli amministratori possono causare gravi danni legali o sanzioni fino al 2% del fatturato.
- L'utente richiede risposte certe, verificabili e ancorate al testo normativo.

### Struttura dell'esempio

```
examples/nis2/
├── faq.json          # 13 schede verificate con keywords, risposte e grafi di suggerimento
├── nis2_tools.js     # Micro-tool veloci: classificatore entità (All. I/II) e scadenziario CSIRT
├── index.html        # Dashboard operativa aziendale con Widget integrato via Shadow DOM
└── chat.html         # Interfaccia chat standalone a schermo intero
```

---

## Come declinare il motore per un nuovo settore (in 4 passi)

### 1. Definire la Conoscenza (`faq.json` o Markdown)
Puoi creare il file `faq.json` direttamente, oppure scrivere singoli file `.md` e compilarli con:

```bash
python3 ../../engine/md_parser.py cartella_markdown/ faq.json --bot-name "MioBot"
```

Ogni voce include:
- `question`: Domanda canonica.
- `keywords`: Parole chiave singole e frasi (ricerca fuzzy Sørensen–Dice e Damerau-1).
- `answers`: Array di risposte verificate (varianti servite a rotazione).
- `suggest`: Slug delle voci correlate per la navigazione contestuale.

### 2. (Opzionale) Aggiungere Micro-Tool Deterministici
Se il settore richiede calcoli esatti (es. conformità, conversioni, formule, codici tributo), registra un tool su `ZeroTools`:

```javascript
ZeroTools.registerTool({
  name: 'mio-calcolatore',
  match(query) {
    return query.includes('calcola') ? { params: ... } : null;
  },
  execute(matchResult) {
    return {
      kind: 'tool',
      label: 'Risultato Calcolo',
      answer: 'Risultato deterministico...',
      suggest: ['domanda-collegata']
    };
  }
});
```

### 3. Integrare il Widget nella tua applicazione
Nel tuo portale o applicativo web, includi il widget con un singolo tag script:

```html
<script src="../../engine/widget.js"
        data-faq="faq.json"
        data-title="Nome Assistente"
        data-color="#0f172a"
        data-position="bottom-right"></script>
```

Grazie allo **Shadow DOM**, la grafica del widget non subirà interferenze dal CSS del tuo sito (Bootstrap, Tailwind, ecc.) e non inquinerà il DOM ospitante.

### 4. (Opzionale) Compilare il portale AEO e SEO
Per trasformare la knowledge base in un portale statico con pagine dedicate per ogni domanda, schema JSON-LD `FAQPage`, mappa e file `llms.txt`:

```bash
python3 ../../engine/build.py .
```
