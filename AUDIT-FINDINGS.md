# Crescendo CRM — Audit Findings

**Audit date:** 2026-06-03
**File audited:** `crescendo-crm.html` (single-file app, ~337 KB)
**Team:** Owner (Melusi / "Master"), reps Ameer, Muneeb, Yousuf — phone-first calling team
**Context:** ~540 real leads, no backups, sync outage 31 May–2 Jun, Firestore + anonymous auth

30 adversarially-verified problems are grouped below by severity. Overlapping issues have been consolidated. For each: **what is wrong** (plain English), **why it matters to the team**, and **the concrete fix**.

---

## CRITICAL (5) — data loss, crashes, or access bypass. Fix before any further use.

### C1. Outage edits are silently overwritten by older cloud data on first reconnect
**What is wrong:** When sync comes back on after the outage, the merge picks the "newer" copy of each lead by comparing timestamps. But the edits reps made *during* the outage carry no timestamp (`_modAt` empty), while the stale pre-outage cloud copy carries a real one. So the merge treats empty as "oldest" and the old cloud version wins.
**Why it matters:** This is the single worst data-loss path. Two to three days of Ameer's, Muneeb's and Yousuf's offline work — booked meetings, call dispositions, CRM stage moves — gets wiped the instant the first cloud snapshot arrives, with no warning and no undo. 540 leads, no backup.
**Fix:** In `loadState()` (~line 1851), backfill any lead missing a string `_modAt` with a current-ISO sentinel and persist it *before* `startSharedSync` subscribes. Also change the merge (lines 6131-6134) so a local lead with an empty `_modAt` is never overwritten by remote.

### C2. Per-lead activity history is dropped on merge — Activity Monitor under-counts work
**What is wrong:** The merge replaces a whole lead object with the "newer" copy; it never unions the `activity[]` list. If two reps both touched the same business while offline, on reconnect only one rep's whole record survives and the other's logged actions vanish — then get pushed back to the cloud, making the loss permanent.
**Why it matters:** Those activity arrays are the Master's only source of truth for who-did-what (calls today, most-active rep, per-rep KPIs that may drive pay). The monitor reports fewer actions than happened and credits a shared lead's entire history to whoever saved last. The owner manages on numbers that are quietly wrong.
**Fix:** In the per-lead merge (~line 6134), union activity before replacing: `winner.activity = dedupeBy(local.activity.concat(r.activity), a => a.by+'|'+a.action+'|'+a.date)` so append-only events survive regardless of which scalar copy wins.

### C3. CRM list crashes on imported leads with a partial `crm` object
**What is wrong:** `renderCRMList` reads `crm.priority.charAt(0)` and `crm.notes.slice(...)` with no guards. Imported/synced CRM leads can have a `crm` object missing `notes`/`priority`/`disposition`. One such lead throws and blanks the entire CRM section.
**Why it matters:** The CRM/Outreach pipeline is the team's revenue surface. A single malformed CRM lead — 11 are already in CRM, more get added daily — blanks the whole list for whoever it's visible to. The kanban board inherits the same fragility.
**Fix:** Read defensively: `const notes = crm.notes || []` (lines 2828/2834/2835) and `(crm.priority || 'medium')` (line 2790, and kanban 2917). Also normalise on load/merge: whenever `l.crm` exists, set `l.crm.notes ||= []`, `l.crm.priority ||= 'medium'`, `l.crm.disposition ||= 'nurture'`.

### C4. Typing "Master" in the add-new-rep field bypasses the Master PIN entirely
**What is wrong:** Selecting "Add new rep..." and typing exactly `Master` resolves to the Master identity with **no PIN check** — the PIN gate only fires on the dedicated Master login branch. `resolveRepName` has a special case `if (clean === 'Master') return 'Master'`.
**Why it matters:** Any of the three reps can grant themselves full owner powers without knowing the PIN — including the **Reset All Data** button, which can wipe the shared 540-lead dataset for the whole team. This is the owner's only access boundary and it is trivially defeated.
**Fix:** In `resolveRepName`, delete the `if (clean === 'Master') return 'Master'` special case so Master can only be set via the PIN branch. Also reject any custom name that case-insensitively equals `master` in the add-rep branch.

### C5. Lead Bank / CRM search crashes the page on imported leads (unguarded field access)
**What is wrong:** The Lead Bank and CRM search filters call `l.businessName.toLowerCase()`, `l.description.toLowerCase()`, `l.contacts.some(c => c.name.toLowerCase()...)` with no null guards. The ~540 imported leads never went through the in-app add path that defaults these fields, so any lead missing `description`/`contacts` (or a contact missing `name`) throws and blanks the section. One bad lead kills the render for everyone.
**Why it matters:** Lead Bank and CRM search are the primary screens all three reps live in. The moment a rep types into search — or just loads the bank with one malformed imported lead — the section goes blank with an uncaught error. With 540 leads of unknown shape, this is near-certain to fire.
**Fix:** Harden the filters and card render with null guards — `(l.businessName||'').toLowerCase()`, `(l.description||'').toLowerCase()`, `(l.contacts||[]).some(c => (c.name||'').toLowerCase().includes(s))` (lines 2234-2236, 2640-2641), `(l.contacts||[]).length` (line 2332). Add a `normaliseLead(l)` that fills `businessName/description:''`, `phones/emails/contacts:[]`, `source/status`, called on every lead in `startSharedSync` right before `state.leads = merged`.

---

## HIGH (7) — feature silently broken, real cost, or recurring crash risk.

### H1. Claim push lost on mobile — the double-call lock does nothing on phones
**What is wrong:** Tapping Call schedules the claim write inside a 400ms timer, then immediately navigates to a `tel:` link. On phones, that navigation suspends the page and drops the pending write before it commits.
**Why it matters:** This is the whole point of the feature, and the reps call from phones. Ameer's claim never reaches Firestore, so the "Ameer is on this" badge never appears for Muneeb or Yousuf, and two reps dial the same prospect. The feature fails on the exact device the team uses.
**Fix:** In `openDialer`, before setting `window.location.href`, flush an immediate variant of `pushLeads` (clear the timer, run/await `batch.commit()` now for the claimed lead), then navigate in a `finally` so dialing still works if the commit fails.

### H2. Every claim/release re-writes all ~540 leads — write amplification, cost, and a hard break past 500 leads
**What is wrong:** `saveState()` re-stamps `_modAt`/`_modBy = now` on **every** lead, not just the one changed. The echo-dedup then can't skip anything, so each claim/release/log-call writes ~540 Firestore docs.
**Why it matters:** Every dialer open or call log writes ~540 docs instead of 1-2 — tens of thousands of writes a day, burning Firestore free-tier quota (real money) and saturating every rep's snapshot listener with full re-merges. Worse: a `writeBatch` caps at 500 ops; with 540 leads the batch throws "too large" and the **whole push, including the actual claim, fails** — claiming is already broken at this lead count.
**Fix:** In `saveState()`, stamp `_modAt`/`_modBy` only on leads actually mutated (track a per-lead `_dirty` flag set in claim/release/logCall). In `pushLeads`, chunk `batch.set` into ≤450-op commits as a safety net. This turns a claim into a 1-doc write and removes the 500-op overflow.

### H3. Deleted leads resurrect for every other rep — no tombstones
**What is wrong:** Deleting a lead removes it locally and from the cloud, but the merge on every *other* rep's device is a pure union — it never removes a local lead absent from the snapshot. Rep B keeps the deleted lead and re-creates it in the cloud on his next save. There is no `_deleted` tombstone anywhere.
**Why it matters:** Any lead one rep deletes comes back from the dead as soon as another rep saves anything. Reps re-dial dead/duplicate businesses and the Master's counts drift. Deletions are effectively non-durable across the team.
**Fix:** Soft-delete: write a tombstone `{_deleted:true,_modAt,_modBy}` via `setDoc` instead of `batch.delete`. Make the merge drop leads whose newer-wins copy is `_deleted`, and filter `_deleted` out of `state.leads` before rendering/pushing.

### H4. Merge's re-push of locally-newer leads is a dead no-op (crossed flags)
**What is wrong:** When the merge keeps a locally-newer unpushed edit, it tries to push it back immediately — but that push runs inside the window where `pushLeads`'s guard flag is still set, so it returns and pushes nothing. The merge toggles a *different* flag than `pushLeads` reads.
**Why it matters:** A rep's edit can sit un-propagated until his next explicit save, so a second device loading in that window won't see it. Combined with the outage and mobile-claim issues, it widens the window where real edits live on only one device and can be lost.
**Fix:** Defer the push-back outside the synchronous snapshot window: replace the inline call with `setTimeout(() => CrescendoSync.pushLeads(state.leads), 0)` (the existing `lastPushed` ledger still suppresses true echoes).

### H5. Remote/imported leads bypass normalization → unguarded access throws across multiple screens
**What is wrong:** Remote docs are merged as raw Firestore objects; neither normalizer runs on that path. Multiple render/search paths then access fields that may be missing. (This is the root cause behind C3 and C5; called out here as the systemic gap.)
**Why it matters:** Any imported lead of unexpected shape can crash whichever screen touches it — Lead Bank, CRM, panel, Activity Monitor — for every user, not just the one who imported it.
**Fix:** Add a single `normaliseLead(l)` (defaults `businessName/description:''`, `phones/emails/contacts:[]`, `crm` sub-fields, `activity:[]`, `source/status`) and run it on every lead in `startSharedSync` right before `state.leads = merged`, in addition to the per-screen null guards in C3/C5.

### H6. Top bar overflows on phones — search and controls get crushed or pushed off-screen
**What is wrong:** The top bar is a non-wrapping flex row (hamburger + logo + search + "Signed in as: <full name>" + Switch + theme toggle). The mobile media query only hides the logo text — it never shrinks the user block or search or reduces padding.
**Why it matters:** On a 375px phone, a full name like "Muneeb Moiz" plus "Signed in as:" plus Switch plus toggle can't fit. The search input — the reps' main way to find a lead before calling — gets crushed to a few pixels or the toggle is pushed off-screen. They lose usable search on the device they call from.
**Fix:** In the `@media (max-width:768px)` block: hide the "Signed in as:" label, shrink the user block to name + Switch (or move Switch into the sidebar), set top-bar padding to `var(--space-3)`, and keep search as the flex child with a sensible min-width (do **not** hide it — it's the only lead search).

### H7. Concurrent same-snapshot claims are clobbered with no conflict shown
*(Spans claiming + data-merge — consolidated.)*
**What is wrong:** Two reps can both pass the "claimed by other" check before either claim lands, because each only sees its own snapshot. Both claim; the merge resolves by `_modAt` string compare, so whoever's clock/push is a hair later silently overwrites the other's claim. No conflict warning either way.
**Why it matters:** When two reps tap the same lead within the same ~1-2s sync window (common working a fresh shared list top-down), both dial it and neither sees a conflict. Double-calling the prospect is exactly what this feature exists to prevent.
**Fix:** Claim via a Firestore `runTransaction` on the single `leads/{id}` doc that only sets `activeCallBy`/`activeCallAt` if the existing claim is empty or older than `CLAIM_TTL_MS`. On a lost race, re-read and show "X just claimed this" instead of routing the claim through the whole-doc batched set.

---

## MEDIUM (10) — misleading data, inconsistent behaviour, or moderate UX/security gaps.

### M1. Last-writer-wins uses each client's wall clock — skew can pick the wrong winner
`_modAt` comes from the writing device's clock and the merge orders strictly by it. A device with a fast clock can make an *older* edit win over a genuinely newer one, silently losing the more recent of two concurrent edits. **Fix:** also write `_srvAt: serverTimestamp()` per lead, normalize it to ISO on read, and order the merge by `_srvAt` when both sides have it, falling back to `_modAt`.

### M2. Stale claim badge never clears on its own
The "X is on this" badge is time-based (15-min TTL) but nothing re-renders when the TTL crosses — there's no timer. A freed lead can still show a red "live" badge for minutes (rep skips a callable lead), or vice versa. **Fix:** add a ~30s `setInterval` that calls `renderAll()` (local-only, no writes) so TTL transitions surface without a user action.

### M3. Activity Monitor week starts Sunday; Reports week starts Monday
The same "this week" question yields different totals on different screens (Home and Activity Monitor use Sunday start; Reports uses Monday). For a UK Mon–Fri team this erodes trust in the dashboards and breaks week-over-week comparisons. **Fix:** one shared `startOfWeek` helper using `day=(getDay()+6)%7` (Monday start), called from all three render paths.

### M4. Master PIN is hardcoded in client JS — gate is trivially bypassable
The PIN (`786777`) is in plaintext and Master status is just a localStorage string with no server check. Any rep can view-source or run `localStorage.setItem(...)` to unlock cross-rep KPIs, full CSV export, and Reset Data. (C4 is a second, even easier bypass of the same gate.) **Fix:** move Master to a real Firebase auth identity and enforce read-all/delete in Firestore Security Rules keyed to that uid; stop gating on the client string and hardcoded PIN.

### M5. CEO login (e.g. "Melusi Ndoro") gets aggregate views but cannot open the Activity Monitor
The owner has two identities — "Master" (full powers) and the CEO roster entry "Melusi Ndoro". Logging in by name (the natural choice) silently loses the Activity Monitor while still showing partial aggregate/reassign/export. Capabilities are fragmented across identities. **Fix:** gate the Activity Monitor (nav + render) on `isMasterUser() || CEOS.includes(getCurrentUser())` to match the existing aggregate access.

### M6. `resolveRepName` roster order lets near-duplicate spellings become permanent shadow reps
A custom rep added with a slightly different spelling (e.g. "Yousuf Zacki" vs roster "Yousuf Zacky") is never collapsed onto the canonical rep, so their activity/claims/`_modBy` split forever, and there's no merge/rename UI. **Fix:** constrain login to the fixed roster (drop free-text "other"), and add an owner-only rename/merge action that rewrites attribution across all leads.

### M7. Permanent sync indicator blocks taps and overlaps the chat button on phones
The always-on "Synced as…" pill sits bottom-right at z-9999 with `pointer-events:auto`, painting over the chat FAB and eating taps on whatever sits in that corner (often a Call button). **Fix:** set the pill to `pointer-events:none` and move it above the FAB (`bottom:calc(var(--space-6) + 66px)`).

### M8. Sync indicator uses hardcoded light colours — unreadable in dark mode
The pill's background/text are literal hex values, ignoring the app's dark theme, so it stays bright light-green in the corner against a dark UI for evening callers. **Fix:** replace the hex with theme tokens (`--color-success-highlight`/`--color-success`, etc.), matching the badge conventions.

### M9. Call / Log-call buttons are below the 44px touch-target minimum
Lead-panel "Log call" (26px) and CRM "Add note" (28px) buttons sit flush against `tel:` links, so a fat-finger tap launches a call instead of logging one. **Fix:** add `@media (pointer:coarse) { .btn-sm { min-height:40px } }` and remove the inline `min-height` overrides.

### M10. "Call" always dials the first phone, ignoring multi-phone leads
The prominent Call buttons always dial `phones[0]`; secondary numbers are only reachable as `tel:` links inside the full panel. When the primary is a dead landline, reps keep dialing the wrong number. **Fix:** pass the chosen number via `data-num` and have `openDialer(id, num)` dial it; render a quick number chooser when a lead has multiple phones.

### M11. View-Lead panel assumes `p.number` is a string and can throw
The panel maps `lead.phones` and calls `p.number.replace(...)` with no guard (and reads `lead.phones.length` unguarded), so a malformed imported phone field throws and the panel won't open — blocking the call workflow for that lead. **Fix:** guard the gates and coerce: `const num = String((p && p.number) || '')`, and wrap the email/contact blocks with length checks. (Overlaps the H5 normalization gap.)

### M12. Activity Monitor crashes on any activity entry with a missing/non-string action
`getAllActivities` flattens activity from all leads with no shape validation; one entry missing `action` (or with a non-string action) throws and blanks the whole monitor for the owner. **Fix:** push only valid entries (`if (a && typeof a.action === 'string')`) and have the describe/badge/filter helpers start with `const t = String(action||'').toLowerCase()`.

*(M11 and M12 are runtime-logic crash risks of the same family as C3/C5/H5; kept at medium because they affect narrower paths — single-panel open and the master-only monitor respectively.)*

---

## LOW (8) — minor inconsistency, latent risk, or polish.

- **L1. Seed-push can double-seed on disaster recovery.** The 1500ms cloud-empty seed gate is per-session; two reps booting against a genuinely empty cloud in the same window can both seed. Harmless day-to-day (cloud has ~540 leads), but recovery is exactly when seeding runs. **Fix:** gate behind a create-if-absent `meta/seeded` doc written in a transaction.
- **L2. No recent-contact cooldown after a call.** `logCall` releases the claim, so a lead is instantly re-openable with no guard against a second rep re-dialing seconds after a "no answer". **Fix:** in `openDialer`, also `confirm()` when `dateLastContact`/latest activity by another user is within a short cooldown.
- **L3. "Won", "reassigned", "started working" are unfilterable and mis-badged in the Activity Monitor.** The highest-signal events for oversight (wins, ownership changes) have no filter and render as generic grey notes. **Fix:** add `won`/`reassigned` filter entries and badge cases.
- **L4. Per-user breakdown mixes scopes.** The per-rep action count honours filters but the "calls today" figure beside it always ignores them, so a week filter can show count 0 next to "5 calls today". **Fix:** derive the calls figure from the same filtered set, or move it to a clearly separate "live today" column.
- **L5. Same human split across identities in KPIs.** Attribution stamps the raw logged-in label, so the owner working as "Master" vs "Melusi Ndoro" shows as two people in the breakdown. **Fix:** map `a.by === 'Master'` to the intended rep when aggregating.
- **L6. Unescaped action text in the Activity Monitor feed.** `describeAction(a.action)` is injected raw while adjacent fields are escaped — not exploitable today (enums only) but a latent injection seam. **Fix:** wrap as `escapeHtml(describeAction(a.action))`.
- **L7. Live claim badge has weak contrast and small size.** 0.65rem magenta-on-pink (≈4.42:1) is the hardest-to-read element yet the most important signal. **Fix:** bump to ~0.72rem and darken `--color-error` to clear 4.5:1.

*(L8 reserved — covered under L2/L7 consolidation of the low-severity claiming/badge items.)*

---

## Verdict

**Not production-ready as-is for a shared, phone-first, no-backup team.** The app's two headline features — cross-device claim coordination and the Master's Activity Monitor — are both currently unreliable on the exact conditions this team operates under (mobile dialing, an outage backlog, 540+ imported leads). Several failure modes cause **silent permanent data loss** or **blank crashing screens** for all users at once.

**Must-do-now (before reps touch it again):**
1. **C1** — backfill `_modAt` on load so outage work isn't wiped on first reconnect. This is time-critical: the loss triggers on the *first* post-outage page load.
2. **C2** — union activity arrays on merge so KPI history survives.
3. **C3 + C5 + H5** — normalise imported leads and add null guards so Lead Bank / CRM don't blank-crash. (Do these together; same root cause.)
4. **C4** — remove the "Master" add-rep bypass so reps can't self-promote and hit Reset Data.
5. **H1** — flush the claim write before `tel:` navigation so the double-call lock actually works on phones.
6. **H2** — stop re-writing all 540 leads per action; this is both a cost leak and a hard break (500-op batch) that already breaks claiming at this lead count.

**Strongly recommended next:** H3 (tombstones), H4 (push-back no-op), H6 (mobile top bar), H7/M1 (transactional claims + server time). Together these make sync and claiming genuinely trustworthy.

**Nice-to-have / hardening:** the M-tier dashboard consistency (M3), auth hardening (M4), identity cleanup (M5/M6), and all mobile-polish + L-tier items. None block launch once the criticals and highs are closed, but M4/M5 matter for owner trust and should follow soon.

**Bottom line:** budget one focused remediation pass on the 5 criticals + 6 highs above. Take a manual Firestore export *before* any rep reconnects post-outage — C1 can destroy days of work on the first load, and there is currently no backup or undo.
