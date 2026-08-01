import puppeteer from '/Users/theshumba/Documents/GitHub/crescendo-crm/node_modules/puppeteer-core/lib/esm/puppeteer/puppeteer-core.js';
const b=await puppeteer.launch({executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:'new',args:['--no-sandbox','--allow-file-access-from-files']});
const p=await b.newPage(); await p.setViewport({width:430,height:900,deviceScaleFactor:2});
await p.setRequestInterception(true);
p.on('request',r=>/firebase|firestore|gstatic|googleapis|google\.com/.test(r.url())?r.abort():r.continue());
await p.goto('file:///Users/theshumba/Documents/GitHub/crescendo-crm/research/cambridge/wrap.html',{waitUntil:'networkidle0'});
await new Promise(r=>setTimeout(r,2000));
let fr=p.frames().find(f=>f.url().includes('crescendo-crm.html'));
await fr.evaluate(()=>{try{localStorage.setItem('crescendo-crm-user','Ameer Munj');}catch(e){}});
await p.reload({waitUntil:'networkidle0'}); await new Promise(r=>setTimeout(r,2600));
fr=p.frames().find(f=>f.url().includes('crescendo-crm.html'));
const r=await fr.evaluate(()=>{
  showSection('cambridge-boutique');renderCambridgeBoutique();
  const d=document.documentElement,bd=document.body;
  const grid=document.querySelector('#cambridge-list .lead-grid');
  const cards=[...document.querySelectorAll('#cambridge-list .lead-card')];
  const widths=cards.map(c=>Math.round(c.getBoundingClientRect().width));
  const rights=cards.map(c=>Math.round(c.getBoundingClientRect().right));
  return {vw:d.clientWidth, docScroll:d.scrollWidth, bodyScroll:bd.scrollWidth,
    gridScroll:grid?grid.scrollWidth:null, gridClient:grid?grid.clientWidth:null,
    maxCardW:Math.max(...widths), maxRight:Math.max(...rights), cards:cards.length,
    overflowingCards:cards.filter(c=>c.scrollWidth>c.clientWidth+1).length,
    loginUp:!!document.querySelector('.login-overlay.active,#login-overlay.active'),
    culprits:(()=>{const bad=[];cards.forEach(c=>{if(c.scrollWidth<=c.clientWidth+1)return;
      [...c.querySelectorAll('*')].forEach(el=>{const w=el.getBoundingClientRect().width;
        if(w>c.clientWidth+1)bad.push((el.className||el.tagName)+' :: '+w.toFixed(0)+' :: '+el.textContent.trim().slice(0,60));});});
      return [...new Set(bad)].slice(0,8);})()};});
console.log(JSON.stringify(r,null,1));
await p.screenshot({path:'/Users/theshumba/Documents/GitHub/crescendo-crm/research/cambridge/mobile-check.png'});
await b.close();
