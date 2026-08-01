import json,re
W='/private/tmp/claude-501/-Users-theshumba/f1c00501-bc1c-4e62-aa8c-40bd7e22b950/scratchpad/cam/'
ch=json.load(open(W+'ch.json'))
LOCAL=re.compile(r'\b(CB\d|PE\d|SG8|CB\d\d|Cambridge|Cambs|Cambridgeshire|Ely|Newmarket|Saffron Walden|Haverhill|Royston|St Neots|St Ives|Huntingdon|Bar Hill|Sawston|Shelford|Histon|Waterbeach|Cottenham|Fulbourn|Linton|Cambourne|Isleham|Swavesey|Bottisham|Burwell|Lode|Over|Girton|Bourn|Soham|Kingston)\b',re.I)
def norm(s):
    s=s.lower()
    s=re.sub(r'\b(ltd|limited|llp|plc|the|&|and|co|company|uk|group)\b',' ',s)
    s=re.sub(r'[^a-z0-9]+','',s)
    return s
ok={};rej={}
for dom,r in ch.items():
    if not r.get('co') or not r.get('dirs'): rej[dom]='no company/officers'; continue
    co=r['co']; cn=norm(co['name']); bn=norm(r['biz']); dn=norm(dom.split('.')[0])
    # brand = business name with the word cambridge removed too
    bn2=re.sub(r'cambridge(shire)?','',bn); cn2=re.sub(r'cambridge(shire)?','',cn); dn2=re.sub(r'cambridge(shire)?','',dn)
    match = (cn2 and (cn2==bn2 or cn2==dn2 or (len(cn2)>7 and (cn2 in bn2 or cn2 in dn2)) or (len(dn2)>7 and dn2 in cn2)))
    loc = bool(LOCAL.search(co['addr']))
    if match and loc: ok[dom]=r
    else: rej[dom]=f"name={'Y' if match else 'N'} loc={'Y' if loc else 'N'} -> {co['name']} @ {co['addr'][:45]}"
print("=== EXACT-MATCH CONFIRMED:",len(ok))
for d,r in sorted(ok.items()):
    dirs=[o for o in r['dirs'] if 'Director' in o['role'] or 'Member' in o['role']]
    dirs=[o for o in dirs if not o['name'].isupper() or ',' in o['name']]
    print(f"{d} :: {r['co']['name']} ({r['co']['num']}) :: {r['co']['addr']}")
    for o in dirs: print(f"     {o['name']} | {o['role']} | {o['appointed']}")
print("\n=== REJECTED:",len(rej))
for d,v in sorted(rej.items()): print(f"  {d}: {v}")
json.dump(ok,open(W+'ch_ok.json','w'),indent=1)
