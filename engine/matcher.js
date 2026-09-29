/* ZeroGPT / Engine – Agnostic deterministic Q&A matcher & Markdown parser.
 * No external dependencies. Works in Browser, Node.js, Web Worker, or Shadow DOM.
 */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else if (typeof define === 'function' && define.amd) define(factory);
  else {
    root.ZeroMatcher = factory();
    // Backwards compatibility alias
    root.FabMatcher = root.ZeroMatcher;
  }
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  const DEFAULT_STOPWORDS = new Set((
    'il lo la i gli le un uno una di a da in con su per tra fra e o ma se che chi cosa come dove quando quanto ' +
    'perche non mi ti si ci vi ne del della dei delle dello degli al allo alla ai agli alle sul sullo sulla sui sugli sulle nel nella nei ' +
    'sono sei e siamo siete ho hai ha abbiamo avete hanno posso puoi puo vorrei voglio sapere dimmi parlami spiegami raccontami esiste esistono ' +
    'c è ce cos cose cioe questo questa questi queste quello quella mio mia tuo tua suo sua piu meno molto poco anche ancora gia solo cose roba ' +
    'the a an of to is are was were be been what who how why when where and or me my your tell about does do can could would please'
  ).split(/\s+/));

  function norm(s) {
    if (!s) return '';
    return String(s).toLowerCase()
      .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
      .replace(/[^a-z0-9\s-]/g, ' ')
      .replace(/[-\s]+/g, ' ')
      .trim();
  }

  function tokens(s, stopwords = DEFAULT_STOPWORDS) {
    return norm(s).split(' ').filter(t => t.length > 1 && !stopwords.has(t));
  }

  function bigrams(w) {
    const out = [];
    for (let i = 0; i < w.length - 1; i++) out.push(w.slice(i, i + 2));
    return out;
  }

  // Sørensen–Dice similarity between two words for typo tolerance.
  function dice(a, b) {
    if (a === b) return 1;
    if (a.length < 2 || b.length < 2) return 0;
    const A = bigrams(a), B = new Map();
    for (const g of bigrams(b)) B.set(g, (B.get(g) || 0) + 1);
    let hits = 0;
    for (const g of A) {
      const n = B.get(g) || 0;
      if (n > 0) { hits++; B.set(g, n - 1); }
    }
    return (2 * hits) / (a.length - 1 + b.length - 1);
  }

  // True if a and b are within one edit (including adjacent transposition).
  function damerau1(a, b) {
    if (a === b) return true;
    let la = a.length, lb = b.length;
    if (Math.abs(la - lb) > 1) return false;
    if (la === lb) {
      const diffs = [];
      for (let k = 0; k < la; k++) if (a[k] !== b[k]) diffs.push(k);
      if (diffs.length === 1) return true;
      return diffs.length === 2 && diffs[1] === diffs[0] + 1 &&
        a[diffs[0]] === b[diffs[1]] && a[diffs[1]] === b[diffs[0]];
    }
    if (la > lb) { [a, b] = [b, a]; [la, lb] = [lb, la]; }
    let i = 0;
    while (i < la && a[i] === b[i]) i++;
    return a.slice(i) === b.slice(i + 1);
  }

  function wordBest(w, inputTokens) {
    let best = 0;
    for (const t of inputTokens) {
      if (t === w) return 1;
      if (t.length > 3 && w.length > 3 && Math.abs(t.length - w.length) <= 3) {
        const sim = dice(t, w);
        if (sim >= 0.7) best = Math.max(best, sim * 0.95);
      }
      if (best < 0.8 && t.length >= 4 && w.length >= 4 && Math.abs(t.length - w.length) <= 1 && t[0] === w[0] && damerau1(t, w)) {
        best = 0.8;
      }
    }
    return best;
  }

  function scoreEntry(entry, inputNorm, inputTokens, stopwords = DEFAULT_STOPWORDS) {
    if (!entry || !entry.keywords) return 0;
    let score = 0;
    for (const raw of entry.keywords) {
      const kw = norm(raw);
      if (!kw) continue;
      if (kw.includes(' ')) {
        if (kw.length >= 5 && inputNorm.includes(kw)) {
          score += 2;
          continue;
        }
        const words = [...new Set(kw.split(' ').filter(w => w.length > 1 && !stopwords.has(w)))];
        if (words.length < 2) continue;
        let total = 0, all = true;
        for (const w of words) {
          const b = wordBest(w, inputTokens);
          if (!b) { all = false; break; }
          total += b;
        }
        if (all) score += 2 * (total / words.length);
        continue;
      }
      score += wordBest(kw, inputTokens);
    }
    return score;
  }

  function ctxTokens(entry, stopwords = DEFAULT_STOPWORDS, cap = 24) {
    const seen = [];
    const sources = [entry.question || ''].concat(entry.keywords || []);
    for (const src of sources) {
      for (const t of tokens(src, stopwords)) {
        if (!seen.includes(t)) seen.push(t);
      }
    }
    return seen.slice(0, cap);
  }

  /* Core pipeline matcher */
  function match(text, db, options = {}) {
    if (!db || !db.entries) return null;
    const inputNorm = norm(text);
    const stopwords = options.stopwords || DEFAULT_STOPWORDS;
    const inputTokens = tokens(text, stopwords);
    const threshold = options.matchThreshold ?? db.config?.matchThreshold ?? 0.75;
    const ctxEntry = options.ctxEntry || null;
    const guard = options.guard || null;
    const commands = options.commands || [];
    const ground = options.ground || [];

    // 1. Refusal Layer
    if (guard && guard.keywords && guard.keywords.some(p => (' ' + inputNorm + ' ').includes(' ' + norm(p) + ' '))) {
      return {
        id: 'guard/refusal',
        question: 'Refusal',
        keywords: guard.keywords,
        answers: [guard.refusal || 'Richiesta non consentita dalle policy di sicurezza.'],
        suggest: [],
        kind: 'guard'
      };
    }

    // 2. Knowledge Base & Smalltalk
    const pool = db.entries.concat(db.smalltalk || []);
    let best = null, bestScore = 0;
    for (const entry of pool) {
      const s = scoreEntry(entry, inputNorm, inputTokens, stopwords);
      if (s > bestScore) {
        bestScore = s;
        best = entry;
      }
    }

    // 3. Multi-turn Contextual Recovery (Elliptical follow-up)
    const CTX_CONFIDENT = 2;
    const CTX_MIN = 2;
    const CTX_MAX_TOKENS = 2;
    if (ctxEntry && bestScore < CTX_CONFIDENT && inputTokens.length <= CTX_MAX_TOKENS) {
      const extra = ctxTokens(ctxEntry, stopwords).filter(t => !inputTokens.includes(t));
      if (extra.length) {
        const combined = inputTokens.concat(extra);
        let b2 = null, s2 = 0;
        for (const entry of db.entries) {
          if (entry.id === ctxEntry.id) continue;
          const comb = scoreEntry(entry, inputNorm, combined, stopwords);
          if (comb <= s2 || comb < CTX_MIN) continue;
          if (comb > scoreEntry(entry, '', extra, stopwords)) {
            b2 = entry;
            s2 = comb;
          }
        }
        if (b2 && s2 > bestScore) return b2;
      }
    }

    // 4. Command Cards / Operational layer
    if (commands && commands.length) {
      let bc = null, sc = 0;
      for (const card of commands) {
        const s = scoreEntry(card, inputNorm, inputTokens, stopwords);
        if (s > sc) { sc = s; bc = card; }
      }
      if (bc && sc > bestScore && (sc >= 2.0 || (sc >= 1.0 && bestScore < threshold))) {
        return {
          id: 'cmd/' + bc.id,
          question: bc.q || bc.title,
          keywords: bc.keywords,
          answers: ['**' + (bc.q || bc.title) + '**\n\n```bash\n' + bc.cmd + '\n```\n' + (bc.note || '')],
          suggest: bc.related || [],
          kind: 'command'
        };
      }
    }

    // 5. Ground-Truth Layer
    if (ground && ground.length) {
      let bg = null, sg = 0;
      for (const g of ground) {
        const s = scoreEntry(g, inputNorm, inputTokens, stopwords);
        if (s > sg) { sg = s; bg = g; }
      }
      if (bg && (sg >= 2.0 && (!best || sg > bestScore || best.id.startsWith('st-')))) {
        return bg;
      }
    }

    // Result or null if below threshold
    return (best && bestScore >= threshold) ? best : null;
  }

  /* Safe Markdown renderer */
  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function inlineMd(s) {
    if (!s) return '';
    const codes = [];
    s = s.replace(/`([^`]+)`/g, (_, code) => {
      codes.push(code);
      return `@@@CODESPAN_${codes.length - 1}@@@`;
    });
    s = s.replace(/\[([^\]]+)\]\((https?:\/\/[^\)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
    s = s.replace(/\[([^\]]+)\]\((mailto:[^\)\s]+)\)/g, '<a href="$2">$1</a>');
    s = s.replace(/\[([^\]]+)\]\(([^):\s]+)\)/g, '<a href="$2">$1</a>');
    s = s.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    s = s.replace(/\*([^*\n]+)\*/g, '<em>$1</em>');
    s = s.replace(/@@@CODESPAN_(\d+)@@@/g, (_, idx) => `<code>${escapeHtml(codes[Number(idx)])}</code>`);
    return s;
  }

  function renderMd(text) {
    if (!text) return '';
    const codeBlocks = [];
    let processed = text.replace(/```([a-zA-Z0-9_-]*)\n([\s\S]*?)```/g, (_, lang, code) => {
      const idx = codeBlocks.length;
      const safeCode = escapeHtml(code.trim());
      const headerLang = escapeHtml(lang ? lang.toUpperCase() : 'CODE');
      const blockHtml = `
        <div class="code-block">
          <div class="code-header">
            <span class="code-lang">${headerLang}</span>
            <button type="button" class="copy-code-btn" data-code="${encodeURIComponent(code.trim())}" aria-label="Copia codice">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
              <span>Copia</span>
            </button>
          </div>
          <pre><code class="language-${escapeHtml(lang)}">${safeCode}</code></pre>
        </div>
      `;
      codeBlocks.push(blockHtml);
      return `\n\n@@@CODEBLOCK_${idx}@@@\n\n`;
    });

    const blocks = processed.split(/\n\n+/);
    const out = [];
    for (const rawBlock of blocks) {
      const b = rawBlock.trim();
      if (!b) continue;
      const cbMatch = b.match(/^@@@CODEBLOCK_(\d+)@@@$/);
      if (cbMatch) {
        out.push(codeBlocks[Number(cbMatch[1])]);
      } else if (b.split('\n').every(l => /^\s*-\s+/.test(l))) {
        const items = b.split('\n').map(l => l.replace(/^\s*-\s+/, '')).map(l => `<li>${inlineMd(escapeHtml(l))}</li>`).join('');
        out.push(`<ul>${items}</ul>`);
      } else {
        const pContent = inlineMd(escapeHtml(b)).replace(/\n/g, '<br>')
          .replace(/@@@CODEBLOCK_(\d+)@@@/g, (_, idx) => codeBlocks[Number(idx)]);
        out.push(`<p>${pContent}</p>`);
      }
    }
    return out.join('');
  }

  return {
    norm,
    tokens,
    bigrams,
    dice,
    damerau1,
    wordBest,
    scoreEntry,
    ctxTokens,
    match,
    escapeHtml,
    inlineMd,
    renderMd,
    DEFAULT_STOPWORDS
  };
});
