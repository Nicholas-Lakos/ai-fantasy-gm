(()=>{
  const norm=v=>String(v||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/[^a-z0-9 ]/gi,'').replace(/\s+/g,' ').trim().toLowerCase();
  const cls=o=>o>=90?'ovr-elite':o>=80?'ovr-great':o>=70?'ovr-good':o>=60?'ovr-average':o>=50?'ovr-below':'ovr-poor';
  let ratings=new Map(),loading=false;
  function token(){return localStorage.getItem('gm_token')||localStorage.getItem('token')||localStorage.getItem('auth_token')||''}
  function rowName(row){const e=row.querySelector('.pn,.showdd-name');return e?String(e.textContent||'').trim():''}
  function num(v){const n=Number(v);return Number.isFinite(n)?n:0}
  function calculate(players){
    const clean=players.filter(p=>p&&p.name).map(p=>({...p,total:num(p.total_points),current:num(p.applied_stat_total),start:num(p.percent_started)}));
    const groups=new Map();
    clean.forEach(p=>{const g=String(p.position||'').toUpperCase();if(!groups.has(g))groups.set(g,[]);groups.get(g).push(p.total)});
    const percentile=(v,a)=>{if(a.length<2)return .5;let n=0;for(const x of a)if(x<=v)n++;return (n-1)/(a.length-1)};
    const out=new Map();
    clean.forEach(p=>{
      const arr=groups.get(String(p.position||'').toUpperCase())||[p.total];
      const seasonPct=percentile(p.total,arr);
      const currentPct=percentile(p.current,clean.map(x=>x.current));
      const startPct=Math.max(0,Math.min(1,p.start/100));
      // ESPN season production is the primary signal; current scoring-period production
      // and usage are secondary signals. Keep the result on a familiar 40-99 scale.
      let o=40+59*(seasonPct*.72+currentPct*.18+startPct*.10);
      if(p.total===0&&p.current===0)o=55+12*startPct;
      o=Math.max(40,Math.min(99,Math.round(o)));
      out.set(norm(p.name),{...p,fantasy_ovr:o});
    });
    return out;
  }
  function paint(){
    document.querySelectorAll('#roster tr.row,#opRoster tr.row,#waiverRows tr.row').forEach(row=>{
      const name=rowName(row),data=ratings.get(norm(name));if(!name||!data)return;
      const o=Math.round(data.fantasy_ovr);if(!Number.isFinite(o))return;
      const avatar=row.querySelector('.avatar');
      if(avatar){avatar.textContent=String(o);avatar.className='avatar '+cls(o);avatar.dataset.fantasyOvr=String(o);avatar.removeAttribute('data-show-ovr');avatar.title='AI Fantasy GM OVR · calculated from ESPN fantasy stats'}
      row.querySelectorAll('.live-ovr-badge,.live-label,.showdd-live').forEach(e=>e.remove());
      const pn=row.querySelector('.pn');const sub=pn?.parentElement?.querySelector('.sub,.showdd-sub');
      if(sub){sub.textContent='Fantasy OVR '+o+' · ESPN stats';sub.title='Season '+(data.total??'—')+' fantasy pts · Current period '+(data.current??'—')+' pts · Started '+(data.start??'—')+'%'}
    });
  }
  async function load(){
    const t=token();if(!t||loading)return false;loading=true;
    try{
      const h={Authorization:'Bearer '+t};
      const [dr,wr]=await Promise.all([fetch('/dashboard?ovr='+Date.now(),{cache:'no-store',credentials:'include',headers:h}),fetch('/espn/waivers?ovr='+Date.now(),{cache:'no-store',credentials:'include',headers:h}).catch(()=>null)]);
      if(!dr.ok)throw new Error('Dashboard HTTP '+dr.status);
      const d=await dr.json();
      const all=[];(d.teams||[]).forEach(t=>all.push(...(t.roster||[])));
      if(wr&&wr.ok){const w=await wr.json();all.push(...(w.players||[]))}
      ratings=calculate(all);window.FANTASY_OVR_READY=ratings.size>0;window.FANTASY_OVR_SOURCE='ESPN Fantasy Baseball stats';window.FANTASY_OVR_COUNT=ratings.size;window.FANTASY_OVR_ERROR='';paint();return ratings.size>0;
    }catch(e){window.FANTASY_OVR_READY=false;window.FANTASY_OVR_ERROR=String(e.message||e);console.warn('Fantasy OVR unavailable:',e);return false}
    finally{loading=false}
  }
  function removeLegacy(){document.querySelectorAll('.live-ovr-badge,.live-label,.showdd-live').forEach(e=>e.remove());document.querySelectorAll('.showdd-sub').forEach(e=>{if(/live series/i.test(e.textContent||''))e.textContent='ESPN fantasy stats'})}
  function start(){removeLegacy();const observer=new MutationObserver(()=>{removeLegacy();paint()});observer.observe(document.body,{subtree:true,childList:true});load();[1000,2500,5000,10000].forEach(ms=>setTimeout(load,ms));setInterval(()=>{if(token())load()},120000);setInterval(()=>{removeLegacy();paint()},500)}
  window.refreshFantasyOVR=load;
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start,{once:true});else start();
})();
