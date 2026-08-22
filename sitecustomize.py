import sys
from fastapi import FastAPI

# Keep production behavior simple: the app's real backend/frontend own the UI.
# The previous runtime patch layer was rewriting player/team responses after
# backend.main had already prepared them, which made debugging and roster
# rendering unnecessarily fragile.
_ORIG_INIT = FastAPI.__init__

def _init(self, *args, **kwargs):
    _ORIG_INIT(self, *args, **kwargs)

    @self.on_event('startup')
    async def _stabilize_espn_live():
        mod = sys.modules.get('backend.main') or sys.modules.get('main')
        if not mod or getattr(mod, '_gm_live_stabilized', False):
            return
        mod._gm_live_stabilized = True
        original_live = mod.live

        async def stable_live(user_id, waivers=False):
            league = mod.league_row(user_id)
            req = mod.req_for(league)

            # Get league metadata/teams without a scoring-period parameter.
            # Team/standings data is the source of truth for the league's team
            # list; roster data is merged into it separately.
            meta = await mod.espn(req, ['mSettings', 'mTeam', 'mStandings', 'mStatus'], None, timeout=30)
            scoring_period = mod.period(meta)
            if scoring_period is None:
                raise mod.HTTPException(502, 'ESPN did not provide the current scoring period.')

            base = await mod.espn(req, ['mTeam', 'mStandings', 'mStatus', 'mSettings'], None, timeout=30)
            roster = {}

            # ESPN has returned inconsistent roster payloads for some leagues.
            # Try the current roster without forcing a scoring period first.
            try:
                roster = await mod.espn(req, ['mRoster'], None, timeout=30)
            except Exception:
                roster = {}

            # Fallback to the scoring-period roster endpoint if needed.
            if not (roster.get('teams') or []):
                try:
                    roster = await mod.espn(req, ['mRoster', 'mTeam'], scoring_period, timeout=30)
                except Exception:
                    roster = {}

            teams_by_id = {}
            for source in (base.get('teams') or [], roster.get('teams') or []):
                for team in source:
                    raw_id = team.get('id')
                    if raw_id is None:
                        continue
                    try:
                        tid = int(raw_id)
                    except Exception:
                        continue
                    merged = teams_by_id.get(tid, {})
                    for key, value in team.items():
                        if key == 'roster':
                            if value and (value.get('entries') if isinstance(value, dict) else None):
                                merged['roster'] = value
                            elif 'roster' not in merged:
                                merged['roster'] = value or {}
                        elif value not in (None, {}, []):
                            merged[key] = value
                    merged['id'] = tid
                    teams_by_id[tid] = merged

            if not teams_by_id:
                # Never silently turn a valid league into an empty UI.
                # If the original loader can still see teams, preserve them.
                try:
                    old = await original_live(user_id, False)
                    _, _, old_data, old_period, _ = old
                    for team in old_data.get('teams') or []:
                        if team.get('id') is not None:
                            teams_by_id[int(team['id'])] = team
                    if old_period:
                        scoring_period = old_period
                except Exception:
                    raise mod.HTTPException(502, 'ESPN returned no league teams. Please reconnect the league.')

            data = dict(base)
            data.update({k: v for k, v in roster.items() if k not in ('teams',) and v not in (None, {}, [])})
            data['teams'] = list(teams_by_id.values())
            data['settings'] = meta.get('settings') or base.get('settings') or data.get('settings') or {}
            data['scoringPeriodId'] = scoring_period

            if waivers:
                pool_rows = await mod.pool(req, scoring_period)
            else:
                pool_rows = []
            return league, req, data, scoring_period, pool_rows

        mod.live = stable_live

FastAPI.__init__ = _init
