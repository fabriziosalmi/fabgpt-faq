/* FabGPT-FAQ – deterministic micro-tools (subnet, cron, chmod, JWT, epoch, ports).
 * Pure functions, no DOM, no network: shared by the chat fast-path (app.js),
 * the /tools/ pages and the node test harness (tools_test.mjs).
 * Every answer is computed, never generated: this code cannot hallucinate.
 */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.FabTools = factory();
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  /* ---------- subnet / CIDR ---------- */

  function parseIp(s) {
    const p = s.split('.').map(Number);
    if (p.length !== 4 || p.some(n => !Number.isInteger(n) || n < 0 || n > 255)) return null;
    return ((p[0] << 24) | (p[1] << 16) | (p[2] << 8) | p[3]) >>> 0;
  }

  function fmtIp(n) {
    return [(n >>> 24) & 255, (n >>> 16) & 255, (n >>> 8) & 255, n & 255].join('.');
  }

  function subnetInfo(ipStr, prefix) {
    const ip = parseIp(ipStr);
    if (ip === null || prefix < 0 || prefix > 32) return null;
    const mask = prefix === 0 ? 0 : (0xffffffff << (32 - prefix)) >>> 0;
    const network = (ip & mask) >>> 0;
    const broadcast = (network | (~mask >>> 0)) >>> 0;
    const total = Math.pow(2, 32 - prefix);
    let hosts, firstHost, lastHost;
    if (prefix >= 31) {
      hosts = prefix === 31 ? 2 : 1;           // RFC 3021 point-to-point / host route
      firstHost = network; lastHost = broadcast;
    } else {
      hosts = total - 2;
      firstHost = network + 1; lastHost = broadcast - 1;
    }
    const priv = (network >>> 24) === 10 ||
      ((network >>> 24) === 172 && ((network >>> 16) & 255) >= 16 && ((network >>> 16) & 255) <= 31) ||
      ((network >>> 24) === 192 && ((network >>> 16) & 255) === 168);
    return {
      input: ipStr + '/' + prefix, prefix: prefix,
      network: fmtIp(network), broadcast: fmtIp(broadcast),
      mask: fmtIp(mask), wildcard: fmtIp(~mask >>> 0),
      totalAddresses: total, usableHosts: hosts,
      firstHost: fmtIp(firstHost), lastHost: fmtIp(lastHost),
      isPrivate: priv,
    };
  }

  function subnetMd(i) {
    let md = '**' + i.input + '** – calcolo deterministico:\n\n';
    md += '- **Rete**: `' + i.network + '` · **Broadcast**: `' + i.broadcast + '`\n';
    md += '- **Maschera**: `' + i.mask + '` (wildcard `' + i.wildcard + '`)\n';
    md += '- **Host usabili**: **' + i.usableHosts.toLocaleString('it-IT') + '**';
    if (i.prefix < 31) md += ' (da `' + i.firstHost + '` a `' + i.lastHost + '`)';
    else if (i.prefix === 31) md += ' (punto-punto RFC 3021: `' + i.firstHost + '` e `' + i.lastHost + '`)';
    else md += ' (host route: il solo `' + i.network + '`)';
    md += '\n- Spazio **' + (i.isPrivate ? 'privato (RFC 1918)' : 'pubblico') + '**, ' +
      i.totalAddresses.toLocaleString('it-IT') + ' indirizzi totali';
    return md;
  }

  /* ---------- cron ---------- */

  var CRON_SHORTCUTS = {
    '@reboot': "all'avvio del sistema", '@yearly': 'una volta all\'anno (1 gennaio, 00:00)',
    '@annually': 'una volta all\'anno (1 gennaio, 00:00)', '@monthly': 'il primo del mese alle 00:00',
    '@weekly': 'ogni domenica alle 00:00', '@daily': 'ogni giorno alle 00:00',
    '@midnight': 'ogni giorno alle 00:00', '@hourly': 'a ogni ora esatta',
  };
  var DOW = ['domenica', 'lunedì', 'martedì', 'mercoledì', 'giovedì', 'venerdì', 'sabato', 'domenica'];
  var MONTHS = ['', 'gennaio', 'febbraio', 'marzo', 'aprile', 'maggio', 'giugno',
    'luglio', 'agosto', 'settembre', 'ottobre', 'novembre', 'dicembre'];

  var PLURAL = { minuto: 'minuti', ora: 'ore', giorno: 'giorni', mese: 'mesi' };

  function fieldDesc(v, unit, names) {
    if (v === '*') return 'ogni ' + unit;
    var m = v.match(/^\*\/(\d+)$/);
    if (m) return 'ogni ' + m[1] + ' ' + (+m[1] === 1 ? unit : (PLURAL[unit] || unit));
    return v.split(',').map(function (part) {
      var r = part.match(/^(\d+)-(\d+)(?:\/(\d+))?$/);
      var nm = function (n) { return names ? (names[+n] || n) : n; };
      if (r) return 'da ' + nm(r[1]) + ' a ' + nm(r[2]) + (r[3] ? ' ogni ' + r[3] : '');
      return String(nm(part));
    }).join(', ');
  }

  function validCronField(v, min, max) {
    return v.split(',').every(function (part) {
      var m = part.match(/^(\*|\d+|\d+-\d+)(?:\/\d+)?$/);
      if (!m) return false;
      var nums = (part.match(/\d+/g) || []).map(Number).filter(function (_, i) { return i < 2; });
      return nums.every(function (n) { return n >= min && n <= max; });
    });
  }

  function explainCron(expr) {
    expr = expr.trim().replace(/\s+/g, ' ');
    if (CRON_SHORTCUTS[expr]) return '`' + expr + '` esegue ' + CRON_SHORTCUTS[expr] + '.';
    var f = expr.split(' ');
    if (f.length !== 5) return null;
    var limits = [[0, 59], [0, 23], [1, 31], [1, 12], [0, 7]];
    for (var i = 0; i < 5; i++) if (!validCronField(f[i], limits[i][0], limits[i][1])) return null;
    var md = '`' + expr + '` – lettura campo per campo:\n\n';
    md += '- **Minuto**: ' + fieldDesc(f[0], 'minuto') + '\n';
    md += '- **Ora**: ' + fieldDesc(f[1], 'ora') + '\n';
    md += '- **Giorno del mese**: ' + fieldDesc(f[2], 'giorno') + '\n';
    md += '- **Mese**: ' + fieldDesc(f[3], 'mese', MONTHS) + '\n';
    md += '- **Giorno della settimana**: ' + fieldDesc(f[4], 'giorno', DOW);
    // the classic surprise: dom + dow together are OR, not AND
    if (f[2] !== '*' && f[4] !== '*') {
      md += '\n\n⚠️ Giorno del mese **e** giorno della settimana insieme sono in **OR**, non in AND: il job gira se *almeno uno* dei due combacia.';
    }
    if (f[0].indexOf('*') === 0 && f[0] !== '*' ) {
      // */n minutes: fine as is
    } else if (f[0] === '*' && f[1] !== '*') {
      md += '\n\n⚠️ Minuto `*` con ora fissa = il job gira **60 volte** in quell\'ora. Se intendevi "una volta", il minuto va fissato (es. `0`).';
    }
    return md;
  }

  /* ---------- chmod / permessi ---------- */

  function octalToRwx(digit) {
    var n = +digit;
    return (n & 4 ? 'r' : '-') + (n & 2 ? 'w' : '-') + (n & 1 ? 'x' : '-');
  }

  function rwxToOctal(t) {
    return (t[0] === 'r' ? 4 : 0) + (t[1] === 'w' ? 2 : 0) + (t[2] === 'x' ? 1 : 0);
  }

  function explainChmod(input) {
    var oct = null, special = '';
    var m = String(input).trim().match(/^([0-7])?([0-7]{3})$/);
    if (m) { oct = m[2]; if (m[1]) special = m[1]; }
    else {
      var r = String(input).trim().match(/^([r-][w-][xsS-]){1}([r-][w-][xsS-]){1}([r-][w-][xtT-]){1}$/);
      if (r) {
        var t = String(input).trim().replace(/[sStT]/g, 'x');
        oct = '' + rwxToOctal(t.slice(0, 3)) + rwxToOctal(t.slice(3, 6)) + rwxToOctal(t.slice(6, 9));
      }
    }
    if (!oct) return null;
    var who = ['Proprietario', 'Gruppo', 'Altri'];
    var md = '**chmod ' + (special || '') + oct + '** = `' +
      octalToRwx(oct[0]) + octalToRwx(oct[1]) + octalToRwx(oct[2]) + '`\n\n';
    for (var i = 0; i < 3; i++) {
      var n = +oct[i], parts = [];
      if (n & 4) parts.push('lettura');
      if (n & 2) parts.push('scrittura');
      if (n & 1) parts.push('esecuzione');
      md += '- **' + who[i] + '** (`' + oct[i] + '`): ' + (parts.length ? parts.join(' + ') : 'nessun permesso') + '\n';
    }
    if (special) {
      var s = +special, sp = [];
      if (s & 4) sp.push('**setuid** (esegue con l\'identità del proprietario)');
      if (s & 2) sp.push('**setgid** (esegue col gruppo / eredita il gruppo nelle directory)');
      if (s & 1) sp.push('**sticky bit** (in una directory, cancella solo chi possiede il file)');
      md += '- **Bit speciali** (`' + special + '`): ' + sp.join(', ') + '\n';
    }
    if (oct === '777') md += '\n⚠️ `777` non è mai la soluzione: chiunque può scrivere ed eseguire. Il problema vero è quasi sempre utente o gruppo sbagliato.';
    if (oct === '600') md += '\nÈ il permesso giusto per chiavi private e secrets: solo il proprietario legge e scrive.';
    return md;
  }

  /* ---------- JWT (decode only, no verification) ---------- */

  function b64urlDecode(s) {
    s = s.replace(/-/g, '+').replace(/_/g, '/');
    while (s.length % 4) s += '=';
    try {
      if (typeof atob === 'function') {
        return decodeURIComponent(Array.prototype.map.call(atob(s), function (c) {
          return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
        }).join(''));
      }
      return Buffer.from(s, 'base64').toString('utf8');
    } catch (e) { return null; }
  }

  function decodeJwt(tok) {
    var parts = tok.trim().split('.');
    if (parts.length < 2) return null;
    var h = b64urlDecode(parts[0]), p = b64urlDecode(parts[1]);
    if (!h || !p) return null;
    var header, payload;
    try { header = JSON.parse(h); payload = JSON.parse(p); } catch (e) { return null; }
    var md = '**JWT decodificato** (solo lettura – la firma NON è verificata qui):\n\n';
    md += '**Header**:\n```json\n' + JSON.stringify(header, null, 2) + '\n```\n';
    md += '**Payload**:\n```json\n' + JSON.stringify(payload, null, 2) + '\n```\n';
    var now = payload && payload.exp ? payload.exp : null;
    if (now) {
      var d = new Date(now * 1000);
      md += '\n- **Scadenza (`exp`)**: ' + d.toISOString().replace('T', ' ').slice(0, 19) + ' UTC';
    }
    if (header && String(header.alg).toLowerCase() === 'none') {
      md += '\n\n⚠️ `alg: none` – un token senza firma: qualunque backend che lo accetti è vulnerabile.';
    }
    md += '\n\nUn JWT è **codificato, non cifrato**: chiunque lo intercetti legge tutto il payload. Mai metterci segreti.';
    return md;
  }

  /* ---------- unix epoch ---------- */

  function explainEpoch(numStr) {
    var n = Number(numStr);
    if (!Number.isFinite(n)) return null;
    var ms = String(Math.trunc(n)).length >= 13;
    var d = new Date(ms ? n : n * 1000);
    if (isNaN(d.getTime())) return null;
    var iso = d.toISOString().replace('T', ' ').slice(0, 19);
    return '**' + numStr + '** è un timestamp Unix' + (ms ? ' in millisecondi' : '') + ':\n\n' +
      '- **UTC**: `' + iso + '`\n' +
      '- Conversione al volo da terminale: `date -d @' + (ms ? Math.floor(n / 1000) : n) + '` (Linux) · `date -r ' + (ms ? Math.floor(n / 1000) : n) + '` (macOS)';
  }

  /* ---------- safe arithmetic (recursive descent, no eval) ---------- */

  function evalArith(expr) {
    var s = expr.replace(/,/g, '.').replace(/\s+/g, '');
    if (!s || s.length > 80 || !/^[\d+\-*/().%^]+$/.test(s)) return null;
    var i = 0;
    function parseExpr() {
      var v = parseTerm();
      while (i < s.length && (s[i] === '+' || s[i] === '-')) {
        var op = s[i++]; var r = parseTerm();
        if (r === null) return null;
        v = op === '+' ? v + r : v - r;
      }
      return v;
    }
    function parseTerm() {
      var v = parseFactor();
      while (i < s.length && (s[i] === '*' || s[i] === '/' || s[i] === '%')) {
        var op = s[i++]; var r = parseFactor();
        if (r === null || v === null) return null;
        if (op === '*') v = v * r;
        else if (op === '%') v = v % r;
        else { if (r === 0) return Infinity; v = v / r; }
      }
      return v;
    }
    function parseFactor() {
      var v = parseUnary();
      if (i < s.length && s[i] === '^') {
        i++; var r = parseFactor();
        if (r === null || v === null) return null;
        v = Math.pow(v, r);
      }
      return v;
    }
    function parseUnary() {
      if (s[i] === '-') { i++; var u = parseUnary(); return u === null ? null : -u; }
      if (s[i] === '+') { i++; return parseUnary(); }
      return parseAtom();
    }
    function parseAtom() {
      if (s[i] === '(') {
        i++; var v = parseExpr();
        if (s[i] !== ')') return null;
        i++; return v;
      }
      var m = s.slice(i).match(/^\d+(?:\.\d+)?/);
      if (!m) return null;
      i += m[0].length;
      return parseFloat(m[0]);
    }
    var out = parseExpr();
    if (out === null || i !== s.length || !isFinite(out)) return null;
    return out;
  }

  function arithMd(expr, result) {
    var shown = Math.abs(result) >= 1e15 ? result.toExponential(6)
      : (Math.round(result * 1e9) / 1e9).toLocaleString('it-IT', { maximumFractionDigits: 9 });
    return '`' + expr.trim() + '` = **' + shown + '**\n\nCalcolo esatto, eseguito in locale – niente modello, niente allucinazioni.';
  }

  /* ---------- well-known port lookup (dataset injected) ---------- */

  function portMd(p) {
    var md = '**Porta ' + p.port + '/' + p.proto + ' – ' + p.service + '**\n\n' + p.desc;
    if (p.risk) md += '\n\n**Nota di sicurezza**: ' + p.risk;
    md += '\n\nVerifica se è in ascolto: `ss -' + (p.proto === 'udp' ? 'u' : 't') + 'lnp | grep :' + p.port + '`';
    return md;
  }

  /* ---------- fast-path detector ---------- */

  function detect(text, opts) {
    opts = opts || {};
    var t = String(text).trim();

    // JWT (most specific signature first)
    var jwt = t.match(/\beyJ[A-Za-z0-9_-]{4,}\.[A-Za-z0-9_-]{4,}\.[A-Za-z0-9_-]*/);
    if (jwt) {
      var jm = decodeJwt(jwt[0]);
      if (jm) return { kind: 'jwt', answer: jm, suggest: opts.jwtSuggest || [], label: 'Decodifica JWT' };
    }

    // CIDR
    var c = t.match(/\b(\d{1,3}(?:\.\d{1,3}){3})\/(\d{1,2})\b/);
    if (c) {
      var info = subnetInfo(c[1], +c[2]);
      if (info) return { kind: 'subnet', answer: subnetMd(info), suggest: opts.subnetSuggest || [], label: 'Calcolo subnet ' + info.input };
    }

    // chmod (needs the keyword or an rwx triple, bare digits are too ambiguous)
    var ch = t.match(/\bchmod\s+([0-7]{3,4})\b/i) || t.match(/(?:^|\s)((?:[r-][w-][xsS-]){2}[r-][w-][xtT-])(?:\s|$)/);
    if (ch) {
      var cm = explainChmod(ch[1]);
      if (cm) return { kind: 'chmod', answer: cm, suggest: opts.chmodSuggest || [], label: 'Permessi ' + ch[1] };
    }

    // cron: 5 fields, and either cron-ish syntax or the word "cron"
    var cronWord = /\bcron/i.test(t);
    var mCron = t.match(/(?:^|\s)((?:[\d*\/,-]+\s+){4}[\d*\/,-]+)(?:\s|$)/);
    if (mCron && (cronWord || /[*\/]/.test(mCron[1]))) {
      var ce = explainCron(mCron[1]);
      if (ce) return { kind: 'cron', answer: ce, suggest: opts.cronSuggest || [], label: 'Cron ' + mCron[1].trim() };
    }
    var sc = t.match(/@(?:reboot|yearly|annually|monthly|weekly|daily|midnight|hourly)\b/);
    if (sc) {
      var se = explainCron(sc[0]);
      if (se) return { kind: 'cron', answer: se, suggest: opts.cronSuggest || [], label: 'Cron ' + sc[0] };
    }

    // well-known port ("porta 443")
    var pm = t.match(/\bporta\s+(\d{1,5})\b/i);
    if (pm && opts.ports) {
      var pdata = opts.ports[pm[1]];
      if (pdata) return { kind: 'port', answer: portMd(pdata), suggest: pdata.suggest || [], label: 'Porta ' + pm[1] };
    }

    // unix epoch: 10 digits in plausible range, or 13 digits; alone or with keyword
    var em = t.match(/\b(1[4-9]\d{8}|2[0-2]\d{8})(\d{3})?\b/);
    if (em && (/\b(timestamp|epoch|unix)\b/i.test(t) || t === em[0])) {
      var ee = explainEpoch(em[0]);
      if (ee) return { kind: 'epoch', answer: ee, suggest: opts.epochSuggest || [], label: 'Timestamp ' + em[0] };
    }

    // plain arithmetic ("1+1?", "quanto fa 12*34?"): last, so cron/CIDR win first
    var at = t.replace(/^(quanto\s+fa|quant'?\s*e'?|calcola(?:mi)?)\s*/i, '').replace(/[?=\s]+$/, '');
    if (/^[\d\s+\-*/().,%^]+$/.test(at) && /\d/.test(at) && /(?!^)[+*/%^]|(?!^)-/.test(at)) {
      var av = evalArith(at);
      if (av !== null) {
        return { kind: 'arith', answer: arithMd(at, av), suggest: opts.arithSuggest || [], label: 'Calcolo ' + at.trim() };
      }
    }

    return null;
  }

  return {
    parseIp: parseIp, fmtIp: fmtIp, subnetInfo: subnetInfo, subnetMd: subnetMd,
    explainCron: explainCron, explainChmod: explainChmod, decodeJwt: decodeJwt,
    explainEpoch: explainEpoch, portMd: portMd, evalArith: evalArith, detect: detect,
  };
});
