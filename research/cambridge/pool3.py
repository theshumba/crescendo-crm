"""Round 3 candidate pool: parse this session's Exa results into new Cambridge domains.

Same bar as rounds 1 and 2: a candidate must show a UK phone number and a Cambridgeshire
signal, and must not already be on the list or already rejected in an earlier round.
"""
import json, glob, re, os, sys
from urllib.parse import urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
D = sys.argv[1] if len(sys.argv) > 1 else '/Users/theshumba/.claude/projects/-Users-theshumba/d1a98302-92cb-4a6a-8bb1-01160de95a28/tool-results/'

PHONE = re.compile(r'(?:\+44\s?\(?0?\)?\s?|\b0)(?:1223|1954|1353|1638|1799|1440|1480|1487|1763|1767|7\d{3})[\s\)\-\.]?\d{3}[\s\-\.]?\d{3,4}\b')
EMAIL = re.compile(r'[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}')
CAMB = re.compile(r'\b(cambridge|cambs|cambridgeshire|ely|newmarket|saffron walden|haverhill|royston|st neots|st ives|huntingdon|sawston|shelford|histon|waterbeach|cottenham|fulbourn|linton|cambourne|isleham|swavesey|bottisham|burwell|girton|soham|trumpington|cherry hinton|chesterton|arbury|milton|impington|willingham|melbourn|duxford|comberton|barton|madingley|grantchester|harston|sawtry|ramsey|march|wisbech|godmanchester|papworth|hardwick|bar hill|oakington|dry drayton|balsham|whittlesford|foxton|meldreth|great abington|stapleford|teversham|cherryhinton)\b', re.I)
BADDOM = re.compile(r'(facebook|instagram|linkedin|twitter|x\.com|youtube|tiktok|pinterest|yelp|tripadvisor|google|yell\.com|thomsonlocal|cylex|opentable|thefork|treatwell|fresha|booksy|wikipedia|reddit|prospeo|apple\.com|bing|indeed|totaljobs|reed\.co|checkatrade|trustpilot|which\.co|gov\.uk|nhs\.uk|rcvs|bupa|amazon|ebay|etsy|eventbrite|designmynight|squaremeal|hardens|michelin|timeout|visitcambridge|cambridge-news|cambridgeindependent|varsity\.co|cambsedition|cambridgeedition|velvetmag|thelisting|boutique-magazine|dineout|restaurantonline|thechefsforum|staffcanteen|primalinformation|restaurantsforkings|love-cambridge|indiecambridge|camcycle|allagents|rightmove|zoopla|onthemarket|nextdoor|substack|medium\.com|wordpress\.com|blogspot|issuu|scribd|pdf|\.gov|nearcut|setmore|gettimely|wixsite|weebly|glassdoor|companieshouse|company-information|endole|bizdb|opencorporates|thegazette|bark\.com|freeindex|thebestof|mumsnet|netmums|daynurseries|carehome|hotukdeals|groupon|wahanda|vagaro|mindbody|classpath|eventful|meetup|whatsonin|hitched|bridebook|guides for brides|guidesforbrides|weddingwire|theknot|yelp|justdial|scoot|touchlocal|192\.com|streetcheck|ukbusiness|b2bindex|kompass|europages|bizvibe|dnb\.com|creditsafe|companycheck|tuugo|hotfrog|brownbook|misterwhat|infoisinfo|cybo|nicelocal|wheree|storeboard|manta|yellowpages|localsearch|findopen|opendi|bizapedia|pagesjaunes|golocal|citysearch|superpages|merchantcircle|angi|thumbtack|houzz|homeadvisor|porch|nextdoor)', re.I)

# Everything already seen: the 81 live leads, plus every domain crawled or rejected in rounds 1-2.
known = set()
for lead in json.load(open(os.path.join(HERE, 'cbq2.json'))):
    d = urlparse(lead['website']).netloc.lower()
    known.add(d[4:] if d.startswith('www.') else d)
for fn in ('old.txt', 'newdoms.txt'):
    p = os.path.join(HERE, fn)
    if os.path.exists(p):
        for line in open(p):
            d = line.split('\t')[0].strip().lower()
            if d:
                known.add(d[4:] if d.startswith('www.') else d)

recs = {}
files = sorted(glob.glob(D + 'mcp-exa-*.txt'))
for f in files:
    try:
        j = json.load(open(f))
    except Exception:
        continue
    for r in j.get('results', []):
        base = urlparse(r.get('url', '')).netloc.lower()
        base = base[4:] if base.startswith('www.') else base
        if not base or BADDOM.search(base):
            continue
        d = recs.setdefault(base, {'t': '', 'ph': set(), 'em': set(), 'camb': False, 'txt': 0})
        pages = [(r.get('text') or '', r.get('title') or '')] + \
                [(s.get('text') or '', s.get('title') or '') for s in (r.get('subpages') or [])]
        for t, ti in pages:
            if ti and not d['t']:
                d['t'] = ti
            d['txt'] += len(t)
            if CAMB.search(t) or CAMB.search(base):
                d['camb'] = True
            for p in PHONE.findall(t):
                p = re.sub(r'[\s\)\-\.]+', ' ', p).strip()
                p = re.sub(r'^\+44\s*\(?0?\)?\s*', '0', p)
                d['ph'].add(p)
            for e in EMAIL.findall(t):
                e = e.lower()
                if not e.endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg')) and 'sentry' not in e:
                    d['em'].add(e)

new = [(k, v) for k, v in recs.items() if v['ph'] and v['camb'] and k not in known]
new.sort()
print(f'search files: {len(files)} | domains seen: {len(recs)} | already known: {len(known)}')
print(f'NEW with phone + Cambridge signal: {len(new)}')
with open(os.path.join(HERE, 'r3_candidates.tsv'), 'w') as fh:
    for k, v in new:
        fh.write(f"{k}\t{v['t'][:70]}\t{';'.join(sorted(v['ph'])[:2])}\t{';'.join(sorted(v['em'])[:2])}\n")
for k, v in new:
    print(f"{k} | {v['t'][:56]} | {sorted(v['ph'])[:1]}")
