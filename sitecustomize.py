import json
import httpx
from starlette.responses import Response
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import FastAPI

_ORIG_INIT = FastAPI.__init__
POS_FIX = {1:'SP',2:'C',3:'1B',4:'2B',5:'3B',6:'SS',7:'LF',8:'CF',9:'RF',10:'OF',11:'DH',12:'RP'}
SLOT_FIX = {0:'C',1:'1B',2:'2B',3:'3B',4:'SS',5:'OF',7:'UTIL',12:'BENCH',13:'SP',14:'RP',15:'P',17:'P'}


def _positions(player):
    eligible = []
    for slot in player.get('eligibleSlots') or []:
        label = SLOT_FIX.get(slot)
        if label and label not in ('UTIL','BENCH') and label not in eligible:
            eligible.append(label)
    default = POS_FIX.get(player.get('defaultPositionId'))
    if default and default not in eligible:
        eligible.insert(0, default)
    return default or '—', eligible


def _patch_module(mod):
    if getattr(mod, '_gm_patch_done', False):
        return
    mod._gm_patch_done = True
    mod.POS.update(POS_FIX)
    mod.SLOT.update(SLOT_FIX)

    # -------------------- ROSTERS --------------------
    orig_cp = mod.compact_player
    def cp(entry):
        out = orig_cp(entry)
        p = (entry.get('playerPoolEntry') or {}).get('player') or {}
        pos, eligible = _positions(p)
        out['position'] = pos
        out['eligible_positions'] = eligible
        out['display_position'] = '/'.join(eligible) if eligible else pos
        slot = entry.get('lineupSlotId')
        out['lineup_slot'] = SLOT_FIX.get(slot, '—')
        out['roster_status'] = 'BENCH' if slot == 12 else 'ACTIVE'
        out['injury_status'] = p.get('injuryStatus') or 'ACTIVE'
        return out
    mod.compact_player = cp

    # -------------------- WAIVERS --------------------
    orig_pool = mod.pool
    async def pool(*args, **kwargs):
        rows = await orig_pool(*args, **kwargs)
        # The base pool already has the correct player IDs and points. Re-query
        # the same pool only to obtain eligibleSlots, because eligibleSlots are
        # fantasy lineup slots and must not be interpreted as default positions.
        req = args[0] if args else kwargs.get('req')
        scoring_period = args[1] if len(args) > 1 else kwargs.get('p')
        if req is not None:
            try:
                filt = {'players': {'filterStatus': {'value':['FREEAGENT','WAIVERS']}, 'limit':500, 'sortPercOwned': {'sortPriority':1,'sortAsc':False}}}
                data = await mod.espn(req, ['kona_player_info'], scoring_period, filt, timeout=35)
                by_id = {str((x.get('player') or {}).get('id') or x.get('id')): x for x in (data.get('players') or [])}
                for row in rows:
                    item = by_id.get(str(row.get('id')))
                    if not item:
                        continue
                    p = item.get('player') or {}
                    pos, eligible = _positions(p)
                    row['position'] = pos
                    row['eligible_positions'] = eligible
                    row['display_position'] = '/'.join(eligible) if eligible else pos
                    pe = item.get('playerPoolEntry') or {}
                    row['status'] = pe.get('status') or item.get('status') or row.get('status') or 'FREEAGENT'
            except Exception:
                pass
        for row in rows:
            row['eligible_positions'] = [x for x in (row.get('eligible_positions') or []) if x not in ('UTIL','BENCH','IL','—')]
            row['display_position'] = '/'.join(row['eligible_positions']) if row['eligible_positions'] else row.get('position','—')
        return rows
    mod.pool = pool

    # -------------------- PLAYER CARD / STATS --------------------
    orig_card = mod.player_card
    async def card(req, pid, scoring_period):
        # kona_player_info exposes stats[]; actual season totals are the entry
        # with statSourceId=0 and statSplitTypeId=0. The old code incorrectly
        # selected statTypeId==0, which is not the season-split selector.
        filt = {'players': {'filterIds': {'value':[int(pid)]}, 'filterStatsForSplitTypeIds': {'value':[0,1]}, 'limit':1}}
        data = None
        try:
            data = await mod.espn(req, ['kona_player_info'], scoring_period, filt, timeout=25)
        except Exception:
            data = None
        items = (data or {}).get('players') or []
        if not items:
            return await orig_card(req, pid, scoring_period)
        item = items[0]
        p = item.get('player') or {}
        pe = item.get('playerPoolEntry') or {}
        season = []
        recent = []
        for s in pe.get('stats') or []:
            if s.get('seasonId') != req.season or s.get('statSourceId',0) != 0:
                continue
            if s.get('statSplitTypeId') == 0:
                season.append(s)
            else:
                recent.append(s)
        season_entry = season[-1] if season else None
        fantasy_points = (season_entry or {}).get('appliedTotal')
        if fantasy_points is None:
            fantasy_points = pe.get('totalPoints')
        applied = (season_entry or {}).get('appliedStats') or {}
        raw = (season_entry or {}).get('stats') or applied
        pos, eligible = _positions(p)

        result = {
            'id': int(pid),
            'name': p.get('fullName') or f'Player {pid}',
            'position': pos,
            'eligible_positions': eligible,
            'display_position': '/'.join(eligible) if eligible else pos,
            'pro_team_id': p.get('proTeamId'),
            'injury_status': p.get('injuryStatus') or 'ACTIVE',
            'active': p.get('active'),
            'total_points': fantasy_points,
            'fantasy_season_points': fantasy_points,
            'current_period_points': pe.get('appliedStatTotal'),
            'percent_owned': pe.get('percentOwned'),
            'percent_started': pe.get('percentStarted'),
            'stats': raw,
            'fantasy_season_stats': applied,
            'stat_entries': season,
            'recent_stat_entries': recent[-14:],
            'raw_stat_count': len(raw),
        }

        # ESPN's fantasy player-card feed is the authoritative fantasy source.
        # For real MLB season stats, use the ESPN athlete feed first, then MLB
        # Stats API as a fallback. Some ESPN IDs are not identical to MLB IDs.
        result['mlb_season_stats'] = []
        urls = [
            f'https://site.web.api.espn.com/apis/common/v3/sports/baseball/mlb/athletes/{int(pid)}',
            f'https://statsapi.mlb.com/api/v1/people/{int(pid)}/stats',
        ]
        async with httpx.AsyncClient(timeout=8, follow_redirects=True, headers={'User-Agent':'AI-Fantasy-GM/2.0'}) as client:
            for url in urls:
                try:
                    params = {'stats':'season','group':'hitting,pitching','season':str(req.season)} if 'statsapi.mlb.com' in url else None
                    resp = await client.get(url, params=params)
                    if resp.status_code >= 400:
                        continue
                    payload = resp.json()
                    rows = []
                    if 'statsapi.mlb.com' in url:
                        for group in payload.get('stats',[]) or []:
                            for split in group.get('splits',[]) or []:
                                rows.append({'group':group.get('group'),'season':split.get('season'),'team':(split.get('team') or {}).get('name'),'stats':split.get('stat') or {}})
                    else:
                        # ESPN athlete payloads vary; preserve common season-stat
                        # structures without inventing values.
                        athletes = payload.get('athlete') or payload.get('athletes') or payload
                        if isinstance(athletes, dict):
                            for key in ('statistics','stats','seasonStats'):
                                value = athletes.get(key)
                                if value:
                                    rows.append({'source':'ESPN','stats':value})
                    if rows:
                        result['mlb_season_stats'] = rows
                        break
                except Exception:
                    continue
        return result
    mod.player_card = card

    # -------------------- TEAM CONTEXT FOR AI --------------------
    orig_team = mod.compact_team
    def team(t):
        out = orig_team(t)
        roster = out.get('roster') or []
        depth = {}
        for p in roster:
            pos = p.get('position')
            if pos:
                depth[pos] = depth.get(pos,0) + 1
        out['roster_count'] = len(roster)
        out['position_depth'] = depth
        out['total_roster_points'] = round(sum(float(p.get('total_points') or 0) for p in roster),2)
        return out
    mod.compact_team = team


class PlayerUI(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        ctype = response.headers.get('content-type','')
        if 'text/html' not in ctype:
            return response
        body = b''
        async for chunk in response.body_iterator:
            body += chunk
        extra = r'''<style>.player-link{cursor:pointer}.player-link:hover{background:#132b43!important}.statgrid{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}.statbox{padding:12px;background:#091625;border:1px solid #29435c;border-radius:10px}.statbox b{display:block;font-size:18px;margin-top:4px}@media(max-width:620px){.statgrid{grid-template-columns:1fr 1fr}}</style><div id="playerModal" class="modal"><div class="modalbox"><button class="close" onclick="closePlayer()">Close</button><div id="playerModalBody" class="loading">Loading player…</div></div></div><script>
async function openPlayer(id){if(!id)return;const m=document.getElementById('playerModal'),b=document.getElementById('playerModalBody');m.classList.add('on');b.innerHTML='<div class="loading">Loading season stats…</div>';try{const r=await api('/espn/player/'+id),p=r.player||{},f=p.fantasy_season_stats||{},mlb=p.mlb_season_stats||[];let fs='';for(const [k,v] of Object.entries(f)){if(v!==null&&v!==undefined&&v!=='')fs+='<div class="statbox"><span class="muted">'+esc(k)+'</span><b>'+esc(v)+'</b></div>'}let ms='';for(const g of mlb){for(const [k,v] of Object.entries(g.stats||{})){if(v!==null&&v!==undefined&&v!=='')ms+='<div class="statbox"><span class="muted">'+esc(k)+'</span><b>'+esc(v)+'</b></div>'}}b.innerHTML='<div class="ey">Player</div><h2 style="margin:4px 0">'+esc(p.name)+'</h2><div class="muted">'+esc(p.display_position||p.position||'—')+' · '+esc(p.injury_status||'ACTIVE')+'</div><h3>Fantasy Season</h3><div class="statgrid">'+(fs||'<div class="muted">Fantasy stats unavailable.</div>')+'</div><h3>MLB Season</h3><div class="statgrid">'+(ms||'<div class="muted">MLB season stats unavailable for this player ID.</div>')+'</div>'}catch(e){b.innerHTML='<div class="notice err">Unable to load player stats: '+esc(e.message)+'</div>'}}
function closePlayer(){document.getElementById('playerModal')?.classList.remove('on')}
function wirePlayerClicks(){document.querySelectorAll('#roster tr[data-player-id],#waiverRows tr[data-player-id],#opRoster tr[data-player-id]').forEach(r=>{r.classList.add('player-link');r.onclick=()=>openPlayer(r.dataset.playerId)})}
setTimeout(wirePlayerClicks,500);setInterval(wirePlayerClicks,1000);
</script>'''
        text = body.decode('utf-8','replace').replace('</body>',extra+'</body>')
        headers = {k:v for k,v in response.headers.items() if k.lower() not in ('content-length','content-encoding')}
        return Response(content=text,status_code=response.status_code,headers=headers,media_type='text/html')


def _init(self,*args,**kwargs):
    _ORIG_INIT(self,*args,**kwargs)
    self.add_middleware(PlayerUI)
    @self.on_event('startup')
    async def _patch_startup():
        import sys
        mod = sys.modules.get('backend.main') or sys.modules.get('main')
        if mod:
            _patch_module(mod)

FastAPI.__init__ = _init
