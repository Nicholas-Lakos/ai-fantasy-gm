(()=>{
const norm=v=>String(v||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/[^a-z0-9 ]/gi,'').replace(/\s+/g,' ').trim().toLowerCase();
const cls=o=>o>=90?'ovr-elite':o>=80?'ovr-great':o>=70?'ovr-good':o>=60?'ovr-average':o>=50?'ovr-below':'ovr-poor';
let ratings=new Map(),loading=false,currentSeason=2026;
const gamesCache=new Map();
function token(){
  const keys=['gm_token','token','auth_token','access_token','jwt','authToken','fantasy_gm_token','fantasyGMToken'];
  for(const k of keys){try{const v=localStorage.getItem(k)||sessionStorage.getItem(k);if(v&&v.split('.').length===3)return v}catch{}}
  try{for(const store of [localStorage,sessionStorage])for(let i=0;i<store.length;i++){const v=store.getItem(store.key(i));if(v&&v.split('.').length===3)return v}}catch{}
  return '';
}
function rowName(row){const e=row.querySelector('.pn,.showdd-name');return e?String(e.textContent||'').trim():''}
function explicitGamesPlayed(value){
  if(!value||typeof value!=='object')return null;
  if(Array.isArray(value)){for(const x of value){const n=explicitGamesPlayed(x);if(Number.isFinite(n))return n}return null}
  for(const [k,v] of Object.entries(value)){
    const key=String(k).toLowerCase().replace(/[^a-z0-9]/g,'');
    if((key==='gamesplayed'||key==='gamesplayedtotal')&&Number.isFinite(Number(v))){const n=Number(v);if(n>0&&n<300)return n}
  }
  for(const v of Object.values(value)){const n=explicitGamesPlayed(v);if(Number.isFinite(n))return n}
  return null;
}
function playedFromGamelog(value){
  const items=value?.events?.items;
  if(Array.isArray(items)){
    const played=items.filter(x=>x&&x.played===true);
    if(played.length)return played.length;
    const unique=new Set(items.map(x=>x?.event?.id||x?.eventId||x?.id).filter(Boolean));
    if(unique.size)return unique.size;
  }
  if(Array.isArray(value?.events)){
    const played=value.events.filter(x=>x&&x.played!==false);
    if(played.length)return played.length;
  }
  return null;
}
async function espnGamesPlayed(p){
  const id=String(p.id);
  const base=`https://site.web.api.espn.com/apis/common/v3/sports/baseball/mlb/athletes/${encodeURIComponent(id)}`;
  const statsUrl=`${base}/stats?season=${currentSeason}&seasontype=2`;
  const logUrl=`${base}/gamelog?season=${currentSeason}&seasontype=2`;
  try{
    const r=await fetch(statsUrl,{cache:'no-store',credentials:'omit'});
    if(r.ok){const d=await r.json();const n=explicitGamesPlayed(d);if(Number.isFinite(n))return n}
  }catch(e){}
  try{
    const r=await fetch(logUrl,{cache:'no-store',credentials:'omit'});
    if(r.ok){const d=await r.json();const n=playedFromGamelog(d);if(Number.isFinite(n)&&n>0&&n<200)return n;const fallback=explicitGamesPlayed(d);if(Number.isFinite(fallback))return fallback}
  }catch(e){}
  throw new Error('ESPN games played unavailable');
}
async function loadGamesPlayed(players){
  const list=(players||[]).filter(p=>p&&p.id&&!gamesCache.has(String(p.id)));
  if(!list.length)return;
  const queue=[...list];
  const worker=async()=>{while(queue.length){const p=queue.shift();if(!p)break;const id=String(p.id);try{const n=await espnGamesPlayed(p);gamesCache.set(id,n)}catch(e){gamesCache.delete(id);console.warn('ESPN games played unavailable for',p.name,e)}}};
  await Promise.all([worker(),worker(),worker(),worker()]);
}
function paintSeasonAverage(row,data){
  const cells=row.querySelectorAll('td');if(!cells.length||!data)return;
  const cell=cells[cells.length-1];
  const total=Number(data.total_points),gp=Number(data.games_played??gamesCache.get(String(data.id)));
  if(!Number.isFinite(total)||!Number.isFinite(gp)||gp<=0)return;
  const avg=total/gp;
  let main=cell.querySelector('.fpts-per-game');
  let detail=cell.querySelector('.fpts-season-detail');
  if(!main){cell.querySelectorAll(':scope > *').forEach(e=>e.remove());main=document.createElement('div');main.className='pts fpts-per-game';cell.appendChild(main)}
  if(!detail){detail=document.createElement('div');detail.className='sub fpts-season-detail';cell.appendChild(detail)}
  main.textContent=avg.toFixed(1)+' FPTS/G';
  detail.textContent=total.toFixed(1)+' season pts · '+gp+' G';
  detail.title='ESPN season fantasy points ÷ ESPN games played';
}
function paint(){
  document.querySelectorAll('#roster tr.row,#opRoster tr.row,#waiverRows tr.row').forEach(row=>{
    const name=rowName(row),data=ratings.get(norm(name));if(!name||!data)return;
    const o=Number(data.fantasy_ovr);if(!Number.isFinite(o))return;
    const avatar=row.querySelector('.avatar');
    if(avatar){avatar.textContent=String(o);avatar.className='avatar '+cls(o);avatar.dataset.fantasyOvr=String(o);avatar.removeAttribute('data-show-ovr');avatar.title='Fantasy OVR calculated from ESPN stats'}
    const showOvr=row.querySelector('.showdd-ovr');
    if(showOvr){showOvr.textContent=String(o);showOvr.className='showdd-ovr '+(o>=90?'showdd-elite':o>=80?'showdd-diamond':o>=70?'showdd-gold':o>=60?'showdd-silver':'showdd-bronze');showOvr.title='Fantasy OVR calculated from ESPN season stats';showOvr.dataset.fantasyOvr=String(o)}
    const pn=row.querySelector('.pn,.showdd-name');const sub=pn?.parentElement?.querySelector('.sub,.showdd-sub');
    if(sub){sub.textContent='ESPN Fantasy OVR '+o+' · '+(data.total_points??'—')+' season pts';sub.title='Calculated from ESPN fantasy stats.'}
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
    currentSeason=Number(d.season)||currentSeason;
    window.FANTASY_OVR_SOURCE=d.source||'ESPN Fantasy Baseball statistics';
    const players=Array.isArray(d.players)?d.players:[];
    ratings=new Map(players.filter(p=>p&&p.name&&Number.isFinite(Number(p.fantasy_ovr))).map(p=>[norm(p.name),p]));
    window.FANTASY_OVR_READY=ratings.size>0;
    window.FANTASY_OVR_COUNT=ratings.size;
    window.FANTASY_OVR_ERROR='';
    await loadGamesPlayed(players);
    paint();
    return ratings.size>0;
  }catch(e){window.FANTASY_OVR_READY=false;window.FANTASY_OVR_ERROR=String(e.message||e);console.warn('Fantasy OVR unavailable:',e);return false}
  finally{loading=false}
}
function removeLegacy(){document.querySelectorAll('.live-ovr-badge,.live-label,.showdd-live').forEach(e=>e.remove())}
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