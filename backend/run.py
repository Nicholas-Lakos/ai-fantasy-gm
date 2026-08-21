import os
import uvicorn
import httpx
from fastapi import Query
from fastapi.responses import FileResponse
from . import main

POS=main.POS
SLOT=main.SLOT

def player_obj(entry):
    ppe=entry.get('playerPoolEntry') or {}
    return ppe.get('player') or entry.get('player') or ppe or entry

def compact_player_fixed(entry):
    ppe=entry.get('playerPoolEntry') or {}; p=player_obj(entry); pid=p.get('id') or ppe.get('id') or entry.get('playerId'); slot=entry.get('lineupSlotId'); injury=p.get('injuryStatus') or entry.get('injuryStatus') or ''
    return {'id':pid,'name':p.get('fullName') or entry.get('fullName') or f'Player {pid}','position':POS.get(p.get('defaultPositionId'),'—'),'eligible_positions':[POS[x] for x in (p.get('eligibleSlots') or []) if x in POS],'pro_team_id':p.get('proTeamId'),'injury_status':inj,'lineup_slot':SLOT.get(slot,'—'),'roster_status':inj or ('BENCH' if slot==12 else 'ACTIVE'),'total_points':ppe.get('totalPoints',entry.get('totalPoints')),'applied_stat_total':ppe.get('appliedStatTotal',entry.get('appliedStatTotal')),'percent_owned':ppe.get('percentOwned',entry.get('percentOwned')),'percent_started':ppe.get('percentStarted',entry.get('percentStarted'))}

async def pool_fixed(req,p,limit=500):
    filters={'players':{'filterStatus':{'value':['FREEAGENT','WAIVERS']},'limit':limit,'sortPercOwned':{'sortPriority':1,'sortAsc':False}}}
    try: data=await main.espn(req,['kona_player_info'],p,filters,timeout=35); items=data.get('players') or []
    except Exception: items=[]
    if not items:
        try: data=await main.espn(req,['kona_player_info'],p,{'players':{'limit':limit,'sortPercOwned':{'sortPriority':1,'sortAsc':False}}},timeout=35); items=data.get('players') or []
        except Exception: items=[]
    out={}
    for entry in items:
        po=player_obj(entry); ppe=entry.get('playerPoolEntry') or {}; status=ppe.get('status') or entry.get('status') or 'FREEAGENT'; on_team=entry.get('onTeamId',ppe.get('onTeamId'))
        if status not in ('FREEAGENT','WAIVERS') and on_team not in (None,0): continue
        pid=po.get('id') or ppe.get('id') or entry.get('id')
        if not pid: continue
        out[pid]={'id':pid,'name':po.get('fullName') or f'Player {pid}','position':POS.get(po.get('defaultPositionId'),'—'),'eligible_positions':[POS[x] for x in (po.get('eligibleSlots') or []) if x in POS],'injury_status':po.get('injuryStatus'),'total_points':ppe.get('totalPoints',entry.get('totalPoints')),'percent_owned':ppe.get('percentOwned',entry.get('percentOwned')),'percent_started':ppe.get('percentStarted',entry.get('percentStarted')),'rank':ppe.get('rank',entry.get('rank')),'status':status,'pro_team_id':po.get('proTeamId')}
    return list(out.values())

async def player_card_fixed(req,pid,p):
    filters={'players':{'filterIds':{'value':[int(pid)]},'filterStatsForTopScoringPeriodIds':{'value':max(int(p),1),'additionalValue':[f'00{req.season}',f'10{req.season}']}}}
    try: data=await main.espn(req,['kona_playercard'],p,filters,timeout=30)
    except Exception: data=await main.espn(req,['kona_player_info'],p,{'players':{'filterIds':{'value':[int(pid)]},'limit':1}},timeout=30)
    items=data.get('players') or []
    if not items: raise main.HTTPException(404,'Player not found in ESPN.')
    x=items[0]; po=player_obj(x); ppe=x.get('playerPoolEntry') or {}; raw=po.get('stats') or x.get('stats') or ppe.get('stats') or []
    if isinstance(raw,dict): raw=[raw]
    season=[];display={};current=ppe.get('appliedStatTotal',x.get('appliedStatTotal'))
    for s in raw:
        if not isinstance(s,dict): continue
        applied=s.get('appliedStats') or s.get('stats') or {}; total=s.get('appliedTotal',s.get('appliedStatTotal')); code=str(s.get('id','')); actual=code==f'00{req.season}' or (s.get('seasonId')==req.season and s.get('statTypeId') in (0,'0'))
        if actual: season.append({'seasonId':s.get('seasonId'),'scoringPeriodId':s.get('scoringPeriodId'),'appliedTotal':total,'appliedStats':applied}); display.update({str(k):v for k,v in applied.items()})
        if s.get('scoringPeriodId')==p and total is not None:
            try: current=float(total)
            except Exception: pass
    return {'id':pid,'name':po.get('fullName') or f'Player {pid}','position':POS.get(po.get('defaultPositionId'),'—'),'eligible_positions':[POS[x] for x in (po.get('eligibleSlots') or []) if x in POS],'pro_team_id':po.get('proTeamId'),'injury_status':po.get('injuryStatus'),'active':po.get('active'),'total_points':ppe.get('totalPoints',x.get('totalPoints')),'current_period_points':current,'percent_owned':ppe.get('percentOwned',x.get('percentOwned')),'percent_started':ppe.get('percentStarted',x.get('percentStarted')),'stats':display,'season_splits':season,'raw_stat_count':len(raw)}

@main.app.get('/mlb/player-stats')
async def mlb_player_stats(name:str=Query(...,min_length=1)):
    async with httpx.AsyncClient(timeout=15,follow_redirects=True) as c:
        r=await c.get('https://statsapi.mlb.com/api/v1/people/search',params={'names':name,'active':'false'}); r.raise_for_status(); people=r.json().get('people') or []
        exact=next((x for x in people if str(x.get('fullName','')).lower()==name.lower()),None) or (people[0] if people else None)
        if not exact: return {'found':False,'name':name}
        pid=exact['id']; h,p=await __import__('asyncio').gather(c.get(f'https://statsapi.mlb.com/api/v1/people/{pid}/stats',params={'stats':'season','group':'hitting','season':2026}),c.get(f'https://statsapi.mlb.com/api/v1/people/{pid}/stats',params={'stats':'season','group':'pitching','season':2026}))
        def first(resp):
            try:
                st=resp.json().get('stats') or []; sp=(st[0].get('splits') or []) if st else []
                return sp[0].get('stat') if sp else None
            except Exception: return None
        return {'found':True,'mlb_id':pid,'name':exact.get('fullName'),'hitting':first(h),'pitching':first(p)}

main.compact_player=compact_player_fixed
main.pool=pool_fixed
main.player_card=player_card_fixed

@main.app.get('/fixes.js')
def fixes_js(): return FileResponse(os.path.join(main.ROOT,'frontend','fixes.js'),media_type='application/javascript')

if __name__=='__main__': uvicorn.run(main.app,host='0.0.0.0',port=8000)
