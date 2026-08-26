from . import run
from . import main
from .show_live import live_ratings_for_names
from fastapi import Header, Query

@main.app.get('/api/show/live-ratings')
async def show_live_ratings(force: bool = Query(False), authorization: str = Header(None)):
    u=main.uid(authorization)
    league=main.league_row(u)
    req=main.req_for(league)
    data=await main.espn(req,['mTeam','mRoster','mStatus'])
    names=[];seen=set()
    for team in data.get('teams',[]):
        for entry in (team.get('roster') or {}).get('entries',[]):
            p=entry.get('playerPoolEntry') or {}
            player=p.get('player') or {}
            name=player.get('fullName')
            if name:
                key=main.re.sub(r'\s+',' ',name.strip()).casefold()
                if key not in seen:
                    seen.add(key);names.append(name)
    return await live_ratings_for_names(names,force)

@main.app.get('/api/show/live-ratings/health')
async def show_live_ratings_health():
    return {'ok':True,'source':'theSHOWBASE Live Series','mode':'league-player-only'}

if __name__=='__main__':
    import uvicorn, os
    uvicorn.run(main.app,host='0.0.0.0',port=int(os.getenv('PORT','8000')))
