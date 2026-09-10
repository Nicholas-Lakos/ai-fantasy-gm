(()=>{
const norm=v=>String(v||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/[^a-z0-9 ]/gi,'').replace(/\s+/g,' ').trim().toLowerCase();
const cls=o=>o>=90?'ovr-elite':o>=80?'ovr-great':o>=70?'ovr-good':o>=60?'ovr-average':o>=50?'ovr-below':'ovr-poor';
let ratings=new Map(),loading=false,scoringPeriod=0;
const gamesCache=new Map();
function token(){
  const keys=['gm_token','token','auth_token','access_token','jwt','authToken','fantasy_gm_token','fantasyGMToken'];
  for(const k of keys){try{const v=localStorage.getItem(k)||sessionStorage.getItem(k);if(v&&v.split('.').length===3)return v}catch{}}
  try{for(const store of [localStorage,sessionStorage])for(let i=0;i<store.length;i++){const v=store.getItem(store.key(i));if(v&&v.split('.').length===3)return v}}catch{}
  return '';
}
function rowName(row){const e=row.querySelector('.pn,.showdd-name');return e?String(e.textContent||'').trim():''}
function findGamesPlayed(value){
  if(!value||typeof value!=='object')return null;
  if(Array.isArray(value)){for(const x of value){const n=findGamesPlayed(x);if(Number.isFinite(n))return n}return null}
  for(const [k,v] of Object.entries(value)){
    const key=String(k).toLowerCase().replace(/[^a-z0-9]/g,'');
    if((key==='gamesplayed'||key==='gp')&&Number.isFinite(Number(v))){const n=Number(v);if(n>0&&n<300)return n}
  }
  for(const v of Object.values(value)){const n=findGamesPlayed(v);if(Number.isFinite(n))return n}
  return null;
}
async function loadGamesPlayed(players){
  const list=(players||[]).filter(p=>p&&p.id&&!gamesCache.has(String(p.id)));
  if(!list.length)return;
  await Promise.all(list.map(async p=>{
    const id=String(p.id);
    try{
      const r=await fetch(`https://site.web.api.espn.com/apis/common/v3/sports/baseball/mlb/athletes/${encodeURIComponent(id)}/stats?season=2026&seasontype=2`,{cache:'no-store'});
      if(!r.ok)throw new Error('stats '+r.status);
      const d=await r.json();
      const n=findGamesPlayed(d);
      gamesCache.set(id,Number.isFinite(n)?n:null);
    }catch{gamesCache.set(id,null)}
  }));
}
function paintSeasonAverage(row,data){
  const cells=row.querySelectorAll('td');if(!cells.length||!data)return;
  const cell=cells[cells.length-1];
  const total=Number(data.total_points),gp=Number(data.games_played??gamesCache.get(String(data.id)));
  if(!Number.isFinite(total)||!Number.isFinite(gp)||gp<=0)return;
  let avg=total/gp;
  let el=cell.querySelector('.season-avg');
  if(!el){el=document.createElement('div');el.className='sub season-avg';el.style.marginTop='3px';cell.appendChild(el)}
  el.textContent='Season Avg '+avg.toFixed(1);
  el.title='League fantasy points ÷ MLB games played';
}
function paint(){
  document.querySelectorAll('#roster tr.row,#opRoster tr.row,#waiverRows tr.row').forEach(row=>{
    const name=rowName(row),data=ratings.get(norm(name));if(!name||!data)return;
    const o=Number(data.fantasy_ovr);if(!Number.isFinite(o))return;
    const avatar=row.querySelector('.avatar');
    if(avatar){avatar.textContent=String(o);avatar.className='avatar '+cls(o);avatar.dataset.fantasyOvr=String(o);avatar.removeAttribute('data-show-ovr');avatar.title='Fantasy OVR calculated from ESPN stats'}
    const showOvr=row.querySelector('.showdd-ovr');
    if(showOvr){showOvr.textContent=String(o);showOvr.className='showdd-ovr '+(o>=90?'showdd-elite':o>=80?'showdd-diamond':o>=70?'showdd-gold':o>=60?'showdd-silver':'showdd-bronze');showOvr.title='Fantasy OVR calculated from ESPN season stats';showOvr.dataset.fantasyOvr=String(o)}
    const live=row.querySelector('.showdd-live');if(live)live.textContent='ESPN OVR';
    row.querySelectorAll('.live-ovr-badge,.live-label').forEach(e=>e.remove());
    const pn=row.querySelector('.pn,.showdd-name');const sub=pn?.parentElement?.querySelector('.sub,.showdd-sub');
    if(sub){sub.textContent='ESPN Fantasy OVR '+o+' · '+(data.total_points??'—')+' season pts';sub.title='Calculated from ESPN league-scored season points, current-period points, and start rate.'}
    paintSeasonAverage(row,data);
  });
}
async function load(){
  if(loading)return false;
  const t=token();
  if(!t){window.FANTASY_OVR_ERROR='No JWT found in browser storage';return false}
  loading=true;
  try{
    const r=await fetch('/api/fantasy-ovr?ts='+Date.now(),{cache:'no-store',credentials:'include',headers:{Authorization:'Bearer '+t}});
    if(!r.ok)throw new Error('Fantasy OVR API HTTP '+r.status);
    const d=await r.json();
    scoringPeriod=Number(d.scoring_period)||0;
    window.FANTASY_SCORING_PERIOD=scoringPeriod;
    const players=Array.isArray(d.players)?d.players:[];
    ratings=new Map(players.filter(p=>p&&p.name&&Number.isFinite(Number(p.fantasy_ovr))).map(p=>[norm(p.name),p]));
    window.FANTASY_OVR_READY=ratings.size>0;
    window.FANTASY_OVR_SOURCE=d.source||'ESPN Fantasy Baseball statistics';
    window.FANTASY_OVR_COUNT=ratings.size;
    window.FANTASY_OVR_ERROR='';
    await loadGamesPlayed(players);
    paint();
    return ratings.size>0;
  }catch(e){window.FANTASY_OVR_READY=false;window.FANTASY_OVR_ERROR=String(e.message||e);console.warn('Fantasy OVR unavailable:',e);return false}
  finally{loading=false}
}
function removeLegacy(){document.querySelectorAll('.live-ovr-badge,.live-label,.showdd-live').forEach(e=>e.remove());document.querySelectorAll('.showdd-sub').forEach(e=>{if(/live series/i.test(e.textContent||''))e.textContent='ESPN fantasy stats'})}
function start(){
  removeLegacy();
  const observer=new MutationObserver(()=>{removeLegacy();paint()});
  observer.observe(document.body,{subtree:true,childList:true});
  load();
  [500,1500,3000,6000,10000].forEach(ms=>setTimeout(load,ms));
  setInterval(()=>{removeLegacy();paint()},500);
  setInterval(load,120000);
}
window.refreshFantasyOVR=load;
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start,{once:true});else start();
})();