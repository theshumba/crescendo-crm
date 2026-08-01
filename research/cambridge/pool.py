import json,glob,re,csv
from urllib.parse import urlparse
D='/Users/theshumba/.claude/projects/-Users-theshumba/f1c00501-bc1c-4e62-aa8c-40bd7e22b950/tool-results/'
PHONE=re.compile(r'(?:\+44\s?\(?0?\)?\s?|\b0)(?:1223|1954|1353|1638|1799|1440|1480|1487|1763|1767|7\d{3})[\s\)\-\.]?\d{3}[\s\-\.]?\d{3,4}\b')
EMAIL=re.compile(r'[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}')
CAMB=re.compile(r'\b(cambridge|cambs|cambridgeshire|ely|newmarket|saffron walden|haverhill|royston|st neots|st ives|huntingdon|sawston|shelford|histon|waterbeach|cottenham|fulbourn|linton|cambourne|isleham|swavesey|bottisham|burwell|girton|soham|trumpington|cherry hinton|chesterton|arbury|milton|impington|willingham|melbourn|duxford|comberton|barton|madingley|grantchester|harston|sawtry|ramsey|march|wisbech|godmanchester)\b',re.I)
BADDOM=re.compile(r'(facebook|instagram|linkedin|twitter|x\.com|youtube|tiktok|pinterest|yelp|tripadvisor|google|yell\.com|thomsonlocal|cylex|opentable|thefork|treatwell|fresha|booksy|wikipedia|reddit|prospeo|apple\.com|bing|indeed|totaljobs|reed\.co|checkatrade|trustpilot|which\.co|gov\.uk|nhs\.uk|rcvs|bupa|amazon|ebay|etsy|eventbrite|designmynight|squaremeal|hardens|michelin|timeout|visitcambridge|cambridge-news|cambridgeindependent|varsity\.co|cambsedition|cambridgeedition|velvetmag|thelisting|boutique-magazine|dineout|restaurantonline|thechefsforum|staffcanteen|primalinformation|restaurantsforkings|love-cambridge|indiecambridge|camcycle|allagents|rightmove|zoopla|onthemarket|nextdoor|substack|medium\.com|wordpress\.com|blogspot|issuu|scribd|pdf|\.gov|nearcut|setmore|gettimely|wixsite|weebly|glassdoor|companieshouse|company-information|endole|bizdb|opencorporates|thegazette)',re.I)
known=set(l.split('\t')[0] for l in open('leads.tsv') if l.strip())
recs={}
for f in sorted(glob.glob(D+'mcp-exa-*.txt')):
    try: j=json.load(open(f))
    except Exception: continue
    for r in j.get('results',[]):
        base=urlparse(r.get('url','')).netloc.lower()
        base=base[4:] if base.startswith('www.') else base
        if not base or BADDOM.search(base): continue
        d=recs.setdefault(base,{'t':'','ph':set(),'em':set(),'camb':False,'txt':0})
        for u,t,ti in [(r.get('url',''),r.get('text') or '',r.get('title') or '')]+[(s.get('url',''),s.get('text') or '',s.get('title') or '') for s in (r.get('subpages') or [])]:
            if ti and not d['t']: d['t']=ti
            d['txt']+=len(t)
            if CAMB.search(t) or CAMB.search(base): d['camb']=True
            for p in PHONE.findall(t):
                p=re.sub(r'[\s\)\-\.]+',' ',p).strip(); p=re.sub(r'^\+44\s*\(?0?\)?\s*','0',p); d['ph'].add(p)
            for e in EMAIL.findall(t):
                e=e.lower()
                if not e.endswith(('.png','.jpg','.jpeg','.gif','.webp','.svg')) and 'sentry' not in e: d['em'].add(e)
new=[(k,v) for k,v in recs.items() if v['ph'] and v['camb'] and k not in known]
new.sort()
print('TOTAL domains:',len(recs),'| NEW with phone + Cambridge signal:',len(new))
with open('new_candidates.tsv','w') as fh:
    for k,v in new: fh.write(f"{k}\t{v['t'][:70]}\t{';'.join(sorted(v['ph'])[:2])}\t{';'.join(sorted(v['em'])[:2])}\n")
for k,v in new: print(f"{k} | {v['t'][:52]} | {sorted(v['ph'])[:1]}")
