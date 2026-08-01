import json,glob,re,os
from urllib.parse import urlparse
D='/Users/theshumba/.claude/projects/-Users-theshumba/f1c00501-bc1c-4e62-aa8c-40bd7e22b950/tool-results/'
PHONE=re.compile(r'(?:\+44\s?\(?0?\)?\s?|\b0)(?:1223|1954|1353|1638|1799|1440|7\d{3})[\s\)\-\.]?\d{3}[\s\-\.]?\d{3,4}\b')
EMAIL=re.compile(r'[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}')
NAME=r'(?:Dr\.?\s+|Mr\.?\s+|Mrs\.?\s+|Ms\.?\s+)?[A-Z][a-zÀ-ɏ]{1,15}(?:\s+[A-Z][a-zÀ-ɏ\'\-]{1,18}){1,2}'
OWNER_PATS=[
 re.compile(r'(?:founded|established|created|started|set up|opened)\s+(?:in\s+\d{4}\s+)?by\s+('+NAME+r')'),
 re.compile(r'('+NAME+r')[,\s]+(?:is\s+)?(?:the\s+)?(?:founder|co-founder|owner|co-owner|proprietor|managing director|principal dentist|principal|chef patron|salon owner|director and owner)'),
 re.compile(r'(?:Founder|Co-Founder|Owner|Co-Owner|Proprietor|Managing Director|Principal Dentist|Chef Patron|Director)\s*(?:&|and|/|,|:|\|| - | – )\s*(?:Director\s*)?[:\-–|]?\s*('+NAME+r')'),
 re.compile(r'('+NAME+r')\s*[\-–|,]\s*(?:Founder|Co-Founder|Owner|Co-Owner|Proprietor|Managing Director|Principal Dentist|Chef Patron)'),
 re.compile(r'(?:Meet|meet)\s+(?:the\s+)?(?:owner|founder)[,:\s]+('+NAME+r')'),
 re.compile(r"('+NAME+r')(?:'s|’s)\s+(?:vision|dream|passion)"),
]
BAD=re.compile(r'^(The|Our|We|This|Cambridge|Read More|Book Now|Find Out|Get In|Contact Us|About Us|Terms|Privacy|Opening Hours|New|All|Please|You|It|If|In|At|On|For|With|And|But|Skip To|Main Content|Menu|Home|Gift Voucher|Every|Each|A |An )', re.I)
SOCIAL={'facebook.com','instagram.com','linkedin.com','twitter.com','x.com','youtube.com','tiktok.com','pinterest.com','yelp.com','tripadvisor.co.uk','tripadvisor.com','google.com','yell.com','thomsonlocal.com','cylex-uk.co.uk','opentable.co.uk','opentable.com','thefork.co.uk','treatwell.co.uk','fresha.com','booksy.com','wikipedia.org','reddit.com','prospeo.io','apple.com','bing.com'}
recs={}
for f in sorted(glob.glob(D+'mcp-exa-*.txt')):
    try: j=json.load(open(f))
    except Exception: continue
    for r in j.get('results',[]):
        chunks=[(r.get('url',''), r.get('text') or '', r.get('title') or '')]
        for sp in (r.get('subpages') or []):
            chunks.append((sp.get('url',''), sp.get('text') or '', sp.get('title') or ''))
        base=urlparse(r.get('url','')).netloc.lower()
        base=base[4:] if base.startswith('www.') else base
        if not base or base in SOCIAL: continue
        d=recs.setdefault(base,{'title':'','ph':set(),'em':set(),'own':{},'urls':set()})
        for u,t,ti in chunks:
            if ti and (not d['title'] or len(d['title'])<8): d['title']=ti
            d['urls'].add(u)
            for p in PHONE.findall(t):
                p=re.sub(r'[\s\)\-\.]+',' ',p).strip()
                p=re.sub(r'^\+44\s*\(?0?\)?\s*','0',p)
                d['ph'].add(p)
            for e in EMAIL.findall(t):
                e=e.lower()
                if not e.endswith(('.png','.jpg','.jpeg','.gif','.webp','.svg')) and 'sentry' not in e and 'example.' not in e:
                    d['em'].add(e)
            for pat in OWNER_PATS:
                for m in pat.findall(t):
                    n=' '.join(m.split())
                    if len(n)<5 or len(n)>40 or BAD.match(n): continue
                    d['own'][n]=d['own'].get(n,0)+1
out=[]
for dom,d in recs.items():
    if not d['ph'] or not d['own']: continue
    owners=sorted(d['own'].items(), key=lambda x:-x[1])[:3]
    out.append((dom,d['title'][:60],sorted(d['ph'])[:2],sorted(d['em'])[:2],owners))
out.sort()
for o in out:
    print(f"{o[0]} :: {o[1]} :: PH={o[2]} :: EM={o[3]} :: OWN={[x[0] for x in o[4]]}")
print('=== QUALIFIED(phone+ownername):',len(out),' of ',len(recs),' domains')
# also list domains with phone but no owner name, for follow-up
gap=[d for d,v in recs.items() if v['ph'] and not v['own']]
print('=== PHONE-ONLY (need owner):',len(gap))
print('; '.join(sorted(gap)))
