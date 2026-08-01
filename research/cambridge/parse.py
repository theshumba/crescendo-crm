import json,glob,re,sys,os
from urllib.parse import urlparse
D='/Users/theshumba/.claude/projects/-Users-theshumba/f1c00501-bc1c-4e62-aa8c-40bd7e22b950/tool-results/'
PHONE=re.compile(r'(?:\+44\s?\(?0?\)?\s?|\b0)(?:1223|1954|1353|1638|1799|7\d{3})[\s\)\-\.]?\d{3}[\s\-\.]?\d{3,4}\b')
EMAIL=re.compile(r'[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}')
seen={}
files=sys.argv[1:] if len(sys.argv)>1 else sorted(glob.glob(D+'mcp-exa-*.txt'))
for f in files:
    try: j=json.load(open(f))
    except Exception as e: print('SKIP',f,e); continue
    for r in j.get('results',[]):
        u=r.get('url',''); t=(r.get('text') or '')
        dom=urlparse(u).netloc.lower().replace('www.','')
        ph=sorted(set(re.sub(r'[\s\)\-\.]+',' ',p).strip() for p in PHONE.findall(t)))
        em=sorted(set(e.lower() for e in EMAIL.findall(t) if not e.lower().endswith(('.png','.jpg','.jpeg','.gif','.webp'))))
        d=seen.setdefault(dom,{'urls':set(),'ph':set(),'em':set(),'title':r.get('title') or ''})
        d['urls'].add(u); d['ph'].update(ph); d['em'].update(em)
        if not d['title']: d['title']=(t[:60].replace('\n',' '))
for dom in sorted(seen):
    d=seen[dom]
    print(f"{dom} | {d['title'][:55]} | PH:{';'.join(sorted(d['ph'])[:3])} | EM:{';'.join(sorted(d['em'])[:2])}")
print('---TOTAL DOMAINS', len(seen))
