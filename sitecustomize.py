import json, asyncio
import httpx
from starlette.responses import Response
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import FastAPI

_ORIG_INIT = FastAPI.__init__
POS_FIX = {1:'SP', 2:'C', 3:'1B', 4:'2B', 5:'3B', 6:'SS', 7:'LF', 8:'CF', 9:'RF', 10:'OF', 11:'DH', 12:'RP', 13:'P'}
SLOT_FIX = {0:'C',1:'1B',2:'2B',3:'3B',4:'SS',5:'OF',6:'UTIL',7:'UTIL',8:'UTIL',12:'BENCH',13:'SP',14:'RP',15:'P',16:'IL',17:'P',18:'IL',19:'IL'}

def _positions(p):
    eligible = p.get('eligibleSlots') or []
    vals=[]
    for x in eligible:
        label=SLOT_FIX.get(x)
        if label and label not in vals and label not in ('UTIL','BENCH','IL'):
            vals.append(label)
    default=POS_FIX.get(p.get('defaultPositionId'))
    if default and default not in vals: vals.insert(0,default)
    return default or '—', vals

def _patch_module(mod):
    if getattr(mod, '_player_patch_done', False): return
    mod._player_patch_done=True
    mod.POS.update(POS_FIX); mod.SLOT.update(SLOT_FIX)
    orig_cp=mod.compact_player
    def cp(e):
        out=orig_cp(e)
        p=(e.get('playerPoolEntry') or {}).get('player') or e.get('player') or {}
        pos, elig=_positions(p)
        out['position']=pos; out['eligible_positions']=elig; out['display_position']=pos if not elig else '/'.join(elig)
        out['status_label']=out.get('roster_status') or 'ACTIVE'
        return out
    mod.compact_player=cp
    orig_pool=mod.pool
    async def pool(*args,**kwargs):
        rows=await orig_pool(*args,**kwargs)
        for out in rows:
            out['eligible_positions']=list(dict.fromkeys([x for x in (out.get('eligible_positions') or []) if x not in ('UTIL','BENCH','IL','—')]))
            if out.get('position') and out['position'] not in out['eligible_positions']:
                out['eligible_positions'].insert(0,out['position'])
            out['display_position']='/'.join(out['eligible_positions']) if out['eligible_positions'] else out.get('position','—')
        return rows
    mod.pool=pool
    orig_card=mod.player_card
    async def card(req,pid,p):
        out=await orig_card(req,pid,p)
        out['position']=POS_FIX.get(out.get('position_id'),out.get('position','—'))
        try:
            async with httpx.AsyncClient(timeout=8,follow_redirects=True,headers={'User-Agent':'AI-Fantasy-GM/2.0'}) as c:
                r=await c.get(f'https://statsapi.mlb.com/api/v1/people/{int(pid)}/stats',params={'stats':'season','group':'hitting,pitching','season':str(req.season)})
                if r.status_code < 400:
                    rows=[]
                    for group in r.json().get('stats',[]) or []:
                        for split in group.get('splits',[]) or []:
                            rows.append({'group':group.get('group'),'season':split.get('season'),'team':(split.get('team') or {}).get('name'),'stats':split.get('stat') or {}})
                    out['mlb_season_stats']=rows
        except Exception: out['mlb_season_stats']=[]
        out['fantasy_season_stats']={'fantasy_points':out.get('total_points'),'applied_stat_total':out.get('current_period_points'),'percent_owned':out.get('percent_owned'),'percent_started':out.get('percent_started'),'scoring_period':p}
        return out
    mod.player_card=card

class PlayerUI(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response=await call_next(request); ctype=response.headers.get('content-type','')
        if 'text/html' not in ctype: return response
        body=b''
        async for chunk in response.body_iterator: body += chunk
        extra=r'''<style>.player-link{cursor:pointer}.player-link:hover{background:#132b43!important}.statgrid{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}.statbox{padding:12px;background:#091625;border:1px solid #29435c;border-radius:10px}.statbox b{display:block;font-size:18px;margin-top:4px}@media(max-width:620px){.statgrid{grid-template-columns:1fr 1fr}}</style><div id="playerModal" class="modal"><div class="modalbox"><button class="close" onclick="closePlayer()">Close</button><div id="playerModalBody" class="loading">Loading player…</div></div></div><script>
async function openPlayer(id){if(!id)return;const m=document.getElementById('playerModal'),b=document.getElementById('playerModalBody');m.classList.add('on');b.innerHTML='<div class="loading">Loading current season stats…</div>';try{const r=await api('/espn/player/'+id),p=r.player||{},mlb=p.mlb_season_stats||[],f=p.fantasy_season_stats||{};let stats='';for(const g of mlb){for(const [k,v] of Object.entries(g.stats||{})){if(v!==null&&v!==undefined&&v!=='')stats+='<div class="statbox"><span class="muted">'+esc(k)+'</span><b>'+esc(v)+'</b></div>'}}b.innerHTML='<div class="ey">Player</div><h2 style="margin:4px 0">'+esc(p.name)+'</h2><div class="muted">'+esc(p.position||'—')+' · '+(p.active?'Active':'Inactive')+'</div><h3>Fantasy Season</h3><div class="statgrid"><div class="statbox"><span class="muted">Fantasy Points</span><b>'+esc(f.fantasy_points??'—')+'</b></div><div class="statbox"><span class="muted">Owned</span><b>'+esc(f.percent_owned??'—')+'</b></div><div class="statbox"><span class="muted">Started</span><b>'+esc(f.percent_started??'—')+'</b></div><div class="statbox"><span class="muted">Scoring Period</span><b>'+esc(f.scoring_period??'—')+'</b></div></div><h3>MLB Season Stats</h3><div class="statgrid">'+(stats||'<div class="muted">No season stats available.</div>')+'</div>'}catch(e){b.innerHTML='<div class="notice err">Unable to load player stats: '+esc(e.message)+'</div>'}}
function closePlayer(){document.getElementById('playerModal')?.classList.remove('on')}
function wirePlayerClicks(){document.querySelectorAll('#roster tr[data-player-id],#waiverRows tr[data-player-id],#opRoster tr[data-player-id]').forEach(r=>{r.classList.add('player-link');r.onclick=()=>openPlayer(r.dataset.playerId)})}
setTimeout(wirePlayerClicks,700);setInterval(wirePlayerClicks,1200);
</script>'''
        text=body.decode('utf-8','replace').replace('</body>',extra+'</body>')
        headers={k:v for k,v in response.headers.items() if k.lower() not in ('content-length','content-encoding')}
        return Response(content=text,status_code=response.status_code,headers=headers,media_type='text/html')

def _init(self,*args,**kwargs):
    _ORIG_INIT(self,*args,**kwargs); self.add_middleware(PlayerUI)
    @self.on_event('startup')
    async def _patch_startup():
        import sys
        mod=sys.modules.get('backend.main') or sys.modules.get('main')
        if mod: _patch_module(mod)
FastAPI.__init__=_init
