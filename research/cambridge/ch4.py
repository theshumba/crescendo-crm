"""Companies House match for round 3, plus the accounts detail rounds 1-2 did not pull.

Matching stays STRICT: a normalised-equality hit on either the business name or the domain
stem, and the registered address must be local. Fuzzy matching was tried in round 2 and
produced confident-looking wrong directors, so it is not coming back.

  python3 ch4.py r3_domains.txt r3_ch.json
"""
import re, html, json, os, time, urllib.parse, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = 'https://find-and-update.company-information.service.gov.uk'
UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36'
CACHE = os.path.join(HERE, 'ch3')
os.makedirs(CACHE, exist_ok=True)
SRC = os.path.join(HERE, sys.argv[1] if len(sys.argv) > 1 else 'r3_domains.txt')
OUT = os.path.join(HERE, sys.argv[2] if len(sys.argv) > 2 else 'r3_ch.json')


def get(url, key):
    p = os.path.join(CACHE, re.sub(r'[^a-zA-Z0-9]', '_', key)[:120] + '.html')
    if os.path.exists(p) and os.path.getsize(p) > 800:
        return open(p, errors='ignore').read()
    r = subprocess.run(['curl', '-sL', '--max-time', '30', '-A', UA, url], capture_output=True, text=True)
    open(p, 'w').write(r.stdout)
    time.sleep(0.25)
    return r.stdout


LOCAL = re.compile(r'\b(CB\d|PE\d|SG8|IP\d|CO\d|Cambridge|Cambs|Cambridgeshire|Ely|Newmarket|Saffron Walden|Haverhill|Royston|St Neots|St Ives|Huntingdon|Sawston|Shelford|Histon|Waterbeach|Cottenham|Fulbourn|Linton|Cambourne|Isleham|Swavesey|Bottisham|Burwell|Girton|Soham|Kingston|Milton|Willingham|Melbourn|Duxford|Comberton|Barton|Impington|Teversham|Sawtry|March|Wisbech|Godmanchester|Over|Lode|Bourn|Oakington|Papworth|Hardwick|Balsham|Whittlesford|Foxton|Meldreth|Stapleford)\b', re.I)


def norm(s):
    s = s.lower()
    s = re.sub(r'\b(ltd|limited|llp|plc|the|and|co|company|uk|group)\b', ' ', s)
    s = re.sub(r'&', ' ', s)
    return re.sub(r'[^a-z0-9]+', '', s)


def sc(s):
    return re.sub(r'cambridgeshire|cambridge|cambs', '', s)


def search(name):
    h = get(BASE + '/search/companies?q=' + urllib.parse.quote(name), 's_' + name)
    out = []
    for m in re.finditer(r'<li class="type-company">(.*?)</li>', h, re.S):
        b = m.group(1)
        num = re.search(r'/company/(\w+)', b)
        nm = re.search(r'title="View company">\s*(.*?)\s*</a>', b, re.S)
        meta = re.search(r'class="meta crumbtrail">\s*(.*?)\s*</p>', b, re.S)
        addr = re.findall(r'<p>(.*?)</p>', b, re.S)
        if not (num and nm):
            continue
        out.append({'num': num.group(1), 'name': html.unescape(re.sub(r'\s+', ' ', nm.group(1))),
                    'meta': html.unescape(re.sub(r'\s+', ' ', meta.group(1) if meta else '')),
                    'addr': html.unescape(re.sub(r'\s+', ' ', addr[-1])) if addr else ''})
    return out


def officers(num):
    h = get(BASE + f'/company/{num}/officers', 'o_' + num)
    res = []
    for m in re.finditer(r'<span id="officer-name-(\d+)">(.*?)</span>', h, re.S):
        i = m.group(1)
        nm = html.unescape(re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', m.group(2)))).strip()

        def f(pat):
            g = re.search(pat.replace('N', i), h, re.S)
            return html.unescape(re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', g.group(1)))).strip() if g else ''
        res.append({'name': nm, 'status': f(r'id="officer-status-tag-N"[^>]*>(.*?)</span>') or 'Active',
                    'role': f(r'id="officer-role-N"[^>]*>(.*?)</dd>'),
                    'occ': f(r'id="officer-occupation-N"[^>]*>(.*?)</dd>'),
                    'appointed': f(r'id="officer-appointed-on-N"[^>]*>(.*?)</dd>'),
                    'nat': f(r'id="officer-nationality-N"[^>]*>(.*?)</dd>')})
    return res


def profile(num):
    h = get(BASE + f'/company/{num}', 'c_' + num)

    def f(pat):
        g = re.search(pat, h, re.S)
        return html.unescape(re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', g.group(1)))).strip() if g else ''
    sic = [html.unescape(re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', x))).strip()
           for x in re.findall(r'id="sic\d+">(.*?)</span>', h, re.S)]
    return {'incorporated': f(r'id="company-creation-date"[^>]*>(.*?)</dd>'),
            'status': f(r'id="company-status"[^>]*>(.*?)</dd>'),
            'type': f(r'id="company-type"[^>]*>(.*?)</dd>'),
            'sic': sic[:3],
            'accountsTo': f(r'id="last-accounts-made-up-to"[^>]*>(.*?)</'),
            'accountsDue': f(r'id="accounts-next-due"[^>]*>(.*?)</'),
            'regAddress': f(r'id="reg-address"[^>]*>(.*?)</dd>')}


rows = []
for line in open(SRC):
    if line.strip():
        p = line.rstrip('\n').split('\t')
        rows.append((p[0], p[1], p[2] if len(p) > 2 else ''))

# The crawled <title> widens the SEARCH, but never the accept test. A truncated title
# fragment ("Dog groomer" from "Dog groomer | Karen's Grooming") normalises to a generic
# string that equals a generic company name, which is how round 3 first matched
# karensgrooming.co.uk to an unrelated THE DOG GROOMER LTD. Search wide, accept narrow.
titles = {}
enr = os.path.join(HERE, 'r3_enriched.json')
if os.path.exists(enr):
    for dom, rec in json.load(open(enr)).items():
        t = (rec.get('title') or '').strip()
        if t:
            titles[dom] = t

MIN_BASIS = 6  # a normalised name shorter than this is too generic to accept on equality

res = {}
for dom, name, cat in rows:
    best = None
    stem = dom.split('.')[0]
    title = titles.get(dom, '')
    # Accept only on full-strength identity: the whole business name, the whole page title,
    # or the domain stem. Never a prefix or a fragment of any of them.
    bases = {b for b in (sc(norm(name)), sc(norm(stem)), sc(norm(title))) if len(b) >= MIN_BASIS}
    queries = {name, ' '.join(name.split()[:2]), title.split('|')[0].strip(), stem}
    for q in [x for x in queries if x and len(x) > 2]:
        try:
            cands = search(q)
        except Exception:
            cands = []
        for c in cands:
            if 'Dissolved' in c['meta'] or 'Liquidation' in c['meta']:
                continue
            cn = sc(norm(c['name']))
            if cn and cn in bases and LOCAL.search(c['addr']):
                best = c
                best['matchedOn'] = ('domain stem' if cn == sc(norm(stem))
                                     else 'business name' if cn == sc(norm(name)) else 'page title')
                break
        if best:
            break
    if not best:
        continue
    try:
        offs = [o for o in officers(best['num']) if o['status'].lower() != 'resigned']
    except Exception:
        offs = []
    if not offs:
        continue
    try:
        prof = profile(best['num'])
    except Exception:
        prof = {}
    res[dom] = {'co': best, 'dirs': offs[:5], 'prof': prof}
    print(f"{dom} | {best['name']} ({best['num']}) | {prof.get('incorporated', '')} | "
          f"{'; '.join(o['name'] for o in offs[:2])}", flush=True)

json.dump(res, open(OUT, 'w'), indent=1)
print('=== matched:', len(res), 'of', len(rows))
