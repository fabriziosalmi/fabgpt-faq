/* NIS2 Dedicated Fast-Path Deterministic Calculators
 * Zero network, zero hallucination. Registers into ZeroTools if available.
 */
(function (root) {
  'use strict';

  // Allegato I: Alta Criticità
  const ALTA_CRITICITA = [
    'energia', 'elettricita', 'petrolio', 'gas', 'idrogeno',
    'trasporti', 'aereo', 'ferroviario', 'marittimo', 'stradale',
    'bancario', 'banche', 'mercati finanziari', 'sanita', 'ospedali',
    'acqua potabile', 'acque reflue', 'infrastrutture digitali', 'cloud',
    'datacenter', 'msp', 'mssp', 'servizi gestiti', 'pa', 'pubblica amministrazione', 'spazio'
  ];

  // Allegato II: Altri Settori Critici
  const ALTRI_CRITICI = [
    'poste', 'servizi postali', 'rifiuti', 'chimica', 'chimico',
    'alimentare', 'cibo', 'manifattura', 'fabbricazione', 'elettronica',
    'dispositivi medici', 'motori', 'digitale', 'marketplace', 'social', 'ricerca'
  ];

  function calcolaClassificazione(dipendenti, fatturato, settore) {
    const d = parseInt(dipendenti, 10);
    const f = parseFloat(fatturato);
    const s = (settore || '').toLowerCase();

    const isGrande = d >= 250 || f >= 50;
    const isMedia = (d >= 50 && d < 250) || (f >= 10 && f < 50);
    const isPiccola = d < 50 && f < 10;

    let catSettore = 'Non riconosciuto';
    let allegato = null;

    if (ALTA_CRITICITA.some(k => s.includes(k))) {
      catSettore = 'Settore ad Alta Criticità (Allegato I)';
      allegato = 1;
    } else if (ALTRI_CRITICI.some(k => s.includes(k))) {
      catSettore = 'Altro Settore Critico (Allegato II)';
      allegato = 2;
    }

    let esito = '';
    let vigilanza = '';
    let sanzione = '';

    if (isPiccola && allegato) {
      esito = '**Fuori dall\'ambito generale** (Micro/Piccola Impresa)';
      vigilanza = 'Esclusa salvo eccezioni (es. fornitori unici, DNS/TLD, o requisiti contrattuali supply chain).';
      sanzione = 'Nessuna diretta (salvo eccezioni di legge).';
    } else if (allegato === 1) {
      if (isGrande) {
        esito = '🔴 **Soggetto Essenziale (Essential Entity)**';
        vigilanza = 'Vigilanza **ex-ante e continua** da parte dell\'ACN (ispezioni regolari e audit).';
        sanzione = 'Fino a **10.000.000 €** o **2% del fatturato annuo globale**.';
      } else {
        esito = '🟠 **Soggetto Importante (Important Entity)**';
        vigilanza = 'Vigilanza **ex-post reattiva** (l\'ACN interviene in caso di incidenti o segnalazioni).';
        sanzione = 'Fino a **7.000.000 €** o **1,4% del fatturato annuo globale**.';
      }
    } else if (allegato === 2) {
      esito = '🟠 **Soggetto Importante (Important Entity)**';
      vigilanza = 'Vigilanza **ex-post reattiva** da parte dell\'ACN.';
      sanzione = 'Fino a **7.000.000 €** o **1,4% del fatturato annuo globale**.';
    } else {
      esito = '⚠️ Settore da verificare';
      vigilanza = 'Specificare uno dei 18 settori degli Allegati I o II.';
      sanzione = 'Da determinare.';
    }

    let md = '### Calcolo Deterministico Conformità NIS2 (D.Lgs. 138/2024)\n\n';
    md += '- **Parametri inseriti**: `' + d + ' dipendenti`, `' + f + ' M€ fatturato`, settore `' + (s || 'generale') + '`\n';
    md += '- **Inquadramento dimensionale**: ' + (isGrande ? '**Grande Impresa**' : isMedia ? '**Media Impresa**' : '**Piccola Impresa**') + '\n';
    md += '- **Inquadramento settoriale**: ' + catSettore + '\n\n';
    md += '#### Risultato:\n' + esito + '\n\n';
    md += '- **Regime di Vigilanza**: ' + vigilanza + '\n';
    md += '- **Massimale Sanzioni**: ' + sanzione + '\n';
    md += '- **Obblighi principali**: Articolo 21 (Misure di sicurezza) e notifica incidenti a 24h/72h a CSIRT Italia.';
    return md;
  }

  function calcolaScadenzeNotifica(baseDate = new Date()) {
    const t0 = new Date(baseDate);
    const t24 = new Date(t0.getTime() + 24 * 3600000);
    const t72 = new Date(t0.getTime() + 72 * 3600000);
    const t1m = new Date(t0.getTime() + 30 * 24 * 3600000);

    const fmt = (d) => d.toLocaleString('it-IT', { dateStyle: 'short', timeStyle: 'short' });

    let md = '### Scadenziario Notifiche Incidenti NIS2 (D.Lgs. 138/2024)\n\n';
    md += '*Riferimento rilevamento evento:* **' + fmt(t0) + '**\n\n';
    md += '| Fase | Scadenza Rigorosa | Contenuto Obbligatorio | Destinatario |\n';
    md += '| :--- | :--- | :--- | :--- |\n';
    md += '| **1. Early Warning** | **' + fmt(t24) + '** (entro 24h) | Pre-allarme: sospetto dolo, impatto potenziale | CSIRT Italia (ACN) |\n';
    md += '| **2. Notifica Incidente** | **' + fmt(t72) + '** (entro 72h) | Valutazione iniziale gravità, indicatori (IoC) | CSIRT Italia (ACN) |\n';
    md += '| **3. Relazione Finale** | **' + fmt(t1m) + '** (entro 1 mese) | Root cause analysis, impatto effettivo, mitigazioni | CSIRT Italia (ACN) |\n\n';
    md += '> **Canale ufficiale:** Portale notifiche CSIRT Italia presso l\'Agenzia per la Cybersicurezza Nazionale.';
    return md;
  }

  // Register in ZeroTools if available
  const toolSuite = root.ZeroTools || root.FabTools;
  if (toolSuite && toolSuite.registerTool) {
    // 1. Tool Classificazione
    toolSuite.registerTool({
      name: 'nis2-classifica',
      match(text) {
        // e.g. "classifica 120 dipendenti 30M energia" or "dipendenti: 80 fatturato: 15 sanità"
        const p = text.toLowerCase();
        if (!p.includes('dipendenti') && !p.includes('fatturato') && !p.includes('classifica')) return null;
        const dipMatch = p.match(/(\d+)\s*(?:dipendenti|addetti|collaboratori)/);
        const fatMatch = p.match(/(\d+(?:[.,]\d+)?)\s*(?:m|mln|milioni|milione)?\s*(?:di\s*)?(?:€|euro|fatturato)/);
        if (dipMatch || fatMatch) {
          const dip = dipMatch ? dipMatch[1] : 50;
          const fat = fatMatch ? fatMatch[1].replace(',', '.') : 10;
          return { dip, fat, raw: text };
        }
        return null;
      },
      execute(m) {
        return {
          kind: 'nis2-tool',
          label: 'Classificatore NIS2',
          answer: calcolaClassificazione(m.dip, m.fat, m.raw),
          suggest: ['soggetti-essenziali-vs-importanti', 'obblighi-notifica-incidenti']
        };
      }
    });

    // 2. Tool Scadenziario Notifica
    toolSuite.registerTool({
      name: 'nis2-deadline',
      match(text) {
        const p = text.toLowerCase();
        if (p.includes('scadenza notifica') || p.includes('calcola deadline') || p.includes('ore notifica') || p.includes('scadenza incidente')) {
          return true;
        }
        return null;
      },
      execute() {
        return {
          kind: 'nis2-tool',
          label: 'Scadenziario Notifiche Incidenti',
          answer: calcolaScadenzeNotifica(new Date()),
          suggest: ['obblighi-notifica-incidenti', 'definizione-incidente-significativo']
        };
      }
    });
  }

  root.NIS2Tools = {
    calcolaClassificazione,
    calcolaScadenzeNotifica
  };
})(typeof globalThis !== 'undefined' ? globalThis : typeof self !== 'undefined' ? self : this);
