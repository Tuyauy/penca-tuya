"""
Router de partidos
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import Optional, List
from database import get_supabase
from auth_utils import get_current_user_optional

router = APIRouter()

PHASE_ORDER = {
    'group': 1,
    'r16': 2,
    'qf': 3,
    'sf': 4,
    'third': 5,
    'final': 6
}

PHASE_LABELS = {
    'group': 'Fase de Grupos',
    'r16': 'Dieciseisavos de Final',
    'qf': 'Cuartos de Final',
    'sf': 'Semifinales',
    'third': 'Tercer y Cuarto Puesto',
    'final': 'Final'
}


@router.get("/")
async def get_matches(
    phase: Optional[str] = None,
    group: Optional[str] = None,
    user_data: Optional[dict] = Depends(get_current_user_optional)
):
    """Obtener todos los partidos, opcionalmente filtrados por fase y grupo"""
    sb = get_supabase()
    
    query = sb.table("matches").select("*")
    
    if phase:
        query = query.eq("phase", phase)
    if group:
        query = query.eq("group_name", group)
    
    result = query.order("match_date").execute()
    matches = result.data or []
    
    # Si hay usuario, agregar sus predicciones
    if user_data and matches:
        match_ids = [m["id"] for m in matches]
        preds_result = sb.table("predictions").select("*").eq(
            "user_id", user_data["sub"]
        ).in_("match_id", match_ids).execute()
        
        preds_map = {p["match_id"]: p for p in (preds_result.data or [])}
        
        for match in matches:
            match["user_prediction"] = preds_map.get(match["id"])
    
    # Agrupar por fase
    grouped = {}
    for match in matches:
        phase_key = match["phase"]
        if phase_key not in grouped:
            grouped[phase_key] = {
                "phase": phase_key,
                "label": PHASE_LABELS.get(phase_key, phase_key),
                "order": PHASE_ORDER.get(phase_key, 99),
                "matches": []
            }
        grouped[phase_key]["matches"].append(match)
    
    # Ordenar por fase
    sorted_phases = sorted(grouped.values(), key=lambda x: x["order"])
    
    return {"phases": sorted_phases, "total": len(matches)}


@router.get("/upcoming")
async def get_upcoming_matches(
    limit: int = 5,
    user_data: Optional[dict] = Depends(get_current_user_optional)
):
    """Próximos partidos disponibles para predecir"""
    sb = get_supabase()
    
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    
    result = sb.table("matches").select("""
        *,
        home_team:home_team_id(id, name, code, flag_url),
        away_team:away_team_id(id, name, code, flag_url)
    """).eq("status", "scheduled").eq("predictions_locked", False).gte(
        "match_date", now
    ).order("match_date").limit(limit).execute()
    
    matches = result.data or []
    
    if user_data and matches:
        match_ids = [m["id"] for m in matches]
        preds_result = sb.table("predictions").select("*").eq(
            "user_id", user_data["sub"]
        ).in_("match_id", match_ids).execute()
        preds_map = {p["match_id"]: p for p in (preds_result.data or [])}
        for match in matches:
            match["user_prediction"] = preds_map.get(match["id"])
    
    return matches


@router.get("/groups")
async def get_groups():
    """Obtener todos los grupos y sus equipos"""
    sb = get_supabase()
    result = sb.table("teams").select("*").order("group_name").order("name").execute()
    
    groups = {}
    for team in (result.data or []):
        g = team.get("group_name", "?")
        if g not in groups:
            groups[g] = {"group": g, "teams": []}
        groups[g]["teams"].append(team)
    
    return sorted(groups.values(), key=lambda x: x["group"])


@router.get("/{match_id}")
async def get_match(match_id: int):
    """Obtener un partido específico"""
    sb = get_supabase()
    result = sb.table("matches").select("*").eq("id", match_id).execute()
    
    if not result.data:
        raise HTTPException(status_code=404, detail="Partido no encontrado")
    
    return result.data[0]
