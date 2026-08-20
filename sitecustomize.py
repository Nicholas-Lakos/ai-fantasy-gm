"""Live MLB enrichment for the AI Fantasy GM.
Loaded automatically by Python from the application root. It enriches the existing
OpenRouter prompt with current MLB stats, recent news, and team-needs profiles.
"""
import asyncio, datetime, json, re
try:
    import httpx
except Exception:
    httpx = None

_ORIGINAL_POST = None


def _names_from_prompt(prompt):
    try:
        marker = 'LIVE ESPN DATA:\n'
        if marker not in prompt:
            return []
        raw = prompt.split(marker, 1)[1].split('\nRECENT CHAT:', 1)[0]
        data = json.loads(raw)
        names = []
        seen = set()
        def add(v):
            if not v or not isinstance(v, str): return
            v = v.strip()
            if len(v) < 4 or v in seen: return
            seen.add(v); names.append(v)
        for p in (data.get('my_team') or {}).get('roster', []): add(p.get('name'))
        for t in data.get('opponent_teams', []):
            for p in t.get('roster', []): add(p.get('name'))
        for p in data.get('live_waivers', []): add(p.get('name'))
        return names
    except Exception:
        return []


def _team_profiles(data):
    teams = data.get('opponent_teams') or []
    if not teams: return []
    position_values = {}
    profiles = []
    for t in teams:
        roster = t.get('roster') or []
        buckets = {}
        for p in roster:
            pos = p.get('position') or 'UTIL'
            buckets.setdefault(pos, []).append(p.get('total_points') or 0)
            position_values.setdefault(pos, []).append(p.get('total_points') or 0)
        avg = {k: round(sum(v)/len(v), 1) for k, v in position_values.items() if v}
        team_avg = sum(avg.values()) / max(1, len(avg))
        strengths = sorted(((k, v) for k, v in avg.items() if v >= team_avg), key=lambda x:x[1], reverse=True)[:3]
        weaknesses = sorted(((k, v) for k, v in avg.items() if v < team_avg), key=lambda x:x[1])[:3]
        profiles.append({
            'team_id': t.get('id'), 'team': t.get('name'),
            'record': t.get('record'), 'roster_size': len(roster),
            'top_players': sorted([{'name':p.get('name'),'position':p.get('position'),'points':p.get('total_points') or 0} for p in roster], key=lambda x:x['points'], reverse=True)[:6],
            'position_depth': {k: len(v) for k,v in buckets.items()},
            'strengths': [k for k,_ in strengths], 'relative_weaknesses': [k for k,_ in weaknesses]
        })
    return profiles


async def _get_json(client, url, params=None, timeout=8):
    try:
        r = await client.get(url, params=params, timeout=timeout)
        if r.status_code < 400:
            return r.json()
    except Exception:
        pass
    return None


async def _enrich(prompt):
    if not httpx or 'LIVE ESPN DATA:' not in prompt:
        return prompt
    names = _names_from_prompt(prompt)
    # Keep enrichment fast: prioritize players explicitly mentioned, then the most
    # useful roster/waiver names. The fantasy points/rosters themselves remain live ESPN data.
    question = prompt.split('\nQUESTION:\n',1)[-1].lower()
    tokens = set(re.findall(r'[a-z0-9]+', question))
    ranked = sorted(names, key=lambda n: (len(tokens.intersection(set(re.findall(r'[a-z0-9]+', n.lower())))), n), reverse=True)
    names = ranked[:24]
    today = datetime.date.today()
    start = today - datetime.timedelta(days=7)
    async with httpx.AsyncClient(headers={'User-Agent':'AI-Fantasy-GM/1.0','Accept':'application/json'}, follow_redirects=True) as client:
        # ESPN's public Now API provides a current news feed without another paid key.
        news_task = _get_json(client, 'https://now.core.api.espn.com/v1/sports/news', {'limit':200})
        # MLB Stats API is public and gives current-season MLB performance data.
        search_tasks = [_get_json(client, 'https://statsapi.mlb.com/api/v1/people/search', {'names':n}) for n in names]
        news, people = await asyncio.gather(news_task, asyncio.gather(*search_tasks))
        news_items = (news or {}).get('articles') or (news or {}).get('feed') or []
        recent_news = []
        for item in news_items:
            title = item.get('headline') or item.get('title') or ''
            desc = item.get('description') or ''
            blob = (title + ' ' + desc).lower()
            matched = [n for n in names if n.lower() in blob]
            if matched:
                recent_news.append({'players':matched[:3], 'headline':title, 'description':desc[:400], 'published':item.get('published') or item.get('publishedDate'), 'link':item.get('links',{}).get('web',{}).get('href') if isinstance(item.get('links'),dict) else None})
        recent_news = recent_news[:60]
        stats = []
        for name, result in zip(names, people):
            plist = (result or {}).get('people') or []
            if not plist: continue
            pid = plist[0].get('id')
            if not pid: continue
            season_url = f'https://statsapi.mlb.com/api/v1/people/{pid}/stats'
            split_url = f'https://statsapi.mlb.com/api/v1/people/{pid}/stats'
            season, recent = await asyncio.gather(
                _get_json(client, season_url, {'stats':'season','group':'hitting,pitching','season':str(today.year)}),
                _get_json(client, split_url, {'stats':'byDateRange','group':'hitting,pitching','startDate':start.isoformat(),'endDate':today.isoformat()})
            )
            stat_rows=[]
            for payload,label in ((season,'season'),(recent,'last_7_days')):
                for split in (payload or {}).get('stats',[]) or []:
                    for s in split.get('splits',[]) or []:
                        stat=s.get('stat') or {}
                        stat_rows.append({'period':label,'group':split.get('group',''),'games':stat.get('gamesPlayed'),'avg':stat.get('avg'),'obp':stat.get('obp'),'slg':stat.get('slg'),'ops':stat.get('ops'),'hr':stat.get('homeRuns'),'rbi':stat.get('rbi'),'runs':stat.get('runs'),'sb':stat.get('stolenBases'),'era':stat.get('era'),'whip':stat.get('whip'),'wins':stat.get('wins'),'losses':stat.get('losses'),'strikeouts':stat.get('strikeOuts'),'saves':stat.get('saves'),'innings':stat.get('inningsPitched')})
            if stat_rows: stats.append({'name':name,'mlbam_id':pid,'stats':stat_rows})
        try:
            data = json.loads(prompt.split('LIVE ESPN DATA:\n',1)[1].split('\nRECENT CHAT:',1)[0])
            data['live_mlb_enrichment'] = {'retrieved_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(), 'recent_news':recent_news, 'mlb_stats':stats, 'team_strategy_profiles':_team_profiles(data), 'news_window_days':7}
            before, rest = prompt.split('LIVE ESPN DATA:\n',1)
            rest_data, after = rest.split('\nRECENT CHAT:',1)
            return before + 'LIVE ESPN DATA:\n' + json.dumps(data,separators=(',',':')) + '\nRECENT CHAT:' + after
        except Exception:
            return prompt


def _patch():
    global _ORIGINAL_POST
    if not httpx or _ORIGINAL_POST is not None: return
    _ORIGINAL_POST = httpx.AsyncClient.post
    async def post(self, url, *args, **kwargs):
        if 'openrouter.ai/api/v1/chat/completions' in str(url):
            try:
                body = kwargs.get('json')
                if isinstance(body, dict) and body.get('messages'):
                    for msg in body['messages']:
                        if msg.get('role') == 'user' and isinstance(msg.get('content'), str) and 'LIVE ESPN DATA:' in msg['content']:
                            msg['content'] = await _enrich(msg['content'])
                            break
                    kwargs['json'] = body
            except Exception:
                pass
        return await _ORIGINAL_POST(self, url, *args, **kwargs)
    httpx.AsyncClient.post = post

_patch()
