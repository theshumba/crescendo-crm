# Crescendo CRM — Consolidated Fix Spec

Single, ordered, conflict-free patch for `/Users/theshumba/Documents/GitHub/crescendo-crm/crescendo-crm.html`.

Six cluster specs (sync-data, identity, claiming, activity-master, ux-mobile, runtime-guards) have been merged. Where multiple clusters touched the same function, their edits are combined into **one** FIND/REPLACE showing the final form. Apply the steps **in the numbered order below** — later steps assume earlier ones (e.g. `normalizeLead`, `_echoKey`, `__leadHashes`, `canViewActivityMonitor`, `MASTER_PIN`/`RESERVED_MASTER_NAME` must exist before they are referenced).

All FIND strings were verified verbatim and unique against the current file (6170 lines).

---

## OPEN QUESTIONS / could-not-fully-de-conflict

1. **`CrescendoSync.__db` exposure for L1 seed transaction.** The sync-data L1 seed-gate references `CrescendoSync.__db`, but `db` is a private closure var. Resolved by **Step 4** adding `CrescendoSync.__db = db;` in `init()` after `ready = true;`. If that line is omitted, L1 safely falls back to the per-session gate (try/catch sets `__mayseed=true`), so the app still works but the cross-device double-seed guard won't engage. **Included as Step 4 — confirm acceptable.**

2. **`lastPushedSuppress` does not exist.** The claiming H7 edit called `lastPushedSuppress(local.id, r)`, which is undefined in the file. Resolved in **Step 16** by replacing that call with the equivalent inline `lastPushed.delete(local.id);` (drops the stale echo key so the overwritten claim isn't re-pushed). Confirm this substitution is acceptable.

3. **Reports vs Activity Monitor week-start.** activity-master claimed Reports (line 4810) is already Monday-start; verified TRUE (`getDay() + 1`). Activity Monitor (line 4659) is Sunday-start (`getDay()`). Step 22 changes only the Activity Monitor to Monday-start to match Reports. No conflict — flagged only because the cluster's description of the existing state was slightly imprecise.

4. **M4 (Master PIN) is NOT a real fix.** The PIN remains client-side and `localStorage['crescendo-crm-user']` is still directly settable. Step 9/10 only removes the trivial free-text "Master" bypass and de-duplicates the literal. A real fix needs Firebase Auth + Firestore Security Rules (out of single-file scope). Documented, not closed.

5. **L5 "Master" label → rep mapping** (activity-master flagged this as out-of-cluster) is intentionally NOT implemented. `resolveRepName` keeps `Master` as `Master`; only near-duplicate rep spellings are canonicalised.

---

## PART A — DATA-INTEGRITY (apply first)

### Step 1 — Firebase import: add `getDoc`, `runTransaction`
*Cluster: sync-data (M1/L1). Location: lines 14-15.*

**FIND**
```
  import { getFirestore, collection, doc, setDoc, deleteDoc, onSnapshot, serverTimestamp, writeBatch } from 'https://www.gstatic.com/firebasejs/10.12.2/firebase-firestore.js';
  window.__fb = { initializeApp, getAuth, signInAnonymously, onAuthStateChanged, getFirestore, collection, doc, setDoc, deleteDoc, onSnapshot, serverTimestamp, writeBatch };
```
**REPLACE**
```
  import { getFirestore, collection, doc, getDoc, setDoc, deleteDoc, onSnapshot, serverTimestamp, writeBatch, runTransaction } from 'https://www.gstatic.com/firebasejs/10.12.2/firebase-firestore.js';
  window.__fb = { initializeApp, getAuth, signInAnonymously, onAuthStateChanged, getFirestore, collection, doc, getDoc, setDoc, deleteDoc, onSnapshot, serverTimestamp, writeBatch, runTransaction };
```
**Resolves:** M1, L1.

---

### Step 2 — CrescendoSync closure vars: add `lastLeads` + `_echoKey` helper
*Clusters: sync-data (M1 echo-key) + claiming (H1 lastLeads). Location: lines 988-991.*

**FIND**
```
  let applyingRemote = false;       // guard so onSnapshot callbacks don't re-push writes
  let lastPushed = new Map();       // leadId -> JSON string of last-pushed lead
  let pushTimer = null;
  let pendingPush = false;
```
**REPLACE**
```
  let applyingRemote = false;       // guard so onSnapshot callbacks don't re-push writes
  let lastPushed = new Map();       // leadId -> JSON string of last-pushed lead (echo key)
  let pushTimer = null;
  let pendingPush = false;
  let lastLeads = null;            // latest leads array handed to pushLeads (for flush())
  // Echo-dedup key: the lead minus volatile server-side fields. _srvAt is a serverTimestamp
  // sentinel on write but a resolved Timestamp on read, so it must be stripped from the key
  // or every push would look "changed" and loop forever (M1 safety).
  function _echoKey(lead) { const o = { ...lead }; delete o._srvAt; return o; }
```
**Resolves:** M1 (shared echo key), H1 (lastLeads capture for flush()).

---

### Step 3 — subscribe onSnapshot: normalise `_srvAt`, use `_echoKey` for ledger
*Cluster: sync-data (M1). Location: lines 1042-1050.*

**FIND**
```
          let modAt = raw._modAt;
          if (modAt && typeof modAt.toDate === 'function') { try { modAt = modAt.toDate().toISOString(); } catch (_) { modAt = ''; } }
          const lead = { ...raw };
          lead._modAt = (typeof modAt === 'string') ? modAt : '';
          // Keep _modAt/_modBy ON the lead so the app-level merge can compare versions.
          remoteLeads.push(lead);
          // lastPushed ledger stores the exact serialization we'd re-push, so identical
          // remote echoes are skipped by pushLeads (prevents push/snapshot loops).
          lastPushed.set(lead.id, JSON.stringify({ ...lead }));
```
**REPLACE**
```
          let modAt = raw._modAt;
          if (modAt && typeof modAt.toDate === 'function') { try { modAt = modAt.toDate().toISOString(); } catch (_) { modAt = ''; } }
          const lead = { ...raw };
          lead._modAt = (typeof modAt === 'string') ? modAt : '';
          // Normalise the server timestamp (M1): _srvAt is written as serverTimestamp() and
          // comes back as a Firestore Timestamp — convert to ISO so the merge can order by it.
          let srvAt = raw._srvAt;
          if (srvAt && typeof srvAt.toDate === 'function') { try { srvAt = srvAt.toDate().toISOString(); } catch (_) { srvAt = ''; } }
          lead._srvAt = (typeof srvAt === 'string') ? srvAt : '';
          // Keep _modAt/_modBy/_srvAt ON the lead so the app-level merge can compare versions.
          remoteLeads.push(lead);
          // lastPushed ledger stores the serialization we'd re-push, so identical remote
          // echoes are skipped by pushLeads (prevents push/snapshot loops). _srvAt is volatile
          // (sentinel on write, Timestamp on read) so it MUST be excluded from the echo key.
          lastPushed.set(lead.id, JSON.stringify(_echoKey(lead)));
```
**Resolves:** M1.

---

### Step 4 — pushLeads: chunked batches + `_srvAt` + echo-key + tombstone deletes + `lastLeads` capture + L5 user normalisation
*Clusters: sync-data (H2/M1/H3) + claiming (H1 lastLeads) + identity (L5 user). MERGED. Location: lines 1066-1106.*

**FIND**
```
  // Push changed leads to Firestore. Debounced to coalesce rapid edits.
  function pushLeads(leads) {
    if (!ready || !db) return;
    if (applyingRemote) return; // don't echo remote writes back
    pendingPush = true;
    if (pushTimer) return;
    pushTimer = setTimeout(async () => {
      pushTimer = null;
      if (!pendingPush) return;
      pendingPush = false;
      try {
        const batch = window.__fb.writeBatch(db);
        const currentIds = new Set();
        const user = (typeof getCurrentUser === 'function') ? getCurrentUser() : 'Unknown';
        for (const lead of leads) {
          if (!lead || !lead.id) continue;
          currentIds.add(lead.id);
          // Never push the fictional demo/sample leads into the production cloud.
          if (lead.source === 'sample') continue;
          // Stamp _modAt as an ISO string (app-level, survives the round-trip for merge ordering).
          // Prefer the lead's own _modAt (set by saveState at write time); fall back to now.
          const stampedAt = (typeof lead._modAt === 'string' && lead._modAt) ? lead._modAt : new Date().toISOString();
          const stampedBy = lead._modBy || user;
          const payload = { ...lead, _modBy: stampedBy, _modAt: stampedAt };
          const serialized = JSON.stringify(payload);
          if (lastPushed.get(lead.id) === serialized) continue; // unchanged — skip echo
          const ref = window.__fb.doc(db, 'leads', String(lead.id));
          batch.set(ref, payload);
          lastPushed.set(lead.id, serialized);
        }
        // Deletions are SCOPED to ids the app explicitly deleted — never inferred from a
        // partial/stale local list. This prevents mass-deletion of the cloud leads.
        for (const id of Array.from(pendingDeletes)) {
          if (!currentIds.has(id)) {
            const ref = window.__fb.doc(db, 'leads', String(id));
            batch.delete(ref);
            lastPushed.delete(id);
          }
          pendingDeletes.delete(id);
        }
        await batch.commit();
        showSyncStatus('connected');
      } catch (e) {
        console.warn('[CrescendoSync] Push failed:', e);
        showSyncStatus('error', e.message || 'Push failed');
      }
    }, 400);
  }
```
**REPLACE**
```
  // Push changed leads to Firestore. Debounced to coalesce rapid edits.
  function pushLeads(leads) {
    if (!ready || !db) return;
    if (applyingRemote) return; // don't echo remote writes back
    lastLeads = leads; // remember the latest list so flush() can commit it synchronously (H1)
    pendingPush = true;
    if (pushTimer) return;
    pushTimer = setTimeout(async () => {
      pushTimer = null;
      if (!pendingPush) return;
      pendingPush = false;
      try {
        const currentIds = new Set();
        const __rawUser = (typeof getCurrentUser === 'function') ? getCurrentUser() : 'Unknown';
        // L5: canonicalise the writer so attribution can't split across name variants.
        const user = (typeof resolveRepName === 'function') ? resolveRepName(__rawUser) : __rawUser;
        // Collect write operations first, then commit in <=450-op chunks. A writeBatch caps
        // at 500 ops; with ~540 leads a single batch throws "too large" and the whole push
        // (including the real claim) fails. Chunking is the hard-break safety net (H2).
        const ops = [];
        for (const lead of leads) {
          if (!lead || !lead.id) continue;
          currentIds.add(lead.id);
          // Never push the fictional demo/sample leads into the production cloud.
          if (lead.source === 'sample') continue;
          // Never push soft-deleted leads as live data (H3).
          if (lead._deleted) continue;
          // Stamp _modAt as an ISO string (app-level, survives the round-trip for merge ordering).
          // Prefer the lead's own _modAt (set by saveState at write time); fall back to now.
          const stampedAt = (typeof lead._modAt === 'string' && lead._modAt) ? lead._modAt : new Date().toISOString();
          const stampedBy = lead._modBy || user;
          // _srvAt: authoritative server clock written every push; merge prefers it over the
          // device wall-clock _modAt when both sides have it (M1). Volatile — see _echoKey.
          const payload = { ...lead, _modBy: stampedBy, _modAt: stampedAt, _srvAt: window.__fb.serverTimestamp() };
          const echo = JSON.stringify(_echoKey(payload));
          if (lastPushed.get(lead.id) === echo) continue; // unchanged — skip echo (H2)
          const ref = window.__fb.doc(db, 'leads', String(lead.id));
          ops.push({ ref: ref, payload: payload });
          lastPushed.set(lead.id, echo);
        }
        // Deletions are SCOPED to ids the app explicitly deleted — never inferred from a
        // partial/stale local list. Soft-delete TOMBSTONE (H3): write {_deleted:true,...} via
        // set instead of a hard delete, so every other rep's merge can DROP the lead rather
        // than resurrect it (a pure-union merge can't see a missing doc).
        for (const id of Array.from(pendingDeletes)) {
          if (!currentIds.has(id)) {
            const ref = window.__fb.doc(db, 'leads', String(id));
            const tomb = { id: String(id), _deleted: true, _modAt: new Date().toISOString(), _modBy: user, _srvAt: window.__fb.serverTimestamp() };
            ops.push({ ref: ref, payload: tomb });
            lastPushed.delete(id);
          }
          pendingDeletes.delete(id);
        }
        // Commit in chunks of <=450 ops (safely under the 500-op writeBatch ceiling).
        const CHUNK = 450;
        for (let i = 0; i < ops.length; i += CHUNK) {
          const batch = window.__fb.writeBatch(db);
          for (const op of ops.slice(i, i + CHUNK)) batch.set(op.ref, op.payload);
          await batch.commit();
        }
        showSyncStatus('connected');
      } catch (e) {
        console.warn('[CrescendoSync] Push failed:', e);
        showSyncStatus('error', e.message || 'Push failed');
      }
    }, 400);
  }
```
**Resolves:** H2 (chunk + echo-only writes), H3 (tombstone deletes), M1 (`_srvAt`), H1 (`lastLeads`), L5 (canonical writer).

---

### Step 5 — add `flush()` (synchronous claim commit before tel:)
*Cluster: claiming (H1). Built on the chunked pushLeads. Location: immediately before `function showSyncStatus(` (line 1114).*

**FIND**
```
  function showSyncStatus(kind, msg) {
    let el = document.getElementById('sync-status-indicator');
```
**REPLACE**
```
  // Commit any pending push RIGHT NOW (synchronously kicks off batch.commit), bypassing the
  // 400ms debounce. Used before tel: navigation so a claim write isn't dropped when the phone
  // suspends the page. Returns a Promise; never rejects (errors surface via showSyncStatus).
  function flush() {
    if (!ready || !db) return Promise.resolve();
    if (applyingRemote) return Promise.resolve();
    if (pushTimer) { clearTimeout(pushTimer); pushTimer = null; }
    if (!pendingPush) return Promise.resolve();
    pendingPush = false;
    const leads = Array.isArray(lastLeads) ? lastLeads : [];
    return (async () => {
      try {
        const currentIds = new Set();
        const __rawUser = (typeof getCurrentUser === 'function') ? getCurrentUser() : 'Unknown';
        const user = (typeof resolveRepName === 'function') ? resolveRepName(__rawUser) : __rawUser;
        const ops = [];
        for (const lead of leads) {
          if (!lead || !lead.id) continue;
          currentIds.add(lead.id);
          if (lead.source === 'sample') continue;
          if (lead._deleted) continue;
          const stampedAt = (typeof lead._modAt === 'string' && lead._modAt) ? lead._modAt : new Date().toISOString();
          const stampedBy = lead._modBy || user;
          const payload = { ...lead, _modBy: stampedBy, _modAt: stampedAt, _srvAt: window.__fb.serverTimestamp() };
          const echo = JSON.stringify(_echoKey(payload));
          if (lastPushed.get(lead.id) === echo) continue;
          const ref = window.__fb.doc(db, 'leads', String(lead.id));
          ops.push({ ref: ref, payload: payload });
          lastPushed.set(lead.id, echo);
        }
        for (const id of Array.from(pendingDeletes)) {
          if (!currentIds.has(id)) {
            const ref = window.__fb.doc(db, 'leads', String(id));
            const tomb = { id: String(id), _deleted: true, _modAt: new Date().toISOString(), _modBy: user, _srvAt: window.__fb.serverTimestamp() };
            ops.push({ ref: ref, payload: tomb });
            lastPushed.delete(id);
          }
          pendingDeletes.delete(id);
        }
        const CHUNK = 450;
        for (let i = 0; i < ops.length; i += CHUNK) {
          const batch = window.__fb.writeBatch(db);
          for (const op of ops.slice(i, i + CHUNK)) batch.set(op.ref, op.payload);
          await batch.commit();
        }
        showSyncStatus('connected');
      } catch (e) {
        console.warn('[CrescendoSync] Flush failed:', e);
        showSyncStatus('error', e.message || 'Flush failed');
      }
    })();
  }

  function showSyncStatus(kind, msg) {
    let el = document.getElementById('sync-status-indicator');
```
**Resolves:** H1. *(Note: flush() mirrors the chunked/tombstone/_srvAt body of Step 4 so it stays consistent.)*

---

### Step 6 — sync indicator styling (mobile-safe, token colours)
*Cluster: ux-mobile (M7/M8). Location: lines 1119, 1127-1138.*

**FIND**
```
      el.style.cssText = 'position:fixed;bottom:12px;right:12px;padding:6px 10px;border-radius:6px;font:500 12px system-ui,sans-serif;z-index:9999;pointer-events:auto;opacity:0.9;cursor:default;';
      document.body && document.body.appendChild(el);
    }
    if (!el.parentNode && document.body) document.body.appendChild(el);
    const who = (typeof getCurrentUser === 'function' && getCurrentUser() !== 'Unknown') ? getCurrentUser() : '';
    if (kind === 'connected') {
      el.textContent = who ? ('● Synced as ' + who) : '● Synced';
      el.title = 'Live: your work is shared with the team in real time.';
      el.style.background = '#e6f7ec';
      el.style.color = '#1a7a3a';
    } else if (kind === 'error') {
      el.textContent = '● Sync error' + (msg ? ': ' + msg : '');
      el.title = 'Could not reach the shared backend. Changes are saved locally and will retry.';
      el.style.background = '#fdecea';
      el.style.color = '#a12622';
    } else {
      el.textContent = '● Offline (local only)';
      el.title = 'Not connected to the shared backend — this device only.';
      el.style.background = '#f1f2f4';
      el.style.color = '#555';
    }
```
**REPLACE**
```
      el.style.cssText = 'position:fixed;right:var(--space-3);bottom:calc(var(--space-6) + 66px);padding:6px 10px;border-radius:6px;font:500 12px system-ui,sans-serif;z-index:401;pointer-events:none;opacity:0.92;cursor:default;';
      document.body && document.body.appendChild(el);
    }
    if (!el.parentNode && document.body) document.body.appendChild(el);
    const who = (typeof getCurrentUser === 'function' && getCurrentUser() !== 'Unknown') ? getCurrentUser() : '';
    if (kind === 'connected') {
      el.textContent = who ? ('● Synced as ' + who) : '● Synced';
      el.title = 'Live: your work is shared with the team in real time.';
      el.style.background = 'var(--color-success-highlight)';
      el.style.color = 'var(--color-success)';
    } else if (kind === 'error') {
      el.textContent = '● Sync error' + (msg ? ': ' + msg : '');
      el.title = 'Could not reach the shared backend. Changes are saved locally and will retry.';
      el.style.background = 'var(--color-error-highlight)';
      el.style.color = 'var(--color-error)';
    } else {
      el.textContent = '● Offline (local only)';
      el.title = 'Not connected to the shared backend — this device only.';
      el.style.background = 'var(--color-surface-offset)';
      el.style.color = 'var(--color-text-muted)';
    }
```
**Resolves:** M7, M8.

---

### Step 7 — export `flush` from CrescendoSync + add `__db` exposure
*Clusters: claiming (H1 export) + sync-data (L1 __db note). Location: line 1144.*

**FIND**
```
  return { init, subscribe, pushLeads, isConfigured, showSyncStatus, queueDelete };
```
**REPLACE**
```
  return { init, subscribe, pushLeads, flush, isConfigured, showSyncStatus, queueDelete };
```
**Resolves:** H1 (export flush).

---

### Step 8 — `init()`: expose `db` for the L1 seed transaction
*Cluster: sync-data (L1 dependency). Location: line 1019.*

**FIND**
```
      await window.__fb.signInAnonymously(auth);
      ready = true;
```
**REPLACE**
```
      await window.__fb.signInAnonymously(auth);
      ready = true;
      CrescendoSync.__db = db; // expose for the L1 create-if-absent seed transaction
```
**Resolves:** L1 (cross-device seed guard `__db` reference). If omitted, L1 falls back safely.

---

## PART B — IDENTITY

### Step 9 — `isMasterUser` block: add `canViewActivityMonitor` + `RESERVED_MASTER_NAME`
*Clusters: identity (M5/C4) + activity-master (M5 — same helper, defined ONCE here). Location: lines 1184-1187.*

**FIND**
```
function isMasterUser() {
  return getCurrentUser() === 'Master';
}
const CONSULTANTS = ['Muneeb Moiz', 'Yousuf Zacky', 'Ameer Munj'];
const CEOS = ['Melusi Ndoro', 'Joshua Khalili', 'Ayoub Rasol'];
```
**REPLACE**
```
function isMasterUser() {
  return getCurrentUser() === 'Master';
}
const CONSULTANTS = ['Muneeb Moiz', 'Yousuf Zacky', 'Ameer Munj'];
const CEOS = ['Melusi Ndoro', 'Joshua Khalili', 'Ayoub Rasol'];
// True for the owner (Master) AND CEO roster logins, who share aggregate access.
// Centralised so nav, redirect, and render gates can't drift apart (M5).
function canViewActivityMonitor() {
  return isMasterUser() || CEOS.includes(getCurrentUser());
}
// Reserved identity that may ONLY be assumed via the Master PIN gate. Free-typed
// 'Master' (any case/spacing) must never resolve to the owner identity (C4).
const RESERVED_MASTER_NAME = 'master';
```
**Resolves:** M5 (single shared helper for both identity + activity-master clusters), C4 (reserved-name constant).

*(Note: function declarations hoist; `canViewActivityMonitor` references `CEOS`/`isMasterUser` at call time, both in scope.)*

---

### Step 10 — `resolveRepName`: remove "Master" bypass, roster-first precedence
*Cluster: identity (C4/M6). Location: lines 1214-1220.*

**FIND**
```
function resolveRepName(name) {
  const clean = String(name || '').replace(/\s+/g, ' ').trim();
  if (!clean) return clean;
  if (clean === 'Master') return 'Master';
  const match = getKnownReps().find(n => n.toLowerCase() === clean.toLowerCase());
  return match || clean;
}
```
**REPLACE**
```
function resolveRepName(name) {
  const clean = String(name || '').replace(/\s+/g, ' ').trim();
  if (!clean) return clean;
  // SECURITY: 'Master' (any case) is NOT resolvable here — the owner identity may only be
  // assumed through the PIN gate. Free-typed 'master' is treated as an ordinary (invalid)
  // rep name so it can never grant owner powers (C4).
  if (clean.toLowerCase() === RESERVED_MASTER_NAME) return clean;
  // Precedence: canonical roster (CEOS then CONSULTANTS) ALWAYS wins over custom reps so a
  // near-duplicate custom rep can never shadow/mis-canonicalise a CEO or consultant (M6).
  const lc = clean.toLowerCase();
  const canonical = [...CEOS, ...CONSULTANTS].find(n => n.toLowerCase() === lc);
  if (canonical) return canonical;
  const custom = getCustomReps().find(n => n.toLowerCase() === lc);
  return custom || clean;
}
```
**Resolves:** C4, M6.

---

### Step 11 — `updateMasterUI`: route nav + redirect through `canViewActivityMonitor`
*Clusters: identity + activity-master (M5 — same target). Location: lines 1241-1246.*

**FIND**
```
  const navBtn = document.getElementById('nav-activity-monitor');
  if (navBtn) navBtn.style.display = isMasterUser() ? '' : 'none';
  // If non-master is on activity-monitor, redirect to home
  if (!isMasterUser() && state.activeSection === 'activity-monitor') {
    showSection('home');
  }
```
**REPLACE**
```
  const navBtn = document.getElementById('nav-activity-monitor');
  // CEO/owner logins share aggregate access, so they also get the Activity Monitor (M5).
  if (navBtn) navBtn.style.display = canViewActivityMonitor() ? '' : 'none';
  // If a user without aggregate access is on activity-monitor, redirect to home
  if (!canViewActivityMonitor() && state.activeSection === 'activity-monitor') {
    showSection('home');
  }
```
**Resolves:** M5.

---

### Step 12 — `addActivity`: normalise attribution at write time
*Cluster: identity (L5). Location: lines 1253-1256.*

**FIND**
```
function addActivity(lead, action) {
  if (!lead.activity) lead.activity = [];
  lead.activity.unshift({ action, by: getCurrentUser(), date: new Date().toISOString() });
}
```
**REPLACE**
```
function addActivity(lead, action) {
  if (!lead.activity) lead.activity = [];
  // Normalise attribution to the canonical roster spelling at write time so one human never
  // splits across near-duplicate spellings in the Activity Monitor (L5).
  const by = resolveRepName(getCurrentUser());
  lead.activity.unshift({ action, by, date: new Date().toISOString() });
}
```
**Resolves:** L5.

---

### Step 13 — login handler: named `MASTER_PIN` constant + documented residual risk
*Cluster: identity (M4). Location: line 4509.*

**FIND**
```
document.getElementById('login-btn').addEventListener('click', () => {
  const select = document.getElementById('login-team-select');
  let name;
```
**REPLACE**
```
// NOTE (M4 — residual risk, NOT fully fixed client-side): this PIN is still shipped in
// client JS, so a determined rep can view-source it or set the 'crescendo-crm-user'
// localStorage key directly to assume Master. A real fix requires a Firebase auth identity +
// Firestore Security Rules keyed to that uid. Until then this only stops the *trivial*
// free-text 'Master' bypass (C4) and avoids re-printing the literal in multiple places.
const MASTER_PIN = '786777';
document.getElementById('login-btn').addEventListener('click', () => {
  const select = document.getElementById('login-team-select');
  let name;
```
**Resolves:** M4 (named constant + documented residual risk).

---

### Step 14 — login handler: use `MASTER_PIN`, reject reserved name in add-rep path
*Cluster: identity (C4/M4). Location: lines 4512-4524.*

**FIND**
```
  if (select.value === '__master__') {
    const pin = document.getElementById('login-pin-input').value;
    if (pin !== '786777') {
      document.getElementById('login-pin-error').style.display = 'block';
      return;
    }
    name = 'Master';
  } else if (select.value === '__other__') {
    // Canonicalize: collapse onto an existing rep if the typed name already exists.
    name = resolveRepName(document.getElementById('login-custom-input').value);
    if (!name) return;
    // Remember genuinely-new reps so they appear in the picker next time.
    addCustomRep(name);
  } else {
```
**REPLACE**
```
  if (select.value === '__master__') {
    const pin = document.getElementById('login-pin-input').value;
    if (pin !== MASTER_PIN) {
      document.getElementById('login-pin-error').style.display = 'block';
      return;
    }
    name = 'Master';
  } else if (select.value === '__other__') {
    // Canonicalize: collapse onto an existing rep if the typed name already exists.
    name = resolveRepName(document.getElementById('login-custom-input').value);
    if (!name) return;
    // SECURITY: the add-rep path must NEVER mint the owner identity. Reject any name that
    // case-insensitively equals the reserved 'Master' sentinel — Master can only be assumed
    // via the PIN branch above (C4).
    if (name.toLowerCase() === RESERVED_MASTER_NAME) {
      const err = document.getElementById('login-pin-error');
      if (err) { err.textContent = 'That name is reserved. Use the Master Account option to sign in as owner.'; err.style.display = 'block'; }
      return;
    }
    // Remember genuinely-new reps so they appear in the picker next time.
    addCustomRep(name);
  } else {
```
**Resolves:** C4, M4.

---

## PART C — DATA NORMALIZATION + SEED/LOAD/MERGE

### Step 15 — `normalizeLead()` helper + wire into seed IIFE
*Cluster: runtime-guards (C3/C5/H5). Introduced ONCE; referenced by Steps 17, 18, 21. Location: lines 1584-1592.*

**FIND**
```
// Normalise lead shape so newly-added fields exist on legacy records
(function normaliseLeads() {
  state.leads.forEach(l => {
    if (l.crm) {
      if (l.crm.dealValue == null) l.crm.dealValue = 15000;
      if (l.crm.outcomeReason == null) l.crm.outcomeReason = '';
    }
  });
})();
```
**REPLACE**
```
// normalizeLead — single source of truth for lead shape. Imported/remote leads of unknown
// shape are coerced here so every renderer/search/filter can assume fields and arrays exist.
// Mutates and returns the lead. Idempotent — safe to call repeatedly (seed, loadState, merge).
function normalizeLead(l) {
  if (!l || typeof l !== 'object') return l;
  if (typeof l.businessName !== 'string') l.businessName = l.businessName == null ? '' : String(l.businessName);
  if (typeof l.description !== 'string') l.description = l.description == null ? '' : String(l.description);
  if (typeof l.industry !== 'string') l.industry = l.industry == null ? '' : String(l.industry);
  if (!Array.isArray(l.phones)) l.phones = [];
  if (!Array.isArray(l.emails)) l.emails = [];
  if (!Array.isArray(l.contacts)) l.contacts = [];
  if (!Array.isArray(l.activity)) l.activity = [];
  if (!Array.isArray(l.researchChecklist)) l.researchChecklist = [];
  if (!l.source) l.source = 'manual';
  if (!l.status) l.status = 'unqualified';
  if (l.qualification === undefined) l.qualification = null;
  if (l.crm === undefined) l.crm = null;
  if (l.crm && typeof l.crm === 'object') {
    if (!Array.isArray(l.crm.notes)) l.crm.notes = [];
    if (!l.crm.priority) l.crm.priority = 'medium';
    if (l.crm.disposition == null) l.crm.disposition = 'nurture';
    if (l.crm.dealValue == null) l.crm.dealValue = 15000;
    if (l.crm.outcomeReason == null) l.crm.outcomeReason = '';
    if (typeof l.crm.stage !== 'number') l.crm.stage = Number(l.crm.stage) || 1;
  }
  return l;
}
(function normaliseLeads() {
  if (Array.isArray(state.leads)) state.leads.forEach(l => normalizeLead(l));
})();
```
**Resolves:** C3, C5, H5.

---

### Step 16 — `saveState`: content-hash dirty-tracking (H2) + canonical `_modBy` (L5)
*Clusters: sync-data (H2) + identity (L5). MERGED. Location: lines 1810-1825.*

**FIND**
```
function saveState() {
  // Stamp a sync timestamp on every lead at the single write chokepoint, so the
  // per-lead merge engine can always tell which side (local vs remote) is newer.
  // __applyingRemote guard: don't re-stamp leads we're currently applying FROM remote.
  try {
    if (!(window.CrescendoSync && CrescendoSync.__applyingRemote)) {
      const __now = new Date().toISOString();
      const __by = (typeof getCurrentUser === 'function') ? getCurrentUser() : 'Unknown';
      if (Array.isArray(state.leads)) {
        for (const __l of state.leads) {
          if (__l && __l.id && !__l.__remoteStamped) { __l._modAt = __now; __l._modBy = __by; }
          if (__l) delete __l.__remoteStamped;
        }
      }
    }
  } catch (_) { /* stamping is best-effort */ }
```
**REPLACE**
```
// Content hash of a lead EXCLUDING sync-bookkeeping fields, so we can tell which leads a given
// saveState actually mutated. Re-stamping/pushing all ~540 leads every call blew the 500-op
// batch limit and amplified writes ~540x (H2). We now stamp only the changed ones.
const __leadHashes = new Map(); // id -> last-seen content hash (set on save & on remote merge)
function __leadContentHash(l) {
  const o = { ...l };
  delete o._modAt; delete o._modBy; delete o._srvAt; delete o.__remoteStamped;
  return JSON.stringify(o);
}
function saveState() {
  // Stamp the sync timestamp ONLY on leads whose content actually changed since the last
  // save/merge, so the per-lead merge can tell which side is newer WITHOUT rewriting every
  // lead. __applyingRemote guard: don't re-stamp leads we're currently applying FROM remote.
  try {
    if (!(window.CrescendoSync && CrescendoSync.__applyingRemote)) {
      const __now = new Date().toISOString();
      // L5: canonicalise the writer so _modBy attribution can't split across name variants.
      const __rawBy = (typeof getCurrentUser === 'function') ? getCurrentUser() : 'Unknown';
      const __by = (typeof resolveRepName === 'function') ? resolveRepName(__rawBy) : __rawBy;
      if (Array.isArray(state.leads)) {
        for (const __l of state.leads) {
          if (!__l || !__l.id) continue;
          if (__l.__remoteStamped) { delete __l.__remoteStamped; __leadHashes.set(__l.id, __leadContentHash(__l)); continue; }
          const __h = __leadContentHash(__l);
          if (__leadHashes.get(__l.id) !== __h) {
            // Genuinely changed (or brand new) → stamp it as a local edit and remember the hash.
            __l._modAt = __now; __l._modBy = __by;
            __leadHashes.set(__l.id, __leadContentHash(__l));
          }
          // else: untouched — leave existing _modAt/_modBy so pushLeads skips it.
        }
      }
    }
  } catch (_) { /* stamping is best-effort */ }
```
**Resolves:** H2 (only changed leads re-stamped), L5 (canonical `_modBy`).

---

### Step 17 — `loadState`: outage-edit `_modAt` backfill (C1) + normalizeLead (C5/H5)
*Clusters: sync-data (C1) + runtime-guards (C5/H5). MERGED. Location: lines 1851-1862.*

**FIND**
```
function loadState() {
  try {
    const saved = localStorage.getItem('crescendo-leads');
    if (saved !== null && saved !== undefined && saved !== '') {
      const parsed = JSON.parse(saved);
      if (Array.isArray(parsed)) {
        state.leads = parsed;
        return true;
      }
    }
  } catch (e) { console.warn('Failed to load state:', e); }
  return false;
}
```
**REPLACE**
```
function loadState() {
  try {
    const saved = localStorage.getItem('crescendo-leads');
    if (saved !== null && saved !== undefined && saved !== '') {
      const parsed = JSON.parse(saved);
      if (Array.isArray(parsed)) {
        // Normalise shape first (C5/H5) so backfill + merge see well-formed leads.
        state.leads = parsed.map(l => normalizeLead(l));
        // OUTAGE-EDIT PROTECTION (C1): edits made while sync was down carry no _modAt. The
        // merge treats empty _modAt as "oldest", so stale cloud copies would overwrite them on
        // first reconnect. Backfill a current-ISO _modAt on every lead missing one and persist
        // it BEFORE startSharedSync subscribes, so offline work wins the merge.
        let __backfilled = false;
        const __now = new Date().toISOString();
        const __by = (typeof getCurrentUser === 'function') ? getCurrentUser() : 'Unknown';
        for (const __l of state.leads) {
          if (__l && __l.id && !(typeof __l._modAt === 'string' && __l._modAt)) {
            __l._modAt = __now;
            if (!__l._modBy) __l._modBy = __by;
            __backfilled = true;
          }
        }
        if (__backfilled) {
          try { localStorage.setItem('crescendo-leads', JSON.stringify(state.leads)); } catch (_) {}
        }
        return true;
      }
    }
  } catch (e) { console.warn('Failed to load state:', e); }
  return false;
}
```
**Resolves:** C1, C5, H5.

---

## PART D — CLAIMING + DIALER

### Step 18 — `openDialer`: recent-contact cooldown (L2) + flush before tel: (H1) + multi-phone chooser (M10) + String coercion (M11)
*Clusters: claiming (H1/L2) + ux-mobile (M10) + runtime-guards (M11). MERGED. Location: lines 1303-1320.*

**FIND**
```
// Open the dialer for a lead, claiming it first and warning if someone else is live on it.
function openDialer(id) {
  const lead = getLeadById(id);
  if (!lead) return;
  const other = claimedByOther(lead);
  if (other) {
    if (!confirm(other + ' is already calling this lead. Open anyway?')) return;
  }
  claimLead(lead);
  const phone = (lead.phones && lead.phones[0] && lead.phones[0].number) ||
                (lead.contacts && lead.contacts.find(c => c.phone) || {}).phone || '';
  if (phone) {
    window.location.href = 'tel:' + phone.replace(/[^+0-9]/g, '');
  } else {
    showToast('No phone number on this lead', 'warning');
  }
  if (typeof renderAll === 'function') renderAll();
}
```
**REPLACE**
```
// Soft cooldown: warn if a DIFFERENT rep contacted this lead very recently, to avoid
// re-dialing seconds after a 'no answer'. Non-blocking (confirm to proceed).
const RECENT_CONTACT_COOLDOWN_MS = 4 * 60 * 1000;
function recentlyContactedByOther(lead) {
  const me = getCurrentUser();
  let when = 0, who = '';
  // Newest activity by someone else (activity[0] is the most recent — see renderLastActivity).
  const acts = (lead && Array.isArray(lead.activity)) ? lead.activity : [];
  for (const a of acts) {
    if (!a || a.by === me || !a.date) continue;
    const t = new Date(a.date).getTime();
    if (!isNaN(t) && t > when) { when = t; who = a.by; }
    break; // list is newest-first; the first other-user entry is the most recent
  }
  if (who && (Date.now() - when) < RECENT_CONTACT_COOLDOWN_MS) {
    return { who: who, minsAgo: Math.max(1, Math.round((Date.now() - when) / 60000)) };
  }
  return null;
}
// Open the dialer for a lead, claiming it first and warning if someone else is live on it.
// `num` (optional) is the specific tapped number; otherwise we choose / prompt.
function openDialer(id, num) {
  const lead = getLeadById(id);
  if (!lead) return;
  const other = claimedByOther(lead);
  if (other) {
    if (!confirm(other + ' is already calling this lead. Open anyway?')) return;
  } else {
    // No live claim, but guard against re-dialing right after another rep just tried.
    const recent = recentlyContactedByOther(lead);
    if (recent && !confirm('Recently contacted by ' + recent.who + ' (' + recent.minsAgo + ' min ago). Call anyway?')) return;
  }
  claimLead(lead);
  // Commit the claim NOW — tel: navigation suspends the page and would drop the debounced push (H1).
  try { CrescendoSync.flush(); } catch (_) { /* best-effort; still dial below */ }
  // Build the candidate number list (lead phones first, then a contact phone).
  const nums = []
    .concat((lead.phones || []).map(p => (p && p.number) || '').filter(Boolean))
    .concat((lead.contacts || []).map(c => (c && c.phone) || '').filter(Boolean));
  let phone = num || '';
  if (!phone) {
    if (nums.length > 1) {
      // Multiple numbers: let the rep choose which one to dial (M10).
      const choice = prompt('This lead has ' + nums.length + ' numbers. Type the line to call:\n' +
        nums.map((n, i) => (i + 1) + '. ' + n).join('\n'), '1');
      if (choice === null) { if (typeof renderAll === 'function') renderAll(); return; }
      const idx = parseInt(choice, 10) - 1;
      phone = (idx >= 0 && idx < nums.length) ? nums[idx] : nums[0];
    } else {
      phone = nums[0] || '';
    }
  }
  if (phone) {
    window.location.href = 'tel:' + String(phone).replace(/[^+0-9]/g, '');
  } else {
    showToast('No phone number on this lead', 'warning');
  }
  if (typeof renderAll === 'function') renderAll();
}
```
**Resolves:** H1, L2, M10, M11.

---

### Step 19 — Lead Bank click handler: pass tapped number
*Cluster: ux-mobile (M10). Location: line 3869.*

**FIND**
```
  else if (action === 'call-lead') openDialer(id);
  else if (action === 'view-lead') openPanel('view-lead', getLeadById(id));
```
**REPLACE**
```
  else if (action === 'call-lead') openDialer(id, target.dataset.num);
  else if (action === 'view-lead') openPanel('view-lead', getLeadById(id));
```
**Resolves:** M10.

---

### Step 20 — Qualified Leads click handler: pass tapped number
*Cluster: ux-mobile (M10). Location: line 3934.*

**FIND**
```
  if (action === 'qualify') openModal('qualify', getLeadById(id));
  else if (action === 'call-lead') openDialer(id);
  else if (action === 'move-to-crm') {
```
**REPLACE**
```
  if (action === 'qualify') openModal('qualify', getLeadById(id));
  else if (action === 'call-lead') openDialer(id, target.dataset.num);
  else if (action === 'move-to-crm') {
```
**Resolves:** M10.

---

### Step 21 — CRM click handler: pass tapped number
*Cluster: ux-mobile (M10). Location: line 3951.*

**FIND**
```
  if (action === 'call-lead') { openDialer(id); return; }
  if (action === 'generate-email') {
```
**REPLACE**
```
  if (action === 'call-lead') { openDialer(id, target.dataset.num); return; }
  if (action === 'generate-email') {
```
**Resolves:** M10.

---

### Step 22 — Side-panel click handler: pass tapped number
*Cluster: ux-mobile (M10). Location: line 4344.*

**FIND**
```
  if (action === 'close-panel') closePanel();
  else if (action === 'call-lead') openDialer(target.dataset.id);
```
**REPLACE**
```
  if (action === 'close-panel') closePanel();
  else if (action === 'call-lead') openDialer(target.dataset.id, target.dataset.num);
```
**Resolves:** M10.

---

## PART E — ACTIVITY MASTER

### Step 23 — `AM_ACTION_TYPES`: add won / reassigned / started filters
*Cluster: activity-master (L3). Location: lines 4553-4559.*

**FIND**
```
  { value: 'note', label: 'Note Added' },
  { value: 'disposition', label: 'Disposition' },
  { value: 'meeting', label: 'Meeting' },
  { value: 'stage', label: 'Stage Changed' },
  { value: 'archived', label: 'Archived' },
  { value: 'reactivated', label: 'Reactivated' }
];
```
**REPLACE**
```
  { value: 'note', label: 'Note Added' },
  { value: 'disposition', label: 'Disposition' },
  { value: 'meeting', label: 'Meeting' },
  { value: 'won', label: 'Won' },
  { value: 'reassigned', label: 'Reassigned' },
  { value: 'started', label: 'Started Working' },
  { value: 'stage', label: 'Stage Changed' },
  { value: 'archived', label: 'Archived' },
  { value: 'reactivated', label: 'Reactivated' }
];
```
**Resolves:** L3.

---

### Step 24 — `getAllActivities`: guard action, synthesize historical timeline, dedupe
*Cluster: activity-master (M12 + historical enhancement). Location: lines 4561-4571.*

**FIND**
```
function getAllActivities() {
  const activities = [];
  state.leads.forEach(lead => {
    if (!lead.activity) return;
    lead.activity.forEach(a => {
      activities.push({ ...a, leadName: lead.businessName, leadId: lead.id, leadStatus: lead.status });
    });
  });
  activities.sort((a, b) => new Date(b.date) - new Date(a.date));
  return activities;
}
```
**REPLACE**
```
// Family key used to dedupe synthesized historical entries against real logged activity[]
// entries (same user + same kind of action + same calendar day).
function activityFamily(action) {
  const t = String(action || '').toLowerCase();
  if (t.includes('logged call') || t.includes('logged a call') || t.startsWith('called')) return 'call';
  if (t.includes('meeting')) return 'meeting';
  if (t.includes('disposition')) return 'disposition';
  if (t.includes('won')) return 'won';
  if (t.includes('reassigned')) return 'reassigned';
  if (t.includes('started working')) return 'started';
  if (t.includes('qualified')) return 'qualified';
  if (t.includes('moved to crm') || t.includes('crm')) return 'crm';
  if (t.includes('note')) return 'note';
  if (t.includes('stage')) return 'stage';
  if (t.includes('archived') || t.includes('archive')) return 'archived';
  if (t.includes('reactivated') || t.includes('reactivate')) return 'reactivated';
  return t;
}
function dayKey(isoDate) {
  const d = new Date(isoDate);
  return isNaN(d) ? String(isoDate || '') : d.toISOString().slice(0, 10);
}
// READ-ONLY: derive timeline entries from historical crm.* fields + status so the master sees
// past rep work that predates per-action activity[] logging. Never written back; tagged
// synthetic:true and "(historical)".
function getSynthesizedActivities(realKeys) {
  const out = [];
  state.leads.forEach(lead => {
    const crm = lead.crm || {};
    const owner = lead.assignedTo || lead.claimedBy || lead.movedToCRMBy || lead.qualifiedBy || 'Unknown';
    const base = { leadName: lead.businessName, leadId: lead.id, leadStatus: lead.status, synthetic: true };
    const candidates = [];
    if (crm.dateFirstContact) candidates.push({ by: owner, action: 'first contact (historical)', date: crm.dateFirstContact, _fam: 'call' });
    if (crm.dateLastContact && crm.dateLastContact !== crm.dateFirstContact) candidates.push({ by: owner, action: 'last contact (historical)', date: crm.dateLastContact, _fam: 'call' });
    if (crm.disposition && crm.disposition !== 'nurture' && crm.disposition !== '') candidates.push({ by: owner, action: 'disposition: ' + getDispositionLabel(crm.disposition) + ' (historical)', date: crm.dateLastContact || crm.dateMovedToCRM || lead.dateAdded, _fam: 'disposition' });
    if (crm.meetingBooked && crm.meetingDate) candidates.push({ by: owner, action: 'meeting booked (historical)', date: crm.meetingDate, _fam: 'meeting' });
    if (lead.qualifiedBy && lead.qualification && lead.qualification.dateQualified) candidates.push({ by: lead.qualifiedBy, action: 'qualified (historical)', date: lead.qualification.dateQualified, _fam: 'qualified' });
    if ((lead.movedToCRMBy || lead.status === 'crm') && crm.dateMovedToCRM) candidates.push({ by: lead.movedToCRMBy || owner, action: 'moved to CRM (historical)', date: crm.dateMovedToCRM, _fam: 'crm' });
    candidates.forEach(c => {
      if (!c.date) return;
      const k = (c.by || 'Unknown') + '|' + c._fam + '|' + dayKey(c.date);
      if (realKeys.has(k)) return; // a real logged activity already covers this user+family+day
      realKeys.add(k);
      out.push({ by: c.by || 'Unknown', action: c.action, date: c.date, ...base });
    });
  });
  return out;
}
function getAllActivities() {
  const activities = [];
  const realKeys = new Set();
  state.leads.forEach(lead => {
    if (!lead.activity) return;
    lead.activity.forEach(a => {
      if (!a || typeof a.action !== 'string') return; // guard malformed entries (M12)
      activities.push({ ...a, leadName: lead.businessName, leadId: lead.id, leadStatus: lead.status });
      realKeys.add((a.by || 'Unknown') + '|' + activityFamily(a.action) + '|' + dayKey(a.date));
    });
  });
  // Append read-only historical entries derived from crm.* fields/status.
  getSynthesizedActivities(realKeys).forEach(a => activities.push(a));
  activities.sort((a, b) => new Date(b.date) - new Date(a.date));
  return activities;
}
```
**Resolves:** M12 + historical-timeline enhancement.

---

### Step 25 — `describeAction`: coerce + won/reassigned/started/historical
*Cluster: activity-master (M12/L3). Location: lines 4590-4603.*

**FIND**
```
function describeAction(action) {
  const a = action.toLowerCase();
  if (a.includes('logged call') || a.includes('logged a call') || a.startsWith('called')) return action;
  if (a.includes('disposition')) return action;
  if (a.includes('meeting')) return action;
  if (a.includes('started working')) return action;
  if (a.includes('qualified')) return 'qualified';
  if (a.includes('moved to crm') || a.includes('crm')) return 'moved to CRM';
  if (a.includes('note') || a.includes('added note')) return 'added a note';
  if (a.includes('stage')) return 'changed stage to ' + action.replace(/.*stage\s*(to\s*)?/i, '');
  if (a.includes('archived') || a.includes('archive')) return 'archived';
  if (a.includes('reactivated') || a.includes('reactivate')) return 'reactivated';
  return action;
}
```
**REPLACE**
```
function describeAction(action) {
  const action0 = String(action == null ? '' : action);
  const a = action0.toLowerCase();
  if (a.includes('logged call') || a.includes('logged a call') || a.startsWith('called')) return action0;
  if (a.includes('disposition')) return action0;
  if (a.includes('meeting')) return action0;
  if (a.includes('won')) return action0;
  if (a.includes('reassigned')) return action0;
  if (a.includes('started working')) return action0;
  if (a.includes('qualified')) return a.includes('historical') ? action0 : 'qualified';
  if (a.includes('moved to crm') || a.includes('crm')) return a.includes('historical') ? action0 : 'moved to CRM';
  if (a.includes('note') || a.includes('added note')) return 'added a note';
  if (a.includes('stage')) return 'changed stage to ' + action0.replace(/.*stage\s*(to\s*)?/i, '');
  if (a.includes('archived') || a.includes('archive')) return 'archived';
  if (a.includes('reactivated') || a.includes('reactivate')) return 'reactivated';
  return action0;
}
```
**Resolves:** M12, L3.

---

### Step 26 — `matchesActionFilter`: coerce + won/reassigned/started
*Cluster: activity-master (M12/L3). Location: lines 4605-4620.*

**FIND**
```
function matchesActionFilter(action, filter) {
  if (filter === 'all') return true;
  const a = action.toLowerCase();
  switch (filter) {
    case 'call': return a.includes('logged call') || a.includes('logged a call') || a.startsWith('called');
    case 'disposition': return a.includes('disposition');
    case 'meeting': return a.includes('meeting');
    case 'qualified': return a.includes('qualified');
    case 'moved to CRM': return (a.includes('moved to crm') || a.includes('crm')) && !a.includes('logged call');
    case 'note': return a.includes('note');
    case 'stage': return a.includes('stage');
    case 'archived': return a.includes('archived') || a.includes('archive');
    case 'reactivated': return a.includes('reactivated') || a.includes('reactivate');
    default: return true;
  }
}
```
**REPLACE**
```
function matchesActionFilter(action, filter) {
  if (filter === 'all') return true;
  const a = String(action || '').toLowerCase();
  switch (filter) {
    case 'call': return a.includes('logged call') || a.includes('logged a call') || a.startsWith('called');
    case 'disposition': return a.includes('disposition');
    case 'meeting': return a.includes('meeting');
    case 'won': return a.includes('won');
    case 'reassigned': return a.includes('reassigned');
    case 'started': return a.includes('started working');
    case 'qualified': return a.includes('qualified');
    case 'moved to CRM': return (a.includes('moved to crm') || a.includes('crm')) && !a.includes('logged call');
    case 'note': return a.includes('note');
    case 'stage': return a.includes('stage');
    case 'archived': return a.includes('archived') || a.includes('archive');
    case 'reactivated': return a.includes('reactivated') || a.includes('reactivate');
    default: return true;
  }
}
```
**Resolves:** M12, L3.

---

### Step 27 — `getActionBadgeClass`: coerce + won/reassigned/started badges
*Cluster: activity-master (M12/L3). Location: lines 4622-4634.*

**FIND**
```
function getActionBadgeClass(action) {
  const a = action.toLowerCase();
  if (a.includes('logged call') || a.includes('logged a call') || a.startsWith('called')) return 'badge-orange';
  if (a.includes('meeting')) return 'badge-purple';
  if (a.includes('disposition')) return 'badge-blue';
  if (a.includes('qualified')) return 'badge-teal';
  if (a.includes('crm')) return 'badge-blue';
  if (a.includes('note')) return 'badge-neutral';
  if (a.includes('stage')) return 'badge-purple';
  if (a.includes('archived') || a.includes('archive')) return 'badge-warning';
  if (a.includes('reactivated') || a.includes('reactivate')) return 'badge-success';
  return 'badge-neutral';
}
```
**REPLACE**
```
function getActionBadgeClass(action) {
  const a = String(action || '').toLowerCase();
  if (a.includes('logged call') || a.includes('logged a call') || a.startsWith('called')) return 'badge-orange';
  if (a.includes('won')) return 'badge-success';
  if (a.includes('reassigned')) return 'badge-purple';
  if (a.includes('started working')) return 'badge-teal';
  if (a.includes('meeting')) return 'badge-purple';
  if (a.includes('disposition')) return 'badge-blue';
  if (a.includes('qualified')) return 'badge-teal';
  if (a.includes('crm')) return 'badge-blue';
  if (a.includes('note')) return 'badge-neutral';
  if (a.includes('stage')) return 'badge-purple';
  if (a.includes('archived') || a.includes('archive')) return 'badge-warning';
  if (a.includes('reactivated') || a.includes('reactivate')) return 'badge-success';
  return 'badge-neutral';
}
```
**Resolves:** M12, L3.

---

### Step 28 — `renderActivityMonitor`: gate via `canViewActivityMonitor`
*Clusters: activity-master + identity (M5 — same line). Location: line 4645.*

**FIND**
```
function renderActivityMonitor() {
  if (!isMasterUser()) return;
```
**REPLACE**
```
function renderActivityMonitor() {
  if (!canViewActivityMonitor()) return;
```
**Resolves:** M5.

---

### Step 29 — `renderActivityMonitor`: Monday-start week (M3) + isCall coerce (M12) + filtered calls-today (L4)
*Cluster: activity-master (M3/M12/L4). Location: lines 4658-4675.*

**FIND**
```
  const startOfWeek = new Date(startOfToday);
  startOfWeek.setDate(startOfWeek.getDate() - startOfWeek.getDay());

  let filtered = allActivities.filter(a => {
    if (filterUser !== 'all' && a.by !== filterUser) return false;
    if (!matchesActionFilter(a.action, filterAction)) return false;
    if (filterDate === 'today' && new Date(a.date) < startOfToday) return false;
    if (filterDate === 'week' && new Date(a.date) < startOfWeek) return false;
    return true;
  });

  // Stats
  const totalActions = allActivities.length;
  const actionsToday = allActivities.filter(a => new Date(a.date) >= startOfToday).length;
  const isCall = (a) => { const t = a.action.toLowerCase(); return t.includes('logged call') || t.includes('logged a call') || t.startsWith('called'); };
  const callsToday = allActivities.filter(a => isCall(a) && new Date(a.date) >= startOfToday).length;
  const callsTodayByUser = {};
  allActivities.forEach(a => { if (isCall(a) && new Date(a.date) >= startOfToday) callsTodayByUser[a.by] = (callsTodayByUser[a.by] || 0) + 1; });
```
**REPLACE**
```
  // Monday-start week, unified with Reports (was Sunday-start here) (M3).
  const startOfWeek = new Date(startOfToday);
  startOfWeek.setDate(startOfWeek.getDate() - ((startOfWeek.getDay() + 6) % 7));

  let filtered = allActivities.filter(a => {
    if (filterUser !== 'all' && a.by !== filterUser) return false;
    if (!matchesActionFilter(a.action, filterAction)) return false;
    if (filterDate === 'today' && new Date(a.date) < startOfToday) return false;
    if (filterDate === 'week' && new Date(a.date) < startOfWeek) return false;
    return true;
  });

  // Stats
  const totalActions = allActivities.length;
  const actionsToday = allActivities.filter(a => new Date(a.date) >= startOfToday).length;
  const isCall = (a) => { const t = String(a.action || '').toLowerCase(); return t.includes('logged call') || t.includes('logged a call') || t.startsWith('called'); };
  const callsToday = allActivities.filter(a => isCall(a) && new Date(a.date) >= startOfToday).length;
  // Per-user "calls today" derived from the SAME filtered set the bars use, so the bar count
  // and the calls figure share one scope (L4).
  const callsTodayByUser = {};
  filtered.forEach(a => { if (isCall(a) && new Date(a.date) >= startOfToday) callsTodayByUser[a.by] = (callsTodayByUser[a.by] || 0) + 1; });
```
**Resolves:** M3, M12, L4.

---

### Step 30 — `renderActivityMonitor` feed HTML: escape injected action text
*Cluster: activity-master (L6). Location: lines 4700-4703.*

**FIND**
```
            <span class="am-feed-user">${escapeHtml(a.by)}</span>
            <span class="am-feed-action"> ${describeAction(a.action)} </span>
            <span class="badge ${getActionBadgeClass(a.action)}" style="margin-right:var(--space-2);">${describeAction(a.action)}</span>
            <span class="am-feed-lead" data-action="am-goto-lead" data-lead-id="${a.leadId}">${escapeHtml(a.leadName)}</span>
```
**REPLACE**
```
            <span class="am-feed-user">${escapeHtml(a.by)}</span>
            <span class="am-feed-action"> ${escapeHtml(describeAction(a.action))} </span>
            <span class="badge ${getActionBadgeClass(a.action)}" style="margin-right:var(--space-2);">${escapeHtml(describeAction(a.action))}</span>
            <span class="am-feed-lead" data-action="am-goto-lead" data-lead-id="${a.leadId}">${escapeHtml(a.leadName)}</span>
```
**Resolves:** L6.

---

## PART F — UX / MOBILE (CSS + markup)

### Step 31 — CSS: `.btn-sm` coarse-pointer touch targets
*Cluster: ux-mobile (M9). Location: line 238.*

**FIND**
```
.btn-sm { padding: var(--space-1) var(--space-3); font-size: var(--text-xs); min-height: 32px; }
```
**REPLACE**
```
.btn-sm { padding: var(--space-1) var(--space-3); font-size: var(--text-xs); min-height: 32px; }
@media (pointer: coarse) { .btn-sm { min-height: 44px; } .call-logger .form-select.call-outcome-select { min-height: 44px; } }
```
**Resolves:** M9.

---

### Step 32 — CSS: `.claim-badge` sizing (L7)
*Cluster: ux-mobile (L7). Location: line 296.*

**FIND**
```
.claim-badge { display: inline-flex; align-items: center; gap: 4px; font-size: 0.65rem; font-weight: 600; color: var(--color-warning); background: var(--color-warning-highlight); border-radius: var(--radius-sm); padding: 2px 8px; margin-top: 4px; }
```
**REPLACE**
```
.claim-badge { display: inline-flex; align-items: center; gap: 4px; font-size: 0.72rem; font-weight: 600; color: var(--color-warning); background: var(--color-warning-highlight); border-radius: var(--radius-sm); padding: 3px 8px; margin-top: 4px; }
```
**Resolves:** L7.

---

### Step 33 — CSS: `.claim-badge.live` accessible contrast (L7)
*Cluster: ux-mobile (L7). Location: line 297.*

**FIND**
```
.claim-badge.live { color: var(--color-error); background: var(--color-error-highlight); }
```
**REPLACE**
```
.claim-badge.live { color: #fff; background: var(--color-error); font-weight: 700; }
```
**Resolves:** L7.

---

### Step 34 — CSS: mobile top-bar compaction (H6)
*Cluster: ux-mobile (H6). Location: lines 523-525.*

**FIND**
```
  .hamburger { display: flex; }
  .top-bar-logo span { display: none; }
  .main-content { padding: var(--space-4); }
```
**REPLACE**
```
  .hamburger { display: flex; }
  .top-bar-logo span { display: none; }
  .top-bar { padding: 0 var(--space-3); gap: var(--space-2); }
  .top-bar-search { margin: 0; min-width: 0; }
  .top-bar-user { font-size: 0; gap: 0; }
  .top-bar-user strong { font-size: var(--text-xs); max-width: 84px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .top-bar-user a#switch-user-btn { font-size: var(--text-xs); margin-left: var(--space-2); }
  .top-bar-user-label { display: none; }
  .main-content { padding: var(--space-4); }
```
**Resolves:** H6. *(Added `.top-bar-user-label { display: none; }` to hide the label that Step 35 wraps.)*

---

### Step 35 — markup: wrap "Signed in as:" label so mobile can hide it (H6)
*Cluster: ux-mobile (H6). Location: lines 836-838.*

**FIND**
```
      <div class="top-bar-user" id="top-bar-user">
        Signed in as: <strong id="current-user-display"></strong>
        <a id="switch-user-btn" role="button" tabindex="0">Switch</a>
      </div>
```
**REPLACE**
```
      <div class="top-bar-user" id="top-bar-user">
        <span class="top-bar-user-label">Signed in as:</span> <strong id="current-user-display"></strong>
        <a id="switch-user-btn" role="button" tabindex="0">Switch</a>
      </div>
```
**Resolves:** H6.

---

## PART G — RUNTIME GUARDS (renderer/search null-safety)

### Step 36 — `renderLeadBank` search filter null-guard
*Cluster: runtime-guards (C5). Location: line 2234.*

**FIND**
```
    leads = leads.filter(l =>
      l.businessName.toLowerCase().includes(s) ||
      l.description.toLowerCase().includes(s) ||
      l.contacts.some(c => c.name.toLowerCase().includes(s))
    );
```
**REPLACE**
```
    leads = leads.filter(l =>
      (l.businessName || '').toLowerCase().includes(s) ||
      (l.description || '').toLowerCase().includes(s) ||
      (l.contacts || []).some(c => (c && c.name || '').toLowerCase().includes(s))
    );
```
**Resolves:** C5.

---

### Step 37 — `renderLeadBank` contact-count null-guard
*Cluster: runtime-guards (C5). Location: line 2332.*

**FIND**
```
            <span><i data-lucide="users" aria-hidden="true"></i> ${l.contacts.length} contact${l.contacts.length !== 1 ? 's' : ''}</span>
```
**REPLACE**
```
            <span><i data-lucide="users" aria-hidden="true"></i> ${(l.contacts || []).length} contact${(l.contacts || []).length !== 1 ? 's' : ''}</span>
```
**Resolves:** C5.

---

### Step 38 — View-Lead panel phone block: per-number Call button (M9/M10), num coercion (M11), 44px target
*Clusters: ux-mobile (M9/M10) + runtime-guards (M11/H5). MERGED — single template line. Location: line 2440.*

**FIND**
```
    ${lead.phones.length ? `<div class="form-group"><span class="form-label">Phone Numbers</span>${lead.phones.map(p => `<div style="display:flex;align-items:center;gap:var(--space-2);margin-bottom:var(--space-1);"><a href="tel:${escapeHtml(p.number.replace(/[^+0-9]/g,''))}" style="font-size:var(--text-sm);color:var(--color-primary);text-decoration:underline;text-underline-offset:2px;"><i data-lucide="phone" style="width:13px;height:13px;vertical-align:-2px;margin-right:3px;" aria-hidden="true"></i>${escapeHtml(p.number)}</a><button class="btn btn-ghost btn-sm" style="min-height:26px;padding:2px var(--space-2);font-size:var(--text-xs);" data-action="log-call" data-id="${lead.id}" data-num="${escapeHtml(p.number)}"><i data-lucide="phone-call" style="width:12px;height:12px;" aria-hidden="true"></i> Log call</button></div>`).join('')}</div>` : ''}
```
**REPLACE**
```
    ${(lead.phones || []).length ? `<div class="form-group"><span class="form-label">Phone Numbers</span>${(lead.phones || []).map(p => { const num = String((p && p.number) || ''); return `<div style="display:flex;align-items:center;gap:var(--space-2);margin-bottom:var(--space-1);"><button class="btn btn-sm" style="background:var(--color-primary);color:white;flex:1 1 auto;justify-content:flex-start;" data-action="call-lead" data-id="${lead.id}" data-num="${escapeHtml(num)}"><i data-lucide="phone" style="width:13px;height:13px;margin-right:4px;" aria-hidden="true"></i>${escapeHtml(num)}</button><button class="btn btn-ghost btn-sm" style="padding:2px var(--space-3);font-size:var(--text-xs);" data-action="log-call" data-id="${lead.id}" data-num="${escapeHtml(num)}"><i data-lucide="phone-call" style="width:12px;height:12px;" aria-hidden="true"></i> Log call</button></div>`; }).join('')}</div>` : ''}
```
**Resolves:** M9, M10, M11, H5. *(This is one self-contained template line; FIND and REPLACE must be applied together — the arrow body `=> { const num...; return \`...\`; }` is balanced.)*

---

### Step 39 — `renderCRM` search filter null-guard
*Cluster: runtime-guards (C5). Location: line 2640.*

**FIND**
```
    leads = leads.filter(l =>
      l.businessName.toLowerCase().includes(s) ||
      l.contacts.some(c => c.name.toLowerCase().includes(s))
    );
```
**REPLACE**
```
    leads = leads.filter(l =>
      (l.businessName || '').toLowerCase().includes(s) ||
      (l.contacts || []).some(c => (c && c.name || '').toLowerCase().includes(s))
    );
```
**Resolves:** C5.

---

### Step 40 — `renderCRMList`: crm locals (notes/priority guards)
*Cluster: runtime-guards (C3). Location: lines 2746-2748.*

**FIND**
```
  leads.forEach(l => {
    const crm = l.crm;
    if (!crm) return;
```
**REPLACE**
```
  leads.forEach(l => {
    const crm = l.crm;
    if (!crm) return;
    const crmNotes = Array.isArray(crm.notes) ? crm.notes : [];
    const crmPriority = crm.priority || 'medium';
```
**Resolves:** C3.

---

### Step 41 — `renderCRMList` priority badge
*Cluster: runtime-guards (C3). Location: line 2790.*

**FIND**
```
            <span class="badge priority-badge ${priorityColors[crm.priority]}" data-action="cycle-priority" data-id="${l.id}" title="Click to change priority">${crm.priority.charAt(0).toUpperCase() + crm.priority.slice(1)}</span>
```
**REPLACE**
```
            <span class="badge priority-badge ${priorityColors[crmPriority]}" data-action="cycle-priority" data-id="${l.id}" title="Click to change priority">${crmPriority.charAt(0).toUpperCase() + crmPriority.slice(1)}</span>
```
**Resolves:** C3.

---

### Step 42 — `renderCRMList` notes block (use `crmNotes`)
*Cluster: runtime-guards (C3). Location: line 2828.*

**FIND**
```
          ${crm.notes.slice(0, expanded ? crm.notes.length : 2).map(n => `
            <div class="crm-note-item">
              <div>${escapeHtml(n.text)}</div>
              <div class="crm-note-time">${formatDateTime(n.timestamp)}${n.addedBy ? ' &middot; ' + escapeHtml(n.addedBy) : ''}</div>
            </div>
          `).join('')}
          ${crm.notes.length > 2 && !expanded ? `<button class="add-item-btn" data-action="expand-notes" data-id="${l.id}">View all ${crm.notes.length} notes</button>` : ''}
          ${crm.notes.length > 2 && expanded ? `<button class="add-item-btn" data-action="collapse-notes" data-id="${l.id}">Show less</button>` : ''}
```
**REPLACE**
```
          ${crmNotes.slice(0, expanded ? crmNotes.length : 2).map(n => `
            <div class="crm-note-item">
              <div>${escapeHtml(n.text)}</div>
              <div class="crm-note-time">${formatDateTime(n.timestamp)}${n.addedBy ? ' &middot; ' + escapeHtml(n.addedBy) : ''}</div>
            </div>
          `).join('')}
          ${crmNotes.length > 2 && !expanded ? `<button class="add-item-btn" data-action="expand-notes" data-id="${l.id}">View all ${crmNotes.length} notes</button>` : ''}
          ${crmNotes.length > 2 && expanded ? `<button class="add-item-btn" data-action="collapse-notes" data-id="${l.id}">Show less</button>` : ''}
```
**Resolves:** C3.

---

### Step 43 — CRM "Add" note button: remove inline min-height (M9)
*Cluster: ux-mobile (M9). Location: line 2838.*

**FIND**
```
            <button class="btn btn-primary btn-sm" data-action="add-note" data-id="${l.id}" style="min-height:28px;padding:var(--space-1) var(--space-2);">Add</button>
```
**REPLACE**
```
            <button class="btn btn-primary btn-sm" data-action="add-note" data-id="${l.id}" style="padding:var(--space-1) var(--space-3);">Add</button>
```
**Resolves:** M9.

---

### Step 44 — `renderCRMBoard` kanban: `crmPriority` local
*Cluster: runtime-guards (C3). Location: lines 2909-2911.*

**FIND**
```
            const priorityColors = { high: 'badge-error', medium: 'badge-orange', low: 'badge-neutral' };
            const fuDays = daysUntil(crm.followUpDate);
```
**REPLACE**
```
            const priorityColors = { high: 'badge-error', medium: 'badge-orange', low: 'badge-neutral' };
            const crmPriority = crm.priority || 'medium';
            const fuDays = daysUntil(crm.followUpDate);
```
**Resolves:** C3.

---

### Step 45 — `renderCRMBoard` kanban priority badge
*Cluster: runtime-guards (C3). Location: line 2917.*

**FIND**
```
                  <span class="badge ${priorityColors[crm.priority]}">${crm.priority}</span>
```
**REPLACE**
```
                  <span class="badge ${priorityColors[crmPriority]}">${crmPriority}</span>
```
**Resolves:** C3.

---

## PART H — MERGE / SEED (last; depends on normalizeLead, _echoKey, __leadHashes, canViewActivityMonitor, CLAIM_TTL_MS)

### Step 46 — startSharedSync merge loop: `_srvAt` ordering (M1), empty-`_modAt` guard (C1), activity union (C2), concurrent-claim guard (H7)
*Clusters: sync-data (C1/C2/M1) + claiming (H7). MERGED. Location: lines 6124-6136.*

> `lastPushedSuppress` (referenced in the original claiming H7 edit) does not exist in the file; replaced with the equivalent inline `lastPushed.delete(local.id);`.

**FIND**
```
      const byId = new Map();
      const localList = Array.isArray(state.leads) ? state.leads : [];
      for (const l of localList) { if (l && l.id) byId.set(l.id, l); }
      for (const r of remoteLeads) {
        if (!r || !r.id) continue;
        const local = byId.get(r.id);
        if (!local) { r.__remoteStamped = true; byId.set(r.id, r); continue; }
        const rAt = (typeof r._modAt === 'string') ? r._modAt : '';
        const lAt = (typeof local._modAt === 'string') ? local._modAt : '';
        // Remote wins only if it is strictly newer than the local copy.
        if (rAt > lAt) { r.__remoteStamped = true; byId.set(r.id, r); }
        // else keep local (an unpushed newer edit, or a tie) and let it push on next saveState.
      }
```
**REPLACE**
```
      const byId = new Map();
      const localList = Array.isArray(state.leads) ? state.leads : [];
      for (const l of localList) { if (l && l.id) byId.set(l.id, l); }
      const me = (typeof getCurrentUser === 'function') ? getCurrentUser() : 'Unknown';
      const claimConflicts = [];
      // Ordering key (M1): prefer the authoritative server clock _srvAt when BOTH sides have it
      // (skew-proof); otherwise fall back to the device wall-clock _modAt.
      const __ord = (a, b) => {
        const aS = (typeof a._srvAt === 'string') ? a._srvAt : '';
        const bS = (typeof b._srvAt === 'string') ? b._srvAt : '';
        if (aS && bS) return [aS, bS];
        return [ (typeof a._modAt === 'string') ? a._modAt : '', (typeof b._modAt === 'string') ? b._modAt : '' ];
      };
      // Activity union (C2): events are append-only; never lose a rep's logged action just
      // because the scalar copy lost the merge. Dedupe by by|action|date.
      const __unionActivity = (a, b) => {
        const out = []; const seen = new Set();
        for (const e of [].concat(Array.isArray(a) ? a : [], Array.isArray(b) ? b : [])) {
          if (!e) continue;
          const k = (e.by || '') + '|' + (e.action || '') + '|' + (e.date || '');
          if (seen.has(k)) continue; seen.add(k); out.push(e);
        }
        out.sort((x, y) => String(y.date || '').localeCompare(String(x.date || '')));
        return out;
      };
      for (const r of remoteLeads) {
        if (!r || !r.id) continue;
        const local = byId.get(r.id);
        if (!local) { r.__remoteStamped = true; byId.set(r.id, r); continue; }
        // CONCURRENT-CLAIM GUARD (H7): if we think we're actively on this lead but a remote copy
        // shows a DIFFERENT rep with a still-active claim, they claimed it in the same window.
        // First-writer-wins by their activeCallAt: keep their active claim, drop ours, warn.
        const rActive = r.activeCallBy && r.activeCallAt &&
          (Date.now() - new Date(r.activeCallAt).getTime()) < CLAIM_TTL_MS;
        if (rActive && local.activeCallBy === me && r.activeCallBy !== me) {
          claimConflicts.push(r.activeCallBy);
          local.activeCallBy = r.activeCallBy;
          local.activeCallAt = r.activeCallAt;
          // Don't re-push our overwritten claim as an echo war.
          try { lastPushed.delete(local.id); } catch (_) {}
        }
        const [rAt, lAt] = __ord(r, local);
        // C1 guard: a local edit with NO _modAt is an unsynced outage edit — never overwrite it.
        const localUnstamped = !(typeof local._modAt === 'string' && local._modAt);
        if (rAt > lAt && !localUnstamped) {
          // C2: carry forward the union of both activity logs onto the winning remote copy.
          r.activity = __unionActivity(local.activity, r.activity);
          r.__remoteStamped = true; byId.set(r.id, r);
        } else {
          // Keep local (unpushed/newer/tie/outage edit) but still absorb any remote activity the
          // local copy is missing, so no rep's logged work is dropped (C2).
          local.activity = __unionActivity(local.activity, r.activity);
        }
      }
      if (claimConflicts.length && typeof showToast === 'function') {
        showToast(claimConflicts[0] + ' just claimed this lead', 'warning');
      }
```
**Resolves:** C1, C2, M1, H7.

---

### Step 47 — startSharedSync merge tail: drop tombstones (H3), normalize (C3/C5/H5), seed hashes (H2), deferred push-back (H4)
*Clusters: sync-data (H3/H4/H2) + runtime-guards (C3/C5/H5). MERGED. Location: lines 6139-6152.*

**FIND**
```
      // Drop the fictional sample leads once real cloud data is present.
      let merged = Array.from(byId.values());
      if (remoteLeads.length > 0) merged = merged.filter(l => l && l.source !== 'sample');
      state.leads = merged;
      // __applyingRemote so saveState below doesn't re-stamp the just-merged remote leads.
      CrescendoSync.__applyingRemote = true;
      try {
        try { localStorage.setItem('crescendo-leads', JSON.stringify(state.leads)); } catch (_) {}
        // Push back any local-only or locally-newer leads the merge kept (real leads only).
        if (typeof CrescendoSync.pushLeads === 'function') CrescendoSync.pushLeads(state.leads);
      } finally { CrescendoSync.__applyingRemote = false; }
      // Clear the per-merge stamp markers now that this snapshot is fully applied.
      for (const l of state.leads) { if (l) delete l.__remoteStamped; }
      if (typeof renderAll === 'function') renderAll();
```
**REPLACE**
```
      // Drop the fictional sample leads once real cloud data is present.
      let merged = Array.from(byId.values());
      if (remoteLeads.length > 0) merged = merged.filter(l => l && l.source !== 'sample');
      // TOMBSTONES (H3): a lead whose winning copy is _deleted is gone team-wide — drop it so it
      // can't render or be re-pushed (no resurrection on next save).
      merged = merged.filter(l => l && !l._deleted);
      // Normalise shape AFTER the merge picks winners / unions activity, BEFORE assign (C3/C5/H5).
      merged.forEach(l => normalizeLead(l));
      state.leads = merged;
      // Seed the content-hash ledger for merged leads so the next saveState doesn't treat
      // freshly-merged remote leads as "changed" and re-stamp/re-push them (H2 coherence).
      try { if (typeof __leadHashes !== 'undefined') for (const l of state.leads) { if (l && l.id) __leadHashes.set(l.id, __leadContentHash(l)); } } catch (_) {}
      // __applyingRemote so saveState/pushLeads don't re-stamp the just-merged remote leads.
      CrescendoSync.__applyingRemote = true;
      try { localStorage.setItem('crescendo-leads', JSON.stringify(state.leads)); } catch (_) {}
      // Clear the per-merge stamp markers now that this snapshot is fully applied.
      for (const l of state.leads) { if (l) delete l.__remoteStamped; }
      CrescendoSync.__applyingRemote = false;
      // PUSH-BACK (H4): defer outside the synchronous snapshot window. Previously this ran while
      // applyingRemote was still set inside pushLeads' closure, so it pushed nothing. The
      // lastPushed ledger still suppresses true echoes, so only locally-newer / local-only leads
      // actually write.
      setTimeout(() => { try { if (typeof CrescendoSync.pushLeads === 'function') CrescendoSync.pushLeads(state.leads); } catch (_) {} }, 0);
      if (typeof renderAll === 'function') renderAll();
```
**Resolves:** H3, H4, H2, C3, C5, H5.

---

### Step 48 — startSharedSync seed gate: create-if-absent meta/seeded transaction (L1)
*Cluster: sync-data (L1). Location: lines 6156-6162. Depends on Step 1 (runTransaction) + Step 8 (`__db`).*

**FIND**
```
    setTimeout(() => {
      if (!CrescendoSync.__cloudSeeded && CrescendoSync.__cloudKnownEmpty &&
          Array.isArray(state.leads) && state.leads.some(l => l && l.source !== 'sample')) {
        CrescendoSync.__cloudSeeded = true;
        CrescendoSync.pushLeads(state.leads.filter(l => l && l.source !== 'sample'));
      }
    }, 1500);
```
**REPLACE**
```
    setTimeout(async () => {
      if (!CrescendoSync.__cloudSeeded && CrescendoSync.__cloudKnownEmpty &&
          Array.isArray(state.leads) && state.leads.some(l => l && l.source !== 'sample')) {
        CrescendoSync.__cloudSeeded = true;
        // DOUBLE-SEED GUARD (L1): two reps booting against a genuinely empty cloud in the same
        // window could both seed all ~540 leads. Claim the seed via a create-if-absent
        // meta/seeded doc in a transaction; only the winner proceeds. Cross-device, not per-session.
        let __mayseed = true;
        try {
          if (window.__fb && window.__fb.runTransaction && CrescendoSync.__db) {
            const ref = window.__fb.doc(CrescendoSync.__db, 'meta', 'seeded');
            __mayseed = await window.__fb.runTransaction(CrescendoSync.__db, async (tx) => {
              const snap = await tx.get(ref);
              if (snap.exists()) return false;
              tx.set(ref, { seededAt: window.__fb.serverTimestamp(), seededBy: (typeof getCurrentUser === 'function') ? getCurrentUser() : 'Unknown' });
              return true;
            });
          }
        } catch (_) { __mayseed = true; /* transaction unavailable — fall back to per-session gate */ }
        if (__mayseed) CrescendoSync.pushLeads(state.leads.filter(l => l && l.source !== 'sample'));
      }
    }, 1500);
```
**Resolves:** L1.

---

### Step 49 — `init()`: local-only claim-badge refresh interval (M2)
*Cluster: claiming (M2). Location: line 6107-6108.*

**FIND**
```
  // Boot shared-backend sync (safe no-op if Firebase isn't configured).
  startSharedSync();
}
```
**REPLACE**
```
  // Boot shared-backend sync (safe no-op if Firebase isn't configured).
  startSharedSync();
  // Refresh claim badges as their CLAIM_TTL_MS expires. Local-only (no writes): re-renders so a
  // freed/stale 'X is on this' badge clears without anyone touching the page (M2).
  if (!window.__claimBadgeTimer) {
    window.__claimBadgeTimer = setInterval(() => {
      if (typeof renderAll === 'function') renderAll();
    }, 30000);
  }
}
```
**Resolves:** M2.

---

## VERIFICATION CHECKLIST

Run after applying all 49 steps.

1. **Batch chunking / >500 leads.** With ~540 real leads, a full push splits into 2 `writeBatch` commits of ≤450 ops each; no "batch too large" error. Confirm the seed push and a single-claim push both succeed. (Steps 4, 5)
2. **Only changed leads write.** Editing one lead and saving pushes exactly one doc (echo-key dedup + content-hash dirty set), not ~540. Re-saving with no change pushes nothing. (Steps 4, 16)
3. **No white-screen on partial/malformed leads.** Import a lead missing `businessName`/`phones`/`contacts`/`crm.priority`/`crm.notes`; Lead Bank, CRM list, CRM kanban, and View-Lead panel all render without throwing. (Steps 15, 17, 36-45, 38)
4. **Activity unioned, not dropped.** Two reps log different calls on the same lead offline; after both sync, the lead's `activity[]` contains BOTH entries (deduped by by|action|date), regardless of which scalar copy won the merge. (Step 46)
5. **Outage edits preserved.** Edit a lead while Firebase is unreachable (no `_modAt` backfill until reconnect), then reconnect with an older cloud copy present: the local outage edit is NOT overwritten (empty/backfilled `_modAt` guard + `localUnstamped` merge guard). (Steps 17, 46)
6. **Soft-delete sticks.** Delete a lead on device A; on device B the lead disappears (tombstone `_deleted` filtered before render/push) and does not resurrect on B's next save. (Steps 4, 47)
7. **Claim survives tel: on mobile.** On a phone, tap Call: `CrescendoSync.flush()` fires the claim commit synchronously before `window.location.href = 'tel:'`; after returning to the app the claim is present in the cloud. (Steps 5, 18)
8. **Concurrent-claim warning.** Two reps claim the same lead within `CLAIM_TTL_MS`; the later device sees an "X just claimed this lead" toast and yields to the first writer. (Step 46)
9. **Stale claim badge clears.** A claim older than `CLAIM_TTL_MS` drops its badge within ~30s without any write, via the local re-render interval. (Step 49)
10. **Master + CEO can open Activity Monitor.** Logging in as `Master` (PIN) OR any CEO name (`Melusi Ndoro`, `Joshua Khalili`, `Ayoub Rasol`) shows the nav button, does not redirect away, and renders the monitor. Consultants/custom reps still cannot. (Steps 9, 11, 28)
11. **No "Master" self-promotion.** Typing `master`/`Master`/`  MASTER ` in the add-rep field is rejected with the reserved-name message; only the PIN branch grants owner. (Steps 9, 10, 14)
12. **Activity Monitor week = Monday-start**, matching Reports; per-user "calls today" matches the bar (filtered scope); won/reassigned/started are filterable and badged; malformed `action` entries don't crash; action text is HTML-escaped. (Steps 23-30)
13. **No push/snapshot loop.** After the first merge settles, the app reaches a steady state with no continuous re-pushing (server `_srvAt` is stripped from the echo key; merged-lead hashes seeded). (Steps 2, 3, 4, 47)
14. **Double-seed guard.** Two fresh devices booting against an empty cloud: only one seeds all leads (meta/seeded transaction); the other yields. Falls back to per-session gate if `runTransaction`/`__db` unavailable. (Steps 1, 8, 48)
15. **Mobile top-bar usable** at 375px: search remains usable, user name truncates to 84px, "Signed in as:" label hidden, Switch visible. Sync indicator sits above the chat FAB and doesn't eat taps. (Steps 6, 34, 35)
16. **Multi-phone dialing.** Tapping a specific number dials that line; a lead with multiple numbers and no specific tap shows a chooser prompt. Touch targets are ≥44px on coarse pointers. (Steps 18, 31, 38, 43)
