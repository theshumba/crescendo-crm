import json,glob,re
from urllib.parse import urlparse
D='/Users/theshumba/.claude/projects/-Users-theshumba/f1c00501-bc1c-4e62-aa8c-40bd7e22b950/tool-results/'
W='/private/tmp/claude-501/-Users-theshumba/f1c00501-bc1c-4e62-aa8c-40bd7e22b950/scratchpad/cam/'
done=set(json.load(open(W+'ch_strict.json')).keys())
want=[l.split('\t')[0] for l in open(W+'leads.tsv') if l.strip()]
urls={}
for f in sorted(glob.glob(D+'mcp-exa-*.txt')):
    try: j=json.load(open(f))
    except Exception: continue
    for r in j.get('results',[]):
        for u in [r.get('url','')]+[s.get('url','') for s in (r.get('subpages') or [])]:
            n=urlparse(u).netloc.lower(); n=n[4:] if n.startswith('www.') else n
            if n in want: urls.setdefault(n,set()).add(u)
def score(u):
    p=u.lower()
    for i,k in enumerate(['meet-the-team','meet_the_team','/team','about-us','/about','our-story','/story','who-we-are','/staff','/contact']):
        if k in p: return i
    return 99
pick=[]
for d in want:
    if d in done: continue
    us=sorted(urls.get(d,[]),key=score)
    pick.append((d,us[0] if us else 'https://'+d))
print(len(pick))
json.dump(pick,open(W+'about_urls.json','w'),indent=1)
for d,u in pick: print(d,'->',u)
