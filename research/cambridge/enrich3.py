"""Round 3 site crawl. Same extraction as enrich.py, but repo-relative and re-runnable.

Reads a tab-separated domain list, crawls up to 4 pages per site into a local cache,
and writes structured facts read off the business's own pages. Nothing here infers:
every field is either present on the site or left empty.

  python3 enrich3.py r3_domains.txt r3_enriched.json
"""
import re, html, json, os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, 'pages3')
os.makedirs(CACHE, exist_ok=True)
SRC = os.path.join(HERE, sys.argv[1] if len(sys.argv) > 1 else 'r3_domains.txt')
OUT = os.path.join(HERE, sys.argv[2] if len(sys.argv) > 2 else 'r3_enriched.json')

UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36'
PATHS = ['', '/about', '/about-us', '/contact', '/contact-us', '/our-story', '/meet-the-team', '/team', '/who-we-are']

doms = []
for line in open(SRC):
    line = line.rstrip('\n')
    if not line.strip():
        continue
    p = line.split('\t')
    doms.append((p[0], p[1] if len(p) > 1 else '', p[2] if len(p) > 2 else ''))


def get(u):
    key = os.path.join(CACHE, re.sub(r'[^a-zA-Z0-9]', '_', u)[:130] + '.html')
    if os.path.exists(key):
        return open(key, errors='ignore').read()
    r = subprocess.run(['curl', '-sL', '--max-time', '18', '--compressed', '-A', UA, u],
                       capture_output=True, text=True, errors='ignore')
    s = r.stdout or ''
    open(key, 'w').write(s)
    return s


def crawl(item):
    dom = item[0]
    pages = []
    for p in PATHS:
        if len(pages) >= 4:
            break
        s = get('https://' + dom + p)
        if len(s) > 1500:
            pages.append((p or '/', s))
    return dom, pages


POST = re.compile(r'\b([A-Z]{1,2}\d{1,2}[A-Z]?)\s*(\d[A-Z]{2})\b')
PHONE = re.compile(r'(?:\+44\s?\(?0?\)?\s?|\b0)(?:1\d{3}|7\d{3}|20)[\s\)\-\.]?\d{3}[\s\-\.]?\d{3,4}\b')
EMAIL = re.compile(r'[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}')
YEAR = re.compile(r'(?:established|founded|since|est\.?|serving .{0,20}since|trading since|opened)\D{0,15}(19\d{2}|20[0-2]\d)', re.I)
COPY = re.compile(r'(?:©|&copy;|copyright)\D{0,20}(20[0-2]\d)', re.I)
SOCIAL = {'instagram': r'instagram\.com/([A-Za-z0-9_.]{2,30})',
          'facebook': r'facebook\.com/([A-Za-z0-9_.\-]{2,40})',
          'linkedin': r'linkedin\.com/(?:company|in)/([A-Za-z0-9_\-]{2,50})',
          'x': r'(?:twitter|x)\.com/([A-Za-z0-9_]{2,20})'}
PLATFORM = [('Shopify', r'cdn\.shopify\.com|shopify'), ('Squarespace', r'squarespace'), ('Wix', r'wix\.com|wixstatic'),
            ('WooCommerce', r'woocommerce'), ('WordPress', r'wp-content|wp-includes'), ('Webflow', r'webflow'),
            ('GoDaddy', r'godaddy|starfield'), ('Weebly', r'weebly')]
BOOKING = [('Fresha', r'fresha\.com'), ('Treatwell', r'treatwell'), ('Booksy', r'booksy'), ('Setmore', r'setmore'),
           ('Calendly', r'calendly'), ('OpenTable', r'opentable'), ('ResDiary', r'resdiary'),
           ('SquareUp', r'squareup\.com/appointments'), ('Acuity', r'acuityscheduling'), ('Timely', r'gettimely'),
           ('Phorest', r'phorest'), ('DesignMyNight', r'designmynight'), ('SimplyBook', r'simplybook'),
           ('Ovatu', r'ovatu'), ('Cliniko', r'cliniko'), ('Jane', r'janeapp'), ('MINDBODY', r'mindbody')]
ECOM = r'add[ _-]?to[ _-]?(cart|basket)|/cart|/basket|checkout|woocommerce-cart|shopify-section'
KEYOWN = re.compile(r"(founded by|co-?founder|founder|owner|proprietor|established by|managing director|principal|chef patron|husband and wife|family[- ]run|run by|my name is|i'?m |meet the team|our director|salon owner|clinic director|head (?:stylist|therapist|coach|groomer)|practice (?:owner|principal)|lead (?:vet|dentist|therapist))", re.I)
NAMEY = re.compile(r"\b(?:Dr\.?\s+)?[A-Z][a-zà-ÿ']{2,14}\s+[A-Z][a-zà-ÿ'\-]{2,18}\b")


def txt(h):
    h = re.sub(r'<(script|style|noscript)[^>]*>.*?</\1>', ' ', h, flags=re.S | re.I)
    h = re.sub(r'<[^>]+>', ' ', h)
    return re.sub(r'\s+', ' ', html.unescape(h))


out = {}
with ThreadPoolExecutor(max_workers=16) as ex:
    crawled = list(ex.map(crawl, doms))
cmap = dict(crawled)

for dom, biz, cat in doms:
    pages = cmap.get(dom, [])
    if not pages:
        out[dom] = {'biz': biz, 'cat': cat, 'dead': True}
        continue
    allh = ' '.join(p[1] for p in pages)
    allt = ' '.join(txt(p[1]) for p in pages)
    rec = {'biz': biz, 'cat': cat, 'dead': False}
    pcs = [' '.join(m) for m in POST.findall(allt)]
    rec['postcode'] = max(set(pcs), key=pcs.count) if pcs else ''
    if rec['postcode']:
        i = allt.find(rec['postcode'].split()[0])
        rec['addr'] = re.sub(r'\s+', ' ', allt[max(0, i - 90):i + 9]).strip()
    else:
        rec['addr'] = ''
    ph = []
    for p in PHONE.findall(allt) + re.findall(r'tel:([+0-9()\s\-]{9,20})', allh):
        p = re.sub(r'[^\d+]', '', p)
        p = re.sub(r'^\+44', '0', p)
        if len(p) == 11 and p.startswith('0'):
            ph.append(p)
    rec['phones'] = sorted(set(ph), key=ph.index)[:4]
    em = [e.lower() for e in EMAIL.findall(allt) + re.findall(r'mailto:([^"\'?&>]+)', allh)]
    em = [e for e in em if not e.endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg'))
          and 'sentry' not in e and 'example' not in e and '@2x' not in e]
    rec['emails'] = sorted(set(em))[:4]
    rec['social'] = {}
    for k, pat in SOCIAL.items():
        m = re.findall(pat, allh, re.I)
        m = [x for x in m if x.lower() not in ('sharer', 'share', 'tr', 'home', 'pages', 'profile', 'plugins',
                                               'dialog', 'intent', 'p', 'photo', 'groups', 'events', 'permalink',
                                               'story.php', 'login')]
        if m:
            rec['social'][k] = max(set(m), key=m.count)
    y = YEAR.findall(allt)
    rec['founded'] = min(y) if y else ''
    c = COPY.findall(allh)
    rec['copyright'] = max(c) if c else ''
    rec['platform'] = next((n for n, p in PLATFORM if re.search(p, allh, re.I)), 'Custom/unknown')
    rec['booking'] = [n for n, p in BOOKING if re.search(p, allh, re.I)]
    rec['ecommerce'] = bool(re.search(ECOM, allh, re.I))
    rec['mobile'] = bool(re.search(r'name=["\']viewport["\']', allh, re.I))
    rec['pages'] = [p[0] for p in pages]
    sn = []
    for m in KEYOWN.finditer(allt):
        s = allt[max(0, m.start() - 120):m.start() + 170]
        if NAMEY.search(s) and s not in sn:
            sn.append(s)
    rec['ownsnips'] = sn[:4]
    rec['title'] = (re.search(r'<title[^>]*>(.*?)</title>', pages[0][1], re.S | re.I) or [None, ''])[1].strip()[:120]
    out[dom] = rec

json.dump(out, open(OUT, 'w'), ensure_ascii=False, indent=1)
alive = [d for d, r in out.items() if not r.get('dead')]
print('crawled:', len(alive), 'of', len(doms), '| dead:', len(doms) - len(alive))
print('with postcode:', sum(1 for d in alive if out[d]['postcode']))
print('with phone:', sum(1 for d in alive if out[d]['phones']))
print('with email:', sum(1 for d in alive if out[d]['emails']))
print('with owner snippets:', sum(1 for d in alive if out[d]['ownsnips']))
