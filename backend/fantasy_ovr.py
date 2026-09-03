"""Dynamic Fantasy OVR engine built from live ESPN fantasy statistics."""
from __future__ import annotations

import asyncio
import math
from statistics import mean, pstdev


def _num(value, default=0.0):
    try:
        x = float(value)
        return x if math.isfinite(x) else default
    except (TypeError, ValueError):
        return default


def _stats_list(player):
    """Normalize the two ESPN shapes used by our player-card implementations."""
    stats = player.get('season_splits') or player.get('stats') or []
    if isinstance(stats, dict):
        return []
    return [s for s in stats if isinstance(s, dict)]


def _percentile(value, values):
    vals = sorted(_num(v) for v in values if v is not None)
    if not vals:
        return 0.5
    if len(vals) == 1:
        return 0.5
    below = sum(1 for v in vals if v < value)
    equal = sum(1 for v in vals if v == value)
    return (below + 0.5 * equal) / len(vals)


def _recent_average(stats, periods=14):
    rows = []
    for s in stats or []:
        pid = s.get('scoringPeriodId')
        if pid is None:
            continue
        if s.get('seasonId') is not None and s.get('statTypeId') not in (None, 0, '0'):
            continue
        rows.append((int(pid), _num(s.get('appliedTotal'))))
    rows.sort(key=lambda x: x[0])
    recent = [v for _, v in rows[-periods:]]
    return mean(recent) if recent else 0.0


def _consistency(stats):
    vals = []
    for s in stats or []:
        if s.get('scoringPeriodId') is None:
            continue
        if s.get('seasonId') is not None and s.get('statTypeId') not in (None, 0, '0'):
            continue
        vals.append(_num(s.get('appliedTotal')))
    if len(vals) < 2:
        return 0.5
    avg = mean(vals)
    sd = pstdev(vals)
    if avg <= 0:
        return 0.5
    return 1.0 / (1.0 + sd / avg)


def build_ovr_rows(players):
    """Return player ratings and the component scores used to explain them."""
    if not players:
        return []

    groups = {}
    for p in players:
        groups.setdefault(str(p.get('position') or '—'), []).append(p)

    raw = []
    for p in players:
        stats = _stats_list(p)
        total = _num(p.get('total_points'))
        daily = [_num(s.get('appliedTotal')) for s in stats if s.get('scoringPeriodId') is not None]
        active_days = sum(1 for x in daily if x > 0)
        season_days = len(daily)
        avg_day = total / max(1, active_days)
        recent = _recent_average(stats)
        consistency = _consistency(stats)
        group = groups.get(str(p.get('position') or '—'), [p])
        totals = [_num(x.get('total_points')) for x in group]
        avgs, recents = [], []
        for x in group:
            xs = _stats_list(x)
            xv = [_num(s.get('appliedTotal')) for s in xs if s.get('scoringPeriodId') is not None]
            xa = _num(x.get('total_points')) / max(1, sum(1 for z in xv if z > 0))
            avgs.append(xa)
            recents.append(_recent_average(xs))
        raw.append({
            'player': p,
            'season_pct': _percentile(total, totals),
            'avg_pct': _percentile(avg_day, avgs),
            'recent_pct': _percentile(recent, recents),
            'consistency': consistency,
            'active_days': active_days,
            'season_days': season_days,
            'avg_day': avg_day,
            'recent_avg': recent,
        })

    output = []
    for r in raw:
        season = r['season_pct']
        avg = r['avg_pct']
        recent = r['recent_pct']
        consistency = r['consistency']
        group_size = len(groups.get(str(r['player'].get('position') or '—'), []))
        if group_size <= 2:
            performance = 0.55 * season + 0.25 * avg + 0.20 * recent
        else:
            performance = 0.40 * season + 0.25 * avg + 0.25 * recent + 0.10 * consistency
        ovr = round(max(55, min(99, 55 + 44 * performance)))
        p = r['player']
        output.append({
            'id': p.get('id'),
            'name': p.get('name'),
            'position': p.get('position'),
            'fantasy_ovr': ovr,
            'ovr_source': 'ESPN stats',
            'ovr_components': {
                'season': round(season * 100),
                'average': round(avg * 100),
                'recent': round(recent * 100),
                'consistency': round(consistency * 100),
            },
            'games_or_active_days': r['active_days'],
            'stat_days': r['season_days'],
            'average_fantasy_points': round(r['avg_day'], 2),
            'recent_average': round(r['recent_avg'], 2),
            'total_points': round(_num(p.get('total_points')), 2),
        })
    return output


async def fetch_fantasy_ovr(req, espn, player_card):
    """Fetch live ESPN cards for every rostered league player and calculate OVRs."""
    roster_data = await espn(req, ['mTeam', 'mRoster', 'mStatus'])
    entries, seen = [], set()
    for team in roster_data.get('teams', []):
        for entry in (team.get('roster') or {}).get('entries', []):
            ppe = entry.get('playerPoolEntry') or {}
            p = ppe.get('player') or {}
            pid = p.get('id') or entry.get('playerId') or ppe.get('id')
            if pid is None or str(pid) in seen:
                continue
            seen.add(str(pid))
            entries.append({
                'id': pid,
                'name': p.get('fullName') or f'Player {pid}',
                'position': p.get('defaultPositionId'),
                'total_points': ppe.get('totalPoints'),
            })

    async def one(e):
        try:
            card = await player_card(req, e['id'], 1)
            card['position'] = card.get('position') or e.get('position')
            if card.get('total_points') is None:
                card['total_points'] = e.get('total_points')
            return card
        except Exception:
            return {**e, 'stats': [], 'season_splits': []}

    sem = asyncio.Semaphore(6)
    async def bounded(e):
        async with sem:
            return await one(e)

    cards = await asyncio.gather(*(bounded(e) for e in entries))
    return build_ovr_rows(cards)
