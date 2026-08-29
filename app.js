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
  let streaming = false;
  const answerCursor = Object.create(null); // entry id -> next variant index
  let lastEntryId = null;

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

  // Type `text` into a fresh bot row, re-rendering partial markdown each tick.
  let finishStream = null; // set while streaming: fast-forwards to the full answer

  function streamAnswer(text, onDone) {
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
    streamAnswer(answer);
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

  inputEl.addEventListener('input', () => { autoGrow(); updateSendState(); });
  inputEl.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      formEl.requestSubmit();
    }
  });

  /* ---------- boot ---------- */

  async function boot() {
    try {
      const res = await fetch('faq.json', { cache: 'no-cache' });
      DB = await res.json();
    } catch (err) {
      const target = addBotRow();
      target.innerHTML = '<p>Non riesco a caricare <code>faq.json</code>. Se hai aperto il file in locale, servilo con un web server: <code>python3 -m http.server</code></p>';
      return;
    }
    document.title = DB.config.botName;
    inputEl.placeholder = DB.config.placeholder || '';
    noteEl.textContent = DB.config.footerNote || '';
    inputEl.focus();

    streamAnswer(DB.config.welcome, () => {
      // Deep link: /?q=<id|slug> asks that entry's canonical question.
      const q = new URLSearchParams(location.search).get('q');
      if (!q) return;
      const entry = DB.entries.find(e => e.id === q || e.slug === q);
      if (entry) setTimeout(() => ask(entry.question), 400);
    });
  }

  boot();

  // Debug hook: FabGPT.test("question") -> matched entry id (or null).
  window.FabGPT = {
    test: t => { const e = DB && match(t); return e ? e.id : null },
  };
})();
