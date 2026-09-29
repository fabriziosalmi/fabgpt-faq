/* ZeroGPT / Engine – Agnostic Standalone ChatGPT-like Chat Application.
 * No runtime dependencies. Configured via faq.json.
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
  let ctxEntry = null;
  const bySlug = new Map();
  const askedSlugs = new Set();
  const answerCursor = Object.create(null);

  /* Helper functions */
  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function renderMd(text) {
    if (window.ZeroMatcher && window.ZeroMatcher.renderMd) {
      return window.ZeroMatcher.renderMd(text);
    }
    // Fallback minimal markdown renderer
    return escapeHtml(text).replace(/\n/g, '<br>');
  }

  function inlineMd(text) {
    if (window.ZeroMatcher && window.ZeroMatcher.inlineMd) {
      return window.ZeroMatcher.inlineMd(text);
    }
    return escapeHtml(text);
  }

  function addBotRow() {
    const row = document.createElement('div');
    row.className = 'turn bot';
    const inner = document.createElement('div');
    inner.className = 'turn-inner';
    const avatar = document.createElement('div');
    avatar.className = 'avatar bot-avatar';
    avatar.textContent = (DB?.config?.botName || 'AI').slice(0, 2).toUpperCase();
    const body = document.createElement('div');
    body.className = 'turn-body';
    inner.appendChild(avatar);
    inner.appendChild(body);
    row.appendChild(inner);
    chatEl.appendChild(row);
    return body;
  }

  function addUserRow(text) {
    const row = document.createElement('div');
    row.className = 'turn user';
    const inner = document.createElement('div');
    inner.className = 'turn-inner';
    const body = document.createElement('div');
    body.className = 'turn-body';
    body.textContent = text;
    inner.appendChild(body);
    row.appendChild(inner);
    chatEl.appendChild(row);
    chatEl.scrollTop = chatEl.scrollHeight;
  }

  function streamAnswer(text, chips = []) {
    streaming = true;
    inputEl.disabled = true;
    sendEl.disabled = true;

    const body = addBotRow();
    const words = text.split(' ');
    let curIdx = 0;
    const step = 2;

    const tick = () => {
      curIdx += step;
      if (curIdx >= words.length) {
        body.innerHTML = renderMd(text);
        streaming = false;
        inputEl.disabled = false;
        sendEl.disabled = false;
        inputEl.focus();

        if (chips && chips.length > 0) {
          const chipsRow = document.createElement('div');
          chipsRow.className = 'chips-row';
          chips.forEach(c => {
            const btn = document.createElement('button');
            btn.className = 'chip-btn';
            btn.textContent = c.label;
            btn.addEventListener('click', () => ask(c.query));
            chipsRow.appendChild(btn);
          });
          body.appendChild(chipsRow);
        }
        chatEl.scrollTop = chatEl.scrollHeight;
      } else {
        const partial = words.slice(0, curIdx).join(' ');
        body.innerHTML = renderMd(partial) + '<span class="typing-cursor"></span>';
        chatEl.scrollTop = chatEl.scrollHeight;
        setTimeout(tick, 20);
      }
    };
    tick();
  }

  function ask(query) {
    const raw = query.trim();
    if (!raw || streaming) return;
    addUserRow(raw);

    // 1. Deterministic micro-tools fast-path
    if (window.ZeroTools || window.FabTools) {
      const tools = window.ZeroTools || window.FabTools;
      const hit = tools.detect(raw);
      if (hit) {
        streamAnswer(hit.answer, (hit.suggest || []).map(s => {
          const e = bySlug.get(s);
          return e ? { label: e.question, query: e.question } : null;
        }).filter(Boolean));
        return;
      }
    }

    // 2. Knowledge base matcher
    if (window.ZeroMatcher) {
      const entry = window.ZeroMatcher.match(raw, DB, { ctxEntry });
      if (entry) {
        ctxEntry = entry;
        if (entry.slug) askedSlugs.add(entry.slug);

        const variants = entry.answers || [];
        const n = variants.length;
        const idx = ((answerCursor[entry.id] ?? -1) + 1) % (n || 1);
        answerCursor[entry.id] = idx;
        const answer = variants[idx] || '';

        const chips = (entry.suggest || []).map(s => {
          const e = bySlug.get(s);
          return e ? { label: e.question, query: e.question } : null;
        }).filter(Boolean);

        streamAnswer(answer, chips);
        return;
      }
    }

    // 3. Fallback
    const fallbacks = DB.fallbacks || ['Nessuna risposta certificata trovata per questa domanda. Prova a riformulare.'];
    const fb = fallbacks[Math.floor(Math.random() * fallbacks.length)];
    const starterChips = (DB.config?.suggest || []).map(s => {
      const e = bySlug.get(s);
      return e ? { label: e.question, query: e.question } : null;
    }).filter(Boolean);
    streamAnswer(fb, starterChips);
  }

  /* Boot */
  async function boot() {
    try {
      const res = await fetch('faq.json', { cache: 'no-cache' });
      DB = await res.json();
      for (const e of DB.entries || []) {
        if (e.slug) bySlug.set(e.slug, e);
      }
    } catch (e) {
      const body = addBotRow();
      body.innerHTML = '<p>Impossibile caricare <code>faq.json</code>. Esegui il sito con un web server locale.</p>';
      return;
    }

    document.title = DB.config?.botName || 'ZeroGPT';
    const headerTitle = document.getElementById('header-title');
    if (headerTitle) headerTitle.textContent = DB.config?.botName || 'ZeroGPT';

    if (noteEl && DB.config?.footerNote) {
      noteEl.innerHTML = inlineMd(DB.config.footerNote);
    }
    if (inputEl && DB.config?.placeholder) {
      inputEl.placeholder = DB.config.placeholder;
    }

    // Welcome message
    const welcome = DB.config?.welcome || 'Ciao! Fai una domanda per iniziare.';
    const starterChips = (DB.config?.suggest || []).map(s => {
      const e = bySlug.get(s);
      return e ? { label: e.question, query: e.question } : null;
    }).filter(Boolean);
    streamAnswer(welcome, starterChips);

    // Deep link ?q=
    const params = new URLSearchParams(window.location.search);
    const qParam = params.get('q');
    if (qParam) {
      const e = bySlug.get(qParam) || DB.entries.find(x => x.id === qParam);
      if (e) {
        setTimeout(() => ask(e.question), 500);
      }
    }
  }

  // Event handlers
  formEl.addEventListener('submit', (e) => {
    e.preventDefault();
    const val = inputEl.value.trim();
    if (!val) return;
    inputEl.value = '';
    ask(val);
  });

  // Delegate copy button
  document.addEventListener('click', (e) => {
    const copyBtn = e.target.closest('.copy-code-btn');
    if (copyBtn) {
      const raw = decodeURIComponent(copyBtn.getAttribute('data-code') || '');
      if (raw) {
        navigator.clipboard.writeText(raw).then(() => {
          const span = copyBtn.querySelector('span');
          if (span) span.textContent = 'Copiato!';
          setTimeout(() => { if (span) span.textContent = 'Copia'; }, 2000);
        });
      }
    }
  });

  window.ZeroChatApp = { ask, boot };
  document.addEventListener('DOMContentLoaded', boot);
})();
