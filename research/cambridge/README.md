# Cambridge Boutiques research pipeline

Builds the lead list behind the **Cambridge Boutiques** tab in `crescendo-crm.html`.
It is embedded in the app as `CBQ_LEADS` and gated by `CBQ_VERSION`, so bumping that
version is what pushes a new round of research to reps who already have the list.

## The bar

A business is only on the list if all three are true:

1. it has a working website,
2. it publishes a direct phone number,
3. a **full** owner or founder name can be verified.

A first name on its own does not qualify. The rep opens the call with that name, so a
wrong or partial one is worse than no lead. Round 3 dropped four businesses for exactly
this (Karen's Grooming, Karim Wellness, Savvy Design, White Wonders) on top of round 2's seven.

## Run order

| Step | Script | What it does |
|---|---|---|
| 1 | `pool3.py` | Parses Exa search results into candidate domains, skipping anything already on the list or already rejected |
| 2 | `enrich3.py` | Crawls up to 4 pages per site, reads postcode, phones, emails, socials, platform, booking system, ecommerce, owner snippets |
| 3 | `ch4.py` | Strict Companies House match, plus incorporation date, SIC codes and accounts dates |
| 4 | `assemble3.py` | Hand-verified table of who owns what, builds the new records and merges them with the existing list |
| 5 | `merge_intel.py` | Hangs the Exa research brief off each lead, cross-checks scraped founding years, writes `cbq3.json` and the desktop CSV |

Then embed: replace the `try { CBQ_LEADS = [...] }` line in `crescendo-crm.html` and bump
`CBQ_VERSION`.

## Two research blocks, deliberately separate

- **`research`** is mechanical extraction: regex over their own pages plus the Companies House
  register. Cheap, wide, and occasionally wrong in a specific way (see below).
- **`intel`** is the Exa researcher's brief: what they sell, what customers say, published
  prices, opening hours, press and awards, each with the URLs actually read.

Keeping them apart is what let step 5 catch **12 wrong founding years**. The `founded` regex
matches any year near the word "since" or "established", so a news item reading
"Oct 2023 15 Years at the Helm" became "Est. 2023" on a card for a business that has traded
35 years. Where `intel.trading` states a different year, the scraped one is dropped rather
than shown. Nothing is invented to replace it.

## Traps worth keeping

- **Search wide, accept narrow.** `ch4.py` searches Companies House on the business name, the
  page title and the domain stem, but only *accepts* a match on full normalised equality with
  the whole name, whole title or whole stem. An earlier version accepted a truncated title
  fragment and matched `karensgrooming.co.uk` to an unrelated "THE DOG GROOMER LTD".
- **Fuzzy matching is banned.** Round 2 tried token overlap plus a Cambridgeshire address and
  produced confident-looking wrong directors. Substring matching failed too.
- **Ids are name slugs, never `crypto.randomUUID()`.** Every device seeds identical ids, so the
  first cloud sync merges instead of minting a full duplicate list per rep.
- **Addresses need trimming.** The extractor grabs 90 characters of running text before the
  postcode and drags in whatever sentence preceded it. `assemble3.py` holds the trimmed
  versions in `ADDRESS`; they remove prose, they never add detail.
- **Phone numbers can hide in markup.** Regency Funeral Directors publishes its number 30 times,
  but split across tags, so text extraction found none. `PHONE_FIX` carries the grep-confirmed one.
- **Check `grid.scrollWidth` vs `grid.clientWidth` for phone layout**, not `document.scrollWidth`.
  `.lead-card { min-width: 0 }` is load-bearing; without it one long address stretches the grid
  track past a 390px screen and clips every card while the document still measures clean.

## Tests

```
node research/cambridge/tab2.mjs   # 38 checks on the list, filters, brief and the upgrade path
node research/cambridge/mob3.mjs   # true 390px phone overflow, via the wrap.html iframe
npm run verify                     # 54 checks on the rest of the CRM
```

The raw crawl caches (`pages3/`, `ch3/`) are gitignored. Re-running steps 2 and 3 refetches them.
