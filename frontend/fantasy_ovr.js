(()=>{
  const norm=v=>String(v||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/[^a-z0-9 ]/gi,'').replace(/\s+/g,' ').trim().toLowerCase();
  const cls=o=>o>=90?'ovr-elite':o>=80?'ovr-great':o>=70?'ovr-good':o>=60?'ovr-average':o>=50?'ovr-below':'ovr-poor';
  let ratings=new Map(),loading=false;

  function authToken(){
    return localStorage.getItem('gm_token') || localStorage.getItem('token') || localStorage.getItem('auth_token') || '';
  }

  function rowName(row){
    const el=row.querySelector('.pn,.showdd-name');
    return el ? String(el.textContent||'').trim() : '';
  }

  function paint(){
    document.querySelectorAll('#roster tr.row,#opRoster tr.row,#waiverRows tr.row').forEach(row=>{
      const name=rowName(row); if(!name)return;
      const data=ratings.get(norm(name)); if(!data)return;
      const o=Math.round(Number(data.fantasy_ovr)); if(!Number.isFinite(o))return;
      const avatar=row.querySelector('.avatar');
      if(avatar){
        avatar.textContent=String(o);
        avatar.className='avatar '+cls(o);
        avatar.title='AI Fantasy GM OVR · calculated from ESPN fantasy stats';
        avatar.dataset.fantasyOvr=String(o);
        avatar.removeAttribute('data-show-ovr');
      }
      const live=row.querySelector('.showdd-live,.live-label,.live-ovr-badge');
      if(live)live.remove();
      const oldSub=row.querySelector('.showdd-sub');
      if(oldSub && /live series/i.test(oldSub.textContent||''))oldSub.textContent='ESPN fantasy stats';
      const pn=row.querySelector('.pn');
      const sub=pn?.parentElement?.querySelector('.sub,.showdd-sub');
      if(sub){
        sub.textContent='Fantasy OVR '+o+' · ESPN stats';
        sub.title='Season '+(data.total_points??'—')+' pts · Avg '+(data.average_fantasy_points??'—')+' pts/day · Recent '+(data.recent_average??'—')+' pts/day';
      }
    });
  }

  async function load(){
    const token=authToken();
    if(!token||loading)return false;
    loading=true;
    try{
      const r=await fetch('/api/fantasy-ovr?ts='+Date.now(),{cache:'no-store',credentials:'include',headers:{Authorization:'Bearer '+token}});
      if(!r.ok)throw new Error('Fantasy OVR HTTP '+r.status);
      const j=await r.json();
      const list=Array.isArray(j.players)?j.players:[];
      const next=new Map();
      list.forEach(p=>{
        const o=Number(p.fantasy_ovr);
        if(p?.name&&Number.isFinite(o))next.set(norm(p.name),p);
      });
      ratings=next;
      window.FANTASY_OVR_READY=ratings.size>0;
      window.FANTASY_OVR_SOURCE='ESPN Fantasy Baseball stats';
      window.FANTASY_OVR_COUNT=ratings.size;
      window.FANTASY_OVR_ERROR='';
      paint();
      return ratings.size>0;
    }catch(e){
      window.FANTASY_OVR_READY=false;
      window.FANTASY_OVR_ERROR=String(e.message||e);
      console.warn('Fantasy OVR unavailable:',e);
      return false;
    }finally{loading=false}
  }

  function removeLegacy(){
    document.querySelectorAll('.live-ovr-badge,.live-label,.showdd-live').forEach(e=>e.remove());
    document.querySelectorAll('.showdd-sub').forEach(e=>{if(/live series/i.test(e.textContent||''))e.textContent='ESPN fantasy stats'});
  }

  function start(){
    removeLegacy();
    const observer=new MutationObserver(()=>{removeLegacy();paint()});
    observer.observe(document.body,{subtree:true,childList:true});
    load();
    [1000,2500,5000,10000].forEach(ms=>setTimeout(load,ms));
    setInterval(()=>{if(authToken())load()},120000);
    setInterval(()=>{removeLegacy();paint()},500);
  }

  window.refreshFantasyOVR=load;
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start,{once:true});else start();
})();
