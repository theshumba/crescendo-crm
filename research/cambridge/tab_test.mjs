import puppeteer from '/Users/theshumba/Documents/GitHub/crescendo-crm/node_modules/puppeteer-core/lib/esm/puppeteer/puppeteer-core.js';
const CHROME='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const FILE='file:///Users/theshumba/Documents/GitHub/crescendo-crm/crescendo-crm.html';
const out=[]; const ck=(n,p,d)=>{out.push([n,p,d]);console.log((p?'  PASS  ':'  FAIL  ')+n+(d?'  — '+d:''));};
const b=await puppeteer.launch({executablePath:CHROME,headless:'new',args:['--no-sandbox']});
const p=await b.newPage(); await p.setViewport({width:1400,height:1000});
await p.setRequestInterception(true);
p.on('request',r=>/firebase|firestore|gstatic|googleapis|google\.com/.test(r.url())?r.abort():r.continue());
const errs=[]; p.on('pageerror',e=>errs.push(String(e))); p.on('console',m=>{if(m.type()==='error')errs.push('console: '+m.text());});
await p.evaluateOnNewDocument(u=>{localStorage.setItem('crescendo-current-user',u);localStorage.setItem('crescendo-team-gate','1');},'Ameer Munj');
await p.goto(FILE,{waitUntil:'networkidle0'}); await new Promise(r=>setTimeout(r,1800));

const base=await p.evaluate(()=>({
  total: state.leads.filter(l=>l.list==='cambridge-boutique').length,
  badge: (document.getElementById('badge-cambridge-boutique')||{}).textContent,
  navUnderQualified: (()=>{const n=[...document.querySelectorAll('.nav-item')].map(x=>x.dataset.section);
     return n[n.indexOf('qualified-leads')+1]==='cambridge-boutique';})(),
  inLeadBank: getFilteredLeadBank().leads.filter(l=>l.list).length,
  inQualified: getFilteredQualified().leads.filter(l=>l.list).length,
  badPhone: state.leads.filter(l=>l.list).filter(l=>typeof (l.phones[0]||{}).number!=='string'||!l.phones[0].number).length,
  noOwner: state.leads.filter(l=>l.list).filter(l=>!(l.contacts||[]).some(c=>c.name)).length,
  noSite: state.leads.filter(l=>l.list).filter(l=>!l.website).length,
  dupIds: (()=>{const i=state.leads.map(l=>l.id);return i.length-new Set(i).size;})()
}));
ck('52 Cambridge leads seeded', base.total===52, base.total+' leads');
ck('sidebar badge shows the count', base.badge==='52', 'badge '+base.badge);
ck('tab sits directly under Qualified Leads', base.navUnderQualified);
ck('they stay out of the Lead Bank', base.inLeadBank===0, base.inLeadBank+' leaked');
ck('they stay out of Qualified Leads', base.inQualified===0, base.inQualified+' leaked');
ck('every lead has a real phone string', base.badPhone===0);
ck('every lead has a named owner', base.noOwner===0);
ck('every lead has a website', base.noSite===0);
ck('no duplicate ids', base.dupIds===0);

const ui=await p.evaluate(()=>{showSection('cambridge-boutique');renderCambridgeBoutique();
  return {cards:document.querySelectorAll('#cambridge-list .lead-card').length,
          count:(document.getElementById('cbq-count')||{}).textContent,
          title:(document.getElementById('topbar-section-title')||{}).textContent};});
ck('the tab renders every card', ui.cards===52, ui.cards+' cards, '+ui.count);
ck('top bar names the section', ui.title==='Cambridge Boutiques', ui.title);

const filt=await p.evaluate(()=>{
  const r={};
  state.filters.cambridge.verified='ch'; renderCambridgeList(); r.ch=document.querySelectorAll('#cambridge-list .lead-card').length;
  state.filters.cambridge.verified='web'; renderCambridgeList(); r.web=document.querySelectorAll('#cambridge-list .lead-card').length;
  state.filters.cambridge.verified='all'; state.filters.cambridge.hasEmail=true; renderCambridgeList(); r.email=document.querySelectorAll('#cambridge-list .lead-card').length;
  state.filters.cambridge.hasEmail=false; state.filters.cambridge.search='punting'; renderCambridgeList(); r.search=document.querySelectorAll('#cambridge-list .lead-card').length;
  state.filters.cambridge.search='Daniel Clifford'; renderCambridgeList(); r.owner=document.querySelectorAll('#cambridge-list .lead-card').length;
  state.filters.cambridge.search=''; renderCambridgeList(); return r;});
ck('Companies House filter splits the list', filt.ch===32 && filt.web===20, filt.ch+' CH / '+filt.web+' website');
ck('has-email filter works', filt.email===26, filt.email+' with email');
ck('search finds a category', filt.search===5, filt.search+' punting');
ck('search finds an owner by name', filt.owner===1, filt.owner+' match');

const mv=await p.evaluate(()=>{const id='cbq-fitzbillies'; moveToCRM(id); renderAll();
  const l=getLeadById(id);
  return {status:l.status, inCrmList:state.leads.filter(x=>x.status==='crm'&&x.list).length,
          stillOnTab:getFilteredCambridge().leads.some(x=>x.id===id),
          badge:(document.getElementById('badge-cambridge-boutique')||{}).textContent};});
ck('Move to CRM moves the lead', mv.status==='crm' && mv.inCrmList===1);
ck('it stays visible on its own tab', mv.stillOnTab===true);
ck('the tab badge drops to unworked only', mv.badge==='51', 'badge '+mv.badge);
const real=errs.filter(e=>!/ERR_FAILED|net::|Failed to load resource|firebase|leaflet/i.test(e));
ck('no runtime errors', real.length===0, real.slice(0,3).join(' | '));
await b.close();
const bad=out.filter(o=>!o[1]).length;
console.log(`\n${out.length-bad}/${out.length} checks passed`);
process.exit(bad?1:0);
