"""Attach the Exa research brief to each lead and emit the final CBQ array.

`research` stays what it always was: facts read off the business's own site plus the
Companies House registry. `intel` is the new, separate block: what the business sells,
what customers say, published prices, hours, press and awards, each with the URLs the
researcher actually read. Keeping them apart matters because they have different
reliability - `research` is mechanical extraction, `intel` is a researcher's reading.

  python3 merge_intel.py
"""
import json, os, re, glob, html, csv

HERE = os.path.dirname(os.path.abspath(__file__))


def norm_name(s):
    s = html.unescape(str(s or ''))
    s = s.replace('’', "'").replace('&', 'and')
    return re.sub(r'[^a-z0-9]+', '', s.lower())


def clean_rating(s):
    """'4.8/5', '5-star', '5.0' -> '4.8' / '5' / '5.0'. Anything else -> ''."""
    m = re.search(r'\d+(?:\.\d+)?', str(s or ''))
    if not m:
        return ''
    v = float(m.group(0))
    return m.group(0) if 0 < v <= 5 else ''


def clean_reviews(s):
    """'174 total ratings', '161+', '1000+' -> '174' / '161+' / '1000+'."""
    m = re.search(r'(\d[\d,]*)\s*(\+)?', str(s or ''))
    return (m.group(1).replace(',', '') + (m.group(2) or '')) if m else ''


intel = {}
for f in sorted(glob.glob(os.path.join(HERE, 'intel', 'b*.json'))):
    for row in json.load(open(f)):
        intel[norm_name(row.get('name'))] = row

leads = json.load(open(os.path.join(HERE, 'cbq3_base.json')))
matched = missing = 0
dropped_years = []
for l in leads:
    r = intel.get(norm_name(l['businessName']))
    if not r:
        l['intel'] = {}
        missing += 1
        print('  no intel for:', l['businessName'])
        continue
    matched += 1
    press = [p for p in (r.get('pressAndAwards') or []) if p.get('what') and p.get('url')]
    l['intel'] = {
        'what': html.unescape(r.get('whatTheyDo') or ''),
        'services': [html.unescape(x) for x in (r.get('services') or [])][:6],
        'prices': html.unescape(r.get('priceSignals') or ''),
        'rating': clean_rating(r.get('googleRating')),
        'reviews': clean_reviews(r.get('googleReviews')),
        'reviewThemes': [html.unescape(x) for x in (r.get('reviewThemes') or [])][:3],
        'hours': html.unescape(r.get('openingHours') or ''),
        'team': html.unescape(r.get('teamSize') or ''),
        'trading': html.unescape(r.get('yearsTrading') or ''),
        'press': [{'what': html.unescape(p['what']), 'url': p['url'], 'when': p.get('when', '')} for p in press][:3],
        'ownerNote': html.unescape(r.get('ownerNote') or ''),
        'social': html.unescape(r.get('socialFollowing') or ''),
        'sources': (r.get('sources') or [])[:5],
    }

    # The "established" year is scraped by regex, so it happily matches a year in a news item
    # ("Oct 2023 15 Years at the Helm") and calls it a founding date. The card prints that as
    # "Est. 2023" next to a business that has traded 35 years. Where the researcher independently
    # states how long they have traded and that text carries a different year, the scraped one is
    # a misread and gets dropped rather than shown. No year is invented to replace it.
    scraped = str(l.get('research', {}).get('founded') or '')
    trading = l['intel']['trading']
    if scraped and trading:
        years = re.findall(r'(?:19|20)\d{2}', trading)
        if years and scraped not in years:
            dropped_years.append((l['businessName'], scraped, trading))
            l['research']['founded'] = ''
        elif not years and re.search(r'\b(?:over\s+)?(\d{2,3})\s*(?:\+\s*)?years?\b', trading):
            claimed = int(re.search(r'\b(?:over\s+)?(\d{2,3})\s*(?:\+\s*)?years?\b', trading).group(1))
            if 2026 - int(scraped) < claimed - 5:
                dropped_years.append((l['businessName'], scraped, trading))
                l['research']['founded'] = ''

out = os.path.join(HERE, 'cbq3.json')
json.dump(leads, open(out, 'w'), ensure_ascii=False, separators=(',', ':'))
size = os.path.getsize(out)

has = lambda k: sum(1 for l in leads if (l.get('intel') or {}).get(k))
print(f'\nleads: {len(leads)} | intel matched: {matched} | no intel: {missing}')
print(f'  what they do: {has("what")}   services: {has("services")}   prices: {has("prices")}')
print(f'  google rating: {has("rating")}   review themes: {has("reviewThemes")}   hours: {has("hours")}')
print(f'  team size: {has("team")}   years trading: {has("trading")}   press/awards: {has("press")}')
print(f'  owner note: {has("ownerNote")}   sources: {has("sources")}')
print(f'bytes: {size:,}')

# Rows whose researched description contradicts the stored category, or that the researcher
# flagged. These are read by a human, not auto-applied.
if dropped_years:
    print(f'\nDropped {len(dropped_years)} scraped founding years the research contradicts:')
    for name, year, trading in dropped_years:
        print(f'  {name}: site regex said {year}, research says "{trading}"')

flags = [l for l in leads if str((l.get('intel') or {}).get('ownerNote', '')).startswith('CHECK')]
if flags:
    print('\nFlagged for a human to decide:')
    for l in flags:
        print(f"  {l['businessName']}: {l['intel']['ownerNote'][7:]}")

cols = ['Business', 'Category', 'What they do', 'Website', 'Postcode', 'Address', 'Phone 1', 'Phone 2',
        'Email 1', 'Owner / Founder', 'Role', 'Verified via', 'Companies House', 'Incorporated',
        'Company status', 'Established', 'Google rating', 'Google reviews', 'What customers say',
        'Published prices', 'Opening hours', 'Team size', 'Years trading', 'Services',
        'Press & awards', 'Owner background', 'Instagram', 'Facebook', 'Website platform',
        'Online booking', 'Sells online', 'Site last updated', 'What we can see', 'Sources']
with open('/Users/theshumba/Desktop/cambridge-boutique-leads.csv', 'w', newline='') as fh:
    w = csv.writer(fh)
    w.writerow(cols)
    for l in leads:
        s = l.get('research') or {}
        i = l.get('intel') or {}
        w.writerow([
            l['businessName'], l['industry'], i.get('what', ''), l['website'], l['postcode'], l['address'],
            (l['phones'][0]['number'] if l['phones'] else ''),
            (l['phones'][1]['number'] if len(l['phones']) > 1 else ''),
            (l['emails'][0]['address'] if l['emails'] else ''),
            '; '.join(c['name'] for c in l['contacts']),
            (l['contacts'][0]['title'] if l['contacts'] else ''),
            s.get('verifiedVia', ''), l['companiesHouse'], s.get('incorporated', ''), s.get('companyStatus', ''),
            s.get('founded', ''), i.get('rating', ''), i.get('reviews', ''), '; '.join(i.get('reviewThemes', [])),
            i.get('prices', ''), i.get('hours', ''), i.get('team', ''), i.get('trading', ''),
            '; '.join(i.get('services', [])),
            '; '.join(f"{p['what']}{(' (' + p['when'] + ')') if p.get('when') else ''}" for p in i.get('press', [])),
            i.get('ownerNote', ''), (s.get('social') or {}).get('instagram', ''),
            (s.get('social') or {}).get('facebook', ''), s.get('platform', ''), ', '.join(s.get('booking', [])),
            'yes' if s.get('ecommerce') else 'no', s.get('siteYear', ''), '; '.join(l.get('observations', [])),
            ' '.join(i.get('sources', [])),
        ])
print(f'\nCSV: {len(cols)} columns -> ~/Desktop/cambridge-boutique-leads.csv')
