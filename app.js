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
      // short-word typos that bigram similarity misses (toen -> token)
      if (best < 0.8 && t.length >= 4 && w.length >= 4 && Math.abs(t.length - w.length) <= 1 && damerau1(t, w)) {
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
        // Multi-word keyword: exact substring wins; otherwise every unique
        // content word must be present (any order, typo-tolerant).
        if (inputNorm.includes(kw)) { score += 2; continue; }
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
    if (best && bestScore >= DB.config.matchThreshold) return best;
    return null;
  }

  /* ---------- minimal markdown rendering (escape first, then decorate) ---------- */

  function escapeHtml(s) {
    return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function inlineMd(s) {
    return s
      .replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
      // internal links: scheme-less relative paths (convention: "q/<slug>/")
      .replace(/\[([^\]]+)\]\(([^):\s]+)\)/g, '<a href="$2">$1</a>')
      .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
      .replace(/\*([^*\n]+)\*/g, '<em>$1</em>')
      .replace(/`([^`]+)`/g, '<code>$1</code>');
  }

  function renderMd(text) {
    const blocks = text.split(/\n\n+/);
    let html = '';
    for (const block of blocks) {
      const lines = block.split('\n');
      if (lines.every(l => /^\s*-\s+/.test(l))) {
        html += '<ul>' + lines.map(l => '<li>' + inlineMd(escapeHtml(l.replace(/^\s*-\s+/, ''))) + '</li>').join('') + '</ul>';
      } else {
        html += '<p>' + inlineMd(escapeHtml(block)).replace(/\n/g, '<br>') + '</p>';
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
      if (picks.length >= 3) break;
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

  function streamAnswer(text, onDone, suggest, diagramId, questionText) {
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
      const n = 1 + Math.floor(Math.random() * perTick);
      buffer += words.slice(i, i + n).join('');
      i += n;
      target.innerHTML = renderMd(buffer);
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

  function pickAnswer(entry) {
    const n = entry.answers.length;
    let idx = answerCursor[entry.id] ?? 0;
    if (entry.id === lastEntryId && n > 1) idx = (idx + 1) % n; // repeated question -> next variant
    answerCursor[entry.id] = idx;
    lastEntryId = entry.id;
    return entry.answers[idx % n];
  }

  let fallbackIdx = -1;
  function pickFallback() {
    fallbackIdx = (fallbackIdx + 1) % DB.fallbacks.length;
    lastEntryId = null;
    return DB.fallbacks[fallbackIdx];
  }

  function ask(text) {
    addUserMessage(text);
    const entry = match(text);
    const answer = entry ? pickAnswer(entry) : pickFallback();
    const qLabel = entry ? entry.question : text;
    if (entry && entry.slug) askedSlugs.add(entry.slug); // thread history
    streamAnswer(answer, null, entry && entry.suggest, entry && entry.id, qLabel);
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
    ask(text);
  });

  // Click any inline `code` to copy it (commands, config snippets).
  chatEl.addEventListener('click', e => {
    const c = e.target.closest('code');
    if (!c || !navigator.clipboard) return;
    navigator.clipboard.writeText(c.textContent).then(() => {
      c.classList.add('copied');
      setTimeout(() => c.classList.remove('copied'), 900);
    });
  });

  inputEl.addEventListener('input', () => { autoGrow(); updateSendState(); });
  inputEl.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      formEl.requestSubmit();
    }
  });

  // Count-up the header stat bar (the real entry count), reduced-motion aware.
  function animateStats(total) {
    const el = document.querySelector('#statbar b[data-to]');
    if (!el) return;
    el.setAttribute('data-to', total);
    if (matchMedia('(prefers-reduced-motion: reduce)').matches) { el.textContent = total; return; }
    let t0 = null;
    requestAnimationFrame(function step(t) {
      if (!t0) t0 = t;
      const p = Math.min(1, (t - t0) / 900);
      el.textContent = Math.round(total * (1 - Math.pow(1 - p, 3)));
      if (p < 1) requestAnimationFrame(step);
    });
  }

  /* ---------- boot ---------- */

  async function boot() {
    try {
      const res = await fetch('faq.json', { cache: 'no-cache' });
      DB = await res.json();
      try { DIAGRAMS = await (await fetch('diagrams.json', { cache: 'no-cache' })).json(); }
      catch (_) { DIAGRAMS = {}; } // diagrams are optional
    } catch (err) {
      const target = addBotRow();
      target.innerHTML = '<p>Non riesco a caricare <code>faq.json</code>. Se hai aperto il file in locale, servilo con un web server: <code>python3 -m http.server</code></p>';
      return;
    }
    document.title = DB.config.botName;
    inputEl.placeholder = DB.config.placeholder || '';
    noteEl.textContent = DB.config.footerNote || '';
    inputEl.focus();
    bySlug = Object.create(null);
    for (const e of DB.entries) bySlug[e.slug] = e;
    animateStats(DB.entries.length);

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
