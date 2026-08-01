import json,re,csv
W='/private/tmp/claude-501/-Users-theshumba/f1c00501-bc1c-4e62-aa8c-40bd7e22b950/scratchpad/cam/'
F=json.load(open(W+'final.json'))
SERVICE=re.compile(r'salon|barber|dentist|dental|clinic|osteo|physio|podiat|chiro|pilates|massage|beauty|hair|brow|nail|tattoo|piercing|grooming|driving|counsel|audiolog|tennis|climb|martial|punting|photograph|golf',re.I)
RETAIL=re.compile(r'shop|retail|jewell|butcher|boutique|antique|wine|gift|homeware|toy|art supplies|furniture|bridal|menswear|optician|farm shop|grocery|deli|bakery|memorabilia|vintage',re.I)
def slug(s): return 'cbq-'+re.sub(r'-+','-',re.sub(r'[^a-z0-9]+','-',s.lower())).strip('-')
def obs(r):
    o=[]
    svc=bool(SERVICE.search(r['cat'])); ret=bool(RETAIL.search(r['cat']))
    if svc and not r['booking']: o.append('no online booking on the site, so every appointment has to come through the phone')
    if r['booking']: o.append('takes bookings through '+', '.join(r['booking']))
    if ret and not r['ecom']: o.append('no online shop, so the business only sells in person')
    if r['ecom']: o.append('sells online already ('+r['platform']+')')
    if r['platform'] in ('Wix','GoDaddy','Weebly'): o.append('site is built on '+r['platform']+', a DIY builder')
    if r['copyright'] and int(r['copyright'])<2025: o.append('site footer still reads '+r['copyright']+', so it has not been touched in a while')
    if not r['social'].get('instagram'): o.append('no Instagram linked from the site')
    if not r['emails']: o.append('no email address published, phone is the only way in')
    if not r['mobile']: o.append('no mobile viewport set, so the site will not scale on a phone')
    return o
def verif(r):
    if r['ch']: return 'Companies House, company no. '+r['ch']
    return 'Stated on the business website'
rows=[]
for r in F:
    ob=obs(r)
    parts=[]
    parts.append(f"Independent {r['cat'].lower()}" + (f" at {r['addr'] or r['postcode']}" if (r['addr'] or r['postcode']) else " in Cambridge") + ".")
    parts.append("Owner: "+", ".join(r['owners'])+(f" ({r['role'].lower()})." if r['role'] else "."))
    if r['inc']: parts.append(f"Company incorporated {r['inc']}"+(f", status {r['costat'].lower()}" if r['costat'] else "")+".")
    elif r['founded']: parts.append(f"Site says the business was established {r['founded']}.")
    if r['sic']: parts.append("Registered activity: "+"; ".join(r['sic'][:2])+".")
    if ob: parts.append("What we can see from their site: "+"; ".join(ob)+".")
    parts.append("Owner name verified via "+verif(r)+".")
    desc=re.sub(r'\s+',' ',' '.join(parts)).strip()
    rows.append({
      'id':slug(r['biz']),'businessName':r['biz'],'industry':r['cat'],'website':'https://'+r['dom'],
      'address':(r['addr'] or ('Cambridge' if not r['postcode'] else r['postcode'])),
      'postcode':r['postcode'],'town':r.get('town','Cambridge'),
      'phones':[{'number':p} for p in r['phones']],
      'emails':[{'address':x} for x in r['emails'][:3]],
      'contacts':[{'name':o,'title':r['role'] or 'Owner','phone':r['phones'][0] if i==0 else '','email':(r['emails'][0] if (i==0 and r['emails']) else '')} for i,o in enumerate(r['owners'])],
      'description':desc,'source':'research','status':'qualified','list':'cambridge-boutique',
      'companiesHouse':r['ch'],
      'qualification':{'strategyDesign':'','experienceDesign':'','digitalCommerce':'',
        'growthIntent':'','weaknessesOpportunities':(('From their own site: '+'; '.join(ob)+'.') if ob else '')},
      'research':{'incorporated':r['inc'],'companyStatus':r['costat'],'sic':r['sic'],'founded':r['founded'],
        'social':r['social'],'platform':r['platform'],'booking':r['booking'],'ecommerce':bool(r['ecom']),
        'mobile':bool(r['mobile']),'siteYear':r['copyright'],'verifiedVia':verif(r)},
      'observations':ob})
ids=[x['id'] for x in rows]; assert len(set(ids))==len(ids), [i for i in ids if ids.count(i)>1]
json.dump(rows,open(W+'cbq2.json','w'),ensure_ascii=False,separators=(',',':'))
print('records:',len(rows),'bytes:',len(open(W+'cbq2.json').read()))
print('avg observations:',round(sum(len(x['observations']) for x in rows)/len(rows),1))
# rich CSV
cols=['Business','Category','Website','Postcode','Address','Phone 1','Phone 2','Email 1','Email 2','Owner / Founder','Role','Verified via','Companies House','Incorporated','Company status','Registered activity','Established','Instagram','Facebook','LinkedIn','Website platform','Online booking','Sells online','Site last updated','What we can see']
with open('/Users/theshumba/Desktop/cambridge-boutique-leads.csv','w',newline='') as fh:
    w=csv.writer(fh); w.writerow(cols)
    for r,src in zip(rows,F):
        s=r['research']
        w.writerow([r['businessName'],r['industry'],r['website'],r['postcode'],r['address'],
          (r['phones'][0]['number'] if r['phones'] else ''),(r['phones'][1]['number'] if len(r['phones'])>1 else ''),
          (r['emails'][0]['address'] if r['emails'] else ''),(r['emails'][1]['address'] if len(r['emails'])>1 else ''),
          '; '.join(c['name'] for c in r['contacts']),r['contacts'][0]['title'],s['verifiedVia'],r['companiesHouse'],
          s['incorporated'],s['companyStatus'],'; '.join(s['sic'][:2]),s['founded'],
          s['social'].get('instagram',''),s['social'].get('facebook',''),s['social'].get('linkedin',''),
          s['platform'],', '.join(s['booking']),'yes' if s['ecommerce'] else 'no',s['siteYear'],'; '.join(r['observations'])])
print('CSV columns:',len(cols))
