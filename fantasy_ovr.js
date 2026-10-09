(()=>{
const norm=v=>String(v||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/[^a-z0-9 ]/gi,'').replace(/\s+/g,' ').trim().toLowerCase();
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const apiBase=()=>String(window.AI_FANTASY_GM_API||'').replace(/\/$/,'');
const token=()=>localStorage.getItem('gm_token')||sessionStorage.getItem('gm_token')||'';
const ratings=new Map();
const byName=new Map();
const cls=o=>o>=90?'ovr-elite':o>=80?'ovr-great':o>=70?'ovr-good':o>=60?'ovr-average':o>=50?'ovr-below':'ovr-poor';
const slug=n=>String(n||'').trim().toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/[^a-z0-9]+/g,'-').replace(/^-+|-+$/g,'');
const espnUrl=(id,name)=>id?`https://www.espn.com/mlb/player/_/id/${encodeURIComponent(id)}/${encodeURIComponent(slug(name))}`:'https://www.espn.com/mlb/';
window.espnPlayerUrl=espnUrl;
function remember(p){if(!p||!p.name)return;const k=norm(p.name);const o=Number(p.fantasy_ovr);byName.set(k,p);if(Number.isFinite(o))ratings.set(k,Math.round(o));}
function rowName(row){return String(row.querySelector('.pn,.showdd-name')?.textContent||'').trim();}
function patch(){
 document.querySelectorAll('#roster tr.row,#opRoster tr.row,#waiverRows tr.row').forEach(row=>{
  const name=rowName(row);if(!name)return;const k=norm(name),p=byName.get(k),o=ratings.get(k);
  const avatar=row.querySelector('.avatar,.showdd-avatar');
  if(avatar&&Number.isFinite(o)){avatar.textContent=String(o);avatar.classList.remove('showdd-elite','showdd-diamond','showdd-gold','showdd-silver','showdd-bronze','showdd-common','show-elite','show-great','show-good','show-average','show-below','show-poor');avatar.classList.add(cls(o));avatar.title='Fantasy OVR calculated from ESPN fantasy stats';}
  row.querySelectorAll('.showdd-live,.live-label,.live-ovr-badge').forEach(x=>x.remove());
  const oldOvr=row.querySelector('.showdd-ovr');if(oldOvr)oldOvr.remove();
  const sub=row.querySelector('.sub,.showdd-sub');if(sub&&Number.isFinite(o))sub.textContent=`Fantasy OVR ${o} · ESPN stats`;
  if(p?.id){row.dataset.espnId=String(p.id);row.dataset.espnName=name;row.title='Open player on ESPN';}
 });
}
async function load(){
 const t=token();if(!t)return;
 try{
  const r=await fetch(apiBase()+'/api/fantasy-ovr?ts='+Date.now(),{cache:'no-store',headers:{Authorization:'Bearer '+t}});
  if(!r.ok)throw new Error('OVR '+r.status);
  const d=await r.json();(d.players||[]).forEach(remember);window.FANTASY_OVR_COUNT=ratings.size;window.FANTASY_OVR_READY=ratings.size>0;patch();
 }catch(e){window.FANTASY_OVR_ERROR=String(e.message||e);console.warn('Fantasy OVR unavailable',e);}
}
const originalPlayerRow=window.playerRow;
if(typeof originalPlayerRow==='function')window.playerRow=function(p,w=false){
 const html=originalPlayerRow(p,w);setTimeout(patch,0);return html;
};
document.addEventListener('click',e=>{
 const row=e.target.closest('#roster tr.row,#opRoster tr.row,#waiverRows tr.row');if(!row)return;
 const name=rowName(row),p=byName.get(norm(name));const id=row.dataset.espnId||p?.id;if(!id)return;
 e.preventDefault();e.stopImmediatePropagation();window.open(espnUrl(id,name),'_blank','noopener,noreferrer');
},true);
const observer=new MutationObserver(patch);
function start(){observer.observe(document.body,{childList:true,subtree:true});patch();load();setTimeout(load,1000);setTimeout(load,3000);setInterval(load,120000);}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start,{once:true});else start();
})();
