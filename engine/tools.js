/* ZeroGPT / Engine – Deterministic micro-tools & fast-path calculator.
 * Pure functions, zero network, zero hallucinations.
 * Supports Subnet/CIDR, Cron, Chmod, JWT, Epoch, Ports, and Custom Tool registration.
 */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else if (typeof define === 'function' && define.amd) define(factory);
  else {
    root.ZeroTools = factory();
    root.FabTools = root.ZeroTools; // Backwards compatibility
  }
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  /* ---------- Subnet / CIDR ---------- */
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
      hosts = prefix === 31 ? 2 : 1;
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
    let md = '**' + i.input + '**: calcolo deterministico:\n\n';
    md += '- **Rete**: `' + i.network + '` · **Broadcast**: `' + i.broadcast + '`\n';
    md += '- **Maschera**: `' + i.mask + '` (wildcard `' + i.wildcard + '`)\n';
    md += '- **Host usabili**: **' + i.usableHosts.toLocaleString('it-IT') + '**';
    if (i.prefix < 31) md += ' (da `' + i.firstHost + '` a `' + i.lastHost + '`)';
    md += '\n- Spazio **' + (i.isPrivate ? 'privato (RFC 1918)' : 'pubblico') + '**';
    return md;
  }

  /* ---------- Chmod Calculator ---------- */
  function parseOctal(s) {
    if (!/^[0-7]{3,4}$/.test(s)) return null;
    const digits = s.length === 4 ? s.slice(1) : s;
    const sym = ['---', '--x', '-w-', '-wx', 'r--', 'r-x', 'rw-', 'rwx'];
    const human = [];
    const roles = ['Proprietario (u)', 'Gruppo (g)', 'Altri (o)'];
    for (let i = 0; i < 3; i++) {
      const d = Number(digits[i]);
      const p = [];
      if (d & 4) p.push('lettura');
      if (d & 2) p.push('scrittura');
      if (d & 1) p.push('esecuzione');
      human.push(roles[i] + ': ' + (p.length ? p.join(', ') : 'nessun permesso'));
    }
    return {
      octal: s,
      symbolic: digits.split('').map(d => sym[Number(d)]).join(''),
      human: human,
    };
  }

  function chmodMd(info) {
    return '**chmod ' + info.octal + '**: permessi deterministici:\n\n' +
      '- Notazione simbolica: `' + info.symbolic + '`\n' +
      '- ' + info.human.join('\n- ');
  }

  /* ---------- JWT Decoder (Stateless, No verify) ---------- */
  function decodeJwt(token) {
    const parts = token.trim().split('.');
    if (parts.length !== 3) return null;
    function b64url(s) {
      s = s.replace(/-/g, '+').replace(/_/g, '/');
      while (s.length % 4) s += '=';
      try {
        if (typeof atob === 'function') return decodeURIComponent(escape(atob(s)));
        if (typeof Buffer !== 'undefined') return Buffer.from(s, 'base64').toString('utf8');
      } catch (_) { return null; }
      return null;
    }
    const h = b64url(parts[0]), p = b64url(parts[1]);
    if (!h || !p) return null;
    try {
      const header = JSON.parse(h), payload = JSON.parse(p);
      return { header, payload, rawHeader: h, rawPayload: p };
    } catch (_) { return null; }
  }

  function jwtMd(info) {
    let md = '**Decodifica JWT (deterministica, senza verifica firma)**:\n\n';
    md += '**Header**:\n```json\n' + JSON.stringify(info.header, null, 2) + '\n```\n\n';
    md += '**Payload**:\n```json\n' + JSON.stringify(info.payload, null, 2) + '\n```';
    if (info.payload.exp) {
      const d = new Date(info.payload.exp * 1000);
      const isPast = d.getTime() < Date.now();
      md += '\n\n- Scadenza (`exp`): **' + d.toISOString() + '** (' + (isPast ? 'scaduto' : 'valido') + ')';
    }
    return md;
  }

  /* ---------- Epoch / Timestamp ---------- */
  function epochInfo(ts) {
    const n = Number(ts);
    if (!Number.isFinite(n) || n < 0) return null;
    const ms = n < 1e11 ? n * 1000 : n; // auto detect seconds vs ms
    const d = new Date(ms);
    if (isNaN(d.getTime())) return null;
    return {
      input: ts,
      iso: d.toISOString(),
      utc: d.toUTCString(),
      local: d.toLocaleString('it-IT', { timeZoneName: 'short' }),
      relative: timeAgo(d.getTime())
    };
  }

  function timeAgo(ms) {
    const diff = Date.now() - ms;
    const abs = Math.abs(diff);
    const past = diff > 0;
    const min = 60000, hour = 3600000, day = 86400000;
    if (abs < min) return 'pochi secondi fa';
    if (abs < hour) return Math.floor(abs / min) + ' minuti ' + (past ? 'fa' : 'nel futuro');
    if (abs < day) return Math.floor(abs / hour) + ' ore ' + (past ? 'fa' : 'nel futuro');
    return Math.floor(abs / day) + ' giorni ' + (past ? 'fa' : 'nel futuro');
  }

  function epochMd(i) {
    return '**Timestamp ' + i.input + '**: conversione deterministica:\n\n' +
      '- **ISO 8601 (UTC)**: `' + i.iso + '`\n' +
      '- **Locale**: `' + i.local + '` (' + i.relative + ')';
  }

  /* ---------- Well-known Ports ---------- */
  function portMd(port, pinfo) {
    return '**Porta ' + port + ' (' + (pinfo.protocol || 'TCP') + ')**: ' + (pinfo.service || 'Servizio noto') + '\n\n' +
      (pinfo.desc || 'Porta di rete standard.') + (pinfo.security ? '\n\n*Nota di sicurezza:* ' + pinfo.security : '');
  }

  /* ---------- Custom Tool Registry ---------- */
  const customTools = [];
  function registerTool(toolDef) {
    // toolDef: { name, match(text), execute(matchResult) -> { kind, label, answer, suggest } }
    customTools.push(toolDef);
  }

  /* ---------- Universal Fast-Path Detector ---------- */
  function detect(text, opts = {}) {
    const raw = (text || '').trim();
    if (!raw) return null;

    // Check custom registered tools first
    for (const ct of customTools) {
      const m = ct.match(raw);
      if (m) {
        const res = ct.execute(m, raw);
        if (res) return res;
      }
    }

    // 1. Subnet CIDR: 192.168.1.0/24, 10.0.0.0/8
    const cidrMatch = raw.match(/^(?:(?:calcola|subnet|cidr|rete)\s+)?([0-9]{1,3}(?:\.[0-9]{1,3}){3})\/([0-9]{1,2})$/i);
    if (cidrMatch) {
      const s = subnetInfo(cidrMatch[1], Number(cidrMatch[2]));
      if (s) return { kind: 'subnet', label: s.input, answer: subnetMd(s), suggest: opts.subnetSuggest || [] };
    }

    // 2. Chmod: chmod 755, 644, 0700
    const chmodMatch = raw.match(/^(?:chmod\s+)?([0-7]{3,4})$/i);
    if (chmodMatch && (raw.toLowerCase().includes('chmod') || raw.length === 3 || raw.length === 4)) {
      const c = parseOctal(chmodMatch[1]);
      if (c) return { kind: 'chmod', label: 'chmod ' + c.octal, answer: chmodMd(c), suggest: opts.chmodSuggest || [] };
    }

    // 3. JWT string
    if (/^eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]*$/.test(raw)) {
      const j = decodeJwt(raw);
      if (j) return { kind: 'jwt', label: 'JWT Decode', answer: jwtMd(j), suggest: opts.jwtSuggest || [] };
    }

    // 4. Epoch: 1700000000 or timestamp 1700000000
    const epochMatch = raw.match(/^(?:epoch|timestamp|ts)?\s*([0-9]{9,13})$/i);
    if (epochMatch) {
      const ep = epochInfo(epochMatch[1]);
      if (ep) return { kind: 'epoch', label: 'Timestamp ' + ep.input, answer: epochMd(ep), suggest: opts.epochSuggest || [] };
    }

    // 5. Port lookup
    const portMatch = raw.match(/^(?:porta|port)\s*([0-9]{1,5})$/i);
    if (portMatch && opts.ports) {
      const pNum = portMatch[1];
      const pInfo = opts.ports[pNum];
      if (pInfo) {
        return {
          kind: 'port',
          label: 'Porta ' + pNum,
          answer: portMd(pNum, pInfo),
          suggest: pInfo.suggest || []
        };
      }
    }

    return null;
  }

  return {
    subnetInfo,
    subnetMd,
    parseOctal,
    chmodMd,
    decodeJwt,
    jwtMd,
    epochInfo,
    epochMd,
    detect,
    registerTool
  };
});
