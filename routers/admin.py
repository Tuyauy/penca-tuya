"""
Router de administración - Panel de control
"""
from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel
from typing import Optional
from database import get_supabase
from auth_utils import require_admin

router = APIRouter()


class MatchCreate(BaseModel):
    match_number: Optional[int] = None
    phase: str  # group, r16, qf, sf, third, final
    group_name: Optional[str] = None
    home_team_id: Optional[int] = None
    away_team_id: Optional[int] = None
    home_team_placeholder: Optional[str] = None
    away_team_placeholder: Optional[str] = None
    match_date: Optional[str] = None
    venue: Optional[str] = None


class MatchUpdate(BaseModel):
    home_team_id: Optional[int] = None
    away_team_id: Optional[int] = None
    home_team_placeholder: Optional[str] = None
    away_team_placeholder: Optional[str] = None
    match_date: Optional[str] = None
    venue: Optional[str] = None
    status: Optional[str] = None
    predictions_locked: Optional[bool] = None


class ResultUpdate(BaseModel):
    home_score: int
    away_score: int
    extra_time: bool = False
    penalties: bool = False
    penalty_winner_id: Optional[int] = None


class TeamCreate(BaseModel):
    name: str
    code: str
    group_name: Optional[str] = None
    flag_url: Optional[str] = None


@router.get("/matches")
async def admin_get_matches(
    phase: Optional[str] = None,
    admin: dict = Depends(require_admin)
):
    """Listar todos los partidos"""
    sb = get_supabase()
    query = sb.table("matches").select("""
        *,
        home_team:teams!matches_home_team_id_fkey(id, name, code),
        away_team:teams!matches_away_team_id_fkey(id, name, code)
    """)
    if phase:
        query = query.eq("phase", phase)
    result = query.order("match_date").execute()
    return result.data or []


@router.post("/matches")
async def admin_create_match(
    match: MatchCreate,
    admin: dict = Depends(require_admin)
):
    """Crear un nuevo partido"""
    sb = get_supabase()
    result = sb.table("matches").insert(match.dict(exclude_none=True)).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Error al crear el partido")
    return result.data[0]


@router.patch("/matches/{match_id}")
async def admin_update_match(
    match_id: int,
    update: MatchUpdate,
    admin: dict = Depends(require_admin)
):
    """Actualizar información de un partido"""
    sb = get_supabase()
    data = {k: v for k, v in update.dict().items() if v is not None}
    result = sb.table("matches").update(data).eq("id", match_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Partido no encontrado")
    return result.data[0]


@router.post("/matches/{match_id}/result")
async def admin_set_result(
    match_id: int,
    result_data: ResultUpdate,
    admin: dict = Depends(require_admin)
):
    """Cargar el resultado de un partido y calcular puntos automáticamente"""
    sb = get_supabase()
    
    # Actualizar resultado
    update = {
        "home_score": result_data.home_score,
        "away_score": result_data.away_score,
        "extra_time": result_data.extra_time,
        "penalties": result_data.penalties,
        "penalty_winner_id": result_data.penalty_winner_id,
        "status": "finished",
        "predictions_locked": True
    }
    
    match_result = sb.table("matches").update(update).eq("id", match_id).execute()
    
    if not match_result.data:
        raise HTTPException(status_code=404, detail="Partido no encontrado")
    
    # Calcular puntos via función SQL
    try:
        sb.rpc("calculate_match_points", {"match_id_param": match_id}).execute()
        calculated = True
        message = "Resultado cargado y puntos calculados correctamente"
    except Exception as e:
        calculated = False
        message = f"Resultado cargado pero error al calcular puntos: {str(e)}"
    
    return {
        "message": message,
        "match": match_result.data[0],
        "points_calculated": calculated
    }


@router.post("/matches/{match_id}/lock")
async def admin_lock_match(
    match_id: int,
    admin: dict = Depends(require_admin)
):
    """Bloquear predicciones para un partido (cuando empieza)"""
    sb = get_supabase()
    result = sb.table("matches").update({
        "predictions_locked": True,
        "status": "live"
    }).eq("id", match_id).execute()
    
    if not result.data:
        raise HTTPException(status_code=404, detail="Partido no encontrado")
    
    return {"message": "Partido bloqueado correctamente"}


@router.get("/teams")
async def admin_get_teams(admin: dict = Depends(require_admin)):
    """Listar todos los equipos"""
    sb = get_supabase()
    result = sb.table("teams").select("*").order("group_name").order("name").execute()
    return result.data or []


@router.post("/teams")
async def admin_create_team(
    team: TeamCreate,
    admin: dict = Depends(require_admin)
):
    """Crear un equipo"""
    sb = get_supabase()
    result = sb.table("teams").insert(team.dict(exclude_none=True)).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Error al crear el equipo")
    return result.data[0]


@router.get("/users")
async def admin_get_users(
    limit: int = 100,
    admin: dict = Depends(require_admin)
):
    """Listar todos los usuarios"""
    sb = get_supabase()
    result = sb.table("penca_users").select(
        "id, email, username, full_name, total_points, prediction_points, purchase_points, created_at"
    ).order("total_points", desc=True).limit(limit).execute()
    return result.data or []


@router.post("/users/{user_id}/grant-admin")
async def admin_grant_admin(
    user_id: str,
    admin: dict = Depends(require_admin)
):
    """Dar permisos de admin a un usuario"""
    sb = get_supabase()
    
    # Primero verificar si la columna is_admin existe
    result = sb.table("penca_users").update({"is_admin": True}).eq("id", user_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return {"message": "Permisos de admin otorgados"}


@router.get("/stats")
async def admin_stats(admin: dict = Depends(require_admin)):
    """Estadísticas generales para el admin"""
    sb = get_supabase()
    
    users = sb.table("penca_users").select("id", count="exact").execute()
    preds = sb.table("predictions").select("id", count="exact").execute()
    finished = sb.table("matches").select("id", count="exact").eq("status", "finished").execute()
    pending = sb.table("matches").select("id", count="exact").eq("status", "scheduled").execute()
    purchases = sb.table("purchase_points").select("id", count="exact").execute()
    
    return {
        "total_users": users.count or 0,
        "total_predictions": preds.count or 0,
        "matches_finished": finished.count or 0,
        "matches_pending": pending.count or 0,
        "total_purchases_registered": purchases.count or 0
    }


# GET /admin/set-result?match_id=X&home=Y&away=Z
@router.get("/set-result")
async def admin_set_result_get(
    match_id: int,
    home: int,
    away: int,
    admin: dict = Depends(require_admin),
):
    """Carga resultado manualmente desde el browser (sin POST body)."""
    sb = get_supabase()
    sb.table("matches").update({
        "home_score": home,
        "away_score": away,
        "status": "finished",
        "predictions_locked": True,
    }).eq("id", match_id).execute()
    try:
        sb.rpc("calculate_match_points", {"match_id_param": match_id}).execute()
        points_ok = True
    except Exception as e:
        points_ok = str(e)
    return {"ok": True, "match_id": match_id, "resultado": f"{home}-{away}", "puntos": points_ok}


# GET /admin/pending-matches
@router.get("/pending-matches")
async def admin_pending_matches(admin: dict = Depends(require_admin)):
    """Partidos sin resultado cuya fecha ya paso."""
    from datetime import datetime, timezone
    sb = get_supabase()
    now_iso = datetime.now(timezone.utc).isoformat()
    res = (
        sb.table("matches")
        .select("id, match_number, phase, group_name, home_team_id, away_team_id, match_date, status, home_score, away_score, sportmonks_id")
        .neq("status", "finished")
        .lt("match_date", now_iso)
        .order("match_date")
        .execute()
    )
    return {"pending": res.data, "count": len(res.data)}
