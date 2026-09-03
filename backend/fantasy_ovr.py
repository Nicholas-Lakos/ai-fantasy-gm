"""Reliable ESPN-stat Fantasy OVR engine.

This intentionally uses the ESPN roster/player-pool statistics that are already
available in the authenticated league response.  A deep kona_playercard request
is optional enrichment, not a requirement for producing an OVR.
"""
from __future__ import annotations

import math


def _num(v, default=0.0):
    try:
        x = float(v)
        return x if math.isfinite(x) else default
    except (TypeError, ValueError):
        return default


def _pct(value, values):
    vals = sorted(_num(x) for x in values)
    if len(vals) <= 1:
        return 0.50
    below = sum(x < value for x in vals)
    equal = sum(x == value for x in vals)
    return (below + 0.5 * equal) / len(vals)


def build_ovr_rows(players):
    """Create a stable 55-99 Fantasy OVR from ESPN fantasy production."""
    if not players:
        return []

    groups = {}
    for p in players:
        groups.setdefault(str(p.get('position') or '—'), []).append(p)

    # Keep the scoring inputs intentionally simple and explainable:
    # season production, per-active-day production, recent/current production,
    # and ESPN ownership/start rate as a small confidence signal.
    prepared = []
    for p in players:
        total = _num(p.get('total_points'))
        applied = _num(p.get('applied_stat_total') if p.get('applied_stat_total') is not None else p.get('current_period_points'))
        avg = _num(p.get('average_fantasy_points'))
        if avg <= 0:
            avg = total / max(1.0, _num(p.get('games_or_active_days'), 1.0))
        recent = _num(p.get('recent_average'))
        if recent <= 0:
            recent = applied
        prepared.append({**p, '_total': total, '_avg': avg, '_recent': recent, '_applied': applied})

    # Percentiles are position-adjusted, so a pitcher is compared primarily
    # with pitchers and hitters with hitters.
    for p in prepared:
        group = groups.get(str(p.get('position') or '—'), prepared)
        totals = [_num(x.get('total_points')) for x in group]
        avgs = []
        recents = []
        for x in group:
            xx = next((q for q in prepared if q.get('id') == x.get('id')), None)
            avgs.append(_num(xx.get('_avg') if xx else x.get('average_fantasy_points')))
            recents.append(_num(xx.get('_recent') if xx else x.get('recent_average')))
        season_pct = _pct(p['_total'], totals)
        avg_pct = _pct(p['_avg'], avgs)
        recent_pct = _pct(p['_recent'], recents)
        started = _num(p.get('percent_started'))
        owned = _num(p.get('percent_owned'))
        market_pct = max(0.0, min(1.0, (0.65 * owned + 0.35 * started) / 100.0)) if (owned or started) else 0.50

        # Production dominates; ESPN market data is only a modest stabilizer.
        performance = 0.45 * season_pct + 0.30 * avg_pct + 0.20 * recent_pct + 0.05 * market_pct
        p['_ovr'] = round(max(55, min(99, 55 + 44 * performance)))
        p['_components'] = (round(season_pct * 100), round(avg_pct * 100), round(recent_pct * 100), round(market_pct * 100))

    return [{
        'id': p.get('id'),
        'name': p.get('name'),
        'position': p.get('position'),
        'fantasy_ovr': p['_ovr'],
        'ovr_source': 'ESPN stats',
        'ovr_components': {
            'season': p['_components'][0],
            'average': p['_components'][1],
            'recent': p['_components'][2],
            'market': p['_components'][3],
        },
        'games_or_active_days': p.get('games_or_active_days', 0),
        'stat_days': p.get('stat_days', 0),
        'average_fantasy_points': round(_num(p.get('_avg')), 2),
        'recent_average': round(_num(p.get('_recent')), 2),
        'total_points': round(_num(p.get('_total')), 2),
    } for p in prepared]


async def fetch_fantasy_ovr(req, espn, player_card=None):
    """Fetch the authenticated ESPN league roster and always return ratings."""
    meta = await espn(req, ['mSettings', 'mStatus'])
    current_period = None
    for obj in (meta.get('status') or {}, meta.get('settings') or {}):
        for key in ('scoringPeriodId', 'currentScoringPeriodId', 'currentScoringPeriod'):
            value = obj.get(key)
            if isinstance(value, dict):
                value = value.get('id')
            try:
                if value is not None:
                    current_period = int(value)
                    break
            except (TypeError, ValueError):
                pass
        if current_period is not None:
            break
    if current_period is None:
        current_period = 1

    data = await espn(req, ['mTeam', 'mRoster', 'mStatus'], current_period)
    players = []
    seen = set()
    for team in data.get('teams', []):
        for entry in (team.get('roster') or {}).get('entries', []):
            ppe = entry.get('playerPoolEntry') or {}
            p = ppe.get('player') or entry.get('player') or {}
            pid = p.get('id') or entry.get('playerId') or ppe.get('id')
            if pid is None or str(pid) in seen:
                continue
            seen.add(str(pid))
            stats = ppe.get('stats') or []
            season_stats = [s for s in stats if s.get('seasonId') == req.season and s.get('statTypeId') == 0]
            recent_values = [
                _num(s.get('appliedTotal')) for s in season_stats
                if s.get('scoringPeriodId') is not None
            ]
            recent = recent_values[-14:] if recent_values else []
            total = ppe.get('totalPoints')
            active_days = sum(1 for x in recent_values if x > 0)
            players.append({
                'id': pid,
                'name': p.get('fullName') or f'Player {pid}',
                'position': p.get('defaultPositionId'),
                'total_points': total,
                'applied_stat_total': ppe.get('appliedStatTotal'),
                'percent_owned': ppe.get('percentOwned'),
                'percent_started': ppe.get('percentStarted'),
                'games_or_active_days': active_days,
                'stat_days': len(recent_values),
                'average_fantasy_points': (_num(total) / max(1, active_days)) if total is not None else 0,
                'recent_average': (sum(recent) / len(recent)) if recent else _num(ppe.get('appliedStatTotal')),
            })

    # Convert ESPN numeric position IDs to the same labels used by the UI.
    labels = {1:'SP',2:'C',3:'1B',4:'2B',5:'3B',6:'SS',7:'LF',8:'CF',9:'RF',10:'OF',11:'DH',12:'RP',13:'P'}
    for p in players:
        p['position'] = labels.get(p.get('position'), p.get('position') or '—')

    return build_ovr_rows(players)
