// Network-sandboxed verification of the Crescendo CRM fixes.
// Every firebase / gstatic / googleapis request is ABORTED, so nothing here can touch the
// live cloud. unpkg (lucide, leaflet) is allowed because the app calls into them on render.
//
// Setup once:  npm install        (pulls puppeteer-core, drives the installed Chrome)
// Run:         npm run verify
import puppeteer from 'puppeteer-core';
import { fileURLToPath } from 'url';
import path from 'path';

const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const FILE = 'file://' + path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', 'crescendo-crm.html');

const results = [];
function check(name, pass, detail) {
  results.push({ name, pass, detail });
  console.log((pass ? '  PASS  ' : '  FAIL  ') + name + (detail ? '  — ' + detail : ''));
}

// LOCAL dates, matching the app. toISOString() is UTC, so between midnight and 1am BST the
// harness disagreed with the app by a day — the very bug the app was fixed for.
const localDay = (d) => d.toLocaleDateString('en-CA');
const today = localDay(new Date());
const yesterday = localDay(new Date(Date.now() - 864e5));

function seedLeads() {
  const mk = (id, name, over = {}) => Object.assign({
    id, businessName: name, description: 'desc', industry: 'Hospitality', address: 'Cambridge, UK',
    website: '', phones: [{ number: '01223 111222' }], emails: [{ address: 'a@b.com' }],
    contacts: [{ name: 'Sam Green', title: 'Owner', phone: '07700 900111', email: 'sam@b.com' }],
    activity: [], researchChecklist: [], source: 'manual', status: 'unqualified',
    qualification: null, crm: null, dateAdded: yesterday, assignedTo: 'Ameer Munj',
    _modAt: yesterday + 'T09:00:00.000Z', _modBy: 'Ameer Munj'
  }, over);
  return [
    mk('q1', 'Alpha Coffee', { status: 'qualified', qualification: { strategyDesign: 'x', experienceDesign: '', digitalCommerce: '', growthIntent: '', weaknessesOpportunities: '', dateQualified: yesterday } }),
    mk('q2', 'Beta Bakery', { status: 'qualified', industry: 'Retail', address: 'Oxford, UK', phones: [], contacts: [{ name: 'Jo', title: '', phone: '', email: '' }], qualification: { strategyDesign: '', experienceDesign: '', digitalCommerce: '', growthIntent: '', weaknessesOpportunities: '', dateQualified: yesterday } }),
    mk('q3', 'Gamma Garage', { status: 'qualified', industry: 'Automotive', address: 'London, UK', qualification: { strategyDesign: '', experienceDesign: '', digitalCommerce: '', growthIntent: '', weaknessesOpportunities: '', dateQualified: yesterday } }),
    mk('c1', 'Delta Deli', { status: 'crm', crm: { stage: 2, disposition: 'nurture', priority: 'medium', dateFirstContact: yesterday, dateLastContact: yesterday, followUpDate: '', meetingBooked: false, meetingDate: '', meetingNotes: '', notes: [], dateMovedToCRM: yesterday, dealValue: 15000, outcomeReason: '' },
      activity: [{ action: 'changed stage to Contacted', by: 'Ameer Munj', date: yesterday + 'T10:00:00.000Z' }, { action: 'moved to CRM', by: 'Ameer Munj', date: yesterday + 'T09:30:00.000Z' }] }),
    mk('c2', 'Epsilon Estates', { status: 'crm', industry: 'Property', crm: { stage: 1, disposition: 'nurture', priority: 'high', dateFirstContact: '', dateLastContact: '', followUpDate: yesterday, meetingBooked: false, meetingDate: '', meetingNotes: '', notes: [], dateMovedToCRM: yesterday, dealValue: 15000, outcomeReason: '' } })
  ];
}

const browser = await puppeteer.launch({ executablePath: CHROME, headless: 'new', args: ['--no-sandbox'] });
const page = await browser.newPage();
await page.setViewport({ width: 1400, height: 1000 });
await page.setRequestInterception(true);
let blocked = 0;
page.on('request', r => {
  const u = r.url();
  if (/firebase|firestore|gstatic|googleapis|google\.com/.test(u)) { blocked++; return r.abort(); }
  return r.continue();
});
const errors = [];
page.on('pageerror', e => errors.push(String(e)));
page.on('console', m => { if (m.type() === 'error') errors.push('console: ' + m.text()); });

// Seed a stale localStorage BEFORE the app boots, exactly like a rep opening yesterday's tab.
await page.evaluateOnNewDocument((leads, user) => {
  localStorage.clear();
  localStorage.setItem('crescendo-leads', JSON.stringify(leads));
  localStorage.setItem('crescendo-crm-user', user);
  localStorage.setItem('crescendo-shared-pool-v1', '1');
}, seedLeads(), 'Joshua Khalili');

await page.goto(FILE, { waitUntil: 'networkidle2', timeout: 45000 });
await new Promise(r => setTimeout(r, 1500));

// Dismiss any login/identity gate by setting the user directly if the picker is showing.
await page.evaluate(() => { if (typeof renderAll === 'function') renderAll(); });

console.log('\n— 0. STORED LEADS SURVIVE A LOAD —');
// Regression guard: loadState() swallows its own exceptions and falls back to the 3 demo
// leads, so anything that throws in there silently replaces a rep's whole book.
// Built-in researched lists (Cambridge Boutiques) are seeded on top of whatever localStorage
// held, by design — an existing rep must receive the list too. They are excluded here so this
// check keeps testing the thing it was written for: that stored leads win over the demo data.
const loaded = await page.evaluate(() => ({
  n: state.leads.length,
  samples: state.leads.filter(l => l.source === 'sample').length,
  ids: state.leads.filter(l => !l.list).map(l => l.id).sort(),
  listed: state.leads.filter(l => l.list).length
}));
check('localStorage leads load, no demo-data fallback',
  loaded.samples === 0 && loaded.ids.join(',') === 'c1,c2,q1,q2,q3',
  loaded.n + ' leads: ' + loaded.ids + (loaded.listed ? ' (+' + loaded.listed + ' list leads)' : ''));

console.log('\n— 1. WRITE AMPLIFICATION (the "move didn\'t stick" root cause) —');
const amp = await page.evaluate(() => {
  const before = state.leads.map(l => ({ id: l.id, m: l._modAt }));
  // Touch exactly ONE lead, the way a rep does.
  const lead = getLeadById('c1');
  lead.crm.priority = 'high';
  saveState();
  const after = state.leads.map(l => ({ id: l.id, m: l._modAt }));
  const restamped = after.filter((a, i) => a.m !== before[i].m).map(a => a.id);
  return { restamped, total: state.leads.length };
});
check('one edit re-stamps only that lead', amp.restamped.length === 1 && amp.restamped[0] === 'c1',
  `re-stamped ${amp.restamped.length}/${amp.total}: [${amp.restamped}]`);

const noop = await page.evaluate(() => {
  const before = state.leads.map(l => l._modAt);
  saveState(); saveState();
  return state.leads.filter((l, i) => l._modAt !== before[i]).map(l => l.id);
});
check('a save that changes nothing stamps nothing', noop.length === 0, '[' + noop + ']');

console.log('\n— 2. MOVE TO CRM —');
const moved = await page.evaluate(() => {
  moveToCRM('q1');
  const l = getLeadById('q1');
  return { status: l.status, followUp: l.crm.followUpDate, movedOn: l.crm.dateMovedToCRM, stageDate: l.crm.stageEnteredAt && l.crm.stageEnteredAt['1'],
           stillQualified: state.leads.filter(x => x.status === 'qualified').map(x => x.id) };
});
check('lead leaves Qualified', moved.status === 'crm' && !moved.stillQualified.includes('q1'), 'now ' + moved.status);
check('gets a follow-up date so it cannot dead-end', moved.followUp === today, 'followUp=' + moved.followUp);
check('stage entry dated', moved.stageDate === today, 'stage 1 entered ' + moved.stageDate);

console.log('\n— 3. STAGE DATES + TODAY COUNTS —');
const stages = await page.evaluate((yest) => {
  const c1 = getLeadById('c1');
  // Historic lead, no stageEnteredAt stored — must be read back out of its activity log.
  const derived = stageEnteredOn(c1, 2);
  setStage(c1, 3);
  saveState();
  return { derived, afterMove: stageEnteredOn(c1, 3), changedOn: stageChangedOn(c1), stage: c1.crm.stage };
}, yesterday);
check('historic stage date derived from activity', stages.derived === yesterday, 'stage 2 entered ' + stages.derived);
check('new stage change is dated today', stages.afterMove === today && stages.changedOn === today, stages.afterMove);

const counts = await page.evaluate(() => {
  const crm = state.leads.filter(l => l.status === 'crm');
  return {
    touchedToday: crm.filter(isTouchedToday).map(l => l.id),
    dueToday: crm.filter(isTodayLead).map(l => l.id),
    buckets: followUpCounts(crm)
  };
});
check('"worked today" counts leads moved today, not just due ones',
  counts.touchedToday.includes('q1') && counts.touchedToday.includes('c1'),
  'worked today: [' + counts.touchedToday + ']  due today: [' + counts.dueToday + ']');
check('follow-up buckets split overdue / today / none',
  counts.buckets.overdue === 1 && counts.buckets.today >= 1,
  JSON.stringify(counts.buckets));

console.log('\n— 4. OUTREACH UI —');
const ui = await page.evaluate(() => {
  showSection('crm');
  renderCRM();
  const strip = document.querySelector('.followup-strip');
  const chips = Array.from(document.querySelectorAll('.fu-chip')).map(b => b.textContent.replace(/\s+/g, ' ').trim());
  return { hasStrip: !!strip, chips };
});
check('follow-up strip lives in Outreach', ui.hasStrip, ui.chips.join(' | '));

const banner = await page.evaluate(() => {
  state.filters.crm.stage = '5';
  renderCRM();
  const n = document.querySelector('.filter-notice');
  const txt = n ? n.textContent.replace(/\s+/g, ' ').trim() : '';
  clearCRMFilters();
  renderCRM();
  return { shown: !!n, txt, gone: !document.querySelector('.filter-notice'), stage: state.filters.crm.stage };
});
check('hidden-by-filter is announced, and clearable', banner.shown && banner.gone && banner.stage === 'all', banner.txt.slice(0, 90));

const dateSort = await page.evaluate(() => {
  state.filters.crm.sort = 'date';
  const ids = getFilteredCRM().leads.map(l => l.id);
  state.filters.crm.sort = 'score';
  return ids;
});
check('"Sort by Date" actually sorts (newest movement first)', dateSort[0] === 'c1' || dateSort[0] === 'q1', '[' + dateSort + ']');

console.log('\n— 5. BOARD CARD OPENS THE RECORD —');
const board = await page.evaluate(() => {
  state.crmView = 'board';
  renderCRM();
  const card = document.querySelector('.kanban-card[data-action="open-crm-sheet"]');
  const colToday = document.querySelector('.kanban-column-today');
  const phoneOnCard = !!document.querySelector('.kanban-card .card-phone');
  if (card) card.click();
  const sheet = document.querySelector('.crm-sheet');
  const tel = sheet ? sheet.querySelector('a[href^="tel:"]') : null;
  const editor = sheet ? sheet.querySelector('select[data-action="change-stage"]') : null;
  const nav = sheet ? sheet.querySelectorAll('[data-action="crm-sheet-nav"]').length : 0;
  return { clickable: !!card, colToday: colToday ? colToday.textContent.trim() : '', phoneOnCard,
           sheetOpen: !!sheet, tel: tel ? tel.getAttribute('href') : '', hasEditor: !!editor, nav };
});
check('board cards are clickable', board.clickable);
check('board columns show how many landed today', !!board.colToday, board.colToday);
check('tapping a card opens the full record', board.sheetOpen && board.hasEditor && board.nav === 2);
check('the phone number is right there', board.phoneOnCard && !!board.tel, board.tel);

const nav = await page.evaluate(() => {
  const before = state.crmSheetId;
  const next = document.querySelector('.crm-sheet-nav[data-dir="1"]');
  if (next && !next.disabled) next.click();
  const after = state.crmSheetId;
  const close = document.querySelector('[data-action="close-crm-sheet"]');
  if (close) close.click();
  return { before, after, closed: !document.querySelector('.crm-sheet') };
});
check('Next walks to the following lead, and it closes', nav.after !== nav.before && nav.closed, nav.before + ' → ' + nav.after);

console.log('\n— 6. QUALIFIED LEADS FILTERS —');
const qual = await page.evaluate(() => {
  state.crmView = 'list';
  showSection('qualified-leads');
  renderQualifiedLeads();
  const inds = Array.from(document.querySelectorAll('[data-filter="ql-industry"] option')).map(o => o.value);
  const cities = Array.from(document.querySelectorAll('[data-filter="ql-city"] option')).map(o => o.value);
  const count = () => getFilteredQualified().leads.map(l => l.id);
  const q = state.filters.qualified;
  q.industry = 'Retail'; const byIndustry = count();
  q.industry = 'all'; q.city = 'London'; const byCity = count();
  q.city = 'all'; q.hasPhone = true; const byPhone = count();
  q.hasPhone = false;
  const phoneShown = !!document.querySelector('.lead-card-phone');
  return { inds, cities, byIndustry, byCity, byPhone, phoneShown };
});
check('industry filter offers the real industries', qual.inds.includes('Retail') && qual.inds.includes('Automotive'), qual.inds.join(','));
check('industry filter narrows the list', qual.byIndustry.length === 1 && qual.byIndustry[0] === 'q2', '[' + qual.byIndustry + ']');
check('city filter works', qual.cities.includes('London') && qual.byCity.length === 1 && qual.byCity[0] === 'q3', '[' + qual.byCity + ']');
check('"has phone" filter works', qual.byPhone.length === 1 && qual.byPhone[0] === 'q3', '[' + qual.byPhone + ']');
check('phone number shows on the qualified card', qual.phoneShown);

console.log('\n— 7. CALLS MOVE THE PIPELINE —');
const call = await page.evaluate(() => {
  const l = getLeadById('c2');            // stage 1, never contacted
  l.crm.followUpDate = '';
  logCall('c2', 'no_answer');
  const miss = { fu: l.crm.followUpDate, stage: l.crm.stage };
  logCall('c2', 'connected');
  const spoke = { fu: l.crm.followUpDate, stage: l.crm.stage, entered: stageEnteredOn(l, 2) };
  // Must never drag a lead backwards.
  setStage(l, 5);
  logCall('c2', 'connected');
  return { miss, spoke, afterLate: l.crm.stage };
});
check('a missed call still books the next attempt', !!call.miss.fu && call.miss.stage === 1, 'follow up ' + call.miss.fu);
check('getting through moves the lead to Contacted, dated', call.spoke.stage === 2 && call.spoke.entered === today, 'stage ' + call.spoke.stage + ' entered ' + call.spoke.entered);
check('a later-stage lead is never dragged backwards', call.afterLate === 5, 'stage ' + call.afterLate);

const dial = await page.evaluate(() => {
  state.pendingCall = null;
  const l = getLeadById('c1');
  l.crm.disposition = 'nurture';
  openDialer('c1', '01223 111222');
  return { pending: state.pendingCall && state.pendingCall.id };
});
check('dialling remembers the call so the outcome gets asked for', dial.pending === 'c1', 'pendingCall=' + dial.pending);

console.log('\n— 8. CSV EXPORT —');
const csv = await page.evaluate(() => {
  let captured = '';
  const origBlob = window.Blob;
  window.Blob = function (parts, opts) { captured = String(parts.join('')); return new origBlob(parts, opts); };
  const origCreate = URL.createObjectURL; URL.createObjectURL = () => 'blob:stub';
  const origRevoke = URL.revokeObjectURL; URL.revokeObjectURL = () => {};
  const origClick = HTMLAnchorElement.prototype.click; HTMLAnchorElement.prototype.click = function () {};
  try { exportLeadsCSV(); } finally {
    window.Blob = origBlob; URL.createObjectURL = origCreate; URL.revokeObjectURL = origRevoke;
    HTMLAnchorElement.prototype.click = origClick;
  }
  return { hasObj: captured.includes('[object Object]'), header: captured.split('\r\n')[0], sample: captured.split('\r\n')[1] || '' };
});
check('no more [object Object] in the Phone / Email columns', !csv.hasObj, csv.sample.slice(0, 110));
check('export carries the follow-up and stage dates', /Follow Up On/.test(csv.header) && /In Stage Since/.test(csv.header));

console.log('\n— 9. MERGE RULE (whose change survives) —');
const merge = await page.evaluate(() => {
  const L = (o) => Object.assign({ id: 'x' }, o);
  const before = {
    // Device clock says local is newer, server clock says remote is. Server must win.
    fastClock: mergeRemoteWins(L({ _modAt: '2026-07-31T23:00:00Z', _srvAt: '2026-07-31T10:00:00Z' }),
                               L({ _modAt: '2026-07-31T09:00:00Z', _srvAt: '2026-07-31T12:00:00Z' })),
    // No server stamps anywhere: fall back to the device clock, as before.
    noSrv:     mergeRemoteWins(L({ _modAt: '2026-07-31T09:00:00Z' }), L({ _modAt: '2026-07-31T10:00:00Z' })),
    tie:       mergeRemoteWins(L({ _modAt: '2026-07-31T09:00:00Z' }), L({ _modAt: '2026-07-31T09:00:00Z' }))
  };
  CrescendoSync.markLocalEdit('x');
  const guarded = mergeRemoteWins(L({ _modAt: '2020-01-01T00:00:00Z', _srvAt: '2020-01-01T00:00:00Z' }),
                                  L({ _modAt: '2030-01-01T00:00:00Z', _srvAt: '2030-01-01T00:00:00Z' }));
  return { ...before, guarded };
});
check('the server clock beats a phone with a fast clock', merge.fastClock === true);
check('device clocks still decide when nothing is server-stamped', merge.noSrv === true && merge.tie === false);
check('an unsynced local edit is never overwritten', merge.guarded === false);

console.log('\n— 10. BULK MOVE FROM QUALIFIED —');
const bulk = await page.evaluate(async () => {
  showSection('qualified-leads');
  renderQualifiedLeads();
  const btn = document.querySelector('[data-action="qual-select-all"]');
  if (btn) btn.click();
  const picked = (state.bulkSelection || []).length;
  await applyBulkAction('qualified', 'move-to-crm');
  // List leads sit in their own tab, so "the Qualified grid is empty" is what must hold here.
  return { picked, leftQualified: state.leads.filter(l => l.status === 'qualified' && !l.list).length,
           inCrm: state.leads.filter(l => l.status === 'crm').length };
});
check('select-all-shown then move sends the batch to Outreach',
  bulk.picked >= 2 && bulk.leftQualified === 0, bulk.picked + ' selected → ' + bulk.leftQualified + ' left, ' + bulk.inCrm + ' in CRM');

console.log('\n— 11. DATES —');
const dates = await page.evaluate(() => {
  const local = todayISO === new Date().toLocaleDateString('en-CA');
  todayISO = '2000-01-01';
  const changed = refreshToday();
  return { local, value: todayISO, rollover: changed && todayISO !== '2000-01-01' };
});
check('today is the local date, not UTC', dates.local, dates.value);
check('a tab left open rolls over to the new day', dates.rollover, 'restored to ' + dates.value);

console.log('\n— 12. WORK THE LIST —');
const work = await page.evaluate(() => {
  // Rebuild a realistic due list: everything is in CRM by now.
  const ids = state.leads.filter(l => l.status === 'crm').map(l => l.id);
  const day = d => d.toLocaleDateString('en-CA');
  const yest = day(new Date(Date.now() - 864e5));
  const older = day(new Date(Date.now() - 5 * 864e5));
  state.leads.forEach((l, i) => { if (l.crm) l.crm.followUpDate = i === 0 ? older : (i === 1 ? yest : todayISO); });
  showSection('crm');
  renderCRM();
  const btn = document.querySelector('[data-action="start-work-list"]');
  const label = btn ? btn.textContent.replace(/\s+/g, ' ').trim() : '';
  if (btn) btn.click();
  const first = state.crmSheetId;
  const queue = (state.workList || []).slice();
  const mostOverdueFirst = queue[0] === state.leads.find(l => l.crm && l.crm.followUpDate === older).id;
  return { ids: ids.length, label, first, queueLen: queue.length, mostOverdueFirst, sheetOpen: !!document.querySelector('.crm-sheet') };
});
check('Outreach offers a one-tap list of what is due', /Work the list/.test(work.label), work.label);
check('starting it opens the first record', work.sheetOpen && !!work.first, work.queueLen + ' in the queue');
check('most overdue comes first', work.mostOverdueFirst);

const worked = await page.evaluate(() => {
  const startId = state.crmSheetId;
  const queue = (state.workList || []).slice();
  // Logging a call should move the rep straight on, not strand them on a lead that is no
  // longer due.
  const sel = document.querySelector('.crm-sheet select[data-action="log-call"]');
  sel.value = 'no_answer';
  sel.dispatchEvent(new Event('change', { bubbles: true }));
  const movedOn = state.crmSheetId !== startId;
  const stillFrozen = JSON.stringify(state.workList) === JSON.stringify(queue);
  const logged = getLeadById(startId);
  return { movedOn, stillFrozen, fu: logged.crm.followUpDate, pos: document.querySelector('.crm-sheet-pos')?.textContent.trim() };
});
check('logging a call advances to the next lead', worked.movedOn, 'now at ' + worked.pos);
check('the queue stays frozen while you work it', worked.stillFrozen, 'follow-up pushed to ' + worked.fu);

const finish = await page.evaluate(() => {
  // Walk to the end; the last Next should finish the run rather than dead-end.
  for (let i = 0; i < 20 && state.workList; i++) {
    const next = document.querySelector('.crm-sheet [data-action="crm-sheet-nav"][data-dir="1"]:not([disabled])');
    if (!next) break;
    next.click();
  }
  const fin = document.querySelector('.crm-sheet [data-action="finish-work-list"]');
  const hadFinish = !!fin;
  if (fin) fin.click();
  return { hadFinish, cleared: !state.workList, closed: !document.querySelector('.crm-sheet') };
});
check('the last lead offers Finish, not a dead-ended Next', finish.hadFinish);
check('finishing the list closes it cleanly', finish.cleared && finish.closed);

console.log('\n— 13. REPORTS + HOME —');
const rep = await page.evaluate(() => {
  showSection('reports');
  renderReports();
  const names = Array.from(document.querySelectorAll('.report-user-card h3')).map(h => h.textContent.trim());
  const labels = Array.from(document.querySelectorAll('.report-user-card .report-user-stat span')).map(s => s.textContent.trim());
  return { names, labels: [...new Set(labels)] };
});
check('reports list the people who actually sell', rep.names.includes('Joshua Khalili') && !rep.names.includes('Melusi Ndoro'), rep.names.join(', '));
check('reports separate conversations from dials', rep.labels.includes('Conversations') && rep.labels.includes('Calls Logged'), rep.labels.join(' / '));

const home = await page.evaluate(() => {
  showSection('home');
  renderHome();
  const txt = document.getElementById('home-content').innerHTML;
  const labels = Array.from(document.querySelectorAll('.home-stat-card .stat-label')).map(s => s.textContent.trim());
  return { emdash: txt.includes('&mdash;') || txt.includes('—'), labels };
});
check('no em dash in the activity feed', !home.emdash);
check('the 48h tile says what it counts', home.labels.some(l => /worked \(48h\)/i.test(l)), home.labels.join(' / '));

console.log('\n— 14. MEETINGS —');
const meet = await page.evaluate(() => {
  const l = getLeadById('c1');
  l.status = 'crm';
  l.crm.meetingBooked = true;
  l.crm.meetingDate = new Date(Date.now() - 3 * 864e5).toISOString().slice(0, 16); // 3 days ago
  l.crm.stage = 3;
  saveState();
  showSection('meetings');
  renderMeetings();
  const txt = document.getElementById('meetings-content').textContent;
  const markBtn = document.querySelector('[data-action="mark-meeting-complete"][data-id="' + l.id + '"]');
  return { needsOutcome: /Needs an outcome/.test(txt), falselyCompleted: /Completed/.test(txt) && !markBtn, canStillMark: !!markBtn };
});
check('a meeting whose slot passed is not called completed', meet.needsOutcome);
check('it can still be marked done after the fact', meet.canStillMark);

const meetDone = await page.evaluate(() => {
  const l = getLeadById('c1');
  document.querySelector('[data-action="mark-meeting-complete"][data-id="' + l.id + '"]').click();
  return { stage: l.crm.stage, fu: l.crm.followUpDate };
});
check('marking it done advances the stage and books the follow-through', meetDone.stage === 4 && !!meetDone.fu, 'stage ' + meetDone.stage + ', follow up ' + meetDone.fu);

const booked = await page.evaluate(() => {
  const l = getLeadById('c2');
  l.status = 'crm'; l.crm.meetingBooked = false; l.crm.followUpDate = ''; l.crm.stage = 1; l.crm.meetingDate = '';
  showSection('crm'); state.crmView = 'list'; renderCRM();
  state.crmDetailsOpen[l.id] = true; renderCRM();
  const t = document.querySelector('[data-action="toggle-meeting"][data-id="' + l.id + '"]');
  if (t) t.click();
  return { booked: l.crm.meetingBooked, fu: l.crm.followUpDate, stage: l.crm.stage };
});
check('booking a meeting sets the follow-up and the stage', booked.booked && !!booked.fu && booked.stage === 3,
  'stage ' + booked.stage + ', follow up ' + booked.fu);

console.log('\n— 15. STALLED LEADS —');
const stall = await page.evaluate(() => {
  const l = getLeadById('c1');
  const old = new Date(Date.now() - 40 * 864e5);
  const day = d => d.toLocaleDateString('en-CA');
  l.status = 'crm'; l.crm.stage = 2; l.crm.meetingBooked = false;
  l.crm.stageEnteredAt = { '2': day(old) };
  l.crm.stageChangedAt = day(old);
  l.activity = [{ action: 'logged call (No answer)', by: 'Ameer Munj', date: old.toISOString() }];
  const fresh = getLeadById('c2');
  const isStale = isStalled(l), freshStale = isStalled(fresh);
  showSection('crm'); renderCRM();
  const chip = document.querySelector('[data-action="toggle-stalled"]');
  return { isStale, freshStale, chip: chip ? chip.textContent.replace(/\s+/g, ' ').trim() : '' };
});
check('a lead parked 40 days with no activity reads as stalled', stall.isStale && !stall.freshStale);
check('Outreach surfaces the stalled count', /stalled/.test(stall.chip), stall.chip);

console.log('\n— 16. NO EM DASHES IN WHAT REPS READ —');
const dashes = await page.evaluate(() => {
  const bad = [];
  ['home', 'lead-bank', 'qualified-leads', 'crm', 'meetings', 'archive', 'playbooks', 'reports'].forEach(s => {
    try { showSection(s); } catch (_) { return; }
    const el = document.getElementById('section-' + s);
    const t = el ? el.textContent : '';
    if (/[—–]/.test(t)) bad.push(s + ': ' + (t.match(/.{0,40}[—–].{0,40}/) || [''])[0]);
  });
  return bad;
});
check('no em or en dashes anywhere in the app copy', dashes.length === 0, dashes.slice(0, 2).join(' | '));

console.log('\n— 17. NO RUNTIME ERRORS —');
const realErrors = errors.filter(e => !/ERR_FAILED|net::|Failed to load resource|firebase|leaflet/i.test(e));
check('no page errors during the run', realErrors.length === 0, realErrors.slice(0, 3).join(' || '));
console.log(`  (${blocked} cloud requests blocked — nothing touched the live database)`);

const failed = results.filter(r => !r.pass);
console.log(`\n${results.length - failed.length}/${results.length} checks passed`);
await browser.close();
process.exit(failed.length ? 1 : 0);
