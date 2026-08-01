import json,re,os,subprocess,html
from concurrent.futures import ThreadPoolExecutor
W='/private/tmp/claude-501/-Users-theshumba/f1c00501-bc1c-4e62-aa8c-40bd7e22b950/scratchpad/cam/'
OUT=W+'sites/'; os.makedirs(OUT,exist_ok=True)
UA='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36'
pick=json.load(open(W+'about_urls.json'))
PATHS=['','/about','/about-us','/our-story','/meet-the-team','/team','/contact']
def grab(args):
    dom,u=args
    got=[]
    base='https://'+dom
    urls=[u]+[base+p for p in PATHS]
    seen=set()
    for x in urls:
        if x in seen: continue
        seen.add(x)
        f=OUT+re.sub(r'[^a-zA-Z0-9]','_',x)[:110]+'.html'
        if os.path.exists(f):
            got.append(f); continue
        r=subprocess.run(['curl','-sL','--max-time','20','--compressed','-A',UA,x],capture_output=True,text=True,errors='ignore')
        if r.stdout and len(r.stdout)>1500:
            open(f,'w').write(r.stdout); got.append(f)
        if len(got)>=4: break
    return dom,got
with ThreadPoolExecutor(max_workers=12) as ex:
    res=list(ex.map(grab,pick))
json.dump({d:g for d,g in res},open(W+'site_files.json','w'),indent=1)
print('domains fetched:',sum(1 for d,g in res if g),'of',len(res))
print('no content:',[d for d,g in res if not g])
