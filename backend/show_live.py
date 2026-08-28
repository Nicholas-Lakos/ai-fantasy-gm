import asyncio, html, re, time, unicodedata
import httpx

BASE_URL='https://www.theshowbase.com/26/player/{}-live'
SEARCH_URL='https://www.theshowbase.com/players?series=Live&search={}'
CACHE_TTL=3600
_cache={}

def norm(s):
    s=html.unescape(str(s or '')).replace('\xa0',' ')
    s=unicodedata.normalize('NFKD',s).encode('ascii','ignore').decode('ascii').lower()
    return re.sub(r'\s+',' ',re.sub(r'[^a-z0-9 ]','',s)).strip()

def slug(name):
    s=unicodedata.normalize('NFKD',str(name or '')).encode('ascii','ignore').decode('ascii').lower()
    return re.sub(r'[^a-z0-9]+','-',s).strip('-')

def parse_ovr(text):
    patterns=[
        r'\b([5-9]\d|100)\s+OVR\b',
        r'>\s*([5-9]\d|100)\s+OVR\s*<',
        r'"(?:overall|ovr)"\s*:\s*"?([5-9]\d|100)',
    ]
    for pattern in patterns:
        m=re.search(pattern,text,re.I)
        if m:return int(m.group(1))
    return None

def parse_search_result(text,name):
    target=norm(name)
    # The filtered Live Series table puts the player name and OVR in the same
    # result row. Prefer an exact name match so another player is never used.
    compact=re.sub(r'\s+',' ',html.unescape(text))
    patterns=[
        rf'{re.escape(name)}.{{0,900}}?(\d{{2,3}})\s+OVR',
        rf'{re.escape(name)}.{{0,900}}?Overall.{{0,80}}?(\d{{2,3}})',
    ]
    for pattern in patterns:
        m=re.search(pattern,compact,re.I|re.S)
        if m:
            o=int(m.group(1))
            if 50<=o<=100:return o
    # Fall back to nearby text around a normalized exact-name occurrence.
    low=compact.lower(); needle=str(name).lower()
    pos=low.find(needle)
    if pos>=0:
        o=parse_ovr(compact[pos:pos+1400])
        if o is not None:return o
    return None

async def _fetch_one(client,name,sem,force=False):
    key=norm(name); now=time.time()
    cached=_cache.get(key)
    if not force and cached and now-cached['at'] < CACHE_TTL:
        return cached['row']
    if not key:return None
    async with sem:
        headers={
            'User-Agent':'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/147.0 Safari/537.36',
            'Accept':'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language':'en-US,en;q=0.9',
            'Referer':'https://www.theshowbase.com/players?series=Live',
        }
        try:
            # First try the exact card URL.
            url=BASE_URL.format(slug(name))
            r=await client.get(url,headers=headers,timeout=15)
            if r.status_code == 200:
                ovr=parse_ovr(r.text)
                if ovr is not None:
                    row={'name':name,'overall':ovr,'source':'theSHOWBASE Live Series','url':url}
                    _cache[key]={'at':now,'row':row}
                    return row
        except Exception:
            pass
        try:
            # Fallback: use the site's filtered Live Series database. This only
            # retrieves the matching search results, not the full 2,036-card set.
            from urllib.parse import quote_plus
            url=SEARCH_URL.format(quote_plus(name))
            r=await client.get(url,headers=headers,timeout=15)
            if r.status_code != 200:return None
            ovr=parse_search_result(r.text,name)
            if ovr is None:return None
            row={'name':name,'overall':ovr,'source':'theSHOWBASE Live Series','url':url}
            _cache[key]={'at':now,'row':row}
            return row
        except Exception:
            return None

async def live_ratings_for_names(names,force=False):
    unique=[];seen=set()
    for name in names or []:
        k=norm(name)
        if k and k not in seen:
            seen.add(k);unique.append(name)
    sem=asyncio.Semaphore(5)
    async with httpx.AsyncClient(follow_redirects=True) as client:
        rows=await asyncio.gather(*[_fetch_one(client,n,sem,force) for n in unique])
    rows=[r for r in rows if r]
    return {'source':'theSHOWBASE Live Series','game':'MLB The Show 26','league_players':len(unique),'matched_players':len(rows),'updated_at':time.time(),'players':rows}

async def live_ratings(force=False):
    return {'source':'theSHOWBASE Live Series','game':'MLB The Show 26','count':0,'updated_at':0,'players':[]}
