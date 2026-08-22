/* Clean production frontend fixes 20260822-clean1 */
(()=>{
const esc=v=>String(v??'').replace(/[&<>\"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}[c]));
const norm=v=>String(v||'').toUpperCase();
// ESPN Fantasy primary position only. The backend position field is derived from ESPN defaultPositionId.
window.pos=p=>{const x=norm(p?.position);if(x==='RELIEF PITCHER')return'RP';if(x==='STARTING PITCHER')return'SP';if(x==='PITCHER')return'P';return x||'—'};
window.primaryPosition=p=>window.pos(p);
window.statusClass=p=>{const i=norm(p?.injury_status);if(i&&i!=='ACTIVE')return[i==='INJURY_RESERVE'||i==='INJURED_RESERVE'?'IL':i,'il'];const s=norm(p?.lineup_slot);if(s==='BENCH')return['BENCH','bench'];if(p?.status==='WAIVERS'||p?.status==='FREEAGENT')return[p.status,'waiver'];return[s||'ACTIVE','active']};
const espnSlug=name=>String(name||'').trim().toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/[^a-z0-9]+/g,'-').replace(/^-+|-+$/g,'');
window.espnPlayerUrl=(id,name)=>{const pid=String(id||'').trim();if(!pid)return'https://www.espn.com/mlb/';const slug=espnSlug(name);return`https://www.espn.com/mlb/player/_/id/${encodeURIComponent(pid)}${slug?`/${encodeURIComponent(slug)}`:''}`};
window.openESPNPlayer=(id,name)=>{const url=window.espnPlayerUrl(id,name);if(url)window.open(url,'_blank','noopener');};
const fmtAvg=v=>v==null||Number.isNaN(Number(v))?'—':Number(v).toFixed(1);
function setPrimaryHeaders(){for(const id of ['roster','opRoster','waiverRows']){const tr=document.querySelector(`#${id}`)?.closest('table')?.querySelector('thead tr');if(!tr)continue;[...tr.children].forEach(th=>{if(th.textContent.trim()==='Eligibility')th.remove()});}}
function ensureHeaders(){setPrimaryHeaders();for(const id of ['roster','opRoster','waiverRows']){const tr=document.querySelector(`#${id}`)?.closest('table')?.querySelector('thead tr');if(!tr)continue;const h=[...tr.children];if(!h.some(x=>x.textContent.trim()==='Avg Pts')){const status=[...h].find(x=>x.textContent.trim()==='Status');if(status){const th=document.createElement('th');th.textContent='Avg Pts';status.insertAdjacentElement('afterend',th)}}}}
window.playerRow=(p,w=false)=>{ensureHeaders();const[st,cl]=statusClass(p),inj=norm(p?.injury_status),url=window.espnPlayerUrl(p?.id,p?.name),name=esc(p?.name||'Player');return`<tr class="row" title="Open player on ESPN"><td><a href="${esc(url)}" target="_blank" rel="noopener noreferrer" style="display:flex;gap:10px;align-items:center;color:inherit;text-decoration:none" aria-label="Open ${name} on ESPN"><div class="avatar">${esc(String(p.name||'?').split(' ').map(x=>x[0]).slice(0,2).join('').toUpperCase())}</div><div><div class="pn">${name}</div><div class="sub">${inj&&inj!=='ACTIVE'?esc(inj):'Open ESPN player ↗'}</div></div></a></td><td><span class="pos">${esc(window.primaryPosition(p))}</span></td>${w?`<td><span class="badge ${cl}">${esc(st)}</span></td><td>${p.percent_owned==null?'—':esc(Number(p.percent_owned).toFixed(1))+'%'}</td>`:`<td><span class="sub">${esc(p.lineup_slot||'—')}</span></td><td><span class="badge ${cl}">${esc(st)}</span></td>`}<td class="avgpts">${fmtAvg(p.average_points)}</td><td class="pts">${p.total_points==null?'—':esc(Number(p.total_points).toFixed(1))}</td></tr>`};
const ANALYTICS_CONTEXT=`

You are also a serious modern baseball analytics expert. When answering fantasy questions, reason from the league's actual scoring settings and live ESPN data first, then use baseball analytics appropriately. Know and explain: wOBA, wRC+, OPS+, ISO, BABIP, K%, BB%, K-BB%, contact rate, chase rate, swinging-strike rate, CSW%, hard-hit rate, barrel rate, exit velocity, launch angle, xBA, xSLG, xwOBA, expected ERA, FIP, xFIP, SIERA, HR/FB, ground-ball and fly-ball rates, platoon splits, park effects, Statcast quality of contact, workload, velocity, pitch mix, and pitcher role. Distinguish descriptive stats from predictive indicators. Do not blindly recommend the player with the best real-life metric: translate the analysis into fantasy value under THIS league's scoring system, roster requirements, playing time, and replacement level. Consider regression when supported by underlying metrics, but do not claim certainty. If a metric is unavailable in the supplied live data, say so rather than inventing a value. For hitters, weigh playing time, lineup spot, power, plate skills, contact quality and category/scoring impact. For pitchers, weigh role, innings, strikeout and walk skills, workload, run prevention, save/hold opportunities when relevant, and underlying skill indicators. Give the fantasy recommendation first and concise analytical evidence second.`;
const nativeFetch=window.fetch.bind(window);
window.fetch=async(input,init={})=>{
  let isAI=false,isDashboard=false;
  try{
    const url=typeof input==='string'?input:(input?.url||'');
    isAI=url.includes('/ai/gm');
    isDashboard=url.includes('/dashboard');
    if(isAI&&init?.body){const body=JSON.parse(init.body);if(body&&typeof body.question==='string'&&!body.question.includes('serious modern baseball analytics expert')){body.question=body.question+ANALYTICS_CONTEXT;init={...init,body:JSON.stringify(body)}}}
  }catch(e){}
  const response=await nativeFetch(input,init);
  if(!isDashboard)return response;
  try{
    if(!response.ok)return response;
    const data=await response.clone().json();
    // Keep the UI usable if a backend response contains the user's team but the
    // teams array is missing or empty. This does not invent league teams; it only
    // normalizes an otherwise valid dashboard payload for the existing renderer.
    if((!Array.isArray(data.teams)||!data.teams.length)&&data.team){data.teams=[data.team]}
    if(data.team && Array.isArray(data.teams)&&data.teams.length){
      const tid=Number(data.team.id);
      const match=data.teams.find(t=>Number(t?.id)===tid);
      if(match){data.team=match}
    }
    return new Response(JSON.stringify(data),{status:response.status,statusText:response.statusText,headers:new Headers(response.headers)});
  }catch(e){return response}
};
const observer=new MutationObserver(()=>{if(document.querySelector('#roster,#opRoster,#waiverRows'))ensureHeaders()});
if(document.body)observer.observe(document.body,{childList:true,subtree:true});
})();
