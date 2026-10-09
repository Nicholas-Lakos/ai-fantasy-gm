(()=>{
const norm=v=>String(v||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/[^a-z0-9 ]/gi,'').replace(/\s+/g,' ').trim().toLowerCase();
const slug=n=>String(n||'').trim().toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/[^a-z0-9]+/g,'-').replace(/^-+|-+$/g,'');
const token=()=>localStorage.getItem('gm_token')||sessionStorage.getItem('gm_token')||'';
const ratings=new Map();
const ids=new Map();
const espn=(id,name)=>id?`https://www.espn.com/mlb/player/_/id/${encodeURIComponent(id)}/${encodeURIComponent(slug(name))}`:'https://www.espn.com/mlb/';
window.espnPlayerUrl=espn;
function nameOf(row){return String(row.querySelector('.pn,.showdd-name')?.textContent||'').trim()}
function apply(){
 document.querySelectorAll('#roster tr.row,#opRoster tr.row,#waiverRows tr.row').forEach(row=>{
  const name=nameOf(row);if(!name)return;const key=norm(name),rating=ratings.get(key),id=ids.get(key)||row.dataset.espnId;
  if(Number.isFinite(rating)){
   const avatar=row.querySelector('.avatar,.showdd-avatar');if(avatar){avatar.textContent=String(Math.round(rating));avatar.title='MLB The Show Live Series Overall';}
   let badge=row.querySelector('.showdd-ovr');if(badge){badge.textContent=String(Math.round(rating));badge.title='MLB The Show Live Series Overall';}
   const sub=row.querySelector('.sub,.showdd-sub');if(sub)sub.textContent='Live Series';
  }
  if(id){row.dataset.espnId=String(id);row.dataset.espnName=name;row.title='Open player on ESPN';}
 });
}
async function loadIds(){
 const t=token();if(!t)return;
 try{const r=await fetch('/dashboard?ts='+Date.now(),{cache:'no-store',headers:{Authorization:'Bearer '+t}});if(!r.ok)return;const d=await r.json();for(const team of d.teams||[])for(const p of team.roster||[])if(p?.name&&p?.id)ids.set(norm(p.name),p.id);apply()}catch{}
}
async function loadRatings(){
 const t=token();if(!t)return;
 try{const r=await fetch('/api/show/live-ratings?force=false&ts='+Date.now(),{cache:'no-store',headers:{Authorization:'Bearer '+t}});if(!r.ok)return;const d=await r.json();const list=Array.isArray(d)?d:(d.players||d.ratings||d.results||[]);for(const p of list){const name=p?.name||p?.player_name||p?.fullName;const o=Number(p?.overall??p?.ovr??p?.rating);if(name&&Number.isFinite(o))ratings.set(norm(name),Math.round(o));}window.SHOW_LIVE_RATINGS_READY=ratings.size>0;apply()}catch(e){console.warn('Live Series OVR unavailable',e)}
}
document.addEventListener('click',e=>{const row=e.target.closest('#roster tr.row,#opRoster tr.row,#waiverRows tr.row');if(!row)return;const name=nameOf(row),id=row.dataset.espnId||ids.get(norm(name));if(!id)return;e.preventDefault();e.stopImmediatePropagation();window.open(espn(id,name),'_blank','noopener,noreferrer')},true);
const obs=new MutationObserver(apply);
function start(){obs.observe(document.body,{subtree:true,childList:true});loadIds();loadRatings();setTimeout(loadIds,1000);setTimeout(loadRatings,1500);setInterval(apply,750);setInterval(loadRatings,120000)}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start,{once:true});else start();
})();
