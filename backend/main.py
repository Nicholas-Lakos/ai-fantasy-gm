import os,sqlite3,hashlib,secrets,hmac,json,asyncio,re
from datetime import datetime,timedelta
from typing import Optional
import httpx,jwt
from fastapi import FastAPI,HTTPException,Header
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel,EmailStr,Field

BASE=os.path.dirname(os.path.abspath(__file__));ROOT=os.path.dirname(BASE);DB=os.getenv('DATABASE_PATH',os.path.join(BASE,'fantasy_gm.db'))
ESPN_BASE='https://lm-api-reads.fantasy.espn.com/apis/v3/games/flb/seasons';OR_BASE='https://openrouter.ai/api/v1/chat/completions'
OR_MODEL=os.getenv('OPENROUTER_MODEL','openrouter/free')
POS={1:'SP',2:'C',3:'1B',4:'2B',5:'3B',6:'SS',7:'LF',8:'CF',9:'RF',10:'OF',11:'DH',12:'RP'}
SLOT={0:'C',1:'1B',2:'2B',3:'3B',4:'SS',5:'OF',7:'UTIL',12:'BENCH',13:'SP',14:'RP',15:'P',17:'P'}

def db():
 c=sqlite3.connect(DB,timeout=15);c.row_factory=sqlite3.Row
 c.execute('CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT,email TEXT UNIQUE NOT NULL,password_hash TEXT NOT NULL,name TEXT NOT NULL)')
 c.execute('CREATE TABLE IF NOT EXISTS leagues(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,league_id TEXT NOT NULL,team_id INTEGER NOT NULL,season INTEGER NOT NULL,espn_s2 TEXT,swid TEXT,league_name TEXT,context_json TEXT,updated_at TEXT)')
 c.execute('CREATE TABLE IF NOT EXISTS ai_messages(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,role TEXT NOT NULL,content TEXT NOT NULL,created_at TEXT NOT NULL)');c.commit();return c

def ph(p,s=None):
 s=s or secrets.token_hex(16);return f'pbkdf2$210000${s}${hashlib.pbkdf2_hmac("sha256",p.encode(),s.encode(),210000).hex()}'
def pv(p,v):
 try:
  _,n,s,d=v.split('$',3);return hmac.compare_digest(hashlib.pbkdf2_hmac('sha256',p.encode(),s.encode(),int(n)).hex(),d)
 except:return hmac.compare_digest(v,hashlib.sha256(('ai-gm:'+p).encode()).hexdigest())
def token(uid):return jwt.encode({'sub':str(uid),'exp':datetime.utcnow()+timedelta(days=14)},os.getenv('JWT_SECRET','ai-fantasy-gm-dev-secret'),algorithm='HS256')
def uid(auth):
 if not auth or not auth.startswith('Bearer '):raise HTTPException(401,'Please sign in first')
 try:return int(jwt.decode(auth[7:],os.getenv('JWT_SECRET','ai-fantasy-gm-dev-secret'),algorithms=['HS256'])['sub'])
 except:raise HTTPException(401,'Your session expired. Please sign in again.')

class Auth(BaseModel):email:EmailStr;password:str=Field(min_length=6);name:str='Fantasy Manager'
class ESPNConnect(BaseModel):league_id:str;team_id:int=9;season:int=2026;espn_s2:Optional[str]=None;swid:Optional[str]=None
class Question(BaseModel):question:str=Field(min_length=1,max_length=4000)

async def espn(req,views=None,period=None,filter_body=None):
 url=f'{ESPN_BASE}/{req.season}/segments/0/leagues/{req.league_id}';views=views or ['mSettings','mTeam','mRoster','mStandings','mMatchup','mStatus','mTransactions'];params=[('view',x) for x in views]
 if period is not None:params.append(('scoringPeriodId',str(period)))
 cookies={}
 if req.espn_s2:cookies['espn_s2']=req.espn_s2.strip()
 if req.swid:cookies['SWID']=req.swid.strip()
 headers={'User-Agent':'Mozilla/5.0 AI-Fantasy-GM','Accept':'application/json'}
 if filter_body:headers['x-fantasy-filter']=json.dumps(filter_body,separators=(',',':'))
 async with httpx.AsyncClient(timeout=25,follow_redirects=True) as c:r=await c.get(url,params=params,cookies=cookies,headers=headers)
 if r.status_code in (401,403):raise HTTPException(502,'ESPN rejected the league credentials. Verify League ID, espn_s2 and SWID.')
 if r.status_code>=400:raise HTTPException(502,f'ESPN returned HTTP {r.status_code}.')
 return r.json()

def current_period(data):
 for obj in [data.get('status') or {},data.get('settings') or {}]:
  for key in ('scoringPeriodId','currentScoringPeriodId','currentScoringPeriod'):
   v=obj.get(key)
   if isinstance(v,dict):v=v.get('id')
   if isinstance(v,int):return v
   if isinstance(v,str) and v.isdigit():return int(v)
 v=data.get('scoringPeriodId');return int(v) if isinstance(v,(int,str)) and str(v).isdigit() else None

def team_name(t):return t.get('name') or t.get('location') or t.get('nickname') or f"Team {t.get('id')}"
def rec(t):return ((t.get('record') or {}).get('overall') or {}) if isinstance(t.get('record'),dict) else {}

def compact_player(e):
 ppe=e.get('playerPoolEntry') or {};p=ppe.get('player') or {};pid=p.get('id') or e.get('playerId');default=p.get('defaultPositionId');slot=e.get('lineupSlotId');inj=p.get('injuryStatus') or e.get('injuryStatus') or ''
 return {'id':pid,'name':p.get('fullName') or f'Player {pid}','position':POS.get(default,'—'),'eligible_positions':[POS[x] for x in (p.get('eligibleSlots') or []) if x in POS],'pro_team_id':p.get('proTeamId'),'injury_status':inj,'injured':p.get('injured',False),'lineup_slot':SLOT.get(slot,'—'),'roster_status':inj or ('BENCH' if slot==12 else 'ACTIVE'),'total_points':ppe.get('totalPoints'),'applied_stat_total':ppe.get('appliedStatTotal'),'percent_owned':ppe.get('percentOwned'),'percent_started':ppe.get('percentStarted')}
def compact_team(t):return {'id':t.get('id'),'name':team_name(t),'location':t.get('location'),'nickname':t.get('nickname'),'record':rec(t),'points':t.get('points'),'projected_rank':t.get('currentProjectedRank'),'standing':t.get('standing'),'logo':t.get('logo'),'roster':[compact_player(e) for e in ((t.get('roster') or {}).get('entries') or [])]}
def summary(data,tid):
 ss=[]
 for t in data.get('teams',[]) or []:
  r=rec(t);ss.append({'id':t.get('id'),'name':team_name(t),'wins':r.get('wins',0),'losses':r.get('losses',0),'ties':r.get('ties',0),'points':t.get('points',0),'projected_rank':t.get('currentProjectedRank')})
 ss.sort(key=lambda x:(x.get('wins',0),x.get('points',0)),reverse=True);rank=next((i+1 for i,x in enumerate(ss) if x['id']==tid),None);return ss,rank

def league_row(u):
 x=db().execute('SELECT * FROM leagues WHERE user_id=? ORDER BY id DESC LIMIT 1',(u,)).fetchone()
 if not x:raise HTTPException(404,'Connect an ESPN league first')
 return x

async def free_players(req,period):
 if period is None:return []
 try:
  filters=[]
  for status in ('FREEAGENT','WAIVERS'):
   filters.append(espn(req,['kona_player_info'],period,{'players':{'filterStatus':{'value':[status]},'limit':500,'sortPercOwned':{'sortPriority':1,'sortAsc':False}}}))
  results=await asyncio.gather(*filters,return_exceptions=True);out={}
  for d in results:
   if isinstance(d,Exception):continue
   for x in d.get('players',[]) or []:
    p=x.get('player') or {};pool=x.get('playerPoolEntry') or {};pid=x.get('id') or p.get('id')
    if not pid:continue
    status=pool.get('status') or x.get('status') or 'FREEAGENT'
    out[pid]={'id':pid,'name':p.get('fullName') or f'Player {pid}','position':POS.get(p.get('defaultPositionId'),'—'),'eligible_positions':[POS.get(v,'—') for v in (p.get('eligibleSlots') or []) if v in POS],'injury_status':p.get('injuryStatus'),'total_points':pool.get('totalPoints'),'percent_owned':pool.get('percentOwned'),'percent_started':pool.get('percentStarted'),'rank':pool.get('rank'),'status':status,'pro_team_id':p.get('proTeamId')}
  return list(out.values())
 except Exception:return []

async def live(u,need_waivers=False):
 l=league_row(u);req=ESPNConnect(league_id=l['league_id'],team_id=l['team_id'],season=l['season'],espn_s2=l['espn_s2'],swid=l['swid'])
 meta=await espn(req,['mSettings','mTeam','mStandings','mStatus']);period=current_period(meta)
 if period is None:raise HTTPException(502,'ESPN did not provide the current scoring period.')
 roster_task=espn(req,['mTeam','mRoster','mStandings','mStatus'],period);waiver_task=free_players(req,period) if need_waivers else None
 if waiver_task is not None:roster_data,waivers=await asyncio.gather(roster_task,waiver_task)
 else:roster_data=await roster_task;waivers=[]
 roster_data['settings']=meta.get('settings') or roster_data.get('settings') or {};roster_data['scoringPeriodId']=period
 c=db();c.execute('UPDATE leagues SET context_json=?,updated_at=? WHERE id=?',(json.dumps(roster_data),datetime.utcnow().isoformat(),l['id']));c.commit()
 return l,req,roster_data,period,waivers

def player_words(name):return set(re.findall(r"[a-z0-9]+",name.lower()))
def relevant_context(question,teams,waivers,my_id):
 q=question.lower();tokens=set(re.findall(r"[a-z0-9]+",q));my=next((t for t in teams if t['id']==my_id),None);opps=[t for t in teams if t['id']!=my_id]
 roster_index=[]
 for t in teams:
  for p in t.get('roster',[]):roster_index.append({'player':p['name'],'team':t['name'],'team_id':t['id'],'position':p.get('position'),'points':p.get('total_points'),'status':p.get('roster_status')})
 trade_words=('trade','target','opponent','other team','manager','offer','who owns','whose team')
 use_all_opps=any(w in q for w in trade_words)
 selected_opps=opps if use_all_opps else []
 # If a player/team is named, include the exact owning team even for non-trade questions.
 for t in opps:
  if any(tok in t['name'].lower() for tok in tokens if len(tok)>2):
   if t not in selected_opps:selected_opps.append(t)
 # Always give the AI an ownership directory, so it can answer "who has Player X?" without guessing.
 ownership=roster_index
 # Keep a large live waiver pool for ranking questions, but always inject exact name matches from the full pool.
 ranked=sorted(waivers,key=lambda p:((p.get('total_points') or 0),(p.get('rank') or 9999),-(p.get('percent_owned') or 0)),reverse=True)
 exact=[]
 for p in waivers:
  words=player_words(p['name'])
  if words and words.intersection(tokens):exact.append(p)
 ws=[];seen=set()
 for p in exact+ranked[:100]:
  if p['id'] not in seen:seen.add(p['id']);ws.append(p)
 return {'my_team':my,'opponent_teams':selected_opps,'player_ownership_index':ownership,'waivers':ws,'waiver_pool_count':len(waivers),'all_opponent_count':len(opps)}

async def ai_call(system,prompt):
 key=os.getenv('OPENROUTER_API_KEY')
 if not key:raise HTTPException(503,'Free AI is not configured. Add OPENROUTER_API_KEY to Render.')
 models=[]
 for m in [OR_MODEL,'openai/gpt-oss-120b:free','openai/gpt-oss-20b:free','nvidia/nemotron-3-nano-30b-a3b:free']:
  if m not in models:models.append(m)
 last='Free AI is temporarily unavailable.'
 async with httpx.AsyncClient(timeout=45,follow_redirects=True) as c:
  for model in models:
   try:
    payload={'model':model,'messages':[{'role':'system','content':system},{'role':'user','content':prompt}],'max_tokens':1400,'temperature':0.12}
    if model=='openrouter/free':payload['reasoning']={'effort':'medium'}
    r=await c.post(OR_BASE,headers={'Authorization':f'Bearer {key}','Content-Type':'application/json','HTTP-Referer':'https://ai-fantasy-gm.onrender.com','X-Title':'AI Fantasy GM'},json=payload)
    if r.status_code>=400:
     try:last=r.json().get('error',{}).get('message') or last
     except:pass
     continue
    body=r.json();choices=body.get('choices') or [];text=(choices[0].get('message',{}).get('content') or '').strip() if choices else ''
    if text and text.lower().strip() not in ('user safety: safe','safe'):return text,body.get('model',model)
    last='The selected model returned a safety classification instead of a baseball answer.'
   except Exception as e:last=str(e)
 raise HTTPException(502,'AI service error: '+last)

app=FastAPI(title='AI Fantasy GM',version='10.0');app.add_middleware(CORSMiddleware,allow_origins=['*'],allow_methods=['*'],allow_headers=['*'])
@app.get('/health')
def health():return {'ok':True,'app':'AI Fantasy GM','version':'10.0','ai_provider':'openrouter-free','ai_configured':bool(os.getenv('OPENROUTER_API_KEY'))}
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
async def connect(req:ESPNConnect,authorization:str=Header(None)):
 u=uid(authorization);meta=await espn(req,['mSettings','mTeam','mStandings','mStatus']);name=(meta.get('settings') or {}).get('name') or 'ESPN Fantasy League';c=db();c.execute('DELETE FROM leagues WHERE user_id=?',(u,));c.execute('INSERT INTO leagues(user_id,league_id,team_id,season,espn_s2,swid,league_name,context_json,updated_at) VALUES(?,?,?,?,?,?,?,?,?)',(u,req.league_id,req.team_id,req.season,req.espn_s2,req.swid,name,json.dumps(meta),datetime.utcnow().isoformat()));c.commit();ss,rank=summary(meta,req.team_id);return {'connected':True,'name':name,'teams':len(ss),'rank':rank,'message':'ESPN league imported successfully.'}
@app.get('/dashboard')
async def dashboard(authorization:str=Header(None)):
 u=uid(authorization);l,req,d,period,_=await live(u);ss,rank=summary(d,l['team_id']);t=next((x for x in d.get('teams',[]) if x.get('id')==l['team_id']),None) or {};return {'league':(d.get('settings') or {}).get('name') or l['league_name'],'rank':rank,'record':rec(t),'team':compact_team(t),'standings':ss,'teams':[compact_team(x) for x in d.get('teams',[]) or []],'status':d.get('status') or {},'scoring_period':period,'live_data':True}
@app.get('/league/teams')
async def teams(authorization:str=Header(None)):
 u=uid(authorization);l,req,d,period,_=await live(u);ss,rank=summary(d,l['team_id']);return {'league':(d.get('settings') or {}).get('name') or l['league_name'],'my_team_id':l['team_id'],'scoring_period':period,'standings':ss,'teams':[compact_team(x) for x in d.get('teams',[]) or []]}
@app.get('/league/teams/{team_id}')
async def team(team_id:int,authorization:str=Header(None)):
 u=uid(authorization);l,req,d,period,_=await live(u);t=next((x for x in d.get('teams',[]) if x.get('id')==team_id),None)
 if not t:raise HTTPException(404,'That team was not found in the league')
 ss,rank=summary(d,team_id);return {'team':compact_team(t),'rank':rank,'scoring_period':period,'standings':ss}
@app.get('/espn/my-team')
async def myteam(authorization:str=Header(None)):return await dashboard(authorization)
@app.get('/espn/waivers')
async def waivers(authorization:str=Header(None)):
 u=uid(authorization);l,req,d,period,players=await live(u,True);players.sort(key=lambda x:((x.get('total_points') or 0),(x.get('rank') or 9999)),reverse=True);return {'scoring_period':period,'players':players,'count':len(players),'live_data':True}
@app.post('/ai/clear')
def clear(authorization:str=Header(None)):
 c=db();c.execute('DELETE FROM ai_messages WHERE user_id=?',(uid(authorization),));c.commit();return {'cleared':True}
@app.post('/ai/gm')
async def gm(q:Question,authorization:str=Header(None)):
 u=uid(authorization);l,req,d,period,waivers=await live(u,True);ss,rank=summary(d,l['team_id']);teams_all=[compact_team(x) for x in d.get('teams',[]) or []];rel=relevant_context(q.question,teams_all,waivers,l['team_id'])
 c=db();rows=c.execute('SELECT role,content FROM ai_messages WHERE user_id=? ORDER BY id DESC LIMIT 8',(u,)).fetchall();history=list(reversed([dict(x) for x in rows]))
 ctx={'league':(d.get('settings') or {}).get('name'),'season':d.get('seasonId',l['season']),'scoring_period':period,'data_timestamp':datetime.utcnow().isoformat(),'standings':ss,'scoring_settings':(d.get('settings') or {}).get('scoringSettings'),'roster_settings':(d.get('settings') or {}).get('rosterSettings'),**rel}
 system='You are AI Fantasy GM, an elite fantasy baseball decision engine. The first job is DATA ACCURACY, the second is analysis. The CURRENT ESPN DATA is authoritative and was fetched immediately before this request. Treat player_ownership_index as the authoritative answer to who owns a player and waivers as the authoritative answer to who is available. A player cannot be both rostered and on waivers. Never invent players, stats, teams, injuries, positions, or availability. Before answering, identify the relevant players in the supplied data and reason from them. For waiver questions, use the live waiver pool first, then compare adds against MY TEAM. For trade questions, use the owning team and that team roster. For lineup questions respect eligibility and roster slots. Apply league scoring and roster settings. Give the recommendation first, then concise evidence. Trades must be ACCEPT, DECLINE, or COUNTER. Waiver advice should name the add and drop when supported. Never output safety classifications, moderation labels, policy text, or User Safety.'
 prompt='CURRENT LIVE ESPN FANTASY BASEBALL DATA:\n'+json.dumps(ctx,separators=(',',':'))+'\nRECENT CONVERSATION:\n'+json.dumps(history,separators=(',',':'))+'\nUSER QUESTION:\n'+q.question
 answer,model=await ai_call(system,prompt);now=datetime.utcnow().isoformat();c.execute('INSERT INTO ai_messages(user_id,role,content,created_at) VALUES(?,?,?,?)',(u,'user',q.question,now));c.execute('INSERT INTO ai_messages(user_id,role,content,created_at) VALUES(?,?,?,?)',(u,'assistant',answer,now));c.commit()
 return {'answer':answer,'context':{'league':ctx['league'],'scoring_period':period,'rank':rank,'my_roster_players':len((rel.get('my_team') or {}).get('roster',[])),'opponent_teams_used':len(rel.get('opponent_teams',[])),'all_opponent_teams':rel.get('all_opponent_count',0),'live_waiver_players_used':len(rel.get('waivers',[])),'live_waiver_pool_count':rel.get('waiver_pool_count',0),'ownership_index_players':len(rel.get('player_ownership_index',[])),'live_data':True,'model':model,'timestamp':now}}
@app.get('/')
def home():return FileResponse(os.path.join(ROOT,'frontend','index.html'))
@app.on_event('startup')
def startup():db().close()
