(()=>{
  const norm=s=>String(s||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/[^a-z0-9 ]/gi,'').replace(/\s+/g,' ').trim().toLowerCase();
  const ratings={};
  let timer=0;

  function names(){
    const out=[]; const seen=new Set();
    document.querySelectorAll('#roster .pn,#opRoster .pn,#waiverRows .pn').forEach(el=>{
      const n=String(el.textContent||'').trim(), k=norm(n);
      if(n&&k&&!seen.has(k)){seen.add(k);out.push(n)}
    });
    return out;
  }

  function cls(o){return o>=90?'show-elite':o>=80?'show-great':o>=70?'show-good':o>=60?'show-average':o>=50?'show-below':'show-poor'}

  function paint(){
    document.querySelectorAll('#roster tr,#opRoster tr,#waiverRows tr').forEach(row=>{
      const name=row.querySelector('.pn'); if(!name)return;
      const o=ratings[norm(name.textContent)]; if(!Number.isFinite(o))return;
      const avatar=row.querySelector('.avatar'); if(!avatar)return;
      avatar.textContent=String(o);
      avatar.dataset.showOvr=String(o);
      avatar.classList.remove('show-elite','show-great','show-good','show-average','show-below','show-poor');
      avatar.classList.add(cls(o));
      avatar.title='MLB The Show 26 Live Series Overall';
    });
  }

  async function load(){
    const ns=names(); if(!ns.length)return;
    try{
      const qs=ns.map(n=>'names='+encodeURIComponent(n)).join('&');
      const r=await fetch('/api/show/live-ratings?'+qs+'&displayFix='+Date.now(),{cache:'no-store',credentials:'include'});
      if(!r.ok)throw new Error('HTTP '+r.status);
      const data=await r.json();
      for(const p of (data.players||[])){
        const o=Number(p.overall); const n=p.name;
        if(n&&Number.isFinite(o))ratings[norm(n)]=Math.round(o);
      }
      paint();
      window.SHOW_LIVE_RATINGS=ratings;
      window.SHOW_LIVE_RATINGS_READY=Object.keys(ratings).length>0;
    }catch(e){console.warn('Live OVR display fix:',e)}
  }

  function schedule(){clearTimeout(timer);timer=setTimeout(load,250)}
  function start(){
    const style=document.createElement('style');
    style.textContent='.avatar.show-elite{background:#c62828!important;color:#fff!important}.avatar.show-great{background:#ef6c00!important;color:#fff!important}.avatar.show-good{background:#fbc02d!important;color:#111!important}.avatar.show-average{background:#2e7d32!important;color:#fff!important}.avatar.show-below{background:#1976d2!important;color:#fff!important}.avatar.show-poor{background:#555!important;color:#fff!important}';
    document.head.appendChild(style);
    const observer=new MutationObserver(schedule);
    ['roster','opRoster','waiverRows'].forEach(id=>{const el=document.getElementById(id);if(el)observer.observe(el,{childList:true,subtree:true})});
    load();
    setTimeout(load,1000);setTimeout(load,3000);setTimeout(load,6000);
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start);else start();
})();
