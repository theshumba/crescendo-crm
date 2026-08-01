import puppeteer from '/Users/theshumba/Documents/GitHub/crescendo-crm/node_modules/puppeteer-core/lib/esm/puppeteer/puppeteer-core.js';
const CHROME='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const FILE='file:///Users/theshumba/Documents/GitHub/crescendo-crm/crescendo-crm.html';
const out=[]; const ck=(n,p,d)=>{out.push([n,p,d]);console.log((p?'  PASS  ':'  FAIL  ')+n+(d?'  — '+d:''));};
const b=await puppeteer.launch({executablePath:CHROME,headless:'new',args:['--no-sandbox']});

// ---- PHASE 1: fresh install ----
let p=await b.newPage(); await p.setViewport({width:1500,height:1000});
await p.setRequestInterception(true);
p.on('request',r=>/firebase|firestore|gstatic|googleapis|google\.com/.test(r.url())?r.abort():r.continue());
const errs=[]; p.on('pageerror',e=>errs.push(String(e))); p.on('console',m=>{if(m.type()==='error')errs.push('console: '+m.text());});
await p.evaluateOnNewDocument(u=>{localStorage.setItem('crescendo-crm-user',u);},'Ameer Munj');
await p.goto(FILE,{waitUntil:'networkidle0'}); await new Promise(r=>setTimeout(r,2200));
const base=await p.evaluate(()=>{const L=state.leads.filter(l=>l.list==='cambridge-boutique');
 return {n:L.length, badge:(document.getElementById('badge-cambridge-boutique')||{}).textContent,
  noPhone:L.filter(l=>!(l.phones&&l.phones[0]&&l.phones[0].number)).length,
  noOwner:L.filter(l=>!(l.contacts||[]).some(c=>c.name&&c.name.trim().split(/\s+/).length>1)).length,
  noSite:L.filter(l=>!l.website).length,
  withResearch:L.filter(l=>l.research&&Object.keys(l.research).length).length,
  withCH:L.filter(l=>l.companiesHouse).length,
  withPostcode:L.filter(l=>l.postcode).length,
  withSocial:L.filter(l=>l.research&&l.research.social&&Object.keys(l.research.social).length).length,
  withObs:L.filter(l=>(l.observations||[]).length).length,
  withWeak:L.filter(l=>l.qualification&&l.qualification.weaknessesOpportunities).length,
  multiPhone:L.filter(l=>(l.phones||[]).length>1).length,
  dup:L.length-new Set(L.map(l=>l.id)).size,
  scores:[...new Set(L.map(l=>getOpportunityScore(l)))].sort((a,b)=>a-b)};});
ck('109 leads seeded', base.n===109, base.n+' leads');
ck('badge matches', base.badge==='109', 'badge '+base.badge);
ck('no duplicate ids', base.dup===0);
ck('every lead still has phone + full owner name + website', base.noPhone===0&&base.noOwner===0&&base.noSite===0,
   `phone gaps ${base.noPhone}, owner gaps ${base.noOwner}, site gaps ${base.noSite}`);
ck('research attached to every lead', base.withResearch===109, base.withResearch);
ck('Companies House numbers carried', base.withCH===67, base.withCH+' with CH number');
ck('postcodes captured', base.withPostcode>=55, base.withPostcode+' with postcode');
ck('social accounts captured', base.withSocial>=55, base.withSocial+' with socials');
ck('site observations captured', base.withObs>=70, base.withObs+' with observations');
ck('observations reach the qualification field', base.withWeak>=70, base.withWeak);
ck('extra phone numbers kept', base.multiPhone>=10, base.multiPhone+' with 2+ numbers');
ck('scores vary rather than sitting flat', base.scores.length>=3, 'score bands: '+base.scores.join(', '));

const filt=await p.evaluate(()=>{const r={};const F=state.filters.cambridge;
 showSection('cambridge-boutique');renderCambridgeBoutique();
 const c=()=>document.querySelectorAll('#cambridge-list .lead-card').length;
 r.all=c(); r.label=(document.getElementById('cbq-count')||{}).textContent; r.more=!!document.querySelector('[data-action="show-more"][data-scope="cambridge"]');
 F.gap='booking';renderCambridgeList();r.booking=c();
 F.gap='shop';renderCambridgeList();r.shop=c();
 F.gap='stale';renderCambridgeList();r.stale=c();
 F.gap='all';F.search='CB1';renderCambridgeList();r.postcode=c();
 // count off the filtered set, not the rendered cards: the grid pages at 60 and there are
 // more than 60 Companies House leads, so counting cards would silently measure the page size
 F.search='';F.verified='ch';r.ch=getFilteredCambridge().leads.length;
 F.verified='all';F.gap='loved';r.loved=getFilteredCambridge().leads.length;
 F.gap='all';F.search='Invisalign';r.service=getFilteredCambridge().leads.length;
 F.search='';F.sort='rating';r.sorted=getFilteredCambridge().leads.slice(0,5).map(l=>parseFloat((l.intel||{}).rating)||0);
 F.sort='name';renderCambridgeList();return r;});
ck('the tab pages the full 109', filt.all===60 && filt.label==='Showing 109 of 109' && filt.more, filt.all+' cards, label "'+filt.label+'", show-more '+filt.more);
ck('no-online-booking filter works', filt.booking>0&&filt.booking<109, filt.booking+' leads');
ck('no-online-shop filter works', filt.shop>0&&filt.shop<109, filt.shop+' leads');
ck('neglected-site filter works', filt.stale>0&&filt.stale<109, filt.stale+' leads');
ck('search reaches postcodes', filt.postcode>0, filt.postcode+' in CB1');
ck('Companies House filter works', filt.ch===67, filt.ch+' leads');
ck('search reaches the researched services', filt.service>0, filt.service+' offer Invisalign');
ck('loved-but-unbookable filter narrows', filt.loved>0&&filt.loved<109, filt.loved+' leads');
ck('rating sort puts the best rated first', filt.sorted[0]>=filt.sorted[4]&&filt.sorted[0]>0, filt.sorted.join(', '));

// ---- the researched brief ----
const brief=await p.evaluate(()=>{const L=state.leads.filter(l=>l.list==='cambridge-boutique');
 const r={withIntel:L.filter(l=>l.intel&&l.intel.what).length,
  withRating:L.filter(l=>l.intel&&l.intel.rating).length,
  withSources:L.filter(l=>(l.intel&&l.intel.sources||[]).length).length,
  withPress:L.filter(l=>(l.intel&&l.intel.press||[]).length).length};
 // no fabricated ratings: every rating must be a real number inside the 0-5 range
 r.badRating=L.filter(l=>l.intel&&l.intel.rating&&!(parseFloat(l.intel.rating)>0&&parseFloat(l.intel.rating)<=5)).length;
 // every press or award claim must carry a URL a rep can open
 r.pressNoUrl=L.reduce((n,l)=>n+((l.intel&&l.intel.press||[]).filter(x=>!x.url||!/^https?:\/\//.test(x.url)).length),0);
 const rated=L.find(l=>l.intel&&l.intel.rating);
 openPanel('view-qualification',rated);
 const html=document.getElementById('panel-content').innerHTML;
 r.panelHasBrief=/Research brief/.test(html);
 r.panelHasWhat=html.includes(rated.intel.what.slice(0,40));
 r.panelHasSources=/Read during research/.test(html);
 r.panelName=rated.businessName;
 closePanel();
 showSection('cambridge-boutique');renderCambridgeBoutique();
 r.cardStar=/★|&#9733;|★/.test(document.getElementById('cambridge-list').innerHTML);
 return r;});
ck('a research brief is attached to every lead', brief.withIntel===109, brief.withIntel+' with a brief');
ck('sources recorded for every lead', brief.withSources===109, brief.withSources+' with sources');
ck('no rating outside the 0 to 5 range', brief.badRating===0, brief.badRating+' bad');
ck('every press mention carries an openable link', brief.pressNoUrl===0, brief.withPress+' leads with press, '+brief.pressNoUrl+' missing a URL');
ck('View Full shows the brief', brief.panelHasBrief&&brief.panelHasWhat&&brief.panelHasSources, brief.panelName);
ck('the card shows the star rating', brief.cardStar);
await p.close();

// ---- PHASE 2: existing install with rep work already done on a v1 lead ----
p=await b.newPage(); await p.setViewport({width:1400,height:900});
await p.setRequestInterception(true);
p.on('request',r=>/firebase|firestore|gstatic|googleapis|google\.com/.test(r.url())?r.abort():r.continue());
p.on('pageerror',e=>errs.push(String(e)));
await p.evaluateOnNewDocument(()=>{
  localStorage.setItem('crescendo-crm-user','Ameer Munj');
  const v1=[{id:'cbq-fitzbillies',businessName:'Fitzbillies',industry:'Bakery & cafe',
    website:'https://fitzbillies.com',address:'REP TYPED THIS ADDRESS',phones:[{number:'01223 211150'}],
    emails:[],contacts:[{name:'Tim Hayward',title:'Director',phone:'01223 211150',email:''}],
    description:'REP TYPED THIS NOTE',source:'research',status:'crm',list:'cambridge-boutique',
    companiesHouse:'07596472',dateAdded:'2026-08-01',assignedTo:'Yousuf Zacky',
    qualification:{strategyDesign:'High fit',experienceDesign:'',digitalCommerce:'',growthIntent:'',weaknessesOpportunities:'',dateQualified:'2026-08-01'},
    crm:{stage:4,disposition:'nurture',priority:'high',notes:[{text:'Spoke to Tim, keen',by:'Yousuf Zacky',date:'2026-08-01T10:00:00.000Z'}],
      followUpDate:'2026-08-09',dateMovedToCRM:'2026-08-01',dealValue:15000,outcomeReason:'',meetingBooked:false,meetingDate:'',meetingNotes:'',dateFirstContact:'2026-08-01',dateLastContact:'2026-08-01'},
    activity:[{action:'logged a call',by:'Yousuf Zacky',date:'2026-08-01T10:00:00.000Z'}]}];
  localStorage.setItem('crescendo-leads',JSON.stringify(v1));
});
await p.goto(FILE,{waitUntil:'networkidle0'}); await new Promise(r=>setTimeout(r,2200));
const up=await p.evaluate(()=>{const l=getLeadById('cbq-fitzbillies');
 return {found:!!l,status:l&&l.status,stage:l&&l.crm&&l.crm.stage,notes:l&&l.crm&&l.crm.notes.length,
   note:l&&l.crm&&l.crm.notes[0]&&l.crm.notes[0].text,activity:l&&l.activity.length,
   assigned:l&&l.assignedTo,rubric:l&&l.qualification.strategyDesign,
   addr:l&&l.address,desc:l&&l.description,
   gotResearch:!!(l&&l.research&&l.research.incorporated),gotObs:!!(l&&(l.observations||[]).length),
   gotIntel:!!(l&&l.intel&&l.intel.what),
   gotEmail:(l&&l.emails||[]).length, ver:l&&l.cbqVersion,
   total:state.leads.filter(x=>x.list==='cambridge-boutique').length};});
ck('the existing lead is still there, not duplicated', up.found&&up.total===109, up.total+' leads');
ck('rep pipeline work survives', up.status==='crm'&&up.stage===4, `status ${up.status}, stage ${up.stage}`);
ck('rep notes and activity survive', up.notes===1&&up.activity===1&&up.note==='Spoke to Tim, keen');
ck('who is on it survives', up.assigned==='Yousuf Zacky', up.assigned);
ck('rep-typed rubric is not overwritten', up.rubric==='High fit', up.rubric);
ck('rep-typed address and note are not overwritten', up.addr==='REP TYPED THIS ADDRESS'&&up.desc==='REP TYPED THIS NOTE');
ck('new research lands on the old lead', up.gotResearch&&up.gotObs, 'research '+up.gotResearch+', observations '+up.gotObs);
ck('the v3 brief reaches a lead seeded before it existed', up.gotIntel, 'intel '+up.gotIntel);
ck('newly found emails are added', up.gotEmail>0, up.gotEmail+' emails');
ck('version marker set so it only upgrades once', up.ver===3, 'v'+up.ver);
const real=errs.filter(e=>!/ERR_FAILED|net::|Failed to load resource|firebase|leaflet/i.test(e));
ck('no runtime errors', real.length===0, real.slice(0,3).join(' | '));
await b.close();
const bad=out.filter(o=>!o[1]).length;
console.log(`\n${out.length-bad}/${out.length} checks passed`);
process.exit(bad?1:0);
