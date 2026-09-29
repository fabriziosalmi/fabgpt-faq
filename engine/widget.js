/**
 * ZeroGPT Embeddable Chat Widget
 * 100% client-side, zero backend, zero hallucinations, Shadow DOM isolation.
 *
 * Usage via script tag:
 *   <script src="path/to/widget.js" data-faq="faq.json" data-title="Assistente NIS2" data-color="#0284c7"></script>
 *
 * Usage via JavaScript:
 *   ZeroChatWidget.init({ faqUrl: 'faq.json', title: 'Assistente NIS2', accentColor: '#0284c7' });
 */
(function () {
  'use strict';

  if (window.ZeroChatWidget) return;

  /* ---------- Embedded Matcher & Markdown Engine ---------- */
  const STOPWORDS = new Set((
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

  function tokens(s) {
    return norm(s).split(' ').filter(t => t.length > 1 && !STOPWORDS.has(t));
  }

  function bigrams(w) {
    const out = [];
    for (let i = 0; i < w.length - 1; i++) out.push(w.slice(i, i + 2));
    return out;
  }

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

  function scoreEntry(entry, inputNorm, inputTokens) {
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
            <span>${headerLang}</span>
            <button type="button" class="copy-btn" data-code="${encodeURIComponent(code.trim())}">Copia</button>
          </div>
          <pre><code>${safeCode}</code></pre>
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

  /* ---------- Widget Implementation ---------- */
  class ZeroChatWidgetElement {
    constructor(config) {
      this.config = Object.assign({
        faqUrl: 'faq.json',
        title: 'Assistente AI',
        subtitle: '100% Deterministico · Zero Allucinazioni',
        accentColor: '#0284c7',
        position: 'bottom-right',
        greeting: null,
        placeholder: 'Fai una domanda...',
        authorLink: null
      }, config);

      this.db = null;
      this.isOpen = false;
      this.isStreaming = false;
      this.lastEntry = null;
      this.bySlug = new Map();
      this.askedSlugs = new Set();

      this.initDom();
      this.loadFaq();
    }

    initDom() {
      this.container = document.createElement('div');
      this.container.id = 'zero-chat-widget-root';
      this.shadow = this.container.attachShadow({ mode: 'open' });

      // Embed CSS inside Shadow DOM for absolute isolation
      const style = document.createElement('style');
      style.textContent = `
        :host {
          --primary: #0f172a;
          --primary-hover: #1e293b;
          --bg-widget: #ffffff;
          --bg-header: #ffffff;
          --bg-body: #f8fafc;
          --text-main: #0f172a;
          --text-muted: #475569;
          --text-subtle: #64748b;
          --border: #e2e8f0;
          --border-strong: #cbd5e1;
          --msg-bot-bg: #ffffff;
          --msg-user-bg: #0f172a;
          --msg-user-text: #ffffff;
          --chip-bg: #ffffff;
          --chip-border: #cbd5e1;
          --chip-text: #0f172a;
          --font: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
          --font-mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
          --radius: 8px;
          --shadow: 0 16px 36px -8px rgba(15, 23, 42, 0.16), 0 4px 12px -2px rgba(15, 23, 42, 0.08);
          font-family: var(--font);
          line-height: 1.5;
        }

        .widget-btn {
          position: fixed;
          ${this.config.position.includes('left') ? 'left: 24px;' : 'right: 24px;'}
          bottom: 24px;
          height: 44px;
          padding: 0 16px;
          border-radius: 22px;
          background: #0f172a;
          color: #ffffff;
          border: 1px solid #1e293b;
          box-shadow: 0 6px 16px rgba(15, 23, 42, 0.2);
          cursor: pointer;
          display: flex;
          align-items: center;
          gap: 8px;
          font-size: 13px;
          font-weight: 600;
          letter-spacing: -0.01em;
          transition: transform 0.15s ease, background-color 0.15s;
          z-index: 999999;
          outline: none;
        }
        .widget-btn:hover {
          transform: translateY(-2px);
          background: #1e293b;
        }
        .widget-btn svg {
          width: 18px;
          height: 18px;
          fill: currentColor;
        }

        .widget-window {
          position: fixed;
          ${this.config.position.includes('left') ? 'left: 24px;' : 'right: 24px;'}
          bottom: 80px;
          width: 420px;
          max-width: calc(100vw - 32px);
          height: 620px;
          max-height: calc(100vh - 100px);
          background: var(--bg-widget);
          border-radius: var(--radius);
          box-shadow: var(--shadow);
          border: 1px solid var(--border-strong);
          display: flex;
          flex-direction: column;
          overflow: hidden;
          opacity: 0;
          transform: translateY(12px) scale(0.98);
          pointer-events: none;
          transition: opacity 0.2s ease, transform 0.2s cubic-bezier(0.16, 1, 0.3, 1);
          z-index: 999998;
        }
        .widget-window.open {
          opacity: 1;
          transform: translateY(0) scale(1);
          pointer-events: auto;
        }

        .widget-header {
          padding: 14px 16px;
          background: var(--bg-header);
          border-bottom: 1px solid var(--border);
          display: flex;
          align-items: center;
          justify-content: space-between;
          flex-shrink: 0;
        }
        .header-title-box {
          display: flex;
          align-items: center;
          gap: 10px;
        }
        .header-avatar {
          width: 34px;
          height: 34px;
          border-radius: 8px;
          background: var(--primary);
          color: #fff;
          display: flex;
          align-items: center;
          justify-content: center;
          font-weight: 700;
          font-size: 14px;
        }
        .header-text h3 {
          margin: 0;
          font-size: 14px;
          font-weight: 600;
          color: var(--text-main);
        }
        .header-text p {
          margin: 0;
          font-size: 11px;
          color: var(--text-muted);
          display: flex;
          align-items: center;
          gap: 4px;
        }
        .status-dot {
          width: 7px;
          height: 7px;
          border-radius: 50%;
          background: #10b981;
          display: inline-block;
        }

        .header-actions {
          display: flex;
          gap: 6px;
        }
        .icon-btn {
          background: transparent;
          border: none;
          color: var(--text-muted);
          padding: 6px;
          border-radius: 6px;
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
        }
        .icon-btn:hover {
          background: var(--border);
          color: var(--text-main);
        }

        .widget-body {
          flex: 1 1 auto;
          overflow-y: auto;
          padding: 16px;
          display: flex;
          flex-direction: column;
          gap: 12px;
          scroll-behavior: smooth;
          background: var(--bg-body);
        }

        .msg-row {
          display: flex;
          flex-direction: column;
          gap: 6px;
          max-width: 92%;
          animation: msg-fade 0.15s ease-out;
        }
        @keyframes msg-fade {
          from { opacity: 0; transform: translateY(4px); }
          to { opacity: 1; transform: translateY(0); }
        }
        .msg-row.user {
          align-self: flex-end;
          align-items: flex-end;
        }
        .msg-row.bot {
          align-self: flex-start;
          align-items: flex-start;
        }

        .bubble {
          padding: 10px 13px;
          border-radius: var(--radius);
          font-size: 12.5px;
          word-break: break-word;
          line-height: 1.5;
        }
        .msg-row.user .bubble {
          background: var(--msg-user-bg);
          color: var(--msg-user-text);
        }
        .msg-row.bot .bubble {
          background: var(--msg-bot-bg);
          color: var(--text-main);
          border: 1px solid var(--border);
          box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
        }

        .bubble p { margin: 0 0 6px 0; }
        .bubble p:last-child { margin-bottom: 0; }
        .bubble ul { margin: 0 0 6px 0; padding-left: 18px; }
        .bubble a { color: var(--accent); text-decoration: underline; }
        .bubble code {
          background: #f1f5f9;
          color: #0f172a;
          padding: 2px 4px;
          border-radius: 4px;
          font-family: var(--font-mono);
          font-size: 11.5px;
          border: 1px solid #e2e8f0;
        }

        .bubble table {
          width: 100%;
          border-collapse: collapse;
          font-size: 11.5px;
          margin: 8px 0;
        }
        .bubble th {
          background: #f1f5f9;
          padding: 5px 8px;
          border: 1px solid var(--border-strong);
          text-align: left;
          font-weight: 600;
        }
        .bubble td {
          padding: 5px 8px;
          border: 1px solid var(--border);
        }

        .code-block {
          background: #0f172a;
          color: #f8fafc;
          border-radius: var(--radius);
          overflow: hidden;
          margin: 6px 0;
          font-size: 11.5px;
          border: 1px solid #1e293b;
        }
        .code-header {
          display: flex;
          justify-content: space-between;
          padding: 4px 8px;
          background: #1e293b;
          color: #94a3b8;
          font-size: 10px;
          font-weight: 600;
        }
        .copy-btn {
          background: transparent;
          border: none;
          color: #cbd5e1;
          cursor: pointer;
          font-size: 10px;
        }
        .code-block pre {
          margin: 0;
          padding: 8px 10px;
          overflow-x: auto;
          font-family: var(--font-mono);
        }

        .chips-container {
          display: flex;
          flex-wrap: wrap;
          gap: 6px;
          margin-top: 4px;
        }
        .chip {
          background: var(--chip-bg);
          border: 1px solid var(--chip-border);
          color: var(--chip-text);
          font-size: 11.5px;
          font-weight: 500;
          padding: 4px 8px;
          border-radius: var(--radius);
          cursor: pointer;
          transition: background-color 0.15s, border-color 0.15s, color 0.15s;
          text-align: left;
        }
        .chip:hover {
          background: var(--primary);
          border-color: var(--primary);
          color: #ffffff;
        }

        .widget-composer {
          padding: 10px 14px;
          background: var(--bg-header);
          border-top: 1px solid var(--border);
          display: flex;
          flex-direction: column;
          gap: 6px;
          flex-shrink: 0;
        }
        .input-row {
          display: flex;
          gap: 6px;
          align-items: center;
        }
        .widget-input {
          flex: 1;
          background: #f8fafc;
          border: 1px solid var(--border-strong);
          color: var(--text-main);
          border-radius: var(--radius);
          padding: 7px 11px;
          font-size: 12.5px;
          outline: none;
          transition: border-color 0.15s, background-color 0.15s;
        }
        .widget-input:focus {
          border-color: var(--primary);
          background: #ffffff;
        }
        .send-btn {
          width: 32px;
          height: 32px;
          border-radius: var(--radius);
          background: var(--primary);
          color: #fff;
          border: none;
          display: flex;
          align-items: center;
          justify-content: center;
          cursor: pointer;
          transition: opacity 0.15s;
        }
        .send-btn:hover {
          opacity: 0.9;
        }
        .composer-badge {
          font-size: 10px;
          color: var(--text-subtle);
          display: flex;
          justify-content: space-between;
        }

        /* Typing indicator */
        .typing-cursor {
          display: inline-block;
          width: 6px;
          height: 14px;
          background: var(--primary);
          margin-left: 2px;
          vertical-align: middle;
          animation: blink 0.8s infinite;
        }
        @keyframes blink {
          0%, 100% { opacity: 1; }
          50% { opacity: 0; }
        }
      `;
      this.shadow.appendChild(style);

      // Launcher Button HTML
      this.btnEl = document.createElement('button');
      this.btnEl.className = 'widget-btn';
      this.btnEl.setAttribute('aria-label', 'Apri chat');
      this.btnEl.innerHTML = `
        <svg viewBox="0 0 24 24">
          <path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H6l-2 2V4h16v12z"/>
        </svg>
      `;
      this.shadow.appendChild(this.btnEl);

      // Chat Window HTML
      this.winEl = document.createElement('div');
      this.winEl.className = 'widget-window';
      this.winEl.innerHTML = `
        <div class="widget-header">
          <div class="header-title-box">
            <div class="header-avatar">${this.config.title.slice(0, 2).toUpperCase()}</div>
            <div class="header-text">
              <h3>${escapeHtml(this.config.title)}</h3>
              <p><span class="status-dot"></span> ${escapeHtml(this.config.subtitle)}</p>
            </div>
          </div>
          <div class="header-actions">
            <button class="icon-btn clear-btn" title="Ricomincia chat">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/></svg>
            </button>
            <button class="icon-btn close-btn" title="Chiudi">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6L6 18M6 6l12 12"/></svg>
            </button>
          </div>
        </div>
        <div class="widget-body" id="messages"></div>
        <div class="widget-composer">
          <div class="input-row">
            <input type="text" class="widget-input" placeholder="${escapeHtml(this.config.placeholder)}" />
            <button class="send-btn" aria-label="Invia">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"/></svg>
            </button>
          </div>
          <div class="composer-badge">Zero allucinazioni · Risposte verificate</div>
        </div>
      `;
      this.shadow.appendChild(this.winEl);
      document.body.appendChild(this.container);

      // Cache elements
      this.bodyEl = this.shadow.querySelector('#messages');
      this.inputEl = this.shadow.querySelector('.widget-input');
      this.sendBtn = this.shadow.querySelector('.send-btn');
      this.closeBtn = this.shadow.querySelector('.close-btn');
      this.clearBtn = this.shadow.querySelector('.clear-btn');

      // Bind events
      this.btnEl.addEventListener('click', () => this.toggle());
      this.closeBtn.addEventListener('click', () => this.close());
      this.clearBtn.addEventListener('click', () => this.reset());
      this.sendBtn.addEventListener('click', () => this.submit());
      this.inputEl.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') this.submit();
      });

      // Delegate copy code
      this.shadow.addEventListener('click', (e) => {
        const copyBtn = e.target.closest('.copy-btn');
        if (copyBtn) {
          const raw = decodeURIComponent(copyBtn.getAttribute('data-code'));
          navigator.clipboard.writeText(raw).then(() => {
            copyBtn.textContent = 'Copiato!';
            setTimeout(() => { copyBtn.textContent = 'Copia'; }, 2000);
          });
        }
      });
    }

    async loadFaq() {
      try {
        const res = await fetch(this.config.faqUrl, { cache: 'no-cache' });
        this.db = await res.json();
        for (const e of this.db.entries || []) {
          if (e.slug) this.bySlug.set(e.slug, e);
        }
        this.renderWelcome();
      } catch (err) {
        console.error('[ZeroChatWidget] Errore caricamento FAQ:', err);
        this.addMessage('bot', 'Impossibile caricare il database delle risposte da ' + this.config.faqUrl);
      }
    }

    renderWelcome() {
      const welcome = this.config.greeting ||
        this.db?.config?.welcome ||
        `Ciao! Sono il tuo assistente verificato. Chiedimi qualsiasi cosa su **${this.config.title}**.`;

      const starterChips = (this.db?.config?.suggest || []).map(s => {
        const entry = this.bySlug.get(s);
        return entry ? { label: entry.question, query: entry.question } : null;
      }).filter(Boolean);

      this.addMessage('bot', welcome, starterChips);
    }

    toggle() {
      if (this.isOpen) this.close();
      else this.open();
    }

    open() {
      this.isOpen = true;
      this.winEl.classList.add('open');
      this.btnEl.innerHTML = `
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M18 6L6 18M6 6l12 12"/></svg>
      `;
      setTimeout(() => this.inputEl.focus(), 200);
    }

    close() {
      this.isOpen = false;
      this.winEl.classList.remove('open');
      this.btnEl.innerHTML = `
        <svg viewBox="0 0 24 24"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H6l-2 2V4h16v12z"/></svg>
      `;
    }

    reset() {
      this.bodyEl.innerHTML = '';
      this.lastEntry = null;
      this.askedSlugs.clear();
      this.renderWelcome();
    }

    submit() {
      const q = this.inputEl.value.trim();
      if (!q || this.isStreaming) return;
      this.inputEl.value = '';
      this.ask(q);
    }

    ask(query) {
      if (!this.isOpen) this.open();
      this.addMessage('user', query);

      // Check deterministic tools fast-path if available
      if (window.ZeroTools || window.FabTools) {
        const tools = window.ZeroTools || window.FabTools;
        const hit = tools.detect(query);
        if (hit) {
          this.streamBotAnswer(hit.answer, hit.suggest || []);
          return;
        }
      }

      if (!this.db) return;
      const matched = this.match(query);
      if (matched) {
        this.lastEntry = matched;
        if (matched.slug) this.askedSlugs.add(matched.slug);
        const ans = Array.isArray(matched.answers)
          ? matched.answers[Math.floor(Math.random() * matched.answers.length)]
          : matched.answers;

        const chips = (matched.suggest || []).map(s => {
          const e = this.bySlug.get(s);
          return e ? { label: e.question, query: e.question } : null;
        }).filter(Boolean);

        this.streamBotAnswer(ans, chips);
      } else {
        const fallbacks = this.db.fallbacks || ['Non ho una risposta verificata per questa richiesta. Prova a riformulare o scegli uno degli argomenti suggeriti.'];
        const fb = fallbacks[Math.floor(Math.random() * fallbacks.length)];
        const restartChips = (this.db.config?.suggest || []).map(s => {
          const e = this.bySlug.get(s);
          return e ? { label: e.question, query: e.question } : null;
        }).filter(Boolean);

        this.streamBotAnswer(fb, restartChips);
      }
    }

    match(query) {
      const inNorm = norm(query);
      const inToks = tokens(query);
      const pool = (this.db.entries || []).concat(this.db.smalltalk || []);

      let best = null, bestScore = 0;
      for (const entry of pool) {
        const s = scoreEntry(entry, inNorm, inToks);
        if (s > bestScore) {
          bestScore = s;
          best = entry;
        }
      }

      const threshold = this.db.config?.matchThreshold ?? 0.75;
      return (best && bestScore >= threshold) ? best : null;
    }

    addMessage(role, text, chips = []) {
      const row = document.createElement('div');
      row.className = `msg-row ${role}`;
      const bubble = document.createElement('div');
      bubble.className = 'bubble';
      bubble.innerHTML = renderMd(text);
      row.appendChild(bubble);

      if (chips && chips.length > 0) {
        const chipsBox = document.createElement('div');
        chipsBox.className = 'chips-container';
        chips.forEach(c => {
          const chip = document.createElement('button');
          chip.className = 'chip';
          chip.textContent = c.label;
          chip.addEventListener('click', () => this.ask(c.query));
          chipsBox.appendChild(chip);
        });
        row.appendChild(chipsBox);
      }

      this.bodyEl.appendChild(row);
      this.bodyEl.scrollTop = this.bodyEl.scrollHeight;
    }

    streamBotAnswer(fullText, chips = []) {
      this.isStreaming = true;
      const row = document.createElement('div');
      row.className = 'msg-row bot';
      const bubble = document.createElement('div');
      bubble.className = 'bubble';
      row.appendChild(bubble);
      this.bodyEl.appendChild(row);

      const words = fullText.split(' ');
      let curIdx = 0;
      const step = 2;

      const tick = () => {
        curIdx += step;
        if (curIdx >= words.length) {
          bubble.innerHTML = renderMd(fullText);
          this.isStreaming = false;

          if (chips && chips.length > 0) {
            const chipsBox = document.createElement('div');
            chipsBox.className = 'chips-container';
            chips.forEach(c => {
              const chip = document.createElement('button');
              chip.className = 'chip';
              chip.textContent = c.label;
              chip.addEventListener('click', () => this.ask(c.query));
              chipsBox.appendChild(chip);
            });
            row.appendChild(chipsBox);
          }
          this.bodyEl.scrollTop = this.bodyEl.scrollHeight;
        } else {
          const partial = words.slice(0, curIdx).join(' ');
          bubble.innerHTML = renderMd(partial) + '<span class="typing-cursor"></span>';
          this.bodyEl.scrollTop = this.bodyEl.scrollHeight;
          setTimeout(tick, 22);
        }
      };
      tick();
    }

    adjustColor(hex, percent) {
      hex = hex.replace(/^\s*#|\s*$/g, '');
      if (hex.length === 3) hex = hex.replace(/(.)/g, '$1$1');
      const num = parseInt(hex, 16);
      const amt = Math.round(2.55 * percent);
      const R = (num >> 16) + amt;
      const G = (num >> 8 & 0x00FF) + amt;
      const B = (num & 0x0000FF) + amt;
      return '#' + (0x1000000 + (R < 255 ? R < 1 ? 0 : R : 255) * 0x10000 +
        (G < 255 ? G < 1 ? 0 : G : 255) * 0x100 +
        (B < 255 ? B < 1 ? 0 : B : 255)).toString(16).slice(1);
    }
  }

  // Auto-init on script tag with data-* attributes
  let autoInstance = null;
  const currentScript = document.currentScript;
  if (currentScript) {
    const faqUrl = currentScript.getAttribute('data-faq') || 'faq.json';
    const title = currentScript.getAttribute('data-title') || 'Assistente';
    const accentColor = currentScript.getAttribute('data-color') || '#0284c7';
    const position = currentScript.getAttribute('data-position') || 'bottom-right';

    window.addEventListener('DOMContentLoaded', () => {
      autoInstance = new ZeroChatWidgetElement({ faqUrl, title, accentColor, position });
    });
  }

  window.ZeroChatWidget = {
    init(options) {
      if (!autoInstance) {
        autoInstance = new ZeroChatWidgetElement(options);
      }
      return autoInstance;
    },
    open() { autoInstance?.open(); },
    close() { autoInstance?.close(); },
    ask(q) { autoInstance?.ask(q); }
  };
})();
