(()=>{
  const norm=v=>String(v||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/[^a-z0-9 ]/gi,'').replace(/\s+/g,' ').trim().toLowerCase();
  const cls=o=>o>=90?'ovr-elite':o>=80?'ovr-great':o>=70?'ovr-good':o>=60?'ovr-average':o>=50?'ovr-below':'ovr-poor';
  let ratings=new Map(),busy=false;

  async function load(){
    const token=localStorage.getItem('gm_token')||'';
    if(!token||busy)return;
    busy=true;
    try{
      const r=await fetch('/api/fantasy-ovr?ts='+Date.now(),{cache:'no-store',headers:{Authorization:'Bearer '+token}});
      if(!r.ok)throw new Error('Fantasy OVR request failed: '+r.status);
      const j=await r.json();
      ratings=new Map((j.players||[]).filter(p=>p.name&&Number.isFinite(Number(p.fantasy_ovr))).map(p=>[norm(p.name),p]));
      window.FANTASY_OVR_READY=ratings.size>0;
      window.FANTASY_OVR_SOURCE=j.source||'ESPN Fantasy Baseball stats';
      paint();
    }catch(e){console.warn('ESPN Fantasy OVR unavailable',e);window.FANTASY_OVR_READY=false}
    finally{busy=false}
  }

  function paint(){
    document.querySelectorAll('tr.row').forEach(row=>{
      const nameEl=row.querySelector('.pn');
      if(!nameEl)return;
      const data=ratings.get(norm(nameEl.textContent));
      if(!data)return;
      const o=Math.round(Number(data.fantasy_ovr));
      if(!Number.isFinite(o))return;
      const avatar=row.querySelector('.avatar');
      if(avatar){
        avatar.textContent=String(o);
        avatar.className='avatar '+cls(o);
        avatar.title='AI Fantasy GM OVR · calculated from live ESPN stats';
        avatar.dataset.fantasyOvr=String(o);
      }
      const sub=nameEl.parentElement?.querySelector('.sub');
      if(sub){
        sub.textContent='Fantasy OVR '+o+' · ESPN stats';
        sub.title=`Season ${data.total_points??'—'} pts · Avg ${data.average_fantasy_points??'—'} pts/day · Recent ${data.recent_average??'—'} pts/day`;
      }
    });
  }

  function addLabel(){
    if(document.getElementById('fantasy-ovr-note'))return;
    const team=document.getElementById('team');
    if(!team)return;
    const card=team.querySelector('.card.full');
    if(!card)return;
    const note=document.createElement('div');
    note.id='fantasy-ovr-note';
    note.className='notice';
    note.style.marginTop='10px';
    note.textContent='Fantasy OVR is calculated from live ESPN fantasy statistics and updates as player performance changes.';
    card.insertBefore(note,card.firstChild);
  }

  const observer=new MutationObserver(()=>{paint();addLabel()});
  observer.observe(document.body,{subtree:true,childList:true});
  window.refreshFantasyOVR=load;
  setTimeout(load,800);
  setInterval(()=>{if(localStorage.getItem('gm_token')&&!window.FANTASY_OVR_READY)load()},3000);
  setInterval(load,120000);
  setInterval(()=>{if(ratings.size)paint()},1000);
})();
