import re,html,subprocess,os
from concurrent.futures import ThreadPoolExecutor
UA='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36'
T=[('willowgrange','https://willowgrangefarm.co.uk/our-founders'),
   ('willowgrange2','https://willowgrangefarm.co.uk/our-story'),
   ('dhthomas','https://www.dhthomas.co.uk/about-us/'),
   ('thomaswilliam','https://www.thomas-william.co.uk/about'),
   ('wallers','https://www.wallersthebutchers.co.uk/about'),
   ('wallers2','https://www.wallersthebutchers.co.uk/'),
   ('rectory','https://www.rectoryfarmshop.co.uk/about'),
   ('camframe','https://www.camframe.co.uk/about'),
   ('carmelo','https://www.carmelohair.co.uk/about'),
   ('chequer','https://www.chequercottage.com/about'),
   ('antonios','https://www.antoniosbarbers.com/about'),
   ('arthan','https://arthanfittedkitchens.co.uk/about-us/meet-the-team/'),
   ('barnwell','https://barnwellbarbers.co.uk/contact'),
   ('miltonchiro','https://www.miltonchiropractic.co.uk/about-us/'),
   ('markethouse','https://markethouse.co.uk/our-story/'),
   ('pipasha','https://www.pipasha-restaurant.co.uk/about-us'),
   ('regentdental','https://www.regentdental.co.uk/about-us/'),
   ('elemhair','https://www.elem-hair.co.uk/about'),
   ('harmonyhair','https://harmonyhaircambridge.com/about'),
   ('millionhairz','https://millionhairz.com/about'),
   ('framcambridge','https://framcambridge.com/pages/about'),
   ('crowntocuff','https://crowntocuff.com/about'),
   ('emilytallulah','https://emilytallulah.com/about'),
   ('giocondagomez','https://giocondagomez.co.uk/about'),
   ('juanweddings','https://juanweddings.com/about'),
   ('thebrowstudio','https://thebrowstudiocambridge.co.uk/about'),
   ('suave','https://suavebarber.co.uk/about'),
   ('cavani','https://cavanicambridge.co.uk/pages/about-us'),
   ('worthhouse','https://www.worth-house.co.uk/about'),
   ('acorn','https://acornguesthouse.com/about'),
   ('camhouse','https://www.cambridgehousehotel.co.uk/about'),
   ('bydi','https://bydi.co.uk/about'),
   ('yads','https://yadsbarber.com/about'),
   ('drfrancis','https://drfrancisbraces.co.uk/about-us/'),
   ('dentistryandmore','https://dentistryandmore.co.uk/meet-the-team/'),
   ('physiofit','https://physiofitcambridge.co.uk/meet-the-team/'),
   ('mbhair','https://mb-hairstudio.co.uk/our-story'),
   ('reeds','https://reedshair.com/meet-the-team/'),
   ('totalhealth','https://totalhealthclinics.com/about-us/'),
   ('bespoketailor','https://www.thebespoketailor.co.uk/about/'),
   ('cambridgebridal','https://www.cambridgebridalstudio.co.uk/about'),
   ('nomads','https://nomadscambridge.com/our-story'),
   ('beauwithyana','https://beauwithyana.com/about'),
   ('bottisham','https://bottishambarber.co.uk/about'),
   ('fairways','https://fairwaysguesthouse.com/about'),
   ('camguesthouse','https://thecambridgeguesthouse.co.uk/about'),
   ('thefold','https://thefoldcambridge.com/our-story'),
   ('rubinallen','https://rubinallenpt.co.uk/about'),
   ('tfm','https://tfmbutchers.co.uk/about'),
   ('galleryabove','https://galleryabove.co.uk/about')]
KEY=re.compile(r"(founder|founded|owner|proprietor|established|principal|director|husband and wife|my name is|i'm |i am |family run|family-run|run by|third generation|generation)",re.I)
NAMEY=re.compile(r"\b[A-Z][a-zà-ÿ']{2,14}\s+[A-Z][a-zà-ÿ'\-]{2,18}\b")
def go(a):
    k,u=a
    r=subprocess.run(['curl','-sL','--max-time','20','--compressed','-A',UA,u],capture_output=True,text=True,errors='ignore')
    s=r.stdout
    if len(s)<1200: return k,'FAIL'
    s=re.sub(r'<(script|style|noscript)[^>]*>.*?</\1>',' ',s,flags=re.S|re.I); s=re.sub(r'<[^>]+>',' ',s)
    t=re.sub(r'\s+',' ',html.unescape(s))
    outs=[]
    for m in KEY.finditer(t):
        sn=t[max(0,m.start()-120):m.start()+160]
        if NAMEY.search(sn) and sn not in outs: outs.append(sn)
    return k,(outs[:2] if outs else 'NONE')
with ThreadPoolExecutor(max_workers=12) as ex:
    for k,v in ex.map(go,T):
        print(f"### {k}")
        if isinstance(v,str): print('   ',v)
        else:
            for s in v: print('   ~',s[:230])
