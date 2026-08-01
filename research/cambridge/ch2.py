import re,html,json,os,time,urllib.parse,subprocess
BASE='https://find-and-update.company-information.service.gov.uk'
UA='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36'
W='/private/tmp/claude-501/-Users-theshumba/f1c00501-bc1c-4e62-aa8c-40bd7e22b950/scratchpad/cam/'
CACHE=W+'ch/'
def get(url,key):
    p=CACHE+re.sub(r'[^a-zA-Z0-9]','_',key)[:120]+'.html'
    if os.path.exists(p) and os.path.getsize(p)>800: return open(p,errors='ignore').read()
    r=subprocess.run(['curl','-sL','--max-time','30','-A',UA,url],capture_output=True,text=True)
    open(p,'w').write(r.stdout); time.sleep(0.3); return r.stdout
LOCAL=re.compile(r'\b(CB\d|Cambridge|Cambs|Cambridgeshire|Ely|Newmarket|Saffron Walden|Haverhill|Royston|St Neots|Huntingdon|Bar Hill|Sawston|Shelford|Histon|Milton|Waterbeach|Cottenham|Fulbourn|Linton|Cambourne|Isleham|Swavesey|Bottisham|Hemingford|Baythorne)\b',re.I)
STOP={'ltd','limited','llp','the','and','co','company','uk','group','services','service','cambridge','cambridgeshire','plc','holdings','of','a','centre','center'}
def toks(s):
    return {t for t in re.findall(r'[a-z0-9]+',s.lower()) if t not in STOP and len(t)>1}
def search(name):
    h=get(BASE+'/search/companies?q='+urllib.parse.quote(name),'s_'+name)
    out=[]
    for m in re.finditer(r'<li class="type-company">(.*?)</li>',h,re.S):
        b=m.group(1)
        num=re.search(r'/company/(\w+)',b); nm=re.search(r'title="View company">\s*(.*?)\s*</a>',b,re.S)
        meta=re.search(r'class="meta crumbtrail">\s*(.*?)\s*</p>',b,re.S)
        addr=re.findall(r'<p>(.*?)</p>',b,re.S)
        if not(num and nm): continue
        out.append({'num':num.group(1),'name':html.unescape(re.sub(r'\s+',' ',nm.group(1))),
                    'meta':html.unescape(re.sub(r'\s+',' ',meta.group(1) if meta else '')),
                    'addr':html.unescape(re.sub(r'\s+',' ',addr[-1])) if addr else ''})
    return out
def officers(num):
    h=get(BASE+f'/company/{num}/officers','o_'+num)
    res=[]
    for m in re.finditer(r'<span id="officer-name-(\d+)">(.*?)</span>',h,re.S):
        i=m.group(1)
        nm=html.unescape(re.sub(r'\s+',' ',re.sub(r'<[^>]+>','',m.group(2)))).strip()
        def f(pat):
            g=re.search(pat.replace('N',i),h,re.S)
            return html.unescape(re.sub(r'\s+',' ',re.sub(r'<[^>]+>','',g.group(1)))).strip() if g else ''
        st=f(r'id="officer-status-tag-N"[^>]*>(.*?)</span>')
        role=f(r'id="officer-role-N"[^>]*>(.*?)</dd>')
        occ=f(r'id="officer-occupation-N"[^>]*>(.*?)</dd>')
        app=f(r'id="officer-appointed-on-N"[^>]*>(.*?)</dd>')
        nat=f(r'id="officer-nationality-N"[^>]*>(.*?)</dd>')
        res.append({'name':nm,'status':st or 'Active','role':role,'occ':occ,'appointed':app,'nat':nat})
    return res
rows=[l.rstrip('\n').split('\t') for l in open(W+'leads.tsv') if l.strip()]
out={}
for dom,name,cat in rows:
    nt=toks(name)|toks(dom.split('.')[0])
    best=None;bs=0
    for q in {name,' '.join(name.split()[:2])}:
        for c in search(q):
            if 'Dissolved' in c['meta'] or 'Liquidation' in c['meta']: continue
            ct=toks(c['name'])
            if not ct: continue
            ov=len(nt&ct); sc=ov/max(1,len(ct))
            score=ov*2+sc+(1.5 if LOCAL.search(c['addr']) else -2)
            if ov>=1 and score>bs: bs=score;best=c
    rec={'dom':dom,'biz':name,'cat':cat,'co':None,'dirs':[],'score':round(bs,2)}
    if best and bs>=3:
        rec['co']={'num':best['num'],'name':best['name'],'addr':best['addr'],'meta':best['meta']}
        try: rec['dirs']=[o for o in officers(best['num']) if o['status'].lower()!='resigned'][:5]
        except Exception: pass
    out[dom]=rec
    print(f"{dom} | {(rec['co']['name'] if rec['co'] else 'NO-MATCH')} | {'; '.join(o['name']+' ('+o['role']+')' for o in rec['dirs'][:3])}",flush=True)
json.dump(out,open(W+'ch.json','w'),indent=1)
