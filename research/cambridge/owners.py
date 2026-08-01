import json,re,html
W='/private/tmp/claude-501/-Users-theshumba/f1c00501-bc1c-4e62-aa8c-40bd7e22b950/scratchpad/cam/'
sf=json.load(open(W+'site_files.json'))
KEY=re.compile(r"(founder|co-founder|founded|owner|owned|proprietor|established|principal|director|chef patron|husband and wife|my name is|i'm |i am |meet |our story|salon owner|lead (?:clinician|nurse|dentist|therapist)|started (?:by|the|her|his|our)|runs|run by)",re.I)
NAMEY=re.compile(r"\b[A-Z][a-zà-ÿ']{2,14}\s+[A-Z][a-zà-ÿ'\-]{2,18}\b")
def text(f):
    s=open(f,errors='ignore').read()
    s=re.sub(r'<(script|style|noscript)[^>]*>.*?</\1>',' ',s,flags=re.S|re.I)
    s=re.sub(r'<[^>]+>',' ',s)
    return re.sub(r'\s+',' ',html.unescape(s))
for dom in sorted(sf):
    outs=[]
    for f in sf[dom]:
        t=text(f)
        for m in KEY.finditer(t):
            s=t[max(0,m.start()-130):m.start()+170]
            if NAMEY.search(s) and s not in outs: outs.append(s)
    if not outs: 
        print(f"### {dom} :: NO-SNIPPET"); continue
    print(f"### {dom}")
    for s in outs[:3]: print("   ~",s[:250])
