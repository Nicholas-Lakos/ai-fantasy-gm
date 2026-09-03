from fastapi import Header
from . import main
from .fantasy_ovr import fetch_fantasy_ovr


@main.app.get('/api/fantasy-ovr')
async def fantasy_ovr(authorization: str = Header(None)):
    user_id = main.uid(authorization)
    league = main.league_row(user_id)
    req = main.req_for(league)
    rows = await fetch_fantasy_ovr(req, main.espn, main.player_card)
    return {
        'source': 'ESPN Fantasy Baseball stats',
        'method': 'position-adjusted dynamic Fantasy OVR',
        'count': len(rows),
        'players': rows,
    }


@main.app.get('/api/fantasy-ovr/health')
def fantasy_ovr_health():
    return {'ok': True, 'source': 'ESPN Fantasy Baseball stats'}
