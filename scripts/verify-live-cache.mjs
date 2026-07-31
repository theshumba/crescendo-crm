// LIVE test against the real crescendocrm-5de1b project. Deliberately passive: it loads the
// app twice in one persistent browser profile and reads state. It never clicks, never edits,
// never calls a mutating function. Run scripts/backup-leads.mjs either side to prove the
// database is untouched.
//
// Run: npm run verify:live
import puppeteer from 'puppeteer-core';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const FILE = 'file://' + path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', 'crescendo-crm.html');
const PROFILE = '/tmp/crescendo-verify-profile';

function pass(name, ok, detail) { console.log((ok ? '  PASS  ' : '  FAIL  ') + name + (detail ? '  — ' + detail : '')); return ok; }

async function run(label, expectCache) {
  const browser = await puppeteer.launch({ executablePath: CHROME, headless: 'new', userDataDir: PROFILE, args: ['--no-sandbox'] });
  const page = await browser.newPage();
  const net = { listen: 0, write: 0, other: 0, bytes: 0 };
  page.on('response', async r => {
    const u = r.url();
    if (!/firestore\.googleapis\.com/.test(u)) return;
    if (/\/Listen\/channel/.test(u)) net.listen++;
    else if (/\/Write\/channel/.test(u)) net.write++;
    else net.other++;
    try { const b = await r.buffer(); net.bytes += b.length; } catch (_) {}
  });
  const errs = [];
  page.on('pageerror', e => errs.push(String(e)));
  // A rep who has logged in before, and NO local leads — so the app has nothing of its own to
  // push even if something went wrong.
  await page.evaluateOnNewDocument(() => {
    localStorage.removeItem('crescendo-leads');
    localStorage.setItem('crescendo-crm-user', 'Master');
    localStorage.setItem('crescendo-shared-pool-v1', '1');
  });
  await page.goto(FILE, { waitUntil: 'networkidle2', timeout: 60000 });
  await new Promise(r => setTimeout(r, 9000));
  const out = await page.evaluate(() => ({
    leads: state.leads.length,
    samples: state.leads.filter(l => l.source === 'sample').length,
    withCrm: state.leads.filter(l => l.status === 'crm').length,
    pending: (() => { try { return CrescendoSync.pendingCount(); } catch (_) { return -1; } })(),
    cloudKnownEmpty: CrescendoSync.__cloudKnownEmpty,
    seeded: !!CrescendoSync.__cloudSeeded,
    chip: (document.getElementById('sync-chip') || {}).textContent,
    stats: (() => { try { return CrescendoSync.stats(); } catch (_) { return null; } })()
  }));
  await browser.close();
  console.log(`\n[${label}] leads=${out.leads} crm=${out.withCrm} samples=${out.samples} pending=${out.pending} cloudKnownEmpty=${out.cloudKnownEmpty} seeded=${out.seeded}`);
  console.log(`[${label}] firestore responses: listen=${net.listen} write=${net.write} other=${net.other} bytes=${(net.bytes / 1024).toFixed(0)}kB`);
  console.log(`[${label}] snapshots:`, JSON.stringify(out.stats));
  if (errs.length) console.log(`[${label}] page errors:`, errs.slice(0, 3));
  return { out, net, errs };
}

fs.rmSync(PROFILE, { recursive: true, force: true });
console.log('=== FIRST LOAD (cold, empty cache) ===');
const a = await run('cold', false);
console.log('\n=== SECOND LOAD (same profile, cache warm) ===');
const b = await run('warm', true);

console.log('\n— RESULTS —');
let ok = true;
ok &= pass('the real leads load from the cloud', a.out.leads > 500 && a.out.samples === 0, a.out.leads + ' leads');
ok &= pass('the warm load still shows every lead', b.out.leads === a.out.leads, b.out.leads + ' leads');
ok &= pass('the cold load comes from the server', a.out.stats && a.out.stats.firstFromCache === false,
  'first snapshot fromCache=' + (a.out.stats || {}).firstFromCache);
ok &= pass('the warm load is served from disk, not re-downloaded', b.out.stats && b.out.stats.firstFromCache === true,
  JSON.stringify(b.out.stats));
ok &= pass('nothing was queued to write on either load', a.out.pending === 0 && b.out.pending === 0);
ok &= pass('the seed-push never armed', a.out.seeded === false && b.out.seeded === false &&
  a.out.cloudKnownEmpty !== true && b.out.cloudKnownEmpty !== true,
  'cold=' + a.out.cloudKnownEmpty + ' warm=' + b.out.cloudKnownEmpty);
ok &= pass('no page errors', a.errs.length === 0 && b.errs.length === 0);
fs.rmSync(PROFILE, { recursive: true, force: true });
process.exit(ok ? 0 : 1);
