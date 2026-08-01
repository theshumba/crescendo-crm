import re,html,json,os,time,urllib.parse,subprocess
BASE='https://find-and-update.company-information.service.gov.uk'
UA='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36'
W='/private/tmp/claude-501/-Users-theshumba/f1c00501-bc1c-4e62-aa8c-40bd7e22b950/scratchpad/cam/'
CACHE=W+'ch/'
def get(url,key):
    p=CACHE+re.sub(r'[^a-zA-Z0-9]','_',key)[:120]+'.html'
    if os.path.exists(p) and os.path.getsize(p)>800: return open(p,errors='ignore').read()
    r=subprocess.run(['curl','-sL','--max-time','30','-A',UA,url],capture_output=True,text=True)
    open(p,'w').write(r.stdout); time.sleep(0.25); return r.stdout
LOCAL=re.compile(r'\b(CB\d|PE\d|SG8|IP\d|CO\d|Cambridge|Cambs|Cambridgeshire|Ely|Newmarket|Saffron Walden|Haverhill|Royston|St Neots|St Ives|Huntingdon|Sawston|Shelford|Histon|Waterbeach|Cottenham|Fulbourn|Linton|Cambourne|Isleham|Swavesey|Bottisham|Burwell|Girton|Soham|Kingston|Milton|Willingham|Melbourn|Duxford|Comberton|Barton|Impington|Teversham|Sawtry|March|Wisbech|Godmanchester|Over|Lode|Bourn)\b',re.I)
def norm(s):
    s=s.lower(); s=re.sub(r'\b(ltd|limited|llp|plc|the|and|co|company|uk|group)\b',' ',s)
    s=re.sub(r'&',' ',s); return re.sub(r'[^a-z0-9]+','',s)
def sc(s): return re.sub(r'cambridgeshire|cambridge|cambs','',s)
def search(name):
    h=get(BASE+'/search/companies?q='+urllib.parse.quote(name),'s_'+name)
    out=[]
    for m in re.finditer(r'<li class="type-company">(.*?)</li>',h,re.S):
        b=m.group(1)
        num=re.search(r'/company/(\w+)',b); nm=re.search(r'title="View company">\s*(.*?)\s*</a>',b,re.S)
        meta=re.search(r'class="meta crumbtrail">\s*(.*?)\s*</p>',b,re.S); addr=re.findall(r'<p>(.*?)</p>',b,re.S)
        if not(num and nm): continue
        out.append({'num':num.group(1),'name':html.unescape(re.sub(r'\s+',' ',nm.group(1))),
                    'meta':html.unescape(re.sub(r'\s+',' ',meta.group(1) if meta else '')),
                    'addr':html.unescape(re.sub(r'\s+',' ',addr[-1])) if addr else ''})
    return out
def officers(num):
    h=get(BASE+f'/company/{num}/officers','o_'+num); res=[]
    for m in re.finditer(r'<span id="officer-name-(\d+)">(.*?)</span>',h,re.S):
        i=m.group(1); nm=html.unescape(re.sub(r'\s+',' ',re.sub(r'<[^>]+>','',m.group(2)))).strip()
        def f(pat):
            g=re.search(pat.replace('N',i),h,re.S)
            return html.unescape(re.sub(r'\s+',' ',re.sub(r'<[^>]+>','',g.group(1)))).strip() if g else ''
        res.append({'name':nm,'status':f(r'id="officer-status-tag-N"[^>]*>(.*?)</span>') or 'Active',
                    'role':f(r'id="officer-role-N"[^>]*>(.*?)</dd>'),'occ':f(r'id="officer-occupation-N"[^>]*>(.*?)</dd>'),
                    'appointed':f(r'id="officer-appointed-on-N"[^>]*>(.*?)</dd>'),'nat':f(r'id="officer-nationality-N"[^>]*>(.*?)</dd>')})
    return res
def profile(num):
    h=get(BASE+f'/company/{num}','c_'+num)
    def f(pat):
        g=re.search(pat,h,re.S)
        return html.unescape(re.sub(r'\s+',' ',re.sub(r'<[^>]+>','',g.group(1)))).strip() if g else ''
    sic=[html.unescape(re.sub(r'\s+',' ',re.sub(r'<[^>]+>','',x))).strip() for x in re.findall(r'id="sic\d+">(.*?)</span>',h,re.S)]
    return {'incorporated':f(r'id="company-creation-date"[^>]*>(.*?)</dd>'),
            'status':f(r'id="company-status"[^>]*>(.*?)</dd>'),
            'type':f(r'id="company-type"[^>]*>(.*?)</dd>'),'sic':sic[:3]}
rows=[]
for f in ['leads.tsv','newdoms.txt']:
    for l in open(W+f):
        if l.strip(): p=l.rstrip('\n').split('\t'); rows.append((p[0],p[1],p[2] if len(p)>2 else ''))
res={}
for dom,name,cat in rows:
    best=None
    for q in {name,' '.join(name.split()[:2])}:
        try: cands=search(q)
        except Exception: cands=[]
        for c in cands:
            if 'Dissolved' in c['meta'] or 'Liquidation' in c['meta']: continue
            cn=sc(norm(c['name'])); bn=sc(norm(name)); dn=sc(norm(dom.split('.')[0]))
            if cn and (cn==bn or cn==dn) and LOCAL.search(c['addr']): best=c; break
        if best: break
    if not best: continue
    try: offs=[o for o in officers(best['num']) if o['status'].lower()!='resigned']
    except Exception: offs=[]
    if not offs: continue
    try: prof=profile(best['num'])
    except Exception: prof={}
    res[dom]={'co':best,'dirs':offs[:5],'prof':prof}
    print(f"{dom} | {best['name']} ({best['num']}) | {prof.get('incorporated','')} | {'; '.join(o['name'] for o in offs[:2])}",flush=True)
json.dump(res,open(W+'ch_all.json','w'),indent=1)
print('=== matched:',len(res),'of',len(rows))
