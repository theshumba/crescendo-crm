import puppeteer from '/Users/theshumba/Documents/GitHub/crescendo-crm/node_modules/puppeteer-core/lib/esm/puppeteer/puppeteer-core.js';
const b=await puppeteer.launch({executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:'new',args:['--no-sandbox','--allow-file-access-from-files']});
const p=await b.newPage(); await p.setViewport({width:420,height:920,deviceScaleFactor:2});
await p.setRequestInterception(true);
p.on('request',r=>/firebase|firestore|gstatic|googleapis|google\.com/.test(r.url())?r.abort():r.continue());
await p.goto('file:///private/tmp/claude-501/-Users-theshumba/f1c00501-bc1c-4e62-aa8c-40bd7e22b950/scratchpad/cam/wrap.html',{waitUntil:'networkidle0'});
await new Promise(r=>setTimeout(r,2000));
let fr=p.frames().find(f=>f.url().includes('crescendo-crm.html'));
await fr.evaluate(()=>{try{localStorage.setItem('crescendo-current-user','Ameer Munj');localStorage.setItem('crescendo-team-gate','1');}catch(e){}});
await p.reload({waitUntil:'networkidle0'}); await new Promise(r=>setTimeout(r,2500));
fr=p.frames().find(f=>f.url().includes('crescendo-crm.html'));
const r=await fr.evaluate(()=>{
  document.querySelectorAll('.login-overlay,#login-overlay,.modal-overlay').forEach(e=>e.classList.remove('active'));
  showSection('cambridge-boutique');renderCambridgeBoutique();window.scrollTo(0,0);
  const d=document.documentElement;
  return {overflow:d.scrollWidth-d.clientWidth, cards:document.querySelectorAll('#cambridge-list .lead-card').length};});
console.log(JSON.stringify(r));
await p.screenshot({path:'/private/tmp/claude-501/-Users-theshumba/f1c00501-bc1c-4e62-aa8c-40bd7e22b950/scratchpad/cam/mobile2.png'});
await b.close();
