import puppeteer from '/Users/theshumba/Documents/GitHub/crescendo-crm/node_modules/puppeteer-core/lib/esm/puppeteer/puppeteer-core.js';
const b=await puppeteer.launch({executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:'new',args:['--no-sandbox','--allow-file-access-from-files']});
const p=await b.newPage(); await p.setViewport({width:420,height:900,deviceScaleFactor:2});
await p.setRequestInterception(true);
p.on('request',r=>/firebase|firestore|gstatic|googleapis|google\.com/.test(r.url())?r.abort():r.continue());
await p.evaluateOnNewDocument(u=>{try{localStorage.setItem('crescendo-current-user',u);localStorage.setItem('crescendo-team-gate','1');}catch(e){}},'Ameer Munj');
await p.goto('file:///private/tmp/claude-501/-Users-theshumba/f1c00501-bc1c-4e62-aa8c-40bd7e22b950/scratchpad/cam/wrap.html',{waitUntil:'networkidle0'});
await new Promise(r=>setTimeout(r,2500));
const fr=p.frames().find(f=>f.url().includes('crescendo-crm.html'));
const res=await fr.evaluate(()=>{showSection('cambridge-boutique');renderCambridgeBoutique();
  const d=document.documentElement;
  const cards=[...document.querySelectorAll('#cambridge-list .lead-card')];
  const over=cards.filter(c=>c.scrollWidth>c.clientWidth+1).length;
  return {pageOverflow:d.scrollWidth-d.clientWidth, cards:cards.length, cardOverflow:over,
    widest:Math.max(...cards.map(c=>c.getBoundingClientRect().width)), vw:d.clientWidth,
    inMore:(renderMoreSheet(),[...document.querySelectorAll('[data-more-section]')]).map(x=>x.dataset.moreSection).includes('cambridge-boutique')};});
console.log(JSON.stringify(res,null,1));
await p.screenshot({path:'/private/tmp/claude-501/-Users-theshumba/f1c00501-bc1c-4e62-aa8c-40bd7e22b950/scratchpad/cam/mobile.png'});
await b.close();
