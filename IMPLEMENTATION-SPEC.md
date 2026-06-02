# Crescendo CRM — Consolidated Implementation Spec

Single-file target: `/Users/theshumba/Documents/GitHub/crescendo-crm/crescendo-crm.html`
Plus security file: `/Users/theshumba/Documents/GitHub/crescendo-crm/firestore.rules`

This merges 6 specialist specs (A sync-safety, claim/double-call, activity-tracking, D identity, E UI/UX, F security) into one ordered, conflict-free edit list. Every FIND below was verified verbatim against the current file. Apply edits **top to bottom in the numbered order**. The data-critical SYNC SAFETY fix (Steps 1–8) lands first.

---

## OPEN QUESTIONS (could not be fully de-conflicted — decide before/at deploy)

1. **`allow delete: if false` (Step 30) vs. real deletions.** Firestore rejects the *entire* atomic batch if it contains any delete. Step 4 already scopes `pushLeads` deletes to an explicit `pendingDeletes` set, so a normal sync push contains no deletes and is unaffected. BUT a genuine user delete (Step 6 `deleteLead` → `queueDelete`) will produce a delete op that the rules now reject, throwing "Sync error" and leaving the lead in the cloud. **Decision needed:** either (a) keep `allow delete: if false` and accept that deletions must be done from the Firebase console (recommended for safety while the team is small), or (b) loosen the rule to `allow delete: if signedIn()` to let user deletes propagate (re-opens a narrower mass-wipe window, now mitigated by Step 4's scoping). Spec ships option (a); flip the one line if the team needs in-app deletes.

2. **Seed-push timing race (Step 8).** Seed-push waits 1500ms for the first snapshot to set `__cloudKnownEmpty`. If the very first `onSnapshot` is slower than 1.5s on a cold connection, a genuinely-empty cloud will NOT be seeded this session (self-heals on next saveState/reload). Tunable; left at 1500ms.

3. **`.firebaserc` default project** is still `PASTE_YOUR_FIREBASE_PROJECT_ID`. Rules cannot be deployed until it is set to `crescendocrm-5de1b` (or pass `--project crescendocrm-5de1b`). Do this only in a PRIVATE/local deploy copy — never commit real project id/config to the public repo (see Deployment section).

4. **LWW on concurrent same-lead edits.** Two reps editing the *same* lead inside one snapshot window resolve last-writer-by-`_modAt` (intended). There is no field-level merge; whole-lead newer-wins. Accepted as the intended behaviour.

---

## PART 1 — SYNC SAFETY & MERGE ENGINE (data-critical, apply FIRST)

### Step 1 — Restore real Firebase config
Location: config block, lines 23–31.

FIND:
```
  window.CRESCENDO_FIREBASE_CONFIG = {
    apiKey: "PASTE_YOUR_API_KEY",
    authDomain: "PASTE_YOUR_PROJECT.firebaseapp.com",
    projectId: "PASTE_YOUR_PROJECT_ID",
    storageBucket: "PASTE_YOUR_PROJECT.firebasestorage.app",
    messagingSenderId: "PASTE_YOUR_SENDER_ID",
    appId: "PASTE_YOUR_APP_ID",
    measurementId: "PASTE_YOUR_MEASUREMENT_ID"
  };
```
REPLACE:
```
  window.CRESCENDO_FIREBASE_CONFIG = {
    apiKey: "AIzaSyDd2_q4ZKw8bOPhCYj8wNB1mbeco7UFKYY",
    authDomain: "crescendocrm-5de1b.firebaseapp.com",
    projectId: "crescendocrm-5de1b",
    storageBucket: "crescendocrm-5de1b.firebasestorage.app",
    messagingSenderId: "1066244350556",
    appId: "1:1066244350556:web:cf064fb67e87ad5fbd7c99",
    measurementId: "G-181JEDDKVS"
  };
```
Rationale: `isConfigured()` passes and the app connects to the live `crescendocrm-5de1b` project.
**DEPLOYMENT WARNING:** apply this only in the PRIVATE/live copy. The public GitHub Pages repo must keep the `PASTE_YOUR_*` placeholders (see Deployment section).

---

### Step 2 — Add merge-engine state vars
Location: `CrescendoSync` IIFE state vars, ~line 980–984.

FIND:
```
  let applyingRemote = false;       // guard so onSnapshot callbacks don't re-push writes
  let lastPushed = new Map();       // leadId -> JSON string of last-pushed lead
  let pushTimer = null;
  let pendingPush = false;
  let onRemoteCb = null;
```
REPLACE:
```
  let applyingRemote = false;       // guard so onSnapshot callbacks don't re-push writes
  let lastPushed = new Map();       // leadId -> JSON string of last-pushed lead
  let pushTimer = null;
  let pendingPush = false;
  let onRemoteCb = null;
  let firstSnapshotSeen = false;    // becomes true after the first remote snapshot arrives
  let cloudWasEmpty = false;        // true only if that first snapshot had ZERO docs
  const pendingDeletes = new Set(); // lead ids the app has EXPLICITLY deleted (scoped delete safety)
```
Rationale: adds first-snapshot gate, empty-cloud detector, and explicit delete set.

---

### Step 3 — Stop stripping `_modAt`/`_modBy`; report first-snapshot/cloud-empty
Location: `subscribe` snapshot handler, ~lines 1025–1037.

FIND:
```
      snap => {
        const remoteLeads = [];
        snap.forEach(d => {
          const raw = d.data();
          // Strip internal sync metadata before handing back to the app.
          const { _modBy, _modAt, ...lead } = raw;
          remoteLeads.push(lead);
          lastPushed.set(lead.id, JSON.stringify(lead));
        });
        applyingRemote = true;
        try { onRemoteCb && onRemoteCb(remoteLeads); }
        finally { applyingRemote = false; }
      },
```
REPLACE:
```
      snap => {
        const remoteLeads = [];
        snap.forEach(d => {
          const raw = d.data();
          // Normalise the sync timestamp to an ISO string for merge comparison.
          // _modAt may be a Firestore Timestamp (legacy serverTimestamp writes) or an ISO string (new writes).
          let modAt = raw._modAt;
          if (modAt && typeof modAt.toDate === 'function') { try { modAt = modAt.toDate().toISOString(); } catch (_) { modAt = ''; } }
          const lead = { ...raw };
          lead._modAt = (typeof modAt === 'string') ? modAt : '';
          // Keep _modAt/_modBy ON the lead so the app-level merge can compare versions.
          remoteLeads.push(lead);
          // lastPushed ledger stores the exact serialization we'd re-push, so identical
          // remote echoes are skipped by pushLeads (prevents push/snapshot loops).
          lastPushed.set(lead.id, JSON.stringify({ ...lead }));
        });
        // Record cloud-empty state exactly once, on the very first snapshot.
        if (!firstSnapshotSeen) { cloudWasEmpty = (remoteLeads.length === 0); }
        applyingRemote = true;
        try { onRemoteCb && onRemoteCb(remoteLeads, { firstSnapshot: !firstSnapshotSeen, cloudEmpty: cloudWasEmpty }); }
        finally { applyingRemote = false; firstSnapshotSeen = true; }
      },
```
Rationale: keeps merge-ordering metadata, normalises legacy Timestamp `_modAt`, and reports first-snapshot/cloud-empty status to the caller.

---

### Step 4 — Scoped deletes + ISO stamp + block sample leads in `pushLeads`
Location: `pushLeads` body, ~lines 1059–1075.

FIND:
```
        for (const lead of leads) {
          if (!lead || !lead.id) continue;
          currentIds.add(lead.id);
          const serialized = JSON.stringify(lead);
          if (lastPushed.get(lead.id) === serialized) continue; // unchanged
          const ref = window.__fb.doc(db, 'leads', String(lead.id));
          batch.set(ref, { ...lead, _modBy: user, _modAt: window.__fb.serverTimestamp() });
          lastPushed.set(lead.id, serialized);
        }
        // Deletions: anything we previously pushed but isn't in leads anymore.
        for (const id of Array.from(lastPushed.keys())) {
          if (!currentIds.has(id)) {
            const ref = window.__fb.doc(db, 'leads', String(id));
            batch.delete(ref);
            lastPushed.delete(id);
          }
        }
```
REPLACE:
```
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
```
Rationale: blocks sample SEED_LEADS reaching prod, writes a comparable ISO `_modAt`, and replaces the dangerous "delete every previously-seen id" loop with an explicit `pendingDeletes` set. (Coordinated with Step 30 rules: a normal push now contains no deletes, so the rules' `allow delete: if false` will not reject syncs.)

---

### Step 5 — Export `queueDelete`
Location: `CrescendoSync` return line, ~line 1109.

FIND:
```
  return { init, subscribe, pushLeads, isConfigured, showSyncStatus };
})();
```
REPLACE:
```
  // Mark a lead id for cloud deletion on the next push (explicit deletes only).
  function queueDelete(id) { if (id != null) pendingDeletes.add(String(id)); }
  return { init, subscribe, pushLeads, isConfigured, showSyncStatus, queueDelete };
})();
```
Rationale: gives `deleteLead` the only path to register an intentional cloud deletion under the scoped model.

---

### Step 6 — `deleteLead` registers intentional deletion
Location: ~lines 1633–1636.

FIND:
```
function deleteLead(id) {
  state.leads = state.leads.filter(l => l.id !== id);
  saveState();
}
```
REPLACE:
```
function deleteLead(id) {
  state.leads = state.leads.filter(l => l.id !== id);
  // Register the intentional deletion so the sync layer removes it from the cloud too.
  try { CrescendoSync.queueDelete(id); } catch (_) {}
  saveState();
}
```
Rationale: genuine user deletions still propagate to Firestore. (See OPEN QUESTION 1 re: `allow delete: if false`.)

---

### Step 7 — `saveState` stamps `_modAt`/`_modBy` at the write chokepoint
Location: `saveState`, ~line 1640.

FIND:
```
function saveState() {
  try {
    localStorage.setItem('crescendo-leads', JSON.stringify(state.leads));
```
REPLACE:
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
  try {
    localStorage.setItem('crescendo-leads', JSON.stringify(state.leads));
```
Rationale: provides the merge-engine ordering key. `__remoteStamped` (set by the merge callback in Step 8) prevents a freshly-merged remote lead from being re-stamped as a fake local edit.
**Compose note:** this PREPENDS a block before the existing `localStorage.setItem` line and does not alter the existing `saveState` body (its trailing `CrescendoSync.pushLeads(state.leads)` call stays — all downstream activity/claim writes rely on it).

---

### Step 8 — Replace blind remote-wins with per-lead merge + gated seed-push
Location: `startSharedSync` subscribe callback + seed-push, ~lines 5844–5855.
This is ONE contiguous replacement combining the sync spec's two stacked edits (merge body + cloudEmpty wiring) into the final block.

FIND:
```
    CrescendoSync.subscribe(remoteLeads => {
      // Remote snapshot wins; this makes the Master view reflect everyone's work live.
      state.leads = remoteLeads;
      // Persist locally too so offline reloads keep the latest data.
      try { localStorage.setItem('crescendo-leads', JSON.stringify(state.leads)); } catch (_) {}
      if (typeof renderAll === 'function') renderAll();
    });
    // First-time seed-push: if we already had local leads but nothing in the cloud yet,
    // kick a push so the Master immediately sees what's local.
    if (Array.isArray(state.leads) && state.leads.length > 0) {
      CrescendoSync.pushLeads(state.leads);
    }
```
REPLACE:
```
    CrescendoSync.subscribe((remoteLeads, meta) => {
      meta = meta || {};
      // SAFE PER-LEAD MERGE: union of local + remote by id, keeping whichever copy has
      // the newer _modAt (ISO string compare; missing/empty _modAt is treated as oldest).
      // This never clobbers a local edit the rep just made that hasn't pushed yet.
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
      // Surface the first-snapshot empty-cloud signal to the deferred seed-push gate.
      if (meta.firstSnapshot) { CrescendoSync.__cloudKnownEmpty = !!meta.cloudEmpty; }
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
    });
    // First-EVER seed-push: only when the cloud is genuinely empty (fresh setup) AND our
    // local leads are real (not the fictional samples). Never push over existing cloud data.
    setTimeout(() => {
      if (!CrescendoSync.__cloudSeeded && CrescendoSync.__cloudKnownEmpty &&
          Array.isArray(state.leads) && state.leads.some(l => l && l.source !== 'sample')) {
        CrescendoSync.__cloudSeeded = true;
        CrescendoSync.pushLeads(state.leads.filter(l => l && l.source !== 'sample'));
      }
    }, 1500);
```
Rationale: eliminates the central data-loss bug — per-lead `_modAt` merge protects unpushed local edits, strips samples once real cloud data exists, and gates seed-push to a genuinely-empty cloud. `renderAll()` is preserved at the end (UI/UX and other concerns hook the same callback — append after merge, before renderAll).

---

## PART 2 — REP IDENTITY (apply before claim/activity so attribution is canonical)

### Step 9 — Add canonical identity layer
Location: USER SESSION block, immediately after CONSULTANTS/CEOS, ~line 1139. Keep this as ONE contiguous insertion (functions are mutually referenced via hoisting).

FIND:
```
const CONSULTANTS = ['Muneeb Moiz', 'Yousuf Zacky', 'Ameer Munj'];
const CEOS = ['Melusi Ndoro', 'Joshua Khalili', 'Ayoub Rasol'];
```
REPLACE:
```
const CONSULTANTS = ['Muneeb Moiz', 'Yousuf Zacky', 'Ameer Munj'];
const CEOS = ['Melusi Ndoro', 'Joshua Khalili', 'Ayoub Rasol'];
// Canonical roster of known reps. Custom reps added via the login picker are
// persisted here so future logins pick the exact same spelling (no duplicates).
function getCustomReps() {
  try { const r = JSON.parse(localStorage.getItem('crescendo-custom-reps') || '[]'); return Array.isArray(r) ? r : []; }
  catch (_) { return []; }
}
function addCustomRep(name) {
  const clean = String(name || '').trim();
  if (!clean) return;
  const reps = getCustomReps();
  // Skip if it already exists (canonically) anywhere in the roster.
  if (resolveRepName(clean) !== clean) return;
  if (!reps.some(r => r.toLowerCase() === clean.toLowerCase())) {
    reps.push(clean);
    try { localStorage.setItem('crescendo-custom-reps', JSON.stringify(reps)); } catch (_) {}
  }
}
// Full ordered list of selectable identities (roster + persisted custom reps, de-duped).
function getKnownReps() {
  const all = [...CEOS, ...CONSULTANTS, ...getCustomReps()];
  const seen = new Set();
  return all.filter(n => { const k = n.toLowerCase(); if (seen.has(k)) return false; seen.add(k); return true; });
}
// Collapse a free-typed name onto its existing canonical spelling if one exists
// (case/whitespace-insensitive). Prevents 'ameer' / 'Ameer ' splitting history.
function resolveRepName(name) {
  const clean = String(name || '').replace(/\s+/g, ' ').trim();
  if (!clean) return clean;
  if (clean === 'Master') return 'Master';
  const match = getKnownReps().find(n => n.toLowerCase() === clean.toLowerCase());
  return match || clean;
}
```
Rationale: one identity layer — known list + persistence + name resolver — so typed names collapse to existing spellings and new reps are remembered.

---

### Step 10 — Route `setCurrentUser` through `resolveRepName`
Location: `setCurrentUser`, ~line 1116.

FIND:
```
function setCurrentUser(name) {
  localStorage.setItem('crescendo-crm-user', name);
  const display = document.getElementById('current-user-display');
  if (display) display.textContent = name;
}
```
REPLACE:
```
function setCurrentUser(name) {
  // Always store the canonical spelling so attribution (_modBy/activity.by/etc.) is consistent.
  const canonical = (name === 'Master') ? 'Master' : resolveRepName(name);
  localStorage.setItem('crescendo-crm-user', canonical);
  const display = document.getElementById('current-user-display');
  if (display) display.textContent = canonical;
}
```
Rationale: single choke point — every identity write becomes canonical, so all downstream `_modBy`/`activity.by`/`qualifiedBy` inherit it.

---

### Step 11 — Rebuild login picker from roster on overlay open
Location: `showLoginOverlay`, ~line 1124.

FIND:
```
function showLoginOverlay() {
  const overlay = document.getElementById('login-overlay');
  overlay.classList.remove('hidden');
  document.getElementById('login-team-select').value = '';
```
REPLACE:
```
function rebuildLoginRepOptions() {
  const select = document.getElementById('login-team-select');
  if (!select) return;
  const reps = getKnownReps();
  select.innerHTML =
    '<option value="" disabled selected>Choose your name...</option>' +
    reps.map(n => `<option value="${escapeHtml(n)}">${escapeHtml(n)}</option>`).join('') +
    '<option value="__other__">Add new rep...</option>' +
    '<optgroup label="---"></optgroup>' +
    '<option value="__master__">Master Account</option>';
}
function showLoginOverlay() {
  const overlay = document.getElementById('login-overlay');
  overlay.classList.remove('hidden');
  rebuildLoginRepOptions();
  document.getElementById('login-team-select').value = '';
```
Rationale: picker always reflects live roster + persisted custom reps; never drifts.

---

### Step 12 — Strip hardcoded names from login markup
Location: login overlay `<select id="login-team-select">`, ~lines 719–730.

FIND:
```
      <select id="login-team-select">
        <option value="" disabled selected>Choose your name...</option>
        <option value="Ayoub Rasol">Ayoub Rasol</option>
        <option value="Melusi Ndoro">Melusi Ndoro</option>
        <option value="Joshua Khalili">Joshua Khalili</option>
        <option value="Muneeb Moiz">Muneeb Moiz</option>
        <option value="Yousuf Zacky">Yousuf Zacky</option>
        <option value="Ameer Munj">Ameer Munj</option>
        <option value="__other__">Other...</option>
        <optgroup label="---"></optgroup>
        <option value="__master__">Master Account</option>
      </select>
```
REPLACE:
```
      <select id="login-team-select">
        <option value="" disabled selected>Choose your name...</option>
        <!-- Options are rebuilt from the canonical roster by rebuildLoginRepOptions() on overlay open. -->
        <option value="__other__">Add new rep...</option>
        <optgroup label="---"></optgroup>
        <option value="__master__">Master Account</option>
      </select>
```
Rationale: names are now generated; markup is the single source only for placeholder/`__other__`/`__master__`.

---

### Step 13 — Canonicalize + persist on login
Location: `login-btn` click handler, ~lines 4274–4280.

FIND:
```
  } else if (select.value === '__other__') {
    name = document.getElementById('login-custom-input').value.trim();
  } else {
    name = select.value;
  }
  if (!name) return;
  setCurrentUser(name);
```
REPLACE:
```
  } else if (select.value === '__other__') {
    // Canonicalize: collapse onto an existing rep if the typed name already exists.
    name = resolveRepName(document.getElementById('login-custom-input').value);
    if (!name) return;
    // Remember genuinely-new reps so they appear in the picker next time.
    addCustomRep(name);
  } else {
    name = select.value;
  }
  if (!name) return;
  setCurrentUser(name);
```
Rationale: the only duplicate-creation path is now canonicalized and persisted ('ameer' → 'Ameer Munj').

---

### Step 14 — Rebuild picker on fresh (not-logged-in) load
Location: `init()`, ~lines 5816–5821. Resolves identity-spec RISK: the overlay is shown by default (not via `showLoginOverlay()`), so without this the dropdown shows no reps on first load.

FIND:
```
function init() {
  // Check if user is already logged in
  if (isLoggedIn()) {
    const user = getCurrentUser();
    document.getElementById('current-user-display').textContent = user;
    hideLoginOverlay();
  }
```
REPLACE:
```
function init() {
  // Check if user is already logged in
  if (isLoggedIn()) {
    const user = getCurrentUser();
    document.getElementById('current-user-display').textContent = user;
    hideLoginOverlay();
  } else if (typeof rebuildLoginRepOptions === 'function') {
    // Not logged in: the overlay is visible by default — populate the rep picker now.
    rebuildLoginRepOptions();
  }
```
Rationale: ensures the data-driven picker is populated even on the default-visible overlay path.

---

## PART 3 — CLAIM/LOCK + ACTIVITY HELPERS (merged single insertion after addActivity)

### Step 15 — Insert claim helpers + call-tracking helpers after `addActivity`
Location: immediately after `addActivity` (~line 1175). **MERGED** from the claim spec and the activity-tracking spec into one contiguous insertion (both anchored the same spot). `addActivity` itself is unchanged; both blocks append after it.

FIND:
```
function addActivity(lead, action) {
  if (!lead.activity) lead.activity = [];
  lead.activity.unshift({ action, by: getCurrentUser(), date: new Date().toISOString() });
}
```
REPLACE:
```
function addActivity(lead, action) {
  if (!lead.activity) lead.activity = [];
  lead.activity.unshift({ action, by: getCurrentUser(), date: new Date().toISOString() });
}
// ===== LEAD CLAIM / DOUBLE-CALL PREVENTION =====
// A claim is "active" for CLAIM_TTL_MS after activeCallAt; after that it is stale
// (crashed tab / rep moved on) and no longer blocks others.
const CLAIM_TTL_MS = 15 * 60 * 1000;
function isClaimActive(lead) {
  if (!lead || !lead.activeCallAt) return false;
  return (Date.now() - new Date(lead.activeCallAt).getTime()) < CLAIM_TTL_MS;
}
// Who (if anyone) other than the current user is actively on this lead right now.
function claimedByOther(lead) {
  if (!isClaimActive(lead)) return null;
  if (lead.activeCallBy && lead.activeCallBy !== getCurrentUser()) return lead.activeCallBy;
  return null;
}
// Mark the current user as actively working/calling this lead and sync immediately.
function claimLead(lead) {
  if (!lead) return;
  const me = getCurrentUser();
  lead.claimedBy = me;
  lead.claimedAt = new Date().toISOString();
  lead.activeCallBy = me;
  lead.activeCallAt = new Date().toISOString();
  addActivity(lead, 'started working this lead');
  saveState(); // persists locally AND pushes via CrescendoSync.pushLeads
}
// Release the active-call flag (rep finished). Keeps claimedBy for attribution.
function releaseLead(lead) {
  if (!lead) return;
  if (lead.activeCallBy === getCurrentUser()) {
    lead.activeCallBy = null;
    lead.activeCallAt = null;
    saveState();
  }
}
// Visible badge for the lead lists/cards/panel. Empty string if free / mine.
function renderClaimBadge(lead) {
  const other = claimedByOther(lead);
  if (other) {
    return '<div class="claim-badge live"><span class="live-dot"></span> ' + escapeHtml(other) + ' is on this</div>';
  }
  // Stale prior claim by someone else — soft "last touched" hint, non-blocking.
  if (lead && lead.claimedBy && lead.claimedBy !== getCurrentUser() && !isClaimActive(lead)) {
    return '<div class="claim-badge"><i data-lucide="hand" aria-hidden="true"></i> Last claimed by ' + escapeHtml(lead.claimedBy) + '</div>';
  }
  return '';
}
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
// ===== CALL OUTCOME LOGGING (synced activity + last-contact stamp) =====
const CALL_OUTCOMES = [
  { value: 'connected', label: 'Connected – spoke to contact' },
  { value: 'gatekeeper', label: 'Reached gatekeeper' },
  { value: 'voicemail', label: 'Left voicemail' },
  { value: 'no_answer', label: 'No answer' },
  { value: 'callback', label: 'Asked to call back' },
  { value: 'wrong_number', label: 'Wrong / dead number' },
  { value: 'not_interested', label: 'Not interested' }
];
function callOutcomeLabel(v) { return (CALL_OUTCOMES.find(o => o.value === v) || {}).label || v; }
// Logs a call attempt + its disposition as a synced activity entry and stamps last-contact.
function logCall(id, outcome) {
  const lead = getLeadById(id);
  if (!lead || !outcome) return;
  if (!lead.crm) lead.crm = {};
  lead.crm.dateLastContact = todayISO;
  if (!lead.crm.dateFirstContact) lead.crm.dateFirstContact = todayISO;
  addActivity(lead, 'logged call (' + callOutcomeLabel(outcome) + ')');
  // Calling is the most important rep action — also release the active-call lock.
  if (typeof releaseLead === 'function') releaseLead(lead);
  saveState();
}
```
Rationale: claim/lock logic (15-min TTL), dialer launcher, and call-outcome logging — all routed through `saveState`/`pushLeads` so they sync live. Activity entries (`'started working this lead'`, `'logged call (...)'`) flow through the single `addActivity` schema `{action, by, date}`. `logCall` releases the lock so a claimed lead doesn't stay "live" after the call is logged (de-conflicts claim + activity ownership of the same lead).

---

## PART 4 — CALL-LOGGER RENDERER

### Step 16 — Define `renderCallLogger` before RESEARCH_ITEMS
Location: just before `const RESEARCH_ITEMS = [`, ~line 2664.

FIND:
```
const RESEARCH_ITEMS = [
```
REPLACE:
```
function renderCallLogger(lead) {
  const primaryPhone = (lead.phones && lead.phones[0] && lead.phones[0].number) || (lead.contacts && (lead.contacts.find(c => c.phone) || {}).phone) || '';
  return `
    <div class="call-logger">
      <div class="call-logger-head">
        <i data-lucide="phone" aria-hidden="true"></i>
        <span>Log a call</span>
        ${primaryPhone ? `<a class="call-dial-link" href="tel:${escapeHtml(primaryPhone.replace(/\s+/g,''))}">${escapeHtml(primaryPhone)}</a>` : '<span class="call-no-phone">No phone on file</span>'}
      </div>
      <select class="form-select call-outcome-select" data-action="log-call" data-id="${lead.id}" aria-label="Log call outcome">
        <option value="" selected>Record call outcome…</option>
        ${CALL_OUTCOMES.map(o => `<option value="${o.value}">${o.label}</option>`).join('')}
      </select>
    </div>

const RESEARCH_ITEMS = [
```
Rationale: the Log-Call UI (dial link + mandatory outcome dropdown) reusing existing form-select styling.
**Verify after paste:** the inserted block must end with a backtick + `;` closing `renderCallLogger`'s return — paste exactly as shown (template literal closes right before the blank line, then `const RESEARCH_ITEMS`). The function closes with `}` after the return. Ensure the final line of the template (`</div>`) is followed by the closing backtick. (The block above intentionally renders as: return-template ... `</div>` closing backtick `;` then `}` then blank line then `const RESEARCH_ITEMS`.) If your editor shows an unterminated template, re-check the closing backtick.

> NOTE TO IMPLEMENTER: use this exact corrected closing to avoid a syntax error — the return template must be terminated. Replace the Step 16 REPLACE body's tail
> `    </div>` / blank / `const RESEARCH_ITEMS = [`
> with:
> ```
>     </div>`;
> }
>
> const RESEARCH_ITEMS = [
> ```

---

## PART 5 — RENDER TEMPLATE MERGES (claim + activity + UI/UX share these blocks)

### Step 17 — Lead-bank card: ownership clarity (E) + claim badge + Call button (claim)
Location: renderLeadBank card body, ~lines 2148–2152. **MERGED** (UI/UX E rewrites the assigned-badge; claim spec adds badge + Call button).

FIND:
```
          ${l.assignedTo ? `<div class="assigned-badge"><i data-lucide="user" aria-hidden="true"></i> Assigned: ${escapeHtml(l.assignedTo)}</div>` : ''}
          ${renderAttribution(l)}
          ${renderLastActivity(l)}
          <div class="lead-card-actions">
            <button class="btn btn-ghost btn-sm" data-action="view-lead" data-id="${l.id}"><i data-lucide="eye" aria-hidden="true"></i> View</button>
```
REPLACE:
```
          ${l.assignedTo ? `<div class="assigned-badge"><i data-lucide="user" aria-hidden="true"></i> ${escapeHtml(l.assignedTo) === getCurrentUser() ? 'You' : 'Assigned: ' + escapeHtml(l.assignedTo)}</div>` : '<div class="assigned-badge" style="color:var(--color-warning);"><i data-lucide="user-plus" aria-hidden="true"></i> Unclaimed</div>'}
          ${renderClaimBadge(l)}
          ${renderAttribution(l)}
          ${renderLastActivity(l)}
          <div class="lead-card-actions">
            <button class="btn btn-ghost btn-sm" data-action="view-lead" data-id="${l.id}"><i data-lucide="eye" aria-hidden="true"></i> View</button>
            ${(l.phones && l.phones.length) ? `<button class="btn btn-sm" style="background:var(--color-primary);color:white" data-action="call-lead" data-id="${l.id}"><i data-lucide="phone" aria-hidden="true"></i> Call</button>` : ''}
```
Rationale: shows "You"/"Unclaimed" ownership, the live-claim badge, and a claim-then-dial Call button all in the lead-bank card.

---

### Step 18 — Lead-bank filter bar: "Mine" quick-chip (E)
Location: renderLeadBank filter bar, ~line 2078.

FIND:
```
      <button class="today-chip${f.today ? ' active' : ''}" data-action="toggle-today-filter" data-scope="lead-bank" aria-pressed="${!!f.today}"><i data-lucide="calendar-clock" aria-hidden="true"></i> Today</button>
      <select class="form-select" data-filter="lb-sort" aria-label="Sort leads">
```
REPLACE:
```
      <button class="today-chip${f.assignedTo === getCurrentUser() ? ' active' : ''}" data-filter="lb-mine" aria-pressed="${f.assignedTo === getCurrentUser()}"><i data-lucide="user-check" aria-hidden="true"></i> Mine</button>
      <button class="today-chip${f.today ? ' active' : ''}" data-action="toggle-today-filter" data-scope="lead-bank" aria-pressed="${!!f.today}"><i data-lucide="calendar-clock" aria-hidden="true"></i> Today</button>
      <select class="form-select" data-filter="lb-sort" aria-label="Sort leads">
```
Rationale: one-click "Mine" chip scopes the lead bank to the current rep.

---

### Step 19 — Qualified-leads card: claim badge + Call button
Location: renderQualifiedLeads card actions, ~lines 2404–2407.

FIND:
```
          ${renderAttribution(l)}
          ${renderLastActivity(l)}
          <div class="lead-card-actions">
            <button class="btn btn-ghost btn-sm" data-action="view-qual" data-id="${l.id}"><i data-lucide="eye" aria-hidden="true"></i> View Full</button>
```
REPLACE:
```
          ${renderAttribution(l)}
          ${renderClaimBadge(l)}
          ${renderLastActivity(l)}
          <div class="lead-card-actions">
            ${(l.phones && l.phones.length) ? `<button class="btn btn-sm" style="background:var(--color-primary);color:white" data-action="call-lead" data-id="${l.id}"><i data-lucide="phone" aria-hidden="true"></i> Call</button>` : ''}
            <button class="btn btn-ghost btn-sm" data-action="view-qual" data-id="${l.id}"><i data-lucide="eye" aria-hidden="true"></i> View Full</button>
```
Rationale: live-claim badge + claim-then-dial Call on qualified cards. (Original claim spec omitted the Call button here; added for parity since these cards have phones.)

---

### Step 20 — CRM row: call-logger (activity) + claim badge + Call button (claim)
Location: renderCRMList row, ~lines 2648–2652. **MERGED** (activity adds `renderCallLogger`; claim adds badge + Call button).

FIND:
```
        ${renderResearchChecklist(l)}
        ${renderAttribution(l)}
        ${renderLastActivity(l)}
        <div class="crm-actions">
          <button class="btn btn-ghost btn-sm btn-generate-email" data-action="generate-email" data-id="${l.id}"><i data-lucide="mail" aria-hidden="true"></i> Generate Email</button>
```
REPLACE:
```
        ${renderResearchChecklist(l)}
        ${renderCallLogger(l)}
        ${renderAttribution(l)}
        ${renderClaimBadge(l)}
        ${renderLastActivity(l)}
        <div class="crm-actions">
          ${(l.phones && l.phones.length) ? `<button class="btn btn-sm" style="background:var(--color-primary);color:white" data-action="call-lead" data-id="${l.id}"><i data-lucide="phone" aria-hidden="true"></i> Call</button>` : ''}
          <button class="btn btn-ghost btn-sm btn-generate-email" data-action="generate-email" data-id="${l.id}"><i data-lucide="mail" aria-hidden="true"></i> Generate Email</button>
```
Rationale: combines the mandatory call-outcome logger, the live-claim badge, and the claim-then-dial Call button in the CRM pipeline rows where most calling happens.

---

### Step 21 — View-lead panel phone block: claim badge + tel: links + Log-call button
Location: renderViewLeadPanel phone block, ~line 2249. **MERGED** (claim spec adds badge + a Call button; UI/UX E converts phones to tel: links + per-number Log-call buttons). Final keeps claim badge above, and per-number tap-to-dial + Log-call.

FIND:
```
    ${lead.phones.length ? `<div class="form-group"><span class="form-label">Phone Numbers</span>${lead.phones.map(p => `<span style="font-size:var(--text-sm);">${escapeHtml(p.number)}</span>`).join('')}</div>` : ''}
```
REPLACE:
```
    ${renderClaimBadge(lead)}
    ${lead.phones.length ? `<div class="form-group"><span class="form-label">Phone Numbers</span>${lead.phones.map(p => `<div style="display:flex;align-items:center;gap:var(--space-2);margin-bottom:var(--space-1);"><a href="tel:${escapeHtml(p.number.replace(/[^+0-9]/g,''))}" style="font-size:var(--text-sm);color:var(--color-primary);text-decoration:underline;text-underline-offset:2px;"><i data-lucide="phone" style="width:13px;height:13px;vertical-align:-2px;margin-right:3px;" aria-hidden="true"></i>${escapeHtml(p.number)}</a><button class="btn btn-ghost btn-sm" style="min-height:26px;padding:2px var(--space-2);font-size:var(--text-xs);" data-action="log-call" data-id="${lead.id}" data-num="${escapeHtml(p.number)}"><i data-lucide="phone-call" style="width:12px;height:12px;" aria-hidden="true"></i> Log call</button></div>`).join('')}</div>` : ''}
```
Rationale: detail panel now shows who is live on the lead (claim badge), tap-to-dial links, and a per-number quick Log-call. (The panel's `log-call` uses the lightweight "logged a call to <num>" activity path wired in Step 26 — distinct from the CRM dropdown's `logCall(id, outcome)`.)

---

## PART 6 — EVENT DISPATCHER WIRING

### Step 22 — Lead-bank click handler: wire `call-lead`
Location: section-lead-bank click handler, ~line 3656.

FIND:
```
  if (action === 'open-add-lead') openPanel('add-lead');
  else if (action === 'view-lead') openPanel('view-lead', getLeadById(id));
```
REPLACE:
```
  if (action === 'open-add-lead') openPanel('add-lead');
  else if (action === 'call-lead') openDialer(id);
  else if (action === 'view-lead') openPanel('view-lead', getLeadById(id));
```
Rationale: wires the lead-bank Call button to the claim/dial flow.

---

### Step 23 — Lead-bank "Mine" chip toggle (E): separate click listener
Location: after the section-lead-bank `change` handler, ~line 3704.

FIND:
```
  if (f === 'lb-show-all') { state.filters.leadBank.assignedTo = e.target.checked ? 'all' : getCurrentUser(); saveState(); renderLeadBank(); }
});
```
REPLACE:
```
  if (f === 'lb-show-all') { state.filters.leadBank.assignedTo = e.target.checked ? 'all' : getCurrentUser(); saveState(); renderLeadBank(); }
});
document.getElementById('section-lead-bank').addEventListener('click', e => {
  const chip = e.target.closest('[data-filter="lb-mine"]');
  if (!chip) return;
  state.filters.leadBank.assignedTo = (state.filters.leadBank.assignedTo === getCurrentUser()) ? 'all' : getCurrentUser();
  saveState();
  renderLeadBank();
});
```
Rationale: toggles the "Mine" chip via a separate listener so it doesn't disturb the existing lead-bank click handler.

---

### Step 24 — Qualified-leads click handler: wire `call-lead`
Location: section-qualified-leads click handler, ~line 3713.

FIND:
```
  if (action === 'qualify') openModal('qualify', getLeadById(id));
  else if (action === 'move-to-crm') {
    moveToCRM(id);
    showToast('Lead moved to CRM', 'success');
    renderAll();
  } else if (action === 'view-qual') {
```
REPLACE:
```
  if (action === 'qualify') openModal('qualify', getLeadById(id));
  else if (action === 'call-lead') openDialer(id);
  else if (action === 'move-to-crm') {
    moveToCRM(id);
    showToast('Lead moved to CRM', 'success');
    renderAll();
  } else if (action === 'view-qual') {
```
Rationale: wires the qualified-leads Call button to the claim/dial flow.

---

### Step 25 — CRM click handler: wire `call-lead`
Location: section-crm click handler first branch, ~line 3730.

FIND:
```
  if (action === 'generate-email') {
    const lead = getLeadById(id);
    if (lead) openModal('email', lead);
    return;
  } else if (action === 'crm-view') {
```
REPLACE:
```
  if (action === 'call-lead') { openDialer(id); return; }
  if (action === 'generate-email') {
    const lead = getLeadById(id);
    if (lead) openModal('email', lead);
    return;
  } else if (action === 'crm-view') {
```
Rationale: wires the CRM-row Call button to the claim/dial flow.

---

### Step 26 — Side-panel click handler: wire `call-lead` (claim) + `log-call` (E)
Location: side-panel click handler, ~lines 4110–4111. **MERGED** (claim's `call-lead` + UI/UX E's `log-call`). Both use the already-computed `target`.

FIND:
```
  if (action === 'close-panel') closePanel();
  else if (action === 'add-phone') addDynamicItem('phones-list', 'phone');
```
REPLACE:
```
  if (action === 'close-panel') closePanel();
  else if (action === 'call-lead') openDialer(target.dataset.id);
  else if (action === 'log-call') {
    const lead = getLeadById(target.dataset.id);
    if (lead) {
      const num = target.dataset.num || '';
      addActivity(lead, 'logged a call' + (num ? ' to ' + num : ''));
      if (typeof releaseLead === 'function') releaseLead(lead);
      saveState();
      renderAll();
      showToast('Call logged on ' + lead.businessName, 'success');
    }
  }
  else if (action === 'add-phone') addDynamicItem('phones-list', 'phone');
```
Rationale: routes the panel's Call (claim/dial) and per-number Log-call (synced activity) buttons through the existing `#side-panel` listener without disturbing other panel actions. (Replaces the claim spec's separate pre-handler `closest` shim — folded into the existing if/else chain using `target`.)

---

### Step 27 — CRM change handler: log-call dropdown (activity) + early return
Location: section-crm `change` listener head, ~lines 3805–3811. The bulk-clear block precedes the change listener; insert the log-call branch at the top of the change listener.

FIND:
```
  } else if (action === 'bulk-clear') {
    state.bulkSelection = [];
    state.bulkScope = null;
    renderCRM();
  }
});
document.getElementById('section-crm').addEventListener('change', e => {
  const action = e.target.dataset.action;
  const id = e.target.dataset.id;
  const f = e.target.dataset.filter;
```
REPLACE:
```
  } else if (action === 'bulk-clear') {
    state.bulkSelection = [];
    state.bulkScope = null;
    renderCRM();
  }
});
document.getElementById('section-crm').addEventListener('change', e => {
  if (e.target.dataset.action === 'log-call') {
    const outcome = e.target.value;
    if (outcome) {
      logCall(e.target.dataset.id, outcome);
      showToast('Call logged: ' + callOutcomeLabel(outcome), 'success');
      renderCRM();
    }
    return;
  }
  const action = e.target.dataset.action;
  const id = e.target.dataset.id;
  const f = e.target.dataset.filter;
```
Rationale: wires the CRM call-outcome dropdown into the existing change-delegation; early-return avoids falling through to filter handlers.

---

### Step 28 — CRM toggle-meeting + change-disposition: log activity
Location: two adjacent activity-spec edits in the CRM handlers.

**28a — toggle-meeting** (~line 3756, inside the click handler):
FIND:
```
      lead.crm.meetingBooked = !lead.crm.meetingBooked;
      if (lead.crm.meetingBooked && !lead.crm.meetingDate) {
        lead.crm.meetingDate = dateTimeFromNow(7, 10, 0);
      }
      saveState();
```
REPLACE:
```
      lead.crm.meetingBooked = !lead.crm.meetingBooked;
      if (lead.crm.meetingBooked && !lead.crm.meetingDate) {
        lead.crm.meetingDate = dateTimeFromNow(7, 10, 0);
      }
      addActivity(lead, lead.crm.meetingBooked ? 'booked a meeting' : 'cancelled meeting');
      saveState();
```

**28b — change-disposition** (~line 3847, inside the change handler):
FIND:
```
      const newDisp = e.target.value;
      if (newDisp === 'not_interested' || newDisp === 'archived') {
        openOutcomeReasonModal(id, newDisp);
      } else {
        lead.crm.disposition = newDisp;
        saveState();
      }
```
REPLACE:
```
      const newDisp = e.target.value;
      if (newDisp === 'not_interested' || newDisp === 'archived') {
        openOutcomeReasonModal(id, newDisp);
      } else {
        lead.crm.disposition = newDisp;
        addActivity(lead, 'set disposition to ' + getDispositionLabel(newDisp));
        saveState();
      }
```
Rationale: meeting toggles and disposition changes were mutating state silently; now each writes a synced, master-visible activity entry.

---

## PART 7 — ACTIVITY MONITOR (master visibility)

### Step 29 — Activity Monitor fixes (bug fix + call/disposition/meeting support, badges, KPIs)
Apply all sub-edits below.

**29a — feed lead-name bug** (~line 4314):
FIND:
```
      activities.push({ ...a, leadName: lead.name, leadId: lead.id, leadStatus: lead.status });
```
REPLACE:
```
      activities.push({ ...a, leadName: lead.businessName, leadId: lead.id, leadStatus: lead.status });
```

**29b — action-type filters** (~line 4299):
FIND:
```
const AM_ACTION_TYPES = [
  { value: 'all', label: 'All Actions' },
  { value: 'qualified', label: 'Qualified' },
  { value: 'moved to CRM', label: 'Moved to CRM' },
  { value: 'note', label: 'Note Added' },
  { value: 'stage', label: 'Stage Changed' },
  { value: 'archived', label: 'Archived' },
  { value: 'reactivated', label: 'Reactivated' }
];
```
REPLACE:
```
const AM_ACTION_TYPES = [
  { value: 'all', label: 'All Actions' },
  { value: 'call', label: 'Calls' },
  { value: 'qualified', label: 'Qualified' },
  { value: 'moved to CRM', label: 'Moved to CRM' },
  { value: 'note', label: 'Note Added' },
  { value: 'disposition', label: 'Disposition' },
  { value: 'meeting', label: 'Meeting' },
  { value: 'stage', label: 'Stage Changed' },
  { value: 'archived', label: 'Archived' },
  { value: 'reactivated', label: 'Reactivated' }
];
```

**29c — describeAction** (~line 4338):
FIND:
```
function describeAction(action) {
  const a = action.toLowerCase();
  if (a.includes('qualified')) return 'qualified';
```
REPLACE:
```
function describeAction(action) {
  const a = action.toLowerCase();
  if (a.includes('logged call') || a.includes('logged a call') || a.startsWith('called')) return action;
  if (a.includes('disposition')) return action;
  if (a.includes('meeting')) return action;
  if (a.includes('started working')) return action;
  if (a.includes('qualified')) return 'qualified';
```

**29d — matchesActionFilter** (~line 4352):
FIND:
```
  switch (filter) {
    case 'qualified': return a.includes('qualified');
    case 'moved to CRM': return a.includes('moved to crm') || a.includes('crm');
    case 'note': return a.includes('note');
```
REPLACE:
```
  switch (filter) {
    case 'call': return a.includes('logged call') || a.includes('logged a call') || a.startsWith('called');
    case 'disposition': return a.includes('disposition');
    case 'meeting': return a.includes('meeting');
    case 'qualified': return a.includes('qualified');
    case 'moved to CRM': return (a.includes('moved to crm') || a.includes('crm')) && !a.includes('logged call');
    case 'note': return a.includes('note');
```

**29e — getActionBadgeClass** (~line 4363):
FIND:
```
function getActionBadgeClass(action) {
  const a = action.toLowerCase();
  if (a.includes('qualified')) return 'badge-teal';
  if (a.includes('crm')) return 'badge-blue';
```
REPLACE:
```
function getActionBadgeClass(action) {
  const a = action.toLowerCase();
  if (a.includes('logged call') || a.includes('logged a call') || a.startsWith('called')) return 'badge-orange';
  if (a.includes('meeting')) return 'badge-purple';
  if (a.includes('disposition')) return 'badge-blue';
  if (a.includes('qualified')) return 'badge-teal';
  if (a.includes('crm')) return 'badge-blue';
```

**29f — calls-today stats** (~line 4408):
FIND:
```
  // Stats
  const totalActions = allActivities.length;
  const actionsToday = allActivities.filter(a => new Date(a.date) >= startOfToday).length;
```
REPLACE:
```
  // Stats
  const totalActions = allActivities.length;
  const actionsToday = allActivities.filter(a => new Date(a.date) >= startOfToday).length;
  const isCall = (a) => { const t = a.action.toLowerCase(); return t.includes('logged call') || t.includes('logged a call') || t.startsWith('called'); };
  const callsToday = allActivities.filter(a => isCall(a) && new Date(a.date) >= startOfToday).length;
  const callsTodayByUser = {};
  allActivities.forEach(a => { if (isCall(a) && new Date(a.date) >= startOfToday) callsTodayByUser[a.by] = (callsTodayByUser[a.by] || 0) + 1; });
```

**29g — per-user breakdown row** (~line 4450):
FIND:
```
    breakdownHTML += `
      <div class="am-user-row">
        <div class="am-user-name">${escapeHtml(user)}</div>
        <div class="am-user-bar-wrap"><div class="am-user-bar" style="width:${pct}%"></div></div>
        <div class="am-user-count">${count}</div>
      </div>`;
```
REPLACE:
```
    const callsTodayCount = callsTodayByUser[user] || 0;
    breakdownHTML += `
      <div class="am-user-row">
        <div class="am-user-name">${escapeHtml(user)}</div>
        <div class="am-user-bar-wrap"><div class="am-user-bar" style="width:${pct}%"></div></div>
        <div class="am-user-count">${count}</div>
        <div class="am-user-calls" title="Calls logged today">${callsTodayCount} 📞</div>
      </div>`;
```
> Renamed the local to `callsTodayCount` to avoid shadowing the outer `callsToday` declared in 29f.

**29h — Calls Today KPI card** (~line 4469):
FIND:
```
      <div class="am-stat-card">
        <div class="am-stat-label">Actions Today</div>
        <div class="am-stat-value">${actionsToday}</div>
      </div>
```
REPLACE:
```
      <div class="am-stat-card">
        <div class="am-stat-label">Actions Today</div>
        <div class="am-stat-value">${actionsToday}</div>
      </div>
      <div class="am-stat-card">
        <div class="am-stat-label">Calls Today</div>
        <div class="am-stat-value">${callsToday}</div>
      </div>
```
Rationale: fixes the blank-lead feed bug; adds calls/disposition/meeting filters, badges, a Calls Today KPI, and a per-rep calls column so the owner can see who is actually dialling.

---

## PART 8 — UI/UX POLISH (sync chip, nav tooltip, CSS)

### Step 30 — Sync chip names the rep + tooltips (E)
Location: `showSyncStatus`, ~lines 1090 and 1094–1106. Two sub-edits.

**30a — enable hover** (~line 1090):
FIND:
```
      el.style.cssText = 'position:fixed;bottom:12px;right:12px;padding:6px 10px;border-radius:6px;font:500 12px system-ui,sans-serif;z-index:9999;pointer-events:none;opacity:0.85;';
```
REPLACE:
```
      el.style.cssText = 'position:fixed;bottom:12px;right:12px;padding:6px 10px;border-radius:6px;font:500 12px system-ui,sans-serif;z-index:9999;pointer-events:auto;opacity:0.9;cursor:default;';
```

**30b — status text + titles** (~lines 1094–1106):
FIND:
```
    if (kind === 'connected') {
      el.textContent = '● Synced';
      el.style.background = '#e6f7ec';
      el.style.color = '#1a7a3a';
    } else if (kind === 'error') {
      el.textContent = '● Sync error' + (msg ? ': ' + msg : '');
      el.style.background = '#fdecea';
      el.style.color = '#a12622';
    } else {
      el.textContent = '● Offline (local only)';
      el.style.background = '#f1f2f4';
      el.style.color = '#555';
    }
```
REPLACE:
```
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
Rationale: names the signed-in rep so the indicator is trustworthy; hover tooltips clarify each state. (No conflict with Part 1 — sync concern A does not edit `showSyncStatus`.)

---

### Step 31 — CRM nav badge tooltip (E)
Location: `renderSidebarBadges` CRM badge, ~lines 1831–1838.

FIND:
```
  const crmBadge = document.getElementById('badge-crm');
  if (overdueInCRM > 0) {
    crmBadge.textContent = crmCount;
    crmBadge.className = 'nav-badge nav-badge-warning';
  } else {
    crmBadge.textContent = crmCount;
    crmBadge.className = 'nav-badge nav-badge-teal';
  }
```
REPLACE:
```
  const crmBadge = document.getElementById('badge-crm');
  if (overdueInCRM > 0) {
    crmBadge.textContent = crmCount;
    crmBadge.className = 'nav-badge nav-badge-warning';
    crmBadge.title = overdueInCRM + ' overdue follow-up' + (overdueInCRM !== 1 ? 's' : '');
  } else {
    crmBadge.textContent = crmCount;
    crmBadge.className = 'nav-badge nav-badge-teal';
    crmBadge.title = crmCount + ' lead' + (crmCount !== 1 ? 's' : '') + ' in CRM';
  }
```
Rationale: hover tooltip explains the warning-coloured CRM badge.

---

### Step 32 — CSS: claim badge styles
Location: after `.assigned-badge i` rule, ~line 287.

FIND:
```
.assigned-badge i { width: 10px; height: 10px; }
.reassign-select
```
REPLACE:
```
.assigned-badge i { width: 10px; height: 10px; }
.claim-badge { display: inline-flex; align-items: center; gap: 4px; font-size: 0.65rem; font-weight: 600; color: var(--color-warning); background: var(--color-warning-highlight); border-radius: var(--radius-sm); padding: 2px 8px; margin-top: 4px; }
.claim-badge.live { color: var(--color-error); background: var(--color-error-highlight); }
.claim-badge i { width: 10px; height: 10px; }
.claim-badge .live-dot { width: 6px; height: 6px; border-radius: 50%; background: currentColor; animation: claimPulse 1.4s ease-in-out infinite; }
@keyframes claimPulse { 0%,100% { opacity: 1; } 50% { opacity: 0.25; } }
.reassign-select
```
Rationale: claim/active-call badge styling reusing warning/error tokens.
> If `--color-warning-highlight` / `--color-error-highlight` are not defined in `:root`, substitute existing highlight tokens (e.g. a faint `oklch(from var(--color-warning) l c h / 0.12)`); verify against the token list before pasting.

---

### Step 33 — CSS: call-logger + per-rep calls column styles
Location: after `.am-empty` rule, ~line 191.

FIND:
```
.am-empty { text-align: center; padding: var(--space-10); color: var(--color-text-faint); font-size: var(--text-sm); }
```
REPLACE:
```
.am-empty { text-align: center; padding: var(--space-10); color: var(--color-text-faint); font-size: var(--text-sm); }
.am-user-calls { font-size: var(--text-xs); font-weight: 600; color: var(--color-text-muted); min-width: 52px; text-align: right; }
.call-logger { margin-top: var(--space-3); padding: var(--space-3); background: var(--color-surface-2); border: 1px solid var(--color-border); border-radius: var(--radius-md); }
.call-logger-head { display: flex; align-items: center; gap: var(--space-2); font-size: var(--text-xs); font-weight: 600; color: var(--color-text-muted); margin-bottom: var(--space-2); }
.call-logger-head i { width: 14px; height: 14px; }
.call-dial-link { margin-left: auto; color: var(--color-primary); font-weight: 600; text-decoration: none; }
.call-dial-link:hover { text-decoration: underline; }
.call-no-phone { margin-left: auto; color: var(--color-text-faint); font-weight: 400; }
.call-outcome-select { width: 100%; font-size: var(--text-xs); }
```
Rationale: styles the Log-Call block and per-rep calls column with existing surface/border tokens.
> Verify `--color-surface-2` / `--color-border` exist; if not, substitute `--color-surface-offset` and an existing border token.

---

## PART 9 — FIRESTORE SECURITY RULES

### Step 34 — Harden `firestore.rules`
Location: `/Users/theshumba/Documents/GitHub/crescendo-crm/firestore.rules` (entire file).

FIND:
```
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    // Any signed-in user (we use anonymous auth) can read/write leads.
    match /leads/{leadId} {
      allow read, write: if request.auth != null;
    }
  }
}
```
REPLACE:
```
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {

    // Crescendo CRM uses anonymous auth, so every teammate is just
    // "some signed-in anonymous user". We CANNOT enforce per-rep ownership
    // here (there is no stable per-rep identity), but we CAN:
    //   1. require an authenticated session (no fully public access),
    //   2. validate the document SHAPE on writes (reject junk / wrong-collection writes),
    //   3. BLOCK client-side deletes — the app's pushLeads() can mass-delete
    //      docs when a rep reconnects with stale/empty local state. Closing deletes is
    //      the single biggest protection for the real leads.
    //   4. lock everything outside the /leads collection.

    function signedIn() {
      return request.auth != null;
    }

    // A well-formed lead doc, as written by pushLeads():
    //   { id, businessName, status, ... , _modBy, _modAt }
    function isLead(data) {
      return data.keys().hasAll(['id', 'businessName', 'status'])
          && data.id is string
          && data.businessName is string
          && data.status in ['new', 'lead', 'unqualified', 'qualified', 'crm']
          && data.size() < 200; // sane upper bound on field count
    }

    match /leads/{leadId} {
      // Reads: any signed-in (anonymous) teammate. NOTE: this is still the
      // full team's lead list — see deployment notes / residual risk below.
      allow read: if signedIn();

      // Creates & updates must look like a real lead doc.
      allow create: if signedIn() && isLead(request.resource.data);
      allow update: if signedIn() && isLead(request.resource.data);

      // No client deletes. Removing a lead is a deliberate admin action —
      // do it from the Firebase console, or via an authenticated admin tool,
      // not from the auto-sync path. This neutralises the mass-wipe vector.
      allow delete: if false;
    }

    // Deny everything else by default (no other collections exist).
    match /{document=**} {
      allow read, write: if false;
    }
  }
}
```
Rationale: keeps anonymous reads + pushLeads create/update working, validates lead shape, removes the client delete mass-wipe vector, and locks all other collections.
> **Coordination:** Step 4 scopes deletes so normal syncs contain none → no rejected pushes. The only delete path is Step 6 (`deleteLead`); see OPEN QUESTION 1. The `status in [...]` list must be widened if new statuses are added, or those writes will be rejected. **Important:** if the real lead docs use status values beyond `['new','lead','unqualified','qualified','crm']` (e.g. `'archive'`), add them here BEFORE deploying or all archive-status updates will be rejected — verify against actual data first.

---

## Deployment & security

- **Firebase web keys are not secrets.** The exposure is the open read rule + public discoverability, not the apiKey. Correct mitigation order: (1) tighten rules (Step 34); (2) stop publishing the real config to a public indexable URL; do NOT rotate the key (would break the app, doesn't help). Optionally restrict the key to specific HTTP referrers in Google Cloud Console > APIs & Services > Credentials.
- **Keep the public GitHub repo a sanitized template.** Do NOT commit Step 1's real config or any lead export. The public repo must keep `PASTE_YOUR_*` placeholders and `.firebaserc` placeholder.
- **Live deploy (private):** create a separate PRIVATE copy with the real config pasted in. Recommended: Firebase Hosting on the same project — `firebase init hosting`, set `.firebaserc` default to `crescendocrm-5de1b` (or `--project crescendocrm-5de1b`), then `firebase deploy`. This avoids a public GitHub Pages URL.
- **Deploy the rules:** `firebase deploy --only firestore:rules --project crescendocrm-5de1b` (after the status-list verification in Step 34).
- **Residual risk (honest):** with anonymous auth there is no real per-rep identity. Rules cannot restrict a rep to their own leads, cannot prevent one anonymous client from reading all leads, and cannot verify `_modBy` (a self-reported localStorage string). Anyone with the web config can sign in anonymously and READ every lead. Rules only reduce write/delete abuse.

---

## Verification checklist

1. **Connects:** Load the live (private) copy. Console shows `[CrescendoSync] Connected`. Bottom-right chip reads "● Synced as <YourName>" (Step 30) on hover shows the tooltip.
2. **Reads the cloud leads:** After login the lead bank/CRM populate from Firestore (not just the local samples). Sample leads disappear once real cloud data arrives (Step 8 filter).
3. **No data clobber:** Rep A edits a lead note and immediately Rep B's tab receives a snapshot — A's unpushed edit is NOT overwritten (per-lead `_modAt` merge, Step 8). Reload A: edit persists. Confirm the cloud doc count stays stable (no mass-delete) after a rep loads with a short/stale local list.
4. **Seed-push safety:** On a non-empty cloud, no seed-push fires (watch network: no full-collection batch.set on login). On a genuinely empty cloud with real local leads, seed-push runs once after ~1.5s.
5. **Claiming visible across reps:** Rep A clicks Call on a lead → Rep B sees the red pulsing "A is on this" badge on that card within a snapshot cycle (lead-bank, qualified, CRM, and view panel). Opening it as B prompts "A is already calling this — open anyway?". Badge clears after 15 min TTL or when A logs the call (releaseLead).
6. **Activity feed populates:** Master account → Activity Monitor. Feed rows show the correct business name (not blank — Step 29a). Logging a call (CRM dropdown or panel Log-call), changing disposition, toggling a meeting each appear as distinct badged entries; "Calls" / "Disposition" / "Meeting" filters work; "Calls Today" KPI and per-rep 📞 column increment.
7. **Identity picker works:** Logged out → login dropdown lists all roster reps (Step 11/14). Add new rep "test rep" → re-open picker, it persists. Type "ameer" via Add-new-rep → resolves to "Ameer Munj" (no duplicate). Attribution on subsequent writes uses the canonical name.
8. **Rules enforced:** From the live app, a normal edit syncs (create/update pass). A malformed write or a write to another collection is rejected. A client delete is rejected (or, if OPEN QUESTION 1 option (b) chosen, allowed). Verify with Firebase console > Firestore Rules Playground.
