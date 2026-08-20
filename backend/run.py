import asyncio
import json
import uvicorn
from . import main

POS = main.POS
SLOT = main.SLOT


def player_obj(entry):
    # ESPN roster/player-pool payloads can place player fields in either
    # playerPoolEntry.player or directly on the entry. Never infer a
    # player's baseball position from the lineup slot.
    ppe = entry.get('playerPoolEntry') or {}
    return ppe.get('player') or entry.get('player') or ppe or entry


def compact_player_fixed(entry):
    ppe = entry.get('playerPoolEntry') or {}
    p = player_obj(entry)
    pid = p.get('id') or ppe.get('id') or entry.get('playerId')
    slot = entry.get('lineupSlotId')
    injury = p.get('injuryStatus') or entry.get('injuryStatus') or ''
    position_id = p.get('defaultPositionId')
    position = POS.get(position_id, '—')
    eligible = [POS[x] for x in (p.get('eligibleSlots') or []) if x in POS]
    return {
        'id': pid,
        'name': p.get('fullName') or entry.get('fullName') or f'Player {pid}',
        'position': position,
        'eligible_positions': eligible,
        'pro_team_id': p.get('proTeamId'),
        'injury_status': injury,
        'lineup_slot': SLOT.get(slot, '—'),
        'roster_status': injury or ('BENCH' if slot == 12 else 'ACTIVE'),
        'total_points': ppe.get('totalPoints', entry.get('totalPoints')),
        'applied_stat_total': ppe.get('appliedStatTotal', entry.get('appliedStatTotal')),
        'percent_owned': ppe.get('percentOwned', entry.get('percentOwned')),
        'percent_started': ppe.get('percentStarted', entry.get('percentStarted')),
    }


async def pool_fixed(req, p, limit=500):
    filters = {'players': {
        'filterStatus': {'value': ['FREEAGENT', 'WAIVERS']},
        'limit': limit,
        'sortPercOwned': {'sortPriority': 1, 'sortAsc': False},
    }}
    try:
        data = await main.espn(req, ['kona_player_info'], p, filters, timeout=35)
        items = data.get('players') or []
    except Exception:
        items = []
    if not items:
        try:
            data = await main.espn(req, ['kona_player_info'], p, {
                'players': {'limit': limit,
                            'sortPercOwned': {'sortPriority': 1, 'sortAsc': False}}
            }, timeout=35)
            items = data.get('players') or []
        except Exception:
            items = []
    out = {}
    for entry in items:
        p_obj = player_obj(entry)
        ppe = entry.get('playerPoolEntry') or {}
        status = ppe.get('status') or entry.get('status') or 'FREEAGENT'
        # When ESPN ignores filterStatus, only keep genuinely available players.
        on_team = entry.get('onTeamId', ppe.get('onTeamId'))
        if status not in ('FREEAGENT', 'WAIVERS') and on_team not in (None, 0):
            continue
        pid = p_obj.get('id') or ppe.get('id') or entry.get('id')
        if not pid:
            continue
        pos_id = p_obj.get('defaultPositionId')
        out[pid] = {
            'id': pid,
            'name': p_obj.get('fullName') or f'Player {pid}',
            'position': POS.get(pos_id, '—'),
            'eligible_positions': [POS[x] for x in (p_obj.get('eligibleSlots') or []) if x in POS],
            'injury_status': p_obj.get('injuryStatus'),
            'total_points': ppe.get('totalPoints', entry.get('totalPoints')),
            'percent_owned': ppe.get('percentOwned', entry.get('percentOwned')),
            'percent_started': ppe.get('percentStarted', entry.get('percentStarted')),
            'rank': ppe.get('rank', entry.get('rank')),
            'status': status,
            'pro_team_id': p_obj.get('proTeamId'),
        }
    return list(out.values())


async def player_card_fixed(req, pid, p):
    filters = {'players': {
        'filterIds': {'value': [int(pid)]},
        'filterStatsForTopScoringPeriodIds': {
            'value': max(int(p), 1),
            'additionalValue': [f'00{req.season}', f'10{req.season}'],
        },
    }}
    try:
        data = await main.espn(req, ['kona_playercard'], p, filters, timeout=30)
    except Exception:
        # Some ESPN payloads return richer data through kona_player_info.
        data = await main.espn(req, ['kona_player_info'], p, {
            'players': {'filterIds': {'value': [int(pid)]}, 'limit': 1}
        }, timeout=30)
    items = data.get('players') or []
    if not items:
        raise main.HTTPException(404, 'Player not found in ESPN.')
    x = items[0]
    p_obj = player_obj(x)
    ppe = x.get('playerPoolEntry') or {}
    # Detailed stats are commonly on the player object for kona_playercard;
    # older responses place them on playerPoolEntry.
    raw_stats = p_obj.get('stats') or x.get('stats') or ppe.get('stats') or []
    if isinstance(raw_stats, dict):
        raw_stats = [raw_stats]
    season_rows = []
    projection_rows = []
    current_total = ppe.get('appliedStatTotal', x.get('appliedStatTotal'))
    for s in raw_stats:
        if not isinstance(s, dict):
            continue
        sid = str(s.get('seasonId', ''))
        stid = s.get('statTypeId')
        code = str(s.get('id', ''))
        applied = s.get('appliedStats') or s.get('stats') or {}
        total = s.get('appliedTotal', s.get('appliedStatTotal'))
        row = {
            'id': s.get('id'),
            'seasonId': s.get('seasonId'),
            'scoringPeriodId': s.get('scoringPeriodId'),
            'statTypeId': stid,
            'appliedTotal': total,
            'appliedStats': applied,
        }
        # ESPN actual season split starts with 00 + season.
        if code == f'00{req.season}' or (s.get('seasonId') == req.season and stid in (0, '0')):
            season_rows.append(row)
        elif code == f'10{req.season}' or (s.get('seasonId') == req.season and stid in (1, '1')):
            projection_rows.append(row)
        if s.get('scoringPeriodId') == p and total is not None:
            try:
                current_total = float(total)
            except Exception:
                pass
    # If ESPN returned only category rows without statTypeId, keep them visible.
    if not season_rows:
        season_rows = [s for s in raw_stats if isinstance(s, dict) and
                       (s.get('seasonId') == req.season or str(s.get('id', '')).startswith(f'00{req.season}'))]
    position_id = p_obj.get('defaultPositionId')
    return {
        'id': pid,
        'name': p_obj.get('fullName') or f'Player {pid}',
        'position': POS.get(position_id, '—'),
        'eligible_positions': [POS[x] for x in (p_obj.get('eligibleSlots') or []) if x in POS],
        'pro_team_id': p_obj.get('proTeamId'),
        'injury_status': p_obj.get('injuryStatus'),
        'active': p_obj.get('active'),
        'total_points': ppe.get('totalPoints', x.get('totalPoints')),
        'current_period_points': current_total,
        'percent_owned': ppe.get('percentOwned', x.get('percentOwned')),
        'percent_started': ppe.get('percentStarted', x.get('percentStarted')),
        'stats': season_rows,
        'projection_stats': projection_rows,
        'raw_stat_count': len(raw_stats),
    }


# Patch the application functions before uvicorn starts serving requests.
main.compact_player = compact_player_fixed
main.pool = pool_fixed
main.player_card = player_card_fixed

if __name__ == '__main__':
    uvicorn.run(main.app, host='0.0.0.0', port=8000)
