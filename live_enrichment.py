"""Fast, explicit live MLB enrichment for AI Fantasy GM.
Loaded before the FastAPI app starts. Adds current MLB stats/news and per-team roster needs
without changing the existing ESPN data pipeline or requiring another paid API key.
"""
import asyncio
import datetime as dt
import json
import re
import httpx

_ORIGINAL_POST = httpx.AsyncClient.post


def _extract_data(prompt):
    try:
        raw = prompt.split("LIVE ESPN DATA:\n", 1)[1].split("\nRECENT CHAT:", 1)[0]
        return json.loads(raw)
    except Exception:
        return None


def _tokens(text):
    return set(re.findall(r"[a-z0-9]+", (text or "").lower()))


def _team_profiles(data):
    profiles = []
    for team in data.get("opponent_teams", []) or []:
        roster = team.get("roster", []) or []
        by_pos = {}
        for p in roster:
            pos = p.get("position") or "UTIL"
            by_pos.setdefault(pos, []).append(float(p.get("total_points") or 0))
        depth = {pos: len(vals) for pos, vals in by_pos.items()}
        avg = {pos: round(sum(vals) / len(vals), 1) for pos, vals in by_pos.items() if vals}
        ranked = sorted(avg.items(), key=lambda x: x[1], reverse=True)
        strengths = [x[0] for x in ranked[:3]]
        weaknesses = [x[0] for x in sorted(avg.items(), key=lambda x: x[1])[:3]]
        profiles.append({
            "team_id": team.get("id"),
            "team": team.get("name"),
            "record": team.get("record"),
            "points": team.get("points", 0),
            "roster_size": len(roster),
            "top_players": sorted([
                {"name": p.get("name"), "position": p.get("position"), "points": p.get("total_points") or 0}
                for p in roster
            ], key=lambda x: x["points"], reverse=True)[:8],
            "position_depth": depth,
            "position_points_avg": avg,
            "strengths": strengths,
            "relative_weaknesses": weaknesses,
        })
    return profiles


def _candidate_names(data, question):
    names = []
    seen = set()
    def add(name):
        if not name or not isinstance(name, str):
            return
        name = name.strip()
        if len(name) < 4 or name in seen:
            return
        seen.add(name); names.append(name)
    for p in (data.get("my_team") or {}).get("roster", []): add(p.get("name"))
    for team in data.get("opponent_teams", []) or []:
        for p in team.get("roster", [])[:10]: add(p.get("name"))
    for p in (data.get("live_waivers") or [])[:40]: add(p.get("name"))
    q = _tokens(question)
    return sorted(names, key=lambda n: (len(q & _tokens(n)), n), reverse=True)[:16]


async def _get(client, url, params=None, timeout=6):
    try:
        r = await client.get(url, params=params, timeout=timeout)
        if r.status_code < 400:
            return r.json()
    except Exception:
        return None
    return None


async def _enrich(prompt):
    data = _extract_data(prompt)
    if not data:
        return prompt
    question = prompt.split("\nQUESTION:\n", 1)[-1]
    names = _candidate_names(data, question)
    today = dt.date.today()
    start = today - dt.timedelta(days=7)
    async with httpx.AsyncClient(headers={"User-Agent": "AI-Fantasy-GM/2.0", "Accept": "application/json"}, follow_redirects=True) as client:
        news_task = _get(client, "https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/news", {"limit": 100}, 6)
        people_tasks = [_get(client, "https://statsapi.mlb.com/api/v1/people/search", {"names": n}, 5) for n in names]
        news, people_results = await asyncio.gather(news_task, asyncio.gather(*people_tasks))

        ids = []
        for name, result in zip(names, people_results):
            people = (result or {}).get("people") or []
            if people and people[0].get("id"):
                ids.append((name, people[0]["id"]))

        async def stats_for(name, pid):
            base = f"https://statsapi.mlb.com/api/v1/people/{pid}/stats"
            season_task = _get(client, base, {"stats": "season", "group": "hitting,pitching", "season": str(today.year)}, 6)
            recent_task = _get(client, base, {"stats": "byDateRange", "group": "hitting,pitching", "startDate": start.isoformat(), "endDate": today.isoformat()}, 6)
            season, recent = await asyncio.gather(season_task, recent_task)
            rows = []
            for payload, label in ((season, "season"), (recent, "last_7_days")):
                for group in (payload or {}).get("stats", []) or []:
                    for split in group.get("splits", []) or []:
                        s = split.get("stat") or {}
                        rows.append({
                            "period": label, "group": group.get("group"), "games": s.get("gamesPlayed"),
                            "avg": s.get("avg"), "obp": s.get("obp"), "slg": s.get("slg"), "ops": s.get("ops"),
                            "hr": s.get("homeRuns"), "rbi": s.get("rbi"), "runs": s.get("runs"), "sb": s.get("stolenBases"),
                            "era": s.get("era"), "whip": s.get("whip"), "wins": s.get("wins"), "losses": s.get("losses"),
                            "strikeouts": s.get("strikeOuts"), "saves": s.get("saves"), "innings": s.get("inningsPitched")
                        })
            return {"name": name, "mlbam_id": pid, "stats": rows}

        stats = await asyncio.gather(*[stats_for(n, pid) for n, pid in ids])
        articles = (news or {}).get("articles") or []
        recent_news = []
        for item in articles:
            title = item.get("headline") or item.get("title") or ""
            desc = item.get("description") or item.get("story") or ""
            blob = (title + " " + desc).lower()
            matched = [n for n in names if n.lower() in blob]
            if matched:
                recent_news.append({"players": matched[:3], "headline": title, "description": desc[:500], "published": item.get("published"), "link": (item.get("links") or {}).get("web", {}).get("href")})
        data["live_mlb_intelligence"] = {
            "retrieved_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            "stats_window": {"season": today.year, "recent_days": 7},
            "player_stats": stats,
            "recent_player_news": recent_news[:50],
            "team_strategy_profiles": _team_profiles(data),
        }
        before, rest = prompt.split("LIVE ESPN DATA:\n", 1)
        _, after = rest.split("\nRECENT CHAT:", 1)
        return before + "LIVE ESPN DATA:\n" + json.dumps(data, separators=(",", ":")) + "\nRECENT CHAT:" + after


async def _patched_post(self, url, *args, **kwargs):
    if "openrouter.ai/api/v1/chat/completions" in str(url):
        try:
            body = kwargs.get("json")
            if isinstance(body, dict):
                for message in body.get("messages", []):
                    if message.get("role") == "user" and isinstance(message.get("content"), str) and "LIVE ESPN DATA:" in message["content"]:
                        message["content"] = await _enrich(message["content"])
                        break
                kwargs["json"] = body
        except Exception:
            pass
    return await _ORIGINAL_POST(self, url, *args, **kwargs)


httpx.AsyncClient.post = _patched_post
