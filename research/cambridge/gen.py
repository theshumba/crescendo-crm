import csv,json,re
AREA={
"All Eyes Spectacle Makers":"Over, Cambridgeshire","Barker Bros Butchers":"5 High Green, Great Shelford, Cambridge",
"Barnwell Barbers":"9 Barnwell Road, Cambridge","Boxed Events":"Histon, Cambridge",
"Buds Fitness":"Sawtry, Huntingdon, Cambridgeshire","Bush & Co":"Great Shelford, Cambridge",
"Cam Osteopathy":"Waterbeach, Cambridge","Cambridge Crafted Kitchens":"Saxon Farm, Lode, Cambridge",
"Cambridge Dental":"Cambridge","Cambridge Osteopaths":"Cambridge",
"Cambridge Photographers":"Lower Cambourne, Cambridge","Cambridge Punters":"Hope Street, Cambridge",
"Cambridge Skin Clinic":"7 Signet Court, Cambridge","Cambridge Smile Studio":"Cambridge",
"Carmelo Hair":"Great Shelford, Cambridge","Catherine Jones Jewellers":"9 Bridge Street, Cambridge",
"Chardome":"Burwell, Cambridge","Crown Catering Cambridge":"Great Chesterford, Saffron Walden",
"Dr Ines Ribeiro":"Cambridge","Dye's Hair & Beauty":"Arbury Court, Cambridge",
"Eyes of Swavesey":"Swavesey, Cambridge","Fantasia (Scuseme)":"Mill Road, Cambridge",
"Fen Ditton Gallery":"Fen Ditton, Cambridge","Fitzbillies":"51-52 Trumpington Street, Cambridge",
"Flowerverse":"Cambridge","Gallery Above":"Linton, Cambridge","Gardner Denley":"Kingston, Cambridge",
"getBEAUTY":"Cambridge","Hardwick Clinic":"Hardwick, Cambridge","Hurst Park Dental":"Cambridge",
"Katie Malik Design Studio":"Saffron Walden","Let's Go Punting":"30 Milton Road, Cambridge",
"MB Hair Studio":"Cambridge","MM Wealth":"Girton, Cambridge","Mensroom Cambridge":"Cherry Hinton, Cambridge",
"Midsummer House":"Midsummer Common, Cambridge","Morgans Butchery":"Baythorne Hall, Haverhill",
"Nicholas Hythe Kitchen Design":"St Ives, Cambridgeshire","PhysioTeq":"Barton Road, Cambridge",
"Pilatesfit Cambridge":"Cambridge","Revive Massage Therapy":"Cambourne, Cambridge",
"Rulos Barbers":"Cambridge","Rutherford's Punting":"Searle Street, Cambridge",
"Salus Wellness":"Cambridge Place, Cambridge","Scholars Punting Cambridge":"Hope Street, Cambridge",
"Scruffs":"Cambridge","Scudamore's Punting":"Granta Place, Mill Lane, Cambridge",
"Soho Fine Art Cambridge":"Cambridge","The Barbers Cambridge":"27 King Street, Cambridge",
"Total Health Clinics":"Cambridge","Willow Grange Farm Shop":"Cambridge","Burr Bridal":"Cambridge"}
def slug(s): return 'cbq-'+re.sub(r'-+','-',re.sub(r'[^a-z0-9]+','-',s.lower())).strip('-')
out=[]
for r in csv.DictReader(open('/Users/theshumba/Desktop/cambridge-boutique-leads.csv')):
    biz=r['Business'].strip()
    owners=[o.strip() for o in r['Owner / Founder'].split(';') if o.strip()]
    role=r['Role'].strip(); ch=r['Companies House'].strip(); src=r['Source of owner name'].strip()
    contacts=[{"name":o,"title":role,"phone":r['Phone'].strip() if i==0 else "","email":r['Email'].strip() if i==0 else ""} for i,o in enumerate(owners)]
    prov=("Owner verified against Companies House (company no. %s), registered in Cambridgeshire." % ch) if ch else ("Owner name published on the business's own website.")
    if 'Website + Companies House' in src: prov="Owner named on the business's own website and confirmed as an active director at Companies House (company no. %s)." % ch
    desc="Independent %s in %s. %s %s" % (r['Category'].strip().lower(), AREA.get(biz,'Cambridge'), "Contact: %s (%s)." % (", ".join(owners), role.lower()), prov)
    out.append({"id":slug(biz),"businessName":biz,"industry":r['Category'].strip(),"website":r['Website'].strip(),
        "address":AREA.get(biz,"Cambridge"),
        "phones":[{"number":r['Phone'].strip()}],
        "emails":([{"address":r['Email'].strip()}] if r['Email'].strip() else []),
        "contacts":contacts,"description":re.sub(r'\s+',' ',desc).strip(),
        "source":"research","status":"qualified","list":"cambridge-boutique",
        "companiesHouse":ch})
print(len(out))
open('cbq.json','w').write(json.dumps(out,ensure_ascii=False,separators=(',',':')))
print(json.dumps(out[0],ensure_ascii=False,indent=1)[:700])
print('bytes',len(open('cbq.json').read()))
ids=[o['id'] for o in out]; print('unique ids:',len(set(ids))==len(ids))
