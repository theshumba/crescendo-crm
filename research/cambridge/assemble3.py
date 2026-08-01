"""Assemble the round 3 additions.

Every row below was read by hand off the business's own site and, where a company exists,
corroborated against an active Companies House directorship. The bar is unchanged from
rounds 1 and 2: a working website, a direct phone number and a FULL owner name. A first
name on its own does not qualify, because the rep opens the call with that name.

Rejected in this round and why, so a fourth round does not re-litigate it:
  chameleonstudios.co.uk, cyclecentric.com  - site does not load, so nothing is verifiable
  cambscuisine.co.uk                        - group site, no direct phone published
  artofclean, autokare, cosmexclinic, cuckoo-bridge, eclipsedesign, gardenfarmflowers,
  irisandviolet, kingswaycycles, oakingtondogdaycare, oxbowandpeach, scotsdales,
  trotteranddeane, willinghamfuneralservice, willowgrange, cambridgeacademy
                                            - no owner name published anywhere on the site
  karensgrooming (Karen and Tony), karimwellness (Karim), savvy-design (Paul),
  whitewonderselypetservices (Raimonda)     - first name only, same rule as round 2's seven
  peasgoodandskeates                        - only a historical 1847 founder, no current owner
  cambridgeacademictuition, kindrednurseries, cambridgecleans, freewheel, printcambridge,
  sportsshopuk, cambridgemakers, twitchettarchitect
                                            - not a local independent, or not verifiable
"""
import json, os, re, csv

HERE = os.path.dirname(os.path.abspath(__file__))
ENR = json.load(open(os.path.join(HERE, 'r3_enriched.json')))
CH = json.load(open(os.path.join(HERE, 'r3_ch.json')))


def ch_name(s):
    """Companies House prints 'SURNAME, First Middle, Title.' - turn it into a usable name."""
    s = re.sub(r',\s*(Mr|Mrs|Ms|Miss|Dr|Prof|Sir|Dame)\.?\s*$', '', s.strip(), flags=re.I)
    if ',' in s:
        sur, rest = s.split(',', 1)
        sur = sur.strip().title()
        rest = rest.strip()
        return f'{rest} {sur}'.strip()
    return s.title()


# dom -> (business name, category, town, owner override, role override)
# owner override is used only where the site names the owner and Companies House does not.
ROWS = [
    # --- Companies House confirmed ---
    ('cambridgeclearbeauty.co.uk', 'Cambridge Clear Beauty', 'Cosmetic surgery clinic', 'Sawston', None, 'Consultant plastic surgeon and director'),
    ('cambridgeimprint.co.uk', 'Cambridge Imprint', 'Patterned paper & homeware', 'Cambridge', None, 'Founding partner'),
    ('cambridgeosteopathy.co.uk', 'Cambridge Osteopathy', 'Osteopathy', 'Cambridge', None, 'Osteopath and director'),
    ('cambridgepianos.co.uk', 'Cambridge Pianoforte', 'Piano sales & tuning', 'Cambridge', None, 'Founding partner'),
    ('camlang.co.uk', 'The Cambridge Centre for Languages', 'Language school', 'Cambridge', None, 'Director'),
    ('highfieldeventgroup.com', 'The Highfield Event Group', 'Marquee & event hire', 'Burwell', None, 'Director'),
    ('kcskriscleaningservices.co.uk', 'KCS Kris Cleaning Services', 'Cleaning services', 'Cambridge', None, 'Director'),
    ('lighthousetoys.com', 'Lighthouse Toys', 'Toy shop', 'Cambridge', None, 'Director'),
    ('montessoricambridge.co.uk', 'Cambridge Montessori Nursery School', 'Nursery & pre-school', 'Cambridge', None, 'Director'),
    ('offgriddesign.co.uk', 'Off Grid Design', 'Design & branding studio', 'Ely', None, 'Director'),
    ('questbrothersclassiccars.com', 'Quest Brothers Classic Cars', 'Classic car restoration', 'St Ives', None, 'Director'),
    ('reform-fit.co.uk', 'Reform Fit', 'Pilates & yoga studio', 'Saffron Walden', None, 'Director'),
    ('regency-autos.co.uk', 'Regency Autos', 'Car garage', 'Cambridge', None, 'Director'),
    ('regencyfuneraldirectors.co.uk', 'Regency Funeral Directors', 'Funeral directors', 'Huntingdon', None, 'Director'),
    ('tekmotiv.co.uk', 'Tekmotiv', 'Electric bike shop', 'Saffron Walden', None, 'Director'),
    ('tevershammotors.co.uk', 'Teversham Motors', 'Garage & MOT centre', 'Cambridge', None, 'Director'),
    # Both of these matched Companies House on the business name in the first pass. The
    # tightened accept test drops them only because "company" is stripped from the registered
    # name but not from the run-together domain stem, so the two normalise differently. The
    # company number is carried explicitly rather than loosening the matcher.
    ('cambridgecyclecompany.co.uk', 'Cambridge Cycle Company', 'Bike shop', 'Sawston', 'Darren Peter Sansom', 'Director'),
    ('cambridgesigncompany.co.uk', 'The Cambridge Sign Company', 'Sign maker & vehicle graphics', 'St Ives', 'Nicholas Charles Robert Dowell-McGrillan', 'Director'),
    # --- owner named on their own site, no company match ---
    ('acs-clean.co.uk', 'Advanced Cleaning Services', 'Commercial cleaning', 'Ely', 'Chris Broadley', 'Owner and Managing Director'),
    ('cambridgelaserclinic.com', 'Cambridge Laser Clinic', 'Laser & skin clinic', 'Cambridge', 'Dr Nathan Holt', 'Founder'),
    ('cambridgepeacefulpets.com', 'Cambridge Peaceful Pets', 'Home visit veterinary service', 'Cambridge', 'Dr Edward Kingsbury', 'Veterinary surgeon and owner'),
    ('gda.dance', 'Generations Dance Academy', 'Dance school', 'Huntingdon', 'Wendy Burke', 'Principal'),
    ('goldstraw.co.uk', 'Goldstraw Goldsmiths', 'Jeweller & goldsmith', 'St Neots', 'Paul Goldstraw', 'Owner and Founder'),
    ('heathfruitfarm.co.uk', 'Heath Fruit Farm', 'Fruit farm & farm shop', 'Bluntisham', 'Robert Bousfield', 'Owner'),
    ('lifeonabikestore.co.uk', 'Life on a Bike', 'Bike shop & workshop', 'Cambridge', 'Jef Sharp', 'Owner'),
    ('movefreechiropractic.co.uk', 'Move Free Chiropractic', 'Chiropractic clinic', 'Cambridge', 'Dr Kyle Wingate', 'Clinic Founder'),
    ('sarahkeybooks.co.uk', 'Sarah Key Books, The Haunted Bookshop', 'Antiquarian bookshop', 'Cambridge', 'Sarah Key', 'Owner'),
    ('traditionalrestorationscambridge.co.uk', 'Traditional Restorations', 'Furniture restoration', 'Sawston', 'Jon Porter', 'Owner'),
]

# Phones the site publishes but the text extractor loses to markup. Both were confirmed by
# grepping the cached page: the number is on their own site, it is just split across tags.
PHONE_FIX = {'regencyfuneraldirectors.co.uk': ['01480759408']}

# The address extractor grabs 90 characters of running text before the postcode, so it drags in
# whatever sentence happened to precede it ("r clients Advanced Cleaning Services The Barn...").
# These are the same strings trimmed back to the address the business actually publishes: no
# detail is added, only surrounding prose removed. An empty value falls back to the postcode.
ADDRESS = {
    'cambridgeclearbeauty.co.uk': 'Building G, South Cambs Business Park, Babraham Road, Sawston, Cambridge CB22 3JH',
    'cambridgeimprint.co.uk': "Unit 12, Chesterton Mill, French's Road, Cambridge, CB4 3NP",
    'cambridgeosteopathy.co.uk': 'Camboro Business Park, Oakington Road, Girton, Cambridge CB3 0QH',
    'cambridgepianos.co.uk': '10-12 Kings Hedges Road, Cambridge CB4 2PA',
    'camlang.co.uk': 'Cambridge House, Camboro Business Park, Girton, Cambridge, CB3 0QH',
    'highfieldeventgroup.com': 'Klondyke Farm, Broads Rd, Cambridge, CB25 0BQ',
    'montessoricambridge.co.uk': '73a Tenison Road, Cambridge, CB1 2DG',
    'offgriddesign.co.uk': 'Appletree House, Hod Hall Lane, Haddenham, Ely, Cambridgeshire, CB6 3UX',
    'questbrothersclassiccars.com': '8b Harding Way, St. Ives, Huntingdon, Cambs PE27 3WR',
    'reform-fit.co.uk': 'The Forge, Rectory Farm Barns, Walden Rd, Little Chesterford, Saffron Walden CB10 1UD',
    'regency-autos.co.uk': '120 Church End, Cambridge CB1 3LB',
    'regencyfuneraldirectors.co.uk': '36 Cromwell House, High Street, Kimbolton, Huntingdon, PE28 0HA',
    'tekmotiv.co.uk': '12 Dencora Park, Saffron Walden, Essex CB11 3GB',
    'tevershammotors.co.uk': '',  # site never prints a street address, only the postcode district
    'cambridgecyclecompany.co.uk': 'Langford Arch Industrial Estate, London Rd, Pampisford, Cambridge CB22 3FX',
    'cambridgesigncompany.co.uk': 'Unit 2 Meridian Court, Compass Point Business Park, St. Ives, Cambridgeshire, PE27 5FH',
    'acs-clean.co.uk': 'The Barn, Fordham House Estate, Fordham, Cambridgeshire CB7 5LL',
    'cambridgelaserclinic.com': '7 Brooklands Ave, Cambridge, CB2 8BB',
    'gda.dance': '10 Orchard Lane, Huntingdon, Cambs, PE29 3QT',
    'goldstraw.co.uk': '14 High Street, St Neots, PE19 1JA',
    'heathfruitfarm.co.uk': 'The Heath, Bluntisham, Cambs PE28 3LQ',
    'lifeonabikestore.co.uk': '171 Mill Road, Cambridge CB1 3AN',
    'movefreechiropractic.co.uk': '91 High Street, Longstanton, Cambridge CB24 3BS',
    'sarahkeybooks.co.uk': "9 St Edward's Passage, Cambridge CB2 3PJ",
    'traditionalrestorationscambridge.co.uk': '5 Babraham Road, Sawston, Cambridge CB22 3DQ',
}

SERVICE = re.compile(r'salon|barber|dentist|dental|clinic|osteo|physio|podiat|chiro|pilates|massage|beauty|hair|brow|nail|tattoo|piercing|grooming|driving|counsel|audiolog|tennis|climb|martial|punting|photograph|golf|dance|school|nursery|veterinar|funeral|cleaning|garage|mot|restoration|hire|surgery|language|tuition|design', re.I)
RETAIL = re.compile(r'shop|retail|jewell|butcher|boutique|antique|wine|gift|homeware|toy|art supplies|furniture|bridal|menswear|optician|farm shop|grocery|deli|bakery|memorabilia|vintage|bookshop|goldsmith|bike|piano|paper', re.I)


def obs(cat, rec):
    o = []
    svc = bool(SERVICE.search(cat))
    ret = bool(RETAIL.search(cat))
    booking = rec.get('booking') or []
    if svc and not booking:
        o.append('no online booking on the site, so every appointment has to come through the phone')
    if booking:
        o.append('takes bookings through ' + ', '.join(booking))
    if ret and not rec.get('ecommerce'):
        o.append('no online shop, so the business only sells in person')
    if rec.get('ecommerce'):
        o.append('sells online already (' + rec.get('platform', '') + ')')
    if rec.get('platform') in ('Wix', 'GoDaddy', 'Weebly'):
        o.append('site is built on ' + rec['platform'] + ', a DIY builder')
    cp = rec.get('copyright')
    if cp and int(cp) < 2025:
        o.append('site footer still reads ' + cp + ', so it has not been touched in a while')
    if not (rec.get('social') or {}).get('instagram'):
        o.append('no Instagram linked from the site')
    if not rec.get('emails'):
        o.append('no email address published, phone is the only way in')
    if not rec.get('mobile'):
        o.append('no mobile viewport set, so the site will not scale on a phone')
    return o


def slug(s):
    return 'cbq-' + re.sub(r'-+', '-', re.sub(r'[^a-z0-9]+', '-', s.lower())).strip('-')


rows = []
for dom, biz, cat, town, owner_override, role in ROWS:
    rec = ENR.get(dom, {})
    ch = CH.get(dom)
    owners, ch_num, prof = [], '', {}
    if ch and not owner_override:
        seen = set()
        for o in ch['dirs']:
            n = ch_name(o['name'])
            if n.lower() not in seen:
                owners.append(n)
                seen.add(n.lower())
        ch_num = ch['co']['num']
        prof = ch['prof']
    elif owner_override:
        owners = [owner_override]
        if dom == 'cambridgecyclecompany.co.uk':
            ch_num = '13149055'
        if dom == 'cambridgesigncompany.co.uk':
            ch_num = '08912492'
    if not owners:
        raise SystemExit(f'no owner for {dom}')

    phones = PHONE_FIX.get(dom) or rec.get('phones') or []
    if not phones:
        raise SystemExit(f'no phone for {dom}')
    # Match how rounds 1-2 stored numbers: 5-digit area code, space, the rest.
    phones = [re.sub(r'^(\d{5})(\d{6})$', r'\1 \2', p) for p in phones]
    emails = (rec.get('emails') or [])[:3]
    ob = obs(cat, rec)
    verified = (f'Companies House, company no. {ch_num}' if ch_num else 'Stated on the business website')
    addr = ADDRESS.get(dom, rec.get('addr', ''))

    parts = [f"Independent {cat.lower()}" + (f" at {addr or rec.get('postcode')}"
             if (addr or rec.get('postcode')) else f" in {town}") + "."]
    parts.append('Owner: ' + ', '.join(owners) + (f' ({role.lower()}).' if role else '.'))
    if prof.get('incorporated'):
        parts.append(f"Company incorporated {prof['incorporated']}" +
                     (f", status {prof['status'].lower()}" if prof.get('status') else '') + '.')
    elif rec.get('founded'):
        parts.append(f"Site says the business was established {rec['founded']}.")
    if prof.get('sic'):
        parts.append('Registered activity: ' + '; '.join(prof['sic'][:2]) + '.')
    if ob:
        parts.append('What we can see from their site: ' + '; '.join(ob) + '.')
    parts.append('Owner name verified via ' + verified + '.')
    desc = re.sub(r'\s+', ' ', ' '.join(parts)).strip()

    rows.append({
        'id': slug(biz), 'businessName': biz, 'industry': cat, 'website': 'https://' + dom,
        'address': (addr or rec.get('postcode') or town),
        'postcode': rec.get('postcode', ''), 'town': town,
        'phones': [{'number': p} for p in phones],
        'emails': [{'address': e} for e in emails],
        'contacts': [{'name': o, 'title': role or 'Owner',
                      'phone': phones[0] if i == 0 else '',
                      'email': (emails[0] if (i == 0 and emails) else '')} for i, o in enumerate(owners)],
        'description': desc, 'source': 'research', 'status': 'qualified', 'list': 'cambridge-boutique',
        'companiesHouse': ch_num,
        'qualification': {'strategyDesign': '', 'experienceDesign': '', 'digitalCommerce': '', 'growthIntent': '',
                          'weaknessesOpportunities': (('From their own site: ' + '; '.join(ob) + '.') if ob else '')},
        'research': {'incorporated': prof.get('incorporated', ''), 'companyStatus': prof.get('status', ''),
                     'sic': prof.get('sic', []), 'founded': rec.get('founded', ''),
                     'social': rec.get('social', {}), 'platform': rec.get('platform', 'Custom/unknown'),
                     'booking': rec.get('booking', []), 'ecommerce': bool(rec.get('ecommerce')),
                     'mobile': bool(rec.get('mobile')), 'siteYear': rec.get('copyright', ''),
                     'verifiedVia': verified,
                     'accountsTo': prof.get('accountsTo', ''), 'accountsDue': prof.get('accountsDue', '')},
        'observations': ob})

existing = json.load(open(os.path.join(HERE, 'cbq2.json')))
have = {r['id'] for r in existing}
clash = [r['id'] for r in rows if r['id'] in have]
assert not clash, f'id clash with the live list: {clash}'
ids = [r['id'] for r in rows]
assert len(set(ids)) == len(ids), [i for i in ids if ids.count(i) > 1]

json.dump(rows, open(os.path.join(HERE, 'r3_new.json'), 'w'), ensure_ascii=False, indent=1)

# The merged, name-sorted list that merge_intel.py then hangs the research brief off.
merged = sorted(existing + rows, key=lambda r: r['businessName'].lower())
json.dump(merged, open(os.path.join(HERE, 'cbq3_base.json'), 'w'), ensure_ascii=False, indent=1)
feed = [{'name': r['businessName'], 'website': r['website'], 'town': r['town'],
         'category': r['industry'], 'owner': (r['contacts'][0]['name'] if r['contacts'] else '')}
        for r in merged]
json.dump(feed, open(os.path.join(HERE, 'enrich_feed.json'), 'w'), ensure_ascii=False, indent=1)

print('new records:', len(rows))
print('Companies House confirmed:', sum(1 for r in rows if r['companiesHouse']))
print('website stated:', sum(1 for r in rows if not r['companiesHouse']))
print('with email:', sum(1 for r in rows if r['emails']))
print('total list will be:', len(existing) + len(rows))
