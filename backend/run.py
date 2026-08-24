import os, asyncio
import uvicorn
import httpx
from fastapi import Query
from fastapi.responses import FileResponse, HTMLResponse
from . import main
from .show_live import live_ratings

POS=main.POS
SLOT=main.SLOT
_ORIGINAL_LIVE=main.live
FRONTEND_VERSION='20260824-recovery-1'

@main.app.middleware('http')
async def inject_current_frontend(request, call_next):
    if request.url.path == '/':
        path=os.path.join(main.ROOT,'frontend','index.html')
        try:
            html=open(path,'r',encoding='utf-8').read()
            tag=f'<script src="/fixes.js?v={FRONTEND_VERSION}"></script>'
            if '/fixes.js?' not in html: html=html.replace('</body>',tag+'</body>')
            return HTMLResponse(html,headers={'Cache-Control':'no-store'})
        except Exception: pass
    return await call_next(request)

def player_obj(entry):
    ppe=entry.get('playerPoolEntry') or {}
    return ppe.get('player') or entry.get('player') or ppe or entry

def compact_player_fixed(entry):
    ppe=entry.get('playerPoolEntry') or {}; p=player_obj(entry); pid=p.get('id') or ppe.get('id') or entry.get('playerId'); slot=entry.get('lineupSlotId'); injury=p.get('injuryStatus') or entry.get('injuryStatus') or ''
    return {'id':pid,'name':p.get('fullName') or entry.get('fullName') or f'Player {pid}','position':POS.get(p.get('defaultPositionId'),'—'),'eligible_positions':[POS[x] for x in (p.get('eligibleSlots') or []) if x in POS],'pro_team_id':p.get('proTeamId'),'injury_status':injury,'lineup_slot':SLOT.get(slot,'—'),'roster_status':injury or ('BENCH' if slot==12 else 'ACTIVE'),'total_points':ppe.get('totalPoints',entry.get('totalPoints')),'applied_stat_total':ppe.get('appliedStatTotal',entry.get('appliedStatTotal')),'percent_owned':ppe.get('percentOwned',entry.get('percentOwned')),'percent_started':ppe.get('percentStarted',entry.get('percentStarted'))}

def compact_team_fixed(t):
    return {'id':t.get('id'),'name':main.team_name(t),'location':t.get('location'),'nickname':t.get('nickname'),'record':main.rec(t),'points':t.get('points',0),'logo':t.get('logo'),'roster':[compact_player_fixed(e) for e in (t.get('roster') or {}).get('entries',[])]}

async def hydrate_rosters(req,d,period):
    ids=[]
    for t in d.get('teams',[]) or []:
        for e in (t.get('roster') or {}).get('entries',[]) or []:
            if e.get('playerId') is not None: ids.append(int(e['playerId']))
    ids=list(dict.fromkeys(ids))
    if not ids:return d
    hydrated={}
    for start in range(0,len(ids),200):
        batch=ids[start:start+200]
        try:
            info=await main.espn(req,['kona_player_info'],period,{'players':{'filterIds':{'value':batch},'limit':len(batch),'sortPercOwned':{'sortPriority':1,'sortAsc':False}}},timeout=35)
            for x in info.get('players',[]) or []:
                pid=x.get('id') or (x.get('playerPoolEntry') or {}).get('id') or (x.get('player') or {}).get('id')
                if pid is not None:hydrated[int(pid)]=x
        except Exception: continue
    for t in d.get('teams',[]) or []:
        for e in (t.get('roster') or {}).get('entries',[]) or []:
            pid=e.get('playerId'); x=hydrated.get(int(pid)) if pid is not None else None
            if not x:continue
            if x.get('playerPoolEntry') is not None:e['playerPoolEntry']=x['playerPoolEntry']
            if x.get('player') is not None:e['player']=x['player']
            elif (x.get('playerPoolEntry') or {}).get('player') is not None:e['player']=(x.get('playerPoolEntry') or {}).get('player')
            for k in ('totalPoints','appliedStatTotal','percentOwned','percentStarted'):
                if k not in e and k in x:e[k]=x[k]
    return d

async def live_fixed(u,waivers=False):
    l,req,d,p,w=await _ORIGINAL_LIVE(u,waivers); d=await hydrate_rosters(req,d,p); return l,req,d,p,w

async def pool_fixed(req,p,limit=500):
    filters={'players':{'filterStatus':{'value':['FREEAGENT','WAIVERS']},'limit':limit,'sortPercOwned':{'sortPriority':1,'sortAsc':False}}}
    try:data=await main.espn(req,['kona_player_info'],p,filters,timeout=35);items=data.get('players') or []
    except Exception:items=[]
    out={}
    for entry in items:
        po=player_obj(entry);ppe=entry.get('playerPoolEntry') or {};status=ppe.get('status') or entry.get('status') or 'FREEAGENT'
        if status not in ('FREEAGENT','WAIVERS'):continue
        pid=po.get('id') or ppe.get('id') or entry.get('id')
        if not pid:continue
        out[int(pid)]={'id':pid,'name':po.get('fullName') or f'Player {pid}','position':POS.get(po.get('defaultPositionId'),'—'),'eligible_positions':[POS[x] for x in (po.get('eligibleSlots') or []) if x in POS],'injury_status':po.get('injuryStatus') or entry.get('injuryStatus'),'total_points':ppe.get('totalPoints',entry.get('totalPoints')),'percent_owned':ppe.get('percentOwned',entry.get('percentOwned')),'percent_started':ppe.get('percentStarted',entry.get('percentStarted')),'rank':ppe.get('rank',entry.get('rank')),'status':status,'pro_team_id':po.get('proTeamId')}
    return list(out.values())

async def player_card_fixed(req,pid,p):
    filters={'players':{'filterIds':{'value':[int(pid)]},'filterStatsForTopScoringPeriodIds':{'value':max(int(p),1),'additionalValue':[f'00{req.season}',f'10{req.season}']}}}
    try:data=await main.espn(req,['kona_playercard'],p,filters,timeout=30)
    except Exception:data=await main.espn(req,['kona_player_info'],p,{'players':{'filterIds':{'value':[int(pid)]},'limit':1,'sortPercOwned':{'sortPriority':1,'sortAsc':False}}},timeout=30)
    items=data.get('players') or []
    if not items:raise main.HTTPException(404,'Player not found in ESPN.')
    x=items[0];po=player_obj(x);ppe=x.get('playerPoolEntry') or {};raw=po.get('stats') or x.get('stats') or ppe.get('stats') or []
    if isinstance(raw,dict):raw=[raw]
    season=[];display={};current=ppe.get('appliedStatTotal',x.get('appliedStatTotal'))
    for s in raw:
        if not isinstance(s,dict):continue
        applied=s.get('appliedStats') or s.get('stats') or {};total=s.get('appliedTotal',s.get('appliedStatTotal'));code=str(s.get('id',''));actual=code==f'00{req.season}' or (s.get('seasonId')==req.season and s.get('statTypeId') in (0,'0'))
        if actual:season.append({'seasonId':s.get('seasonId'),'scoringPeriodId':s.get('scoringPeriodId'),'appliedTotal':total,'appliedStats':applied});display.update({str(k):v for k,v in applied.items()})
        if s.get('scoringPeriodId')==p and total is not None:
            try:current=float(total)
            except Exception:pass
    return {'id':pid,'name':po.get('fullName') or f'Player {pid}','position':POS.get(po.get('defaultPositionId'),'—'),'eligible_positions':[POS[x] for x in (po.get('eligibleSlots') or []) if x in POS],'pro_team_id':po.get('proTeamId'),'injury_status':po.get('injuryStatus'),'active':po.get('active'),'total_points':ppe.get('totalPoints',x.get('totalPoints')),'current_period_points':current,'percent_owned':ppe.get('percentOwned',x.get('percentOwned')),'percent_started':ppe.get('percentStarted',x.get('percentStarted')),'stats':display,'season_splits':season,'raw_stat_count':len(raw)}

async def mlb_payload(name):
    async with httpx.AsyncClient(timeout=20,follow_redirects=True) as c:
        search=await c.get('https://statsapi.mlb.com/api/v1/people/search',params={'names':name,'active':'false','sportIds':'1'});search.raise_for_status();people=search.json().get('people') or []
        exact=next((x for x in people if str(x.get('fullName','')).casefold()==name.casefold()),None) or (people[0] if people else None)
        if not exact:return {'found':False,'name':name}
        pid=exact['id']
        async def stats(group):
            r=await c.get(f'https://statsapi.mlb.com/api/v1/people/{pid}/stats',params={'stats':'season','group':group,'season':2026,'gameType':'R'});r.raise_for_status()
            for block in r.json().get('stats') or []:
                splits=block.get('splits') or []
                if splits:
                    split=next((s for s in splits if s.get('isHome') is None and s.get('team') is None),splits[0]);return split.get('stat') or {}
            return None
        h,p=await asyncio.gather(stats('hitting'),stats('pitching'))
        return {'found':True,'mlb_id':pid,'name':exact.get('fullName'),'position':(exact.get('primaryPosition') or {}).get('abbreviation'),'hitting':h,'pitching':p}

@main.app.get('/mlb/player-stats')
async def mlb_player_stats(name:str=Query(...,min_length=1)):
    try:return await mlb_payload(name)
    except Exception as e:return {'found':False,'name':name,'error':str(e)}

@main.app.get('/api/mlb/player-stats')
async def mlb_player_stats_api(name:str=Query(...,min_length=1)):
    try:return await mlb_payload(name)
    except Exception as e:return {'found':False,'name':name,'error':str(e)}

@main.app.get('/api/show/live-ratings')
async def show_live_ratings(force:bool=False):
    try:return await live_ratings(force)
    except Exception as e:return {'source':'theSHOWBASE Live Series','game':'MLB The Show 26','count':0,'players':[],'error':str(e)}

@main.app.get('/api/show/live-ratings/health')
async def show_live_ratings_health():
    data=await show_live_ratings(False);return {'ok':bool(data.get('count')),'count':data.get('count',0),'source':data.get('source'),'error':data.get('error')}

main.compact_player=compact_player_fixed
main.compact_team=compact_team_fixed
main.pool=pool_fixed
main.player_card=player_card_fixed
main.live=live_fixed

@main.app.get('/fixes.js')
def fixes_js():return FileResponse(os.path.join(main.ROOT,'frontend','fixes.js'),media_type='application/javascript',headers={'Cache-Control':'no-store'})

if __name__=='__main__':uvicorn.run(main.app,host='0.0.0.0',port=8000)