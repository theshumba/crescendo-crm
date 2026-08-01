import re,html,json,os,time,urllib.parse,subprocess,sys
BASE='https://find-and-update.company-information.service.gov.uk'
UA='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36'
CACHE='/private/tmp/claude-501/-Users-theshumba/f1c00501-bc1c-4e62-aa8c-40bd7e22b950/scratchpad/cam/ch/'
def get(url,key):
    p=CACHE+re.sub(r'[^a-zA-Z0-9]','_',key)+'.html'
    if os.path.exists(p) and os.path.getsize(p)>800: return open(p,errors='ignore').read()
    r=subprocess.run(['curl','-sL','--max-time','30','-A',UA,url],capture_output=True,text=True)
    open(p,'w').write(r.stdout); time.sleep(0.35); return r.stdout
LOCAL=re.compile(r'\b(CB\d|Cambridge|Cambs|Cambridgeshire|Ely|Newmarket|Saffron Walden|Haverhill|Royston|St Neots|Huntingdon|Bar Hill|Sawston|Shelford|Histon|Milton|Waterbeach|Cottenham|Fulbourn|Linton|Cambourne|Isleham|Swavesey|Bottisham)\b',re.I)
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
    for m in re.finditer(r'<h2[^>]*id="officer-name-\d+"[^>]*>(.*?)</h2>(.*?)(?=<h2[^>]*id="officer-name-|</main>)',h,re.S):
        nm=html.unescape(re.sub(r'\s+',' ',re.sub(r'<[^>]+>','',m.group(1)))).strip()
        blk=re.sub(r'<[^>]+>',' ',m.group(2)); blk=html.unescape(re.sub(r'\s+',' ',blk))
        role=re.search(r'Role\s*(?:Active|Resigned)?\s*([A-Za-z\- ]{3,30}?)\s+(?:Date of birth|Appointed|Correspondence)',blk)
        resigned='Resigned on' in blk or 'Resigned' in (re.search(r'Role\s+(\w+)',blk).group(1) if re.search(r'Role\s+(\w+)',blk) else '')
        occ=re.search(r'Occupation\s+([A-Za-z\-\/ &]{3,40})',blk)
        nat=re.search(r'Nationality\s+([A-Za-z ]{3,25})',blk)
        res.append({'name':nm,'role':(role.group(1).strip() if role else ''),'resigned':resigned,
                    'occ':(occ.group(1).strip() if occ else ''),'nat':(nat.group(1).strip() if nat else '')})
    return res
rows=[l.rstrip('\n').split('\t') for l in open('/private/tmp/claude-501/-Users-theshumba/f1c00501-bc1c-4e62-aa8c-40bd7e22b950/scratchpad/cam/leads.tsv') if l.strip()]
out={}
for dom,name,cat in rows:
    try: cands=search(name)
    except Exception as e: cands=[]
    pick=None
    for c in cands:
        if 'Dissolved' in c['meta']: continue
        if LOCAL.search(c['addr']): pick=c; break
    if not pick:
        # retry with shortened name
        short=' '.join(name.split()[:2])
        if short.lower()!=name.lower():
            try: cands2=search(short)
            except Exception: cands2=[]
            for c in cands2:
                if 'Dissolved' in c['meta']: continue
                if LOCAL.search(c['addr']) and c['name'].split()[0].lower()==name.split()[0].lower(): pick=c; break
    rec={'dom':dom,'biz':name,'cat':cat,'co':None,'dirs':[]}
    if pick:
        rec['co']={'num':pick['num'],'name':pick['name'],'addr':pick['addr'],'meta':pick['meta']}
        try:
            offs=[o for o in officers(pick['num']) if not o['resigned']]
        except Exception: offs=[]
        rec['dirs']=offs[:4]
    out[dom]=rec
    print(dom,'|',(pick['name'] if pick else 'NO-CO'),'|',';'.join(o['name'] for o in rec['dirs'][:3]),flush=True)
json.dump(out,open('/private/tmp/claude-501/-Users-theshumba/f1c00501-bc1c-4e62-aa8c-40bd7e22b950/scratchpad/cam/ch.json','w'),indent=1)
