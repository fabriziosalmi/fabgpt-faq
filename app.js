/* FabGPT – static FAQ engine disguised as an AI chat.
 * No dependencies. Content lives in faq.json.
 */
(() => {
  'use strict';

  const chatEl = document.getElementById('chat');
  const formEl = document.getElementById('composer-form');
  const inputEl = document.getElementById('input');
  const sendEl = document.getElementById('send');
  const noteEl = document.getElementById('composer-note');

  let DB = null;
  let DIAGRAMS = {};                         // entry id -> inline SVG
  let PORTS = {};                            // well-known ports dataset (ports.json)
  let COMMANDS = [];
  let GROUND = [];                           // ground-truth layer (ground.json)                         // command cards (commands.json)
  const CMD_MIN = 2.0;                       // a card must reach this AND strictly beat the KB
  const GROUND_MIN = 2.0;                    // same contract for the ground-truth layer
  let streaming = false;
  const answerCursor = Object.create(null); // entry id -> next variant index
  let lastEntryId = null;
  let bySlug = null;                         // slug -> entry (built at boot)
  const askedSlugs = new Set();              // thread history: entries already asked

  /* ---------- text normalization & fuzzy matching ---------- */

  const STOPWORDS = new Set(('il lo la i gli le un uno una di a da in con su per tra fra e o ma se che chi cosa come dove quando quanto ' +
    'perche non mi ti si ci vi ne del della dei delle dello degli al allo alla ai agli alle sul sullo sulla sui sugli sulle nel nella nei ' +
    'sono sei e siamo siete ho hai ha abbiamo avete hanno posso puoi puo vorrei voglio sapere dimmi parlami spiegami raccontami esiste esistono ' +
    'c è ce cos cose cioe questo questa questi queste quello quella mio mia tuo tua suo sua piu meno molto poco anche ancora gia solo cose roba ' +
    'the a an of to is are was were be been what who how why when where and or me my your tell about does do can could would please').split(/\s+/));

  function norm(s) {
    return s.toLowerCase()
      .normalize('NFD').replace(/[̀-ͯ]/g, '')
      .replace(/[^a-z0-9\s-]/g, ' ')
      .replace(/[-\s]+/g, ' ')
      .trim();
  }

  function tokens(s) {
    return norm(s).split(' ').filter(t => t.length > 1 && !STOPWORDS.has(t));
  }

  function bigrams(w) {
    const out = [];
    for (let i = 0; i < w.length - 1; i++) out.push(w.slice(i, i + 2));
    return out;
  }

  // Sørensen–Dice similarity between two words, for typo tolerance.
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

  // True if a and b are within one edit (incl. adjacent transposition).
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

  // Best fuzzy match of one keyword word against the input tokens.
  function wordBest(w, inputTokens) {
    let best = 0;
    for (const t of inputTokens) {
      if (t === w) return 1;
      if (t.length > 3 && w.length > 3 && Math.abs(t.length - w.length) <= 3) {
        const sim = dice(t, w);
        if (sim >= 0.7) best = Math.max(best, sim * 0.95);
      }
      // short-word typos that bigram similarity misses (toen -> token);
      // first char must match: bash!=hash are different words, not typos
      if (best < 0.8 && t.length >= 4 && w.length >= 4 && Math.abs(t.length - w.length) <= 1 && t[0] === w[0] && damerau1(t, w)) {
        best = 0.8;
      }
    }
    return best;
  }

  function scoreEntry(entry, inputNorm, inputTokens) {
    let score = 0;
    for (const raw of entry.keywords) {
      const kw = norm(raw);
      if (!kw) continue;
      if (kw.includes(' ')) {
        // Multi-word keyword: exact substring wins (but only for phrases of
        // at least 5 chars: "up d" must not match inside "backup di");
        // otherwise every unique content word must be present.
        if (kw.length >= 5 && inputNorm.includes(kw)) { score += 2; continue; }
        const words = [...new Set(kw.split(' ').filter(w => w.length > 1 && !STOPWORDS.has(w)))];
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

  // Conversational context (mirrored in qa.py): the last KB entry answered.
  const CTX_CONFIDENT = 2;  // pass-1 score at/above which context is never consulted
  const CTX_MIN = 2;        // a contextual candidate must reach this combined score
  const CTX_CAP = 24;       // max context tokens carried from the previous entry
  const CTX_MAX_TOKENS = 2; // context applies only to elliptical inputs (<= this many content words)
  let ctxEntry = null;      // last knowledge-base entry served (smalltalk excluded)

  function ctxTokens(entry) {
    const seen = [];
    for (const src of [entry.question].concat(entry.keywords)) {
      for (const t of tokens(src)) if (!seen.includes(t)) seen.push(t);
    }
    return seen.slice(0, CTX_CAP);
  }

  function cardEntry(bc) {
    return {
      id: 'cmd/' + bc.id,
      question: bc.q,
      keywords: bc.keywords,
      answers: ['**' + bc.q + '**\n\n```bash\n' + bc.cmd + '\n```\n' + bc.note +
                '\n\n[Scheda completa dei comandi →](comandi/' + bc.group + '/#' + bc.id + ')'],
      suggest: bc.related || [],
      kind: 'command',
      group: bc.group,
      cardId: bc.id,
    };
  }

  function match(text) {
    const inputNorm = norm(text);
    const inputTokens = tokens(text);
    // Smalltalk goes last so knowledge-base entries win ties.
    const pool = DB.entries.concat(DB.smalltalk || []);
    let best = null, bestScore = 0;
    for (const entry of pool) {
      const s = scoreEntry(entry, inputNorm, inputTokens);
      if (s > bestScore) { bestScore = s; best = entry; }
    }
    // Weak direct match + an active thread: retry with the previous entry's
    // tokens added. A contextual candidate counts only if the NEW input
    // contributed (combined score > score from context tokens alone).
    if (ctxEntry && bestScore < CTX_CONFIDENT && inputTokens.length <= CTX_MAX_TOKENS) {
      const extra = ctxTokens(ctxEntry).filter(t => !inputTokens.includes(t));
      if (extra.length) {
        const combined = inputTokens.concat(extra);
        let b2 = null, s2 = 0;
        for (const entry of DB.entries) {
          if (entry.id === ctxEntry.id) continue;
          const comb = scoreEntry(entry, inputNorm, combined);
          if (comb <= s2 || comb < CTX_MIN) continue;
          if (comb > scoreEntry(entry, '', extra)) { b2 = entry; s2 = comb; }
        }
        // command cards join the contextual rescue (entries win ties)
        for (const card of COMMANDS) {
          if (ctxEntry.id === 'cmd/' + card.id) continue;
          const comb = scoreEntry(card, inputNorm, combined);
          if (comb <= s2 || comb < CTX_MIN) continue;
          if (comb > scoreEntry(card, '', extra)) { b2 = cardEntry(card); s2 = comb; }
        }
        if (b2 && s2 > bestScore) return b2;
      }
    }
    // Command cards (commands.json): operational one-liners. A card wins only
    // if it reaches CMD_MIN and STRICTLY beats the KB score (ties favor the KB),
    // so canonical questions keep routing to their entries. Mirrored in qa.py.
    // Ground-truth candidate (ground.json): scored here so the card rescue
    // below can be required to beat it too (a bare tool-name rescue must not
    // shadow a classic question the ground layer answers properly).
    let bg = null, sg = 0;
    for (const g of GROUND) {
      const s = scoreEntry(g, inputNorm, inputTokens);
      if (s > sg) { sg = s; bg = g; }
    }
    if (COMMANDS.length) {
      let bc = null, sc = 0;
      for (const card of COMMANDS) {
        const s = scoreEntry(card, inputNorm, inputTokens);
        if (s > sc) { sc = s; bc = card; }
      }
      // a card answers when it clearly wins, OR as a rescue when the KB has
      // nothing at all (bare tool names: hadolint, composerize...) - but the
      // rescue must also beat the ground-truth candidate
      if (bc && sc > bestScore &&
          (sc >= CMD_MIN || (sc >= 1 && sc > sg && bestScore < DB.config.matchThreshold))) {
        return cardEntry(bc);
      }
    }
    // Ground-truth layer: the classic questions everyone asks an "AI" on day
    // one. Same contract as the cards: it answers only if it reaches
    // GROUND_MIN AND strictly beats the KB score (or the KB result is an
    // encyclopedic deflector), plus the same bare-entity rescue when the KB
    // has nothing at all. The gate suite runs with ground loaded: no-steal.
    const kb = (best && bestScore >= DB.config.matchThreshold) ? best : null;
    if (bg) {
      const deflector = kb && (kb.id === 'st-cultura-generale' || kb.id === 'st-matematica');
      if ((sg >= GROUND_MIN && (!kb || sg > bestScore || deflector)) ||
          (sg >= 1 && !kb)) return bg;
    }
    return kb;
  }

  /* ---------- minimal markdown rendering (escape first, then decorate) ---------- */

  function escapeHtml(s) {
    return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function inlineMd(s) {
    // Code spans first, as placeholders: bold/italic must never eat the
    // asterisks inside a backtick span (cron expressions, globs, chmod).
    const codes = [];
    s = s.replace(/`([^`]+)`/g, (_, c) => {
      codes.push(c);
      return '@@@CODESPAN_' + (codes.length - 1) + '@@@';
    });
    s = s
      .replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
      .replace(/\[([^\]]+)\]\((mailto:[^)\s]+)\)/g, '<a href="$2">$1</a>')
      // internal links: scheme-less relative paths (convention: "q/<slug>/")
      .replace(/\[([^\]]+)\]\(([^):\s]+)\)/g, '<a href="$2">$1</a>')
      .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
      .replace(/\*([^*\n]+)\*/g, '<em>$1</em>');
    return s.replace(/@@@CODESPAN_(\d+)@@@/g, (_, i) => '<code>' + codes[+i] + '</code>');
  }

  function renderMd(text) {
    const codeBlocks = [];
    const createBlock = (lang, code) => {
      const idx = codeBlocks.length;
      const cleanLang = lang ? ` class="language-${escapeHtml(lang)}"` : '';
      const headerLang = escapeHtml((lang || 'CODE').toUpperCase());
      codeBlocks.push(
        `<div class="code-block">` +
        `<div class="code-header"><span class="code-lang">${headerLang}</span>` +
        `<button type="button" class="copy-code-btn" aria-label="Copia codice">` +
        `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>` +
        `<span>Copia</span></button></div>` +
        `<pre><code${cleanLang}>${escapeHtml(code)}</code></pre></div>`
      );
      return `\n\n@@@CODEBLOCK_${idx}@@@\n\n`;
    };

    // Match closed code blocks
    let processed = text.replace(/```([a-zA-Z0-9_-]*)\n([\s\S]*?)```/g, (_, lang, code) => createBlock(lang, code.trim()));

    // Handle unclosed code block during active streaming
    processed = processed.replace(/```([a-zA-Z0-9_-]*)\n([\s\S]*)$/g, (_, lang, code) => createBlock(lang, code));

    const blocks = processed.split(/\n\n+/);
    let html = '';
    for (const block of blocks) {
      const trimmed = block.trim();
      if (!trimmed) continue;
      if (/^@@@CODEBLOCK_\d+@@@$/.test(trimmed)) {
        const idx = parseInt(trimmed.replace(/\D/g, ''), 10);
        html += codeBlocks[idx] || '';
      } else if (trimmed.split('\n').every(l => /^\s*-\s+/.test(l))) {
        html += '<ul>' + trimmed.split('\n').map(l => '<li>' + inlineMd(escapeHtml(l.replace(/^\s*-\s+/, ''))) + '</li>').join('') + '</ul>';
      } else {
        let pContent = inlineMd(escapeHtml(trimmed)).replace(/\n/g, '<br>');
        pContent = pContent.replace(/@@@CODEBLOCK_(\d+)@@@/g, (_, i) => codeBlocks[parseInt(i, 10)] || '');
        html += '<p>' + pContent + '</p>';
      }
    }
    return html;
  }

  /* ---------- chat UI ---------- */

  function nearBottom() {
    return chatEl.scrollHeight - chatEl.scrollTop - chatEl.clientHeight < 120;
  }

  function scrollToBottom(force) {
    if (force || nearBottom()) chatEl.scrollTop = chatEl.scrollHeight;
  }

  function addUserMessage(text) {
    const row = document.createElement('div');
    row.className = 'msg msg-user';
    const bubble = document.createElement('div');
    bubble.className = 'bubble';
    bubble.textContent = text;
    row.appendChild(bubble);
    chatEl.appendChild(row);
    scrollToBottom(true);
  }

  function addBotRow() {
    const row = document.createElement('div');
    row.className = 'msg msg-bot';
    row.innerHTML = '<div class="avatar">F</div><div class="content"></div>';
    chatEl.appendChild(row);
    scrollToBottom(true);
    return row.querySelector('.content');
  }

  // Thread-aware suggested-question chips: resolve `suggest` slugs to entries,
  // drop ones already asked this session, cap at 3, render as clickable chips
  // that ask the entry's canonical question. `contentEl` is the bot row body.
  function renderChips(suggest, contentEl) {
    if (!suggest || !suggest.length || !bySlug) return;
    const picks = [];
    for (const slug of suggest) {
      const entry = bySlug[slug];
      if (entry && !askedSlugs.has(slug)) picks.push(entry);
      if (picks.length >= 4) break;
    }
    if (!picks.length) return;
    const wrap = document.createElement('div');
    wrap.className = 'chips';
    for (const entry of picks) {
      const chip = document.createElement('button');
      chip.type = 'button';
      chip.className = 'chip';
      chip.textContent = entry.question;
      chip.addEventListener('click', () => {
        if (streaming && finishStream) finishStream();
        // once used, the whole chip row is spent: remove it
        wrap.remove();
        ask(entry.question);
      });
      wrap.appendChild(chip);
    }
    contentEl.appendChild(wrap);
    scrollToBottom(false);
  }

  // Type `text` into a fresh bot row, re-rendering partial markdown each tick.
  let finishStream = null; // set while streaming: fast-forwards to the full answer

  // Track complete dialogue turns for incremental session export
  const sessionTurns = [];

  // Copy Q&A action bar (copies single turn Q&A, and full incremental session thread up to this point).
  function copyQaAction(questionText, answerText, historySnapshot) {
    const bar = document.createElement('div');
    bar.className = 'qa-actions';

    // 1. Copy single turn Q&A
    const btnQa = document.createElement('button');
    btnQa.type = 'button';
    btnQa.className = 'copy-qa-btn';
    btnQa.setAttribute('aria-label', 'Copia questo turno domanda e risposta');
    btnQa.innerHTML = "<svg width='13' height='13' viewBox='0 0 24 24' fill='none' "
      + "stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'>"
      + "<rect x='9' y='9' width='13' height='13' rx='2' ry='2'></rect>"
      + "<path d='M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1'></path></svg>"
      + "<span>Copia Q&A</span>";
    btnQa.addEventListener('click', () => {
      const formatted = `Q: ${questionText}\n\nA:\n${answerText}`;
      if (navigator.clipboard) {
        navigator.clipboard.writeText(formatted).then(() => {
          btnQa.classList.add('copied');
          btnQa.querySelector('span').textContent = 'Copiato!';
          setTimeout(() => {
            btnQa.classList.remove('copied');
            btnQa.querySelector('span').textContent = 'Copia Q&A';
          }, 1500);
        });
      }
    });
    bar.appendChild(btnQa);

    // 2. Copy incremental session thread (all turns up to this point)
    if (historySnapshot && historySnapshot.length > 1) {
      const btnSess = document.createElement('button');
      btnSess.type = 'button';
      btnSess.className = 'copy-session-btn';
      btnSess.setAttribute('aria-label', `Copia intera sessione (${historySnapshot.length} turni)`);
      btnSess.innerHTML = "<svg width='13' height='13' viewBox='0 0 24 24' fill='none' "
        + "stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'>"
        + "<path d='M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z'></path>"
        + "<polyline points='14 2 14 8 20 8'></polyline><line x1='16' y1='13' x2='8' y2='13'></line>"
        + "<line x1='16' y1='17' x2='8' y2='17'></line><polyline points='10 9 9 9 8 9'></polyline></svg>"
        + `<span>Copia sessione (${historySnapshot.length})</span>`;
      btnSess.addEventListener('click', () => {
        const mdTurns = historySnapshot.map((t, idx) => `### ${idx + 1}. ${t.q}\n\n${t.a}`).join('\n\n---\n\n');
        const exportText = `# Sessione FabGPT-FAQ (${historySnapshot.length} turni)\n\n${mdTurns}`;
        if (navigator.clipboard) {
          navigator.clipboard.writeText(exportText).then(() => {
            btnSess.classList.add('copied');
            btnSess.querySelector('span').textContent = 'Sessione copiata!';
            setTimeout(() => {
              btnSess.classList.remove('copied');
              btnSess.querySelector('span').textContent = `Copia sessione (${historySnapshot.length})`;
            }, 1500);
          });
        }
      });
      bar.appendChild(btnSess);
    }

    return bar;
  }

  // R13 - condensazione: wrap the tail of the freshest text node (the words
  // appended this tick) in a fading span. The next tick's re-render dissolves
  // the span back into plain, fully opaque text, so only the stream head
  // condenses and settled words never flicker.
  function condense(root, k) {
    if (!k) return;
    let node = root;
    while (node && node.lastChild) node = node.lastChild;
    if (!node || node.nodeType !== 3) return;
    const t = node.nodeValue;
    const tail = t.slice(Math.max(0, t.length - k));
    if (!tail.trim()) return;
    node.nodeValue = t.slice(0, t.length - tail.length);
    const span = document.createElement('span');
    span.className = 'cond';
    span.textContent = tail;
    node.parentNode.appendChild(span);
  }

  function streamAnswer(text, onDone, suggest, diagramId, questionText) {
    // '{n}' in any bot text resolves to the live entry count: no hardcoded
    // numbers that drift stale as the knowledge base grows
    text = String(text).replace(/\{n\}/g, DB && DB.entries ? DB.entries.length : '');
    streaming = true;
    updateSendState();
    const target = addBotRow();
    target.classList.add('typing');
    const words = text.split(/(?<=\s)/); // keep whitespace attached
    const cfg = DB.config.typing || {};
    const minD = cfg.minDelay ?? 18, maxD = cfg.maxDelay ?? 55, perTick = cfg.wordsPerTick ?? 2;
    let i = 0, buffer = '', timer = null;

    function done() {
      target.classList.remove('typing');
      streaming = false;
      finishStream = null;
      updateSendState();
      const svg = diagramId && DIAGRAMS[diagramId];
      if (svg) {
        const fig = document.createElement('figure');
        fig.className = 'diagram';
        fig.setAttribute('aria-label', `Schema: ${questionText || ''}`);
        const copySvgBtn = document.createElement('button');
        copySvgBtn.type = 'button';
        copySvgBtn.className = 'copy-diagram-btn';
        copySvgBtn.setAttribute('aria-label', 'Copia codice SVG dello schema');
        copySvgBtn.innerHTML = "<svg width='11' height='11' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><rect x='9' y='9' width='13' height='13' rx='2' ry='2'></rect><path d='M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1'></path></svg> <span>SVG</span>";
        copySvgBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          if (navigator.clipboard) {
            navigator.clipboard.writeText(svg).then(() => {
              copySvgBtn.classList.add('copied');
              copySvgBtn.querySelector('span').textContent = 'Copiato!';
              setTimeout(() => {
                copySvgBtn.classList.remove('copied');
                copySvgBtn.querySelector('span').textContent = 'SVG';
              }, 1500);
            });
          }
        });
        fig.appendChild(copySvgBtn);
        const svgContainer = document.createElement('div');
        svgContainer.innerHTML = svg;
        fig.appendChild(svgContainer.firstElementChild);
        target.appendChild(fig);
      }
      if (questionText) {
        sessionTurns.push({ q: questionText, a: text, diagramId: diagramId || null, svg: svg || null });
        const snapshot = sessionTurns.slice();
        target.appendChild(copyQaAction(questionText, text, snapshot));
      }
      renderChips(suggest, target);
      scrollToBottom(false);
      if (onDone) onDone();
    }

    finishStream = () => {
      clearTimeout(timer);
      target.innerHTML = renderMd(text);
      done();
    };

    function tick() {
      // background tabs throttle timers to ~1/s: render everything at once
      // instead of crawling - the user returns to a finished answer.
      if (document.hidden) { i = words.length; buffer = text; }
      const n = 1 + Math.floor(Math.random() * perTick);
      const added = words.slice(i, i + n).join('');
      buffer += added;
      i += n;
      target.innerHTML = renderMd(buffer);
      if (!document.hidden) condense(target, added.length);
      scrollToBottom(false);
      if (i < words.length) {
        let delay = minD + Math.random() * (maxD - minD);
        if (/[.!?:]\s*$/.test(buffer)) delay += 120 + Math.random() * 180; // breathe at sentence ends
        timer = setTimeout(tick, delay);
      } else {
        done();
      }
    }
    timer = setTimeout(tick, 140 + Math.random() * 260);
  }

  const servedCount = Object.create(null);        // entry id -> times served

  function pickAnswer(entry) {
    const n = entry.answers.length;
    const seen = entry.id in answerCursor;          // already answered in this session
    let idx = answerCursor[entry.id] ?? 0;
    if (seen && n > 1) idx = (idx + 1) % n;         // re-asked (anywhere) -> next variant
    answerCursor[entry.id] = idx;
    servedCount[entry.id] = (servedCount[entry.id] || 0) + 1;
    lastEntryId = entry.id;
    let text = entry.answers[idx % n];
    // variants exhausted (or single answer): acknowledge instead of parroting
    if (seen && servedCount[entry.id] > n && (entry.slug || entry.kind === 'command' || entry.kind === 'ground')) {
      text = "*Te l'avevo già raccontata – eccola di nuovo:*\n\n" + text;
    }
    return text;
  }

  let fallbackIdx = -1;
  function pickFallback() {
    fallbackIdx = (fallbackIdx + 1) % DB.fallbacks.length;
    lastEntryId = null;
    return DB.fallbacks[fallbackIdx];
  }

  // Fast-path: deterministic micro-tools (tools.js). Recognized patterns
  // (CIDR, cron, chmod, JWT, epoch, well-known ports) are COMPUTED, not
  // matched: zero inference, zero hallucination. Context is left untouched.
  const TOOL_SUGGEST = {
    subnet: ['cos-e-il-subnetting-e-il-cidr', 'segmentare-la-rete-con-vlan', 'nat-statico-dinamico-e-pat'],
    cron: ['cron-la-sintassi-spiegata', 'gestire-servizi-linux-con-systemctl', 'bash-scripting-le-basi-che-servono'],
    chmod: ['permessi-linux-chmod-chown-umask', 'utenti-gruppi-e-sudo-su-linux', 'come-funzionano-le-chiavi-ssh'],
    jwt: ['oauth2-proxy-autenticazione-davanti-ai-servizi', 'vulnerabilita-nei-redirect-oauth', 'come-gestire-i-secrets'],
    epoch: ['dove-sono-i-log-su-linux', 'cron-la-sintassi-spiegata', 'security-logging-fatto-bene'],
    datetime: ['cron-la-sintassi-spiegata', 'dove-sono-i-log-su-linux', 'gestire-servizi-linux-con-systemctl'],
  };

  function tryFastPath(text) {
    if (typeof FabTools === 'undefined') return null;
    const hit = FabTools.detect(text, {
      ports: PORTS,
      subnetSuggest: TOOL_SUGGEST.subnet, cronSuggest: TOOL_SUGGEST.cron,
      chmodSuggest: TOOL_SUGGEST.chmod, jwtSuggest: TOOL_SUGGEST.jwt,
      epochSuggest: TOOL_SUGGEST.epoch, datetimeSuggest: TOOL_SUGGEST.datetime,
    });
    return hit || null;
  }

  function ask(text) {
    addUserMessage(text);
    const fp = tryFastPath(text);
    if (fp) {
      const pn = fp.kind === 'port' && fp.label.match(/\d+/);
      updateCrumb(fp.kind === 'port' ? 'port' : 'tool', fp.label,
        fp.kind === 'port' ? (pn ? 'porta/' + pn[0] + '/' : null) : TOOL_PAGES[fp.kind]);
      streamAnswer(fp.answer, null, fp.suggest, null, text);
      return;
    }
    let entry = match(text);
    // "approfondisci" on an active thread: serve the next answer variant of
    // the last KB entry instead of the generic smalltalk reply (qa.py mirrors).
    if (entry && entry.id === 'st-approfondisci' && ctxEntry && ctxEntry.answers.length > 1) {
      entry = ctxEntry;
      const n = entry.answers.length;
      const idx = ((answerCursor[entry.id] ?? 0) + 1) % n;
      answerCursor[entry.id] = idx;
      lastEntryId = entry.id;
      askedSlugs.add(entry.slug);
      crumbForEntry(entry);
      streamAnswer(entry.answers[idx], null, entry.suggest, entry.id, entry.question);
      return;
    }
    const answer = entry ? pickAnswer(entry) : pickFallback();
    // a fallback must never be a dead end: offer the starter hubs to restart
    const fallbackChips = entry ? null : (DB.config.suggest || []);
    const qLabel = entry ? (entry.question || text) : text;
    if (entry && (entry.slug || entry.kind === 'command' || entry.kind === 'ground')) {
      if (entry.slug) askedSlugs.add(entry.slug);
      ctxEntry = entry;                             // cards and ground carry context too
    }
    crumbForEntry(entry);
    // a ground answer with no suggestions of its own bridges back to the hubs
    const chips = entry
      ? ((entry.suggest && entry.suggest.length) ? entry.suggest
         : (entry.kind === 'ground' ? (DB.config.suggest || []) : entry.suggest))
      : fallbackChips;
    streamAnswer(answer, null, chips, entry && entry.id, qLabel);
  }

  /* ---------- composer ---------- */

  function updateSendState() {
    sendEl.disabled = inputEl.value.trim() === '';
  }

  function autoGrow() {
    inputEl.style.height = 'auto';
    // Only trust scrollHeight when there is text and a real layout width
    // (a zero-width viewport wraps every character and inflates the measure).
    if (inputEl.value !== '' && inputEl.offsetWidth > 0) {
      inputEl.style.height = Math.min(inputEl.scrollHeight, 180) + 'px';
    }
  }

  formEl.addEventListener('submit', e => {
    e.preventDefault();
    const text = inputEl.value.trim();
    if (!text || !DB) return;
    if (streaming && finishStream) finishStream(); // impatient user: fast-forward
    inputEl.value = '';
    autoGrow();
    updateSendState();
    hideSuggest();
    ask(text);
  });

  // Click any inline `code` or `.copy-code-btn` to copy it.
  chatEl.addEventListener('click', e => {
    const copyCodeBtn = e.target.closest('.copy-code-btn');
    if (copyCodeBtn) {
      const block = copyCodeBtn.closest('.code-block');
      const code = block ? block.querySelector('code')?.textContent : '';
      if (code && navigator.clipboard) {
        navigator.clipboard.writeText(code).then(() => {
          copyCodeBtn.classList.add('copied');
          copyCodeBtn.querySelector('span').textContent = 'Copiato!';
          setTimeout(() => {
            copyCodeBtn.classList.remove('copied');
            copyCodeBtn.querySelector('span').textContent = 'Copia';
          }, 1500);
        });
      }
      return;
    }
    const c = e.target.closest('code:not(pre code)');
    if (!c || !navigator.clipboard) return;
    navigator.clipboard.writeText(c.textContent).then(() => {
      c.classList.add('copied');
      setTimeout(() => c.classList.remove('copied'), 900);
    });
  });

  inputEl.addEventListener('input', () => { autoGrow(); updateSendState(); scheduleSuggest(); });
  inputEl.addEventListener('keydown', e => {
    if (suggestNav(e)) return;
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      formEl.requestSubmit();
    }
  });

  /* ---------- live search: the composer doubles as a search box ----------
     While typing, the same scorer that answers the chat ranks the knowledge
     base and offers the top matching questions above the composer. Picking
     one asks it in chat (arrows + Enter, or click; Esc closes). */
  const suggestEl = document.getElementById('suggestbox');
  const SUGGEST_MAX = 5;
  const SUGGEST_MIN_SCORE = 1;
  let suggestTimer = null;
  let suggestItems = [];   // [{entry}] currently rendered
  let suggestIdx = -1;     // keyboard cursor (-1 = none)

  function hideSuggest() {
    if (!suggestEl) return;
    suggestEl.hidden = true;
    suggestEl.innerHTML = '';
    suggestItems = [];
    suggestIdx = -1;
    inputEl.setAttribute('aria-expanded', 'false');
  }

  function scheduleSuggest() {
    if (suggestTimer) clearTimeout(suggestTimer);
    suggestTimer = setTimeout(updateSuggest, 120);
  }

  function updateSuggest() {
    if (!suggestEl || !DB) return;
    const raw = inputEl.value.trim();
    if (raw.length < 3 || raw.length > 80) { hideSuggest(); return; }
    const inputNorm = norm(raw);
    const inputTokens = tokens(raw);
    if (!inputTokens.length) { hideSuggest(); return; }
    const scored = [];
    for (const entry of DB.entries) {
      let s = scoreEntry(entry, inputNorm, inputTokens);
      // typing the question itself must rank it first
      if (inputNorm.length >= 4 && norm(entry.question).includes(inputNorm)) s += 3;
      if (s >= SUGGEST_MIN_SCORE) scored.push([s, scored.length, entry]);
    }
    scored.sort((a, b) => b[0] - a[0] || a[1] - b[1]);
    const top = scored.slice(0, SUGGEST_MAX);
    if (!top.length) { hideSuggest(); return; }
    suggestItems = top.map(t => t[2]);
    suggestIdx = -1;
    suggestEl.innerHTML = suggestItems.map((e, i) =>
      '<button type="button" class="sg" role="option" id="sg-' + i + '" aria-selected="false">' +
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/></svg>' +
      '<span>' + escapeHtml(e.question) + '</span></button>'
    ).join('');
    suggestEl.hidden = false;
    inputEl.setAttribute('aria-expanded', 'true');
  }

  function pickSuggest(i) {
    const entry = suggestItems[i];
    if (!entry) return;
    hideSuggest();
    if (streaming && finishStream) finishStream();
    inputEl.value = '';
    autoGrow();
    updateSendState();
    ask(entry.question);
  }

  // Arrow keys move the cursor, Enter picks, Esc closes. Returns true when
  // the event was consumed by the suggestion list.
  function suggestNav(e) {
    if (!suggestEl || suggestEl.hidden) return false;
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      const n = suggestItems.length;
      suggestIdx = e.key === 'ArrowDown'
        ? (suggestIdx + 1) % n
        : (suggestIdx <= 0 ? n - 1 : suggestIdx - 1);
      suggestEl.querySelectorAll('.sg').forEach((b, i) => {
        b.classList.toggle('on', i === suggestIdx);
        b.setAttribute('aria-selected', i === suggestIdx ? 'true' : 'false');
      });
      return true;
    }
    if (e.key === 'Enter' && suggestIdx >= 0 && !e.shiftKey) {
      e.preventDefault();
      pickSuggest(suggestIdx);
      return true;
    }
    if (e.key === 'Escape') { hideSuggest(); return true; }
    return false;
  }

  if (suggestEl) {
    // pointerdown fires before the textarea loses focus: no blur race
    suggestEl.addEventListener('pointerdown', e => {
      const b = e.target.closest('.sg');
      if (!b) return;
      e.preventDefault();
      pickSuggest([...suggestEl.querySelectorAll('.sg')].indexOf(b));
    });
    inputEl.addEventListener('blur', () => setTimeout(hideSuggest, 150));
  }

  // Live context breadcrumb in the header bar: every answered turn gets a
  // link to its shareable static page (KB entry, command card or tool).
  const CRUMB_SVG = {
    kb: '<circle cx="12" cy="12" r="10"/><polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76"/>',
    book: '<path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>',
    cmd: '<polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/>',
    tool: '<path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/>',
    port: '<path d="M12 22v-5"/><path d="M9 8V2"/><path d="M15 8V2"/><path d="M18 8v5a4 4 0 0 1-4 4h-4a4 4 0 0 1-4-4V8Z"/>',
  };

  function updateCrumb(kind, label, href) {
    const el = document.getElementById('ctxcrumb');
    if (!el || !label || !href) return;
    const ic = document.getElementById('ctxcrumb-ic');
    if (ic) {
      ic.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
        (CRUMB_SVG[kind] || CRUMB_SVG.book) + '</svg>';
    }
    document.getElementById('ctxcrumb-tx').textContent = label;
    el.setAttribute('href', href);
    el.hidden = false;
  }

  const TOOL_PAGES = {
    subnet: 'tools/calcolatore-subnet/', cron: 'tools/spiega-cron/',
    chmod: 'tools/calcolatore-chmod/', jwt: 'tools/decodifica-jwt/',
    epoch: 'tools/timestamp-unix/',
  };

  function crumbForEntry(entry) {
    if (!entry) return;
    if (entry.kind === 'command' && entry.group && entry.cardId) {
      updateCrumb('cmd', entry.question, 'comandi/' + entry.group + '/#' + entry.cardId);
    } else if (entry.slug) {
      const vlabel = ((DB.verticals || []).find(v => v.id === entry.vertical) || {}).label;
      updateCrumb('book', (vlabel ? vlabel + ' › ' : '') + entry.question, 'q/' + entry.slug + '/');
    }
  }

  /* ---------- boot ---------- */

  async function boot() {
    try {
      const res = await fetch('faq.json', { cache: 'no-cache' });
      DB = await res.json();
      try { DIAGRAMS = await (await fetch('diagrams.json', { cache: 'no-cache' })).json(); }
      catch (_) { DIAGRAMS = {}; } // diagrams are optional
      try { PORTS = (await (await fetch('ports.json', { cache: 'no-cache' })).json()).ports; }
      catch (_) { PORTS = {}; } // port dataset is optional
      try { COMMANDS = (await (await fetch('commands.json', { cache: 'no-cache' })).json()).cards; }
      catch (_) { COMMANDS = []; } // command cards are optional
      try { GROUND = (await (await fetch('ground.json', { cache: 'no-cache' })).json()).entries; }
      catch (_) { GROUND = []; } // ground-truth layer is optional
      // Self-heal a stale cached index.html that predates the tools.js tag.
      if (typeof FabTools === 'undefined') {
        const s = document.createElement('script');
        s.src = 'tools.js?v=' + Date.now();
        document.head.appendChild(s);
      }
    } catch (err) {
      const target = addBotRow();
      target.innerHTML = '<p>Non riesco a caricare <code>faq.json</code>. Se hai aperto il file in locale, servilo con un web server: <code>python3 -m http.server</code></p>';
      return;
    }
    document.title = DB.config.botName;
    // R4bis - invito mutevole: rotate honest placeholders deterministically
    // by day ({n} = live entry count); config.placeholder stays the fallback.
    const phs = DB.config.placeholders;
    inputEl.placeholder = (phs && phs.length)
      ? phs[Math.floor(Date.now() / 86400000) % phs.length].replace('{n}', DB.entries.length)
      : (DB.config.placeholder || '');
    noteEl.innerHTML = inlineMd(escapeHtml(DB.config.footerNote || ''));
    inputEl.focus();
    bySlug = Object.create(null);
    for (const e of DB.entries) bySlug[e.slug] = e;

    const q = new URLSearchParams(location.search).get('q');
    const deepEntry = q && DB.entries.find(e => e.id === q || e.slug === q);
    // Starter chips after the welcome — unless a deep link will drive the first ask.
    streamAnswer(DB.config.welcome, () => {
      if (deepEntry) setTimeout(() => ask(deepEntry.question), 400);
    }, deepEntry ? null : DB.config.suggest);
  }

  boot();

  // Debug hook: FabGPT.test("question") -> matched entry id (or null).
  window.FabGPT = {
    test: t => { const e = DB && match(t); return e ? e.id : null },
  };
})();
