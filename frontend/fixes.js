(()=>{
const esc=v=>String(v??'').replace(/[&<>\"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}[c]));
const norm=v=>String(v||'').toUpperCase();
const hitters=['C','1B','2B','3B','SS','LF','CF','RF','OF','DH'];
const hitter=v=>hitters.includes(norm(v));
window.pos=p=>{const x=norm(p?.position);const elig=(p?.eligible_positions||[]).map(norm);if(x==='RP'&&elig.some(hitter))return elig.find(hitter)||'—';if(x==='RELIEF PITCHER'&&elig.some(hitter))return elig.find(hitter)||'—';if(x==='STARTING PITCHER'&&elig.some(hitter))return elig.find(hitter)||'—';return x||'—'};
window.elig=p=>{const actual=norm(p?.position);let a=(p?.eligible_positions||[]).map(norm);if(hitter(actual))a=a.filter(x=>x!=='RP'&&x!=='RELIEF PITCHER'&&x!=='SP'&&x!=='STARTING PITCHER');return[...new Set(a.map(x=>x==='RELIEF PITCHER'?'RP':x==='STARTING PITCHER'?'SP':x))].join(' · ')||'—'};
window.statusClass=p=>{const i=norm(p?.injury_status);if(i&&i!=='ACTIVE')return[i==='INJURY_RESERVE'||i==='INJURED_RESERVE'?'IL':i,'il'];const s=norm(p?.lineup_slot);if(s==='BENCH')return['BENCH','bench'];if(p?.status==='WAIVERS'||p?.status==='FREEAGENT')return[p.status,'waiver'];return[s||'ACTIVE','active']};
const espnSlug=name=>String(name||'').trim().toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/[^a-z0-9]+/g,'-').replace(/^-+|-+$/g,'');
window.espnPlayerUrl=(id,name)=>{const pid=String(id||'').trim();if(!pid)return'https://www.espn.com/mlb/';const slug=espnSlug(name);return`https://www.espn.com/mlb/player/_/id/${encodeURIComponent(pid)}${slug?`/${encodeURIComponent(slug)}`:''}`};
window.openESPNPlayer=(id,name)=>{const url=window.espnPlayerUrl(id,name);if(url)window.open(url,'_blank','noopener');};
window.playerRow=(p,w=false)=>{const[st,cl]=statusClass(p),inj=norm(p?.injury_status),url=window.espnPlayerUrl(p?.id,p?.name),name=esc(p?.name||'Player');const pts=p?.total_points??p?.applied_stat_total??p?.average_points;return`<tr class="row" title="Open player on ESPN"><td><a href="${esc(url)}" target="_blank" rel="noopener noreferrer" style="display:flex;gap:10px;align-items:center;color:inherit;text-decoration:none" aria-label="Open ${name} on ESPN"><div class="avatar">${esc(String(p.name||'?').split(' ').map(x=>x[0]).slice(0,2).join('').toUpperCase())}</div><div><div class="pn">${name}</div><div class="sub">${inj&&inj!=='ACTIVE'?esc(inj):'Open ESPN player ↗'}</div></div></a></td><td><span class="pos">${esc(pos(p))}</span></td><td><span class="sub">${esc(elig(p))}${p.lineup_slot?' · '+esc(p.lineup_slot):''}</span></td><td><span class="badge ${cl}">${esc(st)}</span></td>${w?`<td>${p.percent_owned==null?'—':esc(Number(p.percent_owned).toFixed(1))+'%'}</td>`:''}<td class="pts">${pts==null?'—':esc(Number(pts).toFixed(1))}</td></tr>`};

function tradeValue(p){const a=Number(p?.average_points);if(Number.isFinite(a)&&a>0)return a;const t=Number(p?.total_points);return Number.isFinite(t)?t/Math.max(1,Number(p?.games_played)||20):0}
function tradePlayerLabel(p){return `${p.name||'Player'} · ${pos(p)} · ${tradeValue(p).toFixed(1)} pts/wk`}
let tradePlayers=[];
async function loadTradePlayers(){
 const box=document.getElementById('tradeStatus');if(box)box.textContent='Loading your league players…';
 try{
  const [lg,wa]=await Promise.all([api('/league/teams'),api('/espn/waivers').catch(()=>({players:[]}))]);
  const map=new Map();
  (lg.teams||[]).forEach(t=>(t.roster||[]).forEach(p=>{if(p?.id)map.set(String(p.id),{...p,team_name:t.name})}));
  (wa.players||[]).forEach(p=>{if(p?.id&&!map.has(String(p.id)))map.set(String(p.id),{...p,team_name:'Free Agent'})});
  tradePlayers=[...map.values()].sort((a,b)=>String(a.name).localeCompare(String(b.name)));
  ['tradeGive1','tradeGive2','tradeGive3','tradeGet1','tradeGet2','tradeGet3'].forEach(id=>{
   const s=document.getElementById(id);if(!s)return;s.innerHTML='<option value="">Select a player…</option>'+tradePlayers.map(p=>`<option value="${esc(p.id)}">${esc(tradePlayerLabel(p))}</option>`).join('');
  });
  if(box)box.textContent=`${tradePlayers.length} players loaded from your league.`;
 }catch(e){if(box)box.textContent='Could not load league players: '+e.message}
}
function selectedTrade(ids){return ids.map(id=>{const v=document.getElementById(id)?.value;return tradePlayers.find(p=>String(p.id)===String(v))}).filter(Boolean)}
window.analyzeTrade=function(){
 const give=selectedTrade(['tradeGive1','tradeGive2','tradeGive3']),get=selectedTrade(['tradeGet1','tradeGet2','tradeGet3']);
 const out=document.getElementById('tradeResult');if(!out)return;
 if(!give.length||!get.length){out.innerHTML='<div class="notice err">Select at least one player on both sides of the trade.</div>';return}
 const gv=give.reduce((s,p)=>s+tradeValue(p),0),rv=get.reduce((s,p)=>s+tradeValue(p),0),diff=rv-gv;
 let verdict=Math.abs(diff)<2.5?'FAIR / CLOSE':diff>0?'FAVORS YOU':'FAVORS THE OTHER SIDE';
 let cls=Math.abs(diff)<2.5?'trade-even':diff>0?'trade-good':'trade-bad';
 const side=(a)=>a.map(p=>`<div class="trade-player"><b>${esc(p.name)}</b><span>${esc(pos(p))} · ${tradeValue(p).toFixed(1)} pts/wk${p.total_points!=null?' · '+Number(p.total_points).toFixed(1)+' season':''}</span></div>`).join('');
 out.innerHTML=`<div class="trade-verdict ${cls}"><div class="ey">TRADE VERDICT</div><div class="trade-title">${verdict}</div><div class="trade-diff">${diff>=0?'+':''}${diff.toFixed(1)} projected points/week</div></div><div class="trade-columns"><div><h3>You Give</h3>${side(give)}<div class="trade-total">Total: ${gv.toFixed(1)} pts/wk</div></div><div><h3>You Receive</h3>${side(get)}<div class="trade-total">Total: ${rv.toFixed(1)} pts/wk</div></div></div><button class="btn" onclick="askTradeAI()">Ask AI GM About This Trade ✦</button><div id="tradeAI" class="trade-ai"></div>`;
}
window.askTradeAI=async function(){const give=selectedTrade(['tradeGive1','tradeGive2','tradeGive3']),get=selectedTrade(['tradeGet1','tradeGet2','tradeGet3']);const el=document.getElementById('tradeAI');if(!el)return;el.textContent='AI is analyzing your roster and this trade…';const g=give.map(p=>p.name).join(', '),r=get.map(p=>p.name).join(', ');try{const j=await api('/ai/gm',{method:'POST',body:JSON.stringify({question:`Analyze this fantasy baseball trade for MY team. I give ${g}. I receive ${r}. Consider my roster, league context, player values, positions, injuries, and whether I should accept. Give a clear verdict and explain why.`})});el.textContent=j.answer||'No AI analysis returned.'}catch(e){el.textContent='AI error: '+e.message}}
function injectTradeTab(){
 if(document.getElementById('trade'))return;
 const nav=document.querySelector('.nav');if(nav){const b=document.createElement('button');b.innerHTML='↔ Trade Analyzer';b.onclick=function(){go('trade',b);loadTradePlayers()};nav.insertBefore(b,nav.querySelector('button[onclick*="go(\'ai\'"]')||null)}
 const mobile=document.querySelector('.mobile');if(mobile){const b=document.createElement('button');b.innerHTML='<span class="icon">↔</span>Trade';b.onclick=function(){go('trade',b);loadTradePlayers()};mobile.appendChild(b)}
 const main=document.querySelector('.main');if(!main)return;
 const s=document.createElement('section');s.id='trade';s.className='screen';s.innerHTML=`<div class="top"><div><div class="ey">Trade Machine</div><div class="title">Trade Analyzer</div><div class="muted">Compare players using your league's live ESPN data.</div></div><button class="btn" onclick="loadTradePlayers()">Refresh Players</button></div><div id="tradeStatus" class="notice">Loading league players…</div><div class="trade-grid"><div class="card"><div class="ey">YOU GIVE</div><h2>Players You Send</h2>${['tradeGive1','tradeGive2','tradeGive3'].map(id=>`<select id="${id}" class="input trade-select"><option value="">Select a player…</option></select>`).join('')}</div><div class="card"><div class="ey">YOU RECEIVE</div><h2>Players You Get</h2>${['tradeGet1','tradeGet2','tradeGet3'].map(id=>`<select id="${id}" class="input trade-select"><option value="">Select a player…</option></select>`).join('')}</div></div><button class="btn trade-analyze" onclick="analyzeTrade()">Analyze Trade</button><div id="tradeResult" class="card full" style="margin-top:14px"><div class="muted">Select players on both sides, then analyze the trade.</div></div>`;
 main.appendChild(s);
 const st=document.createElement('style');st.textContent='.trade-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}.trade-select{margin-top:9px}.trade-analyze{margin-top:14px}.trade-verdict{padding:18px;border-radius:12px;margin-bottom:18px;border:1px solid var(--line)}.trade-good{background:#0b3325}.trade-bad{background:#3a1820}.trade-even{background:#18283a}.trade-title{font-size:27px;font-weight:950;margin:5px 0}.trade-diff{font-size:16px;font-weight:850}.trade-columns{display:grid;grid-template-columns:1fr 1fr;gap:24px;margin-bottom:18px}.trade-player{display:flex;justify-content:space-between;gap:12px;padding:10px 0;border-bottom:1px solid #172a3e}.trade-player span{color:var(--muted);font-size:12px}.trade-total{font-weight:900;padding-top:10px}.trade-ai{margin-top:14px;padding:14px;background:#091625;border-radius:10px;white-space:pre-wrap;line-height:1.55}.trade-grid .card{grid-column:auto}@media(max-width:700px){.trade-grid,.trade-columns{grid-template-columns:1fr}}';document.head.appendChild(st);
 loadTradePlayers();
}

async function requestNextWeekProjection(){
 const el=document.getElementById('projectionResult');if(!el)return;
 el.innerHTML='<div class="projection-loading">🔮 AI is analyzing your roster, league scoring, recent production, and the upcoming scoring period…</div>';
 try{
  const j=await api('/ai/gm',{method:'POST',body:JSON.stringify({question:`Predict MY team's total fantasy points for the UPCOMING ESPN scoring week. Use the live roster and league scoring settings you have. Give a realistic numeric projected team total, a reasonable low-to-high range, and confidence (High/Medium/Low). Then list each of my active players with an estimated contribution to the weekly total, account for likely playing time, pitcher starts, injuries, and the number of games where possible. Do not use the current week's points as the forecast. Clearly label this as a projection, not a guarantee.`})});
  const answer=j.answer||'No projection returned.';
  el.innerHTML=`<div class="projection-answer">${esc(answer).replace(/\n/g,'<br>')}</div>`;
 }catch(e){el.innerHTML=`<div class="notice err">Projection error: ${esc(e.message)}</div>`}
}
window.requestNextWeekProjection=requestNextWeekProjection;
function injectProjectionTab(){
 if(document.getElementById('projection'))return;
 const nav=document.querySelector('.nav');if(nav){const b=document.createElement('button');b.innerHTML='🔮 Next Week';b.onclick=function(){go('projection',b);requestNextWeekProjection()};nav.insertBefore(b,nav.querySelector('button[onclick*="go(\'ai\'"]')||null)}
 const mobile=document.querySelector('.mobile');if(mobile){const b=document.createElement('button');b.innerHTML='<span class="icon">🔮</span>Next Week';b.onclick=function(){go('projection',b);requestNextWeekProjection()};mobile.appendChild(b)}
 const main=document.querySelector('.main');if(!main)return;
 const s=document.createElement('section');s.id='projection';s.className='screen';s.innerHTML=`<div class="top"><div><div class="ey">AI FORECAST</div><div class="title">Next Week Projection</div><div class="muted">AI predicts your team's upcoming ESPN scoring-week points using your live roster and league settings.</div></div><button class="btn" onclick="requestNextWeekProjection()">Refresh Projection</button></div><div class="card projection-card"><div class="projection-head"><div><div class="ey">UPCOMING WEEK</div><h2>🔮 Projected Team Points</h2></div><div class="projection-badge">AI GM</div></div><div id="projectionResult" class="projection-result"><div class="muted">Click Refresh Projection to get your forecast.</div></div></div><div class="notice">Projection uses the live ESPN roster and scoring settings available to the AI. It is an estimate, not a guarantee.</div>`;
 main.appendChild(s);
 const st=document.createElement('style');st.textContent='.projection-card{margin-top:16px}.projection-head{display:flex;justify-content:space-between;align-items:center;gap:15px}.projection-badge{padding:7px 11px;border-radius:999px;background:#152f4a;font-weight:900;font-size:12px}.projection-result{margin-top:18px}.projection-loading{padding:22px;border-radius:12px;background:#091625;font-weight:800}.projection-answer{padding:22px;border-radius:12px;background:#091625;line-height:1.65;font-size:15px;white-space:normal}.projection-answer br{content:"";display:block;margin:6px 0}@media(max-width:700px){.projection-head{align-items:flex-start;flex-direction:column}}';document.head.appendChild(st);
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>{injectTradeTab();injectProjectionTab()});else{injectTradeTab();injectProjectionTab()}
})();