import asyncio, html, re, time, unicodedata
import httpx

SHOWDD_BASE='https://www.showdd.io/series/live?page={}'
THESHOWBASE_BASE='https://www.theshowbase.com/26/player/{}-live'
CACHE_TTL=21600
_catalog={}
_catalog_at=0.0

def norm(s):
    s=html.unescape(str(s or '')).replace('\xa0',' ')
    s=unicodedata.normalize('NFKD',s).encode('ascii','ignore').decode('ascii').lower()
    return re.sub(r'\s+',' ',re.sub(r'[^a-z0-9 ]','',s)).strip()

def slug(name):
    s=unicodedata.normalize('NFKD',str(name or '')).encode('ascii','ignore').decode('ascii').lower()
    return re.sub(r'[^a-z0-9]+','-',s).strip('-')

def parse_showdd_page(text):
    found={}
    pattern=re.compile(r'(?:alt|title)=[\"\']([^\"\']+?),\s*(\d{2,3})\s+Live\s*-\s*MLB\s+the\s+Show\s+26',re.I)
    for m in pattern.finditer(text or ''):
        name=html.unescape(m.group(1)).strip()
        try:o=int(m.group(2))
        except ValueError:continue
        if name and 40<=o<=99:found[norm(name)]={'name':name,'overall':o,'source':'showdd.io Live Series'}
    return found

async def _catalog_for_names(names):
    global _catalog,_catalog_at
    requested={norm(n) for n in names if norm(n)}
    if not requested:return {}
    now=time.time()
    if _catalog and now-_catalog_at<CACHE_TTL:
        return {k:_catalog[k] for k in requested if k in _catalog}
    headers={'User-Agent':'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/147.0 Safari/537.36','Accept':'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8','Accept-Language':'en-US,en;q=0.9'}
    sem=asyncio.Semaphore(10)
    found={}
    async def fetch_page(client,page):
        async with sem:
            try:
                r=await client.get(SHOWDD_BASE.format(page),headers=headers,timeout=20)
                if r.status_code!=200:return {}
                return parse_showdd_page(r.text)
            except Exception:return {}
    async with httpx.AsyncClient(follow_redirects=True) as client:
        for start in range(1,103,10):
            results=await asyncio.gather(*[fetch_page(client,p) for p in range(start,min(start+10,103))])
            for result in results:found.update(result)
            if requested.issubset(found.keys()):break
    _catalog.update(found);_catalog_at=time.time()
    return {k:_catalog[k] for k in requested if k in _catalog}

async def _fallback(client,name,sem):
    async with sem:
        try:
            url=THESHOWBASE_BASE.format(slug(name))
            headers={'User-Agent':'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/147.0 Safari/537.36','Accept':'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'}
            r=await client.get(url,headers=headers,timeout=20)
            if r.status_code!=200:return None
            m=re.search(r'\b(\d{2,3})\s+OVR\b',html.unescape(r.text),re.I)
            if not m:return None
            o=int(m.group(1))
            if not 40<=o<=99:return None
            return {'name':name,'overall':o,'source':'theSHOWBASE Live Series','url':url}
        except Exception:return None

async def live_ratings_for_names(names,force=False):
    unique=[];seen=set()
    for name in names or []:
        clean=' '.join(str(name or '').split()).strip();k=norm(clean)
        if k and k not in seen:seen.add(k);unique.append(clean)
    if not unique:return {'source':'showdd.io Live Series','game':'MLB The Show 26','league_players':0,'matched_players':0,'updated_at':time.time(),'players':[]}
    if force:
        global _catalog_at
        _catalog_at=0
    catalog=await _catalog_for_names(unique)
    rows=[dict(catalog[norm(n)],name=n) for n in unique if norm(n) in catalog]
    missing=[n for n in unique if norm(n) not in catalog]
    if missing:
        sem=asyncio.Semaphore(5)
        async with httpx.AsyncClient(follow_redirects=True) as client:
            fallback=await asyncio.gather(*[_fallback(client,n,sem) for n in missing])
        rows.extend(r for r in fallback if r)
    return {'source':'showdd.io Live Series','game':'MLB The Show 26','league_players':len(unique),'matched_players':len(rows),'updated_at':time.time(),'players':rows}

async def live_ratings(force=False):
    return {'source':'showdd.io Live Series','game':'MLB The Show 26','count':0,'updated_at':time.time(),'players':[]}

# ESPN league scoring patch. ESPN's roster data contains the league's season
# fantasy totals and averages; keep those values attached to each roster entry.
def _install_league_scoring_patch():
    import sys
    main=sys.modules.get('backend.main') or sys.modules.get('main')
    if not main or getattr(main,'_league_scoring_patch_installed',False):
        return
    original_live=main.live
    original_compact_player=main.compact_player

    def patched_compact_player(entry):
        result=original_compact_player(entry)
        ppe=entry.get('playerPoolEntry') or {}
        avg=ppe.get('seasonAverage')
        # Fallback: read the season average directly from ESPN's roster/player
        # stats. This is the same value displayed by ESPN's Fantasy Pts AVG.
        if avg is None:
            stats=ppe.get('stats') or []
            averages=[]
            for s in stats:
                if s.get('seasonId') != getattr(entry.get('playerPoolEntry') or {}, '_season', s.get('seasonId')):
                    pass
                source=s.get('statSourceId',s.get('statTypeId'))
                split=s.get('statSplitTypeId')
                if source not in (0,'0') or split not in (None,0,'0'):
                    continue
                value=s.get('appliedAverage')
                if value is not None:
                    try: averages.append(float(value))
                    except (TypeError,ValueError): pass
            if averages:
                avg=averages[-1]
        if avg is not None:
            try: result['season_average']=float(avg)
            except (TypeError,ValueError): pass
        return result

    main.compact_player=patched_compact_player

    async def enrich(req, data, scoring_period):
        entries=[]
        for team in data.get('teams',[]) or []:
            entries.extend((team.get('roster') or {}).get('entries',[]) or [])
        ids=[]
        for entry in entries:
            pid=entry.get('playerId') or (entry.get('playerPoolEntry') or {}).get('id')
            if pid and int(pid) not in ids: ids.append(int(pid))
        if not ids:return data
        filters={'players':{'filterIds':{'value':ids},'filterStatsForTopScoringPeriodIds':{'value':max(int(scoring_period or 1),1),'additionalValue':[f'00{req.season}',f'10{req.season}']}}}
        try:payload=await main.espn(req,['kona_playercard'],scoring_period,filters,timeout=35)
        except Exception:return data
        by_id={};avg_by_id={}
        for item in payload.get('players',[]) or []:
            pid=item.get('id') or (item.get('player') or {}).get('id')
            if not pid:continue
            pe=item.get('playerPoolEntry') or {}
            stats=pe.get('stats') or (item.get('player') or {}).get('stats') or []
            candidates=[];averages=[]
            for s in stats:
                if s.get('seasonId')!=req.season:continue
                source=s.get('statSourceId',s.get('statTypeId'));split=s.get('statSplitTypeId')
                if source not in (0,'0') or split not in (None,0,'0'):continue
                val=s.get('appliedTotal')
                if val is not None:
                    try:candidates.append(float(val))
                    except (TypeError,ValueError):pass
                avg=s.get('appliedAverage')
                if avg is not None:
                    try:averages.append(float(avg))
                    except (TypeError,ValueError):pass
            if candidates:by_id[int(pid)]=candidates[-1]
            if averages:avg_by_id[int(pid)]=averages[-1]
        for entry in entries:
            pid=entry.get('playerId') or (entry.get('playerPoolEntry') or {}).get('id')
            if pid is None:continue
            pid=int(pid);pe=entry.get('playerPoolEntry') or {}
            if pid in by_id:pe['totalPoints']=by_id[pid]
            if pid in avg_by_id:pe['seasonAverage']=avg_by_id[pid]
            entry['playerPoolEntry']=pe
        return data

    async def patched_live(u,waivers=False):
        result=await original_live(u,waivers)
        league_row,req,data,p,w=result
        data=await enrich(req,data,p)
        return league_row,req,data,p,w
    main.live=patched_live
    main._league_scoring_patch_installed=True

_install_league_scoring_patch()
