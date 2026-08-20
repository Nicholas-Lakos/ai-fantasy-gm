import os, sqlite3, hashlib, secrets, json, hmac
from datetime import datetime, timedelta
from typing import Optional
import httpx, jwt
from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field

BASE= os.path.dirname(os.path.abspath(__file__))
ROOT= os.path.dirname(BASE)
DB=os.getenv("DATABASE_PATH", os.path.join(BASE,"fantasy_gm.db"))
SECRET_FILE=os.path.join(BASE,".jwt_secret")
def load_secret():
    env=os.getenv("JWT_SECRET")
    if env: return env
    try:
        with open(SECRET_FILE,"r") as f: return f.read().strip()
    except FileNotFoundError:
        value=secrets.token_urlsafe(48)
        try:
            with open(SECRET_FILE,"w") as f: f.write(value)
            try: os.chmod(SECRET_FILE,0o600)
            except OSError: pass
        except OSError: pass
        return value
JWT_SECRET=load_secret()
ESPN_BASE="https://lm-api-reads.fantasy.espn.com/apis/v3/games/flb/seasons"

app=FastAPI(title="AI Fantasy GM", version="2.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def db():
    c=sqlite3.connect(DB, timeout=10); c.row_factory=sqlite3.Row
    c.execute("CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT,email TEXT UNIQUE NOT NULL,password_hash TEXT NOT NULL,name TEXT NOT NULL)")
    c.execute("CREATE TABLE IF NOT EXISTS leagues(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,league_id TEXT NOT NULL,team_id INTEGER NOT NULL,season INTEGER NOT NULL,espn_s2 TEXT,swid TEXT,league_name TEXT,context_json TEXT,updated_at TEXT)")
    c.commit(); return c

def pw_hash(p, salt=None):
    salt=salt or secrets.token_hex(16)
    digest=hashlib.pbkdf2_hmac("sha256",p.encode(),salt.encode(),210000).hex()
    return f"pbkdf2$210000${salt}${digest}"
def pw_verify(p, stored):
    if stored.startswith("pbkdf2$"):
        try:
            _,iters,salt,digest=stored.split("$",3)
            got=hashlib.pbkdf2_hmac("sha256",p.encode(),salt.encode(),int(iters)).hex()
            return hmac.compare_digest(got,digest)
        except Exception: return False
    return hmac.compare_digest(stored, hashlib.sha256(("ai-gm:"+p).encode()).hexdigest())
def make_token(uid): return jwt.encode({"sub":str(uid),"exp":datetime.utcnow()+timedelta(days=14)},JWT_SECRET,algorithm="HS256")
def auth_user(auth):
    if not auth or not auth.startswith("Bearer "): raise HTTPException(401,"Please sign in first")
    try: return int(jwt.decode(auth[7:],JWT_SECRET,algorithms=["HS256"])["sub"])
    except Exception: raise HTTPException(401,"Your session expired. Please sign in again.")

class Auth(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    name: str = "Fantasy Manager"
class ESPNConnect(BaseModel):
    league_id: str
    team_id: int = 9
    season: int = 2026
    espn_s2: Optional[str] = None
    swid: Optional[str] = None
class Question(BaseModel): question: str = Field(min_length=1, max_length=2000)

async def espn(req):
    url=f"{ESPN_BASE}/{req.season}/segments/0/leagues/{req.league_id}"
    params=[("view",v) for v in ["mSettings","mTeam","mRoster","mStandings","mMatchup","mStatus","mTransactions"]]
    cookies={}
    if req.espn_s2: cookies["espn_s2"]=req.espn_s2.strip()
    if req.swid: cookies["SWID"]=req.swid.strip()
    headers={"User-Agent":"Mozilla/5.0 AI-Fantasy-GM","Accept":"application/json"}
    async with httpx.AsyncClient(timeout=30,follow_redirects=True) as c:
        r=await c.get(url,params=params,cookies=cookies,headers=headers)
    if r.status_code in (401,403): raise HTTPException(502,"ESPN requires valid private-league cookies (espn_s2 and SWID). Check them and try again.")
    if r.status_code>=400: raise HTTPException(502,f"ESPN returned HTTP {r.status_code}. Verify the league ID and season.")
    try: return r.json()
    except: raise HTTPException(502,"ESPN returned an unexpected response.")

def save_context(uid, req, data):
    settings=data.get("settings") or {}; name=settings.get("name") or "ESPN Fantasy League"
    c=db(); c.execute("DELETE FROM leagues WHERE user_id=?",(uid,)); c.execute("INSERT INTO leagues(user_id,league_id,team_id,season,espn_s2,swid,league_name,context_json,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",(uid,req.league_id,req.team_id,req.season,req.espn_s2,req.swid,name,json.dumps(data),datetime.utcnow().isoformat())); c.commit()
    return name

def league_for(uid):
    c=db(); l=c.execute("SELECT * FROM leagues WHERE user_id=? ORDER BY id DESC LIMIT 1",(uid,)).fetchone()
    if not l: raise HTTPException(404,"Connect an ESPN league first")
    return l

def team_from(data, team_id):
    for t in data.get("teams",[]) or []:
        if t.get("id")==team_id: return t
    return None

def summary(data, team_id):
    teams=data.get("teams",[]) or []; t=team_from(data,team_id)
    standings=[]
    for x in teams:
        rec=x.get("record",{}).get("overall",{}) if isinstance(x.get("record"),dict) else {}
        standings.append({"id":x.get("id"),"name":x.get("name") or x.get("location") or f"Team {x.get('id')}","wins":rec.get("wins"),"losses":rec.get("losses"),"ties":rec.get("ties"),"points":x.get("points")})
    standings=sorted(standings,key=lambda x: ((x.get("wins") or 0), (x.get("points") or 0)), reverse=True)
    rank=next((i+1 for i,x in enumerate(standings) if x["id"]==team_id),None)
    return {"team":t,"rank":rank,"standings":standings,"league_name":(data.get("settings") or {}).get("name","ESPN Fantasy League"),"status":data.get("status") or {}}

@app.get("/health")
def health(): return {"ok":True,"app":"AI Fantasy GM","version":"2.0"}

@app.post("/auth/signup")
def signup(a:Auth):
    if len(a.password)<6: raise HTTPException(400,"Password must be at least 6 characters")
    if not a.email.strip(): raise HTTPException(400,"Email is required")
    c=db()
    try:
        cur=c.execute("INSERT INTO users(email,password_hash,name) VALUES(?,?,?)",(a.email.lower(),pw_hash(a.password),a.name.strip() or "Fantasy Manager")); c.commit()
    except sqlite3.IntegrityError: raise HTTPException(409,"That email is already registered")
    return {"token":make_token(cur.lastrowid),"user":{"id":cur.lastrowid,"email":a.email.lower(),"name":a.name}}

@app.post("/auth/login")
def login(a:Auth):
    if len(a.password)<1: raise HTTPException(400,"Password is required")
    c=db(); u=c.execute("SELECT * FROM users WHERE email=?",(a.email.lower(),)).fetchone()
    if not u or not pw_verify(a.password,u["password_hash"]): raise HTTPException(401,"Invalid email or password")
    if not u["password_hash"].startswith("pbkdf2$"):
        c.execute("UPDATE users SET password_hash=? WHERE id=?",(pw_hash(a.password),u["id"])); c.commit()
    return {"token":make_token(u["id"]),"user":{"id":u["id"],"email":u["email"],"name":u["name"]}}

@app.get("/auth/me")
def me(authorization:str=Header(None)):
    uid=auth_user(authorization); c=db(); u=c.execute("SELECT id,email,name FROM users WHERE id=?",(uid,)).fetchone()
    return {"user":dict(u)}

@app.get("/espn/connection")
def connection(authorization:str=Header(None)):
    uid=auth_user(authorization); l=league_for(uid)
    return {"connected":True,"league_id":l["league_id"],"team_id":l["team_id"],"season":l["season"],"league_name":l["league_name"],"updated_at":l["updated_at"],"has_private_credentials":bool(l["espn_s2"] and l["swid"])}

@app.post("/espn/connect")
async def connect(req:ESPNConnect, authorization:str=Header(None)):
    uid=auth_user(authorization)
    if not req.league_id.strip(): raise HTTPException(400,"League ID is required")
    data=await espn(req)
    name=save_context(uid,req,data); s=summary(data,req.team_id)
    return {"connected":True,"league_id":req.league_id,"team_id":req.team_id,"season":req.season,"name":name,"rank":s["rank"],"teams":len(s["standings"]),"message":"ESPN league imported successfully."}

@app.get("/dashboard")
async def dashboard(authorization:str=Header(None)):
    uid=auth_user(authorization); l=league_for(uid)
    req=ESPNConnect(league_id=l["league_id"],team_id=l["team_id"],season=l["season"],espn_s2=l["espn_s2"],swid=l["swid"])
    data=await espn(req); s=summary(data,l["team_id"])
    t=s["team"] or {}; rec=(t.get("record") or {}).get("overall") if isinstance(t.get("record"),dict) else {}
    return {"league":s["league_name"],"rank":s["rank"],"record":rec or {},"team":t,"standings":s["standings"],"status":s["status"]}

@app.get("/espn/my-team")
async def my_team(authorization:str=Header(None)): return await dashboard(authorization)

@app.post("/ai/gm")
async def gm(q:Question,authorization:str=Header(None)):
    uid=auth_user(authorization); l=league_for(uid)
    c=db(); data=json.loads(l["context_json"] or "{}")
    s=summary(data,l["team_id"]); t=s["team"] or {}; rec=(t.get("record") or {}).get("overall") if isinstance(t.get("record"),dict) else {}
    text=q.question.lower()
    if any(w in text for w in ["trade","deal"]): answer=f"I’d evaluate this trade against your current roster and league scoring. You are currently around rank {s['rank'] or '—'} with {rec.get('wins','—')}-{rec.get('losses','—')}. Send me the two sides of the trade and I’ll break down roster fit, value, and risk."
    elif any(w in text for w in ["waiver","pickup","free agent"]): answer="Tell me the available players (or ask for waiver priorities). I’ll focus on playing time, projected value, roster fit, and replacement value rather than generic rankings."
    elif any(w in text for w in ["start","lineup","bench"]): answer="I can help set your lineup. Give me the players you’re deciding between and I’ll prioritize current role, schedule, matchup, eligibility, and your league scoring."
    else: answer=f"Your league context is loaded for {s['league_name']}. Ask me about a trade, waiver pickup, lineup decision, or roster weakness and I’ll use your ESPN team context."
    return {"answer":answer,"context":{"league":s["league_name"],"rank":s["rank"],"record":rec}}

@app.get("/", include_in_schema=False)
def home(): return FileResponse(os.path.join(ROOT,"frontend","index.html"))

@app.on_event("startup")
def startup(): db().close()
