from . import run
from . import main
from .show_live import live_ratings_for_names
from fastapi import Header, Query

@main.app.get('/api/show/live-ratings')
async def show_live_ratings(
    force: bool = Query(False),
    authorization: str = Header(None),
    names: list[str] = Query(default=[]),
):
    # Prefer explicitly requested league-player names from the browser. This lets
    # the frontend ask for only the players currently displayed, without requiring
    # a second authentication lookup.
    requested=[]
    seen=set()
    for name in names or []:
        clean=' '.join(str(name or '').split()).strip()
        key=clean.casefold()
        if clean and key not in seen:
            seen.add(key); requested.append(clean)

    if requested:
        return await live_ratings_for_names(requested,force)

    # Backward-compatible authenticated fallback.
    u=main.uid(authorization)
    league=main.league_row(u)
    req=main.req_for(league)
    data=await main.espn(req,['mTeam','mRoster','mStatus'])
    roster_names=[]
    seen=set()
    for team in data.get('teams',[]):
        for entry in (team.get('roster') or {}).get('entries',[]):
            p=entry.get('playerPoolEntry') or {}
            player=p.get('player') or {}
            name=player.get('fullName')
            if name:
                key=main.re.sub(r'\s+',' ',name.strip()).casefold()
                if key not in seen:
                    seen.add(key);roster_names.append(name)
    return await live_ratings_for_names(roster_names,force)

@main.app.get('/api/show/live-ratings/health')
async def show_live_ratings_health():
    return {'ok':True,'source':'theSHOWBASE Live Series','mode':'league-player-only'}

if __name__=='__main__':
    import uvicorn, os
    uvicorn.run(main.app,host='0.0.0.0',port=int(os.getenv('PORT','8000')))
