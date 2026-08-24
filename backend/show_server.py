from . import run
from . import main
from .show_live import live_ratings
from fastapi import Query

@main.app.get('/api/show/live-ratings')
async def show_live_ratings(force: bool = Query(False)):
    return await live_ratings(force)

@main.app.get('/api/show/live-ratings/health')
async def show_live_ratings_health():
    data=await live_ratings(False)
    return {'ok':True,'count':data.get('count',0),'source':data.get('source')}

if __name__=='__main__':
    import uvicorn, os
    uvicorn.run(main.app,host='0.0.0.0',port=int(os.getenv('PORT','8000')))
