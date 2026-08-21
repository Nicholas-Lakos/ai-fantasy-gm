(() => {
  const injuryLabel = s => ({
    ACTIVE:'ACTIVE', QUESTIONABLE:'QUESTIONABLE', DOUBTFUL:'DOUBTFUL', OUT:'OUT',
    INJURY_RESERVE:'IL', INJURED_RESERVE:'IL', SUSPENDED:'SUSPENDED', DAY_TO_DAY:'DAY-TO-DAY'
  }[(s || '').toUpperCase()] || (s || '').toUpperCase());

  // Always use the player's primary ESPN position. Never infer a position from
  // eligibleSlots or lineupSlotId; those are fantasy eligibility/roster slots.
  window.pos = function(p) {
    const primary = String(p?.position || '').toUpperCase();
    if (primary === 'RELIEF PITCHER' || primary === 'RP') return 'RP';
    if (primary === 'PITCHER' || primary === 'P') return 'P';
    if (primary === 'STARTING PITCHER' || primary === 'SP') return 'SP';
    return primary || '—';
  };
  window.elig = function(p) {
    const a = Array.isArray(p?.eligible_positions) ? p.eligible_positions.filter(Boolean) : [];
    const primary = pos(p);
    const filtered = [...new Set(a.map(x => String(x).toUpperCase()).filter(x => x !== 'RELIEF PITCHER' || primary === 'RP'))];
    return filtered.length ? filtered.join(' · ') : '—';
  };
  window.statusClass = function(p) {
    const injury = (p?.injury_status || '').toUpperCase();
    if (injury && injury !== 'ACTIVE') return [injuryLabel(injury), 'il'];
    const s = (p?.lineup_slot || '').toUpperCase();
    if (s === 'BENCH') return ['BENCH', 'bench'];
    if (p?.status === 'WAIVERS' || p?.status === 'FREEAGENT') return [p.status, 'waiver'];
    return [s || 'ACTIVE', 'active'];
  };
  window.playerRow = function(p, waiver=false) {
    const [st,cl] = statusClass(p);
    const injury = (p?.injury_status || '').toUpperCase();
    const injuryText = injury && injury !== 'ACTIVE' ? ` · ${esc(injuryLabel(injury))}` : '';
    return `<tr class="row" onclick="openPlayer(${Number(p.id)})"><td><div class="player"><div class="avatar">${esc(initials(p.name))}</div><div><div class="pn">${esc(p.name)}</div><div class="sub">${p.pro_team_id ? 'MLB team ID '+esc(p.pro_team_id) : 'Player profile'}${injuryText}</div></div></div></td><td><span class="pos">${esc(pos(p))}</span></td><td><span class="sub">${esc(elig(p))}${p.lineup_slot ? ' · '+esc(p.lineup_slot) : ''}</span></td><td><span class="badge ${cl}">${esc(st)}</span></td>${waiver ? `<td>${p.percent_owned==null?'—':esc(Number(p.percent_owned).toFixed(1))+'%'}</td>` : ''}<td class="pts">${p.total_points==null?'—':esc(Number(p.total_points).toFixed(1))}</td></tr>`;
  };

  const fmt = (v,digits=2) => v == null || v === '' ? '—' : (typeof v === 'number' ? Number(v).toFixed(digits) : String(v));
  const statCards = (obj, keys) => keys.filter(k => obj && obj[k.key] != null).map(k => `<div class="stat"><span>${k.label}</span><b>${esc(fmt(obj[k.key], k.digits ?? 2))}</b></div>`).join('');

  async function mlbStats(name) {
    const q=encodeURIComponent(name||'');
    const search=await fetch(`https://statsapi.mlb.com/api/v1/people/search?names=${q}&active=false`).then(r=>r.ok?r.json():null).catch(()=>null);
    const people=search?.people||[]; const exact=people.find(x=>String(x.fullName||'').toLowerCase()===String(name||'').toLowerCase())||people[0];
    if(!exact?.id)return null;
    const [hit,pit]=await Promise.all([
      fetch(`https://statsapi.mlb.com/api/v1/people/${exact.id}/stats?stats=season&group=hitting&season=2026`).then(r=>r.ok?r.json():null).catch(()=>null),
      fetch(`https://statsapi.mlb.com/api/v1/people/${exact.id}/stats?stats=season&group=pitching&season=2026`).then(r=>r.ok?r.json():null).catch(()=>null)
    ]);
    return {person:exact,hitting:hit?.stats?.[0]?.splits?.[0]?.stat||null,pitching:pit?.stats?.[0]?.splits?.[0]?.stat||null};
  }

  window.openPlayer=async function(id){
    $('playerModal').classList.add('on'); $('pmName').textContent='Loading player…'; $('pmSub').textContent='Live ESPN + MLB season data'; $('pmStats').innerHTML='<div class="loading">Loading labeled season statistics…</div>';
    try{
      const j=await api('/espn/player/'+id),p=j.player||{}; $('pmName').textContent=p.name||'Player';
      const injury=(p.injury_status||'').toUpperCase(); $('pmSub').textContent=`${pos(p)}${elig(p)!=='—'?' · '+elig(p):''}${injury&&injury!=='ACTIVE'?' · '+injuryLabel(injury):''} · Scoring period ${j.scoring_period||'—'}`;
      let html='<div class="statgrid">'+statCards(p,[{label:'Fantasy season points',key:'total_points',digits:1},{label:'Current period points',key:'current_period_points',digits:1},{label:'Owned',key:'percent_owned',digits:1},{label:'Started',key:'percent_started',digits:1}])+'</div>';
      const mlb=await mlbStats(p.name);
      if(mlb?.hitting){const h=mlb.hitting;html+='<div class="sectionTitle">2026 MLB Batting</div><div class="statgrid">'+statCards(h,[{label:'Games (G)',key:'gamesPlayed',digits:0},{label:'At Bats (AB)',key:'atBats',digits:0},{label:'Runs (R)',key:'runs',digits:0},{label:'Hits (H)',key:'hits',digits:0},{label:'Doubles (2B)',key:'doubles',digits:0},{label:'Triples (3B)',key:'triples',digits:0},{label:'Home Runs (HR)',key:'homeRuns',digits:0},{label:'RBI',key:'rbi',digits:0},{label:'Walks (BB)',key:'baseOnBalls',digits:0},{label:'Strikeouts (SO)',key:'strikeOuts',digits:0},{label:'Stolen Bases (SB)',key:'stolenBases',digits:0},{label:'Batting Avg (AVG)',key:'avg',digits:3},{label:'On-Base % (OBP)',key:'obp',digits:3},{label:'Slugging % (SLG)',key:'slg',digits:3},{label:'OPS',key:'ops',digits:3}])+'</div>';}
      if(mlb?.pitching){const x=mlb.pitching;html+='<div class="sectionTitle">2026 MLB Pitching</div><div class="statgrid">'+statCards(x,[{label:'Games (G)',key:'gamesPlayed',digits:0},{label:'Starts (GS)',key:'gamesStarted',digits:0},{label:'Innings (IP)',key:'inningsPitched',digits:1},{label:'Wins (W)',key:'wins',digits:0},{label:'Losses (L)',key:'losses',digits:0},{label:'Saves (SV)',key:'saves',digits:0},{label:'Strikeouts (K)',key:'strikeOuts',digits:0},{label:'ERA',key:'era',digits:2},{label:'WHIP',key:'whip',digits:2},{label:'Hits Allowed (H)',key:'hits',digits:0},{label:'Earned Runs (ER)',key:'earnedRuns',digits:0},{label:'Walks (BB)',key:'baseOnBalls',digits:0}])+'</div>';}
      html+='<div class="sectionTitle">ESPN Fantasy Season</div><div class="notice">Fantasy points are the league-scored total. MLB stats are labeled with standard baseball abbreviations.</div>';
      $('pmStats').innerHTML=html;
    }catch(e){$('pmStats').innerHTML=`<div class="notice err">${esc(e.message)}</div>`;}
  };
})();
