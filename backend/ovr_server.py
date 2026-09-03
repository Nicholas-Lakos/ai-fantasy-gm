import os
from fastapi import Header
from fastapi.responses import FileResponse, HTMLResponse
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


@main.app.middleware('http')
async def inject_fantasy_ovr_frontend(request, call_next):
    response = await call_next(request)
    if request.url.path != '/' or response.status_code != 200:
        return response
    try:
        body = b''
        async for chunk in response.body_iterator:
            body += chunk
        text = body.decode('utf-8')
        if '/fantasy_ovr.js' not in text:
            text = text.replace('</body>', '<script src="/fantasy_ovr.js?v=20260902"></script></body>')
        return HTMLResponse(text, status_code=response.status_code, headers={'Cache-Control': 'no-store'})
    except Exception:
        return response


@main.app.get('/fantasy_ovr.js')
def fantasy_ovr_js():
    path = os.path.join(main.ROOT, 'frontend', 'fantasy_ovr.js')
    return FileResponse(path, media_type='application/javascript', headers={'Cache-Control': 'no-store'})
