/* League renderer hardening: always use the normalized dashboard payload. */
(()=>{
  const esc=v=>String(v??'').replace(/[&<>\"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}[c]));
  const teamList=d=>Array.isArray(d?.teams)?d.teams:(d?.team?[d.team]:[]);
  const rec=t=>t?.record||{};
  const teamById=(d,id)=>teamList(d).find(t=>Number(t?.id)===Number(id));
  const render=(d)=>{
    const teams=teamList(d), myId=Number(d?.team?.id||d?.my_team_id);
    const standings=Array.isArray(d?.standings)&&d.standings.length?d.standings:teams.map(t=>{const r=rec(t);return{id:t.id,name:t.name,wins:r.wins||0,losses:r.losses||0,ties:r.ties||0,points:t.points??0}});
    standings.sort((a,b)=>(b.wins||0)-(a.wins||0)||(b.points||0)-(a.points||0));
    const s=document.getElementById('standings'), box=document.getElementById('teams');
    if(s)s.innerHTML=standings.map((t,i)=>`<tr class="row" onclick="openTeam(${Number(t.id)})"><td>${i+1}</td><td><b>${esc(t.name||`Team ${t.id}`)}</b>${Number(t.id)===myId?' <span class="badge active">YOU</span>':''}</td><td>${t.wins||0}</td><td>${t.losses||0}</td><td>${t.ties||0}</td><td class="pts">${t.points??'—'}</td></tr>`).join('')||'<tr><td colspan="6" class="loading">No league teams found.</td></tr>';
    if(box)box.innerHTML=teams.map(t=>{const r=rec(t), roster=Array.isArray(t.roster)?t.roster:[];const top=roster.slice().sort((a,b)=>(b.total_points||0)-(a.total_points||0)).slice(0,3).map(p=>esc(p.name)).join(', ');return `<div class="team ${Number(t.id)===myId?'me':''}" onclick="openTeam(${Number(t.id)})"><h3>${esc(t.name||`Team ${t.id}`)} ${Number(t.id)===myId?'· YOU':''}</h3><div class="muted">${r.wins||0}-${r.losses||0}-${r.ties||0} · ${roster.length} players</div><div class="sub" style="margin-top:8px">Top: ${top||'—'}</div></div>`}).join('')||'<div class="loading">No league teams found.</div>';
  };
  window.loadLeague=async()=>{
    const notice=document.getElementById('leagueNotice');
    try{
      if(notice)notice.innerHTML='<div class="notice">Loading all ESPN teams…</div>';
      const d=await api('/dashboard');
      if(!teamList(d).length)throw new Error('ESPN returned no league teams.');
      render(d);
      if(notice)notice.innerHTML='';
    }catch(e){if(notice)notice.innerHTML=`<div class="notice err">${esc(e.message||'Unable to load league teams.')}</div>`;}
  };
  window.openTeam=async(id)=>{
    try{
      const d=await api('/dashboard'), t=teamById(d,id);
      if(!t)throw new Error('That team was not found in the ESPN league data.');
      const name=document.getElementById('opponentName'),meta=document.getElementById('opponentMeta'),rows=document.getElementById('opRoster');
      if(name)name.textContent=t.name||`Team ${id}`;
      const r=rec(t), rank=(d.standings||[]).findIndex(x=>Number(x.id)===Number(id))+1;
      if(meta)meta.textContent=`Rank #${rank||'—'} · ${r.wins||0}-${r.losses||0}-${r.ties||0} · Scoring period ${d.scoring_period||'—'}`;
      const roster=Array.isArray(t.roster)?t.roster:[];
      if(rows)rows.innerHTML=roster.map(p=>window.playerRow?pRow(p):`<tr><td>${esc(p.name)}</td><td>${esc(p.position||'—')}</td><td>${esc(p.lineup_slot||'—')}</td><td>${esc(p.injury_status||'ACTIVE')}</td><td>${p.total_points??'—'}</td></tr>`).join('')||'<tr><td colspan="5" class="loading">No roster players returned.</td></tr>';
      if(typeof go==='function')go('opponent');
    }catch(e){alert(e.message||'Unable to open team.');}
    function pRow(p){return window.playerRow(p);}
  };
  if(typeof window.go==='function'){
    const originalGo=window.go;
    window.go=function(id,...rest){const out=originalGo.call(this,id,...rest);if(id==='league')setTimeout(()=>window.loadLeague(),0);return out;};
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>{if(location.hash==='#league')window.loadLeague()});
})();
