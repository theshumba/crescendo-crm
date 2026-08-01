import json,csv,re
W='/private/tmp/claude-501/-Users-theshumba/f1c00501-bc1c-4e62-aa8c-40bd7e22b950/scratchpad/cam/'
final=json.load(open(W+'final.json')); e=json.load(open(W+'enriched.json')); ch=json.load(open(W+'ch_all.json'))
have={r['dom'] for r in final}
def dom(u): return re.sub(r'^https?://(www\.)?','',u).strip('/').lower()
for o in csv.DictReader(open('/Users/theshumba/Desktop/cambridge-boutique-leads.csv')):
    d=dom(o['Website'])
    if d in have: continue
    en=e.get(d,{})
    c=ch.get(d,{})
    final.append({'dom':d,'biz':o['Business'],'cat':o['Category'],
      'owners':[x.strip() for x in o['Owner / Founder'].split(';')],'role':o['Role'],
      'ch':o['Companies House'],'inc':c.get('prof',{}).get('incorporated',''),
      'costat':c.get('prof',{}).get('status',''),'sic':c.get('prof',{}).get('sic',[]),
      'phones':(en.get('phones') or [re.sub(r'[^\d]','',o['Phone'])]),
      'emails':(en.get('emails') or ([o['Email']] if o['Email'] else [])),
      'postcode':en.get('postcode',''),'addr':en.get('addr',''),'social':en.get('social',{}),
      'founded':en.get('founded',''),'copyright':en.get('copyright',''),
      'platform':en.get('platform','Custom/unknown'),'booking':en.get('booking',[]),
      'ecom':en.get('ecommerce',False),'mobile':en.get('mobile',True),'src':'old'})
# normalise phone display
def fmt(p):
    p=re.sub(r'[^\d]','',p)
    if len(p)==11 and p.startswith('01'): return p[:5]+' '+p[5:]
    if len(p)==11 and p.startswith('07'): return p[:5]+' '+p[5:]
    return p
for r in final:
    r['phones']=[fmt(x) for x in r['phones'] if len(re.sub(r'[^\d]','',x))==11][:3] or [fmt(x) for x in r['phones']][:1]
final=[r for r in final if r['phones'] and r['owners']]
final.sort(key=lambda x:x['biz'].lower())
json.dump(final,open(W+'final.json','w'),ensure_ascii=False,indent=1)
print('TOTAL QUALIFIED:',len(final))
print(' Companies House verified:',sum(1 for r in final if r['ch']))
print(' with email:',sum(1 for r in final if r['emails']))
print(' with postcode:',sum(1 for r in final if r['postcode']))
print(' with instagram:',sum(1 for r in final if r['social'].get('instagram')))
print(' with any social:',sum(1 for r in final if r['social']))
print(' with incorporation date:',sum(1 for r in final if r['inc']))
print(' with founded year:',sum(1 for r in final if r['founded']))
print(' online booking:',sum(1 for r in final if r['booking']),' ecommerce:',sum(1 for r in final if r['ecom']))
cats={}
for r in final: cats[r['cat']]=cats.get(r['cat'],0)+1
print(' categories:',len(cats))
