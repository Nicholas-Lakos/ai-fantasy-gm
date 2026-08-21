(()=>{
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const norm=v=>String(v||'').toUpperCase();
window.pos=p=>{const x=norm(p?.position);if(x==='RELIEF PITCHER')return'RP';if(x==='STARTING PITCHER')return'SP';return x||'—'};
window.elig=p=>[...new Set((p?.eligible_positions||[]).map(norm).map(x=>x==='RELIEF PITCHER'?'RP':x==='STARTING PITCHER'?'SP':x))].join(' · ')||'—';
window.statusClass=p=>{const i=norm(p?.injury_status);if(i&&i!=='ACTIVE')return[i==='INJURY_RESERVE'||i==='INJURED_RESERVE'?'IL':i,'il'];const s=norm(p?.lineup_slot);if(s==='BENCH')return['BENCH','bench'];if(p?.status==='WAIVERS'||p?.status==='FREEAGENT')return[p.status,'waiver'];return[s||'ACTIVE','active']};
// Open immediately on the user's click so browsers do not block the new tab.
window.openESPNPlayer=name=>{const q=encodeURIComponent(String(name||''));if(q)window.open(`https://www.espn.com/search/_/q/${q}`,'_blank','noopener');};
window.playerRow=(p,w=false)=>{const[st,cl]=statusClass(p),inj=norm(p?.injury_status);return`<tr class="row" onclick="openESPNPlayer(${JSON.stringify(p.name||'')})" title="Open player on ESPN"><td><div class="player"><div class="avatar">${esc(String(p.name||'?').split(' ').map(x=>x[0]).slice(0,2).join('').toUpperCase())}</div><div><div class="pn">${esc(p.name)}</div><div class="sub">${inj&&inj!=='ACTIVE'?esc(inj):'Open ESPN player ↗'}</div></div></div></td><td><span class="pos">${esc(pos(p))}</span></td><td><span class="sub">${esc(elig(p))}${p.lineup_slot?' · '+esc(p.lineup_slot):''}</span></td><td><span class="badge ${cl}">${esc(st)}</span></td>${w?`<td>${p.percent_owned==null?'—':esc(Number(p.percent_owned).toFixed(1))+'%'}</td>`:''}<td class="pts">${p.total_points==null?'—':esc(Number(p.total_points).toFixed(1))}</td></tr>`};
})();
