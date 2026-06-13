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
    """GET request to Sportmonks. Retries 3x with backoff on 503/timeout."""
    headers = {"Authorization": SM_API_KEY}
    url = f"{SM_BASE}{path}"
    p = {"include": "", **(params or {})}
    delays = [5, 10, 20]
    last_exc = None
    for attempt, delay in enumerate(delays, 1):
        try:
            resp = httpx.get(url, headers=headers, params=p, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except (httpx.TimeoutException, httpx.HTTPStatusError) as e:
            is_retryable = isinstance(e, httpx.TimeoutException) or (
                isinstance(e, httpx.HTTPStatusError) and e.response.status_code in (503, 502, 429)
            )
            if is_retryable and attempt <= len(delays):
                logger.warning(
                    "Sportmonks _sm_get intento %d fallido (%s), reintentando en %ds...",
                    attempt, e, delay
                )
                time.sleep(delay)
                last_exc = e
            else:
                raise
    raise last_exc

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
    scores_raw = f.get("scores")
    # Sportmonks v3: scores can be a list of score objects or a dict
    home_score = None
    away_score = None
    logger.warning("[DIAG] _parse_fixture id=%s state=%s scores_raw=%s", f.get("id"), (f.get("state") or {}).get("short_name"), str(scores_raw)[:500])
    if isinstance(scores_raw, list):
        for _sc in scores_raw:
            _sc_type = (_sc.get("type") or {}).get("developer_name", "") if isinstance(_sc.get("type"), dict) else ""
            _score_obj = _sc.get("score") or {}
            _goals = _score_obj.get("goals")
            _participant = _score_obj.get("participant", "")
            if "FT" in _sc_type or _sc.get("type_id") in (1525, 1):
                if _participant == "home" and _goals is not None:
                    home_score = _goals
                elif _participant == "away" and _goals is not None:
                    away_score = _goals
    elif isinstance(scores_raw, dict) and scores_raw:
        home_score = scores_raw.get("localteam_score") if scores_raw.get("localteam_score") is not None else scores_raw.get("home_score")
        away_score = scores_raw.get("visitorteam_score") if scores_raw.get("visitorteam_score") is not None else scores_raw.get("away_score")

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

# ── /api/standings ──────────────────────────────────────────────────────────
# Sportmonks detail type_ids for standings (verified against API):
# 129=overall-matches-played, 130=overall-won, 131=overall-draw, 132=overall-lost
# 133=overall-goals-scored, 134=overall-goals-against
_SM_DETAIL = {
    "played":   129,
    "won":      130,
    "draw":     131,
    "lost":     132,
    "gf":       133,
    "ga":       134,
}
_STANDINGS_CACHE_TTL = 300  # 5 minutes

@router.get("/standings")
async def get_standings():
    """Return group standings from Sportmonks (5-min cache)."""
    if not SM_API_KEY:
        return {"groups": [], "error": "SPORTMONKS_API_KEY not configured"}
    try:
        def fetch():
            # Fetch all 48 group-stage standing entries (48 = 12 groups × 4 teams)
            raw_data = _sm_get(
                f"/standings/seasons/{SM_SEASON_ID}",
                {"include": "participant;details.type;group", "per_page": "50"}
            )
            raw_standings = raw_data.get("data") or []

            groups: dict = {}
            for entry in raw_standings:
                # Group name from the nested group object
                grp_obj = entry.get("group") or {}
                grp_raw = grp_obj.get("name") or entry.get("group_name") or "?"
                grp_letter = grp_raw.replace("Group ", "").strip()

                # Stats from details array keyed by type_id
                detail_map = {d["type_id"]: d["value"] for d in (entry.get("details") or [])}

                participant = entry.get("participant") or {}
                team_entry = {
                    "name": participant.get("name", "?"),
                    "code": participant.get("short_code", "???"),
                    "p":    detail_map.get(_SM_DETAIL["played"], 0),
                    "w":    detail_map.get(_SM_DETAIL["won"],    0),
                    "d":    detail_map.get(_SM_DETAIL["draw"],   0),
                    "l":    detail_map.get(_SM_DETAIL["lost"],   0),
                    "gf":   detail_map.get(_SM_DETAIL["gf"],     0),
                    "ga":   detail_map.get(_SM_DETAIL["ga"],     0),
                    "pts":  entry.get("points", 0),
                }
                if grp_letter not in groups:
                    groups[grp_letter] = {"group": grp_letter, "teams": []}
                groups[grp_letter]["teams"].append(team_entry)

            # Sort each group by pts desc, then goal diff, then goals scored
            for g in groups.values():
                g["teams"].sort(key=lambda t: (
                    -(t["pts"]),
                    -((t["gf"] - t["ga"])),
                    -(t["gf"])
                ))
            return sorted(groups.values(), key=lambda g: g["group"])

        # Use 5-minute cache
        now = time.time()
        cache_key = "standings_v2"
        if cache_key in _cache:
            ts, cached = _cache[cache_key]
            if now - ts < _STANDINGS_CACHE_TTL:
                return {"groups": cached}
        result = fetch()
        _cache[cache_key] = (now, result)
        return {"groups": result}
    except Exception as e:
        logger.error("Sportmonks standings error: %s", e)
        return {"groups": [], "error": str(e)}


# ── /api/admin/link-fixtures ────────────────────────────────────────────────
@router.get("/admin/link-fixtures")
async def admin_link_fixtures():
    """
    Diagnostic linking endpoint.
    Step 0: Lists all seasons for league 732 so we can verify the correct season ID.
    Step 1: Tries 3 fixture endpoints filtered by season 26618, captures URL+status+count+sample dates.
    Step 2: Links unlinked Supabase matches using the first working endpoint.
    """
    if not SM_API_KEY:
        return {"ok": False, "error": "SPORTMONKS_API_KEY not configured"}

    import httpx as _httpx

    def _raw_get(path, params=None):
        """Direct HTTP GET, returns (status_code, json_body)."""
        headers = {"Authorization": SM_API_KEY}
        url = f"{SM_BASE}{path}"
        p = {**(params or {})}
        resp = _httpx.get(url, headers=headers, params=p, timeout=15)
        try:
            body = resp.json()
        except Exception:
            body = {}
        return resp.status_code, body

    try:
        sb = get_supabase()

        # ── Step 0: list seasons for league 732 ──────────────────────────────
        seasons_info = []
        seasons_error = None
        try:
            sc, sbody = _raw_get("/seasons", {"filters": f"leagueId:{SM_LEAGUE_ID}", "per_page": "50"})
            if sc == 200:
                for s in (sbody.get("data") or []):
                    seasons_info.append({
                        "id": s.get("id"),
                        "name": s.get("name"),
                        "league_id": s.get("league_id"),
                        "starting_at": s.get("starting_at"),
                        "ending_at": s.get("ending_at"),
                    })
            else:
                seasons_error = f"status {sc}: {str(sbody)[:200]}"
        except Exception as se:
            seasons_error = str(se)

        # ── Step 1: try 3 fixture endpoints filtered by season ────────────────
        fixture_attempts = []
        sm_fixtures = []
        working_endpoint = None

        endpoints_to_try = [
            ("/fixtures", {"filters": f"fixtureSeasons:{SM_SEASON_ID}", "include": "participants;state", "per_page": "500"}),
            ("/fixtures", {"filters": f"fixtureLeagues:{SM_LEAGUE_ID};fixtureSeason:{SM_SEASON_ID}", "include": "participants;state", "per_page": "500"}),
            (f"/seasons/{SM_SEASON_ID}/fixtures", {"include": "participants;state", "per_page": "500"}),
        ]

        for path, params in endpoints_to_try:
            full_url = f"{SM_BASE}{path}"
            try:
                sc, body = _raw_get(path, params)
                data = body.get("data") or []
                sample_dates = sorted({
                    (f.get("starting_at") or f.get("date") or "")[:10]
                    for f in data[:50] if (f.get("starting_at") or f.get("date") or "")[:4]
                })
                attempt = {
                    "url": full_url,
                    "params": params,
                    "status": sc,
                    "fixtures_returned": len(data),
                    "sample_dates": sample_dates[:10],
                }
                fixture_attempts.append(attempt)
                if sc == 200 and data and working_endpoint is None:
                    sm_fixtures = data
                    working_endpoint = full_url
            except Exception as req_err:
                fixture_attempts.append({"url": full_url, "params": params, "status": "exception", "error": str(req_err)})

        # ── Step 2: fetch unlinked + attempt linking ──────────────────────────
        unlinked_res = sb.table("matches").select(
            "id, match_date, "
            "home_team:teams!matches_home_team_id_fkey(name, code), "
            "away_team:teams!matches_away_team_id_fkey(name, code)"
        ).is_("sportmonks_id", "null").execute()
        unlinked = unlinked_res.data or []

        sm_by_date: dict = {}
        for rf in sm_fixtures:
            starting_at = rf.get("starting_at") or rf.get("date") or ""
            dk = starting_at[:10]
            sm_by_date.setdefault(dk, []).append(rf)

        linked_count = 0
        debug_failures = []

        for match in unlinked:
            raw_md = match.get("match_date") or ""
            date_key = raw_md[:10]
            home_name = (match.get("home_team") or {}).get("name", "")
            away_name = (match.get("away_team") or {}).get("name", "")
            day_candidates = sm_by_date.get(date_key, [])

            found = False
            for rf in day_candidates:
                participants = rf.get("participants") or []
                home_sm = next((p for p in participants if (p.get("meta") or {}).get("location") == "home"), None)
                away_sm = next((p for p in participants if (p.get("meta") or {}).get("location") == "away"), None)
                if not home_sm or not away_sm:
                    continue
                home_sm_code = home_sm.get("short_code", "") or home_sm.get("code", "")
                away_sm_code = away_sm.get("short_code", "") or away_sm.get("code", "")
                if (
                    _teams_match(home_name, home_sm.get("name", ""), home_sm_code)
                    and _teams_match(away_name, away_sm.get("name", ""), away_sm_code)
                ):
                    sb.table("matches").update({"sportmonks_id": rf.get("id")}).eq("id", match["id"]).execute()
                    linked_count += 1
                    found = True
                    break

            if not found and len(debug_failures) < 3:
                first_candidates = [
                    {
                        "sm_home": next((p.get("name") for p in (rf.get("participants") or []) if (p.get("meta") or {}).get("location") == "home"), None),
                        "sm_home_code": next((p.get("short_code") or p.get("code") for p in (rf.get("participants") or []) if (p.get("meta") or {}).get("location") == "home"), None),
                        "sm_away": next((p.get("name") for p in (rf.get("participants") or []) if (p.get("meta") or {}).get("location") == "away"), None),
                        "sm_away_code": next((p.get("short_code") or p.get("code") for p in (rf.get("participants") or []) if (p.get("meta") or {}).get("location") == "away"), None),
                    }
                    for rf in day_candidates[:5]
                ]
                debug_failures.append({
                    "supabase_home": home_name,
                    "supabase_away": away_name,
                    "match_date": date_key,
                    "sm_candidates_on_date": len(day_candidates),
                    "first_5_candidates": first_candidates,
                })

        return {
            "ok": True,
            "seasons_for_league_732": seasons_info,
            "seasons_error": seasons_error,
            "fixture_attempts": fixture_attempts,
            "working_endpoint": working_endpoint,
            "sm_fixtures_fetched": len(sm_fixtures),
            "sm_dates_with_fixtures": sorted(sm_by_date.keys()),
            "unlinked_in_supabase": len(unlinked),
            "linked_this_run": linked_count,
            "debug_first_3_failures": debug_failures,
        }
    except Exception as e:
        logger.error("admin_link_fixtures error: %s", e)
        return {"ok": False, "error": str(e)}


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

# ── Mapa código Sportmonks → nombres en Supabase (para linking) ────────────
# Códigos verificados directamente contra la API de Sportmonks (season 26618)
_CODE_TO_NAMES: dict = {
    "MEX": ["México", "Mexico"],
    "ZAF": ["Sudáfrica", "Sudafrica", "South Africa"],       # Sportmonks usa ZAF, no RSA
    "KOR": ["Rep. de Corea", "Corea del Sur", "Korea Republic", "South Korea"],
    "CZE": ["Chequia", "Czech Republic", "Czechia"],
    "CAN": ["Canadá", "Canada"],
    "BIH": ["Bosnia y Herzegovina", "Bosnia & Herzegovina", "Bosnia and Herzegovina"],
    "QAT": ["Catar", "Qatar"],
    "SUI": ["Suiza", "Switzerland"],
    "BRA": ["Brasil", "Brazil"],
    "MAR": ["Marruecos", "Morocco"],
    "HTI": ["Haití", "Haiti"],                                # Sportmonks usa HTI, no HAI
    "SCO": ["Escocia", "Scotland"],
    "USA": ["Estados Unidos", "EE. UU.", "United States"],
    "PRY": ["Paraguay"],                                      # Sportmonks usa PRY, no PAR
    "AUS": ["Australia"],
    "TUR": ["Turquía", "Turquia", "Turkey", "Türkiye"],
    "GER": ["Alemania", "Germany"],
    "CUW": ["Curazao", "Curaçao", "Curacao"],
    "CIV": ["Costa de Marfil", "Ivory Coast", "Côte d'Ivoire"],
    "ECU": ["Ecuador"],
    "NED": ["Países Bajos", "Paises Bajos", "Netherlands"],
    "JPN": ["Japón", "Japan"],
    "SWE": ["Suecia", "Sweden"],
    "TUN": ["Túnez", "Tunez", "Tunisia"],
    "BEL": ["Bélgica", "Belgica", "Belgium"],
    "EGY": ["Egipto", "Egypt"],
    "IRN": ["RI de Irán", "Irán", "Iran"],
    "NZL": ["Nueva Zelanda", "New Zealand"],
    "ESP": ["España", "Espana", "Spain"],
    "CPV": ["Islas de Cabo Verde", "Cabo Verde", "Cape Verde", "Cape Verde Islands"],
    "KSA": ["Arabia Saudí", "Arabia Saudita", "Saudi Arabia"],
    "URU": ["Uruguay"],
    "FRA": ["Francia", "France"],
    "SEN": ["Senegal"],
    "IRQ": ["Irak", "Iraq"],
    "NOR": ["Noruega", "Norway"],
    "ARG": ["Argentina"],
    "DZA": ["Argelia", "Algeria"],                            # Sportmonks usa DZA, no ALG
    "AUT": ["Austria"],
    "JOR": ["Jordania", "Jordan"],
    "POR": ["Portugal"],
    "COD": ["RD Congo", "Congo DR", "DR Congo", "Democratic Republic of Congo"],
    "UZB": ["Uzbekistán", "Uzbekistan"],
    "COL": ["Colombia"],
    "ENG": ["Inglaterra", "England"],
    "CRO": ["Croacia", "Croatia"],
    "GHA": ["Ghana"],
    "PAN": ["Panamá", "Panama"],
}

# Mapa inverso: nombre_lower → código
_NAME_TO_CODE: dict = {
    name.lower(): code
    for code, names in _CODE_TO_NAMES.items()
    for name in names
}



def _normalize_team_name(name: str) -> str:
    """Normaliza un nombre de equipo para comparación (sin tildes, lowercase)."""
    import unicodedata
    nfkd = unicodedata.normalize("NFKD", name or "")
    ascii_str = nfkd.encode("ascii", "ignore").decode("ascii")
    return ascii_str.lower().strip()


def _teams_match(sb_name: str, sm_name: str, sm_code: str) -> bool:
    """Determina si un equipo de Supabase matchea un equipo de Sportmonks."""
    sb_norm = _normalize_team_name(sb_name)
    sm_norm = _normalize_team_name(sm_name or "")
    sm_code_up = (sm_code or "").upper()

    if sb_norm and sm_norm:
        if sb_norm in sm_norm or sm_norm in sb_norm:
            return True

    if sm_code_up and sm_code_up in _CODE_TO_NAMES:
        known_norms = [_normalize_team_name(n) for n in _CODE_TO_NAMES[sm_code_up]]
        if sb_norm in known_norms or any(sb_norm in n or n in sb_norm for n in known_norms):
            return True

    if sb_norm in _NAME_TO_CODE:
        if _NAME_TO_CODE[sb_norm] == sm_code_up:
            return True

    return False


def _link_unmatched_fixtures(sb) -> None:
    """
    Para cada partido en Supabase sin sportmonks_id, busca el fixture
    correspondiente en Sportmonks usando fecha + nombre de equipos.
    Usa paginación (per_page=25) para obtener todos los fixtures de la temporada.
    Ignora fixtures placeholder (equipos genéricos de eliminatoria).
    """
    unlinked_res = sb.table("matches").select(
        "id, match_date, "
        "home_team:teams!matches_home_team_id_fkey(name, code), "
        "away_team:teams!matches_away_team_id_fkey(name, code)"
    ).is_("sportmonks_id", "null").execute()
    unlinked = unlinked_res.data or []
    if not unlinked:
        logger.info("Linking: todos los partidos ya tienen sportmonks_id")
        return
    logger.info("Intentando linkear %d partidos sin sportmonks_id", len(unlinked))

    # Fetch todos los fixtures de la temporada con paginación (max 25 por página)
    all_season_fixtures = []
    try:
        page = 1
        while True:
            raw_data = _sm_get(
                "/fixtures",
                {
                    "filters": f"fixtureSeasons:{SM_SEASON_ID}",
                    "include": "participants;state",
                    "per_page": "25",
                    "page": str(page),
                }
            )
            page_fixtures = raw_data.get("data") or []
            all_season_fixtures.extend(page_fixtures)
            pagination = raw_data.get("pagination") or {}
            if not pagination.get("has_more", False):
                break
            page += 1
            if page > 20:  # safety cap
                break
        logger.info("Sportmonks: %d fixtures totales para temporada %s (%d páginas)", len(all_season_fixtures), SM_SEASON_ID, page)
    except Exception as fetch_err:
        logger.error("Error fetching season fixtures para linking: %s", fetch_err)
        return

    if not all_season_fixtures:
        logger.warning("Linking: Sportmonks no devolvió fixtures para temporada %s", SM_SEASON_ID)
        return

    # Filtrar placeholders (eliminatoria sin equipos definidos aún)
    real_fixtures = [
        f for f in all_season_fixtures
        if not f.get("placeholder") and all(
            not p.get("placeholder") and p.get("short_code")
            for p in (f.get("participants") or [])
        )
    ]
    logger.info("Fixtures reales (no placeholder): %d", len(real_fixtures))

    # Agrupar por fecha
    sm_by_date: dict = {}
    for rf in real_fixtures:
        starting_at = rf.get("starting_at") or ""
        dk = starting_at[:10]
        sm_by_date.setdefault(dk, []).append(rf)

    linked_count = 0
    not_linked = []

    for match in unlinked:
        raw_md = match.get("match_date") or ""
        if not raw_md:
            continue
        date_key = raw_md[:10]
        candidates = sm_by_date.get(date_key, [])
        home_name = (match.get("home_team") or {}).get("name", "")
        away_name = (match.get("away_team") or {}).get("name", "")

        if not candidates:
            not_linked.append(f"{home_name} vs {away_name} (sin fixtures en fecha {date_key})")
            continue

        found = False
        for rf in candidates:
            participants = rf.get("participants") or []
            home_sm = next((p for p in participants if (p.get("meta") or {}).get("location") == "home"), None)
            away_sm = next((p for p in participants if (p.get("meta") or {}).get("location") == "away"), None)
            if not home_sm or not away_sm:
                continue
            home_sm_code = home_sm.get("short_code", "") or ""
            away_sm_code = away_sm.get("short_code", "") or ""
            if (
                _teams_match(home_name, home_sm.get("name", ""), home_sm_code)
                and _teams_match(away_name, away_sm.get("name", ""), away_sm_code)
            ):
                sm_fixture_id = rf.get("id")
                sb.table("matches").update({"sportmonks_id": sm_fixture_id}).eq("id", match["id"]).execute()
                logger.info("Linkeado: %s vs %s → Sportmonks ID %s", home_name, away_name, sm_fixture_id)
                linked_count += 1
                found = True
                break

        if not found:
            not_linked.append(f"{home_name} vs {away_name} (fecha {date_key}, {len(candidates)} candidatos)")

    if linked_count:
        logger.info("Linking completado: %d partidos linkeados", linked_count)
    for nl in not_linked:
        logger.warning("No se pudo linkear: %s", nl)


def _sync_standings_to_db(sb) -> None:
    """
    Fetch current standings from Sportmonks and upsert into group_standings table.
    Called after a group match finishes.
    """
    try:
        raw_data = _sm_get(
            f"/standings/seasons/{SM_SEASON_ID}",
            {"include": "participant;details.type;group", "per_page": "50"}
        )
        raw_standings = raw_data.get("data") or []
        if not raw_standings:
            return

        # Fetch team IDs from Supabase (code → id)
        teams_res = sb.table("teams").select("id, code").execute()
        code_to_id = {t["code"]: t["id"] for t in (teams_res.data or [])}

        rows = []
        for entry in raw_standings:
            grp_obj = entry.get("group") or {}
            grp_name = (grp_obj.get("name") or "").replace("Group ", "").strip()
            if not grp_name:
                continue
            participant = entry.get("participant") or {}
            sm_code = participant.get("short_code", "")
            # Map SM code to Supabase code via _CODE_TO_NAMES
            team_id = code_to_id.get(sm_code)
            if not team_id:
                # Try by name match
                sm_name = participant.get("name", "")
                for sb_code, sb_id in code_to_id.items():
                    for alias in _CODE_TO_NAMES.get(sm_code, []):
                        if _normalize_team_name(alias) == _normalize_team_name(sm_name):
                            team_id = sb_id
                            break
                    if team_id:
                        break
            if not team_id:
                continue

            detail_map = {d["type_id"]: d["value"] for d in (entry.get("details") or [])}
            rows.append({
                "group_name": grp_name,
                "team_id": team_id,
                "position": entry.get("position", 0),
                "played":  detail_map.get(129, 0),
                "won":     detail_map.get(130, 0),
                "drawn":   detail_map.get(131, 0),
                "lost":    detail_map.get(132, 0),
                "goals_for":     detail_map.get(133, 0),
                "goals_against": detail_map.get(134, 0),
                "points":  entry.get("points", 0),
            })

        if rows:
            sb.table("group_standings").upsert(rows, on_conflict="group_name,team_id").execute()
            logger.info("group_standings actualizado: %d filas", len(rows))
    except Exception as e:
        logger.error("_sync_standings_to_db error: %s", e)


def _update_ko_placeholders(sb) -> None:
    """
    Check Sportmonks for KO fixtures that now have real teams (no longer placeholder).
    Update home_team_id and away_team_id in Supabase matches.
    """
    try:
        # Fetch KO fixtures from SM (non-group stage, may now have real teams)
        all_fixtures = []
        page = 1
        while True:
            raw = _sm_get(
                "/fixtures",
                {"filters": f"fixtureSeasons:{SM_SEASON_ID}", "include": "participants;state", "per_page": "25", "page": str(page)}
            )
            chunk = raw.get("data") or []
            all_fixtures.extend(chunk)
            if not (raw.get("pagination") or {}).get("has_more", False):
                break
            page += 1
            if page > 20:
                break

        # Only care about non-placeholder KO fixtures
        ko_real = [
            f for f in all_fixtures
            if not f.get("placeholder")
            and f.get("group_id") is None  # group_id=null means it's a KO fixture
            and all(not p.get("placeholder") and p.get("short_code") for p in (f.get("participants") or []))
        ]
        if not ko_real:
            return

        # Load our KO matches that don't have teams yet
        ko_phases = ["r16", "qf", "sf", "third", "final"]
        our_ko = sb.table("matches").select("id, sportmonks_id, phase").in_("phase", ko_phases).is_("home_team_id", "null").execute()
        if not (our_ko.data or []):
            return

        # Fetch team code→id map
        teams_res = sb.table("teams").select("id, code, name").execute()
        code_to_id = {t["code"]: t["id"] for t in (teams_res.data or [])}

        sm_map = {f["id"]: f for f in ko_real}
        for match in (our_ko.data or []):
            sm_id = match.get("sportmonks_id")
            if not sm_id or sm_id not in sm_map:
                continue
            f = sm_map[sm_id]
            participants = f.get("participants") or []
            home_sm = next((p for p in participants if (p.get("meta") or {}).get("location") == "home"), None)
            away_sm = next((p for p in participants if (p.get("meta") or {}).get("location") == "away"), None)
            if not home_sm or not away_sm:
                continue
            home_id = code_to_id.get(home_sm.get("short_code", ""))
            away_id = code_to_id.get(away_sm.get("short_code", ""))
            if home_id and away_id:
                sb.table("matches").update({
                    "home_team_id": home_id,
                    "away_team_id": away_id,
                }).eq("id", match["id"]).execute()
                logger.info("KO match %s updated: %s vs %s", match["id"], home_sm.get("name"), away_sm.get("name"))
    except Exception as e:
        logger.error("_update_ko_placeholders error: %s", e)


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


        # Orphan rescue: partidos no-finished con sportmonks_id y match_date < now-2h
        try:
            from datetime import datetime, timezone, timedelta
            _orp_cutoff = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
            _orp_res = sb.table("matches").select("id,sportmonks_id,status").neq("status", "finished").lt("match_date", _orp_cutoff).not_.is_("sportmonks_id", "null").execute()
            _orphans = _orp_res.data or []
            if _orphans:
                logger.info("Orphan rescue: %d partidos con sportmonks_id y match_date antiguo", len(_orphans))
                for _om in _orphans:
                    _sm_id = _om.get("sportmonks_id")
                    if not _sm_id:
                        continue
                    try:
                        _fx_raw = _sm_get(f"/fixtures/{_sm_id}", {"include": "participants;scores"})
                        _fx = (_fx_raw.get("data") or {}) if _fx_raw else {}
                        _p = _parse_fixture(_fx) if _fx else None
                        if not _p:
                            continue
                        if _p.get("status") in ("finished",) and _p.get("home_score") is not None:
                            sb.table("matches").update({
                                "home_score": _p["home_score"],
                                "away_score": _p["away_score"],
                                "status": "finished",
                                "predictions_locked": True,
                            }).eq("id", _om["id"]).execute()
                            try:
                                sb.rpc("calculate_match_points", {"match_id_param": _om["id"]}).execute()
                            except Exception:
                                pass
                            logger.info("Orphan rescued finished: match_id=%s sm=%s %s-%s", _om["id"], _sm_id, _p["home_score"], _p["away_score"])
                        elif _p.get("status") == "live" and _p.get("home_score") is not None:
                            sb.table("matches").update({
                                "home_score": _p["home_score"],
                                "away_score": _p["away_score"],
                                "status": "live",
                                "predictions_locked": True,
                            }).eq("id", _om["id"]).execute()
                            logger.info("Orphan updated live: match_id=%s sm=%s %s-%s", _om["id"], _sm_id, _p["home_score"], _p["away_score"])
                    except Exception as _oe:
                        logger.error("Orphan fetch sm_id=%s: %s", _sm_id, _oe)
        except Exception as _orp_e:
            logger.error("Orphan rescue failed: %s", _orp_e)

        # ── Lockear partidos que empiezan en menos de 30 minutos ──────────────────
        try:
            from datetime import datetime, timezone, timedelta
            lock_cutoff = datetime.now(timezone.utc) + timedelta(minutes=30)
            sb.table("matches")            .update({"predictions_locked": True})            .eq("predictions_locked", False)            .eq("status", "scheduled")            .lte("match_date", lock_cutoff.isoformat())            .execute()
            logger.info("Auto-lock: partidos con match_date <= %s bloqueados", lock_cutoff.isoformat())
        except Exception as lock_err:
            logger.error("Error en auto-lock de partidos: %s", lock_err)

        # ── Linking: asignar sportmonks_id a partidos sin él ────────────────
        try:
            _link_unmatched_fixtures(sb)
        except Exception as link_err:
            logger.error("Error en linking de partidos: %s", link_err)


        # ── Fetch today's fixtures from Sportmonks ─────────────────────────
        from datetime import date
        today = date.today().isoformat()
        try:
            from datetime import date as _date, timedelta as _td
            _today = _date.today().isoformat()
            _yesterday = (_date.today() - _td(days=1)).isoformat()
            _all_today = []
            _page = 1
            while True:
                _d = _sm_get(
                    f"/fixtures/between/2026-06-11/2026-07-19",
                    {
                        "filters": f"fixtureLeagues:{SM_LEAGUE_ID}",
                        "include": "participants;scores;state",
                        "per_page": "25",
                        "page": str(_page),
                    }
                )
                _chunk = _d.get("data") or []
                _all_today.extend([x for x in _chunk if (x.get("starting_at") or "")[:10] >= _yesterday])
                _pag = _d.get("pagination") or {}
                if not _pag.get("has_more", False):
                    break
                _page += 1
                if _page > 10:
                    break
            data = {"data": _all_today}
        except Exception as e:
            logger.warning("Sportmonks fixtures fetch error: %s", e)
            return

        fixtures = data.get("data") or []
        logger.warning("[SYNC] Sportmonks fixtures hoy: %d", len(fixtures))
        if not fixtures:
            return



        # ── Build a map: sportmonks_id -> parsed fixture ───────────────────
        sm_map = {f["sportmonks_id"]: f for f in [_parse_fixture(fx) for fx in fixtures]}
        for _fx_dbg in list(sm_map.values())[:5]:
            logger.warning("[SYNC] Fixture SM: sm_id=%s state_short=%s status=%s home=%s away=%s", _fx_dbg.get('sportmonks_id'), _fx_dbg.get('state_short'), _fx_dbg.get('status'), _fx_dbg.get('home_score'), _fx_dbg.get('away_score'))

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

        # ── After a group match finishes: sync standings + KO placeholders ──
        if sm["status"] == "finished" and om.get("status") != "finished":
            if om.get("phase") == "group":
                try:
                    _sync_standings_to_db(sb)
                except Exception as std_e:
                    logger.error("standings sync error: %s", std_e)
                try:
                    _update_ko_placeholders(sb)
                except Exception as ko_e:
                    logger.error("ko placeholder update error: %s", ko_e)


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
