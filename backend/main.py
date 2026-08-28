import os,sqlite3,hashlib,secrets,hmac,json,asyncio,re
from datetime import datetime,timedelta
from typing import Optional
import httpx,jwt
from fastapi import FastAPI,HTTPException,Header
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel,EmailStr,Field
BASE=os.path.dirname(os.path.abspath(__file__));ROOT=os.path.dirname(BASE);DB=os.getenv('DATABASE_PATH',os.path.join(BASE,'fantasy_gm.db'))
ESPN_BASE='https://lm-api-reads.fantasy.espn.com/apis/v3/games/flb/seasons';OR_BASE='https://openrouter.ai/api/v1/chat/completions';OR_MODEL=os.getenv('OPENROUTER_MODEL','openrouter/free')
POS={1:'SP',2:'C',3:'1B',4:'2B',5:'3B',6:'SS',7:'LF',8:'CF',9:'RF',10:'OF',11:'DH',12:'RP',13:'P'};SLOT={0:'C',1:'1B',2:'2B',3:'3B',4:'SS',5:'OF',7:'UTIL',12:'BENCH',13:'SP',14:'RP',15:'P',17:'P'}
def db():
 c=sqlite3.connect(DB,timeout=15);c.row_factory=sqlite3.Row;c.execute('CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT,email TEXT UNIQUE NOT NULL,password_hash TEXT NOT NULL,name TEXT NOT NULL)');c.execute('CREATE TABLE IF NOT EXISTS leagues(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,league_id TEXT NOT NULL,team_id INTEGER NOT NULL,season INTEGER NOT NULL,espn_s2 TEXT,swid TEXT,league_name TEXT,context_json TEXT,updated_at TEXT)');c.execute('CREATE TABLE IF NOT EXISTS ai_messages(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,role TEXT NOT NULL,content TEXT NOT NULL,created_at TEXT NOT NULL)');c.commit();return c
def ph(p,s=None):s=s or secrets.token_hex(16);return f'pbkdf2$210000${s}${hashlib.pbkdf2_hmac("sha256",p.encode(),s.encode(),210000).hex()}'
def pv(p,v):
 try:_,n,s,d=v.split('$',3);return hmac.compare_digest(hashlib.pbkdf2_hmac('sha256',p.encode(),s.encode(),int(n)).hex(),d)
 except:return hmac.compare_digest(v,hashlib.sha256(('ai-gm:'+p).encode()).hexdigest())
def token(uid):return jwt.encode({'sub':str(uid),'exp':datetime.utcnow()+timedelta(days=14)},os.getenv('JWT_SECRET','ai-fantasy-gm-dev-secret'),algorithm='HS256')
def uid(auth):
 if not auth or not auth.startswith('Bearer '):raise HTTPException(401,'Please sign in first')
 try:return int(jwt.decode(auth[7:],os.getenv('JWT_SECRET','ai-fantasy-gm-dev-secret'),algorithms=['HS256'])['sub'])
 except:raise HTTPException(401,'Your session expired. Please sign in again.')
class Auth(BaseModel):email:EmailStr;password:str=Field(min_length=6);name:str='Fantasy Manager'
class ESPNConnect(BaseModel):league_id:str;team_id:int=9;season:int=2026;espn_s2:Optional[str]=None;swid:Optional[str]=None
class Question(BaseModel):question:str=Field(min_length=1,max_length=4000)
def req_for(row):return ESPNConnect(league_id=row['league_id'],team_id=row['team_id'],season=row['season'],espn_s2=row['espn_s2'],swid=row['swid'])
async def espn(req,views=None,period=None,filter_body=None,timeout=25):
 url=f'{ESPN_BASE}/{req.season}/segments/0/leagues/{req.league_id}';params=[('view',v) for v in (views or [])]
 if period is not None:params.append(('scoringPeriodId',str(period)))
 cookies={}
 if req.espn_s2:cookies['espn_s2']=req.espn_s2.strip()
 if req.swid:cookies['SWID']=req.swid.strip()
 headers={'User-Agent':'Mozilla/5.0 AI-Fantasy-GM','Accept':'application/json'}
 if filter_body:headers['x-fantasy-filter']=json.dumps(filter_body,separators=(',',':'))
 async with httpx.AsyncClient(timeout=timeout,follow_redirects=True) as c:r=await c.get(url,params=params,cookies=cookies,headers=headers)
 if r.status_code in (401,403):raise HTTPException(502,'ESPN rejected the league credentials.')
 if r.status_code>=400:raise HTTPException(502,f'ESPN returned HTTP {r.status_code}.')
 return r.json()
def period(d):
 for o in (d.get('status') or {},d.get('settings') or {}):
  for k in ('scoringPeriodId','currentScoringPeriodId','currentScoringPeriod'):
   v=o.get(k);v=v.get('id') if isinstance(v,dict) else v
   if isinstance(v,int) or (isinstance(v,str) and v.isdigit()):return int(v)
 v=d.get('scoringPeriodId');return int(v) if isinstance(v,(int,str)) and str(v).isdigit() else None
def team_name(t):return t.get('name') or t.get('location') or t.get('nickname') or f"Team {t.get('id')}"
def rec(t):return ((t.get('record') or {}).get('overall') or {})
def compact_player(e):
 ppe=e.get('playerPoolEntry') or {};p=ppe.get('player') or {};pid=p.get('id') or e.get('playerId');slot=e.get('lineupSlotId');inj=p.get('injuryStatus') or e.get('injuryStatus') or ''
 return {'id':pid,'name':p.get('fullName') or f'Player {pid}','position':POS.get(p.get('defaultPositionId'),'—'),'eligible_positions':[POS[x] for x in p.get('eligibleSlots',[]) if x in POS],'pro_team_id':p.get('proTeamId'),'injury_status':inj,'lineup_slot':SLOT.get(slot,'—'),'roster_status':inj or ('BENCH' if slot==12 else 'ACTIVE'),'total_points':ppe.get('totalPoints'),'applied_stat_total':ppe.get('appliedStatTotal'),'percent_owned':ppe.get('percentOwned'),'percent_started':ppe.get('percentStarted')}
def compact_team(t):return {'id':t.get('id'),'name':team_name(t),'location':t.get('location'),'nickname':t.get('nickname'),'record':rec(t),'points':t.get('points',0),'logo':t.get('logo'),'roster':[compact_player(e) for e in (t.get('roster') or {}).get('entries',[])]}
def standings(d,tid):
 a=[]
 for t in d.get('teams',[]):
  r=rec(t);a.append({'id':t.get('id'),'name':team_name(t),'wins':r.get('wins',0),'losses':r.get('losses',0),'ties':r.get('ties',0),'points':t.get('points',0)})
 a.sort(key=lambda x:(x['wins'],x['points']),reverse=True);return a,next((i+1 for i,x in enumerate(a) if x['id']==tid),None)
def league_row(u):
 x=db().execute('SELECT * FROM leagues WHERE user_id=? ORDER BY id DESC LIMIT 1',(u,)).fetchone()
 if not x:raise HTTPException(404,'Connect an ESPN league first')
 return x
async def pool(req,p,limit=500):
 filters={'players':{'filterStatus':{'value':['FREEAGENT','WAIVERS']},'limit':limit,'sortPercOwned':{'sortPriority':1,'sortAsc':False}}}
 try:d=await espn(req,['kona_player_info'],p,filters,timeout=35);items=d.get('players') or []
 except Exception:items=[]
 if not items:
  try:
   d=await espn(req,['kona_player_info'],p,{'players':{'limit':limit,'sortPercOwned':{'sortPriority':1,'sortAsc':False}}},timeout=35);items=[x for x in (d.get('players') or []) if ((x.get('playerPoolEntry') or {}).get('status') in ('FREEAGENT','WAIVERS') or x.get('status') in ('FREEAGENT','WAIVERS'))]
  except Exception:items=[]
 out={}
 for x in items:
  pl=x.get('player') or {};pe=x.get('playerPoolEntry') or {};pid=x.get('id') or pl.get('id')
  if not pid:continue
  status=pe.get('status') or x.get('status') or 'FREEAGENT';out[pid]={'id':pid,'name':pl.get('fullName') or f'Player {pid}','position':POS.get(pl.get('defaultPositionId'),'—'),'eligible_positions':[POS.get(v,'—') for v in pl.get('eligibleSlots',[]) if v in POS],'injury_status':pl.get('injuryStatus'),'total_points':pe.get('totalPoints'),'percent_owned':pe.get('percentOwned'),'percent_started':pe.get('percentStarted'),'rank':pe.get('rank'),'status':status,'pro_team_id':pl.get('proTeamId')}
 return list(out.values())
async def live(u,waivers=False):
 l=league_row(u);req=req_for(l);meta=await espn(req,['mSettings','mTeam','mStandings','mStatus']);p=period(meta)
 if p is None:raise HTTPException(502,'ESPN did not provide the current scoring period.')
 rt=espn(req,['mTeam','mRoster','mStandings','mStatus'],p)
 if waivers:d,w=await asyncio.gather(rt,pool(req,p))
 else:d=await rt;w=[]
 d['settings']=meta.get('settings') or d.get('settings') or {};d['scoringPeriodId']=p;return l,req,d,p,w
async def player_card(req,pid,p):
 # kona_playercard is ESPN's deep per-player view and needs filterStatsForTopScoringPeriodIds
 # with season/type codes. kona_player_info often omits the detailed stats array.
 filters={'players':{'filterIds':{'value':[int(pid)]},'filterStatsForTopScoringPeriodIds':{'value':max(int(p),1),'additionalValue':[f'00{req.season}',f'10{req.season}']}}}
 try:d=await espn(req,['kona_playercard'],p,filters,timeout=25)
 except HTTPException:raise
 except Exception as e:raise HTTPException(502,'ESPN player stats request failed.')
 items=d.get('players') or []
 if not items:raise HTTPException(404,'Player not found in ESPN player card.')
 x=items[0];pl=x.get('player') or {};pe=x.get('playerPoolEntry') or {};stats=[];current=0
 for s in pe.get('stats',[]) or []:
  if s.get('seasonId')==req.season and s.get('statTypeId')==0:
   stats.append({'scoringPeriodId':s.get('scoringPeriodId'),'appliedTotal':s.get('appliedTotal'),'appliedStats':s.get('appliedStats') or {}})
   current=max(current,float(s.get('appliedTotal') or 0))
 # Also expose every stat split so the frontend has something to render even when ESPN returns multiple season entries.
 if not stats:
  for s in pe.get('stats',[]) or []:
   stats.append({'seasonId':s.get('seasonId'),'statTypeId':s.get('statTypeId'),'scoringPeriodId':s.get('scoringPeriodId'),'appliedTotal':s.get('appliedTotal'),'appliedStats':s.get('appliedStats') or {}})
 return {'id':pid,'name':pl.get('fullName'),'position':POS.get(pl.get('defaultPositionId'),'—'),'eligible_positions':[POS.get(v,'—') for v in pl.get('eligibleSlots',[]) if v in POS],'pro_team_id':pl.get('proTeamId'),'injury_status':pl.get('injuryStatus'),'active':pl.get('active'),'total_points':pe.get('totalPoints'),'current_period_points':current or pe.get('appliedStatTotal'),'percent_owned':pe.get('percentOwned'),'percent_started':pe.get('percentStarted'),'stats':stats,'raw_stat_count':len(stats)}

app=FastAPI(title='AI Fantasy GM',version='11.2');app.add_middleware(CORSMiddleware,allow_origins=['*'],allow_methods=['*'],allow_headers=['*'])
# LIVE_SHOW_OVR_SYSTEM_V2
from show_live import live_ratings_for_names

@app.get('/api/show/live-ratings')
async def show_live_ratings(authorization: str = Header(None)):
    u = uid(authorization)
    l = league_row(u)
    req = req_for(l)
    data = await espn(req, ['mTeam', 'mRoster', 'mStatus'])
    names = []
    seen = set()
    for team in data.get('teams', []):
        for entry in (team.get('roster') or {}).get('entries', []):
            ppe = entry.get('playerPoolEntry') or {}
            player = ppe.get('player') or {}
            name = player.get('fullName')
            if name:
                key = ' '.join(str(name).split()).casefold()
                if key not in seen:
                    seen.add(key)
                    names.append(name)
    result = await live_ratings_for_names(names)
    return result

@app.get('/health')
def health():return {'ok':True,'version':'11.2','ai_provider':'openrouter-free','ai_configured':bool(os.getenv('OPENROUTER_API_KEY'))}
@app.post('/auth/signup')
def signup(a:Auth):
 c=db()
 try:x=c.execute('INSERT INTO users(email,password_hash,name) VALUES(?,?,?)',(a.email.lower(),ph(a.password),a.name.strip() or 'Fantasy Manager'));c.commit()
 except sqlite3.IntegrityError:raise HTTPException(409,'That email is already registered')
 return {'token':token(x.lastrowid),'user':{'id':x.lastrowid,'email':a.email.lower(),'name':a.name}}
@app.post('/auth/login')
def login(a:Auth):
 u=db().execute('SELECT * FROM users WHERE email=?',(a.email.lower(),)).fetchone()
 if not u or not pv(a.password,u['password_hash']):raise HTTPException(401,'Invalid email or password')
 return {'token':token(u['id']),'user':{'id':u['id'],'email':u['email'],'name':u['name']}}
@app.get('/auth/me')
def me(authorization:str=Header(None)):
 u=db().execute('SELECT id,email,name FROM users WHERE id=?',(uid(authorization),)).fetchone();return {'user':dict(u)}
@app.post('/espn/connect')
async def connect(r:ESPNConnect,authorization:str=Header(None)):
 u=uid(authorization);m=await espn(r,['mSettings','mTeam','mStandings','mStatus']);name=(m.get('settings') or {}).get('name') or 'ESPN Fantasy League';c=db();c.execute('DELETE FROM leagues WHERE user_id=?',(u,));c.execute('INSERT INTO leagues(user_id,league_id,team_id,season,espn_s2,swid,league_name,context_json,updated_at) VALUES(?,?,?,?,?,?,?,?,?)',(u,r.league_id,r.team_id,r.season,r.espn_s2,r.swid,name,json.dumps(m),datetime.utcnow().isoformat()));c.commit();ss,rank=standings(m,r.team_id);return {'connected':True,'name':name,'teams':len(ss),'rank':rank}
@app.get('/dashboard')
async def dashboard(authorization:str=Header(None)):
 u=uid(authorization);l,r,d,p,_=await live(u);ss,rank=standings(d,l['team_id']);t=next((x for x in d.get('teams',[]) if x.get('id')==l['team_id']),{})
 return {'league':(d.get('settings') or {}).get('name') or l['league_name'],'rank':rank,'record':rec(t),'team':compact_team(t),'teams':[compact_team(x) for x in d.get('teams',[])],'standings':ss,'scoring_period':p,'live_data':True}
@app.get('/league/teams')
async def teams(authorization:str=Header(None)):
 u=uid(authorization);l,r,d,p,_=await live(u);ss,_=standings(d,l['team_id']);return {'league':(d.get('settings') or {}).get('name') or l['league_name'],'my_team_id':l['team_id'],'scoring_period':p,'standings':ss,'teams':[compact_team(x) for x in d.get('teams',[])]}
@app.get('/league/teams/{team_id}')
async def team(team_id:int,authorization:str=Header(None)):
 u=uid(authorization);l,r,d,p,_=await live(u);t=next((x for x in d.get('teams',[]) if x.get('id')==team_id),None)
 if not t:raise HTTPException(404,'That team was not found')
 ss,rank=standings(d,team_id);return {'team':compact_team(t),'rank':rank,'standings':ss,'scoring_period':p}
@app.get('/espn/my-team')
async def myteam(authorization:str=Header(None)):return await dashboard(authorization)
@app.get('/espn/waivers')
async def waivers(authorization:str=Header(None)):
 u=uid(authorization);l,r,d,p,w=await live(u,True);w.sort(key=lambda x:(x.get('total_points') or 0),reverse=True);return {'scoring_period':p,'players':w,'count':len(w),'live_data':True}
@app.get('/espn/player/{player_id}')
async def player(player_id:int,authorization:str=Header(None)):
 u=uid(authorization);l,r,d,p,w=await live(u);return {'player':await player_card(r,player_id,p),'scoring_period':p,'live_data':True}
@app.post('/ai/clear')
def clear(authorization:str=Header(None)):
 c=db();c.execute('DELETE FROM ai_messages WHERE user_id=?',(uid(authorization),));c.commit();return {'cleared':True}
async def ai_call(system,prompt):
 key=os.getenv('OPENROUTER_API_KEY')
 if not key:raise HTTPException(503,'Free AI is not configured. Add OPENROUTER_API_KEY to Render.')
 models=[OR_MODEL,'openai/gpt-oss-120b:free','openai/gpt-oss-20b:free','nvidia/nemotron-3-nano-30b-a3b:free'];last='Free AI unavailable.'
 async with httpx.AsyncClient(timeout=45) as c:
  for m in dict.fromkeys(models):
   try:
    body={'model':m,'messages':[{'role':'system','content':system},{'role':'user','content':prompt}],'max_tokens':1400,'temperature':0.12};r=await c.post(OR_BASE,headers={'Authorization':f'Bearer {key}','Content-Type':'application/json','HTTP-Referer':'https://ai-fantasy-gm.onrender.com','X-Title':'AI Fantasy GM'},json=body)
    if r.status_code>=400:continue
    j=r.json();text=((j.get('choices') or [{}])[0].get('message',{}).get('content') or '').strip()
    if text and text.lower() not in ('safe','user safety: safe'):return text,j.get('model',m)
   except Exception as e:last=str(e)
 raise HTTPException(502,'AI service error: '+last)
@app.post('/ai/gm')
async def gm(q:Question,authorization:str=Header(None)):
 u=uid(authorization);l,r,d,p,w=await live(u,True);ss,rank=standings(d,l['team_id']);teams=[compact_team(x) for x in d.get('teams',[])];my=next((x for x in teams if x['id']==l['team_id']),None);owners=[{'player':p['name'],'team':t['name'],'team_id':t['id'],'position':p['position'],'points':p['total_points']} for t in teams for p in t['roster']];qwords=set(re.findall(r'[a-z0-9]+',q.question.lower()));ranked=sorted(w,key=lambda x:(x.get('total_points') or 0),reverse=True);relevant=[]
 for x in w:
  if qwords.intersection(set(re.findall(r'[a-z0-9]+',x['name'].lower()))):relevant.append(x)
 data={'league':(d.get('settings') or {}).get('name'),'scoring_period':p,'standings':ss,'my_team':my,'opponent_teams':teams,'player_ownership_index':owners,'live_waivers':list({x['id']:x for x in relevant+ranked[:150]}.values()),'waiver_pool_count':len(w),'scoring_settings':(d.get('settings') or {}).get('scoringSettings'),'roster_settings':(d.get('settings') or {}).get('rosterSettings')}
 system='You are an elite fantasy baseball GM. The LIVE ESPN JSON supplied here was fetched immediately before this question. Treat it as authoritative. Never invent players or stats. Determine player ownership from player_ownership_index and waiver availability from live_waivers. Use league scoring and roster settings. Give the recommendation first, then concise evidence. For waivers name the best add and drop. For trades use ACCEPT, DECLINE, or COUNTER and name the manager. Never output safety labels or policy text.'
 c=db();hist=c.execute('SELECT role,content FROM ai_messages WHERE user_id=? ORDER BY id DESC LIMIT 6',(u,)).fetchall();prompt='LIVE ESPN DATA:\n'+json.dumps(data,separators=(',',':'))+'\nRECENT CHAT:\n'+json.dumps([dict(x) for x in reversed(hist)],separators=(',',':'))+'\nQUESTION:\n'+q.question
 ans,model=await ai_call(system,prompt);now=datetime.utcnow().isoformat();c.execute('INSERT INTO ai_messages(user_id,role,content,created_at) VALUES(?,?,?,?)',(u,'user',q.question,now));c.execute('INSERT INTO ai_messages(user_id,role,content,created_at) VALUES(?,?,?,?)',(u,'assistant',ans,now));c.commit();return {'answer':ans,'context':{'scoring_period':p,'my_roster_players':len(my['roster']) if my else 0,'all_opponent_teams':len(teams)-1,'live_waiver_pool_count':len(w),'model':model,'live_data':True}}
@app.get('/')
def home():return FileResponse(os.path.join(ROOT,'frontend','index.html'))
@app.on_event('startup')
def startup():db().close()
