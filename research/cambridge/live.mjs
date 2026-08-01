import puppeteer from '/Users/theshumba/Documents/GitHub/crescendo-crm/node_modules/puppeteer-core/lib/esm/puppeteer/puppeteer-core.js';
const b=await puppeteer.launch({executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:'new',args:['--no-sandbox']});
const p=await b.newPage(); await p.setViewport({width:1500,height:1000});
await p.setRequestInterception(true);
let blocked=0;
p.on('request',r=>{if(/firebase|firestore|gstatic|googleapis|google\.com/.test(r.url())){blocked++;return r.abort();}r.continue();});
await p.evaluateOnNewDocument(u=>{localStorage.setItem('crescendo-crm-user',u);},'Ameer Munj');
await p.goto('https://theshumba.github.io/crescendo-crm/crescendo-crm.html?t='+Date.now(),{waitUntil:'networkidle0'});
await new Promise(r=>setTimeout(r,2500));
const r=await p.evaluate(()=>{showSection('cambridge-boutique');renderCambridgeBoutique();
 return {cards:document.querySelectorAll('#cambridge-list .lead-card').length,
   badge:(document.getElementById('badge-cambridge-boutique')||{}).textContent,
   title:(document.getElementById('topbar-section-title')||{}).textContent,
   leadBankLeak:getFilteredLeadBank().leads.filter(l=>l.list).length,
   qualLeak:getFilteredQualified().leads.filter(l=>l.list).length};});
console.log(JSON.stringify(r),'| cloud requests blocked:',blocked);
await b.close();
