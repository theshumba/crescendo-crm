import json,re
W='/private/tmp/claude-501/-Users-theshumba/f1c00501-bc1c-4e62-aa8c-40bd7e22b950/scratchpad/cam/'
ch=json.load(open(W+'ch.json'))
GEN={'ltd','limited','llp','the','and','co','company','uk','group','plc','holdings','of','a','an','services','service'}
CAT={'cambridge','cambridgeshire','cambs','barbers','barber','barbershop','hair','hairdressing','beauty','salon','dental','dentist','dentistry','clinic','clinics','skin','punting','punters','bridal','bed','breakfast','guesthouse','guest','house','kitchens','kitchen','design','build','flowers','florist','butchers','butchery','farm','shop','gallery','art','fine','studio','photography','photographers','physiotherapy','physio','osteopathy','osteopaths','osteopath','wellness','catering','caterers','events','fitness','restaurant','restaurants','tailor','tailors','bespoke','menswear','massage','therapy','nails','lashes','brows','wedding','weddings','films','film','videographer','estate','agents','agent','wealth','financial','planning','hotel','hotels','cottage','spectacle','makers','opticians','optician','interiors','interior','crafts','craft','contemporary','aesthetics','aesthetic','chiropractic','personal','training','trainer','project','consulting','property','buying','shops','stores','store','centre','mini','market','lab','ceramics','systems','electrical','developments','development','barns','drive','print','ark','chest','court','management','boutique','care','health','total'}
def toks(s): return [t for t in re.findall(r'[a-z0-9&]+',s.lower()) if t not in GEN and len(t)>1]
def brand(s): return {t for t in toks(s) if t not in CAT}
ok={};bad={}
for dom,r in ch.items():
    if not r.get('co') or not r.get('dirs'): bad[dom]=r; continue
    b=brand(r['biz'])|brand(dom.split('.')[0])
    c=brand(r['co']['name'])
    shared=b&c; extra=c-b
    # confident if every distinctive company token is in the brand and at least one shared,
    # or company name token-set is a subset/superset with <=1 extra
    if shared and len(extra)<=0: ok[dom]=r
    elif shared and len(extra)==1 and len(shared)>=1 and len(c)>=2: ok[dom]=r
    else: bad[dom]=r
print("=== CONFIDENT MATCH:",len(ok))
for d,r in sorted(ok.items()):
    print(f"{d} | {r['biz']} | CO={r['co']['name']} ({r['co']['num']}) | {r['co']['addr'][:60]}")
    for o in r['dirs']:
        if o['role'] in ('Director','LLP Designated Member','LLP Member'):
            print(f"      -> {o['name']} | {o['role']} | occ={o['occ']} | appt={o['appointed']}")
print()
print("=== NEEDS OTHER SOURCE:",len(bad))
print('; '.join(sorted(bad)))
json.dump({'ok':ok,'bad':list(bad)},open(W+'strict.json','w'),indent=1)
