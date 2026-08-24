import asyncio, html, re, time
from html.parser import HTMLParser
import httpx

BASE_URL='https://www.theshowbase.com/series/live'
CACHE_TTL=21600
_cache={'at':0.0,'players':[]}

class RowParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True); self.rows=[]; self.in_tr=False; self.in_td=False; self.cells=[]; self.buf=[]
    def handle_starttag(self,tag,attrs):
        if tag=='tr': self.in_tr=True; self.cells=[]
        elif tag=='td' and self.in_tr: self.in_td=True; self.buf=[]
    def handle_endtag(self,tag):
        if tag=='td' and self.in_td:
            self.cells.append(' '.join(''.join(self.buf).split())); self.in_td=False
        elif tag=='tr' and self.in_tr:
            if self.cells:self.rows.append(self.cells)
            self.in_tr=False
    def handle_data(self,data):
        if self.in_td:self.buf.append(data)

def norm(s):
    s=html.unescape(str(s or '')).replace('\xa0',' ')
    s=re.sub(r'[^A-Za-z0-9 .\'’\-]+','',s).lower()
    s=re.sub(r'\s+',' ',s).strip()
    return s

def parse_page(text):
    p=RowParser();p.feed(text);out=[]
    for cells in p.rows:
        # TheSHOWBASE's ratings table is Name / OVR / Meta / Position ...
        for i,c in enumerate(cells):
            if re.fullmatch(r'\d{1,2}',c or '') and 40 <= int(c) <= 99 and i>0:
                name=cells[i-1].strip()
                if name and len(name)>1 and not re.fullmatch(r'\d+',name):
                    out.append({'name':html.unescape(name),'overall':int(c)})
                break
    return out

async def _fetch_page(client,page):
    r=await client.get(BASE_URL,params={'page':page},headers={'User-Agent':'AI-Fantasy-GM/1.0','Accept':'text/html'},timeout=30)
    r.raise_for_status();return parse_page(r.text)

async def load_live(force=False):
    now=time.time()
    if not force and _cache['players'] and now-_cache['at'] < CACHE_TTL:return _cache['players']
    async with httpx.AsyncClient(follow_redirects=True) as c:
        pages=await asyncio.gather(*[_fetch_page(c,p) for p in range(1,42)],return_exceptions=True)
    merged={}
    for rows in pages:
        if isinstance(rows,Exception):continue
        for x in rows:
            k=norm(x['name'])
            if k: merged[k]=x
    players=list(merged.values())
    if players:
        _cache.update(at=now,players=players)
    return players

async def live_ratings(force=False):
    players=await load_live(force)
    return {'source':'theSHOWBASE Live Series','game':'MLB The Show 26','count':len(players),'updated_at':_cache['at'],'players':players}
