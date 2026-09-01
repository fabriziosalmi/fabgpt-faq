#!/usr/bin/env node
/* Gate T6: deterministic micro-tools (tools.js). Run: node tools_test.mjs */
import { createRequire } from 'module';
const require = createRequire(import.meta.url);
const T = require('./tools.js');

let pass = 0, fail = 0;
function ok(cond, name, extra) {
  if (cond) { pass++; }
  else { fail++; console.log(`  FAIL ${name}${extra ? ' – ' + extra : ''}`); }
}

/* subnet */
let s = T.subnetInfo('192.168.1.0', 24);
ok(s.network === '192.168.1.0' && s.broadcast === '192.168.1.255' && s.usableHosts === 254 &&
   s.mask === '255.255.255.0' && s.isPrivate, 'subnet /24');
s = T.subnetInfo('10.0.0.130', 26);
ok(s.network === '10.0.0.128' && s.broadcast === '10.0.0.191' && s.usableHosts === 62 &&
   s.firstHost === '10.0.0.129' && s.lastHost === '10.0.0.190', 'subnet /26 mid-block');
s = T.subnetInfo('172.16.0.0', 12);
ok(s.usableHosts === 1048574 && s.isPrivate, 'subnet /12 rfc1918');
s = T.subnetInfo('8.8.8.8', 32);
ok(s.usableHosts === 1 && !s.isPrivate, 'subnet /32 host route');
s = T.subnetInfo('10.0.0.0', 31);
ok(s.usableHosts === 2, 'subnet /31 rfc3021');
ok(T.subnetInfo('300.1.1.1', 24) === null, 'subnet invalid ip rejected');
ok(T.subnetInfo('10.0.0.1', 33) === null, 'subnet /33 rejected');

/* cron */
ok(/ogni 5 minuto|ogni 5 minuti/.test(T.explainCron('*/5 * * * *')), 'cron */5');
ok(/OR/.test(T.explainCron('0 3 1 * 1')), 'cron dom+dow OR warning');
ok(/60 volte/.test(T.explainCron('* 3 * * *')), 'cron *-minute warning');
ok(T.explainCron('99 * * * *') === null, 'cron minute 99 rejected');
ok(/avvio/.test(T.explainCron('@reboot')), 'cron @reboot');
ok(T.explainCron('foo bar') === null, 'cron garbage rejected');

/* chmod */
ok(/rwxr-xr-x/.test(T.explainChmod('755')), 'chmod 755 rwx');
ok(/rw-r--r--/.test(T.explainChmod('644')), 'chmod 644 rwx');
ok(/non è mai la soluzione/.test(T.explainChmod('777')), 'chmod 777 warning');
ok(/chiavi private/.test(T.explainChmod('600')), 'chmod 600 note');
ok(/setuid/.test(T.explainChmod('4755')), 'chmod 4755 setuid');
ok(T.explainChmod('rwxr-xr--') !== null && /754/.test(T.explainChmod('rwxr-xr--')), 'rwx->754');
ok(T.explainChmod('890') === null, 'chmod 890 rejected');

/* jwt: {"alg":"HS256","typ":"JWT"}.{"sub":"1234567890","name":"John Doe","iat":1516239022} */
const tok = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c';
ok(/John Doe/.test(T.decodeJwt(tok)), 'jwt decode payload');
ok(/NON è verificata/.test(T.decodeJwt(tok)), 'jwt no-verify disclaimer');
ok(T.decodeJwt('non.un.jwt') === null, 'jwt garbage rejected');

/* epoch */
ok(/2021/.test(T.explainEpoch('1609459200')), 'epoch 2021');
ok(/millisecondi/.test(T.explainEpoch('1609459200000')), 'epoch ms detected');

/* detect() routing */
const ports = { '443': { port: 443, proto: 'tcp', service: 'HTTPS', desc: 'x', risk: '', suggest: [] } };
ok(T.detect('quanti host ha 192.168.1.0/26?').kind === 'subnet', 'detect cidr in sentence');
ok(T.detect('*/5 * * * *').kind === 'cron', 'detect bare cron');
ok(T.detect('chmod 754 cosa significa?').kind === 'chmod', 'detect chmod');
ok(T.detect('754 cosa significa?') === null, 'bare 754 NOT detected (ambiguous)');
ok(T.detect(tok).kind === 'jwt', 'detect jwt');
ok(T.detect('porta 443', { ports }).kind === 'port', 'detect known port');
ok(T.detect('porta 49999', { ports }) === null, 'unknown port falls through to matcher');
ok(T.detect('1609459200').kind === 'epoch', 'detect bare epoch');
ok(T.detect('ho 1609459200 mele') === null, 'epoch inside prose NOT detected without keyword');
ok(T.detect("cos'è proxmox?") === null, 'plain question falls through');
ok(T.detect('1 2 3 4 5') === null, 'five plain digits NOT cron without syntax');

/* arithmetic */
ok(T.evalArith('1+1') === 2, 'arith 1+1');
ok(T.evalArith('2+3*4') === 14, 'arith precedence');
ok(T.evalArith('(2+3)*4') === 20, 'arith parens');
ok(T.evalArith('10/4') === 2.5, 'arith division');
ok(T.evalArith('2^10') === 1024, 'arith power');
ok(T.evalArith('-5+3') === -2, 'arith unary');
ok(T.evalArith('*/5 * * * *') === null, 'arith rejects cron');
ok(T.evalArith('1..2') === null, 'arith rejects malformed');
ok(T.detect('1+1?').kind === 'arith', 'detect 1+1?');
ok(T.detect('quanto fa 12*34?').kind === 'arith', 'detect quanto fa');
ok(T.detect('*/5 2 * * 1-5').kind === 'cron', 'cron still wins over arith');
ok(T.detect('192.168.1.0/24').kind === 'subnet', 'cidr still wins over arith');
ok(T.detect('42') === null, 'bare number not arith');
ok(T.detect('1609459200').kind === 'epoch', 'epoch still wins');

console.log(`${fail === 0 ? 'PASS' : 'FAIL'}  T6 tools: ${pass}/${pass + fail}`);
process.exit(fail === 0 ? 0 : 1);
