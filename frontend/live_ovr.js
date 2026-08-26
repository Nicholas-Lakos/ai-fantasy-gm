(()=>{
  const normalize=n=>String(n||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9 ]/g,'').replace(/\s+/g,' ').trim();
  const ratings={};
  const cls=o=>o>=90?'ovr-elite':o>=80?'ovr-great':o>=70?'ovr-good':o>=60?'ovr-average':o>=50?'ovr-below':'ovr-poor';
  async function loadLiveLeagueOVRs(){
    const token=localStorage.getItem('gm_token')||'';
    if(!token)return 0;
    try{
      const r=await fetch('/api/show/live-ratings',{cache:'no-store',headers:{Authorization:'Bearer '+token}});
      if(!r.ok)throw new Error('Live OVR endpoint '+r.status);
      const data=await r.json();
      for(const p of (data.players||[])){
        const o=Number(p.overall);
        if(p.name&&Number.isFinite(o))ratings[normalize(p.name)]=Math.round(o);
      }
      window.SHOW_LIVE_RATINGS=ratings;
      window.SHOW_LIVE_RATINGS_META={league_players:data.league_players||0,matched_players:data.matched_players||0};
      return Object.keys(ratings).length;
    }catch(e){console.warn('Live Series OVR refresh failed',e);return 0}
  }
  function patchRow(row){
    const name=row.querySelector('.pn')?.textContent?.trim();
    const o=ratings[normalize(name)];
    if(!Number.isFinite(o))return;
    const avatar=row.querySelector('.avatar');
    if(!avatar)return;
    avatar.className='avatar '+cls(o);
    avatar.textContent=String(o);
    avatar.title='MLB The Show 26 Live Series OVR';
    avatar.setAttribute('data-show-ovr',String(o));
    const sub=row.querySelector('.sub');
    if(sub && !String(sub.textContent||'').includes('INJURED'))sub.textContent='MLB The Show 26 Live Series OVR '+o;
  }
  function patchVisible(){
    document.querySelectorAll('#roster tr,#waiverRows tr,#opRoster tr').forEach(patchRow);
  }
  const install=()=>{
    const old=window.playerRow;
    if(typeof old==='function' && !old.__liveWrapped){
      const wrapped=function(p,w){
        const html=old.call(this,p,w);
        const o=ratings[normalize(p?.name)];
        if(!Number.isFinite(o))return html;
        return html.replace(/<div class="avatar[^>]*>.*?<\/div>/,'<div class="avatar '+cls(o)+'" title="MLB The Show 26 Live Series OVR" data-show-ovr="'+o+'">'+o+'</div>');
      };
      wrapped.__liveWrapped=true;
      window.playerRow=wrapped;
    }
  };
  async function start(){
    install();
    await loadLiveLeagueOVRs();
    patchVisible();
    install();
    patchVisible();
    window.dispatchEvent(new CustomEvent('show-live-ratings-ready'));
  }
  window.loadLiveLeagueOVRs=loadLiveLeagueOVRs;
  start();
  setInterval(()=>{loadLiveLeagueOVRs().then(()=>{install();patchVisible()})},3600000);
})();
