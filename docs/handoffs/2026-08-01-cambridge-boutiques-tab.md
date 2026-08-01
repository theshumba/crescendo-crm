---
date: 2026-08-01
branch: main
status: shipped
---

# Session handoff: Cambridge Boutiques lead list + its own CRM tab

## Resume protocol

1. Read this whole file
2. Run: `git status && git log --oneline -5`
3. Open: `crescendo-crm.html:2372` (list block), `crescendo-crm.html:4233` (tab renderers), `~/Desktop/cambridge-boutique-leads.csv`
4. Ask the user: "Pick up at chasing the 7 first-name-only leads, or pivot?"

> **Scope note:** mixed. Code work was in-repo (`crescendo-crm.html`, `scripts/verify.mjs`), both commits pushed and live. Out-of-repo artefacts this session: `~/Desktop/cambridge-boutique-leads.csv` + `-notes.md`, the memory file `crescendo-crm-backend.md`, and a research pipeline in the session scratchpad (see Code anchors). Working tree is clean — nothing dirty belongs to anyone else.
> **Variant:** Feature.

## Task state

**What we were doing:** Found qualified Cambridge boutique businesses with Exa, then put them into the Crescendo CRM as their own tab under Qualified Leads. Second pass grew the list 52 → 81 and enriched every record. Both rounds are committed, pushed and verified live on Pages.

**Exact next step:** Nothing is half-finished. The obvious next move is chasing the 7 businesses that published only a first name, so they clear the bar: Reeds Hair (Andrew), No.5 The Skin Clinic (Laura), Violet and Bloom (Georgina), Lily Cora Flowers (Lily), CSL Brows and Beauty (Charlotte), Prestige Skin (Abby), Elem Hair (Lisa and Justin). Each needs a surname from a phone call or a Companies House match; add them to `newdoms.txt` and re-run the pipeline (Code anchors).

**Open questions:**
- Should the 7 first-name-only businesses go in with a first name, or stay out until a surname is confirmed? Current rule keeps them out.
- Two rows carry a role caveat rather than confirmed ownership: Hurst Park Dental (Max Leslie, lead cosmetic dentist) and Soho Fine Art (Jackie Ritsema, Executive Gallery Director). Leave, relabel, or drop?
- Nobody has worked the list yet (0 moved to CRM). Worth deciding who owns it before the reps find it themselves.

**Blockers:** None.

## Reasoning trail

**Decisions made:**
- **Qualification bar = website + direct phone + FULL owner name**, email optional. A wrong or missing owner name is worse than no lead, since the rep opens the call with it. ~80 businesses that had site+phone were dropped for having no verifiable owner.
- **Leads live in their own tab, not the Lead Bank or Qualified grid.** `lead.list = 'cambridge-boutique'`, and `isListLead()` excludes them from both lists and both badges, so a new list never disturbs counts reps already work to.
- **Ids are name slugs (`cbq-<slug>`), never `crypto.randomUUID()`** — every device seeds identical ids so the first cloud sync merges instead of minting 81 clones per rep. This is the documented single-file-crm invariant.
- **Seeder is add-or-enrich, gated by `CBQ_VERSION`** — an existing lead keeps everything a rep owns (status, crm, activity, assignedTo, claim, typed free text) and receives only research fields plus union-merged new phones/emails. Bump `CBQ_VERSION` to push a future research round.
- **Site observations are read off each business's own site, never inferred** — "no online booking", "sells nothing online", "footer still says 2019". These fill `qualification.weaknessesOpportunities` and a new "Any opening" filter. Deliberately did NOT fill the three fit-rating fields, since rating fit would be fabrication.
- **`source: 'research'` added to `SOURCES`** — needed because `firestore.rules` rejects `source == 'sample'`; all 81 pass the create guard so they sync on first rep load.
- **Two `scripts/verify.mjs` assertions were made list-aware rather than loosened** — both counted global totals that these leads legitimately change; they still test their original intent.

**Tried and rejected:**
- **Fuzzy Companies House matching (token overlap + Cambridgeshire address)** — produced confident-looking but wrong directors (Market House → "Cambridge Mini Market", Milton Chiropractic → "Milton Keynes Chiropractic"). Replaced with strict normalised-name equality; substring matching also failed (`"bedbreakfast" in "5chapelstreetbedandbreakfast"`).
- **Regex extraction of owner names from page text** — too noisy alone. What worked: strict CH equality for 49, plus hand-reading crawled About/Team pages for the rest.
- **Blanket `white-space: normal` on `.lead-card .badge`** to fix overflow — broke the status pill into "Quali fied". Scoped to `.service-tag` instead.

## Code anchors

- `crescendo-crm.html:2372-2439` — `CBQ_LIST`, `CBQ_VERSION`, the 81-lead data array, `seedCambridgeBoutiques()` add-or-enrich logic, `isListLead()`, `cbqLeads()`. Start here for anything data-related.
- `crescendo-crm.html:4233` — `getFilteredCambridge()`, including the "Any opening" gap filter (booking / shop / email / social / stale).
- `crescendo-crm.html:4271` / `:4349` — `renderCambridgeBoutique()` (toolbar + header counts) and `renderCambridgeList()` (card template with verification chips, observations, socials).
- `crescendo-crm.html:433` — `.lead-card { min-width: 0 }`. **Load-bearing:** without it a grid item takes min-content width and one long address stretched the track to 712px inside a 358px column, clipping every card on a phone while `document.scrollWidth` still read clean. Measure `grid.scrollWidth` vs `grid.clientWidth` when checking phone layout.
- `crescendo-crm.html:1082` and `:6149` — nav button (sits directly under Qualified Leads) and the section's delegated event handlers.
- `scripts/verify.mjs:82` and `:302` — the two assertions made list-aware.
- `/private/tmp/claude-501/-Users-theshumba/f1c00501-bc1c-4e62-aa8c-40bd7e22b950/scratchpad/cam/` — the research pipeline, in run order: `pool.py` (parse Exa results → candidates), `enrich.py` (deep site crawl: postcode, socials, platform, booking, ecommerce), `ch3.py` (strict Companies House match + firmographics), `merge.py` → `build.py` (final records + CSV). Tests: `tab2.mjs` (28 checks), `mob3.mjs` (phone overflow), `shot.mjs` (screenshot). **Scratchpad is session-scoped and will not survive — copy it into the repo if a third round is wanted.**

## Git state snapshot

**Branch:** `main`

**Status:**
```
(clean)
```

**Recent commits:**
```
4eecb20 Grow the Cambridge list to 81 and give every lead real depth
5a694e2 Add a Cambridge Boutiques tab with 52 verified local leads
4aac647 Tell reps when a new version is out instead of relying on someone saying "hard-refresh"
239b5f7 Cache reads to disk, fix the meetings that could never be closed, and back up nightly
7c429c4 Work the list, honest reports, and a Home page that lands you on the lead
abe16a5 Calls now book the next step and move the pipeline; close the last clobber path
019a894 Stop moved leads reverting, date every stage change, and add the filters reps asked for
2250a9b Correct the name: Adan, not Adnan
7da52f3 Make "Move to CRM" actually move, and treat Joshua + Adnan as sales people
00cbc75 Add Amir Hasbullah to the consultant roster
```

**Diff stat:**
```
(no unstaged changes)
```
