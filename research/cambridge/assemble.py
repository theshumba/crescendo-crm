import json,re,csv
W='/private/tmp/claude-501/-Users-theshumba/f1c00501-bc1c-4e62-aa8c-40bd7e22b950/scratchpad/cam/'
e=json.load(open(W+'enriched.json')); ch=json.load(open(W+'ch_all.json'))
# Owner names read off the business's own website (evidence reviewed by hand this session)
WEB={
 'burrbridal.co.uk':('Kim Burr','Founder & owner'),
 'cambridge.dental':('Dr Geeta Bellis','Lead dentist'),
 'cambridgeosteopaths.com':('Alexander Taylor','Proprietor'),
 'crowncateringcambridge.com':('Roger Hornett','Chairman & Chief Executive'),
 'drinesribeiro.com':('Dr Ines Ribeiro','Owner'),
 'dyeshairandbeauty.co.uk':('Diane Cundell','Founder, 1998'),
 'eyesofswavesey.co.uk':('Emma Logan','Director & Senior Optometrist'),
 'fendittongallery.com':('Hannah Munby; Lotte Attwood','Owners, mother and daughter'),
 'flowerverse.co.uk':('Natalia Golowicz','Founder'),
 'galleryabove.co.uk':('Rosemary Wellings','Owner'),
 'getbeauty.uk':('Ramona Ristea','Founder'),
 'hardwickclinic.co.uk':('Dr Tatyana Lapa-Enright','Founder, 2013'),
 'hurstparkdental.com':('Max Leslie','Lead cosmetic dentist'),
 'mb-hairstudio.co.uk':('Mesut Can Polat; Beata Drzala','Salon owners'),
 'revivemassagecambourne.co.uk':('Aneta Plutowska','Founder'),
 'rulos.co.uk':('Giovanni Favarulo','Founder'),
 'scruffs.co.uk':('Garry Chapman; Grant Chapman','Owners, second generation'),
 'scuseme.co.uk':('Dawn Giesler','Founder'),
 'sohofineart.co.uk':('Jackie Ritsema','Executive Gallery Director'),
 'totalhealthclinics.com':('Ben Barker','Founder'),
 'thebespoketailor.co.uk':('Adrian Barrows','Director'),
 # new this round
 'alexandergreens.co.uk':('Jonathan Wright','Director'),
 'cuttingedgepodiatry.co.uk':('Suvanne Southgate','Principal Podiatrist'),
 'freepresscambridge.com':('Megan Stepney; Thomas Stepney','Owners, siblings'),
 'goddenshomeinteriors.co.uk':('Aaron Godden','Owner'),
 'histonfootcare.co.uk':('Andrew Goodwin','Principal'),
 'maioranaupholstery.co.uk':('Alessio Maiorana','Founder, 1976'),
 'sageblinds.co.uk':('Martin Sorrell; Clare Sorrell','Owners'),
 'timjenningsdesign.co.uk':('Tim Jennings','Owner & lead designer'),
 'planninghouse.co.uk':('Chris Pipe','Founder'),
 'sproctor.co.uk':('Shaun Proctor','Owner'),
 'counsellingwithmadeleine.co.uk':('Madeleine Gooding','Owner'),
}
# corroborations where site + register agree (keep website-facing name, cite CH number)
def clean(n):
    n=n.strip()
    if ',' in n:
        parts=[p.strip() for p in n.split(',')]
        if len(parts)>=2 and parts[1] and not parts[1].islower():
            title=parts[2] if len(parts)>2 else ''
            n=(title+' ' if title in ('Dr','Prof','Mrs','Mr','Ms') else '')+parts[1]+' '+parts[0]
    return ' '.join(w.capitalize() if w.isupper() and len(w)>2 else w for w in n.split()).replace('  ',' ')
rows=[]
for dom,r in e.items():
    if r.get('dead'): continue
    biz=r['biz']; cat=r['cat']
    phones=r['phones']; emails=r['emails']
    owners=[]; role=''; chnum=''; inc=''; costat=''; sic=[]
    if dom in ch:
        c=ch[dom]; chnum=c['co']['num']; inc=c['prof'].get('incorporated',''); costat=c['prof'].get('status',''); sic=c['prof'].get('sic',[])
        ds=[o for o in c['dirs'] if ('Director' in o['role'] or 'Member' in o['role']) and ',' in o['name']]
        seen=set(); 
        for o in ds:
            n=clean(o['name'])
            if n not in seen: seen.add(n); owners.append(n)
        owners=owners[:3]; role='Director' if owners else ''
        if dom in WEB: owners=[x.strip() for x in WEB[dom][0].split(';')]; role=WEB[dom][1]
    elif dom in WEB:
        owners=[x.strip() for x in WEB[dom][0].split(';')]; role=WEB[dom][1]
    if not owners or not phones or not dom: continue
    if any(len(o.split())<2 for o in owners): continue
    rows.append({'dom':dom,'biz':biz,'cat':cat,'owners':owners,'role':role,'ch':chnum,'inc':inc,
        'costat':costat,'sic':sic,'phones':phones,'emails':emails,'postcode':r['postcode'],'addr':r['addr'],
        'social':r['social'],'founded':r['founded'],'copyright':r['copyright'],'platform':r['platform'],
        'booking':r['booking'],'ecom':r['ecommerce'],'mobile':r['mobile'],'src':r['src']})
rows.sort(key=lambda x:x['biz'])
json.dump(rows,open(W+'final.json','w'),ensure_ascii=False,indent=1)
print('QUALIFIED TOTAL:',len(rows),' (was 52)')
print(' new this round:',sum(1 for r in rows if r['src']=='new'))
print(' Companies House verified:',sum(1 for r in rows if r['ch']))
print(' with email:',sum(1 for r in rows if r['emails']))
print(' with postcode:',sum(1 for r in rows if r['postcode']))
print(' with instagram:',sum(1 for r in rows if r['social'].get('instagram')))
print(' with incorporation date:',sum(1 for r in rows if r['inc']))
print(' with online booking:',sum(1 for r in rows if r['booking']))
print(' with ecommerce:',sum(1 for r in rows if r['ecom']))
print(' 2+ phone numbers:',sum(1 for r in rows if len(r['phones'])>1))
