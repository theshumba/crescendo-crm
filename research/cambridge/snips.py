import json,glob,re
from urllib.parse import urlparse
D='/Users/theshumba/.claude/projects/-Users-theshumba/f1c00501-bc1c-4e62-aa8c-40bd7e22b950/tool-results/'
PHONE=re.compile(r'(?:\+44\s?\(?0?\)?\s?|\b0)(?:1223|1954|1353|1638|1799|1440|7\d{3})[\s\)\-\.]?\d{3}[\s\-\.]?\d{3,4}\b')
EMAIL=re.compile(r'[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}')
KEY=re.compile(r'(founded by|founder|co-founder|owner|proprietor|established by|managing director|principal dentist|chef patron|started (?:the|her|his|our)|opened (?:the|her|his|our)|husband and wife|family[- ]run|meet the team|our director)',re.I)
EXCL={'allagents.co.uk','andrewlynes.substack.com','bupa.co.uk','finder.bupa.co.uk','confetti.co.uk','cvsvets.com','medivetgroup.com','vets4pets.com','findavet.rcvs.org.uk','vetverified.com','nextdoor.co.uk','rmwilliams.com','jewelersaround.co.uk','weddingmall.co.uk','ukbride.co.uk','sausagereview.co.uk','visitcambridge.org','indiecambridge.com','camcycle.org.uk','rathbones.com','tc-group.com','theprogenygroup.com','thestaffcanteen.com','cambsedition.co.uk','thecambridgebelfry.co.uk','prospeo.io','fineandcountry.co.uk','thelistingmagazine.co.uk','velvetmag.co.uk','varsity.co.uk','cambridge-news.co.uk','boutique-magazine.co.uk','dineoutmagazine.co.uk','restaurantonline.co.uk','thechefsforum.co.uk','primalinformation.com','restaurantsforkings.com','love-cambridge.com','linkedin.com','facebook.com','instagram.com','jivamuktiyoga.com','playsport.com','find-and-update.company-information.service.gov.uk'}
recs={}
for f in sorted(glob.glob(D+'mcp-exa-*.txt')):
    try: j=json.load(open(f))
    except Exception: continue
    for r in j.get('results',[]):
        base=urlparse(r.get('url','')).netloc.lower()
        base=base[4:] if base.startswith('www.') else base
        if not base or base in EXCL: continue
        d=recs.setdefault(base,{'t':'','ph':set(),'em':set(),'sn':[]})
        for u,t,ti in [(r.get('url',''),r.get('text') or '',r.get('title') or '')]+[(s.get('url',''),s.get('text') or '',s.get('title') or '') for s in (r.get('subpages') or [])]:
            if ti and not d['t']: d['t']=ti
            for p in PHONE.findall(t):
                p=re.sub(r'[\s\)\-\.]+',' ',p).strip(); p=re.sub(r'^\+44\s*\(?0?\)?\s*','0',p); d['ph'].add(p)
            for e in EMAIL.findall(t):
                e=e.lower()
                if not e.endswith(('.png','.jpg','.jpeg','.gif','.webp','.svg')): d['em'].add(e)
            flat=re.sub(r'\s+',' ',t)
            for m in KEY.finditer(flat):
                s=flat[max(0,m.start()-110):m.start()+130]
                if s not in d['sn']: d['sn'].append(s)
for dom in sorted(recs):
    d=recs[dom]
    if not d['ph']: continue
    print(f"### {dom} | {d['t'][:50]} | PH={sorted(d['ph'])[:2]} | EM={sorted(d['em'])[:2]}")
    for s in d['sn'][:2]: print('   ~',s[:230])
