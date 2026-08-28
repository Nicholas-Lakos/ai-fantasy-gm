(()=>{
  const normalize=n=>String(n||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9 ]/g,'').replace(/\s+/g,' ').trim();
  const ratings={};
  const cls=o=>o>=90?'ovr-elite':o>=80?'ovr-great':o>=70?'ovr-good':o>=60?'ovr-average':o>=50?'ovr-below':'ovr-poor';

  function rosterNames(){
    const out=[]; const seen=new Set();
    document.querySelectorAll('#roster .pn,#opRoster .pn,#waiverRows .pn').forEach(el=>{
      const n=String(el.textContent||'').trim(), k=normalize(n);
      if(n&&k&&!seen.has(k)){seen.add(k);out.push(n)}
    });
    return out;
  }

  function installStyle(){
    if(document.getElementById('live-ovr-style'))return;
    const s=document.createElement('style');s.id='live-ovr-style';
    s.textContent=`
      .live-ovr-badge{display:inline-flex;align-items:center;justify-content:center;min-width:32px;height:24px;padding:0 7px;margin-left:7px;border-radius:6px;font-size:13px;font-weight:950;line-height:1;vertical-align:middle;border:1px solid rgba(255,255,255,.14)}
      .live-ovr-badge.ovr-elite{background:#b42335;color:#fff}.live-ovr-badge.ovr-great{background:#c96b1d;color:#fff}.live-ovr-badge.ovr-good{background:#c6a72b;color:#111}.live-ovr-badge.ovr-average{background:#218c62;color:#fff}.live-ovr-badge.ovr-below{background:#276ea8;color:#fff}.live-ovr-badge.ovr-poor{background:#4b5563;color:#fff}
      .live-label{display:inline-block;margin-left:6px;padding:3px 6px;border-radius:4px;background:#31465a;color:#cbd7e2;font-size:9px;font-weight:900;letter-spacing:.7px;vertical-align:middle}
    `;
    document.head.appendChild(s);
  }

  async function loadLiveLeagueOVRs(){
    const names=rosterNames();
    if(!names.length)return 0;
    try{
      const qs=names.map(n=>'names='+encodeURIComponent(n)).join('&');
      const r=await fetch('/api/show/live-ratings?'+qs+'&cacheBust='+Date.now(),{cache:'no-store',credentials:'include'});
      if(!r.ok)throw new Error('Live OVR endpoint '+r.status);
      const data=await r.json();
      for(const p of (data.players||[])){
        const o=Number(p.overall);
        if(p.name&&Number.isFinite(o))ratings[normalize(p.name)]=Math.round(o);
      }
      window.SHOW_LIVE_RATINGS=ratings;
      window.SHOW_LIVE_RATINGS_META={league_players:data.league_players||names.length,matched_players:data.matched_players||Object.keys(ratings).length};
      patchVisible();
      return Object.keys(ratings).length;
    }catch(e){console.warn('Live Series OVR refresh failed',e);return 0}
  }

  function patchRow(row){
    const nameEl=row.querySelector('.pn');
    if(!nameEl)return;
    const name=String(nameEl.textContent||'').trim();
    const o=ratings[normalize(name)];
    if(!Number.isFinite(o))return;

    let badge=nameEl.parentElement?.querySelector('.live-ovr-badge');
    if(!badge){
      badge=document.createElement('span');
      badge.className='live-ovr-badge';
      nameEl.insertAdjacentElement('afterend',badge);
    }
    badge.className='live-ovr-badge '+cls(o);
    badge.textContent=String(o);
    badge.title='MLB The Show 26 Live Series Overall';

    let live=nameEl.parentElement?.querySelector('.live-label');
    if(!live){
      live=document.createElement('span');live.className='live-label';live.textContent='LIVE';
      nameEl.insertAdjacentElement('afterend',live);
    }
  }

  function patchVisible(){
    document.querySelectorAll('#roster tr,#waiverRows tr,#opRoster tr').forEach(patchRow);
  }

  function observe(){
    const targets=['roster','waiverRows','opRoster'];
    const observer=new MutationObserver(()=>{
      patchVisible();
      clearTimeout(observer._timer);
      observer._timer=setTimeout(loadLiveLeagueOVRs,150);
    });
    targets.forEach(id=>{const el=document.getElementById(id);if(el)observer.observe(el,{childList:true,subtree:true})});
  }

  async function start(){
    installStyle();
    observe();
    await loadLiveLeagueOVRs();
    patchVisible();
    window.dispatchEvent(new CustomEvent('show-live-ratings-ready'));
  }

  window.loadLiveLeagueOVRs=loadLiveLeagueOVRs;
  start();
  setInterval(loadLiveLeagueOVRs,3600000);
})();
