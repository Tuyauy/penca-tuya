"""
Sportmonks API integration — live scores, standings, auto-sync
"""
import os
import time
import logging
from typing import Optional
import httpx
from fastapi import APIRouter
from database import get_supabase

logger = logging.getLogger(__name__)

router = APIRouter()

# ── Config ────────────────────────────────────────────────────────────────────
SM_API_KEY    = os.getenv("SPORTMONKS_API_KEY", "")
SM_BASE       = "https://api.sportmonks.com/v3/football"
SM_SEASON_ID  = 26618
SM_LEAGUE_ID  = 732

# In-memory cache  {key: (timestamp, data)}
_cache: dict = {}
CACHE_TTL = 60  # seconds

def _cached(key: str, fetch_fn):
    """Return cached value or call fetch_fn() and cache the result."""
    now = time.time()
    if key in _cache:
        ts, data = _cache[key]
        if now - ts < CACHE_TTL:
            return data
    data = fetch_fn()
    _cache[key] = (now, data)
    return data

def _sm_get(path: str, params: dict = None) -> dict:
    """GET request to Sportmonks with API key header."""
    headers = {"Authorization": SM_API_KEY}
    url = f"{SM_BASE}{path}"
    p = {"include": "", **(params or {})}
    resp = httpx.get(url, headers=headers, params=p, timeout=10)
    resp.raise_for_status()
    return resp.json()

# ── Helper: map Sportmonks state to our status ────────────────────────────────
_LIVE_STATES   = {"LIVE", "HT", "ET", "PEN_LIVE", "AET", "BREAK"}
_FINISH_STATES = {"FT", "AET", "FT_PEN", "AWARDED", "WO"}

def _sm_state_to_status(state_short: str) -> str:
    if state_short in _LIVE_STATES:
        return "live"
    if state_short in _FINISH_STATES:
        return "finished"
    return "scheduled"

# ── Map Sportmonks fixture to our match dict ──────────────────────────────────
def _parse_fixture(f: dict) -> dict:
    state     = (f.get("state") or {}).get("short_name", "")
    scores    = f.get("scores") or {}
    # Sportmonks v3: scores.localteam_score / scores.visitorteam_score
    home_score = None
    away_score = None
    if scores:
        home_score = scores.get("localteam_score") if scores.get("localteam_score") is not None else scores.get("home_score")
        away_score = scores.get("visitorteam_score") if scores.get("visitorteam_score") is not None else scores.get("away_score")

    participants = f.get("participants") or []
    home_team_sm = next((p for p in participants if (p.get("meta") or {}).get("location") == "home"), None)
    away_team_sm = next((p for p in participants if (p.get("meta") or {}).get("location") == "away"), None)

    return {
        "sportmonks_id": f.get("id"),
        "home_team_name": (home_team_sm or {}).get("name"),
        "away_team_name": (away_team_sm or {}).get("name"),
        "home_team_sm_id": (home_team_sm or {}).get("id"),
        "away_team_sm_id": (away_team_sm or {}).get("id"),
        "home_score": home_score,
        "away_score": away_score,
        "status": _sm_state_to_status(state),
        "state_short": state,
        "minute": f.get("minute"),
    }

# ── /api/livescores ───────────────────────────────────────────────────────────
@router.get("/livescores")
async def get_livescores():
    """Return currently live matches from Sportmonks (60s cache)."""
    if not SM_API_KEY:
        return {"live": [], "error": "SPORTMONKS_API_KEY not configured"}
    try:
        def fetch():
            data = _sm_get(
                "/livescores/inplay",
                {"filters": f"livescoreSeasons:{SM_SEASON_ID}", "include": "participants;scores;state"}
            )
            fixtures = data.get("data") or []
            return [_parse_fixture(f) for f in fixtures]
        return {"live": _cached("livescores", fetch)}
    except Exception as e:
        logger.error("Sportmonks livescores error: %s", e)
        return {"live": [], "error": str(e)}

# ── /api/standings ────────────────────────────────────────────────────────────
@router.get("/standings")
async def get_standings():
    """Return group standings from Sportmonks (60s cache)."""
    if not SM_API_KEY:
        return {"groups": [], "error": "SPORTMONKS_API_KEY not configured"}
    try:
        def fetch():
            data = _sm_get(
                f"/standings/seasons/{SM_SEASON_ID}",
                {"include": "participant"}
            )
            raw_standings = data.get("data") or []
            groups = {}
            for entry in raw_standings:
                grp_name = entry.get("group_name") or entry.get("round_name") or "?"
                # Sportmonks uses single letter or "Group A" etc.
                grp_letter = grp_name.replace("Group ", "").strip()
                if grp_letter not in groups:
                    groups[grp_letter] = {"group": grp_letter, "teams": []}
                participant = entry.get("participant") or {}
                groups[grp_letter]["teams"].append({
                    "name": participant.get("name", "?"),
                    "code": participant.get("short_code", "???"),
                    "p":   entry.get("games_played", 0),
                    "w":   entry.get("won", 0),
                    "d":   entry.get("draw", 0),
                    "l":   entry.get("lost", 0),
                    "gf":  entry.get("goals_scored", 0),
                    "ga":  entry.get("goals_against", 0),
                    "pts": entry.get("points", 0),
                })
                # Sort each group by pts desc, then goal diff
            for g in groups.values():
                g["teams"].sort(key=lambda t: (-(t["pts"]), -((t["gf"]-t["ga"])), -(t["gf"])))
            return sorted(groups.values(), key=lambda g: g["group"])
        return {"groups": _cached("standings", fetch)}
    except Exception as e:
        logger.error("Sportmonks standings error: %s", e)
        return {"groups": [], "error": str(e)}

# ── Auto-sync helpers (called by scheduler) ──────────────────────────────────
def _calculate_provisional_points(pred_home: int, pred_away: int,
                                   real_home: int, real_away: int) -> int:
    """Mirror of SQL calculate_match_points logic for provisional scoring."""
    if pred_home == real_home and pred_away == real_away:
        return 10
    pred_diff = pred_home - pred_away
    real_diff = real_home - real_away
    if pred_diff == 0 and real_diff == 0:
        return 7
    if pred_diff == real_diff:
        return 5
    if (pred_home > pred_away and real_home > real_away) or        (pred_home < pred_away and real_home < real_away):
        return 3
    return 0

def sync_live_and_finished():
    """
    Called every 2 minutes by APScheduler.
    1. Fetch all fixtures for the season that are live or recently finished.
    2. For live matches: update provisional_points on predictions.
    3. For finished matches: update match result, call calculate_match_points().
    """
    if not SM_API_KEY:
        return
    try:
        sb = get_supabase()

        # ── Fetch today's fixtures from Sportmonks ─────────────────────────
        from datetime import date
        today = date.today().isoformat()
        try:
            data = _sm_get(
                f"/fixtures/date/{today}",
                {"filters": f"fixtureLeagues:{SM_LEAGUE_ID}", "include": "participants;scores;state"}
            )
        except Exception as e:
            logger.warning("Sportmonks fixtures fetch error: %s", e)
            return

        fixtures = data.get("data") or []
        if not fixtures:
            return

        # ── Build a map: sportmonks_id -> parsed fixture ───────────────────
        sm_map = {f["sportmonks_id"]: f for f in [_parse_fixture(fx) for fx in fixtures]}

        # ── Load our matches that reference sportmonks_id ──────────────────
        sm_ids = list(sm_map.keys())
        if not sm_ids:
            return

        our_matches_res = sb.table("matches").select("*").in_("sportmonks_id", sm_ids).execute()
        our_matches = our_matches_res.data or []

        for om in our_matches:
            sm_id = om.get("sportmonks_id")
            if not sm_id or sm_id not in sm_map:
                continue
            sm = sm_map[sm_id]
            match_id = om["id"]

            # ── Handle LIVE match: update provisional points ───────────────
            if sm["status"] == "live":
                # Mark match as live in DB
                if om.get("status") != "live":
                    sb.table("matches").update({
                        "status": "live",
                        "predictions_locked": True,
                        "home_score": sm["home_score"],
                        "away_score": sm["away_score"],
                    }).eq("id", match_id).execute()
                elif sm["home_score"] is not None:
                    sb.table("matches").update({
                        "home_score": sm["home_score"],
                        "away_score": sm["away_score"],
                    }).eq("id", match_id).execute()

                # Update provisional points for each prediction
                if sm["home_score"] is not None and sm["away_score"] is not None:
                    preds_res = sb.table("predictions").select("id,user_id,predicted_home_score,predicted_away_score").eq("match_id", match_id).execute()
                    for pred in (preds_res.data or []):
                        prov = _calculate_provisional_points(
                            pred["predicted_home_score"], pred["predicted_away_score"],
                            sm["home_score"], sm["away_score"]
                        )
                        try:
                            sb.table("predictions").update({"provisional_points": prov}).eq("id", pred["id"]).execute()
                        except Exception:
                            pass  # Column may not exist yet — migration handles it

            # ── Handle FINISHED match: set result and calc final points ─────
            elif sm["status"] == "finished" and om.get("status") != "finished":
                if sm["home_score"] is None or sm["away_score"] is None:
                    continue
                sb.table("matches").update({
                    "home_score": sm["home_score"],
                    "away_score": sm["away_score"],
                    "status": "finished",
                    "predictions_locked": True,
                }).eq("id", match_id).execute()
                # Calculate final points
                try:
                    sb.rpc("calculate_match_points", {"match_id_param": match_id}).execute()
                except Exception as calc_e:
                    logger.error("calculate_match_points failed for match %s: %s", match_id, calc_e)

        # ── Rebuild provisional_total for affected users ───────────────────
        _refresh_provisional_totals(sb, [om["id"] for om in our_matches])

    except Exception as e:
        logger.error("sync_live_and_finished error: %s", e)

def _refresh_provisional_totals(sb, match_ids: list):
    """Recalculate provisional_total for all users who have predictions on these matches."""
    if not match_ids:
        return
    try:
        preds_res = sb.table("predictions").select("user_id,provisional_points,points_earned,points_calculated").in_("match_id", match_ids).execute()
        by_user: dict = {}
        for p in (preds_res.data or []):
            uid = p["user_id"]
            if uid not in by_user:
                by_user[uid] = 0
            pts = p.get("provisional_points")
            if pts is not None:
                by_user[uid] += pts
        for uid, prov_pts in by_user.items():
            try:
                # provisional_total = purchase_points + prediction_points (final) + provisional uplift
                user_res = sb.table("penca_users").select("purchase_points,prediction_points").eq("id", uid).execute()
                if user_res.data:
                    u = user_res.data[0]
                    # We store the provisional total (replaces total_points temporarily)
                    sb.table("penca_users").update({
                        "provisional_total": (u["purchase_points"] or 0) + (u["prediction_points"] or 0) + prov_pts
                    }).eq("id", uid).execute()
            except Exception:
                pass
    except Exception as e:
        logger.error("_refresh_provisional_totals error: %s", e)
