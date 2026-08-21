(()=>{
const esc=v=>String(v??'').replace(/[&<>\"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}[c]));
const norm=v=>String(v||'').toUpperCase();
// ESPN's defaultPositionId is the player's primary fantasy position. Do not replace it with eligible slots.
window.pos=p=>{const x=norm(p?.position);if(x==='RELIEF PITCHER')return'RP';if(x==='STARTING PITCHER')return'SP';if(x==='PITCHER')return'P';return x||'—'};
window.statusClass=p=>{const i=norm(p?.injury_status);if(i&&i!=='ACTIVE')return[i==='INJURY_RESERVE'||i==='INJURED_RESERVE'?'IL':i,'il'];const s=norm(p?.lineup_slot);if(s==='BENCH')return['BENCH','bench'];if(p?.status==='WAIVERS'||p?.status==='FREEAGENT')return[p.status,'waiver'];return[s||'ACTIVE','active']};
const espnSlug=name=>String(name||'').trim().toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/[^a-z0-9]+/g,'-').replace(/^-+|-+$/g,'');
window.espnPlayerUrl=(id,name)=>{const pid=String(id||'').trim();if(!pid)return'https://www.espn.com/mlb/';const slug=espnSlug(name);return`https://www.espn.com/mlb/player/_/id/${encodeURIComponent(pid)}${slug?`/${encodeURIComponent(slug)}`:''}`};
window.openESPNPlayer=(id,name)=>{const url=window.espnPlayerUrl(id,name);if(url)window.open(url,'_blank','noopener');};
const fmtAvg=v=>v==null||Number.isNaN(Number(v))?'—':Number(v).toFixed(1);
function setPrimaryHeaders(){
 const team=document.querySelector('#roster')?.closest('table')?.querySelector('thead tr');if(team){const labels=[...team.children].map(x=>x.textContent.trim());if(labels.includes('Eligibility'))team.children[[...team.children].findIndex(x=>x.textContent.trim()==='Eligibility')].remove();}
 const opp=document.querySelector('#opRoster')?.closest('table')?.querySelector('thead tr');if(opp){const labels=[...opp.children].map(x=>x.textContent.trim());if(labels.includes('Eligibility'))opp.children[[...opp.children].findIndex(x=>x.textContent.trim()==='Eligibility')].remove();}
 const wa=document.querySelector('#waiverRows')?.closest('table')?.querySelector('thead tr');if(wa){const labels=[...wa.children].map(x=>x.textContent.trim());if(labels.includes('Eligibility'))wa.children[[...wa.children].findIndex(x=>x.textContent.trim()==='Eligibility')].remove();}
}
function ensureHeaders(){setPrimaryHeaders();
 const team=document.querySelector('#roster')?.closest('table')?.querySelector('thead tr');if(team){const h=[...team.children];if(h.length===5&&h[3]?.textContent==='Status'){const th=document.createElement('th');th.textContent='Avg Pts';team.insertBefore(th,h[4]);}}
 const opp=document.querySelector('#opRoster')?.closest('table')?.querySelector('thead tr');if(opp){const h=[...opp.children];if(h.length===5&&h[3]?.textContent==='Status'){const th=document.createElement('th');th.textContent='Avg Pts';opp.insertBefore(th,h[4]);}}
 const wa=document.querySelector('#waiverRows')?.closest('table')?.querySelector('thead tr');if(wa){const h=[...wa.children];if(h.length===5&&h[3]?.textContent==='Status'){const th=document.createElement('th');th.textContent='Avg Pts';wa.insertBefore(th,h[4]);}}
}
window.playerRow=(p,w=false)=>{ensureHeaders();const[st,cl]=statusClass(p),inj=norm(p?.injury_status),url=window.espnPlayerUrl(p?.id,p?.name),name=esc(p?.name||'Player');return`<tr class="row" title="Open player on ESPN"><td><a href="${esc(url)}" target="_blank" rel="noopener noreferrer" style="display:flex;gap:10px;align-items:center;color:inherit;text-decoration:none" aria-label="Open ${name} on ESPN"><div class="avatar">${esc(String(p.name||'?').split(' ').map(x=>x[0]).slice(0,2).join('').toUpperCase())}</div><div><div class="pn">${name}</div><div class="sub">${inj&&inj!=='ACTIVE'?esc(inj):'Open ESPN player ↗'}</div></div></a></td><td><span class="pos">${esc(pos(p))}</span></td>${w?`<td><span class="badge ${cl}">${esc(st)}</span></td><td>${p.percent_owned==null?'—':esc(Number(p.percent_owned).toFixed(1))+'%'}</td>`:`<td><span class="sub">${p.lineup_slot?'': ''}${esc(p.lineup_slot||'—')}</span></td><td><span class="badge ${cl}">${esc(st)}</span></td>`}<td class="avgpts">${fmtAvg(p.average_points)}</td><td class="pts">${p.total_points==null?'—':esc(Number(p.total_points).toFixed(1))}</td></tr>`};
})();
