# Mirror Spec — England/UK Map Feature (from GaitGuard CRM `crm.html`)

This is a paste-reference spec for replicating the GaitGuard single-file-app map into another CRM.
Source: `/Users/theshumba/Documents/GitHub/gaitguard/crm.html`.

**One-line summary:** Leaflet 1.9.4 (CDN) + OpenStreetMap tiles, no external geocoding — leads are
placed via a hardcoded `GEO_CENTROIDS` county/region lookup table (with explicit `lat`/`lng` taking
priority and a deterministic jitter to de-overlap), rendered as colour-by-business `circleMarker`s with
popups; unlocated leads are counted in an "N location unknown" caption (not plotted); the map lives in a
standard nav section that calls `renderMap()` on show and uses `invalidateSize()` after layout.

---

## 1. CDN includes

In `<head>` (lines 11–15). Leaflet **1.9.4**, CSS + JS with SRI integrity hashes. **No marker-cluster
plugin.** Tiles come from OpenStreetMap (configured at init, not in `<head>`).

```html
<!-- Leaflet (map view — site-visit density planning). Loaded from CDN; degrades gracefully if offline. -->
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
      integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=" crossorigin="" />
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
        integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=" crossorigin=""></script>
```

Tile provider (set in `renderMap`, line 5636):
```js
window.L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom: 18,
  attribution: '&copy; OpenStreetMap contributors'
}).addTo(map);
```

---

## 2. Container markup + CSS

### Nav section shell (lines 962–963)
```html
<section id="section-map" aria-label="Map">
  <div id="map-content"></div>
</section>
```

### Section visibility CSS (lines 222–224)
Sections are show/hidden by an `.active` class — nothing map-specific; the map is just a section.
```css
.main-content { flex: 1; padding: var(--space-8); overflow-y: auto; }
.main-content section { display: none; }
.main-content section.active { display: block; }
```

### The map div itself is created inside `renderMap` (line 5621), inline-styled — **height 560px**, bordered, rounded, `z-index:0` (keeps tiles below app chrome):
```html
<div id="gg-leaflet-map" style="height:560px;border:1px solid var(--color-border);border-radius:var(--radius-md);overflow:hidden;z-index:0;"></div>
```

There is **no separate sidebar/list layout for the map** — the only "list" content is the legend +
counts caption rendered above the map (see §6). A fixed pixel height is required because Leaflet cannot
size against a `display:none` parent.

---

## 3. Map init (`L.map`, center/zoom, bounds, tiles)

Lines 5634–5662. Note: **no `maxBounds`; UK framing is achieved purely via `fitBounds` to the marker
group**, with a fixed UK-overview fallback `setView([54.0, -2.5], 5/6)` when there are no/invalid markers.

```js
const map = window.L.map(mapEl, { scrollWheelZoom: true });
__ggMap = map;
window.L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom: 18,
  attribution: '&copy; OpenStreetMap contributors'
}).addTo(map);

// ... markers built ...

if (markers.length) {
  const group = window.L.featureGroup(markers);
  try { map.fitBounds(group.getBounds().pad(0.2)); }
  catch (e) { map.setView([54.0, -2.5], 6); }
} else {
  map.setView([54.0, -2.5], 5); // default: UK overview
}
```

`[54.0, -2.5]` is the UK centroid; zoom 5 = whole-UK overview, zoom 6 = the fallback when bounds fail.

---

## 4. How a lead becomes coordinates (the geocoding logic)

**There is NO network geocoding** (no Nominatim, no postcodes.io). Coordinates come from one of two
sources, in priority order, resolved synchronously by `geocodeLead(l)`:

1. **Explicit stored `lead.lat` / `lead.lng`** (win if finite and not 0,0).
2. **A hardcoded centroid lookup table** `GEO_CENTROIDS` keyed by lowercased UK region/county (and Gulf
   city) name, matched against `lead.region` then `lead.county`, with exact-key match first then a loose
   `includes()` contains-match.

A deterministic hash-based **jitter** (±~0.09°) is applied to centroid matches so co-located leads don't
stack on the exact same pixel. There is **no caching layer** (nothing to cache — the table is in-memory
and lookups are O(1)/O(n) string matches). **Failure/missing = returns `null`** and the lead is bucketed
as "location unknown" (see §6).

### Centroid table (lines 5513–5544, abridged — keep the full table when mirroring)
```js
const GEO_CENTROIDS = {
  // UK nations / broad regions
  'england': [52.3555, -1.1743], 'scotland': [56.4907, -4.2026], 'wales': [52.1307, -3.7837],
  'northern ireland': [54.7877, -6.4923], 'uk': [54.0, -2.5], 'united kingdom': [54.0, -2.5],
  'south east': [51.2, -0.5], 'south west': [50.8, -3.5], 'east': [52.2, 0.5], 'east anglia': [52.4, 0.7],
  'east midlands': [52.8, -1.0], 'west midlands': [52.5, -2.0], 'north west': [53.8, -2.6],
  'north east': [54.9, -1.7], 'yorkshire': [53.9, -1.3], 'london': [51.5074, -0.1278],
  'home counties': [51.5, -0.4], 'midlands': [52.6, -1.5],
  // UK counties (equestrian heartlands first)
  'surrey': [51.24, -0.42], 'kent': [51.20, 0.70], 'sussex': [50.95, -0.20], 'east sussex': [50.90, 0.27],
  'west sussex': [50.93, -0.45], 'hampshire': [51.06, -1.31], 'berkshire': [51.45, -1.04],
  'oxfordshire': [51.76, -1.26], 'buckinghamshire': [51.81, -0.81], 'hertfordshire': [51.81, -0.23],
  'essex': [51.76, 0.47], 'gloucestershire': [51.86, -2.07], 'wiltshire': [51.35, -1.99],
  'somerset': [51.10, -2.93], 'dorset': [50.74, -2.34], 'devon': [50.72, -3.74], 'cornwall': [50.40, -4.65],
  'warwickshire': [52.27, -1.59], 'worcestershire': [52.19, -2.22], 'shropshire': [52.62, -2.75],
  'staffordshire': [52.84, -2.06], 'cheshire': [53.18, -2.60], 'lancashire': [53.81, -2.69],
  'cumbria': [54.58, -2.80], 'northumberland': [55.21, -2.08], 'durham': [54.73, -1.85],
  'leicestershire': [52.64, -1.13], 'northamptonshire': [52.27, -0.88], 'nottinghamshire': [53.10, -1.00],
  'derbyshire': [53.10, -1.56], 'lincolnshire': [53.07, -0.24], 'norfolk': [52.66, 1.05],
  'suffolk': [52.19, 0.97], 'cambridgeshire': [52.33, 0.12], 'bedfordshire': [52.10, -0.46],
  'north yorkshire': [54.10, -1.45], 'west yorkshire': [53.76, -1.65], 'south yorkshire': [53.50, -1.35],
  'east yorkshire': [53.84, -0.43], 'greater manchester': [53.49, -2.24], 'merseyside': [53.42, -2.93],
  'herefordshire': [52.08, -2.72], 'rutland': [52.66, -0.63], 'isle of wight': [50.69, -1.30],
  'pembrokeshire': [51.80, -4.90], 'powys': [52.33, -3.39], 'aberdeenshire': [57.28, -2.38],
  'edinburgh': [55.95, -3.19], 'glasgow': [55.86, -4.25], 'fife': [56.21, -3.15],
  // Gulf cities (drop these if England-only) ...
  'dubai': [25.20, 55.27], 'abu dhabi': [24.45, 54.38], /* ... etc ... */
};
```

### Deterministic jitter (lines 5546–5553)
```js
function geoJitter(seed) {
  let h = 0;
  const s = String(seed || '');
  for (let i = 0; i < s.length; i++) { h = (h * 31 + s.charCodeAt(i)) & 0xffff; }
  const dx = ((h % 100) / 100 - 0.5) * 0.18;
  const dy = (((h >> 5) % 100) / 100 - 0.5) * 0.18;
  return [dx, dy];
}
```

### Resolver (lines 5554–5577) — quoted verbatim
```js
// Resolve a [lat,lng] for a lead, or null when no location signal exists.
function geocodeLead(l) {
  if (!l) return null;
  // Explicit coordinates win.
  const lat = Number(l.lat), lng = Number(l.lng);
  if (Number.isFinite(lat) && Number.isFinite(lng) && (lat !== 0 || lng !== 0)) return [lat, lng];
  // Derive from region / county text against the centroid lookup.
  const candidates = [l.region, l.county].filter(s => typeof s === 'string' && s.trim());
  for (const c of candidates) {
    const key = c.trim().toLowerCase();
    if (GEO_CENTROIDS[key]) {
      const [j1, j2] = geoJitter(l.id || c);
      return [GEO_CENTROIDS[key][0] + j1, GEO_CENTROIDS[key][1] + j2];
    }
    // Loose contains match (e.g. "West Surrey" → surrey).
    for (const k of Object.keys(GEO_CENTROIDS)) {
      if (key.includes(k)) {
        const [j1, j2] = geoJitter(l.id || c);
        return [GEO_CENTROIDS[k][0] + j1, GEO_CENTROIDS[k][1] + j2];
      }
    }
  }
  return null;
}
```

> Mirroring note: to upgrade to real geocoding (postcodes.io / Nominatim), you'd replace the lookup with
> an async fetch + a `Map` cache keyed by postcode/place, write the result back to `lead.lat/lng` so the
> "explicit coords win" branch then short-circuits on subsequent renders. As shipped, GaitGuard does
> none of this — it is fully offline/synchronous.

---

## 5. Marker rendering (icons, colour, popups, click, clustering)

- **No custom `divIcon`/image icons and no clustering.** Each lead = a Leaflet `circleMarker`
  (radius 7, white 1.5px stroke, 85% fill opacity).
- **Colour by `business` field** via `leadBusinessColor()` (lines 5578–5584): purple `#7c3aed` = Crest &
  Canter, teal `#0d9488` = GaitGuard, blue `#2563eb` = Both/other. (In a different CRM, recolour by
  whatever your status/stage dimension is.)
- **Popup** binds an HTML string of: business name, business label, region/county, and CRM stage name.
- **Click behaviour = default Leaflet popup open.** There is *no* "click marker → open lead detail"
  wiring; the popup is read-only.

Marker build loop (lines 5641–5654):
```js
const markers = [];
located.forEach(({ lead, pt }) => {
  const color = leadBusinessColor(lead);
  const m = window.L.circleMarker(pt, {
    radius: 7, color: '#fff', weight: 1.5, fillColor: color, fillOpacity: 0.85
  });
  const name = escapeHtml(lead.businessName || 'Unnamed lead');
  const where = escapeHtml((lead.region && lead.region.trim()) || (lead.county && lead.county.trim()) || '');
  const bizLabel = (lead.business === 'CC') ? 'Crest & Canter' : (lead.business === 'BOTH' ? 'Both services' : 'GaitGuard');
  const stage = lead.crm ? escapeHtml(getStageName(lead.crm.stage)) : '';
  m.bindPopup(`<strong>${name}</strong><br>${bizLabel}${where ? ' · ' + where : ''}${stage ? '<br>Stage: ' + stage : ''}`);
  m.addTo(map);
  markers.push(m);
});
```

Colour helper (lines 5578–5584):
```js
function leadBusinessColor(l) {
  const biz = (l && l.business) || 'GG';
  if (biz === 'CC') return '#7c3aed';   // purple — Crest & Canter
  if (biz === 'GG') return '#0d9488';   // teal — GaitGuard
  return '#2563eb';                      // blue — BOTH
}
```

---

## 6. Leads WITHOUT a location

Not plotted, not in a list — they are simply **counted**. The render partitions scoped leads into
`located[]` vs an `unknown` counter, then surfaces it in the caption "`N mapped · M location unknown`"
and explains the approximation in the intro paragraph. There is **no "undisclosed" sidebar bucket**.

Partition (lines 5594–5600):
```js
const scoped = state.leads.filter(businessMatch).map(l => { backfillSharedSchema(l); return l; });
const located = [];
let unknown = 0;
scoped.forEach(l => {
  const pt = geocodeLead(l);
  if (pt) located.push({ lead: l, pt }); else unknown++;
});
```

Legend + counts caption (lines 5610–5619):
```js
container.innerHTML = `
  <div class="section-header"><h1>Map</h1></div>
  <p style="color:var(--color-text-muted);font-size:var(--text-sm);margin-bottom:var(--space-4);">
    Lead density for planning site-visits. Pins are approximate — derived from region/county when exact coordinates are missing.
    Respects the current service filter (<strong>${/* filter label */''}</strong>).
  </p>
  <div style="display:flex;gap:var(--space-4);flex-wrap:wrap;margin-bottom:var(--space-4);font-size:var(--text-sm);">
    <span ...><span style="...background:#7c3aed;..."></span> Crest &amp; Canter (${ccCount})</span>
    <span ...><span style="...background:#0d9488;..."></span> GaitGuard (${ggCount})</span>
    ${bothCount ? `<span ...><span style="...background:#2563eb;..."></span> Both (${bothCount})</span>` : ''}
    <span style="color:var(--color-text-muted);">${located.length} mapped · ${unknown} location unknown</span>
  </div>
  ${leafletReady
    ? `<div id="gg-leaflet-map" style="height:560px;...;z-index:0;"></div>`
    : `<div style="...border:1px dashed ...;">Map library unavailable (offline?). Lead counts above still reflect the data.</div>`}
`;
```

---

## 7. Render / refresh lifecycle

- **Rebuilt from scratch every time the section is shown.** `renderMap()` is called via
  `renderActiveSection()` whenever `state.activeSection === 'map'` (line 1986). There is no incremental
  marker diffing — each call re-derives `located`, rewrites `container.innerHTML`, and recreates the map.
- **Stays in sync with lead data** because it always reads live `state.leads` (filtered by
  `businessMatch`) at render time, and re-renders on section show / `renderAll()`.
- **Old instance is destroyed first** to avoid Leaflet's "container already initialized" error, since the
  DOM node it was bound to gets blown away by the `innerHTML` rewrite (lines 5630–5635):
  ```js
  if (__ggMap) { __ggMap.remove(); __ggMap = null; }
  const mapEl = document.getElementById('gg-leaflet-map');
  if (!mapEl) return;
  const map = window.L.map(mapEl, { scrollWheelZoom: true });
  __ggMap = map;
  ```
- **`invalidateSize` timing** — called once on a 60ms `setTimeout` so Leaflet recomputes tile layout
  after the (previously `display:none`) container has been laid out (lines 5663–5664):
  ```js
  // Leaflet needs a size recalculation once the container is laid out.
  setTimeout(() => { try { map.invalidateSize(); } catch (e) {} }, 60);
  ```
- **Graceful degradation** — `leafletReady` gates everything; if `window.L` is missing (offline), it
  renders the counts + a dashed "Map library unavailable" placeholder and returns, never throwing
  (lines 5592, 5620–5626).

Module-level state (lines 5586–5587):
```js
let __ggMap = null;          // Leaflet map instance (reused across renders)
let __ggMapLayer = null;     // current marker layer group  (declared; markers actually added directly)
```

---

## 8. Nav wiring / `showSection` integration

**Nav button** (lines 859–862) — a standard `.nav-item` with `data-section="map"` and a lucide `map`
icon:
```html
<button class="nav-item" data-section="map">
  <i data-lucide="map" aria-hidden="true"></i>
  Map
</button>
```

**Delegated nav click** (line 4004) reads `data-section` and calls `showSection`:
```js
if (nav) showSection(nav.dataset.section);
```

**`showSection('map')`** (lines 1949–1974) toggles `.active` on `#section-map` + the nav button, then
calls `renderActiveSection()` → `renderMap()` (line 1986). Key lines:
```js
state.activeSection = sectionId;
document.querySelectorAll('.main-content section').forEach(s => s.classList.remove('active'));
const sec = document.getElementById('section-' + sectionId);
if (sec) sec.classList.add('active');
// ...nav active toggles...
renderActiveSection();   // -> case 'map': renderMap(); break;
```

---

## Minimal mirror checklist

1. Add Leaflet 1.9.4 CSS+JS (with SRI) to `<head>`.
2. Add a nav button `data-section="map"` + an empty `<section id="section-map"><div id="map-content"></div></section>`.
3. Wire `case 'map': renderMap(); break;` into your `renderActiveSection()` switch.
4. Paste `GEO_CENTROIDS`, `geoJitter`, `geocodeLead`, `leadBusinessColor`, the module-level `__ggMap`, and
   `renderMap()` — adapt field names (`businessName`, `region`, `county`, `lat`, `lng`, `business`,
   `crm.stage`) and the colour dimension to your schema.
5. Keep the destroy-before-create + 60ms `invalidateSize` pattern (mandatory for a section that starts hidden).
